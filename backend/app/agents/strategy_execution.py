"""
Agent 4: Strategy Execution Agent — v3.1

New in v3.1:
- Inserts approval_items into the approval_queue DB table (human review needed)
- Registers handled events in active_disruptions for event-level dedup
- Test-mode aware: marks all writes with is_test=True
"""
from app.agents.state import AgentState
from app.tools.db_tools import (
    create_purchase_order,
    log_disruption,
    check_existing_po,
    get_supplier_email,
    create_approval_queue_item,
)
from app.tools.email_tools import send_purchase_order_email
from app.tools.vendor_notify import send_proactive_advisory
from app.services.event_dedup import register_active_disruption
from app.services.llm_factory import get_llm
from app.services.llm_utils import invoke_llm_with_retry
from langchain_core.prompts import PromptTemplate
import json
import logging

logger = logging.getLogger(__name__)


EXECUTIVE_SUMMARY_PROMPT = PromptTemplate(
    template="""You are a Chief Supply Chain Officer writing a concise board briefing.

## Threat
{threat_info}

## Risk Analysis
{risk_reasoning}

## CFO Financial Decisions & Calculations
{financial_summary}

## Autonomous Actions Taken
{actions_summary}

## Pending Human Approvals
{approvals_summary}

Write a 200-250 word executive summary covering:
1. SITUATION: What happened and where? (1-2 sentences)
2. IMPACT: Which materials/routes are affected and why? Include stock days vs delay days. (2-3 sentences)
3. FINANCIAL LOGIC: Why was this course of action chosen? Reference specific numbers (₹ costs, days, reliability %). (2-3 sentences)
4. ACTIONS TAKEN: What did the system execute autonomously? (2-3 sentences)
5. PENDING APPROVALS: What requires human review and why? (1-2 sentences, or "None" if nothing pending)
6. OUTLOOK: Any ongoing risks or follow-up needed? (1 sentence)

Output plain text only. No markdown, no bullet points, no headers.
""",
    input_variables=["threat_info", "risk_reasoning", "financial_summary",
                     "actions_summary", "approvals_summary"],
)


def strategy_execution_node(state: AgentState):
    """Agent 4: Executes CFO decisions, queues approval items, logs everything, registers event."""
    pipeline_id = state.get("pipeline_run_id", "unknown")
    logger.info(f"[strategy_execution] Pipeline {pipeline_id}: Starting execution")

    financial_analysis = state.get("financial_analysis", [])
    approval_items = state.get("approval_items", [])
    threat_payload = state.get("threat_payload", {})
    risk_reasoning = state.get("risk_reasoning", "No risk reasoning available.")
    confidence_score = state.get("confidence_score", 80)
    is_test = state.get("is_test", False)

    source_event = threat_payload.get("summary", "Unknown Disruption")
    severity = threat_payload.get("severity", "HIGH")
    region = threat_payload.get("region", "Unknown")
    event_type = threat_payload.get("event_type", "other")

    actions_taken = []

    # ── Execute auto-approved decisions ──
    for analysis in financial_analysis:
        rec = analysis.get("recommendation")
        mat_id = analysis.get("material_id")
        mat_name = analysis.get("material_name", "Unknown")

        detailed_reasoning = (
            f"### Market Intel Reasoning\n{threat_payload.get('reasoning', 'N/A')}\n\n"
            f"### Risk Assessment Reasoning\n{risk_reasoning}\n\n"
            f"### Financial Rationale\n{analysis.get('rationale', 'N/A')}"
        )

        if rec == "EXECUTE_BACKUP_PO":
            action = _execute_backup_po(analysis, source_event, severity, pipeline_id, is_test, detailed_reasoning)
            if action:
                actions_taken.append(action)

        elif rec == "PROACTIVE_ADVISORY":
            action = _send_proactive_advisory(analysis, threat_payload, source_event, severity, pipeline_id, detailed_reasoning)
            if action:
                actions_taken.append(action)

        elif rec == "HOLD_AND_MONITOR":
            desc = f"Hold & Monitor. Rationale: {analysis.get('rationale', 'N/A')}"
            log_disruption(
                source_event=source_event, material_id=mat_id,
                severity=severity, action_taken=desc,
                pipeline_run_id=pipeline_id, is_test=is_test,
                disruption_type=str(getattr(event_type, "value", event_type)),
                detailed_reasoning=detailed_reasoning,
            )
            actions_taken.append({"material": mat_name, "action": desc, "status": "HELD"})
            logger.info(f"[strategy_execution] Pipeline {pipeline_id}: {mat_name} → HOLD_AND_MONITOR")

    # ── Queue items needing human approval ──
    approval_queue_results = []
    for item in approval_items:
        item["market_intel_reasoning"] = threat_payload.get("reasoning", "")
        result = _queue_for_approval(item, pipeline_id, is_test)
        approval_queue_results.append(result)
        logger.info(
            f"[strategy_execution] Pipeline {pipeline_id}: {item.get('material_name')} → "
            f"APPROVAL QUEUE (reason: {item.get('trigger_reason')})"
        )

    # ── Register this event in active_disruptions (event-level dedup) ──
    if not is_test and region != "Unknown":
        action_summary = (
            f"Pipeline {pipeline_id}: {len(actions_taken)} actions executed, "
            f"{len(approval_queue_results)} queued for approval."
        )
        try:
            register_active_disruption(
                region=region,
                event_type=event_type,
                pipeline_run_id=pipeline_id,
                action_taken=action_summary,
                confidence_score=confidence_score,
                is_test=is_test,
            )
        except Exception as e:
            logger.warning(f"[strategy_execution] Pipeline {pipeline_id}: Failed to register active disruption — {e}")

    # ── Generate executive summary ──
    executive_summary = _generate_executive_summary(
        threat_payload, risk_reasoning, financial_analysis,
        actions_taken, approval_queue_results, pipeline_id
    )

    logger.info(
        f"[strategy_execution] Pipeline {pipeline_id}: Done. "
        f"Actions: {len(actions_taken)}, Approvals queued: {len(approval_queue_results)}"
    )

    return {
        "recommended_actions": actions_taken,
        "executive_summary": executive_summary,
        "execution_status": "COMPLETED",
    }


