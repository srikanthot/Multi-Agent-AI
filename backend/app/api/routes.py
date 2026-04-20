"""FastAPI routes — thin routes delegating to AgentRuntime and chat_store.
 
Chat endpoints (backward-compatible):
  POST /chat/stream    — SSE streaming answer with citations
  POST /chat           — non-streaming JSON answer with citations
 
Conversation management endpoints:
  GET    /conversations                        — list user's threads
  POST   /conversations                        — create new thread
  GET    /conversations/{thread_id}/messages   — ordered message history
  DELETE /conversations/{thread_id}            — soft delete
  PATCH  /conversations/{thread_id}            — rename title
 
Authentication:
  - In production (DEBUG_MODE=false), unauthenticated requests → 401.
  - In local dev  (DEBUG_MODE=true), X-Debug-User-Id provides identity.
 
Multi-user isolation:
  When the client supplies a session_id in a chat request, the route
  validates that the conversation exists for the resolved user BEFORE
  dispatching to AgentRuntime.  If the thread_id is not owned by this user,
  the route returns HTTP 404 immediately.
"""
 
from __future__ import annotations
 
import logging
import re
import uuid
 
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
 
from app.agent_runtime.agent import AgentRuntime
from app.agent_runtime.session import AgentSession
from app.api.schemas import (
    ChatRequest,
    ConversationResponse,
    CreateConversationRequest,
    FeedbackRequest,
    MessageResponse,
    UpdateConversationRequest,
)
from app.auth.identity import UserIdentity, resolve_identity
from app.config.settings import (
    DEBUG_MODE,
    RATE_LIMIT_CHAT,
    RATE_LIMIT_DEFAULT,
    RATE_LIMIT_ENABLED,
)
from app.storage import chat_store
from app.storage.cosmos_client import is_storage_enabled
 
logger = logging.getLogger(__name__)
router = APIRouter()
 
_runtime = AgentRuntime()
 
# UUID format validation for path params
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
 
 
# ---------------------------------------------------------------------------
# Dependency — identity resolver with auth enforcement
# ---------------------------------------------------------------------------
 
async def get_identity(request: Request) -> UserIdentity:
    """FastAPI dependency: resolve user identity from request headers.
 
    In production (DEBUG_MODE=false), rejects unauthenticated requests with 401.
    In local dev (DEBUG_MODE=true), allows debug headers.
    """
    identity = resolve_identity(request)
 
    # In production, require authentication
    if not DEBUG_MODE and not identity.is_authenticated:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
 
    return identity
 
 
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
 
def _validate_thread_id(thread_id: str) -> None:
    """Validate thread_id is a proper UUID format."""
    if not _UUID_RE.match(thread_id):
        raise HTTPException(status_code=400, detail="Invalid thread_id format")
 
 
def _conv_to_response(conv) -> ConversationResponse:
    return ConversationResponse(
        thread_id=conv.thread_id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        last_message_at=conv.last_message_at,
        last_user_message_preview=conv.last_user_message_preview,
        last_assistant_message_preview=conv.last_assistant_message_preview,
        message_count=conv.message_count,
        is_deleted=conv.is_deleted,
    )
 
 
def _msg_to_response(msg) -> MessageResponse:
    return MessageResponse(
        id=msg.id,
        thread_id=msg.thread_id,
        role=msg.role,
        meta=msg.meta,
        content=msg.content,
        citations=msg.citations,
        created_at=msg.created_at,
        sequence=msg.sequence,
        status=msg.status,
    )
 
 
def _make_session(body: ChatRequest) -> AgentSession:
    """Create an AgentSession from the request body, honouring session_id alias."""
    session = AgentSession(question=body.question)
    if body.session_id:
        session.session_id = body.session_id
        session.client_provided = True
    return session
 
 
async def _assert_conversation_ownership(thread_id: str, user_id: str) -> None:
    """Raise HTTP 404 if the thread does not exist or is not owned by user_id."""
    if not is_storage_enabled():
        return
    conv = await chat_store.get_conversation(thread_id, user_id)
    if conv is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or access denied.",
        )
 
 
# ---------------------------------------------------------------------------
# Chat endpoints
# ---------------------------------------------------------------------------
 
