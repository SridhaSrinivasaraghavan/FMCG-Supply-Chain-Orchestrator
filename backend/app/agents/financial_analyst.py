"""
Agent 3: Financial Analyst Agent (Smart CFO Upgrade)

Phase 1: Deterministic math to calculate backup premiums and idle costs.
Phase 2: Uses an LLM (acting as CFO) to review the math, quality tradeoffs (reliability scores),
company rules, and the Risk Assessment's indirect delay estimates to make a final 
strategic decision: EXECUTE_BACKUP_PO, HOLD_AND_MONITOR, or PROACTIVE_ADVISORY.
"""
from app.agents.state import AgentState
from app.config import settings
from app.services.llm_factory import get_llm
from langchain_core.prompts import PromptTemplate
import json
import logging

logger = logging.getLogger(__name__)


CFO_DECISION_PROMPT = PromptTemplate(
    template="""You are the Chief Financial Officer (CFO) of a major FMCG company.

Your Risk Assessment team has provided an analysis of a new threat, and your quantitative systems have run the raw financial math for backup supplier options.

## Threat & Risk Assessment
- News Event: {threat_summary}
- Risk Analyst's Reasoning: {risk_reasoning}

## Raw Financial Math (Cost/Benefit for Backups)
{financial_math}

## COMPANY POLICY
1. **Quality over Price**: Do not compromise on quality. If a backup supplier has a reliability score < 0.90, strongly prefer avoiding them unless the delay is catastrophic (factory goes idle).
2. **Proactive Advisories**: If the delay is minor (e.g., a few hours of traffic) and the shipment can still make it, recommend a PROACTIVE_ADVISORY to ask the current vendor to ship early. Do not waste money on backups for minor logistics delays.
3. **Hold & Monitor**: If the delay is manageable and we have plenty of buffer stock, recommend HOLD_AND_MONITOR to save money.
4. **Emergency PO**: If the factory is at risk of going idle (negative net savings, or days_remaining < delay_days), recommend EXECUTE_BACKUP_PO with the best quality/price backup.

## Your Task
Review the math and the risk reasoning. For each impacted material, decide on the best course of action.

Respond ONLY with a valid JSON array of objects, like this:
[
  {{
    "material_id": 1,
    "material_name": "Grade-A Wheat Flour",
    "recommendation": "PROACTIVE_ADVISORY",
    "rationale": "The marathon on NH-44 causes a 5-hour delay. We have 10 days of stock, so the factory won't go idle, but requesting early dispatch ensures we don't miss the receiving window."
  }}
]

IMPORTANT: ONLY output raw JSON. Do not use markdown blocks.
""",
    input_variables=["threat_summary", "risk_reasoning", "financial_math"],
)


def financial_analyst_node(state: AgentState):
    print("--- FINANCIAL ANALYST (CFO) AGENT ---")
    impacted_materials = state.get("impacted_materials", [])
    threat_payload = state.get("threat_payload", {})
    risk_reasoning = state.get("risk_reasoning", "No indirect risks identified.")
    
    # If the Risk Analyst determined there's an indirect delay, we would parse it.
    # For now, we rely on the direct delay_days for the raw math, but the LLM reads the risk_reasoning for nuance.
    delay_days = threat_payload.get("estimated_delay_days", 7)
    
    if not impacted_materials:
        return {"financial_analysis": [], "recommended_actions": []}
        
    # 1. Run the raw quantitative math
    raw_math_results = []
    
    for mat in impacted_materials:
        days_remaining = mat["current_stock"] / mat["daily_consumption_rate"]
        idle_days = max(0, delay_days - days_remaining)
        factory_idle_cost = settings.FACTORY_IDLE_COST_PER_DAY * idle_days
        
        best_alt = None
        alts_info = []
        
        if mat["alternate_suppliers"]:
            # Evaluate all alternates for the LLM to see
            for alt in mat["alternate_suppliers"]:
                primary_assumed_price = alt["unit_price"] * 0.8 
                order_qty = mat["daily_consumption_rate"] * (delay_days + 2)
                backup_premium = (alt["unit_price"] - primary_assumed_price) * order_qty
                
                alt_dict = {
                    "supplier_id": alt["supplier_id"],
                    "supplier_name": alt["name"],
                    "unit_price": alt["unit_price"],
                    "reliability_score": alt["reliability_score"],
                    "backup_premium": backup_premium,
                    "order_qty": order_qty,
                    "total_cost": alt["unit_price"] * order_qty
                }
                alts_info.append(alt_dict)
                
                if not best_alt or alt["unit_price"] < best_alt["unit_price"]:
                    best_alt = alt_dict
        
        raw_math_results.append({
            "material_id": mat["material_id"],
            "material_name": mat["name"],
            "days_remaining": round(days_remaining, 1),
            "delay_days": delay_days,
            "factory_idle_cost": factory_idle_cost,
            "alternates": alts_info,
            "best_fallback_assumed": best_alt
        })
        
    # 2. Ask the CFO LLM to make the final decision based on company policy
    llm = get_llm("financial_analyst")
    
    if hasattr(llm, '_llm_type') and llm._llm_type == "fake-mock-llm":
        # Fallback to deterministic logic if testing without LLM
        analysis_results = []
        for r in raw_math_results:
            rec = "HOLD_AND_MONITOR"
            if r["factory_idle_cost"] > 0 and r["alternates"]:
                rec = "EXECUTE_BACKUP_PO"
            
            analysis_results.append({
                "material_id": r["material_id"],
                "material_name": r["material_name"],
                "recommendation": rec,
                "rationale": "Mock mode deterministic fallback.",
                "best_alternate": r["best_fallback_assumed"],
                "order_qty": r.get("best_fallback_assumed", {}).get("order_qty", 0) if r.get("best_fallback_assumed") else 0,
                "total_cost": r.get("best_fallback_assumed", {}).get("total_cost", 0) if r.get("best_fallback_assumed") else 0
            })
        return {"financial_analysis": analysis_results}
        
    try:
        prompt_text = CFO_DECISION_PROMPT.format(
            threat_summary=threat_payload.get("summary", "Unknown"),
            risk_reasoning=risk_reasoning,
            financial_math=json.dumps(raw_math_results, indent=2)
        )
        
        response = llm.invoke(prompt_text)
        content = response.content if hasattr(response, 'content') else str(response)
        
        # Clean up potential markdown from the LLM
        content = content.replace("```json", "").replace("```", "").strip()
        cfo_decisions = json.loads(content)
        
        # Merge the CFO's decision back into the raw math results for the Strategy Execution agent
        final_analysis = []
        for r in raw_math_results:
            # Find matching decision
            decision = next((d for d in cfo_decisions if str(d.get("material_id")) == str(r["material_id"])), {})
            
            final_analysis.append({
                "material_id": r["material_id"],
                "material_name": r["material_name"],
                "recommendation": decision.get("recommendation", "HOLD_AND_MONITOR"),
                "rationale": decision.get("rationale", "No rationale provided by CFO."),
                "best_alternate": r.get("best_fallback_assumed"),
                "order_qty": r.get("best_fallback_assumed", {}).get("order_qty", 0) if r.get("best_fallback_assumed") else 0,
                "total_cost": r.get("best_fallback_assumed", {}).get("total_cost", 0) if r.get("best_fallback_assumed") else 0
            })
            
            print(f"  CFO Decision for {r['material_name']}: {decision.get('recommendation')} - {decision.get('rationale')[:60]}...")
            
        return {"financial_analysis": final_analysis}
        
    except Exception as e:
        logger.error(f"CFO LLM reasoning failed: {e}")
        return {"error": str(e)}
