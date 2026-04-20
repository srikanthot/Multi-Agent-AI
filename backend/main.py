"""FastAPI application entry point for the PSEG Tech Manual Chatbot.
 
Production-hardened with:
  - Startup config validation (fail fast on missing env vars)
  - Request ID middleware (X-Request-ID header, propagated to all logs)
  - Request body size limit middleware
  - Per-IP rate limiting (via slowapi)
  - Structured JSON logging (for Azure Monitor / Log Analytics)
  - Async health check with response caching
  - CORS with production-safe wildcard handling
"""
 
import asyncio
import contextvars
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
 
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
 
from app.api.routes import router
from app.config.settings import (
    ALLOWED_ORIGINS,
    CORS_ALLOW_CREDENTIALS,
    MAX_REQUEST_BODY_BYTES,
    RATE_LIMIT_CHAT,
    RATE_LIMIT_DEFAULT,
    RATE_LIMIT_ENABLED,
    validate_settings,
)
 
# ---------------------------------------------------------------------------
# Structured logging — JSON format for production, human-readable for dev
# ---------------------------------------------------------------------------
 
# Context variable for request ID — available across async/thread boundaries.
current_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
 
 
class _JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON for Azure Monitor ingestion."""
 
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include request_id from contextvar or record attribute
        request_id = current_request_id.get("") or getattr(record, "request_id", None)
        if request_id:
            log_entry["request_id"] = request_id
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)
 
 
_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler])
 
# Suppress verbose Azure SDK HTTP-level logging
logging.getLogger("azure.cosmos").setLevel(logging.WARNING)
logging.getLogger("azure.core").setLevel(logging.WARNING)
 
logger = logging.getLogger(__name__)
 
 
# ---------------------------------------------------------------------------
# Rate limiting (slowapi)
# ---------------------------------------------------------------------------
 
def _get_client_ip(request: Request) -> str:
    """Extract client IP from X-Forwarded-For (Azure App Service) or direct."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
 
 
_limiter = None
 
if RATE_LIMIT_ENABLED:
    try:
        from slowapi import Limiter
        from slowapi.errors import RateLimitExceeded
 
        _limiter = Limiter(key_func=_get_client_ip)
 
        def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please slow down."},
            )
 
    except ImportError:
        logger.warning("slowapi not installed — rate limiting disabled")
 
 
# ---------------------------------------------------------------------------
# Middleware: Request ID
# ---------------------------------------------------------------------------
 
class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request for log correlation."""
 
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:12]
        request.state.request_id = request_id
        # Set contextvar so all downstream logging includes request_id
        token = current_request_id.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            current_request_id.reset(token)
 
 
# ---------------------------------------------------------------------------
# Middleware: Body size limit
# ---------------------------------------------------------------------------
 
class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with bodies exceeding MAX_REQUEST_BODY_BYTES.
 
    Checks Content-Length header first (fast path), then falls back to
    reading the body for requests without Content-Length to prevent
    memory exhaustion from oversized payloads.
    """
 
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_BODY_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": f"Request body too large (max {MAX_REQUEST_BODY_BYTES} bytes)"},
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                )
        elif request.method in ("POST", "PUT", "PATCH"):
            # No Content-Length — read body to verify actual size
            body = await request.body()
            if len(body) > MAX_REQUEST_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Request body too large (max {MAX_REQUEST_BODY_BYTES} bytes)"},
                )
        return await call_next(request)
 
 
# ---------------------------------------------------------------------------
# Middleware: Global request timeout
# ---------------------------------------------------------------------------
 
