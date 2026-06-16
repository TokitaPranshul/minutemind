from typing import Optional, TypedDict


class IngestState(TypedDict, total=False):
    raw_input: dict
    company_id: str
    transcript_of_record: list[dict]  # list of {speaker, t, text}
    analyzer_output: Optional[dict]
    grounding_report: Optional[dict]
    indexed_counts: Optional[dict]
    halt: bool
    halt_reason: Optional[str]
    error: Optional[str]
    chroma_path: Optional[str]
