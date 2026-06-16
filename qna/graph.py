from langgraph.graph import END, StateGraph

from qna import nodes
from qna.state import QnAState


def _classifier_route(state):
    t = state.get("turn_type")
    if t in ("social", "meta", "out_of_scope", "unclear"):
        return "fixed_response"
    if t == "task_ambiguous":
        return "clarify"
    # task / clarify_answer / correction -> task subgraph
    return "rewrite"


def _gate_route(state):
    verdict = state.get("gate_verdict")
    if verdict == "PASS":
        return "answer"
    if verdict == "RETRY":
        return "retrieve"
    return "bail"


def build_qna_graph():
    g = StateGraph(QnAState)

    g.add_node("classifier", nodes.classifier_node)
    g.add_node("fixed_response", nodes.fixed_response_node)
    g.add_node("clarify", nodes.clarify_node)
    g.add_node("rewrite", nodes.rewrite_node)
    g.add_node("router", nodes.router_node)
    g.add_node("retrieve", nodes.retrieve_node)
    g.add_node("compose", nodes.compose_node)
    g.add_node("answer_gate", nodes.answer_gate_node)
    g.add_node("answer", nodes.answer_node)
    g.add_node("bail", nodes.bail_node)

    g.set_entry_point("classifier")

    g.add_conditional_edges(
        "classifier",
        _classifier_route,
        {
            "fixed_response": "fixed_response",
            "clarify": "clarify",
            "rewrite": "rewrite",
        },
    )
    g.add_edge("fixed_response", END)
    g.add_edge("clarify", END)

    # task subgraph
    g.add_edge("rewrite", "router")
    g.add_edge("router", "retrieve")
    g.add_edge("retrieve", "compose")
    g.add_edge("compose", "answer_gate")

    g.add_conditional_edges(
        "answer_gate",
        _gate_route,
        {"answer": "answer", "retrieve": "retrieve", "bail": "bail"},
    )
    g.add_edge("answer", END)
    g.add_edge("bail", END)

    return g.compile()
