"""RetrievalTool — hybrid search against Azure AI Search.
 
Pipeline inside retrieve():
  1. Distill the user's query: strip conversational filler so BM25 keyword
     search focuses on technical terms.
     The original query is still used for vector embedding (semantic).
  2. Generate query embedding via Azure OpenAI (aoai_embeddings.embed).
  3. Issue a hybrid search against RETRIEVAL_CANDIDATES (wider pool):
       keyword (distilled search_text) + vector (VectorizedQuery on text_vector).
  4. Optionally apply semantic reranking with manual-semantic-config.
  5. Normalise raw Azure Search documents to a canonical dict schema.
  6. Sort by effective score: reranker_score when semantic is active,
     base RRF score otherwise.
  7. Filter TOC / index pages.
  8. Adaptive diversity filter (dominant source gets higher cap).
  9. Score-gap filter using effective score.
 10. Return at most TOP_K final results.
 
The index is assumed to ALREADY EXIST — this module never creates or
modifies the index.
"""
 
import logging
import re
from collections import defaultdict
 
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
 
from app.config.settings import (
    AZURE_SEARCH_API_KEY,
    AZURE_SEARCH_ENDPOINT,
    AZURE_SEARCH_INDEX,
    DIVERSITY_BY_SOURCE,
    DOMINANT_SOURCE_SCORE_RATIO,
    MAX_CHUNKS_DOMINANT_SOURCE,
    MAX_CHUNKS_PER_SOURCE,
    QUERY_LANGUAGE,
    RETRIEVAL_CANDIDATES,
    SCORE_GAP_MIN_RATIO,
    SEARCH_CHUNK_ID_FIELD,
    SEARCH_CONTENT_FIELD,
    SEARCH_FILENAME_FIELD,
    SEARCH_FILTER,
    SEARCH_PAGE_FIELD,
    SEARCH_SECTION1_FIELD,
    SEARCH_SECTION2_FIELD,
    SEARCH_SECTION3_FIELD,
    SEARCH_SEMANTIC_CONTENT_FIELD,
    SEARCH_TITLE_FIELD,
    SEARCH_URL_FIELD,
    SEARCH_VECTOR_FIELD,
    SEMANTIC_CONFIG_NAME,
    TOP_K,
    TRACE_MODE,
    USE_SEMANTIC_RERANKER,
    VECTOR_K,
)
from app.llm.aoai_embeddings import embed
 
logger = logging.getLogger(__name__)
 
# ---------------------------------------------------------------------------
# Query distillation — strip conversational filler before BM25 keyword search
# ---------------------------------------------------------------------------
_FILLER_RE = re.compile(
    r"\b(right now|currently|at this (moment|time)|i am|i'm|i need to|i want to|"
    r"can you|what should( i)?|how do i|what are the|please|tell me|help me|"
    r"so |just |i was told|could you|would you|i have to|what do i|"
    r"show me|give me|find me|get me|provide me|i'd like|i need|"
    r"i want to know|basically|actually|really|anyway)\b",
    re.IGNORECASE,
)
 
# ---------------------------------------------------------------------------
# TOC/index chunk detection
# ---------------------------------------------------------------------------
_TOC_CHUNK_PATTERNS = [
    re.compile(r"Table\s+of\s+Contents", re.IGNORECASE),
    re.compile(r"(\. ){5,}"),          # dot leaders: ". . . . . . 2-11"
    re.compile(r"^Index\b", re.IGNORECASE | re.MULTILINE),
]
 
_NUMBERED_SECTION_RE = re.compile(r"^\d+(\.\d+)*\s+\S")
 
 
def _is_toc_chunk(content: str) -> bool:
    """Return True if this chunk looks like a Table of Contents / index page."""
    sample = content[:400]
    return any(p.search(sample) for p in _TOC_CHUNK_PATTERNS)
 
 
def _distill_keyword_query(question: str) -> str:
    """Remove conversational filler to improve BM25 keyword recall."""
    distilled = _FILLER_RE.sub(" ", question)
    distilled = re.sub(r"[,\s]+", " ", distilled).strip()
    return distilled if len(distilled) >= 10 else question
 
 
def _extract_heading(content: str) -> str:
    """Extract a section heading from the first few lines of a chunk."""
    for line in content.strip().splitlines()[:4]:
        line = line.strip()
        if not line or len(line) > 80:
            continue
        if _NUMBERED_SECTION_RE.match(line):
            return line
        if line.isupper() and len(line) >= 5:
            return line
        words = line.split()
        if (2 <= len(words) <= 9
                and all(w[0].isupper() for w in words if len(w) > 3)):
            return line
    return ""
 
 
