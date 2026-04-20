"""Application settings loaded from environment variables.
 
All configuration is driven by .env so the same codebase works across
dev / staging / production without code changes.
 
Startup validation (validate_settings) is called from the FastAPI lifespan
and will fail fast with clear messages if required config is missing.
"""
 
import logging
import os
import sys
 
from dotenv import load_dotenv
 
load_dotenv(override=True)
 
logger = logging.getLogger(__name__)
 
# ---------------------------------------------------------------------------
# Azure OpenAI (GCC High — openai.azure.us)
# ---------------------------------------------------------------------------
AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
AZURE_OPENAI_CHAT_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "")
# Agent Framework SDK reads AZURE_OPENAI_CHAT_DEPLOYMENT_NAME; fallback to legacy var
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME: str = os.getenv(
    "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME",
    os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", ""),
)
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", "")
 
# ---------------------------------------------------------------------------
# Azure AI Search (GCC High — search.azure.us)
# ---------------------------------------------------------------------------
AZURE_SEARCH_ENDPOINT: str = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_API_KEY: str = os.getenv("AZURE_SEARCH_API_KEY", "")
AZURE_SEARCH_INDEX: str = os.getenv("AZURE_SEARCH_INDEX", "rag-psegtechm-index-finalv2")
 
# ---------------------------------------------------------------------------
# Index field mappings — must match the actual index schema exactly.
# ---------------------------------------------------------------------------
SEARCH_CONTENT_FIELD: str = os.getenv("SEARCH_CONTENT_FIELD", "chunk")
SEARCH_SEMANTIC_CONTENT_FIELD: str = os.getenv("SEARCH_SEMANTIC_CONTENT_FIELD", "chunk_for_semantic")
SEARCH_VECTOR_FIELD: str = os.getenv("SEARCH_VECTOR_FIELD", "text_vector")
SEARCH_FILENAME_FIELD: str = os.getenv("SEARCH_FILENAME_FIELD", "source_file")
SEARCH_URL_FIELD: str = os.getenv("SEARCH_URL_FIELD", "source_url")
SEARCH_CHUNK_ID_FIELD: str = os.getenv("SEARCH_CHUNK_ID_FIELD", "chunk_id")
SEARCH_TITLE_FIELD: str = os.getenv("SEARCH_TITLE_FIELD", "title")
SEARCH_SECTION1_FIELD: str = os.getenv("SEARCH_SECTION1_FIELD", "header_1")
SEARCH_SECTION2_FIELD: str = os.getenv("SEARCH_SECTION2_FIELD", "header_2")
SEARCH_SECTION3_FIELD: str = os.getenv("SEARCH_SECTION3_FIELD", "header_3")
# Leave blank if the index has no page number field (new layout-based index has none)
SEARCH_PAGE_FIELD: str = os.getenv("SEARCH_PAGE_FIELD", "")
 
# ---------------------------------------------------------------------------
# Multimodal index — record type filtering
# ---------------------------------------------------------------------------
# OData filter applied to every search query. Use to exclude summary / decorative
# records or restrict to specific processing statuses.
# Default: allow text, diagram, and table records that were processed successfully.
SEARCH_FILTER: str = os.getenv(
    "SEARCH_FILTER",
    "(processing_status eq 'ok' or processing_status eq 'cache_hit') and record_type ne 'summary'",
)
 
# ---------------------------------------------------------------------------
# Retrieval tuning
# ---------------------------------------------------------------------------
TOP_K: int = int(os.getenv("TOP_K", "7"))
# How many candidates to fetch before diversity/gap filters trim to TOP_K.
RETRIEVAL_CANDIDATES: int = int(os.getenv("RETRIEVAL_CANDIDATES", "25"))
VECTOR_K: int = int(os.getenv("VECTOR_K", "50"))
 
# ---------------------------------------------------------------------------
# Retrieval quality
# ---------------------------------------------------------------------------
USE_SEMANTIC_RERANKER: bool = os.getenv("USE_SEMANTIC_RERANKER", "true").lower() == "true"
SEMANTIC_CONFIG_NAME: str = os.getenv("SEMANTIC_CONFIG_NAME", "manual-semantic-config")
QUERY_LANGUAGE: str = os.getenv("QUERY_LANGUAGE", "en-us")
MIN_RESULTS: int = int(os.getenv("MIN_RESULTS", "2"))
# Gate threshold for base RRF/hybrid scores (range 0.01–0.033 for Azure hybrid)
MIN_AVG_SCORE: float = float(os.getenv("MIN_AVG_SCORE", "0.02"))
# Gate threshold for semantic reranker scores (range 0.0–4.0); used when reranker active
# 1.8 = "relevant" — raised from 1.5 to reduce marginal chunks reaching the LLM
MIN_RERANKER_SCORE: float = float(os.getenv("MIN_RERANKER_SCORE", "1.8"))
DIVERSITY_BY_SOURCE: bool = os.getenv("DIVERSITY_BY_SOURCE", "true").lower() == "true"
MAX_CHUNKS_PER_SOURCE: int = int(os.getenv("MAX_CHUNKS_PER_SOURCE", "3"))
# When one source's top score >= DOMINANT_SOURCE_SCORE_RATIO × next source's top score,
# that source is "dominant" and may contribute up to MAX_CHUNKS_DOMINANT_SOURCE chunks.
DOMINANT_SOURCE_SCORE_RATIO: float = float(os.getenv("DOMINANT_SOURCE_SCORE_RATIO", "1.5"))
MAX_CHUNKS_DOMINANT_SOURCE: int = int(os.getenv("MAX_CHUNKS_DOMINANT_SOURCE", "4"))
# After diversity filtering, discard chunks whose effective score < SCORE_GAP_MIN_RATIO × top.
# 0.75 = keep only results within 25% of top score — tightened from 0.70 to reduce noise
SCORE_GAP_MIN_RATIO: float = float(os.getenv("SCORE_GAP_MIN_RATIO", "0.75"))
TRACE_MODE: bool = os.getenv("TRACE_MODE", "false").lower() == "true"
 
