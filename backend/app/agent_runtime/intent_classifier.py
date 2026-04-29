"""Pre-retrieval intent classifier for the PSEG Tech Manual Chatbot.
 
Classifies user input BEFORE the RAG pipeline runs.  Three outcomes:
 
  - GREETING / CHITCHAT / ACKNOWLEDGEMENT / SELF_DESCRIPTION / GIBBERISH
        → Return a canned friendly response.  No search, no LLM call.
  - VAGUE_QUERY
        → Return a polite clarification request.  No search, no LLM call.
  - TECHNICAL_QUESTION
        → Proceed to the full RAG pipeline (retrieve → gate → generate).
 
This module intentionally uses only deterministic pattern matching — no LLM
call — so it adds zero latency and zero cost.  The patterns are tuned for
a field-technician audience using a technical manual chatbot.
"""
 
import re
import logging
 
logger = logging.getLogger(__name__)
 
# ─── Intent types ──────────────────────────────────────────────────────────
INTENT_GREETING = "greeting"
INTENT_ACKNOWLEDGEMENT = "acknowledgement"
INTENT_SELF_DESCRIPTION = "self_description"
INTENT_GIBBERISH = "gibberish"
INTENT_VAGUE_QUERY = "vague_query"
INTENT_OUT_OF_SCOPE = "out_of_scope"
INTENT_INJECTION = "injection"
INTENT_CONDENSATION = "condensation"
INTENT_TECHNICAL = "technical"
 
# ─── Pattern sets ──────────────────────────────────────────────────────────
 
# Greetings — exact or near-exact matches (lowered, stripped)
_GREETINGS = {
    "hi", "hello", "hey", "hiya", "howdy", "sup", "yo",
    "good morning", "good afternoon", "good evening", "good night",
    "morning", "afternoon", "evening",
    "hi there", "hello there", "hey there",
    "greetings", "hola", "namaste",
    "how are you", "how are you doing", "how's it going",
    "what's up", "whats up", "wassup",
}
 
# True acknowledgements / thank-yous / farewells — always close the turn.
_ACKNOWLEDGEMENTS = {
    "ok", "okay", "k", "fine",
    "got it", "understood", "alright", "right", "cool", "great",
    "thanks", "thank you", "thank you so much", "thanks a lot",
    "thx", "ty", "appreciate it", "cheers",
    "bye", "goodbye", "bye bye", "see you", "take care",
    "that's all", "thats all", "nothing else", "no more questions",
    "that is all",
    "good", "nice", "perfect", "awesome", "wonderful", "excellent",
}

# Affirmatives — when the bot just asked a question (e.g. "Would you like
# the step-by-step procedure?"), these mean "yes, continue with that
# offer". When the bot did NOT ask a question, these are just polite
# acknowledgements.
_AFFIRMATIVE_CONTINUE = {
    "yes", "yep", "yeah", "yup", "yes please", "yeah please",
    "sure", "sure please", "sure thing", "yes go ahead", "go ahead",
    "please do", "please continue", "ok sure",
}

# Negatives — when the bot asked a question, these mean "no, don't continue".
# Either way, route to a polite acknowledgement.
_NEGATIVE_DECLINE = {
    "no", "nope", "no thanks", "no thank you", "nah",
}
 
# Self-description questions
_SELF_DESCRIPTION_PATTERNS = [
    r"^who are you",
    r"^what are you",
    r"^what can you do",
    r"^what do you do",
    r"^what is this",
    r"^what's this",
    r"^help$",
    r"^what is this (chat|bot|app|tool)",
    r"^how does this (work|chat|bot)",
    r"^are you (a |an )?(bot|ai|robot|chatbot|assistant)",
    r"^tell me about yourself",
    r"^introduce yourself",
]
 
