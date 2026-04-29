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
    "You rewrite a user's latest question into a single standalone search query "
    "for a RAG system over PSEG technical manuals.\n\n"
    "Decide first whether the question is a TOPIC SWITCH, a FOLLOW-UP, or a "
    "RETURN-TO-EARLIER, then act:\n\n"
    "TOPIC SWITCH \u2014 the question introduces a new equipment, procedure, "
    "standard, or named entity that does NOT appear in the prior turns.\n"
    "  Action: return the user's question UNCHANGED. Do NOT inject any prior "
    "context. Do NOT mention equipment from earlier turns.\n\n"
    "FOLLOW-UP \u2014 the question uses pronouns or generic nouns (it, that, the "
    "procedure, more details, what tools, the next step) that only make sense "
    "in light of the previous exchange.\n"
    "  Action: rewrite into a self-contained query that names the specific "
    "equipment, voltage, or procedure from the IMMEDIATELY PRECEDING exchange.\n\n"
    "RETURN-TO-EARLIER \u2014 the question uses 'back to', 'going back', 'remind me "
    "about', 'earlier you said', or names a topic from an earlier turn that is "
    "no longer the most recent.\n"
    "  Action: rewrite to anchor on THAT EARLIER topic specifically. The most "
    "recent exchange is NOT the right anchor here \u2014 find the older mention in "
    "the conversation and use it.\n\n"
    "Rules that apply in all cases:\n"
    "- When the conversation contains MULTIPLE distinct topics, pick the ONE "
    "topic that the new question most plausibly relates to. NEVER blend "
    "keywords from different topics into one query.\n"
    "- Preserve the user's format instructions (e.g. 'step by step', 'in detail', "
    "'list all').\n"
    "- Never invent equipment or procedures the user did not mention.\n"
    "- If you are unsure between two topics, prefer the more recent one. If you "
    "are unsure whether to rewrite at all, return the user's question unchanged.\n"
    "- Return ONLY the query \u2014 no explanation, no quotes, no prefixes."
)
 
# Module-level singleton client (shared with aoai_embeddings via same config).
_client: AzureOpenAI | None = None


# Stopwords used by _is_already_standalone to identify content-bearing words.
# Kept separate from the validator's _STOPWORDS so the two heuristics can
# evolve independently without coupling failures.
_STOPWORDS_FOR_STANDALONE = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "am", "do", "does", "did", "have", "has", "had", "having",
    "will", "would", "could", "should", "can", "may", "might", "shall",
    "to", "of", "in", "on", "at", "by", "for", "with", "from", "into",
    "up", "out", "if", "or", "and", "but", "not", "no", "so",
    "as", "me", "my", "i", "you", "your", "we", "our",
    "they", "them", "their", "he", "she", "his", "her",
    "what", "how", "why", "when", "where", "who", "which",
    "please", "tell", "give", "show", "explain", "describe", "list",
    "about", "regarding", "concerning",
    # Verbs commonly used in bare follow-ups — not topical content.
    "need", "needs", "needed", "want", "wants", "wanted",
    "require", "requires", "required",
    "use", "uses", "used", "using",
    "know", "knows", "knew",
}

# Generic-followup nouns: questions whose ONLY content word is one of these
# are bare follow-ups that need the rewriter to inject the prior topic.
# Anything outside this set (e.g. 'Vibratium', 'transformer', 'NESC') is
# a specific subject and the question is treated as standalone.
_GENERIC_FOLLOWUP_NOUNS = {
    "procedure", "procedures", "process", "processes",
    "step", "steps", "spec", "specs", "specification", "specifications",
    "detail", "details", "information", "info",
    "requirement", "requirements", "rule", "rules", "guideline", "guidelines",
    "more", "next", "last", "first", "recent", "previous",
    "tool", "tools", "thing", "things", "item", "items",
    "example", "examples", "case", "cases",
    "summary", "summaries", "overview",
    "value", "values", "number", "numbers",
    "type", "types", "kind", "kinds", "sort", "sorts",
    "way", "ways", "method", "methods",
    "part", "parts", "piece", "pieces",
    "section", "sections", "chapter", "chapters",
    "question", "questions", "answer", "answers",
    "topic", "topics", "subject", "subjects",
    "explanation", "definition",
}
 
 
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
    if not q:
        return False
    if not any(c.isalnum() for c in q):
        return False

    # Anaphora / context markers force a rewrite — the question references
    # something from prior turns that retrieval cannot resolve on its own.
    context_markers = [
        "this", "that", "these", "those", " it ", " its ",
        "the above", "above", "you mentioned", "you said", "you told",
        "same ", "previous", "earlier", "as you", "like you",
        "from before", "from last", "in that", "for that", "about that",
        "what you", "like that", "mentioned earlier", "just described",
        "you described", "the one you", "the last", "from the last",
        # 'what about X' / 'how about X' are anaphoric follow-ups even when X
        # looks specific — the user is asking about X *in the context of the
        # prior turn*. Without context-injection the search loses the anchor.
        "what about", "how about",
        # 'back to X' / 'going back to' / 'returning to' / 'coming back to'
        # signal the user is revisiting an earlier topic. Even though X may
        # name a specific entity, the rewriter is needed to anchor X to the
        # earlier exchange (otherwise retrieval may miss prior context the
        # user wants the answer extended from).
        "back to", "going back", "returning to", "coming back",
    ]
    padded = f" {q} "
    if any(marker in padded for marker in context_markers):
        return False

    # No anaphora.  Now distinguish a topic-switch question that introduces
    # a specific subject ('tell me about Vibratium', 'what is GDS') from a
    # bare follow-up that re-uses generic nouns ('specifications', 'the
    # procedure', 'more details').  A bare follow-up needs the rewriter to
    # inject the prior topic; a topic switch must NOT be rewritten because
    # the rewriter would otherwise bleed prior context into the new query
    # and break retrieval.
    # Threshold of 3 catches short acronyms ('GDS', 'kV') that the user may
    # use to introduce a topic; common 3-letter words are already filtered
    # out by _STOPWORDS_FOR_STANDALONE.
    content_words = [
        w for w in re.findall(r"[a-z0-9]+", q)
        if len(w) >= 3 and w not in _STOPWORDS_FOR_STANDALONE
        and w not in _GENERIC_FOLLOWUP_NOUNS
    ]
    if not content_words:
        # No specific subject — bare follow-up, send to rewriter.
        return False

    # At least one specific subject word — trust the user's words verbatim.
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
    max_history_chars: int = 2500,
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
 
 
 