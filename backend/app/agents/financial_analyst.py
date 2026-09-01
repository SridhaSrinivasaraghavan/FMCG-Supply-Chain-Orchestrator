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
from langchain_core.prompts import PromptTemplate
import json
import logging

logger = logging.getLogger(__name__)

MAX_AUTO_PO_COST = getattr(settings, 'MAX_AUTO_PO_COST', 100000.0)
LOW_CONFIDENCE_THRESHOLD = 60  # Below this → human review


CFO_DECISION_PROMPT = PromptTemplate(
    template="""You are the Chief Financial Officer (CFO) of a major FMCG company in India.

## Threat & Risk Assessment
- News Event: {threat_summary}
- Region Affected: {region}
- Estimated Delay: {delay_days} days
- Risk Analyst's Reasoning: {risk_reasoning}
- Confidence Score: {confidence_score}/100

## Product Impact (Bill of Materials)
{bom_impact}

## Raw Financial Math (pre-calculated for you)
{financial_math}

## DECISION POLICY — Apply in this exact order:
1. IF days_remaining < delay_days AND factory_idle_cost > 0 AND reliable alternate exists (reliability ≥ 0.85):
   → EXECUTE_BACKUP_PO (pick highest reliability, then lowest price)
2. IF days_remaining < delay_days AND factory_idle_cost > 0 BUT no reliable alternate (all < 0.85):
   → EXECUTE_BACKUP_PO with best available (factory idle risk overrides quality preference)
3. IF days_remaining >= delay_days AND delay_days > 3:
   → PROACTIVE_ADVISORY (request early dispatch from primary vendor)
4. IF days_remaining >= delay_days AND delay_days <= 3:
   → HOLD_AND_MONITOR (buffer is sufficient)
5. IF no alternates AND factory NOT at risk:
   → HOLD_AND_MONITOR

## IMPORTANT: Be specific in your rationale. Reference the actual numbers from the financial math.
Example: "We have 8.5 days of stock vs 14-day delay. Factory will idle for 5.5 days costing ₹82,500. Ordering from National Cash & Carry (reliability: 93%) at ₹24/unit."

Output ONLY a JSON array:
[
  {{
    "material_id": 1,
    "material_name": "Grade-A Wheat Flour",
    "recommendation": "EXECUTE_BACKUP_PO",
    "rationale": "8.5 days stock vs 14-day delay. Idle cost: ₹82,500. Backup: National Cash & Carry (93% reliable) at ₹24/unit for 1,820 units = ₹43,680."
  }}
]

VALID recommendations: EXECUTE_BACKUP_PO, PROACTIVE_ADVISORY, HOLD_AND_MONITOR
""",
    input_variables=["threat_summary", "region", "delay_days", "risk_reasoning",
                     "confidence_score", "bom_impact", "financial_math"],
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

    # ── Step 1: Deterministic Financial Math ──
    raw_math_results = []
    valid_material_ids = set()

    for mat in impacted_materials:
        mat_id = mat["material_id"]
        valid_material_ids.add(mat_id)

        days_remaining = (
            mat["current_stock"] / mat["daily_consumption_rate"]
            if mat["daily_consumption_rate"] > 0 else 999
        )
        idle_days = max(0, delay_days - days_remaining)
        factory_idle_cost = settings.FACTORY_IDLE_COST_PER_DAY * idle_days

        primary_price = get_primary_supplier_price(mat_id)

        best_alt = None
        alts_info = []

        for alt in mat.get("alternate_suppliers", []):
            actual_primary = primary_price if primary_price else alt["unit_price"] * 0.85
            # MOQ check: order at least min_order_qty
            raw_order_qty = mat["daily_consumption_rate"] * (delay_days + 3)
            moq = alt.get("min_order_qty", 0)
            max_cap = alt.get("max_supply_capacity", 999999)
            order_qty = max(raw_order_qty, moq)
            order_qty = min(order_qty, max_cap)  # Clip to supplier capacity

            backup_premium = (alt["unit_price"] - actual_primary) * order_qty

            alt_dict = {
                "supplier_id": alt["supplier_id"],
                "supplier_name": alt["name"],
                "unit_price": alt["unit_price"],
                "reliability_score": alt["reliability_score"],
                "lead_time_days": alt.get("lead_time_days", 0),
                "backup_premium": round(backup_premium, 2),
                "order_qty": round(order_qty, 2),
                "total_cost": round(alt["unit_price"] * order_qty, 2),
                "moq": moq,
                "max_capacity": max_cap,
                "capacity_capped": order_qty < raw_order_qty,
            }
            alts_info.append(alt_dict)

            if not best_alt or alt["reliability_score"] > best_alt["reliability_score"]:
                best_alt = alt_dict
            elif (alt["reliability_score"] == best_alt["reliability_score"]
                  and alt["unit_price"] < best_alt["unit_price"]):
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

    # ── Step 2: BOM Impact ──
    bom_impact_text = _get_bom_impact_text(valid_material_ids, pipeline_id)

    # ── Step 3: CFO LLM Decision ──
    llm = get_llm("financial_analyst")

    if hasattr(llm, '_llm_type') and llm._llm_type == "fake-mock-llm":
        return _deterministic_fallback(raw_math_results, confidence_score, is_test, pipeline_id)

    try:
        prompt_text = CFO_DECISION_PROMPT.format(
            threat_summary=threat_payload.get("summary", "Unknown"),
            region=threat_payload.get("region", "Unknown"),
            delay_days=delay_days,
            risk_reasoning=risk_reasoning,
            confidence_score=confidence_score,
            bom_impact=bom_impact_text,
            financial_math=json.dumps(raw_math_results, indent=2),
        )

        content = invoke_llm_with_retry(
            llm=llm, prompt_text=prompt_text, max_retries=2,
            pipeline_run_id=pipeline_id, agent_name="financial_analyst",
        )

        if content is None:
            return _deterministic_fallback(raw_math_results, confidence_score, is_test, pipeline_id)

        cfo_raw = parse_llm_json(content)
        if not isinstance(cfo_raw, list):
            cfo_raw = [cfo_raw] if isinstance(cfo_raw, dict) else []

        cfo_decisions = validate_cfo_decisions(cfo_raw, valid_material_ids)
        return _merge_and_route(raw_math_results, cfo_decisions, confidence_score,
                                threat_payload, risk_reasoning, is_test, pipeline_id)

    except Exception as e:
        logger.error(f"[financial_analyst] Pipeline {pipeline_id}: CFO error — {e}")
        return _deterministic_fallback(raw_math_results, confidence_score, is_test, pipeline_id)


def _merge_and_route(raw_math, cfo_decisions, confidence_score, threat_payload,
                     risk_reasoning, is_test, pipeline_id):
    """
    Merges CFO decisions with math, then splits items into:
    - financial_analysis: can be auto-executed
    - approval_items: need human approval (cost > ceiling OR low confidence)
    """
    financial_analysis = []
    approval_items = []

    for r in raw_math:
        decision = next((d for d in cfo_decisions if d.get("material_id") == r["material_id"]), {})
        rec = decision.get("recommendation", "HOLD_AND_MONITOR")
        rationale = decision.get("rationale", "No rationale provided.")
        best_alt = r.get("best_fallback_assumed")
        total_cost = best_alt.get("total_cost", 0) if best_alt else 0

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
            "factory_idle_cost": r["factory_idle_cost"],
        }

        # ── Routing Decision ──
        needs_approval = False
        trigger_reason = None

        if rec == "EXECUTE_BACKUP_PO" and not is_test:
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