# Out-of-scope patterns — clearly non-technical-manual questions
_OUT_OF_SCOPE_PATTERNS = [
    r"(?:what(?:'s| is) the )?(?:weather|forecast)\s*(?:today|tomorrow|this week|outside)?",
    r"temperature outside\s*(?:today|tomorrow|right now)?",
    r"(who is|who's) the (ceo|president|cfo|manager|director)",
    r"(write|create|generate|code|build)\s*(me )?(a |an )?(python|javascript|java|code|script|program|app|website)",
    r"(capital|population|area) of \w+",
    r"(recipe|cook|bake|ingredients)\s",
    r"(movie|film|song|music|game|sport)\s",
    r"(stock|crypto|bitcoin|market|invest)",
    r"(joke|funny|laugh|humor)",
    r"(translate|translation)\s",
    r"(news|politics|election)",
    r"(math|calculate|solve)\s.*\d",
    r"explain (quantum|relativity|evolution|philosophy|psychology)",
    # Personal / HR / non-technical
    r"(salary|payroll|vacation|holiday|pto|time.?off|sick leave|benefits|401k|pension)",
    r"(schedule|shift|roster|overtime) for (me|my|next week|today)",
    r"(email|phone|address|contact).*(manager|supervisor|boss|hr )",
    r"(order|buy|purchase|amazon|ebay|shopping)",
    r"(social media|facebook|twitter|instagram|tiktok)",
    r"(homework|essay|assignment|exam|test prep)\s",
    r"(travel|flight|hotel|booking|reservation)\s",
]
 
# Prompt injection patterns — attempts to override system instructions
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|rules?|prompts?|guidelines?)",
    r"disregard\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|rules?|prompts?)",
    r"forget\s+(all\s+)?(previous|prior|your)\s+(instructions?|rules?|prompts?)",
    r"(reveal|show|print|output|display|repeat)\s+(your\s+)?(system\s+)?(prompt|instructions?|rules?)",
    r"you\s+are\s+now\s+(a|an|in)\s+",
    r"(new|override|replace)\s+(system\s+)?(instructions?|prompt|persona|role)",
    r"act\s+as\s+(?!a\s+technician|a\s+field|an\s+engineer)",  # "act as" except legit
    r"pretend\s+(you\s+are|to\s+be)\s+",
    r"jailbreak",
    r"dan\s+mode",
    r"developer\s+mode\s*(enabled|on|activated)",
]
 
# ─── Canned responses ──────────────────────────────────────────────────────
 
GREETING_RESPONSE = (
    "Hello! I'm the PSEG Tech Manual Assistant. I can help you find information "
    "from PSEG technical manuals — including procedures, safety requirements, "
    "specifications, and troubleshooting steps.\n\n"
    "What would you like to know?"
)
 
ACKNOWLEDGEMENT_RESPONSE = (
    "You're welcome! Let me know if you have any other questions about the "
    "technical manuals."
)
 
SELF_DESCRIPTION_RESPONSE = (
    "I'm the PSEG Tech Manual Assistant. I answer questions using information "
    "from PSEG's technical manuals and procedure documents.\n\n"
    "I can help with:\n"
    "- Equipment procedures (installation, maintenance, testing)\n"
    "- Safety requirements and protocols\n"
    "- Technical specifications and ratings\n"
    "- Troubleshooting and fault procedures\n"
    "- Switching and grounding procedures\n\n"
    "Ask me a specific question and I'll find the relevant information "
    "with source citations."
)
 
GIBBERISH_RESPONSE = (
    "I didn't quite understand that. Could you ask a question about the PSEG "
    "technical manuals? For example:\n"
    "- \"What are the safety requirements for underground cable work?\"\n"
    "- \"How do I test insulation resistance?\"\n"
    "- \"What is the procedure for transformer maintenance?\""
)
 
OUT_OF_SCOPE_RESPONSE = (
    "I can only answer questions based on the PSEG technical manuals. "
    "That topic doesn't appear to be covered in the manuals I have access to.\n\n"
    "Try asking about equipment procedures, safety requirements, specifications, "
    "or troubleshooting steps."
)
 
INJECTION_RESPONSE = (
    "I can only answer questions about PSEG technical manuals. "
    "I'm not able to change my instructions or behave as a different assistant.\n\n"
    "How can I help you with the technical manuals?"
)
 
