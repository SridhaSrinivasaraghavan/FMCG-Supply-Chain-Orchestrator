"""
Agent 3: Financial Analyst Agent (Smart CFO)

Phase 1: Deterministic math to calculate backup premiums and idle costs.
Phase 2: Uses an LLM (acting as CFO) to review the math, quality tradeoffs,
         company rules, and BOM impact to make a final strategic decision:
         EXECUTE_BACKUP_PO, HOLD_AND_MONITOR, or PROACTIVE_ADVISORY.

Improvements:
- Fetches actual primary supplier prices from DB (no more hardcoded 0.8 assumption)
- BOM integration: calculates which products are affected by material shortages
- Explicit numerical Decision Matrix in prompt (reduces hallucination)
- Validated output via CFODecision schema with enum enforcement
- Carries primary_supplier_id through to Strategy Execution
- Cost ceiling check before recommending EXECUTE_BACKUP_PO
"""
from app.agents.state import AgentState
from app.agents.validators import validate_cfo_decisions
from app.config import settings
from app.services.llm_factory import get_llm
from app.services.llm_utils import invoke_llm_with_retry, parse_llm_json
from app.tools.db_tools import get_primary_supplier_price, get_bom_impact
from langchain_core.prompts import PromptTemplate
import json
import logging

logger = logging.getLogger(__name__)

# Maximum cost for an autonomous PO (above this, flag for human review)
MAX_AUTO_PO_COST = getattr(settings, 'MAX_AUTO_PO_COST', 100000.0)


CFO_DECISION_PROMPT = PromptTemplate(
    template="""You are the Chief Financial Officer (CFO) of a major FMCG company.

Your Risk Assessment team has analyzed a new threat, and your quantitative systems have run the raw financial math.

## Threat & Risk Assessment
- News Event: {threat_summary}
- Risk Analyst's Reasoning: {risk_reasoning}

## Product Impact (Bill of Materials)
{bom_impact}

## Raw Financial Math (Cost/Benefit for Backups)
{financial_math}

## DECISION POLICY — Apply EXACTLY in this order:
1. IF days_remaining < delay_days AND factory_idle_cost > 0 AND alternates exist with reliability ≥ 0.90:
   → EXECUTE_BACKUP_PO (pick supplier with highest reliability_score)
2. IF days_remaining < delay_days AND factory_idle_cost > 0 BUT no reliable alternates (all < 0.90):
   → EXECUTE_BACKUP_PO with best available (override quality rule to prevent factory idle)
3. IF days_remaining >= delay_days AND delay_days > 2:
   → PROACTIVE_ADVISORY (tell current vendor to dispatch early)
4. IF days_remaining >= delay_days AND delay_days <= 2:
   → HOLD_AND_MONITOR (buffer stock is sufficient)
5. IF no alternates available AND factory NOT at risk:
   → HOLD_AND_MONITOR

## Your Task
For EACH impacted material, apply the decision policy above and output your decision.

Output ONLY a JSON array (no markdown, no explanation):
[
  {{
    "material_id": 1,
    "material_name": "Grade-A Wheat Flour",
    "recommendation": "PROACTIVE_ADVISORY",
    "rationale": "We have 10 days of stock vs 5-day delay. Buffer is sufficient but requesting early dispatch to maintain safety margin."
  }}
]

VALID recommendation values: EXECUTE_BACKUP_PO, PROACTIVE_ADVISORY, HOLD_AND_MONITOR
""",
    input_variables=["threat_summary", "risk_reasoning", "bom_impact", "financial_math"],
)


