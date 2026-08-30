from app.agents.state import AgentState
from app.services.llm_factory import get_llm
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.schemas import ThreatPayload
import json

def market_intel_node(state: AgentState):
    """
    Agent 1: Ingests unstructured news and extracts a structured JSON threat payload.
    """
    print("--- MARKET INTEL AGENT ---")
    raw_news = state.get("raw_news", "")
    
    llm = get_llm("market_intel")
    
    parser = JsonOutputParser(pydantic_object=ThreatPayload)
    
    prompt = PromptTemplate(
        template="""You are a Supply Chain Market Intelligence Agent.
        Analyze the following disruption report and extract the key information into JSON.
        
        CRITICAL INSTRUCTIONS:
        - Do NOT repeat the JSON schema back to me. 
        - You must actually extract the values from the Disruption Report and fill out the JSON.
        - ONLY output valid, raw JSON. Do not add markdown blocks like ```json or any other text.
        
        {format_instructions}
        
        Disruption Report:
        {raw_news}
        """,
        input_variables=["raw_news"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    
    chain = prompt | llm
    
    try:
        # Check if we are using the mock LLM to avoid real API calls in testing
        if llm._llm_type == "fake-mock-llm":
             response = llm.invoke(prompt.format(raw_news=raw_news))
             result = json.loads(response.content)
        else:
            response = chain.invoke({"raw_news": raw_news})
            if isinstance(response, dict):
                 result = response
            else:
                 # Attempt parsing if it's an AIMessage
                 result = parser.parse(response.content)
                 
        return {"threat_payload": result}
    except Exception as e:
        print(f"Error in Market Intel: {e}")
        return {"error": str(e)}
