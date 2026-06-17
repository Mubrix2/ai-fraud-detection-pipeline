# app/core/investigation_agent.py
"""
AI Investigation Agent for fraud analysts.

Built with LangGraph. Analysts ask questions in natural language.
The agent queries real data using four tools.

Example queries:
  "Why was TXN-001 flagged?"
  "Show me velocity for customer C1234567890"
  "List the last 10 blocked transactions"
  "Generate investigation report for TXN-001"
"""
import logging
from typing import Annotated

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from app.config import GROQ_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = SYSTEM_PROMPT = """You are a fraud investigation assistant for a fintech compliance team.

CRITICAL RULES FOR TOOL USE:
1. Call tools ONE AT A TIME. Never nest a tool call inside another tool's arguments.
2. If you need a transaction ID, call list_flagged_transactions FIRST, get the ID 
   from the result, THEN call get_transaction_details or generate_investigation_report.
3. Wait for each tool result before deciding your next action.
4. Never invent transaction IDs — always retrieve them from list_flagged_transactions.

WORKFLOW EXAMPLE:
User: "Generate a report for the latest blocked transaction"
Step 1: Call list_flagged_transactions(limit="1")
Step 2: Read the transaction_id from the result
Step 3: Call generate_investigation_report(transaction_id="<id from step 2>")

Be concise. Lead with the decision and risk level, then evidence."""


@tool
def get_transaction_details(transaction_id: str) -> str:
    """Get full details of a specific transaction by ID."""
    from app.streaming.consumer import get_result
    result = get_result(transaction_id)
    if not result:
        return f"Transaction {transaction_id} not found."

    prob  = result.get("fraud_probability", 0) * 100
    rules = result.get("triggered_rules", [])
    reasons = "\n".join(
        f"  - {r['description']} (SHAP: {r['shap_value']:+.3f})"
        for r in result.get("top_reasons", [])[:3]
    )
    return (
        f"Transaction: {transaction_id}\n"
        f"Decision:    {result.get('decision')}\n"
        f"Fraud Prob:  {prob:.1f}%\n"
        f"Amount:      ₦{result.get('transaction', {}).get('amount', 0):,.0f}\n"
        f"Type:        {result.get('transaction', {}).get('type')}\n"
        f"AML Flags:   {result.get('aml_flag_count', 0)}\n"
        f"Rules:       {', '.join(rules) if rules else 'none'}\n"
        f"Top reasons:\n{reasons or '  No SHAP data'}\n"
        f"SAR required: {result.get('requires_sar', False)}"
    )


@tool
def list_flagged_transactions(limit: str = "10") -> str:
    """
    List recently flagged (REVIEW or BLOCK) transactions.

    Args:
        limit: Maximum number of transactions to return (1-20).
               Accepts a number as a string, e.g. "10".
    """
    # Groq's tool-calling sometimes sends numbers as strings.
    # Coerce defensively — int() handles both "5" and 5.
    try:
        limit_int = int(limit)
    except (ValueError, TypeError):
        limit_int = 10

    limit_int = max(1, min(limit_int, 20))  # clamp to 1-20

    from app.streaming.consumer import get_all_results
    flagged = [
        r for r in get_all_results()
        if r.get("decision") in ("REVIEW", "BLOCK")
    ][:limit_int]

    if not flagged:
        return "No flagged transactions in the current session."

    lines = [f"Flagged transactions ({len(flagged)}):"]
    for r in flagged:
        lines.append(
            f"  {r['transaction_id'][:20]:<22} | "
            f"{r['decision']:<6} | "
            f"{r.get('fraud_probability', 0)*100:.1f}% | "
            f"₦{r.get('transaction', {}).get('amount', 0):>12,.0f}"
        )
    return "\n".join(lines)


@tool
def get_customer_velocity(customer_id: str) -> str:
    """Get velocity statistics for a customer account."""
    from app.core.velocity_engine import _history
    history = _history.get(customer_id, [])
    if not history:
        return f"No transaction history for {customer_id}."

    amounts = [amt for _, amt in history]
    return (
        f"Customer: {customer_id}\n"
        f"Total transactions tracked: {len(history)}\n"
        f"Average amount:  ₦{sum(amounts)/len(amounts):,.0f}\n"
        f"Maximum amount:  ₦{max(amounts):,.0f}\n"
        f"Total value:     ₦{sum(amounts):,.0f}"
    )