def financial_analyst_node(state: AgentState):
    """Agent 3: Runs financial math + CFO policy decision for each impacted material."""
    pipeline_id = state.get("pipeline_run_id", "unknown")
    logger.info(f"[financial_analyst] Pipeline {pipeline_id}: Starting financial analysis")
    
    impacted_materials = state.get("impacted_materials", [])
    threat_payload = state.get("threat_payload", {})
    risk_reasoning = state.get("risk_reasoning", "No indirect risks identified.")
    
    delay_days = threat_payload.get("estimated_delay_days", 7)
    
    if not impacted_materials:
        logger.info(f"[financial_analyst] Pipeline {pipeline_id}: No impacted materials — nothing to analyze")
        return {"financial_analysis": [], "recommended_actions": []}
    
    # ── Step 1: Deterministic Financial Math ──
    raw_math_results = []
    valid_material_ids = set()
    
    for mat in impacted_materials:
        mat_id = mat["material_id"]
        valid_material_ids.add(mat_id)
        
        days_remaining = mat["current_stock"] / mat["daily_consumption_rate"] if mat["daily_consumption_rate"] > 0 else 999
        idle_days = max(0, delay_days - days_remaining)
        factory_idle_cost = settings.FACTORY_IDLE_COST_PER_DAY * idle_days
        
        # Get ACTUAL primary supplier price from DB (not hardcoded assumption)
        primary_price = get_primary_supplier_price(mat_id)
        
        best_alt = None
        alts_info = []
        
        if mat.get("alternate_suppliers"):
            for alt in mat["alternate_suppliers"]:
                # Calculate premium using REAL primary price
                actual_primary_price = primary_price if primary_price else alt["unit_price"] * 0.8
                order_qty = mat["daily_consumption_rate"] * (delay_days + 2)
                backup_premium = (alt["unit_price"] - actual_primary_price) * order_qty
                
                alt_dict = {
                    "supplier_id": alt["supplier_id"],
                    "supplier_name": alt["name"],
                    "unit_price": alt["unit_price"],
                    "reliability_score": alt["reliability_score"],
                    "lead_time_days": alt.get("lead_time_days", 0),
                    "backup_premium": round(backup_premium, 2),
                    "order_qty": round(order_qty, 2),
                    "total_cost": round(alt["unit_price"] * order_qty, 2),
                }
                alts_info.append(alt_dict)
                
                # Prefer highest reliability, then lowest price
                if not best_alt or alt["reliability_score"] > best_alt["reliability_score"]:
                    best_alt = alt_dict
                elif alt["reliability_score"] == best_alt["reliability_score"] and alt["unit_price"] < best_alt["unit_price"]:
                    best_alt = alt_dict
        
        raw_math_results.append({
            "material_id": mat_id,
            "material_name": mat["name"],
            "days_remaining": round(days_remaining, 1),
            "delay_days": delay_days,
            "factory_idle_cost": round(factory_idle_cost, 2),
            "primary_supplier_id": mat.get("primary_supplier_id"),
            "primary_supplier_name": mat.get("primary_supplier_name", "Unknown"),
            "primary_unit_price": primary_price,
            "alternates": alts_info,
            "best_fallback_assumed": best_alt,
        })
    
    logger.info(f"[financial_analyst] Pipeline {pipeline_id}: Math computed for {len(raw_math_results)} materials")
    
    # ── Step 1.5: BOM Impact Analysis ──
    bom_impact_text = _get_bom_impact_text(valid_material_ids, pipeline_id)
    
    # ── Step 2: CFO LLM Decision ──
    llm = get_llm("financial_analyst")
    
    if hasattr(llm, '_llm_type') and llm._llm_type == "fake-mock-llm":
        return _deterministic_fallback(raw_math_results, pipeline_id)
    
    try:
        prompt_text = CFO_DECISION_PROMPT.format(
            threat_summary=threat_payload.get("summary", "Unknown"),
            risk_reasoning=risk_reasoning,
            bom_impact=bom_impact_text,
            financial_math=json.dumps(raw_math_results, indent=2),
        )
        
        content = invoke_llm_with_retry(
            llm=llm,
            prompt_text=prompt_text,
            max_retries=2,
            pipeline_run_id=pipeline_id,
            agent_name="financial_analyst",
        )
        
        if content is None:
            logger.warning(f"[financial_analyst] Pipeline {pipeline_id}: CFO LLM failed — using deterministic fallback")
            return _deterministic_fallback(raw_math_results, pipeline_id)
        
        cfo_decisions_raw = parse_llm_json(content)
        
        if not isinstance(cfo_decisions_raw, list):
            cfo_decisions_raw = [cfo_decisions_raw] if isinstance(cfo_decisions_raw, dict) else []
        
        # Validate CFO decisions
        cfo_decisions = validate_cfo_decisions(cfo_decisions_raw, valid_material_ids)
        
        # Merge CFO decisions with raw math
        final_analysis = _merge_decisions(raw_math_results, cfo_decisions, pipeline_id)
        
        return {"financial_analysis": final_analysis}
        
    except Exception as e:
        logger.error(f"[financial_analyst] Pipeline {pipeline_id}: CFO LLM error — {e}. Using deterministic fallback.")
        return _deterministic_fallback(raw_math_results, pipeline_id)


