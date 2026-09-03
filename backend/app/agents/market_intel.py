"""
Agent 1: Market Intel Agent (The Scout) — v3.1

Key improvements over v3.0:
- Realistic delay inference table (LLM infers delay from event type, not extracts from text)
- Confidence scoring (0-100): measures how certain the LLM is about the threat
- is_supply_chain_relevant flag: prevents wasting LLM compute on irrelevant news
- Confidence < 60 → flagged for human review in approval queue
"""
from app.agents.state import AgentState
from app.agents.validators import validate_threat_payload
from app.services.llm_factory import get_llm
from app.services.llm_utils import invoke_llm_with_retry, parse_llm_json
from langchain_core.prompts import PromptTemplate
import logging

logger = logging.getLogger(__name__)


MARKET_INTEL_PROMPT = PromptTemplate(
    template="""You are a Supply Chain Threat Intelligence Engine for a major FMCG manufacturer in India.

Your job: Read a news report and extract a structured JSON threat assessment.

## DELAY INFERENCE TABLE
News articles RARELY state the exact delay. Use this table to INFER it based on event type and severity:

| Event Type               | Realistic Delay Estimate                          |
|--------------------------|---------------------------------------------------|
| road_accident_minor      | 3-8 hours → use 0.3 days                         |
| road_accident_major      | 12-48 hours → use 1-2 days                       |
| road_bridge_closure      | 7-30 days (structural damage or repair)           |
| flood_localized          | 2-5 days (streets flood, clear in 1-3 days)      |
| flood_regional_severe    | 10-25 days (monsoon, widespread, rail+road)       |
| fire_warehouse           | 21-60 days (facility rebuilt/alternate found)     |
| fire_factory             | 45-120 days (production line destroyed)           |
| port_strike              | 7-21 days                                         |
| rail_strike              | 5-14 days                                         |
| highway_blockade         | 3-10 days (political, protest)                    |
| earthquake_moderate      | 14-45 days                                        |
| earthquake_severe        | 60-120 days                                       |
| chemical_spill_road      | 2-5 days (road closed for cleanup)                |
| chemical_spill_facility  | 30-90 days (facility shutdown)                    |
| cyclone_severe_weather   | 3-10 days (depends on landfall path)              |
| dense_fog_highway        | 0.5-1 day                                         |
| crop_failure_shortage    | 30-90 days                                        |
| customs_regulatory_delay | 3-10 days                                         |
| transport_disruption     | 1-5 days (generic)                                |
| other                    | 3-7 days (default)                                |

## REGION MAPPING (India)
- Delhi, Haryana, Punjab, UP, Uttarakhand, Himachal, J&K, Rajasthan → North
- Mumbai, Pune, Nashik, Goa, Gujarat → West
- Bangalore, Chennai, Hyderabad, Kerala, Tamil Nadu, Andhra → South
- Kolkata, West Bengal, Odisha, Bihar, Jharkhand, Northeast → East
- MP, Chhattisgarh, Telangana (central region), Nagpur → Central

## SEVERITY MAPPING (based on delay):
- < 1 day = LOW
- 1-4 days = MEDIUM
- 5-14 days = HIGH
- 15+ days = CRITICAL

## CONFIDENCE SCORING (how certain are you that this is a real, supply-chain-relevant threat?):
- 90-100: Direct, confirmed disruption. Specific location. Clear impact on freight/production.
- 70-89: Credible report. Location implied. Likely to cause delays.
- 50-69: Possible impact but vague. Location unclear or event not confirmed.
- 30-49: Indirect mention. May affect supply chain but not central to article.
- 0-29: Unrelated, rumour, or irrelevant to FMCG supply chain.

## YOUR TASK
1. Determine if this article is relevant to our supply chain (freight, raw materials, roads, ports, factories, floods, strikes). NOTE: Assume ANY major freight, port, or transport disruption is highly relevant to us, even if FMCG is not explicitly mentioned.
2. If NOT relevant, set is_supply_chain_relevant=false and everything else to defaults.
3. If relevant, extract all fields carefully.

Output ONLY valid JSON — no markdown, no explanation:
{{
  "is_supply_chain_relevant": true,
  "confidence_score": 85,
  "event_type": "flood_regional_severe",
  "region": "North",
  "severity": "HIGH",
  "estimated_delay_days": 14,
  "affected_commodities": ["wheat", "flour"],
  "key_location": "Delhi-Meerut highway near Ghaziabad",
  "summary": "Severe monsoon flooding in North region blocks NH58 and NH24, halting freight for an estimated 2 weeks."
}}

Valid event_type values: road_accident_minor, road_accident_major, road_bridge_closure, flood_localized, flood_regional_severe, fire_warehouse, fire_factory, port_strike, rail_strike, highway_blockade, earthquake_moderate, earthquake_severe, chemical_spill_road, chemical_spill_facility, cyclone_severe_weather, dense_fog_highway, crop_failure_shortage, customs_regulatory_delay, transport_disruption, other

News Article:
{raw_news}
""",
    input_variables=["raw_news"],
)


