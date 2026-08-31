"""
Agent 4: Strategy Execution Agent (The Doer)

Executes the CFO's decision. Handles 3 outcomes:
1. EXECUTE_BACKUP_PO (Emergency) — creates PO, sends email, logs disruption
2. PROACTIVE_ADVISORY (Minor delay) — notifies primary vendor to dispatch early
3. HOLD_AND_MONITOR (No action needed) — logs the decision

Improvements:
- Uses real primary_supplier_id from Financial Analyst (no more hardcoded supplier_id=1)
- PO deduplication check before creating new POs
- Uses actual supplier email from DB
- Pipeline run ID tracked in all DB writes
- Executive summary generation isolated from execution logic
"""
from app.agents.state import AgentState
from app.tools.db_tools import (
    create_purchase_order, 
    log_disruption, 
    check_existing_po,
    get_supplier_email,
)
from app.tools.email_tools import send_purchase_order_email
from app.tools.vendor_notify import send_proactive_advisory
from app.services.llm_factory import get_llm
from app.services.llm_utils import invoke_llm_with_retry
from langchain_core.prompts import PromptTemplate
import json
import logging

logger = logging.getLogger(__name__)


EXECUTIVE_SUMMARY_PROMPT = PromptTemplate(
    template="""You are a Chief Supply Chain Officer writing an executive briefing for the board.

## Threat Detected
{threat_info}

## Risk Analysis
{risk_reasoning}

## CFO Financial Decisions
{financial_summary}

## Autonomous Actions Taken
{actions_summary}

## Your Task
Write a concise 200-300 word executive summary covering:
1. **SITUATION**: What happened? (1-2 sentences)
2. **IMPACT**: What materials/routes are affected? (2-3 sentences)
3. **DECISION**: Why was this course of action chosen? Reference specific numbers (costs, days of stock). (2-3 sentences)
4. **ACTIONS**: What did the system do autonomously? (2-3 sentences)
5. **OUTLOOK**: Any ongoing risks or follow-up needed? (1-2 sentences)

Output plain text only. No markdown headers, no bullet points.
""",
    input_variables=["threat_info", "risk_reasoning", "financial_summary", "actions_summary"],
)


def strategy_execution_node(state: AgentState):
    """Agent 4: Executes CFO decisions — creates POs, sends notifications, logs everything."""
    pipeline_id = state.get("pipeline_run_id", "unknown")
    logger.info(f"[strategy_execution] Pipeline {pipeline_id}: Starting execution")
    
    financial_analysis = state.get("financial_analysis", [])
    threat_payload = state.get("threat_payload", {})
    risk_reasoning = state.get("risk_reasoning", "No risk reasoning available.")
    source_event = threat_payload.get("summary", "Unknown Disruption")
    severity = threat_payload.get("severity", "HIGH")

    actions_taken = []

    for analysis in financial_analysis:
        rec = analysis.get("recommendation")
        mat_id = analysis.get("material_id")
        mat_name = analysis.get("material_name", "Unknown")
        
        if rec == "EXECUTE_BACKUP_PO":
            action = _execute_backup_po(analysis, source_event, severity, pipeline_id)
            if action:
                actions_taken.append(action)

        elif rec == "PROACTIVE_ADVISORY":
            action = _send_proactive_advisory(analysis, threat_payload, source_event, severity, pipeline_id)
            if action:
                actions_taken.append(action)
            
        elif rec == "HOLD_AND_MONITOR":
            action_desc = f"Hold & Monitor. Rationale: {analysis.get('rationale', 'N/A')}"
            log_disruption(
                source_event=source_event, 
                material_id=mat_id, 
                severity=severity, 
                action_taken=action_desc,
                pipeline_run_id=pipeline_id,
            )
            actions_taken.append({
                "material": mat_name,
                "action": action_desc,
                "status": "HELD",
            })
            logger.info(f"[strategy_execution] Pipeline {pipeline_id}: {mat_name} → HOLD_AND_MONITOR")
        
        else:
            logger.warning(
                f"[strategy_execution] Pipeline {pipeline_id}: Unknown recommendation '{rec}' "
                f"for {mat_name}. Treating as HOLD_AND_MONITOR."
            )
            log_disruption(
                source_event=source_event,
                material_id=mat_id,
                severity=severity,
                action_taken=f"Unknown recommendation '{rec}' — logged for review. Rationale: {analysis.get('rationale', 'N/A')}",
                pipeline_run_id=pipeline_id,
            )
            actions_taken.append({
                "material": mat_name,
                "action": f"Unknown recommendation '{rec}' — logged for manual review",
                "status": "REVIEW_NEEDED",
            })

    # Generate executive summary (isolated — failure here won't affect execution)
    executive_summary = _generate_executive_summary(
        threat_payload, risk_reasoning, financial_analysis, actions_taken, pipeline_id
    )

    logger.info(f"[strategy_execution] Pipeline {pipeline_id}: Execution complete. {len(actions_taken)} actions taken.")
    
    return {
        "recommended_actions": actions_taken,
        "executive_summary": executive_summary,
        "execution_status": "COMPLETED",
    }