def _effective_score(r: dict) -> float:
    """Return the best available relevance score for sorting and gap-filtering.
 
    When semantic reranker is active, reranker_score (0-4 scale) is used.
    Otherwise the base RRF/hybrid score (0.01-0.033 scale) is used.
    """
    rs = r.get("reranker_score")
    return rs if rs is not None else r["score"]
 
 
# Module-level singleton — reuses HTTP connection pool across calls.
_search_client: SearchClient | None = None
 
 
def _get_search_client() -> SearchClient:
    """Return the shared SearchClient, creating it on first use."""
    global _search_client
    if _search_client is None:
        _search_client = SearchClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            index_name=AZURE_SEARCH_INDEX,
            credential=AzureKeyCredential(AZURE_SEARCH_API_KEY),
        )
    return _search_client
 
 
def _select_fields() -> list[str]:
    """Return the list of index fields to retrieve.
 
    Includes all schema fields needed for context building and citations.
    Optional fields (SEARCH_PAGE_FIELD) are included only when non-empty.
    text_vector is excluded — it is stored=false/not retrievable.
    """
    fields = [
        SEARCH_CONTENT_FIELD,
        SEARCH_SEMANTIC_CONTENT_FIELD,
        SEARCH_TITLE_FIELD,
        SEARCH_FILENAME_FIELD,
        SEARCH_URL_FIELD,
        SEARCH_CHUNK_ID_FIELD,
        SEARCH_SECTION1_FIELD,
        SEARCH_SECTION2_FIELD,
        SEARCH_SECTION3_FIELD,
        # Schema-fixed fields not exposed as env vars
        "parent_id",
        "layout_ordinal",
        # Multimodal index fields
        "record_type",
        "diagram_description",
        "diagram_category",
        "figure_ref",
        "has_diagram",
        "surrounding_context",
        "table_caption",
        "printed_page_label",
        "processing_status",
    ]
    if SEARCH_PAGE_FIELD:
        fields.append(SEARCH_PAGE_FIELD)
    # Filter out any blank values (optional fields left empty in .env)
    return [f for f in fields if f]
 
 
def _normalize(doc: dict) -> dict:
    """Map a raw Azure Search document to the canonical result schema.
 
    Returns
    -------
    dict with keys:
        content            -- main chunk text passed to the LLM
        semantic_content   -- chunk_for_semantic (stored, not sent to LLM directly)
        title              -- document title
        source             -- source filename
        url                -- blob URL
        chunk_id           -- unique chunk key
        parent_id          -- parent document key
        section1/2/3       -- header_1/2/3 breadcrumb fields
        layout_ordinal     -- section ordering within the document
        page               -- page number string (empty if SEARCH_PAGE_FIELD not set)
        printed_page_label -- human-readable page label (e.g. '3-12')
        record_type        -- 'text', 'diagram', 'table', or 'summary'
        diagram_description -- GPT-4.1 vision description for diagram records
        diagram_category   -- e.g. 'wiring_diagram', 'schematic'
        figure_ref         -- e.g. 'Figure 4-2'
        table_caption      -- caption for table records
        score              -- base RRF/hybrid search score
        reranker_score     -- semantic reranker score (None if reranker not used)
    """
    record_type = doc.get("record_type") or "text"
    diagram_desc = doc.get("diagram_description") or ""
    raw_content = doc.get(SEARCH_CONTENT_FIELD) or ""
 
    # For diagram records, prefer the rich GPT-4.1 description over raw chunk
    if record_type == "diagram" and diagram_desc:
        content = diagram_desc
    else:
        content = raw_content
 
    return {
        "content":              content,
        "semantic_content":     doc.get(SEARCH_SEMANTIC_CONTENT_FIELD) or "",
        "title":                doc.get(SEARCH_TITLE_FIELD) or "",
        "source":               doc.get(SEARCH_FILENAME_FIELD) or "",
        "url":                  doc.get(SEARCH_URL_FIELD) or "",
        "chunk_id":             doc.get(SEARCH_CHUNK_ID_FIELD) or "",
        "parent_id":            doc.get("parent_id") or "",
        "section1":             doc.get(SEARCH_SECTION1_FIELD) or "",
        "section2":             doc.get(SEARCH_SECTION2_FIELD) or "",
        "section3":             doc.get(SEARCH_SECTION3_FIELD) or "",
        "layout_ordinal":       doc.get("layout_ordinal"),
        "page":                 str(doc.get(SEARCH_PAGE_FIELD) or "") if SEARCH_PAGE_FIELD else "",
        "printed_page_label":   doc.get("printed_page_label") or "",
        "record_type":          record_type,
        "diagram_description":  diagram_desc,
        "diagram_category":     doc.get("diagram_category") or "",
        "figure_ref":           doc.get("figure_ref") or "",
        "table_caption":        doc.get("table_caption") or "",
        "score":                doc.get("@search.score") or 0.0,
        "reranker_score":       doc.get("@search.reranker_score"),  # None when not used
    }
 
 
