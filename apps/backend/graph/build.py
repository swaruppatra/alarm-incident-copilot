from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from apps.backend.graph.nodes import (
    await_confirmation_node,
    call_mcp_tools_node,
    classify_intent_node,
    execute_write_node,
    plan_node,
    respond_node,
    retrieve_docs_node,
    route_after_confirmation,
    route_after_mcp_call,
    route_after_plan,
    route_after_synthesize,
    synthesize_answer_node,
)
from apps.backend.graph.state import AgentState

agent_builder = StateGraph(AgentState)
agent_builder.add_node("classify_intent", classify_intent_node)
agent_builder.add_node("plan", plan_node)
agent_builder.add_node("call_mcp_tools", call_mcp_tools_node)
agent_builder.add_node("retrieve_docs", retrieve_docs_node)
agent_builder.add_node("synthesize_answer", synthesize_answer_node)
agent_builder.add_node("await_confirmation", await_confirmation_node)
agent_builder.add_node("execute_write", execute_write_node)
agent_builder.add_node("respond", respond_node)

agent_builder.add_edge(START, "classify_intent")
agent_builder.add_edge("classify_intent", "plan")
agent_builder.add_conditional_edges("plan", route_after_plan, {
    "call_mcp_tools": "call_mcp_tools", "retrieve_docs": "retrieve_docs", "synthesize_answer": "synthesize_answer",
})
agent_builder.add_conditional_edges("call_mcp_tools", route_after_mcp_call, {
    # "error" -> synthesize_answer, not respond: a failed tool call still has
    # to produce a real degraded answer ("X succeeded, Y was unavailable"),
    # not the raw "Tool call failed: ..." ToolMessage as the final response.
    "plan": "plan", "confirm_write": "await_confirmation", "error": "synthesize_answer",
})
agent_builder.add_edge("retrieve_docs", "plan")
agent_builder.add_conditional_edges("synthesize_answer", route_after_synthesize, {
    "await_confirmation": "await_confirmation", "respond": "respond",
})
agent_builder.add_conditional_edges("await_confirmation", route_after_confirmation, {
    "execute_write": "execute_write", "respond": "respond",
})
agent_builder.add_edge("execute_write", "respond")
agent_builder.add_edge("respond", END)
graph = agent_builder.compile(checkpointer=MemorySaver())  # checkpointer required for interrupt()


if __name__ == "__main__":
    from pathlib import Path

    output_path = Path(__file__).resolve().parents[3] / "docs" / "agent-graph.png"
    output_path.write_bytes(graph.get_graph().draw_mermaid_png())
    print(f"Saved graph diagram to {output_path}")