# Condensation patterns — user wants to reformat / compress the prior answer.
# Only meaningful when there is prior conversation history (has_history=True).
# The agent skips retrieval and asks the LLM to reformat from its session history.
_CONDENSATION_PATTERNS = re.compile(
    r"(?:"
    # "give me in N steps/points/lines/sentences/words/bullets"
    r"(?:give\s+(?:it\s+to\s+me|me)|show\s+me|list\s+(?:it|them))\s+in\s+\d+\s*(?:steps?|points?|lines?|sentences?|words?|bullets?)"
    r"|in\s+(?:just\s+)?\d+\s*(?:steps?|points?|lines?|sentences?|words?|bullets?)"
    # "summarize", "summarise", "give me a summary"
    r"|(?:give\s+me\s+(?:a\s+)?)?summar(?:ize|ise)(?:\s+that|\s+this|\s+it)?"
    # "make it shorter", "shorter version", "can you shorten"
    r"|(?:make\s+(?:it|that)\s+)?shorter(?:\s+version)?"
    r"|can\s+you\s+shorten"
    r"|shorten\s+(?:that|this|it)"
    # "in one/a sentence", "briefly", "brief version", "quick summary"
    r"|in\s+(?:one|a|two|three)\s+(?:sentence|sentences|line|lines|paragraph)"
    r"|(?:very\s+)?briefly"
    r"|brief\s+(?:version|summary|overview)"
    r"|quick\s+(?:summary|overview|recap)"
    # "simplify", "simpler", "condense", "compress", "tl;dr", "tldr"
    r"|simplif(?:y|ied)(?:\s+(?:that|this|it))?"
    r"|(?:make\s+(?:it|that)\s+)?simpler"
    r"|condense(?:\s+(?:that|this|it))?"
    r"|tl[;:]?dr"
    # "just the steps/key points/main points"
    r"|just\s+(?:the\s+)?(?:steps?|key\s+points?|main\s+points?|highlights?)"
    # "can you make it shorter/simpler/briefer"
    r"|can\s+you\s+make\s+(?:it|that)\s+(?:shorter|simpler|briefer|more\s+concise)"
    r")",
    re.IGNORECASE,
)
 
VAGUE_QUERY_RESPONSE = (
    "Your question is a bit broad — the technical manuals cover many different "
    "equipment types and procedures.\n\n"
    "Could you be more specific? For example:\n"
    "- Which equipment or system are you asking about?\n"
    "- What specific procedure, task, or specification do you need?\n"
    "- Is there a particular voltage, model, or manual section?\n\n"
    "The more detail you provide, the better I can find the right information."
)
 
 
# ─── Classifier ────────────────────────────────────────────────────────────
 
def _strip_punctuation(text: str) -> str:
    """Remove trailing punctuation and extra whitespace."""
    return re.sub(r"[.!?,;:]+$", "", text.strip()).strip()
 
 
def _count_meaningful_words(text: str) -> int:
    """Count words that aren't stopwords or filler."""
    stopwords = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "am", "do", "does", "did", "have", "has", "had", "will",
        "would", "could", "should", "can", "may", "might", "shall",
        "to", "of", "in", "on", "at", "by", "for", "with", "from",
        "up", "out", "if", "or", "and", "but", "not", "no", "so",
        "as", "it", "its", "this", "that", "what", "how", "which",
        "when", "where", "who", "why", "me", "my", "i", "you", "your",
        "we", "our", "they", "them", "their", "he", "she", "his", "her",
        "please", "tell", "give", "show", "explain", "about",
    }
    words = re.findall(r"[a-z0-9]+", text.lower())
    return sum(1 for w in words if w not in stopwords and len(w) > 1)
 
 
