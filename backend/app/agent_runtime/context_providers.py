"""ContextProvider — formats retrieved evidence into grounded prompt context.
 
Each retrieved chunk is formatted as a numbered evidence block containing
title, source file, section breadcrumb, URL, chunk ID, and the chunk content.
 
Multimodal support: diagram records include figure_ref and diagram_category;
table records include table_caption. The record_type tag helps the LLM
distinguish between text, diagram, and table evidence.
"""
 
 
def _section_path(r: dict) -> str:
    """Build a readable section breadcrumb from header_1/2/3 fields."""
    parts = [r.get("section1") or "", r.get("section2") or "", r.get("section3") or ""]
    return " > ".join(p for p in parts if p)
 
 
def build_context_blocks(results: list[dict]) -> str:
    """Format retrieved chunks into numbered, labeled evidence blocks.
 
    Each block carries a header with source metadata followed by the raw chunk
    content. The LLM prompt instructs the model to answer only from these blocks
    and to reference them by their [N] label.
 
    Parameters
    ----------
    results:
        Normalised result dicts from RetrievalTool — keys: content, title,
        source, url, chunk_id, section1, section2, section3, score,
        record_type, figure_ref, diagram_category, table_caption,
        printed_page_label.
 
    Returns
    -------
    str
        A single string with one evidence block per chunk, separated by
        horizontal rules.
    """
    blocks: list[str] = []
    for i, r in enumerate(results, start=1):
        record_type = r.get("record_type", "text")
        lines = [f"[{i}]"]
        # Record type tag so the LLM knows what kind of evidence this is
        if record_type and record_type != "text":
            lines.append(f"Type: {record_type}")
        if r.get("title"):
            lines.append(f"Title: {r['title']}")
        lines.append(f"Source: {r['source']}")
        section = _section_path(r)
        if section:
            lines.append(f"Section: {section}")
        # Page info
        page_label = r.get("printed_page_label") or r.get("page") or ""
        if page_label:
            lines.append(f"Page: {page_label}")
        # Diagram-specific metadata
        if record_type == "diagram":
            if r.get("figure_ref"):
                lines.append(f"Figure: {r['figure_ref']}")
            if r.get("diagram_category"):
                lines.append(f"Diagram type: {r['diagram_category']}")
        # Table-specific metadata
        if record_type == "table" and r.get("table_caption"):
            lines.append(f"Table: {r['table_caption']}")
        if r.get("url"):
            lines.append(f"URL: {r['url']}")
        if r.get("chunk_id"):
            lines.append(f"Chunk ID: {r['chunk_id']}")
        if r.get("layout_ordinal") is not None:
            lines.append(f"Position in document: {r['layout_ordinal']}")
        lines.append("Content:")
        lines.append(r["content"])
        blocks.append("\n".join(lines))
 
    return "\n\n---\n\n".join(blocks)
 