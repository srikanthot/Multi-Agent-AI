"""Query rewriter — reformulates follow-up questions into standalone search queries.
 
When a user asks "explain more about this" or "what about the technical requirements",
the retrieval system has no context from the prior conversation. This module uses a
fast LLM call to rewrite such follow-up questions into self-contained search queries
that include the necessary context (e.g., equipment type, kV rating, topic).
 
The rewrite only fires when there is conversation history AND the question looks like
a follow-up (short, contains pronouns/demonstratives, lacks technical specificity).
"""
 
import logging
import re
 
from openai import AzureOpenAI
 
from app.config.settings import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_CHAT_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
    LLM_TIMEOUT_SECONDS,
    TRACE_MODE,
)
 
logger = logging.getLogger(__name__)
 
_REWRITE_SYSTEM = (
    "You are a query rewriter for a RAG system that searches PSEG technical manuals. "
    "Given a conversation snippet and the user's latest question, rewrite it into a "
    "single standalone natural-language search query.\n\n"
    "Rules:\n"
    "- Focus ONLY on the most recent topic in the conversation \u2014 ignore earlier "
    "unrelated topics.\n"
    "- Include the specific subject, equipment type, voltage, or procedure from the "
    "immediately preceding exchange.\n"
    "- Preserve the user's intent and any format instructions (e.g. 'step by step', "
    "'in detail', 'list all').\n"
    "- If the question is ALREADY self-contained and specific, return it unchanged.\n"
    "- Return ONLY the rewritten question \u2014 no explanation, no quotes, no prefixes."
)
 
# Module-level singleton client (shared with aoai_embeddings via same config).
_client: AzureOpenAI | None = None
 
 
def _get_client() -> AzureOpenAI:
    global _client
    if _client is None:
        _client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            max_retries=3,
        )
    return _client
 
 
def _is_already_standalone(question: str) -> bool:
    """Heuristic: is this question clearly self-contained and technical?
 
    Returns True for long, specific questions that already contain enough
    context for retrieval — skipping the rewrite LLM call to save latency.
    Short, vague, or pronoun-heavy questions return False (need rewriting).
    """
    q = question.lower().strip()
    words = q.split()
 
    # Short questions almost always benefit from context injection
    if len(words) <= 12:
        return False
 
    # Even long questions need rewriting if they reference prior context
    context_markers = [
        "this", "that", "these", "those", "it ", "its ",
        "the above", "above", "you mentioned", "you said", "you told",
        "same ", "previous", "earlier", "as you", "like you",
        "from before", "from last", "in that", "for that", "about that",
        "what you", "like that", "mentioned earlier", "just described",
        "you described", "the one you", "the last", "from the last",
    ]
    if any(marker in q for marker in context_markers):
        return False
 
    # Long question with no context references — likely standalone
    return True
 
 
def _is_valid_rewrite(original: str, rewritten: str) -> bool:
    """Sanity-check the rewritten query before using it for retrieval.
 
    Rejects the rewrite if:
    - It is too short to be meaningful (< 8 chars)
    - It is suspiciously long (> 4x the original — likely hallucinated)
    - It shares no significant words with the original + would be pure drift
 
    Returns True if the rewrite looks usable, False to fall back to original.
    """
    if not rewritten or len(rewritten) < 8:
        return False
    if len(rewritten) > max(len(original) * 4, 400):
        return False
    # Must share at least one non-trivial word with the original
    _STOPWORDS = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "what", "how", "why", "when", "where", "who", "which",
        "do", "does", "did", "can", "could", "would", "should", "will",
        "to", "of", "in", "on", "at", "for", "with", "and", "or",
        "me", "my", "i", "you", "your", "it", "its", "this", "that",
        "give", "tell", "show", "explain", "please", "about",
    }
    orig_words = {w for w in re.findall(r"[a-z0-9]+", original.lower()) if w not in _STOPWORDS and len(w) > 2}
    rew_words = {w for w in re.findall(r"[a-z0-9]+", rewritten.lower()) if w not in _STOPWORDS and len(w) > 2}
    if orig_words and not orig_words.intersection(rew_words):
        # Zero overlap with original — rewriter likely drifted completely
        return False
    return True
 
 
def rewrite_query(
    question: str,
    history: list,
    max_history_chars: int = 1500,
) -> str:
    """Rewrite a follow-up question into a standalone search query.
 
    Parameters
    ----------
    question:
        The user's current question.
    history:
        List of MessageRecord objects (chronological) from prior turns.
    max_history_chars:
        Truncate history context to this many chars to keep the rewrite fast.
 
    Returns
    -------
    str
        The rewritten standalone query, or the original question if rewriting
        is not needed or fails.
    """
    # No history → nothing to contextualize
    if not history:
        return question
 
    # Skip the LLM call only for clearly self-contained technical questions
    if _is_already_standalone(question):
        if TRACE_MODE:
            logger.info("TRACE | query_rewrite: skipped (standalone) %r", question)
        return question
 
    # Build a compact history summary for the rewrite prompt
    lines: list[str] = []
    total = 0
    for msg in reversed(history):
        role = "User" if msg.role == "user" else "Assistant"
        content = msg.content
        if len(content) > 400:
            content = content[:397] + "…"
        line = f"{role}: {content}"
        if total + len(line) > max_history_chars:
            break
        lines.insert(0, line)
        total += len(line)
 
    if not lines:
        return question
 
    history_text = "\n".join(lines)
 
    # Use a shorter timeout for the rewrite call — it's a lightweight
    # single-shot completion.  Fall back to the global LLM timeout or 15s.
    rewrite_timeout = min(LLM_TIMEOUT_SECONDS, 15) if LLM_TIMEOUT_SECONDS > 0 else 15
 
    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=AZURE_OPENAI_CHAT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": _REWRITE_SYSTEM},
                {"role": "user", "content": (
                    f"Conversation history:\n{history_text}\n\n"
                    f"Follow-up question: {question}\n\n"
                    "Rewritten standalone search query:"
                )},
            ],
            max_tokens=150,
            temperature=0.0,
            timeout=rewrite_timeout,
        )
        rewritten = resp.choices[0].message.content.strip()
 
        if _is_valid_rewrite(question, rewritten):
            if TRACE_MODE:
                logger.info(
                    "TRACE | query_rewrite: %r → %r", question, rewritten
                )
            return rewritten
        else:
            if TRACE_MODE:
                logger.info(
                    "TRACE | query_rewrite: rejected rewrite %r — using original", rewritten
                )
 
    except Exception:
        logger.error("Query rewrite failed — using original question", exc_info=True)
 
    return question
 
 
 