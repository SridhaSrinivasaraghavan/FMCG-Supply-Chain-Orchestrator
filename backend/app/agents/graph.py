"""
Graph Routing — v3.1

Adds two intelligent early-exit conditions to prevent wasting LLM compute:
1. After Market Intel: exit if article is not supply-chain-relevant OR confidence < 20
2. After Risk Assessment: exit if no materials are impacted in the affected region
3. Conditional routing after Financial Analyst: only run Strategy Execution if there's work to do
"""
# pyrefly: ignore [missing-import]
from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.market_intel import market_intel_node
from app.agents.risk_assessment import risk_assessment_node
from app.agents.financial_analyst import financial_analyst_node
from app.agents.strategy_execution import strategy_execution_node
import logging

logger = logging.getLogger(__name__)

def route_after_market_intel(state: AgentState) -> str:
    """
    Exit early if:
    - An error occurred
    - Article is not supply-chain-relevant (e.g., sports news, politics)
    - Confidence is too low (< 20 = almost certainly irrelevant)
    """
    if state.get("error"):
        logger.info(f"[graph] Exiting after Market Intel: error — {state.get('error')}")
        return "end"

    if not state.get("is_supply_chain_relevant", True):
        logger.info(f"[graph] Exiting after Market Intel: article not supply-chain-relevant")
        return "end"

    threat = state.get("threat_payload")
    if not threat:
        logger.info("[graph] Exiting after Market Intel: no threat payload")
        return "end"

    # Unknown region = no DB match possible, skip all downstream LLM calls
    if threat.get("region", "Unknown") == "Unknown":
        logger.info("[graph] Exiting after Market Intel: region is Unknown, no DB match possible")
        return "end"

    return "risk_assessment"


def route_after_risk_assessment(state: AgentState) -> str:
    """
    Exit early if no materials are impacted (no suppliers in affected region,
    no route conflicts) — prevents CFO LLM from being called with empty data.
    """
    if state.get("error"):
        logger.info("[graph] Exiting after Risk Assessment: error")
        return "end"

    impacted = state.get("impacted_materials", [])
    if not impacted:
        logger.info("[graph] Exiting after Risk Assessment: no impacted materials found")
        return "end"

    return "financial_analyst"


def route_after_financial_analyst(state: AgentState) -> str:
    """
    Only run Strategy Execution if there's actionable output (decisions or approvals).
    """
    if state.get("error"):
        return "end"

    analysis = state.get("financial_analysis", [])
    approvals = state.get("approval_items", [])

    if not analysis and not approvals:
        logger.info("[graph] Exiting after Financial Analyst: no actionable decisions")
        return "end"

    return "strategy_execution"


# ─── Build Graph ───
workflow = StateGraph(AgentState)

workflow.add_node("market_intel", market_intel_node)
workflow.add_node("risk_assessment", risk_assessment_node)
workflow.add_node("financial_analyst", financial_analyst_node)
workflow.add_node("strategy_execution", strategy_execution_node)

workflow.set_entry_point("market_intel")

# Conditional early exits at each stage
workflow.add_conditional_edges(
    "market_intel",
    route_after_market_intel,
    {"risk_assessment": "risk_assessment", "end": END},
)

workflow.add_conditional_edges(
    "risk_assessment",
    route_after_risk_assessment,
    {"financial_analyst": "financial_analyst", "end": END},
)

workflow.add_conditional_edges(
    "financial_analyst",
    route_after_financial_analyst,
    {"strategy_execution": "strategy_execution", "end": END},
)

workflow.add_edge("strategy_execution", END)

app_graph = workflow.compile()
