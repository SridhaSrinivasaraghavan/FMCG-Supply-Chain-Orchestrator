from app.agents.state import AgentState
from app.tools.db_tools import get_impacted_materials

def risk_assessment_node(state: AgentState):
    """
    Agent 2: Takes the region from the threat payload and queries the database
    to find impacted primary suppliers and their alternate backups.
    """
    print("--- RISK ASSESSMENT AGENT ---")
    payload = state.get("threat_payload")
    
    if not payload:
        return {"error": "No threat payload provided from Market Intel."}
        
    region = payload.get("region")
    if not region:
         return {"error": "No region found in threat payload."}
         
    try:
        impacted_materials = get_impacted_materials(region)
        return {"impacted_materials": impacted_materials}
    except Exception as e:
        print(f"Error in Risk Assessment: {e}")
        return {"error": str(e)}
