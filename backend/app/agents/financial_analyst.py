"""
Agent 3: Financial Analyst Agent (Smart CFO) — v3.1

New in v3.1:
- Routes to ApprovalQueue instead of creating PO when: cost > MAX_AUTO_PO_COST OR confidence < 60
- MOQ (minimum order quantity) and capacity check against backup supplier
- Passes confidence_score from Market Intel into routing decisions
"""
from app.agents.state import AgentState
from app.agents.validators import validate_cfo_decisions
from app.config import settings
from app.services.llm_factory import get_llm
from app.services.llm_utils import invoke_llm_with_retry, parse_llm_json
from app.tools.db_tools import get_primary_supplier_price, get_bom_impact
# pyrefly: ignore [missing-import]
from langchain_core.prompts import PromptTemplate
import json
import logging

logger = logging.getLogger(__name__)

MAX_AUTO_PO_COST = getattr(settings, 'MAX_AUTO_PO_COST', 100000.0)
LOW_CONFIDENCE_THRESHOLD = 60  # Below this → human review


CFO_DECISION_PROMPT = PromptTemplate(
    template="""You are the Chief Financial Officer (CFO) of a major FMCG company.

## Threat & Risk Assessment
- News Event: {threat_summary}
- Region Affected: {region}
- Estimated Delay: {delay_days} days
- Confidence Score: {confidence_score}/100

## Product Impact (Bill of Materials)
{bom_impact}

## Optimal Financial Decisions (Calculated by Quantitative Models)
{optimal_decisions}

## INSTRUCTIONS:
Our quantitative models have already computed the exact mathematically optimal decision for each impacted material to minimize Total Cost (Backup Premium + Factory Idle Cost). 
Your ONLY job is to read these decisions and write a highly detailed, professional CFO rationale explaining exactly WHY this decision makes financial sense. You MUST explicitly cite the specific costs involved, the mathematical differences between the options (like backup premium vs. factory idle cost), and the total potential avoided losses.

CRITICAL RULE 1: You MUST generate a rationale for EVERY SINGLE material provided in the input. Do NOT skip any materials. If the decision is PROACTIVE_ADVISORY or HOLD_AND_MONITOR because we have enough stock, explicitly explain that we avoid unnecessary backup costs because our current inventory covers the delay.
CRITICAL RULE 2: You are generating rationales for multiple different materials. You MUST ensure that the rationale for material A ONLY mentions material A. Do NOT copy the rationale from one material into another. Do NOT mention Cocoa Powder when discussing Palm Oil. Match the exact `material_name` provided in the input decisions.

Output ONLY a strict JSON array matching this format:
[
  {{
    "material_id": 123,
    "rationale": "<Write your highly detailed, multi-sentence rationale here explaining all the math and logic>"
  }}
]
""",
    input_variables=["threat_summary", "region", "delay_days", "risk_reasoning",
                     "confidence_score", "bom_impact", "optimal_decisions"],
)