def _execute_backup_po(analysis, source_event, severity, pipeline_id, is_test, detailed_reasoning):
    mat_id = analysis["material_id"]
    mat_name = analysis.get("material_name", "Unknown")
    best_alt = analysis.get("best_alternate")

    if not best_alt:
        return {"material": mat_name, "action": "Skipped — no backup supplier available", "status": "SKIPPED"}

    # Dedup check (skip in test mode)
    if not is_test:
        existing_po = check_existing_po(mat_id, hours=24)
        if existing_po:
            logger.warning(
                f"[strategy_execution] Pipeline {pipeline_id}: Duplicate PO blocked for {mat_name}. "
                f"Existing PO #{existing_po['po_id']} created at {existing_po['created_at']}"
            )
            return {
                "material": mat_name,
                "action": f"Duplicate PO blocked — existing PO #{existing_po['po_id']} already active",
                "status": "DEDUP_BLOCKED",
            }

    try:
        po_result = create_purchase_order(
            material_id=mat_id,
            supplier_id=best_alt["supplier_id"],
            quantity=analysis.get("order_qty", 0),
            total_cost=analysis.get("total_cost", 0),
            pipeline_run_id=pipeline_id,
            is_test=is_test,
        )

        action_desc = (
            f"Emergency PO #{po_result['po_id']}: {analysis.get('order_qty', 0):,.1f} units "
            f"from {best_alt['supplier_name']} @ ₹{analysis.get('total_cost', 0):,.2f}. "
            f"Rationale: {analysis.get('rationale', 'N/A')}"
        )

        log_disruption(
            source_event=source_event, material_id=mat_id,
            severity=severity, action_taken=action_desc,
            pipeline_run_id=pipeline_id, is_test=is_test,
            disruption_type=str(getattr(analysis.get("event_type", "OTHER"), "value", analysis.get("event_type", "OTHER"))),
            detailed_reasoning=detailed_reasoning,
        )

        supplier_email = get_supplier_email(best_alt["supplier_id"])
        email_result = send_purchase_order_email(supplier_email, {
            "po_id": po_result["po_id"],
            "material_name": mat_name,
            "quantity": analysis.get("order_qty", 0),
            "total_cost": analysis.get("total_cost", 0),
        })

        logger.info(f"[strategy_execution] Pipeline {pipeline_id}: PO #{po_result['po_id']} created for {mat_name}")

        return {
            "material": mat_name,
            "action": action_desc,
            "status": "EXECUTED" + (" [TEST]" if is_test else ""),
            "po_id": po_result["po_id"],
        }

    except Exception as e:
        logger.error(f"[strategy_execution] Pipeline {pipeline_id}: PO creation failed for {mat_name}: {e}")
        return {"material": mat_name, "action": f"PO creation FAILED: {e}", "status": "ERROR"}


