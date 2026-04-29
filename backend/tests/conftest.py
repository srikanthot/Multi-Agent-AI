"""Pytest config — sets minimal env vars so the app modules can import.

The unit tests target pure-logic functions that don't touch Azure, but the
parent modules read os.environ at import time. We populate dummy values so
imports succeed without the real .env file.
"""

import os

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.us")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-06-01")
os.environ.setdefault("AZURE_OPENAI_CHAT_DEPLOYMENT", "test-chat")
os.environ.setdefault("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "test-chat")
os.environ.setdefault("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", "test-embed")
os.environ.setdefault("AZURE_SEARCH_ENDPOINT", "https://test.search.azure.us")
os.environ.setdefault("AZURE_SEARCH_API_KEY", "test-key")
os.environ.setdefault("AZURE_SEARCH_INDEX", "test-index")
os.environ.setdefault("DEBUG_MODE", "true")
os.environ.setdefault("TRACE_MODE", "false")