def financial_analyst_node(state: AgentState):
    """Agent 3: Financial math + CFO decision. Routes high-cost/low-confidence items to approval queue."""
    pipeline_id = state.get("pipeline_run_id", "unknown")
    logger.info(f"[financial_analyst] Pipeline {pipeline_id}: Starting financial analysis")

    impacted_materials = state.get("impacted_materials", [])
    threat_payload = state.get("threat_payload", {})
    risk_reasoning = state.get("risk_reasoning", "No indirect risks identified.")
    confidence_score = state.get("confidence_score", 80)
    is_test = state.get("is_test", False)
    delay_days = threat_payload.get("estimated_delay_days", 7)

    if not impacted_materials:
        return {"financial_analysis": [], "approval_items": []}

    # ── Step 1: Deterministic Financial Math & BOM ──
    valid_material_ids = {mat["material_id"] for mat in impacted_materials}
    bom_data = get_bom_impact(list(valid_material_ids))
    
    # Precompute daily revenue loss per material based on products
    material_daily_loss = {}
    for item in bom_data:
        mat_id = item["material_id"]
        demand = item.get("daily_demand", 0)
        price = item.get("selling_price", 0)
        material_daily_loss[mat_id] = material_daily_loss.get(mat_id, 0) + (demand * price)

    raw_math_results = []
    
    for mat in impacted_materials:
        mat_id = mat["material_id"]
        daily_loss = material_daily_loss.get(mat_id, getattr(settings, 'FACTORY_IDLE_COST_PER_DAY', 50000))

        days_remaining = (
            mat["current_stock"] / mat["daily_consumption_rate"]
            if mat["daily_consumption_rate"] > 0 else 999
        )
        idle_days = max(0, delay_days - days_remaining)
        base_factory_idle_cost = daily_loss * idle_days

        primary_price = get_primary_supplier_price(mat_id)
        alts_info = []

        for alt in mat.get("alternate_suppliers", []):
            actual_primary = primary_price if primary_price else alt["unit_price"] * 0.85
            raw_order_qty = mat["daily_consumption_rate"] * (delay_days + 3)
            moq = alt.get("min_order_qty", 0)
            max_cap = alt.get("max_supply_capacity", 999999)
            order_qty = max(raw_order_qty, moq)
            order_qty = min(order_qty, max_cap)

            backup_premium = (alt["unit_price"] - actual_primary) * order_qty
            lead_time = alt.get("lead_time_days", 0)
            
            # If lead time > days remaining, factory idles while waiting for backup
            alt_idle_days = max(0, lead_time - days_remaining)
            alt_idle_cost = alt_idle_days * daily_loss
            
            alts_info.append({
                "supplier_id": alt["supplier_id"],
                "supplier_name": alt["name"],
                "unit_price": alt["unit_price"],
                "reliability_score": alt["reliability_score"],
                "lead_time_days": lead_time,
                "backup_premium": round(backup_premium, 2),
                "order_qty": round(order_qty, 2),
                "total_cost_of_goods": round(alt["unit_price"] * order_qty, 2),
                "projected_idle_cost_with_this_supplier": round(alt_idle_cost, 2),
                "total_financial_impact": round(backup_premium + alt_idle_cost, 2)
            })

        raw_math_results.append({
            "material_id": mat_id,
            "material_name": mat["name"],
            "days_remaining": round(days_remaining, 1),
            "delay_days": delay_days,
            "daily_revenue_loss": round(daily_loss, 2),
            "base_factory_idle_cost": round(base_factory_idle_cost, 2),
            "primary_supplier_id": mat.get("primary_supplier_id"),
            "primary_supplier_name": mat.get("primary_supplier_name", "Unknown"),
            "primary_supplier_lead_time_days": mat.get("primary_supplier_lead_time_days", 3),
            "primary_unit_price": primary_price,
            "alternates": alts_info
        })

    logger.info(f"[financial_analyst] Pipeline {pipeline_id}: Math computed for {len(raw_math_results)} materials")

    # ── Step 2: BOM Impact ──
    bom_impact_text = "No BOM data available."
    if bom_data:
        lines = []
        for item in bom_data:
            lines.append(f"- {item['product_name']} requires {item['required_quantity_per_unit']} {item['unit']} of {item['material_name']}. (Demand: {item['daily_demand']}/day, Price: ₹{item['selling_price']})")
        bom_impact_text = "\n".join(lines)

    # ── Step 3: Compute Optimal Decisions in Python ──
    optimal_decisions = []
    for r in raw_math_results:
        delay = r["delay_days"]
        remaining = r["days_remaining"]
        
        if remaining < delay and r["base_factory_idle_cost"] > 0 and r["alternates"]:
            best_alt = min(r["alternates"], key=lambda x: x["total_financial_impact"])
            optimal_decisions.append({
                "material_id": r["material_id"],
                "material_name": r["material_name"],
                "recommendation": "EXECUTE_BACKUP_PO",
                "backup_supplier_id": best_alt["supplier_id"],
                "backup_supplier_name": best_alt["supplier_name"],
                "financial_context": f"Factory idles in {remaining} days. Primary delayed {delay} days. Selected {best_alt['supplier_name']} because its total impact (Premium + Idle) is ₹{best_alt['total_financial_impact']}.",
                "best_alternate": best_alt
            })
        elif remaining >= delay and delay > 3:
            optimal_decisions.append({
                "material_id": r["material_id"],
                "material_name": r["material_name"],
                "recommendation": "PROACTIVE_ADVISORY",
                "backup_supplier_id": None,
                "financial_context": f"Sufficient buffer ({remaining} days) to handle {delay} day delay. Issuing advisory.",
                "best_alternate": None
            })
        else:
            optimal_decisions.append({
                "material_id": r["material_id"],
                "material_name": r["material_name"],
                "recommendation": "HOLD_AND_MONITOR",
                "backup_supplier_id": None,
                "financial_context": f"Sufficient buffer ({remaining} days) for minor {delay} day delay. No action needed.",
                "best_alternate": None
            })
            
    # ── Step 4: CFO LLM Rationale Generation ──
    llm = get_llm("financial_analyst")

    if hasattr(llm, '_llm_type') and llm._llm_type == "fake-mock-llm":
        return _deterministic_fallback(raw_math_results, confidence_score, is_test, pipeline_id)

    try:
        # Simplify the representation for the LLM
        prompt_decisions = [{
            "material_name": d["material_name"],
            "recommendation": d["recommendation"],
            "backup_supplier_name": d.get("backup_supplier_name"),
            "context": d["financial_context"]
        } for d in optimal_decisions]
        
        prompt_text = CFO_DECISION_PROMPT.format(
            threat_summary=threat_payload.get("summary", "Unknown"),
            region=threat_payload.get("region", "Unknown"),
            delay_days=delay_days,
            risk_reasoning=risk_reasoning,
            confidence_score=confidence_score,
            bom_impact=bom_impact_text,
            optimal_decisions=json.dumps(prompt_decisions, indent=2),
        )

        content = invoke_llm_with_retry(
            llm=llm, prompt_text=prompt_text, max_retries=2,
            pipeline_run_id=pipeline_id, agent_name="financial_analyst",
        )

        if content is None:
            return _deterministic_fallback(raw_math_results, confidence_score, is_test, pipeline_id)

        llm_rationales_raw = parse_llm_json(content)
        if not isinstance(llm_rationales_raw, list):
            llm_rationales_raw = [llm_rationales_raw] if isinstance(llm_rationales_raw, dict) else []

        return _merge_and_route(raw_math_results, optimal_decisions, llm_rationales_raw, confidence_score,
                                threat_payload, risk_reasoning, is_test, pipeline_id)

    except Exception as e:
        logger.error(f"[financial_analyst] Pipeline {pipeline_id}: CFO error — {e}")
        return _deterministic_fallback(raw_math_results, confidence_score, is_test, pipeline_id)