@router.post("/chat/stream")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    identity: UserIdentity = Depends(get_identity),
) -> StreamingResponse:
    """Stream a grounded answer with citations via Server-Sent Events."""
    # Rate limiting (applied manually since slowapi decorators need Request)
    _apply_rate_limit(request, "chat")
 
    logger.info(
        "POST /chat/stream | user=%s auth=%s session=%s | question=%s",
        identity.user_id, identity.auth_source, body.session_id, body.question,
    )
 
    if body.session_id:
        await _assert_conversation_ownership(body.session_id, identity.user_id)
 
    session = _make_session(body)
    return StreamingResponse(
        _runtime.run_stream(body.question, session, identity),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
 
 
@router.post("/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    identity: UserIdentity = Depends(get_identity),
) -> dict:
    """Return a grounded answer and citations as normal JSON."""
    _apply_rate_limit(request, "chat")
 
    logger.info(
        "POST /chat | user=%s auth=%s session=%s | question=%s",
        identity.user_id, identity.auth_source, body.session_id, body.question,
    )
 
    if body.session_id:
        await _assert_conversation_ownership(body.session_id, identity.user_id)
 
    session = _make_session(body)
    result = await _runtime.run_once(body.question, session, identity)
    return result
 
 
# ---------------------------------------------------------------------------
# Conversation management endpoints
# ---------------------------------------------------------------------------
 
@router.get("/conversations")
async def list_conversations(
    identity: UserIdentity = Depends(get_identity),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[ConversationResponse]:
    """Return recent conversations for the resolved user, newest first."""
    if not is_storage_enabled():
        return []
    convs = await chat_store.list_conversations(identity.user_id, limit=limit, offset=offset)
    return [_conv_to_response(c) for c in convs]
 
 
@router.post("/conversations")
async def create_conversation(
    body: CreateConversationRequest,
    identity: UserIdentity = Depends(get_identity),
) -> ConversationResponse:
    """Create a new empty conversation thread and return its thread_id."""
    thread_id = str(uuid.uuid4())
    title = body.title or "New Chat"
 
    if is_storage_enabled():
        conv = await chat_store.create_conversation(
            thread_id=thread_id,
            user_id=identity.user_id,
            user_name=identity.user_name,
            title=title,
        )
        if conv is None:
            raise HTTPException(status_code=503, detail="Storage unavailable")
        return _conv_to_response(conv)
 
    # Storage disabled — return a minimal ephemeral representation
    from app.storage.models import ConversationRecord
    conv = ConversationRecord(
        id=thread_id,
        thread_id=thread_id,
        user_id=identity.user_id,
        user_name=identity.user_name,
        title=title,
    )
    return _conv_to_response(conv)
 
 
@router.get("/conversations/{thread_id}/messages")
async def get_conversation_messages(
    thread_id: str,
    identity: UserIdentity = Depends(get_identity),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[MessageResponse]:
    """Return ordered message history for a thread."""
    _validate_thread_id(thread_id)
 
    if not is_storage_enabled():
        return []
 
    messages = await chat_store.get_messages_for_user(
        thread_id, identity.user_id, max_turns=limit
    )
 
    if not messages:
        conv = await chat_store.get_conversation(thread_id, identity.user_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
 
    return [_msg_to_response(m) for m in messages]
 
 
@router.delete("/conversations/{thread_id}")
async def delete_conversation(
    thread_id: str,
    identity: UserIdentity = Depends(get_identity),
) -> dict:
    """Soft-delete a conversation (marks is_deleted=true, does not remove data)."""
    _validate_thread_id(thread_id)
 
    if not is_storage_enabled():
        return {"deleted": False, "reason": "storage_disabled"}
 
    success = await chat_store.soft_delete_conversation(thread_id, identity.user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
 
    return {"deleted": True, "thread_id": thread_id}
 
 
@router.patch("/conversations/{thread_id}")
async def update_conversation(
    thread_id: str,
    body: UpdateConversationRequest,
    identity: UserIdentity = Depends(get_identity),
) -> ConversationResponse:
    """Rename a conversation thread."""
    _validate_thread_id(thread_id)
 
    if not is_storage_enabled():
        raise HTTPException(status_code=503, detail="Storage unavailable")
 
    success = await chat_store.update_conversation_title(
        thread_id, identity.user_id, body.title
    )
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
 
    conv = await chat_store.get_conversation(thread_id, identity.user_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
 
    return _conv_to_response(conv)
 
 
# ---------------------------------------------------------------------------
# Feedback endpoint
# ---------------------------------------------------------------------------
 
@router.post("/feedback")
async def submit_feedback(
    body: FeedbackRequest,
    identity: UserIdentity = Depends(get_identity),
) -> dict:
    """Store thumbs-up / thumbs-down feedback for a specific assistant message."""
    from app.storage.cosmos_client import get_feedback_container
    from app.storage.models import FeedbackRecord
 
    container = get_feedback_container()
    if container is None:
        raise HTTPException(status_code=503, detail="Storage unavailable")
 
    # Validate that the thread belongs to the authenticated user
    if body.thread_id and is_storage_enabled():
        conv = await chat_store.get_conversation(body.thread_id, identity.user_id)
        if conv is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found or access denied.",
            )
 
    record = FeedbackRecord(
        thread_id=body.thread_id,
        message_id=body.message_id,
        user_id=identity.user_id,
        rating=body.rating,
        comment=body.comment,
    )
    try:
        await container.upsert_item(body=record.model_dump(mode="json"))
        logger.info(
            "feedback: saved | user=%s thread=%s msg=%s rating=%s",
            identity.user_id, body.thread_id, body.message_id, body.rating,
        )
        return {"status": "ok"}
    except Exception:
        logger.exception("feedback: failed to save")
        raise HTTPException(status_code=500, detail="Failed to save feedback")
 
 
# ---------------------------------------------------------------------------
# On-demand SAS URL signing — keeps PDF links working in old history
# ---------------------------------------------------------------------------
 
@router.get("/sas")
async def get_signed_url(
    request: Request,
    url: str = Query(..., description="Raw or expired Azure Blob URL to sign"),
    identity: UserIdentity = Depends(get_identity),
) -> dict:
    """Generate a fresh short-lived SAS URL for a PDF citation.
 
    The frontend calls this when the user clicks "Open PDF" — even for old
    conversations whose original SAS tokens have expired.  Strips any
    existing (expired) SAS query params before re-signing.
    """
    from app.tools.sas_helper import sign_url, is_sas_enabled, _parse_blob_url
    from urllib.parse import urlparse, urlunparse
 
    _apply_rate_limit(request, "default")
 
    if not is_sas_enabled():
        # SAS not configured — return the original URL and let the
        # frontend try opening it directly (works if blob is public).
        return {"signed_url": url}
 
    if not url or not _parse_blob_url(url):
        raise HTTPException(status_code=400, detail="Invalid blob storage URL")
 
    # Strip any existing (expired) SAS query params before re-signing
    parsed = urlparse(url)
    clean_url = urlunparse(parsed._replace(query="", fragment=""))
 
    signed = sign_url(clean_url)
    return {"signed_url": signed}
 
 
# ---------------------------------------------------------------------------
# Rate limiting helper
# ---------------------------------------------------------------------------
 
def _apply_rate_limit(request: Request, endpoint_type: str = "default") -> None:
    """Apply rate limiting if slowapi is available and enabled."""
    if not RATE_LIMIT_ENABLED:
        return
 
    limiter = getattr(request.app.state, "limiter", None)
    if limiter is None:
        return
 
    limit_string = RATE_LIMIT_CHAT if endpoint_type == "chat" else RATE_LIMIT_DEFAULT
    try:
        limiter._check_request_limit(request, None, [limit_string], False)
    except Exception as exc:
        exc_name = type(exc).__name__
        # RateLimitExceeded is expected — re-raise it so caller gets 429
        if "RateLimit" in exc_name:
            raise
        # In production, fail closed to prevent abuse if limiter is broken.
        # In debug mode, allow through with a warning.
        if DEBUG_MODE:
            logger.warning("Rate limiter internal error (%s) — request allowed through (debug): %s", exc_name, exc)
        else:
            logger.error("Rate limiter internal error (%s) — rejecting request (fail-closed): %s", exc_name, exc)
            raise HTTPException(status_code=503, detail="Service temporarily unavailable")
 
 