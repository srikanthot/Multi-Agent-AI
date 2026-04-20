"""Identity resolution — normalizes user context from HTTP request headers.
 
Resolution priority (highest to lowest):
  1. Authorization: Bearer <JWT>   — validate token, extract oid + name claims
  2. X-MS-CLIENT-PRINCIPAL-ID      — Azure App Service Easy Auth (trusted headers)
  3. X-Debug-User-Id               — local dev only (requires DEBUG_MODE=true)
  4. Reject with is_authenticated=False (production) or env default (legacy)
 
JWT validation is active when ENTRA_TENANT_ID and JWT_AUDIENCE are both set.
The token is verified against Entra's JWKS (public keys) with audience, issuer,
and expiry checks.  The user_id is set to the `oid` claim (immutable Object ID).
 
When running locally with DEBUG_MODE=true, JWT validation is skipped and the
X-Debug-User-Id header provides per-user isolation without real auth.
"""
 
from __future__ import annotations
 
import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional
 
from fastapi import Request
 
from app.config.settings import (
    DEBUG_MODE,
    DEFAULT_LOCAL_USER_ID,
    ENTRA_ISSUER,
    ENTRA_JWKS_URI,
    ENTRA_TENANT_ID,
    JWT_AUDIENCE,
)
 
logger = logging.getLogger(__name__)
 
# ---------------------------------------------------------------------------
# JWKS cache — Entra rotates keys infrequently; cache for 1 hour.
# Lock protects against race conditions in multi-threaded environments.
# ---------------------------------------------------------------------------
_jwks_cache: dict = {}
_jwks_cache_expiry: float = 0.0
_JWKS_CACHE_TTL_SECONDS = 3600
_jwks_lock = threading.Lock()
 
 
def _fetch_jwks() -> dict:
    """Fetch and cache the JWKS (JSON Web Key Set) from Entra ID."""
    global _jwks_cache, _jwks_cache_expiry
 
    with _jwks_lock:
        now = time.monotonic()
        if _jwks_cache and now < _jwks_cache_expiry:
            return _jwks_cache
 
        if not ENTRA_JWKS_URI:
            return {}
 
        try:
            import httpx
            resp = httpx.get(ENTRA_JWKS_URI, timeout=10)
            resp.raise_for_status()
            _jwks_cache = resp.json()
            _jwks_cache_expiry = now + _JWKS_CACHE_TTL_SECONDS
            logger.info("JWKS refreshed from %s (%d keys)", ENTRA_JWKS_URI, len(_jwks_cache.get("keys", [])))
            return _jwks_cache
        except Exception:
            logger.exception("Failed to fetch JWKS from %s", ENTRA_JWKS_URI)
            if _jwks_cache:
                logger.warning("Returning stale JWKS cache — key rotation may not be reflected")
                return _jwks_cache
            return {}
 
 
def _validate_jwt(token: str) -> Optional[dict]:
    """Validate a Bearer JWT token and return its decoded claims.
 
    Returns None if validation fails for any reason.
    """
    try:
        import jwt
        from jwt import PyJWKClient
    except ImportError:
        logger.error("PyJWT not installed — JWT validation unavailable")
        return None
 
    if not ENTRA_TENANT_ID or not JWT_AUDIENCE:
        return None
 
    try:
        # Use PyJWKClient to fetch and match the signing key
        jwks_data = _fetch_jwks()
        if not jwks_data:
            return None
 
        # Get the signing key from JWKS based on the token's kid header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            logger.warning("JWT missing 'kid' header")
            return None
 
        # Find the matching key
        signing_key = None
        for key_data in jwks_data.get("keys", []):
            if key_data.get("kid") == kid:
                from jwt.algorithms import RSAAlgorithm
                signing_key = RSAAlgorithm.from_jwk(key_data)
                break
 
        if signing_key is None:
            logger.warning("JWT kid=%s not found in JWKS — possibly rotated, refreshing", kid)
            # Force refresh and retry
            global _jwks_cache_expiry
            _jwks_cache_expiry = 0.0
            jwks_data = _fetch_jwks()
            for key_data in jwks_data.get("keys", []):
                if key_data.get("kid") == kid:
                    from jwt.algorithms import RSAAlgorithm
                    signing_key = RSAAlgorithm.from_jwk(key_data)
                    break
 
        if signing_key is None:
            logger.warning("JWT kid=%s not found in JWKS even after refresh", kid)
            return None
 
        # Decode and verify the token
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=JWT_AUDIENCE,
            issuer=ENTRA_ISSUER,
            options={
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
                "require": ["exp", "oid", "aud", "iss"],
            },
        )
 
        return claims
 
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        return None
    except jwt.InvalidAudienceError:
        logger.warning("JWT audience mismatch — expected %s", JWT_AUDIENCE)
        return None
    except jwt.InvalidIssuerError:
        logger.warning("JWT issuer mismatch — expected %s", ENTRA_ISSUER)
        return None
    except jwt.InvalidTokenError as exc:
        logger.warning("JWT validation failed: %s", exc)
        return None
    except Exception:
        logger.exception("Unexpected error during JWT validation")
        return None
 
 
# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
 
@dataclass
class UserIdentity:
    """Normalized identity resolved from the incoming HTTP request."""
 
    user_id: str
    user_name: str
    auth_source: str   # "jwt" | "app_service" | "debug_header" | "env_default" | "anonymous"
    is_authenticated: bool
 
 
def resolve_identity(request: Request) -> UserIdentity:
    """Return a normalized UserIdentity from request headers or env defaults.
 
    Resolution priority:
      1. Bearer JWT token (when ENTRA_TENANT_ID + JWT_AUDIENCE configured)
      2. X-MS-CLIENT-PRINCIPAL-ID (Easy Auth)
      3. X-Debug-User-Id (DEBUG_MODE only)
      4. DEFAULT_LOCAL_USER_ID / anonymous fallback
    """
 
    # 1. JWT Bearer token — most secure, self-contained identity
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and ENTRA_TENANT_ID and JWT_AUDIENCE:
        token = auth_header[7:].strip()
        if token:
            claims = _validate_jwt(token)
            if claims:
                user_id = claims.get("oid", "")
                user_name = claims.get("name", "") or claims.get("preferred_username", "") or user_id
                if user_id:
                    return UserIdentity(
                        user_id=user_id,
                        user_name=user_name,
                        auth_source="jwt",
                        is_authenticated=True,
                    )
                logger.warning("JWT valid but missing 'oid' claim")
            # Token present but invalid — do NOT fall through to debug mode.
            # In production, a bad token should be rejected, not silently downgraded.
            if not DEBUG_MODE:
                return UserIdentity(
                    user_id="__unauthenticated__",
                    user_name="",
                    auth_source="jwt_failed",
                    is_authenticated=False,
                )
 
    # 2. Azure App Service managed auth (Easy Auth)
    ms_id = request.headers.get("X-MS-CLIENT-PRINCIPAL-ID")
    ms_name = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
    if ms_id:
        return UserIdentity(
            user_id=ms_id,
            user_name=ms_name or ms_id,
            auth_source="app_service",
            is_authenticated=True,
        )
 
    # 3. Debug header — honoured ONLY when DEBUG_MODE=true
    if DEBUG_MODE:
        debug_id = (request.headers.get("X-Debug-User-Id") or "").strip()
        if debug_id:
            return UserIdentity(
                user_id=debug_id,
                user_name=debug_id,
                auth_source="debug_header",
                is_authenticated=False,
            )
        # Header missing/empty — return unidentified so they see zero history
        return UserIdentity(
            user_id="__unidentified__",
            user_name="anonymous",
            auth_source="debug_header_missing",
            is_authenticated=False,
        )
 
    # 4. Env-configured local default (legacy — no auth at all)
    if DEFAULT_LOCAL_USER_ID and DEFAULT_LOCAL_USER_ID != "anonymous":
        return UserIdentity(
            user_id=DEFAULT_LOCAL_USER_ID,
            user_name=DEFAULT_LOCAL_USER_ID,
            auth_source="env_default",
            is_authenticated=False,
        )
 
    # 5. No identity resolved — unauthenticated
    return UserIdentity(
        user_id="anonymous",
        user_name="anonymous",
        auth_source="anonymous",
        is_authenticated=False,
    )
 
 