# Streaming endpoints get a longer timeout; others use a shorter one.
_REQUEST_TIMEOUT_SECONDS = 300  # 5 minutes for streaming
_NON_STREAM_TIMEOUT_SECONDS = 120  # 2 minutes for non-streaming
 
 
class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Cancel requests that exceed the maximum allowed duration."""
 
    async def dispatch(self, request: Request, call_next):
        is_stream = request.url.path.endswith("/stream")
        timeout = _REQUEST_TIMEOUT_SECONDS if is_stream else _NON_STREAM_TIMEOUT_SECONDS
        try:
            async with asyncio.timeout(timeout):
                return await call_next(request)
        except TimeoutError:
            logger.error(
                "Request timed out after %ds | method=%s path=%s",
                timeout, request.method, request.url.path,
            )
            return JSONResponse(
                status_code=504,
                content={"detail": "Request timed out. Please try again."},
            )
 
 
# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
 
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and tear down shared resources."""
    from app.storage.cosmos_client import close_cosmos, init_cosmos
 
    # Validate configuration — exit(1) if critical vars missing
    validate_settings()
 
    # Widen the default thread pool for synchronous Azure SDK calls.
    loop = asyncio.get_running_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=100))
 
    logger.info("Starting up — initializing Cosmos DB storage...")
    await init_cosmos()
    logger.info("Startup complete.")
    yield
    logger.info("Shutting down — closing Cosmos DB client...")
    await close_cosmos()
    logger.info("Shutdown complete.")
 
 
# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
 
app = FastAPI(
    title="PSEG Tech Manual Chatbot",
    description=(
        "Agent-pattern RAG chatbot for GCC High. "
        "Hybrid Azure AI Search + Azure OpenAI, streamed SSE with structured citations. "
        "Persistent chat history via Azure Cosmos DB."
    ),
    version="4.1.0",
    lifespan=lifespan,
    docs_url=None,      # disable Swagger UI in production
    redoc_url=None,      # disable ReDoc in production
    openapi_url=None,    # disable OpenAPI schema in production
)
 
# Register middleware (order matters — outermost first)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(RequestTimeoutMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
 
# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
# Rate limiter
if _limiter is not None:
    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
 
app.include_router(router)
 
 
# ---------------------------------------------------------------------------
# Health check — async, cached, no API keys in response
# ---------------------------------------------------------------------------
 
_health_cache: dict = {}
_health_cache_expiry: float = 0.0
_HEALTH_CACHE_TTL = 30  # seconds
 
 
@app.get("/health")
async def health() -> dict:
    """Health-check endpoint — probes Cosmos, Search, and OpenAI.
 
    Results are cached for 30 seconds to avoid hammering Azure services
    on every load balancer probe.
    """
    global _health_cache, _health_cache_expiry
 
    now = time.monotonic()
    if _health_cache and now < _health_cache_expiry:
        return _health_cache
 
    from app.config.settings import (
        AZURE_OPENAI_API_KEY,
        AZURE_OPENAI_API_VERSION,
        AZURE_OPENAI_CHAT_DEPLOYMENT,
        AZURE_OPENAI_ENDPOINT,
        AZURE_SEARCH_API_KEY,
        AZURE_SEARCH_ENDPOINT,
        AZURE_SEARCH_INDEX,
    )
    from app.storage.cosmos_client import is_storage_enabled
 
    status: dict[str, str] = {
        "storage": "cosmos" if is_storage_enabled() else "in-memory",
    }
 
    # Probe Azure AI Search — async, lightweight
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"{AZURE_SEARCH_ENDPOINT}/indexes/{AZURE_SEARCH_INDEX}/stats"
                f"?api-version=2024-05-01-preview",
                headers={"api-key": AZURE_SEARCH_API_KEY},
            )
        status["search"] = "ok" if r.status_code == 200 else "unavailable"
    except Exception:
        status["search"] = "unavailable"
 
    # Probe Azure OpenAI — async, minimal token usage
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{AZURE_OPENAI_ENDPOINT}openai/deployments/{AZURE_OPENAI_CHAT_DEPLOYMENT}"
                f"/chat/completions?api-version={AZURE_OPENAI_API_VERSION}",
                headers={"api-key": AZURE_OPENAI_API_KEY},
                json={"messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
            )
        status["openai"] = "ok" if r.status_code == 200 else "unavailable"
    except Exception:
        status["openai"] = "unavailable"
 
    _healthy_values = {"ok", "cosmos", "in-memory"}
    overall = "ok" if all(v in _healthy_values for v in status.values()) else "degraded"
    result = {"status": overall, **status}
 
    _health_cache = result
    _health_cache_expiry = now + _HEALTH_CACHE_TTL
 
    return result
 
 