@tool
def generate_investigation_report(transaction_id: str) -> str:
    """Generate a structured investigation report for a transaction."""
    from app.streaming.consumer import get_result
    from datetime import datetime, timezone

    result = get_result(transaction_id)
    if not result:
        return f"Cannot generate report: {transaction_id} not found."

    now   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    prob  = result.get("fraud_probability", 0) * 100
    rules = result.get("triggered_rules", [])
    reasons = "\n".join(
        f"  {i+1}. {r['description']} ({r['impact']} impact)"
        for i, r in enumerate(result.get("top_reasons", [])[:5])
    )

    return (
        f"FRAUD INVESTIGATION REPORT\n"
        f"{'='*40}\n"
        f"Generated:    {now}\n"
        f"Transaction:  {transaction_id}\n"
        f"Decision:     {result.get('decision')}\n"
        f"Fraud Prob:   {prob:.1f}%\n"
        f"Amount:       ₦{result.get('transaction', {}).get('amount', 0):,.0f}\n"
        f"Type:         {result.get('transaction', {}).get('type')}\n"
        f"AML Flags:    {result.get('aml_flag_count', 0)}\n"
        f"SAR Required: {result.get('requires_sar', False)}\n"
        f"CTR Required: {result.get('requires_ctr', False)}\n\n"
        f"Business Rules Triggered:\n"
        f"  {chr(10).join(rules) if rules else '  None'}\n\n"
        f"SHAP Risk Factors:\n{reasons or '  Not available'}\n\n"
        f"Explanation:\n{result.get('explanation_text', 'N/A')}\n"
        f"Processing:   {result.get('processing_ms', 0):.1f}ms"
    )

@tool
def get_latest_flagged_transaction() -> str:
    """
    Get the most recently flagged (REVIEW or BLOCK) transaction directly.
    Use this instead of list_flagged_transactions when the user asks about
    'the latest', 'the most recent', or 'the last' flagged transaction.
    Returns full details including decision, risk, rules, and SHAP reasons.
    """
    from app.streaming.consumer import get_all_results
    flagged = [
        r for r in get_all_results()
        if r.get("decision") in ("REVIEW", "BLOCK")
    ]
    if not flagged:
        return "No flagged transactions found in the current session."

    r = flagged[0]  # already sorted newest first
    prob  = r.get("fraud_probability", 0) * 100
    rules = r.get("triggered_rules", [])
    reasons = "\n".join(
        f"  - {x['description']} (SHAP: {x['shap_value']:+.3f})"
        for x in r.get("top_reasons", [])[:3]
    )
    return (
        f"Latest flagged transaction:\n"
        f"ID:       {r['transaction_id']}\n"
        f"Decision: {r['decision']}\n"
        f"Risk:     {prob:.1f}%\n"
        f"Amount:   ₦{r.get('transaction', {}).get('amount', 0):,.0f}\n"
        f"Rules:    {', '.join(rules) if rules else 'none'}\n"
        f"SAR:      {r.get('requires_sar', False)}\n"
        f"Reasons:\n{reasons or '  No SHAP data'}"
    )

_TOOLS = [
    get_transaction_details,
    list_flagged_transactions,
    get_customer_velocity,
    generate_investigation_report,
    get_latest_flagged_transaction,
]

_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        llm = ChatGroq(
            api_key    = GROQ_API_KEY,
            model      = LLM_MODEL,
            temperature= 0.1,
        ).bind_tools(_TOOLS)

        class State(TypedDict):
            messages: Annotated[list, add_messages]

        def llm_node(state: State):
            msgs = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
            return {"messages": [llm.invoke(msgs)]}

        def should_continue(state: State):
            last = state["messages"][-1]
            return "tools" if getattr(last, "tool_calls", None) else END

        graph = StateGraph(State)
        graph.add_node("llm", llm_node)
        graph.add_node("tools", ToolNode(_TOOLS))
        graph.set_entry_point("llm")
        graph.add_conditional_edges("llm", should_continue, {"tools": "tools", END: END})
        graph.add_edge("tools", "llm")

        _agent = graph.compile(checkpointer=MemorySaver())
        logger.info("Investigation agent ready")
    return _agent


def investigate(question: str, session_id: str = "analyst-1") -> str:
    agent  = _get_agent()
    result = agent.invoke(
        {"messages": [HumanMessage(content=question)]},
        config={"configurable": {"thread_id": session_id}, "recursion_limit": 20},
    )
    return result["messages"][-1].content