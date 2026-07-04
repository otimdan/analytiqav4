from pydantic import BaseModel, Field
from typing import Optional


class ClassificationResult(BaseModel):
    regime: str
    confidence: str
    needs_disambiguation: bool = False
    reasoning: Optional[str] = None


class HypothesisExtraction(BaseModel):
    is_hypothesis: bool
    research_question: Optional[str] = None
    named_variables: list[str] = Field(default_factory=list)
    matched_columns: list[str] = Field(default_factory=list)
    unmatched_variables: list[str] = Field(default_factory=list)
    hypothesis_type: Optional[str] = None


class ConfirmatoryNarration(BaseModel):
    plain_language_result: str
    statistical_summary: str
    suspect_result: bool = False
    suspect_reason: Optional[str] = None


class OrientationRecap(BaseModel):
    what_has_been_done: list[str]
    suggested_next: str
    is_hypothesis_candidate: bool = False
    candidate_hypothesis_text: Optional[str] = None


class RepairRequest(BaseModel):
    original_code: str
    error_summary: str
    hint: Optional[str] = None
    temperature: float = 0.1