def _get_bom_impact_text(material_ids, pipeline_id):
    try:
        bom_data = get_bom_impact(list(material_ids))
        if not bom_data:
            return "No BOM data available."
        lines = []
        for item in bom_data:
            lines.append(
                f"- '{item['product_name']}' requires {item['required_quantity_per_unit']} "
                f"{item.get('unit','units')} of {item['material_name']} per unit. "
                f"Shortfall = production STOP."
            )
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"[financial_analyst] Pipeline {pipeline_id}: BOM lookup failed — {e}")
        return "BOM data unavailable."


def _deterministic_fallback(raw_math, confidence_score, is_test, pipeline_id):
    """Rule-based fallback when CFO LLM unavailable."""
    logger.info(f"[financial_analyst] Pipeline {pipeline_id}: Using deterministic fallback")
    financial_analysis = []
    approval_items = []

    for r in raw_math:
        days_rem = r["days_remaining"]
        delay = r["delay_days"]
        idle_cost = r["factory_idle_cost"]
        best_alt = r.get("best_fallback_assumed")
        total_cost = best_alt.get("total_cost", 0) if best_alt else 0

        if idle_cost > 0 and best_alt:
            rec = "EXECUTE_BACKUP_PO"
            rationale = (
                f"[Deterministic] {days_rem:.1f}d stock vs {delay}d delay. "
                f"Idle cost: ₹{idle_cost:,.0f}. Ordering from {best_alt['supplier_name']}."
            )
        elif delay > 3:
            rec = "PROACTIVE_ADVISORY"
            rationale = f"[Deterministic] Buffer sufficient ({days_rem:.1f}d vs {delay}d). Requesting early dispatch."
        else:
            rec = "HOLD_AND_MONITOR"
            rationale = f"[Deterministic] Delay {delay}d within buffer {days_rem:.1f}d."

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
            "days_remaining": days_rem,
            "delay_days": delay,
            "factory_idle_cost": idle_cost,
        }

        if rec == "EXECUTE_BACKUP_PO" and not is_test and total_cost > MAX_AUTO_PO_COST:
            approval_items.append({**item, "trigger_reason": "COST_CEILING",
                                   "confidence_score": confidence_score})
        else:
            financial_analysis.append(item)

    return {"financial_analysis": financial_analysis, "approval_items": approval_items}
