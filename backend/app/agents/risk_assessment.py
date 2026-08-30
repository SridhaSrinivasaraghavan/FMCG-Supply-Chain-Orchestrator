"""
Agent 2: Risk Assessment Agent (Generalized Intelligence)

Queries the database for directly impacted materials (based on supplier region),
AND pulls the FULL logistics map (factories, routes, schedules).
Passes all of this to the LLM to identify generalized indirect impacts
(e.g. route closures, receiving window violations, cascading delays).
"""
from app.agents.state import AgentState
from app.tools.db_tools import get_impacted_materials, get_all_materials_summary, get_full_logistics_context
from app.services.llm_factory import get_llm
from langchain_core.prompts import PromptTemplate
import json
import logging

logger = logging.getLogger(__name__)


RISK_REASONING_PROMPT = PromptTemplate(
    template="""You are a Senior Supply Chain Risk Analyst.

A disruption has been detected. Below is the threat data and our physical supply chain map.

## Threat Information
- Event: {event_type}
- Region/Location: {region}
- Severity: {severity}
- Raw News Summary: {summary}

## Our Supply Chain Map (Logistics Context)
{logistics_context}

## Directly Impacted Materials (Suppliers in the affected region)
{direct_impacts}

## Full Inventory Context
{full_inventory}

## Your Task
Think deeply like a human supply chain expert. Do NOT just look at direct impacts.
Look at the Logistics Context and find intersections:

1. **ROUTE CONFLICTS**: Does the news mention a highway, city, or region that our trucks pass through? If a route is blocked, calculate the likely delay.
2. **TIMING & SCHEDULES**: If a truck is delayed, does it miss the factory's `receiving_window`? (If a truck arrives after the window closes, the delivery is pushed to the NEXT day, meaning a 3-hour traffic delay becomes a 24-hour supply delay).
3. **INDIRECT MATERIAL RISKS**: Which specific materials are on the delayed routes?
4. **SEVERITY**: Rate the final risk as LOW / MEDIUM / HIGH / CRITICAL.

IMPORTANT: You must respond ONLY with a valid JSON object in this exact format:
{{
  "reasoning": "Your detailed human-like analysis text here...",
  "indirectly_impacted_material_ids": [1, 2] // List of material_ids on the affected routes
}}
""",
    input_variables=["event_type", "region", "severity", "summary", "logistics_context", "direct_impacts", "full_inventory"],
)


def risk_assessment_node(state: AgentState):
    print("--- RISK ASSESSMENT AGENT ---")
    payload = state.get("threat_payload")

    if not payload:
        return {"error": "No threat payload provided from Market Intel."}

    region = payload.get("region", "")
    summary = payload.get("summary", "")

    try:
        # 1. Direct database lookup (deterministic)
        impacted_materials = get_impacted_materials(region)
        
        # 2. Pull generalized logistics context
        logistics_context = get_full_logistics_context()

        # 3. LLM reasoning for indirect risks and route conflicts
        risk_output = _analyze_generalized_risks(payload, impacted_materials, logistics_context)
        
        reasoning = risk_output.get("reasoning", "No analysis provided.")
        indirect_ids = risk_output.get("indirectly_impacted_material_ids", [])
        
        # 4. Merge indirect impacts with direct impacts
        from app.tools.db_tools import get_materials_with_alternates
        
        if indirect_ids:
            # Get the full details for the indirectly impacted materials
            indirect_materials = get_materials_with_alternates(indirect_ids)
            
            # Merge them, ensuring no duplicates
            existing_ids = {m["material_id"] for m in impacted_materials}
            for m in indirect_materials:
                if m["material_id"] not in existing_ids:
                    impacted_materials.append(m)

        return {
            "impacted_materials": impacted_materials,  # Now includes indirect impacts!
            "risk_reasoning": reasoning,
        }
    except Exception as e:
        logger.error(f"Error in Risk Assessment: {e}")
        return {"error": str(e)}


def _analyze_generalized_risks(threat_payload: dict, direct_impacts: list, logistics_context: dict) -> dict:
    llm = get_llm("risk_assessment")

    if hasattr(llm, '_llm_type') and llm._llm_type == "fake-mock-llm":
        return {"reasoning": "Mock mode: Generalized risk analysis skipped.", "indirectly_impacted_material_ids": []}

    direct_str = json.dumps(direct_impacts, indent=2) if direct_impacts else "None"
    logistics_str = json.dumps(logistics_context, indent=2)
    
    try:
        full_inventory = get_all_materials_summary()
        inventory_str = json.dumps(full_inventory, indent=2)
    except Exception:
        inventory_str = "Unavailable"

    try:
        prompt_text = RISK_REASONING_PROMPT.format(
            event_type=threat_payload.get("event_type", "unknown"),
            region=threat_payload.get("region", "unknown"),
            severity=threat_payload.get("severity", "unknown"),
            summary=threat_payload.get("summary", "unknown"),
            logistics_context=logistics_str,
            direct_impacts=direct_str,
            full_inventory=inventory_str,
        )

        response = llm.invoke(prompt_text)
        content = response.content if hasattr(response, 'content') else str(response)
        
        # Clean up potential markdown from the LLM
        content = content.replace("```json", "").replace("```", "").strip()
        parsed_output = json.loads(content)
        
        print(f"  LLM Risk Reasoning: {parsed_output.get('reasoning', '')[:120]}...")
        return parsed_output

    except Exception as e:
        logger.error(f"LLM generalized risk reasoning failed: {e}")
        return {"reasoning": f"LLM reasoning unavailable: {str(e)}", "indirectly_impacted_material_ids": []}
