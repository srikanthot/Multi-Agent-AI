"""SAS token helper — signs Azure Blob Storage URLs for secure PDF access.
 
Generates short-lived Shared Access Signature (SAS) tokens so the frontend
can load PDFs directly from Azure Blob Storage without public access enabled.
 
The storage account key stays on the backend; the frontend only receives
a time-limited signed URL that auto-expires.
"""
 
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
 
from app.config.settings import (
    AZURE_STORAGE_ACCOUNT_NAME,
    AZURE_STORAGE_ACCOUNT_KEY,
    SAS_TOKEN_EXPIRY_MINUTES,
)
 
logger = logging.getLogger(__name__)
 
_sas_available = False
 
try:
    from azure.storage.blob import generate_blob_sas, BlobSasPermissions
 
    _sas_available = True
except ImportError:
    logger.warning(
        "azure-storage-blob not installed — SAS token generation disabled. "
        "Run: pip install azure-storage-blob"
    )
 
 
def is_sas_enabled() -> bool:
    """Return True if SAS token generation is properly configured."""
    return (
        _sas_available
        and bool(AZURE_STORAGE_ACCOUNT_NAME)
        and bool(AZURE_STORAGE_ACCOUNT_KEY)
    )
 
 
def _parse_blob_url(url: str) -> tuple[str, str] | None:
    """Extract (container_name, blob_path) from an Azure Blob Storage URL.
 
    Supports formats:
      https://<account>.blob.core.windows.net/<container>/<blob>
      https://<account>.blob.core.usgovcloudapi.net/<container>/<blob>
    """
    try:
        parsed = urlparse(url)
        # Must be a blob storage URL for the configured account
        if not parsed.hostname or ".blob." not in parsed.hostname:
            return None
        if AZURE_STORAGE_ACCOUNT_NAME and not parsed.hostname.startswith(
            f"{AZURE_STORAGE_ACCOUNT_NAME}."
        ):
            logger.warning("SAS: blob URL for wrong account: %s", parsed.hostname)
            return None
        # Path: /<container>/<blob_path>
        parts = parsed.path.lstrip("/").split("/", 1)
        if len(parts) < 2:
            return None
        return parts[0], parts[1]
    except Exception:
        return None
 
 
def sign_url(url: str) -> str:
    """Append a SAS token to an Azure Blob Storage URL.
 
    If SAS is not configured or the URL is not a blob URL, returns the
    original URL unchanged (graceful fallback).
    """
    if not url or not is_sas_enabled():
        return url
 
    # Don't re-sign URLs that already have a SAS token
    if "sig=" in url:
        return url
 
    parsed_blob = _parse_blob_url(url)
    if parsed_blob is None:
        return url
 
    container_name, blob_name = parsed_blob
 
    try:
        sas_token = generate_blob_sas(
            account_name=AZURE_STORAGE_ACCOUNT_NAME,
            account_key=AZURE_STORAGE_ACCOUNT_KEY,
            container_name=container_name,
            blob_name=blob_name,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(minutes=SAS_TOKEN_EXPIRY_MINUTES),
        )
 
        # Append SAS token to the URL
        parsed = urlparse(url)
        existing_qs = parsed.query
        new_qs = f"{existing_qs}&{sas_token}" if existing_qs else sas_token
        signed = urlunparse(parsed._replace(query=new_qs))
        return signed
 
    except Exception:
        logger.exception("Failed to generate SAS token for %s", url)
        return url
 
 
def sign_urls_in_results(results: list[dict]) -> list[dict]:
    """Sign all blob URLs in a list of retrieval result dicts (in-place)."""
    if not is_sas_enabled():
        return results
 
    for r in results:
        if r.get("url"):
            r["url"] = sign_url(r["url"])
 
    return results
 
 