def _send_proactive_advisory(analysis, threat_payload, source_event, severity, pipeline_id, detailed_reasoning):
    mat_id = analysis["material_id"]
    mat_name = analysis.get("material_name", "Unknown")
    primary_supplier_id = analysis.get("primary_supplier_id")
    primary_email = get_supplier_email(primary_supplier_id) if primary_supplier_id else "unknown@supplier.com"

    subject = f"URGENT: Proactive Dispatch Advisory for {mat_name}"
    body = (
        f"Dear Partner,\n\n"
        f"Our AI supply chain system has detected a potential logistics disruption.\n\n"
        f"Context: {threat_payload.get('summary', 'Unknown event')}\n"
        f"AI Analysis: {analysis.get('rationale', 'N/A')}\n\n"
        f"Please dispatch your next delivery AHEAD of schedule to avoid missing our factory receiving window.\n\n"
        f"Thank you,\nAutonomous FMCG Supply Chain System"
    )

    try:
        send_proactive_advisory(
            supplier_id=primary_supplier_id or 0,
            supplier_email=primary_email,
            subject=subject, body=body,
        )
        action_desc = f"Proactive Advisory sent to {primary_email}. Rationale: {analysis.get('rationale', 'N/A')}"
        log_disruption(
            source_event=source_event, material_id=mat_id,
            severity=severity, action_taken=action_desc, pipeline_run_id=pipeline_id,
            disruption_type=str(getattr(threat_payload.get("event_type", "OTHER"), "value", threat_payload.get("event_type", "OTHER"))),
            detailed_reasoning=detailed_reasoning,
        )
        logger.info(f"[strategy_execution] Pipeline {pipeline_id}: Advisory sent for {mat_name}")
        return {"material": mat_name, "action": action_desc, "status": "ADVISORY_SENT"}

    except Exception as e:
        logger.error(f"[strategy_execution] Pipeline {pipeline_id}: Advisory failed for {mat_name}: {e}")
        return {"material": mat_name, "action": f"Advisory FAILED: {e}", "status": "ERROR"}


def _queue_for_approval(item, pipeline_id, is_test):
    """Inserts item into the approval_queue table — a human must review before PO is placed."""
    mat_name = item.get("material_name", "Unknown")
    try:
        best_alt = item.get("best_alternate") or {}
        result = create_approval_queue_item(
            pipeline_run_id=pipeline_id,
            material_id=item["material_id"],
            material_name=mat_name,
            recommended_action=item.get("recommendation", "EXECUTE_BACKUP_PO"),
            backup_supplier_id=best_alt.get("supplier_id"),
            backup_supplier_name=best_alt.get("supplier_name", "Unknown"),
            order_quantity=item.get("order_qty", 0),
            total_cost=item.get("total_cost", 0),
            trigger_reason=item.get("trigger_reason", "COST_CEILING"),
            confidence_score=item.get("confidence_score", 80),
            rationale=item.get("rationale", ""),
            risk_reasoning=item.get("risk_reasoning", ""),
            threat_summary=item.get("threat_summary", ""),
            severity=item.get("severity", "HIGH"),
            is_test=is_test,
            market_intel_reasoning=item.get("market_intel_reasoning", ""),
        )
        return {
            "material": mat_name,
            "action": f"Queued for human approval (reason: {item.get('trigger_reason')}). Approval #{result['approval_id']}",
            "status": "PENDING_APPROVAL",
            "approval_id": result["approval_id"],
        }
    except Exception as e:
        logger.error(f"[strategy_execution] Pipeline {pipeline_id}: Approval queue insert failed for {mat_name}: {e}")
        return {"material": mat_name, "action": f"Approval queue FAILED: {e}", "status": "ERROR"}


def _generate_executive_summary(threat_payload, risk_reasoning, financial_analysis,
                                 actions_taken, approval_items, pipeline_id):
    llm = get_llm("strategy_execution")
    if hasattr(llm, '_llm_type') and llm._llm_type == "fake-mock-llm":
        return "EXECUTIVE SUMMARY (Mock Mode): Pipeline complete. See actions for details."

    try:
        prompt_text = EXECUTIVE_SUMMARY_PROMPT.format(
            threat_info=json.dumps(threat_payload, indent=2),
            risk_reasoning=risk_reasoning,
            financial_summary=json.dumps(financial_analysis, indent=2),
            actions_summary=json.dumps(actions_taken, indent=2),
            approvals_summary=json.dumps(approval_items, indent=2) if approval_items else "None",
        )
        content = invoke_llm_with_retry(
            llm=llm, prompt_text=prompt_text, max_retries=1,
            pipeline_run_id=pipeline_id, agent_name="strategy_execution",
        )
        return content if content else "Executive summary unavailable after retries."
    except Exception as e:
        logger.error(f"[strategy_execution] Pipeline {pipeline_id}: Executive summary failed: {e}")
        return f"Executive summary unavailable: {e}"
