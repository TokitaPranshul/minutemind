"""Pydantic v2 schemas for MinuteMind.

Two families:
  * Analyzer output (the grounded record an LLM must produce)
  * QnA structured outputs (classifier / rewrite / router / composer / judge)
  * KB record shapes (what we actually store in Chroma)
"""
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Analyzer output (ingestion reference Section 6.2)
# ---------------------------------------------------------------------------
class Evidence(BaseModel):
    speaker: str
    t: str
    quote: str


class Decision(BaseModel):
    id: str
    text: str
    decided_by: list[str] = Field(default_factory=list)
    evidence: Evidence
    confidence: float
    uncertain: bool = False


class ActionItem(BaseModel):
    id: str
    task: str
    owner: Optional[str] = None
    due: Optional[str] = None
    evidence: Evidence
    confidence: float
    uncertain: bool = False


class Entity(BaseModel):
    name: str
    type: str


class OpenQuestion(BaseModel):
    text: str
    raised_by: str
    evidence: Evidence


class Facts(BaseModel):
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)


class SentimentInference(BaseModel):
    label: str
    confidence: float
    evidence: list[str] = Field(default_factory=list)


class PerSpeakerSentiment(BaseModel):
    speaker: str
    label: str
    confidence: float
    evidence: list[str] = Field(default_factory=list)


class RiskBlocker(BaseModel):
    desc: str
    confidence: float
    evidence: list[str] = Field(default_factory=list)


class TensionPoint(BaseModel):
    desc: str
    confidence: float
    evidence: list[str] = Field(default_factory=list)


class DecisionFirmness(BaseModel):
    ref: str
    label: str
    confidence: float
    evidence: list[str] = Field(default_factory=list)


class CommitmentStrength(BaseModel):
    ref: str
    label: str
    confidence: float
    evidence: list[str] = Field(default_factory=list)


class ParticipationBalance(BaseModel):
    note: str
    confidence: float


class OpenLoop(BaseModel):
    desc: str
    confidence: float
    evidence: list[str] = Field(default_factory=list)


class Inferences(BaseModel):
    overall_sentiment: Optional[SentimentInference] = None
    per_speaker_sentiment: list[PerSpeakerSentiment] = Field(default_factory=list)
    urgency: Optional[SentimentInference] = None
    decision_firmness: list[DecisionFirmness] = Field(default_factory=list)
    commitment_strength: list[CommitmentStrength] = Field(default_factory=list)
    risks_blockers: list[RiskBlocker] = Field(default_factory=list)
    tension_points: list[TensionPoint] = Field(default_factory=list)
    participation_balance: Optional[ParticipationBalance] = None
    open_loops: list[OpenLoop] = Field(default_factory=list)


class AnalyzerOutput(BaseModel):
    meeting_id: Optional[str] = None
    summary: str
    facts: Facts
    inferences: Inferences


# ---------------------------------------------------------------------------
# Ingestion grounding judge
# ---------------------------------------------------------------------------
class GroundingVerdict(BaseModel):
    supports_claim: bool
    verdict: str
    note: str = ""


# ---------------------------------------------------------------------------
# QnA structured outputs (QnA reference Section 8)
# ---------------------------------------------------------------------------
class TurnClassification(BaseModel):
    type: str
    note: str = ""


class QueryRewrite(BaseModel):
    standalone_question: str


class RouterOutput(BaseModel):
    intent: str
    retrieval_mode: str
    namespace: list[str] = Field(default_factory=list)
    filters: dict = Field(default_factory=dict)
    note: str = ""


class ComposerOutput(BaseModel):
    answer: str
    citations: list[dict] = Field(default_factory=list)


class AnswerJudgeOutput(BaseModel):
    all_supported: bool
    violations: list = Field(default_factory=list)
    verdict: str
    note: str = ""


# ---------------------------------------------------------------------------
# KB record shapes (Chroma)
# ---------------------------------------------------------------------------
class KBChunk(BaseModel):
    text: str
    company_id: str
    meeting_id: str
    date: str
    speaker: str
    t_start: str
    t_end: str


class KBFact(BaseModel):
    type: str
    text: str
    company_id: str
    meeting_id: str
    date: str
    evidence_speaker: str
    evidence_t: str
    evidence_quote: str
    confidence: float
    owner: Optional[str] = None
    due: Optional[str] = None


class KBInference(BaseModel):
    type: str
    label: str
    confidence: float
    company_id: str
    meeting_id: str
    date: str
    evidence_t: list[str] = Field(default_factory=list)
