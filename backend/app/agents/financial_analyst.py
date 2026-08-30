from app.agents.state import AgentState
from app.config import settings
import pandas as pd
from datetime import datetime, timedelta

def financial_analyst_node(state: AgentState):
    """
    Agent 3: Deterministic calculation node.
    Computes depletion curves and cost-benefit of backup suppliers.
    """
    print("--- FINANCIAL ANALYST AGENT ---")
    impacted_materials = state.get("impacted_materials", [])
    threat_payload = state.get("threat_payload", {})
    delay_days = threat_payload.get("estimated_delay_days", 7)
    
    if not impacted_materials:
        return {"financial_analysis": [], "recommended_actions": []}
        
    analysis_results = []
    
    for mat in impacted_materials:
        # Calculate depletion
        days_remaining = mat["current_stock"] / mat["daily_consumption_rate"]
        
        # Idle cost calculation
        # If delay is longer than our stock can cover, factory goes idle
        idle_days = max(0, delay_days - days_remaining)
        factory_idle_cost = settings.FACTORY_IDLE_COST_PER_DAY * idle_days
        
        # Evaluate alternate suppliers
        best_alt = None
        min_markup = float('inf')
        
        # Primary price is unknown in the material payload natively, but we can assume
        # a standard calculation or require it from Risk Assessment. For this demo,
        # we just take the first alternate supplier and calculate premium based on unit_price.
        
        if mat["alternate_suppliers"]:
            # Sort alternates by unit price
            alts_sorted = sorted(mat["alternate_suppliers"], key=lambda x: x["unit_price"])
            best_alt = alts_sorted[0]
            
            # Simplified markup logic: Assume primary was 20% cheaper than the best backup
            primary_assumed_price = best_alt["unit_price"] * 0.8 
            
            # Quantity to order: Enough to cover the delay period + 2 days buffer
            order_qty = mat["daily_consumption_rate"] * (delay_days + 2)
            
            backup_premium = (best_alt["unit_price"] - primary_assumed_price) * order_qty
            net_savings = factory_idle_cost - backup_premium
            
            recommendation = "EXECUTE_BACKUP_PO" if net_savings > 0 else "HOLD_AND_MONITOR"
            
            analysis_results.append({
                "material_id": mat["material_id"],
                "material_name": mat["name"],
                "days_remaining": days_remaining,
                "factory_idle_cost": factory_idle_cost,
                "backup_premium": backup_premium,
                "net_savings": net_savings,
                "recommendation": recommendation,
                "best_alternate": best_alt,
                "order_qty": order_qty,
                "total_cost": best_alt["unit_price"] * order_qty
            })
            
    return {"financial_analysis": analysis_results}