def _execute_backup_po(analysis: dict, source_event: str, severity: str, pipeline_id: str) -> dict:
    """Executes an emergency backup purchase order with dedup checking."""
    mat_id = analysis["material_id"]
    mat_name = analysis.get("material_name", "Unknown")
    best_alt = analysis.get("best_alternate")
    
    if not best_alt:
        logger.warning(f"[strategy_execution] Pipeline {pipeline_id}: No backup supplier for {mat_name} — skipping PO")
        return {
            "material": mat_name,
            "action": "EXECUTE_BACKUP_PO skipped — no backup supplier available",
            "status": "SKIPPED",
        }
    
    # ── Deduplication check ──
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
    
    # ── Create PO ──
    try:
        po_result = create_purchase_order(
            material_id=mat_id,
            supplier_id=best_alt["supplier_id"],
            quantity=analysis.get("order_qty", 0),
            total_cost=analysis.get("total_cost", 0),
            pipeline_run_id=pipeline_id,
        )
        
        action_desc = (
            f"Emergency PO #{po_result['po_id']}: {analysis.get('order_qty', 0):.1f} units "
            f"from {best_alt['supplier_name']} @ ${analysis.get('total_cost', 0):.2f}. "
            f"Rationale: {analysis.get('rationale', 'N/A')}"
        )
        
        log_disruption(
            source_event=source_event, 
            material_id=mat_id, 
            severity=severity, 
            action_taken=action_desc,
            pipeline_run_id=pipeline_id,
        )
        
        # ── Send PO email ──
        supplier_email = get_supplier_email(best_alt["supplier_id"])
        email_payload = {
            "po_id": po_result["po_id"],
            "material_name": mat_name,
            "quantity": analysis.get("order_qty", 0),
            "total_cost": analysis.get("total_cost", 0),
        }
        email_result = send_purchase_order_email(supplier_email, email_payload)
        
        logger.info(
            f"[strategy_execution] Pipeline {pipeline_id}: PO #{po_result['po_id']} created for {mat_name}. "
            f"Email: {email_result.get('status')}"
        )
        
        return {
            "material": mat_name,
            "action": action_desc,
            "status": "EXECUTED",
            "po_id": po_result["po_id"],
            "email": email_result.get("status"),
        }
        
    except Exception as e:
        logger.error(f"[strategy_execution] Pipeline {pipeline_id}: PO creation failed for {mat_name}: {e}")
        return {
            "material": mat_name,
            "action": f"PO creation FAILED: {str(e)}",
            "status": "ERROR",
        }


def _send_proactive_advisory(
    analysis: dict, threat_payload: dict, source_event: str, severity: str, pipeline_id: str
) -> dict:
    """Sends a proactive advisory to the PRIMARY supplier to dispatch early."""
    mat_id = analysis["material_id"]
    mat_name = analysis.get("material_name", "Unknown")
    
    # Use REAL primary supplier ID from the Financial Analyst's data
    primary_supplier_id = analysis.get("primary_supplier_id")
    
    if primary_supplier_id:
        primary_email = get_supplier_email(primary_supplier_id)
    else:
        primary_email = f"logistics@{mat_name.lower().split()[0]}.com"
        logger.warning(f"[strategy_execution] Pipeline {pipeline_id}: No primary_supplier_id for {mat_name}, using generated email")
    
    subject = f"URGENT: Proactive Routing Advisory for {mat_name}"
    body = (
        f"Dear Partner,\n\n"
        f"Our AI supply chain system has detected a potential logistics delay affecting your route.\n\n"
        f"Context: {threat_payload.get('summary', 'Unknown event')}\n"
        f"AI Analysis: {analysis.get('rationale', 'N/A')}\n\n"
        f"Please adjust your dispatch schedule immediately to avoid missing our factory receiving window.\n\n"
        f"Thank you,\nAutonomous FMCG Supply Chain System"
    )
    
    try:
        adv_result = send_proactive_advisory(
            supplier_id=primary_supplier_id or 0,
            supplier_email=primary_email,
            subject=subject,
            body=body,
        )
        
        action_desc = f"Sent Proactive Advisory to {primary_email}. Rationale: {analysis.get('rationale', 'N/A')}"
        log_disruption(
            source_event=source_event, 
            material_id=mat_id, 
            severity=severity, 
            action_taken=action_desc,
            pipeline_run_id=pipeline_id,
        )
        
        logger.info(f"[strategy_execution] Pipeline {pipeline_id}: Advisory sent for {mat_name} to {primary_email}")
        
        return {
            "material": mat_name,
            "action": action_desc,
            "status": "ADVISORY_SENT",
        }
        
    except Exception as e:
        logger.error(f"[strategy_execution] Pipeline {pipeline_id}: Advisory failed for {mat_name}: {e}")
        return {
            "material": mat_name,
            "action": f"Advisory FAILED: {str(e)}",
            "status": "ERROR",
        }


def _generate_executive_summary(
    threat_payload: dict, risk_reasoning: str, 
    financial_analysis: list, actions_taken: list, pipeline_id: str
) -> str:
    """Generates an executive summary. Failure here is non-critical."""
    llm = get_llm("strategy_execution")
    
    if hasattr(llm, '_llm_type') and llm._llm_type == "fake-mock-llm":
        return "EXECUTIVE SUMMARY (Mock Mode): Processing complete. See actions taken for details."

    try:
        prompt_text = EXECUTIVE_SUMMARY_PROMPT.format(
            threat_info=json.dumps(threat_payload, indent=2),
            risk_reasoning=risk_reasoning,
            financial_summary=json.dumps(financial_analysis, indent=2),
            actions_summary=json.dumps(actions_taken, indent=2),
        )
        
        content = invoke_llm_with_retry(
            llm=llm,
            prompt_text=prompt_text,
            max_retries=1,  # Only 1 retry for summary — it's non-critical
            pipeline_run_id=pipeline_id,
            agent_name="strategy_execution",
        )
        
        if content:
            return content
        return "Executive summary generation failed after retries. See detailed actions above."
        
    except Exception as e:
        logger.error(f"[strategy_execution] Pipeline {pipeline_id}: Executive summary failed: {e}")
        return f"Executive summary unavailable: {str(e)}"
