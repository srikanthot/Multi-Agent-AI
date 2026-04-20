"""Azure OpenAI embeddings wrapper for GCC High.
 
The Azure AI Search index has NO built-in vectorizer configured, so query
embeddings must be generated here in the API before issuing the hybrid
search. This module calls the embeddings deployment and returns a list[float]
vector ready for VectorizedQuery.
"""
 
import logging
 
from openai import AzureOpenAI
 
from app.config.settings import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
)
 
logger = logging.getLogger(__name__)
 
# Module-level singleton — reuses HTTP connection pool across calls.
_client: AzureOpenAI | None = None
 
 
def _get_client() -> AzureOpenAI:
    """Return the shared AzureOpenAI client, creating it on first use.
 
    The openai SDK >=1.0 retries transient errors (429/500/502/503/504) with
    exponential backoff automatically (max_retries=2 by default).  We raise
    the limit to 3 to absorb GCC High throttling spikes.
    """
    global _client
    if _client is None:
        _client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            max_retries=3,
        )
    return _client
 
 
def embed(text: str) -> list[float]:
    """Generate an embedding vector for the given text.
 
    Parameters
    ----------
    text:
        The query string to embed.
 
    Returns
    -------
    list[float]
        Embedding vector from the configured embeddings deployment.
        Dimensionality matches the index's vector field.
 
    Raises
    ------
    openai.OpenAIError
        Propagated to the caller (RetrievalTool handles it).
    """
    client = _get_client()
 
    response = client.embeddings.create(
        model=AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
        input=text,
    )
 
    return response.data[0].embedding
 