def _is_gibberish(text: str) -> bool:
    """Detect keyboard spam, random characters, or meaningless input."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", text).strip()
    if not cleaned:
        return True
    # Very short with no real words
    words = cleaned.split()
    if len(words) <= 2 and all(len(w) <= 2 for w in words):
        return True
    # Repeated characters like "aaaaaa" or "asdfgh"
    if len(cleaned) >= 3 and len(set(cleaned.replace(" ", ""))) <= 3:
        return True
    return False
 
 
def _is_vague_no_history(question: str, has_history: bool) -> bool:
    """Detect vague queries that need clarification.
 
    When has_history=True the user is in an active conversation — short or
    seemingly vague follow-ups ("what about testing?", "tell me more") are
    valid in context and should proceed to RAG. Only genuine standalone vague
    questions without any conversation context should trigger clarification.
    """
    # Never block follow-ups in an active conversation — they have context
    if has_history:
        return False
 
    q = question.lower().strip()
    meaningful = _count_meaningful_words(q)
 
    # Very vague single-concept queries without specificity (first message only)
    vague_patterns = [
        r"^(what|how)\s+(about|is|are)\s+(the\s+)?(procedure|steps|process|requirements?|specifications?|specs?)(\?)?$",
        r"^(tell|show|give)\s+me\s+(about\s+)?(the\s+)?(procedure|steps|process|requirements?|specifications?|specs?)(\?)?$",
        r"^(safety|maintenance|installation|testing|troubleshooting|inspection|procedure)(\?)?$",
        r"^(what|how)\s+(about|is)\s+(safety|maintenance|installation|testing)(\?)?$",
        r"^(the\s+)?(procedure|steps|requirements?|specifications?)(\?)?$",
        # Single generic nouns without equipment/context
        r"^(equipment|tools|materials|parts|components|wiring|cables?)(\?)?$",
        r"^(regulations?|standards?|compliance|rules?)(\?)?$",
        r"^(how to|what to do)(\?)?$",
    ]
    if any(re.match(p, q) for p in vague_patterns):
        return True

    # ── Implicit-reference vague questions ──
    # These match the C8 user-reported pattern: short questions with implicit
    # demonstratives (this/that/here/there) and a generic noun, where the
    # user has not specified the equipment, voltage, or location enough for
    # retrieval to land on the right manual section.
    #
    # Only fire when meaningful words <= 4 — protects specific questions like
    # "Can I install a 15 kV pad-mount transformer here?" from being caught.
    if meaningful <= 4:
        implicit_vague_patterns = [
            # "Can I install/use/put/connect this/the [thing] here/there/inside?"
            # "Can we ..."
            r"^can\s+(i|we)\s+(install|use|put|set|place|run|connect|do|build|operate)\s+(this|that|the|a|an|my)\b",
            # "Can the/this [thing] go/be/fit somewhere?"
            r"^can\s+(the|this|that|my|a|an)\s+\w+(\s+\w+){0,2}\s+(go|be|fit)\b",
            # "Is this/that [thing] (ok|okay|acceptable|allowed|fine|good|right|enough)?"
            r"^is\s+(this|that|it|the)\b.*\b(ok|okay|acceptable|allowed|fine|good|right|enough|safe|proper|valid|correct)\b\s*\??$",
            # "What [generic-noun] do I/we need?" / "What [generic-noun] should I use?"
            # Catches: "What SCADA do I need?", "What breaker should I use?"
            r"^what\s+\w+(\s+\w+){0,1}\s+(do\s+(i|we)\s+)?need\b",
            r"^what\s+\w+(\s+\w+){0,1}\s+should\s+(i|we)\s+(use|do|get|pick|choose|install)\b",
            # "Can I install/put X here?" / "Can we install Y there?"
            r"^can\s+(i|we)\s+(install|put|use|set|place)\s+\w+(\s+\w+){0,2}\s+(here|there|inside|outside|in\s+(this|that|here|there))\??$",
            # "Where do I/we put X?" — implicit-location question
            r"^where\s+(do|should|can)\s+(i|we)\s+\w+\s+",
        ]
        if any(re.match(p, q) for p in implicit_vague_patterns):
            return True
 
    # Pronoun-heavy with no history (first message in conversation)
    pronoun_patterns = [
        r"\b(it|this|that|these|those|the one|the same)\b",
    ]
    if meaningful <= 1 and any(re.search(p, q) for p in pronoun_patterns):
        return True
 
    return False
 
 
def _assistant_ended_with_question(prior_text: str) -> bool:
    """Return True if the last non-empty line of prior_text ends with '?'.

    Used so the bot recognizes when 'yes'/'sure'/'yep' is the user accepting
    an offer the bot just made (e.g. 'Would you like the step-by-step?'),
    rather than a closing acknowledgement.
    """
    if not prior_text:
        return False
    for line in reversed(prior_text.strip().splitlines()):
        line = line.strip().rstrip("*_`)\"' ")
        if line:
            return line.endswith("?")
    return False


def classify_intent(
    question: str,
    has_history: bool = False,
    prior_assistant_msg: str = "",
) -> tuple[str, str | None]:
    """Classify user intent before retrieval.
 
    Parameters
    ----------
    question : str
        The raw user input.
    has_history : bool
        Whether there are prior messages in this conversation.
 
    Returns
    -------
    (intent, canned_response)
        If canned_response is not None, the pipeline should short-circuit
        and return it directly (no retrieval, no LLM).
        If canned_response is None, proceed with the full RAG pipeline.
    """
    raw = question.strip()
    if not raw or not raw.replace(" ", "").replace("\t", "").replace("\n", ""):
        return INTENT_GIBBERISH, GIBBERISH_RESPONSE
 
    normalized = _strip_punctuation(raw).lower()
 
    # 1. Exact-match greetings
    if normalized in _GREETINGS:
        logger.info("Intent: greeting | input=%r", raw)
        return INTENT_GREETING, GREETING_RESPONSE
 
    # 2a. Affirmative-continue ("yes", "sure", "yep", ...) — when the bot
    # just asked a question (e.g. "Would you like the step-by-step?"), the
    # user's "yes" should accept that offer and route to RAG, NOT short-
    # circuit with a "you're welcome" close.
    if normalized in _AFFIRMATIVE_CONTINUE:
        if has_history and _assistant_ended_with_question(prior_assistant_msg):
            logger.info(
                "Intent: affirmative-continue (prior bot question detected) | input=%r",
                raw,
            )
            return INTENT_TECHNICAL, None
        logger.info("Intent: affirmative-acknowledgement | input=%r", raw)
        return INTENT_ACKNOWLEDGEMENT, ACKNOWLEDGEMENT_RESPONSE

    # 2b. Negative decline ("no", "nope", ...) — always close politely.
    if normalized in _NEGATIVE_DECLINE:
        logger.info("Intent: negative-acknowledgement | input=%r", raw)
        return INTENT_ACKNOWLEDGEMENT, ACKNOWLEDGEMENT_RESPONSE

    # 2c. True acknowledgements ("thanks", "bye", "got it", ...) — close.
    if normalized in _ACKNOWLEDGEMENTS:
        logger.info("Intent: acknowledgement | input=%r", raw)
        return INTENT_ACKNOWLEDGEMENT, ACKNOWLEDGEMENT_RESPONSE
 
    # 3. Self-description questions
    for pattern in _SELF_DESCRIPTION_PATTERNS:
        if re.match(pattern, normalized):
            logger.info("Intent: self_description | input=%r", raw)
            return INTENT_SELF_DESCRIPTION, SELF_DESCRIPTION_RESPONSE
 
    # 4. Gibberish / nonsense
    if _is_gibberish(raw):
        logger.info("Intent: gibberish | input=%r", raw)
        return INTENT_GIBBERISH, GIBBERISH_RESPONSE
 
    # 4b. Prompt injection attempts
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, normalized):
            logger.warning("Intent: INJECTION attempt blocked | input=%r", raw)
            return INTENT_INJECTION, INJECTION_RESPONSE
 
    # 5. Out-of-scope topics
    for pattern in _OUT_OF_SCOPE_PATTERNS:
        if re.search(pattern, normalized):
            logger.info("Intent: out_of_scope | input=%r", raw)
            return INTENT_OUT_OF_SCOPE, OUT_OF_SCOPE_RESPONSE
 
    # 6. Vague queries needing clarification (only when no prior conversation)
    if _is_vague_no_history(raw, has_history):
        logger.info("Intent: vague_query | input=%r", raw)
        return INTENT_VAGUE_QUERY, VAGUE_QUERY_RESPONSE
 
    # 7. Condensation — user wants to reformat/compress the prior answer.
    # Only fires when there is prior history (otherwise "summarize" is a vague
    # first question and should go through normal RAG).
    if has_history and _CONDENSATION_PATTERNS.search(normalized):
        logger.info("Intent: condensation | input=%r", raw)
        return INTENT_CONDENSATION, None  # None = proceed to pipeline (skip retrieval)
 
    # 8. Proceed with full RAG pipeline
    return INTENT_TECHNICAL, None
 