def _merge_and_route(raw_math, optimal_decisions, llm_rationales, confidence_score, threat_payload,
                     risk_reasoning, is_test, pipeline_id):
    """
    Merges optimal decisions with LLM rationales, then splits items into:
    - financial_analysis: can be auto-executed
    - approval_items: need human approval (cost > ceiling OR low confidence)
    """
    financial_analysis = []
    approval_items = []

    for r in raw_math:
        opt_dec = next((d for d in optimal_decisions if d.get("material_id") == r["material_id"]), {})
        llm_rat = next((rat for rat in llm_rationales if rat.get("material_id") == r["material_id"]), {})
        
        rec = opt_dec.get("recommendation", "HOLD_AND_MONITOR")
        rationale = llm_rat.get("rationale", opt_dec.get("financial_context", "No rationale generated."))
        best_alt = opt_dec.get("best_alternate")
            
        total_cost = best_alt.get("total_cost_of_goods", 0) if best_alt else 0

        item = {
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
            "factory_idle_cost": r["base_factory_idle_cost"],  # Show unmitigated risk cost in the UI
        }

        # ── Routing Decision ──
        needs_approval = False
        trigger_reason = None

        if rec == "EXECUTE_BACKUP_PO":
            if total_cost > MAX_AUTO_PO_COST:
                needs_approval = True
                trigger_reason = "COST_CEILING"
                logger.warning(
                    f"[financial_analyst] Pipeline {pipeline_id}: {r['material_name']} → "
                    f"APPROVAL QUEUE (cost ₹{total_cost:,.0f} > ceiling ₹{MAX_AUTO_PO_COST:,.0f})"
                )
            elif confidence_score < LOW_CONFIDENCE_THRESHOLD:
                needs_approval = True
                trigger_reason = "LOW_CONFIDENCE"
                logger.warning(
                    f"[financial_analyst] Pipeline {pipeline_id}: {r['material_name']} → "
                    f"APPROVAL QUEUE (confidence {confidence_score}% < {LOW_CONFIDENCE_THRESHOLD}% threshold)"
                )

        if needs_approval and best_alt:
            approval_items.append({
                **item,
                "trigger_reason": trigger_reason,
                "confidence_score": confidence_score,
                "risk_reasoning": risk_reasoning,
                "threat_summary": threat_payload.get("summary", ""),
                "severity": threat_payload.get("severity", "HIGH"),
            })
        else:
            financial_analysis.append(item)
            logger.info(f"[financial_analyst] Pipeline {pipeline_id}: {r['material_name']} → {rec} (auto-execute)")

    return {"financial_analysis": financial_analysis, "approval_items": approval_items}


def _deterministic_fallback(raw_math, confidence_score, is_test, pipeline_id):
    """
    Fallback logic if LLM parsing fails entirely.
    """
    logger.warning(f"[financial_analyst] Pipeline {pipeline_id}: Using deterministic fallback logic!")
    cfo_decisions = []
    
    for r in raw_math:
        delay_days = r["delay_days"]
        days_remaining = r["days_remaining"]
        
        if days_remaining < delay_days and r["base_factory_idle_cost"] > 0 and r["alternates"]:
            best_alt = min(r["alternates"], key=lambda x: x["total_financial_impact"])
            cfo_decisions.append({
                "material_id": r["material_id"],
                "recommendation": "EXECUTE_BACKUP_PO",
                "backup_supplier_id": best_alt["supplier_id"],
                "rationale": f"Deterministic Fallback. Factory at risk. Lowest total impact: {best_alt['total_financial_impact']}.",
            })
        elif days_remaining >= delay_days and delay_days > 3:
            cfo_decisions.append({
                "material_id": r["material_id"],
                "recommendation": "PROACTIVE_ADVISORY",
                "backup_supplier_id": None,
                "rationale": "Deterministic Fallback. Sufficient buffer for now, monitoring.",
            })
        else:
            cfo_decisions.append({
                "material_id": r["material_id"],
                "recommendation": "HOLD_AND_MONITOR",
                "backup_supplier_id": None,
                "rationale": "Deterministic Fallback. Buffer sufficient.",
            })

    return _merge_and_route(
        raw_math=raw_math,
        optimal_decisions=cfo_decisions,
        llm_rationales=[],
        confidence_score=confidence_score,
        threat_payload={"summary": "Fallback Mode", "severity": "MEDIUM"},
        risk_reasoning="Fallback mode due to LLM error.",
        is_test=is_test,
        pipeline_id=pipeline_id,
    )
