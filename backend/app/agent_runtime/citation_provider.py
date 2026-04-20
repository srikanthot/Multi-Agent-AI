"""CitationProvider — deduplicates and structures citations.
 
Converts the raw list of retrieved result dicts into a clean, deduplicated
list of Citation objects ready for the structured SSE citations event.
 
Deduplication key is chunk_id (globally unique per chunk in the index).
Falls back to source+url if chunk_id is missing.
Results are assumed to arrive ordered by relevance score descending, so the
first occurrence of each key is the most relevant chunk.
"""
 
from app.api.schemas import Citation
 
 
def _section_path(r: dict) -> str:
    """Build a section breadcrumb from header_1/2/3 fields.
 
    Uses the most specific (last) available header.
    """
    parts = [r.get("section3") or "", r.get("section2") or "", r.get("section1") or ""]
    return next((p for p in parts if p), "")
 
 
def build_citations(results: list[dict]) -> list[Citation]:
    """Build a deduplicated, ordered citation list from retrieved results.
 
    Parameters
    ----------
    results:
        Normalised result dicts from RetrievalTool — keys: source, title,
        url, chunk_id, section1/2/3, score, record_type, figure_ref,
        diagram_category, table_caption, printed_page_label.
        Ordered highest relevance first.
 
    Returns
    -------
    list[Citation]
        One Citation per unique chunk_id (or source+url), in order of
        first appearance (highest relevance).
    """
    seen: set[str] = set()
    citations: list[Citation] = []
 
    for r in results:
        # chunk_id is globally unique per indexed chunk
        key = r.get("chunk_id") or f"{r['source']}|{r.get('url', '')}"
        if key not in seen:
            seen.add(key)
            ref_num = len(citations) + 1
            # Prefer printed_page_label for human display, fall back to page
            page = r.get("printed_page_label") or r.get("page", "")
            citations.append(
                Citation(
                    ref_number=ref_num,
                    source=r["source"],
                    title=r.get("title", ""),
                    section=_section_path(r),
                    url=r.get("url", ""),
                    chunk_id=r.get("chunk_id", ""),
                    page=page,
                    record_type=r.get("record_type", "text"),
                    figure_ref=r.get("figure_ref", ""),
                    diagram_category=r.get("diagram_category", ""),
                    table_caption=r.get("table_caption", ""),
                )
            )
 
    return citations