def _adaptive_diversity(results: list[dict]) -> list[dict]:
    """Adaptive per-source cap that rewards a clearly dominant source.
 
    Standard: cap every source at MAX_CHUNKS_PER_SOURCE.
    Dominant: if one source's top effective score >= DOMINANT_SOURCE_SCORE_RATIO
    x the next source's top score, allow up to MAX_CHUNKS_DOMINANT_SOURCE from it.
    """
    if not results:
        return results
 
    source_top: dict[str, float] = {}
    for r in results:
        src = r["source"]
        if src not in source_top:
            source_top[src] = _effective_score(r)
 
    sorted_sources = sorted(source_top.items(), key=lambda x: x[1], reverse=True)
    dominant_source = sorted_sources[0][0]
    dominant_score = sorted_sources[0][1]
    second_score = sorted_sources[1][1] if len(sorted_sources) > 1 else 0.0
 
    is_dominant = (
        second_score == 0.0
        or dominant_score >= DOMINANT_SOURCE_SCORE_RATIO * second_score
    )
    cap_for_dominant = MAX_CHUNKS_DOMINANT_SOURCE if is_dominant else MAX_CHUNKS_PER_SOURCE
 
    if TRACE_MODE:
        ratio_str = (
            f"{dominant_score / second_score:.2f}x"
            if second_score > 0 else "inf"
        )
        logger.info(
            "TRACE | dominant_source=%s  score_ratio=%s  dominant=%s  cap=%d",
            dominant_source, ratio_str, is_dominant, cap_for_dominant,
        )
 
    counts: defaultdict[str, int] = defaultdict(int)
    filtered: list[dict] = []
    for r in results:
        src = r["source"]
        cap = cap_for_dominant if src == dominant_source else MAX_CHUNKS_PER_SOURCE
        if counts[src] < cap:
            filtered.append(r)
            counts[src] += 1
    return filtered
 
 
def _filter_score_gap(results: list[dict]) -> list[dict]:
    """Remove chunks whose effective score falls below SCORE_GAP_MIN_RATIO x top.
 
    Uses effective score (reranker when available) so the filter is consistent
    with the sort order.
    """
    if not results or SCORE_GAP_MIN_RATIO <= 0:
        return results
 
    top_score = _effective_score(results[0])
    if top_score == 0:
        return results
 
    threshold = SCORE_GAP_MIN_RATIO * top_score
    filtered = [r for r in results if _effective_score(r) >= threshold]
 
    removed = len(results) - len(filtered)
    if TRACE_MODE and removed:
        logger.info(
            "TRACE | score_gap_filter: removed %d chunk(s) below %.4f "
            "(%.0f%% of top %.4f)",
            removed, threshold, SCORE_GAP_MIN_RATIO * 100, top_score,
        )
    return filtered
 
 
