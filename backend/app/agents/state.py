from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages
from app.schemas import ThreatPayload, ImpactedMaterialInfo, FinancialAnalysis

class AgentState(TypedDict):
    """
    The shared state dictionary representing the workflow state at any given node in the graph.
    """
    raw_news: str
    region: Optional[str]
    threat_payload: Optional[dict]          # from Market Intel
    impacted_materials: Optional[list]      # from Risk Assessment
    financial_analysis: Optional[list]      # from Financial Analyst
    recommended_actions: Optional[list]     # from Strategy Execution
    execution_status: Optional[str]         # final status
    error: Optional[str]                    # error capture
    messages: Annotated[list, add_messages] # conversation history
