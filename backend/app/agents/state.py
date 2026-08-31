from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    The shared state dictionary representing the workflow state at any given node in the graph.
    
    This state flows through all agents in the pipeline:
    Market Intel → Risk Assessment → Financial Analyst → Strategy Execution
    
    Each agent reads from previous fields and writes to its own output fields.
    """
    # ─── Pipeline Metadata ───
    pipeline_run_id: str                     # UUID for correlating all actions in this run
    started_at: str                          # ISO timestamp when pipeline was triggered
    
    # ─── Input ───
    raw_news: str                            # Raw news text to analyze
    region: Optional[str]                    # Pre-specified region (if known)
    auto_triggered: Optional[bool]           # True if triggered by auto-scanner
    
    # ─── Agent 1: Market Intel Output ───
    threat_payload: Optional[dict]           # Structured threat extraction (validated)
    
    # ─── Agent 2: Risk Assessment Output ───
    impacted_materials: Optional[list]       # Materials at risk (direct + indirect)
    risk_reasoning: Optional[str]            # LLM reasoning about indirect risks
    risk_level: Optional[str]               # Overall risk level: LOW/MEDIUM/HIGH/CRITICAL
    
    # ─── Agent 3: Financial Analyst Output ───
    financial_analysis: Optional[list]       # Cost analysis + CFO decisions per material
    
    # ─── Agent 4: Strategy Execution Output ───
    recommended_actions: Optional[list]      # Actions taken (PO, advisory, hold)
    executive_summary: Optional[str]         # LLM-generated executive summary
    execution_status: Optional[str]          # Final status: COMPLETED / ERROR
    
    # ─── Error Handling ───
    error: Optional[str]                     # Error capture for conditional routing
    
    # ─── LangGraph Internal ───
    messages: Annotated[list, add_messages]  # Conversation history
