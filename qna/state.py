from typing import Optional, TypedDict


class QnAState(TypedDict, total=False):
    company_id: str
    chat_history: list[dict]  # list of {role: "user"|"assistant", content: str}
    latest_turn: str
    turn_type: Optional[str]
    standalone_question: Optional[str]
    route: Optional[dict]
    retrieved: Optional[list[dict]]
    draft_answer: Optional[str]
    draft_citations: Optional[list[dict]]
    gate_verdict: Optional[str]
    retry_count: int
    final_answer: Optional[str]
    error: Optional[str]
    chroma_path: Optional[str]