# Maximum seconds to wait for the LLM to finish generating a response.
# Prevents hung workers when Azure OpenAI is unresponsive.  0 = no timeout.
LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
 
# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# ALLOWED_ORIGINS: "*" for local dev (no credentials), or a comma-separated
# list of explicit origins for browser-credentialed requests from a deployed
# frontend (e.g. http://localhost:8501,https://myapp.azurewebsites.net).
#
# Production rule: the CORS spec forbids combining allow_credentials=True
# with a wildcard origin.  We enforce this automatically:
#   - ALLOWED_ORIGINS=*           → allow_credentials=False  (open, no creds)
#   - ALLOWED_ORIGINS=<explicit>  → allow_credentials=True   (credentialed OK)
# ---------------------------------------------------------------------------
_allowed_origins_raw: str = os.getenv("ALLOWED_ORIGINS", "*")
if _allowed_origins_raw.strip() == "*":
    ALLOWED_ORIGINS: list[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = False
else:
    ALLOWED_ORIGINS = [o.strip() for o in _allowed_origins_raw.split(",") if o.strip()]
    CORS_ALLOW_CREDENTIALS = True
 
# ---------------------------------------------------------------------------
# Azure Cosmos DB — persistent chat history
# ---------------------------------------------------------------------------
# Auth mode: "key" (local/dev) or "managed_identity" (production)
COSMOS_AUTH_MODE: str = os.getenv("COSMOS_AUTH_MODE", "key")
COSMOS_ENDPOINT: str = os.getenv("COSMOS_ENDPOINT", "")
COSMOS_KEY: str = os.getenv("COSMOS_KEY", "")
COSMOS_DATABASE: str = os.getenv("COSMOS_DATABASE", "pseg-chatbot")
COSMOS_CONVERSATIONS_CONTAINER: str = os.getenv("COSMOS_CONVERSATIONS_CONTAINER", "conversations")
COSMOS_MESSAGES_CONTAINER: str = os.getenv("COSMOS_MESSAGES_CONTAINER", "messages")
COSMOS_FEEDBACK_CONTAINER: str = os.getenv("COSMOS_FEEDBACK_CONTAINER", "feedback")
# Auto-create database and containers on startup if they don't exist
COSMOS_AUTO_CREATE_CONTAINERS: bool = os.getenv("COSMOS_AUTO_CREATE_CONTAINERS", "true").lower() == "true"
# Max prior turns (messages) to load per thread for LLM context
COSMOS_HISTORY_MAX_TURNS: int = int(os.getenv("COSMOS_HISTORY_MAX_TURNS", "12"))
# TTL — set COSMOS_ENABLE_TTL=true to auto-expire documents
COSMOS_ENABLE_TTL: bool = os.getenv("COSMOS_ENABLE_TTL", "false").lower() == "true"
COSMOS_TTL_SECONDS: int = int(os.getenv("COSMOS_TTL_SECONDS", "7776000"))  # 90 days
 
# ---------------------------------------------------------------------------
# Azure Blob Storage — SAS token generation for PDF citation URLs
# ---------------------------------------------------------------------------
# Required to generate short-lived signed URLs so the frontend can open PDFs.
# The storage account key never leaves the backend.
AZURE_STORAGE_ACCOUNT_NAME: str = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "")
AZURE_STORAGE_ACCOUNT_KEY: str = os.getenv("AZURE_STORAGE_ACCOUNT_KEY", "")
# How long (minutes) a generated SAS token remains valid. Default: 60 min.
SAS_TOKEN_EXPIRY_MINUTES: int = int(os.getenv("SAS_TOKEN_EXPIRY_MINUTES", "60"))
 
# ---------------------------------------------------------------------------
# Identity — authentication and user resolution
# ---------------------------------------------------------------------------
# Set DEBUG_MODE=true ONLY for local development. In production this MUST be
# false. When true, the X-Debug-User-Id header is honoured for per-user
# isolation without real auth.
DEFAULT_LOCAL_USER_ID: str = os.getenv("DEFAULT_LOCAL_USER_ID", "local-user")
DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"
 
