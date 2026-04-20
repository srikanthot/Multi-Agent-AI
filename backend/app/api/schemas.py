"""Pydantic request / response models for the chat and conversation APIs."""
 
from __future__ import annotations
 
import re
from datetime import datetime
from typing import Any, Optional
 
from pydantic import BaseModel, Field, field_validator
 
 
# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------
 
# UUID v4 format: 8-4-4-4-12 hex chars
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
 
 
def _validate_uuid(v: str, field_name: str) -> str:
    """Validate that a string looks like a UUID v4."""
    if not _UUID_RE.match(v):
        raise ValueError(f"{field_name} must be a valid UUID")
    return v
 
 
# ---------------------------------------------------------------------------
# Chat request / response
# ---------------------------------------------------------------------------
 
# Maximum question length (chars).  text-embedding-ada-002 has an 8 191 token
# limit (~32 KB of English text); 2 000 chars is generous for a field-tech
# question while preventing abuse.
_MAX_QUESTION_LEN = 2000
 
 
class ChatRequest(BaseModel):
    """Incoming chat request body.
 
    session_id is treated as thread_id for backward compatibility with
    the frontend.  If omitted, a new thread is created.
    """
 
    question: str = Field(..., min_length=1, max_length=_MAX_QUESTION_LEN)
    session_id: Optional[str] = None
 
    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _validate_uuid(v, "session_id")
        return v
 
 
class Citation(BaseModel):
    """A single citation reference with structured metadata."""
 
    ref_number: int = 0
    source: str
    title: str = ""
    section: str = ""
    page: str = ""
    url: str = ""
    chunk_id: str = ""
    record_type: str = "text"
    figure_ref: str = ""
    diagram_category: str = ""
    table_caption: str = ""
 
 
class CitationsPayload(BaseModel):
    """Wrapper for the SSE ``citations`` named event."""
 
    citations: list[Citation]
 
 
# ---------------------------------------------------------------------------
# Conversation management
# ---------------------------------------------------------------------------
 
class ConversationResponse(BaseModel):
    """Public representation of a conversation thread."""
 
    thread_id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    last_message_at: Optional[datetime]
    last_user_message_preview: str
    last_assistant_message_preview: str
    message_count: int
    is_deleted: bool
 
 
class CreateConversationRequest(BaseModel):
    """Body for POST /conversations."""
 
    title: Optional[str] = None      # If omitted, defaults to "New Chat"
 
 
class UpdateConversationRequest(BaseModel):
    """Body for PATCH /conversations/{thread_id}."""
 
    title: str = Field(..., min_length=1, max_length=200)
 
 
class MessageResponse(BaseModel):
    """Public representation of a single message."""
 
    id: str
    thread_id: str
    role: str
    content: str
    meta: dict[str, Any]
    citations: list[dict[str, Any]]
    created_at: datetime
    sequence: int
    status: str
 
 
# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------
 
class FeedbackRequest(BaseModel):
    """Body for POST /feedback."""
 
    thread_id: str
    message_id: str
    rating: str = Field(..., pattern="^(up|down)$")
    comment: str = Field(default="", max_length=2000)
 
    @field_validator("thread_id")
    @classmethod
    def validate_thread_id(cls, v: str) -> str:
        return _validate_uuid(v, "thread_id")
 
    @field_validator("message_id")
    @classmethod
    def validate_message_id(cls, v: str) -> str:
        return _validate_uuid(v, "message_id")
 