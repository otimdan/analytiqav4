from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from uuid import UUID, uuid4


class Session(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: Optional[UUID] = None
    created_at: datetime
    last_active_at: datetime
    dataset_filename: Optional[str] = None
    dataset_csv: Optional[str] = None
    sandbox_id: Optional[str] = None
    profile: Optional[dict[str, Any]] = None
    hypothesis_text: Optional[str] = None
    hypothesis_columns: Optional[list[str]] = None
    pending_candidate: Optional[str] = None
    hypothesis_on_record: bool = False
    suggestion_mode: bool = False
    feedback_count: int = 0


class Message(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    created_at: datetime
    role: str
    content: str
    regime: Optional[str] = None
    classification_confidence: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class Artifact(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    message_id: Optional[UUID] = None
    created_at: datetime
    stage: str
    artifact_type: str
    content: dict[str, Any]
    code_used: Optional[str] = None
    superseded: bool = False
    superseded_by: Optional[UUID] = None
    variables_involved: Optional[list[str]] = None


class Feedback(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    message_id: UUID
    created_at: datetime
    rating: int
    comment: Optional[str] = None


class HypothesisCandidate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    created_at: datetime
    candidate_text: str
    matched_columns: Optional[list[str]] = None
    source_message_id: UUID
    status: str = "pending"


class QueryRequest(BaseModel):
    session_id: str
    message: str


class UploadResponse(BaseModel):
    session_id: str
    filename: str
    rows: int
    columns: int
    column_names: list[str]
    profile_summary: dict[str, Any]


class SessionStateResponse(BaseModel):
    session_id: str
    hypothesis_on_record: bool
    suggestion_mode: bool
    hypothesis_text: Optional[str]
    dataset_filename: Optional[str]
    profile_summary: Optional[dict[str, Any]]
    artifact_count: int
    dataset_ready: bool = False


class FeedbackRequest(BaseModel):
    session_id: str
    message_id: str
    rating: int
    comment: Optional[str] = None
