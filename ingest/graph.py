from langgraph.graph import END, StateGraph

from ingest import nodes
from ingest.state import IngestState


def _halt_or(next_node):
    def router(state):
        if state.get("halt"):
            return END
        return next_node

    return router


def build_graph():
    g = StateGraph(IngestState)

    g.add_node("intake", nodes.intake)
    g.add_node("validate", nodes.validate)
    g.add_node("speaker_resolution", nodes.speaker_resolution)
    g.add_node("analyzer", nodes.analyzer)
    g.add_node("grounding_gate", nodes.grounding_gate)
    g.add_node("indexer", nodes.indexer)

    g.set_entry_point("intake")

    # halt-aware conditional edges after intake and validate
    g.add_conditional_edges("intake", _halt_or("validate"), {"validate": "validate", END: END})
    g.add_conditional_edges(
        "validate", _halt_or("speaker_resolution"), {"speaker_resolution": "speaker_resolution", END: END}
    )
    g.add_edge("speaker_resolution", "analyzer")
    # analyzer can also halt
    g.add_conditional_edges(
        "analyzer", _halt_or("grounding_gate"), {"grounding_gate": "grounding_gate", END: END}
    )
    g.add_edge("grounding_gate", "indexer")
    g.add_edge("indexer", END)

    return g.compile()
