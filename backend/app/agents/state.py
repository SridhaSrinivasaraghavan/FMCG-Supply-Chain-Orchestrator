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
    risk_reasoning: Optional[str]           # LLM reasoning about indirect risks
    financial_analysis: Optional[list]      # from Financial Analyst
    recommended_actions: Optional[list]     # from Strategy Execution
    executive_summary: Optional[str]        # LLM-generated executive summary of entire incident
    execution_status: Optional[str]         # final status
    auto_triggered: Optional[bool]          # True if triggered by auto-scanner
    error: Optional[str]                    # error capture
    messages: Annotated[list, add_messages] # conversation history