def market_intel_node(state: AgentState):
    """Agent 1: Extracts structured threat from unstructured news with confidence scoring."""
    pipeline_id = state.get("pipeline_run_id", "unknown")
    logger.info(f"[market_intel] Pipeline {pipeline_id}: Starting threat extraction")

    raw_news = state.get("raw_news", "")
    if not raw_news or not raw_news.strip():
        logger.warning(f"[market_intel] Pipeline {pipeline_id}: Empty news text")
        return {"error": "No news text provided.", "is_supply_chain_relevant": False}

    llm = get_llm("market_intel")

    if hasattr(llm, '_llm_type') and llm._llm_type == "fake-mock-llm":
        mock = {
            "is_supply_chain_relevant": True,
            "confidence_score": 90,
            "event_type": "flood_regional_severe",
            "region": "North",
            "severity": "CRITICAL",
            "estimated_delay_days": 15,
            "affected_commodities": ["wheat", "sugar"],
            "key_location": "Delhi/NCR",
            "summary": "Mock: Severe flooding in North halting freight transport."
        }
        validated = validate_threat_payload(mock)
        return {"threat_payload": validated, "confidence_score": 90, "is_supply_chain_relevant": True}

    try:
        prompt_text = MARKET_INTEL_PROMPT.format(raw_news=raw_news)
        content = invoke_llm_with_retry(
            llm=llm, prompt_text=prompt_text, max_retries=2,
            pipeline_run_id=pipeline_id, agent_name="market_intel",
        )

        if content is None:
            return {"error": "Market Intel LLM failed after retries.", "is_supply_chain_relevant": False}

        result = parse_llm_json(content)
        if not isinstance(result, dict):
            result = {}

        # Check relevance first
        is_relevant = result.get("is_supply_chain_relevant", True)
        confidence = int(result.get("confidence_score", 70))

        if not is_relevant or confidence < 20:
            logger.info(f"[market_intel] Pipeline {pipeline_id}: Article NOT relevant (confidence={confidence}). Aborting pipeline.")
            return {
                "is_supply_chain_relevant": False,
                "confidence_score": confidence,
                "threat_payload": None,
            }

        validated = validate_threat_payload(result)

        logger.info(
            f"[market_intel] Pipeline {pipeline_id}: Threat extracted — "
            f"{validated['event_type']} in {validated['region']} "
            f"({validated['severity']}, confidence={confidence}%)"
        )
        return {
            "threat_payload": validated,
            "confidence_score": confidence,
            "is_supply_chain_relevant": True,
        }

    except Exception as e:
        logger.error(f"[market_intel] Pipeline {pipeline_id}: Error — {e}")
        return {"error": f"Market Intel failed: {str(e)}", "is_supply_chain_relevant": False}
