"""
Agent 4: Strategy Execution Agent

Executes the CFO's decision. Handles 3 outcomes:
1. EXECUTE_BACKUP_PO (Emergency)
2. PROACTIVE_ADVISORY (Minor delay, request early dispatch)
3. HOLD_AND_MONITOR (No action needed)
"""
from app.agents.state import AgentState
from app.tools.db_tools import create_purchase_order, log_disruption
from app.tools.email_tools import send_purchase_order_email
from app.tools.vendor_notify import send_proactive_advisory
from app.services.llm_factory import get_llm
from langchain_core.prompts import PromptTemplate
import json
import logging

logger = logging.getLogger(__name__)

EXECUTIVE_SUMMARY_PROMPT = PromptTemplate(
    template="""You are a Chief Supply Chain Officer writing an executive briefing.

## Threat Detected
{threat_info}

## Risk Analysis (Indirect & Logistics)
{risk_reasoning}

## CFO Financial Decisions
{financial_summary}

## Actions Taken
{actions_summary}

## Your Task
Write a 200-300 word executive summary covering:
1. **SITUATION**: What happened?
2. **IMPACT**: What materials/routes are affected? 
3. **ANALYSIS**: Why was a certain decision made (e.g. why buy vs why just send an advisory)?
4. **ACTIONS**: What autonomous actions did the system take?
5. **OUTLOOK**: Any ongoing risks?

IMPORTANT: Output plain text only.
""",
    input_variables=["threat_info", "risk_reasoning", "financial_summary", "actions_summary"],
)

def strategy_execution_node(state: AgentState):
    print("--- STRATEGY EXECUTION AGENT ---")
    financial_analysis = state.get("financial_analysis", [])
    threat_payload = state.get("threat_payload", {})
    risk_reasoning = state.get("risk_reasoning", "No risk reasoning available.")
    source_event = threat_payload.get("summary", "Unknown Disruption")
    severity = threat_payload.get("severity", "HIGH")

    actions_taken = []

    for analysis in financial_analysis:
        rec = analysis.get("recommendation")
        
        if rec == "EXECUTE_BACKUP_PO":
            best_alt = analysis["best_alternate"]
            if not best_alt:
                continue
                
            po_result = create_purchase_order(
                material_id=analysis["material_id"],
                supplier_id=best_alt["supplier_id"],
                quantity=analysis["order_qty"],
                total_cost=analysis["total_cost"],
            )
            
            action_desc = f"Emergency PO: {analysis['order_qty']} units from {best_alt['supplier_name']}. Rationale: {analysis['rationale']}"
            log_disruption(source_event, analysis["material_id"], severity, action_desc)
            
            email_payload = {
                "po_id": po_result["po_id"],
                "material_name": analysis["material_name"],
                "quantity": analysis["order_qty"],
                "total_cost": analysis["total_cost"],
            }
            email_result = send_purchase_order_email(f"orders@{best_alt['supplier_name'].lower().replace(' ', '')}.com", email_payload)
            
            actions_taken.append({
                "material": analysis["material_name"],
                "action": action_desc,
                "status": "EXECUTED",
                "email": email_result["status"]
            })

        elif rec == "PROACTIVE_ADVISORY":
            # For advisories, we notify the CURRENT (primary) supplier.
            # In a real system, we'd query the DB for the primary supplier email. For demo, we mock it.
            primary_supplier_email = f"logistics@{analysis['material_name'].lower().split()[0]}.com"
            
            subject = f"URGENT: Proactive Routing Advisory for {analysis['material_name']}"
            body = f"Dear Partner,\n\nOur AI has detected a potential logistics delay affecting your route.\n\nContext: {threat_payload.get('summary')}\nAI Analysis: {analysis['rationale']}\n\nPlease adjust your dispatch schedule immediately to avoid missing our factory receiving window.\n\nThank you."
            
            adv_result = send_proactive_advisory(
                supplier_id=1, # Mock ID since we don't have primary ID easily here
                supplier_email=primary_supplier_email,
                subject=subject,
                body=body
            )
            
            action_desc = f"Sent Proactive Advisory to vendor. Rationale: {analysis['rationale']}"
            log_disruption(source_event, analysis["material_id"], severity, action_desc)
            
            actions_taken.append({
                "material": analysis["material_name"],
                "action": action_desc,
                "status": "ADVISORY_SENT"
            })
            
        elif rec == "HOLD_AND_MONITOR":
            action_desc = f"Hold & Monitor. Rationale: {analysis['rationale']}"
            log_disruption(source_event, analysis["material_id"], severity, action_desc)
            actions_taken.append({
                "material": analysis["material_name"],
                "action": action_desc,
                "status": "HELD"
            })

    executive_summary = _generate_executive_summary(threat_payload, risk_reasoning, financial_analysis, actions_taken)

    return {
        "recommended_actions": actions_taken,
        "executive_summary": executive_summary,
        "execution_status": "COMPLETED",
    }

def _generate_executive_summary(threat_payload, risk_reasoning, financial_analysis, actions_taken):
    llm = get_llm("strategy_execution")
    if hasattr(llm, '_llm_type') and llm._llm_type == "fake-mock-llm":
        return "EXECUTIVE SUMMARY (Mock Mode): Processing complete."

    try:
        prompt_text = EXECUTIVE_SUMMARY_PROMPT.format(
            threat_info=json.dumps(threat_payload, indent=2),
            risk_reasoning=risk_reasoning,
            financial_summary=json.dumps(financial_analysis, indent=2),
            actions_summary=json.dumps(actions_taken, indent=2),
        )
        response = llm.invoke(prompt_text)
        summary = response.content if hasattr(response, 'content') else str(response)
        return summary
    except Exception as e:
        logger.error(f"Executive summary generation failed: {e}")
        return f"Executive summary unavailable: {str(e)}"