def retrieve(question: str, top_k: int = TOP_K) -> list[dict]:
    """Run a hybrid search and return normalised, filtered results.
 
    Parameters
    ----------
    question:
        The user's question. Used verbatim for vector embedding.
        A distilled version is used for BM25 keyword search.
    top_k:
        Maximum number of chunks to return after all filters.
 
    Returns
    -------
    list[dict]
        Normalised result dicts ordered by effective relevance score descending.
    """
    # ── 1. Distill keyword query ──────────────────────────────────────────────
    keyword_query = _distill_keyword_query(question)
    if TRACE_MODE and keyword_query != question:
        logger.info("TRACE | keyword_query=%r", keyword_query)
 
    # ── 2. Generate query embedding (original question, not distilled) ────────
    query_vector: list[float] | None = None
    try:
        query_vector = embed(question)
    except Exception:
        logger.error(
            "Embedding generation FAILED — falling back to keyword-only search. "
            "Retrieval quality will be degraded (keyword-only, no semantic matching). "
            "Check Azure OpenAI endpoint, API key, and embedding deployment.",
            exc_info=True,
        )
 
    # ── 3. Build search arguments ─────────────────────────────────────────────
    client = _get_search_client()
    select = _select_fields()
 
    search_kwargs: dict = {
        "search_text": keyword_query,
        "top": RETRIEVAL_CANDIDATES,
        "select": select,
    }
 
    # Apply OData filter to exclude summary/decorative/broken records
    if SEARCH_FILTER:
        search_kwargs["filter"] = SEARCH_FILTER
 
    if query_vector:
        search_kwargs["vector_queries"] = [
            VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=VECTOR_K,
                fields=SEARCH_VECTOR_FIELD,
            )
        ]
 
    # ── 4. Execute search (with optional semantic reranking) ──────────────────
    raw_results: list[dict] = []
 
    if USE_SEMANTIC_RERANKER:
        try:
            from azure.search.documents.models import QueryType  # noqa: PLC0415
 
            search_kwargs["query_type"] = QueryType.SEMANTIC
            search_kwargs["semantic_configuration_name"] = SEMANTIC_CONFIG_NAME
            search_kwargs["query_language"] = QUERY_LANGUAGE
            raw_results = list(client.search(**search_kwargs))
            logger.info("Semantic reranker active — %d raw results", len(raw_results))
        except Exception:
            logger.error(
                "Semantic reranking FAILED — falling back to pure hybrid search. "
                "QUALITY DEGRADED: results will use RRF scores instead of "
                "reranker scores, which may cause gate threshold mismatches. "
                "Check semantic config '%s' and index status.",
                SEMANTIC_CONFIG_NAME,
                exc_info=True,
            )
            search_kwargs.pop("query_type", None)
            search_kwargs.pop("semantic_configuration_name", None)
            search_kwargs.pop("query_language", None)
            raw_results = list(client.search(**search_kwargs))
    else:
        raw_results = list(client.search(**search_kwargs))
 
    # ── 5. Normalise and sort by effective score ──────────────────────────────
    # Sort by reranker_score when semantic is on (Azure returns results already
    # in reranker order, but re-sort after normalisation to be explicit).
    results = [_normalize(doc) for doc in raw_results]
 
    # Filter out documents with missing critical fields
    before_validation = len(results)
    results = [r for r in results if r["content"].strip() and r["source"].strip()]
    if len(results) < before_validation:
        logger.warning(
            "Filtered %d document(s) with missing content or source fields",
            before_validation - len(results),
        )
 
    results.sort(key=_effective_score, reverse=True)
 
    # ── 5b. Filter TOC / index pages ─────────────────────────────────────────
    before_toc = len(results)
    results = [r for r in results if not _is_toc_chunk(r["content"])]
    if TRACE_MODE and len(results) < before_toc:
        logger.info(
            "TRACE | toc_filter: removed %d TOC/index chunk(s)",
            before_toc - len(results),
        )
 
    # ── 6. Adaptive diversity filter ─────────────────────────────────────────
    if DIVERSITY_BY_SOURCE:
        results = _adaptive_diversity(results)
 
    # ── 7. Score-gap filter ───────────────────────────────────────────────────
    results = _filter_score_gap(results)
 
    # ── 8. Trim to top_k ──────────────────────────────────────────────────────
    results = results[:top_k]
 
    # ── 9. Re-order within each source by layout_ordinal ─────────────────────
    # After all score-based filtering, chunks from the same document should be
    # presented to the LLM in their original document sequence so procedures
    # read in order (step 1, step 2, step 3) rather than relevance order.
    # Cross-source ordering is preserved — the source with the highest-scoring
    # first chunk appears first in the final list.
    if len(results) > 1:
        # Determine source ordering by the first (highest-scoring) chunk per source
        source_order: dict[str, int] = {}
        for r in results:
            if r["source"] not in source_order:
                source_order[r["source"]] = len(source_order)
        results.sort(key=lambda r: (
            source_order[r["source"]],                    # primary: source relevance rank
            r["layout_ordinal"] if r["layout_ordinal"] is not None else float("inf"),  # secondary: doc position
        ))
 
    # ── 9. Trace logging ──────────────────────────────────────────────────────
    if TRACE_MODE:
        logger.info("TRACE | final_chunks=%d (top_k=%d)", len(results), top_k)
        for i, r in enumerate(results, start=1):
            heading = _extract_heading(r["content"])
            section_parts = [r["section1"], r["section2"], r["section3"]]
            section = " > ".join(p for p in section_parts if p)
            reranker_str = (
                f"  reranker={r['reranker_score']:.4f}"
                if r.get("reranker_score") is not None else ""
            )
            preview = r["content"][:120].replace("\n", " ")
            rtype = r.get("record_type", "text")
            logger.info(
                "TRACE | [%d] type=%s  source=%s  ordinal=%s  score=%.4f%s  section=%r | %s",
                i, rtype, r["source"], r["layout_ordinal"], r["score"],
                reranker_str, section, preview,
            )
 
    return results
 