# ---------------------------------------------------------------------------
# JWT / Entra ID token validation
# ---------------------------------------------------------------------------
# Set these to enable server-side JWT validation of Bearer tokens from MSAL.
# When both are blank, the backend relies on Easy Auth headers or DEBUG_MODE.
#
# ENTRA_TENANT_ID: Your Azure AD tenant ID (GUID)
# JWT_AUDIENCE:    Backend App Registration client ID (the "aud" claim in tokens)
# ENTRA_CLOUD:     "gcc_high" (login.microsoftonline.us) or "public" (login.microsoftonline.com)
ENTRA_TENANT_ID: str = os.getenv("ENTRA_TENANT_ID", "")
JWT_AUDIENCE: str = os.getenv("JWT_AUDIENCE", "")
ENTRA_CLOUD: str = os.getenv("ENTRA_CLOUD", "gcc_high")
 
# Derived Entra endpoints
if ENTRA_CLOUD == "gcc_high":
    _ENTRA_LOGIN_BASE = "https://login.microsoftonline.us"
else:
    _ENTRA_LOGIN_BASE = "https://login.microsoftonline.com"
 
ENTRA_ISSUER: str = f"{_ENTRA_LOGIN_BASE}/{ENTRA_TENANT_ID}/v2.0" if ENTRA_TENANT_ID else ""
ENTRA_JWKS_URI: str = (
    f"{_ENTRA_LOGIN_BASE}/{ENTRA_TENANT_ID}/discovery/v2.0/keys"
    if ENTRA_TENANT_ID else ""
)
 
# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
RATE_LIMIT_CHAT: str = os.getenv("RATE_LIMIT_CHAT", "10/minute")
RATE_LIMIT_DEFAULT: str = os.getenv("RATE_LIMIT_DEFAULT", "60/minute")
RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
 
# ---------------------------------------------------------------------------
# Request body size limit (bytes). Default 64 KB — generous for chat requests.
# ---------------------------------------------------------------------------
MAX_REQUEST_BODY_BYTES: int = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(64 * 1024)))
 
 
# ---------------------------------------------------------------------------
# Startup validation — called once from FastAPI lifespan
# ---------------------------------------------------------------------------
 
def validate_settings() -> None:
    """Validate critical settings at startup. Logs warnings for non-fatal
    issues and exits for fatal misconfigurations."""
 
    errors: list[str] = []
    warnings: list[str] = []
 
    # Required for core functionality
    if not AZURE_OPENAI_ENDPOINT:
        errors.append("AZURE_OPENAI_ENDPOINT is not set — LLM calls will fail")
    if not AZURE_OPENAI_API_KEY:
        errors.append("AZURE_OPENAI_API_KEY is not set — LLM calls will fail")
    if not AZURE_OPENAI_CHAT_DEPLOYMENT:
        errors.append("AZURE_OPENAI_CHAT_DEPLOYMENT is not set — LLM calls will fail")
    if not AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT:
        errors.append("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT is not set — embedding calls will fail")
    if not AZURE_SEARCH_ENDPOINT:
        errors.append("AZURE_SEARCH_ENDPOINT is not set — search will fail")
    if not AZURE_SEARCH_API_KEY:
        errors.append("AZURE_SEARCH_API_KEY is not set — search will fail")
 
    # Security warnings
    if DEBUG_MODE:
        warnings.append(
            "DEBUG_MODE=true — X-Debug-User-Id header is honoured. "
            "NEVER enable this in production!"
        )
    if ALLOWED_ORIGINS == ["*"] and not DEBUG_MODE:
        warnings.append(
            "ALLOWED_ORIGINS=* with DEBUG_MODE=false — consider setting "
            "explicit origins for production"
        )
    if TRACE_MODE:
        warnings.append(
            "TRACE_MODE=true — verbose retrieval logging is enabled. "
            "Disable in production for performance."
        )
 
    # Auth configuration status
    if ENTRA_TENANT_ID and JWT_AUDIENCE:
        logger.info(
            "JWT validation enabled — audience=%s issuer=%s",
            JWT_AUDIENCE, ENTRA_ISSUER,
        )
    elif not DEBUG_MODE:
        warnings.append(
            "ENTRA_TENANT_ID and JWT_AUDIENCE are not set and DEBUG_MODE=false. "
            "The backend will rely on Easy Auth headers (X-MS-CLIENT-PRINCIPAL-ID) "
            "for authentication. If Easy Auth is not enabled on the App Service, "
            "all requests will be treated as unauthenticated."
        )
 
    for w in warnings:
        logger.warning("CONFIG WARNING: %s", w)
 
    if errors:
        for e in errors:
            logger.error("CONFIG ERROR: %s", e)
        logger.error(
            "Startup blocked — %d configuration error(s). "
            "Fix the above and restart.", len(errors),
        )
        sys.exit(1)
