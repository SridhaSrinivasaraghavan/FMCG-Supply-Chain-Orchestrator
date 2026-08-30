from app.agents.state import AgentState
from app.tools.db_tools import create_purchase_order, log_disruption
from app.tools.email_tools import send_purchase_order_email

def strategy_execution_node(state: AgentState):
    """
    Agent 4: Takes financial recommendations and executes them.
    Triggers DB tools and email dispatch.
    """
    print("--- STRATEGY EXECUTION AGENT ---")
    financial_analysis = state.get("financial_analysis", [])
    threat_payload = state.get("threat_payload", {})
    source_event = threat_payload.get("summary", "Unknown Disruption")
    severity = threat_payload.get("severity", "HIGH")
    
    actions_taken = []
    
    for analysis in financial_analysis:
        if analysis.get("recommendation") == "EXECUTE_BACKUP_PO":
            material_id = analysis["material_id"]
            best_alt = analysis["best_alternate"]
            
            # 1. Create Purchase Order
            po_result = create_purchase_order(
                material_id=material_id,
                supplier_id=best_alt["supplier_id"],
                quantity=analysis["order_qty"],
                total_cost=analysis["total_cost"]
            )
            
            # 2. Log the disruption and action
            action_desc = f"Ordered {analysis['order_qty']} units from {best_alt['name']}"
            log_result = log_disruption(
                source_event=source_event,
                material_id=material_id,
                severity=severity,
                action_taken=action_desc
            )
            
            # 3. Send Email
            email_payload = {
                "po_id": po_result["po_id"],
                "material_name": analysis["material_name"],
                "quantity": analysis["order_qty"],
                "total_cost": analysis["total_cost"]
            }
            # The supplier email isn't directly passed in best_alt, so we'll mock it 
            # or it should be joined in Risk Assessment. Using a dummy for demo.
            email_result = send_purchase_order_email(
                supplier_email=f"orders@{best_alt['name'].lower().replace(' ', '')}.com",
                po_details=email_payload
            )
            
            actions_taken.append({
                "material": analysis["material_name"],
                "action": action_desc,
                "po_id": po_result["po_id"],
                "email_status": email_result["status"]
            })
            
        elif analysis.get("recommendation") == "HOLD_AND_MONITOR":
            actions_taken.append({
                 "material": analysis["material_name"],
                 "action": "Held PO. Monitored situation. No savings from backup."
            })
            log_disruption(
                source_event=source_event,
                material_id=analysis["material_id"],
                severity=severity,
                action_taken="Monitored (No PO executed)"
            )
            
    return {
        "recommended_actions": actions_taken,
        "execution_status": "COMPLETED"
    }
