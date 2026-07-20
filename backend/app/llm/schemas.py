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


class RegressionSpec(BaseModel):
    """LLM extraction of a modelling request into columns. The engine validates
    these against the real dataset and runs the audited template — the LLM only
    identifies which column is the outcome and which are predictors."""
    is_regression: bool
    outcome: Optional[str] = None
    predictors: list[str] = Field(default_factory=list)


class CleaningSpec(BaseModel):
    """LLM extraction of a data-cleaning request into ONE operation + params from
    the fixed menu. The engine validates + runs the audited transform. Flat schema
    (all possible params) for reliable structured output; the handler picks the
    ones the chosen operation needs."""
    is_cleaning: bool
    operation: Optional[str] = None
    column: Optional[str] = None
    columns: Optional[list[str]] = None
    strategy: Optional[str] = None       # impute: mean|median|mode|constant
    method: Optional[str] = None         # outliers: iqr|zscore
    action: Optional[str] = None         # outliers: remove|cap
    value: Optional[str] = None          # impute constant / filter value
    operator: Optional[str] = None       # filter: ==,!=,>,<,>=,<= ; derive: +,-,*,/
    mapping: Optional[dict[str, str]] = None  # recode old->new
    old: Optional[str] = None            # rename
    new: Optional[str] = None            # rename / derive new column name
    left: Optional[str] = None           # derive
    right: Optional[str] = None          # derive
    right_is_col: Optional[bool] = None  # derive: is `right` a column or a number


class RepairRequest(BaseModel):
    original_code: str
    error_summary: str
    hint: Optional[str] = None
    temperature: float = 0.1
