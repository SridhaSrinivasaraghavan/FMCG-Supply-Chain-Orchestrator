from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.market_intel import market_intel_node
from app.agents.risk_assessment import risk_assessment_node
from app.agents.financial_analyst import financial_analyst_node
from app.agents.strategy_execution import strategy_execution_node

def route_after_analysis(state: AgentState) -> str:
    """
    Conditional routing: if no materials require execution, end graph early.
    """
    if state.get("error"):
         return "end"
         
    financial_analysis = state.get("financial_analysis", [])
    if not financial_analysis:
        return "end"
        
    # Check if ANY recommendation is EXECUTE_BACKUP_PO
    # (Actually we want strategy execution to run even for HOLD_AND_MONITOR to log it)
    return "strategy_execution"

# Build Graph
workflow = StateGraph(AgentState)

workflow.add_node("market_intel", market_intel_node)
workflow.add_node("risk_assessment", risk_assessment_node)
workflow.add_node("financial_analyst", financial_analyst_node)
workflow.add_node("strategy_execution", strategy_execution_node)

# Set edges
workflow.set_entry_point("market_intel")
workflow.add_edge("market_intel", "risk_assessment")
workflow.add_edge("risk_assessment", "financial_analyst")

# Conditional routing after financial analysis
workflow.add_conditional_edges(
    "financial_analyst",
    route_after_analysis,
    {
        "strategy_execution": "strategy_execution",
        "end": END
    }
)

workflow.add_edge("strategy_execution", END)

# Compile the graph
app_graph = workflow.compile()