def _get_bom_impact_text(material_ids: set, pipeline_id: str) -> str:
    """Fetches BOM impact for impacted materials — shows which products are affected."""
    try:
        bom_data = get_bom_impact(list(material_ids))
        if not bom_data:
            return "No BOM data available — unable to assess product-level impact."
        
        lines = []
        for item in bom_data:
            lines.append(
                f"- Product '{item['product_name']}' requires {item['required_quantity_per_unit']} "
                f"{item.get('unit', 'units')} of {item['material_name']} per unit. "
                f"If {item['material_name']} runs out, {item['product_name']} production STOPS."
            )
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"[financial_analyst] Pipeline {pipeline_id}: BOM lookup failed — {e}")
        return "BOM data unavailable."


def _merge_decisions(raw_math_results: list, cfo_decisions: list, pipeline_id: str) -> list:
    """Merges CFO LLM decisions back into the raw math results for Strategy Execution."""
    final_analysis = []
    
    for r in raw_math_results:
        decision = next(
            (d for d in cfo_decisions if d.get("material_id") == r["material_id"]),
            {}
        )
        
        rec = decision.get("recommendation", "HOLD_AND_MONITOR")
        rationale = decision.get("rationale", "No rationale provided by CFO.")
        
        # Cost ceiling check
        best_alt = r.get("best_fallback_assumed")
        total_cost = best_alt.get("total_cost", 0) if best_alt else 0
        
        if rec == "EXECUTE_BACKUP_PO" and total_cost > MAX_AUTO_PO_COST:
            logger.warning(
                f"[financial_analyst] Pipeline {pipeline_id}: PO cost ${total_cost:.2f} exceeds "
                f"ceiling ${MAX_AUTO_PO_COST:.2f} for {r['material_name']}. Flagging for human review."
            )
            rationale += f" [⚠️ COST CEILING EXCEEDED: ${total_cost:.2f} > ${MAX_AUTO_PO_COST:.2f}. Requires human approval.]"
        
        final_analysis.append({
            "material_id": r["material_id"],
            "material_name": r["material_name"],
            "recommendation": rec,
            "rationale": rationale,
            "best_alternate": best_alt,
            "primary_supplier_id": r.get("primary_supplier_id"),
            "primary_supplier_name": r.get("primary_supplier_name"),
            "order_qty": best_alt.get("order_qty", 0) if best_alt else 0,
            "total_cost": total_cost,
            "days_remaining": r["days_remaining"],
            "delay_days": r["delay_days"],
            "factory_idle_cost": r["factory_idle_cost"],
        })
        
        logger.info(f"[financial_analyst] Pipeline {pipeline_id}: {r['material_name']} → {rec}")
    
    return final_analysis


def _deterministic_fallback(raw_math_results: list, pipeline_id: str) -> dict:
    """Deterministic fallback when LLM is unavailable — applies the decision policy mechanically."""
    logger.info(f"[financial_analyst] Pipeline {pipeline_id}: Using deterministic fallback logic")
    analysis_results = []
    
    for r in raw_math_results:
        days_remaining = r["days_remaining"]
        delay_days = r["delay_days"]
        factory_idle_cost = r["factory_idle_cost"]
        best_alt = r.get("best_fallback_assumed")
        
        # Apply decision policy
        if factory_idle_cost > 0 and best_alt:
            rec = "EXECUTE_BACKUP_PO"
            rationale = (
                f"Factory idle risk: {days_remaining:.1f} days stock vs {delay_days} day delay. "
                f"Idle cost: ${factory_idle_cost:.2f}. Ordering from {best_alt['supplier_name']}."
            )
        elif days_remaining < delay_days and not best_alt:
            rec = "HOLD_AND_MONITOR"
            rationale = f"Factory at risk but no backup suppliers available. Manual intervention needed."
        elif delay_days > 2:
            rec = "PROACTIVE_ADVISORY"
            rationale = (
                f"Buffer sufficient ({days_remaining:.1f} days vs {delay_days} day delay) "
                f"but requesting early dispatch as precaution."
            )
        else:
            rec = "HOLD_AND_MONITOR"
            rationale = f"Delay of {delay_days} days is within safety buffer of {days_remaining:.1f} days."
        
        analysis_results.append({
            "material_id": r["material_id"],
            "material_name": r["material_name"],
            "recommendation": rec,
            "rationale": f"[Deterministic fallback] {rationale}",
            "best_alternate": best_alt,
            "primary_supplier_id": r.get("primary_supplier_id"),
            "primary_supplier_name": r.get("primary_supplier_name"),
            "order_qty": best_alt.get("order_qty", 0) if best_alt else 0,
            "total_cost": best_alt.get("total_cost", 0) if best_alt else 0,
            "days_remaining": days_remaining,
            "delay_days": delay_days,
            "factory_idle_cost": factory_idle_cost,
        })
    
    return {"financial_analysis": analysis_results}
