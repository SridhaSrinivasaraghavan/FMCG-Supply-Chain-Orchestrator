"""
Agent 1: Market Intel Agent (The Scout)

Ingests unstructured news text and extracts a structured JSON threat payload.
Uses improved prompts with explicit schema examples, severity mapping,
and validated output via the inter-agent validation layer.
"""
from app.agents.state import AgentState
from app.agents.validators import validate_threat_payload
from app.services.llm_factory import get_llm
from app.services.llm_utils import invoke_llm_with_retry, parse_llm_json
from langchain_core.prompts import PromptTemplate
import json
import logging

logger = logging.getLogger(__name__)


# ─── Improved Prompt: Explicit schema with severity mapping ───
MARKET_INTEL_PROMPT = PromptTemplate(
    template="""You are a Supply Chain Threat Extraction Engine.
Given a disruption report, extract EXACTLY these fields as JSON.

EXAMPLE OUTPUT:
{{
  "event_type": "flood",
  "region": "North",
  "severity": "HIGH",
  "estimated_delay_days": 7,
  "affected_commodities": ["wheat", "sugar"],
  "summary": "Severe flooding in North region halting freight transport."
}}

FIELD RULES:
- event_type: One of [flood, strike, shortage, accident, weather, fire, chemical_spill, earthquake, political, transport_disruption, other]
- region: One of [North, South, East, West, Central, Unknown]. Extract from location names (e.g., Delhi/NCR = North, Mumbai = West, Chennai/Bangalore = South, Kolkata = East)
- severity: Use this mapping based on delay duration:
  * 0-2 day delay = "LOW"
  * 3-7 day delay = "MEDIUM"  
  * 8-14 day delay = "HIGH"
  * 15+ day delay = "CRITICAL"
- estimated_delay_days: Integer between 0 and 90. Extract from the text. If unclear, estimate based on event type.
- affected_commodities: List generic commodity names (wheat, sugar, oil, flour, chemicals). NOT brand names.
- summary: One sentence, max 50 words.

CRITICAL: Output ONLY raw JSON. No markdown blocks, no explanation text, no preamble.

Disruption Report:
{raw_news}
""",
    input_variables=["raw_news"],
)


def market_intel_node(state: AgentState):
    """
    Agent 1: Ingests unstructured news and extracts a structured JSON threat payload.
    Uses validation to ensure output conforms to expected schema.
    """
    pipeline_id = state.get("pipeline_run_id", "unknown")
    logger.info(f"[market_intel] Pipeline {pipeline_id}: Starting threat extraction")
    
    raw_news = state.get("raw_news", "")
    if not raw_news or not raw_news.strip():
        logger.warning(f"[market_intel] Pipeline {pipeline_id}: Empty news text received")
        return {"error": "No news text provided to analyze."}
    
    llm = get_llm("market_intel")
    
    # Mock LLM handling
    if hasattr(llm, '_llm_type') and llm._llm_type == "fake-mock-llm":
        mock_result = {
            "event_type": "flood",
            "region": "North",
            "severity": "CRITICAL",
            "estimated_delay_days": 5,
            "affected_commodities": ["wheat", "sugar"],
            "summary": "Mock extraction of severe flooding in the North."
        }
        validated = validate_threat_payload(mock_result)
        logger.info(f"[market_intel] Pipeline {pipeline_id}: Mock mode — returning mock payload")
        return {"threat_payload": validated}
    
    try:
        prompt_text = MARKET_INTEL_PROMPT.format(raw_news=raw_news)
        
        # Use retry utility for robustness
        content = invoke_llm_with_retry(
            llm=llm,
            prompt_text=prompt_text,
            max_retries=2,
            pipeline_run_id=pipeline_id,
            agent_name="market_intel",
        )
        
        if content is None:
            logger.error(f"[market_intel] Pipeline {pipeline_id}: LLM returned no content after retries")
            return {"error": "Market Intel LLM failed to respond after retries."}
        
        # Parse JSON from LLM response
        result = parse_llm_json(content)
        
        if not isinstance(result, dict):
            logger.warning(f"[market_intel] Pipeline {pipeline_id}: LLM returned non-dict: {type(result)}")
            result = {}
        
        # Validate against strict schema
        validated = validate_threat_payload(result)
        
        logger.info(
            f"[market_intel] Pipeline {pipeline_id}: Threat extracted — "
            f"{validated['event_type']} in {validated['region']} ({validated['severity']})"
        )
        return {"threat_payload": validated}
        
    except Exception as e:
        logger.error(f"[market_intel] Pipeline {pipeline_id}: Error — {e}")
        return {"error": f"Market Intel failed: {str(e)}"}
