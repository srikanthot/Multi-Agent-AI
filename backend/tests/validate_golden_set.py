"""Validate that every expected_keyword in golden_set.json appears verbatim
in the cited manual PDF.

Why this exists:
  ChatGPT generated the test set. ChatGPT sometimes invents keywords that
  aren't actually in the source manual. If we run the full test suite without
  pre-validating the keywords, false negatives will mask the real chatbot
  accuracy. This script catches hallucinated keywords before we waste a real
  Azure test run on bad data.

What it does:
  1. Loads golden_set.json
  2. Loads each PDF in tests/fixtures/manuals/ via PyMuPDF
  3. Normalizes both keyword strings AND PDF text (smart-quote handling, etc.)
  4. For every expected_keywords entry across all 200 tests, checks whether
     the phrase appears verbatim in the manual it claims to be from
  5. Writes a report listing every miss

Run from backend/ directory:
    python -m tests.validate_golden_set

Output:
    tests/golden_validation_report.txt   — human-readable
    tests/golden_validation_report.json  — machine-readable
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF is required. Install: pip install pymupdf", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HERE = Path(__file__).parent
GOLDEN = HERE / "golden_set.json"
MANUALS_DIR = HERE / "fixtures" / "manuals"
REPORT_TXT = HERE / "golden_validation_report.txt"
REPORT_JSON = HERE / "golden_validation_report.json"


# ---------------------------------------------------------------------------
# Text normalization — both PDF text and expected_keywords go through this.
# ChatGPT's output uses curly quotes and en/em-dashes; PDFs use the same.
# Mojibake from earlier copy-paste rounds also gets cleaned here.
# ---------------------------------------------------------------------------

# Curly / typographic punctuation -> ASCII equivalents.
_QUOTE_MAP = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-", "−": "-",
    " ": " ",
    "…": "...",
}
# Mojibake that shows up when UTF-8 was decoded as Windows-1252 then re-encoded.
_MOJIBAKE_MAP = {
    "â€™": "'",
    "â€œ": '"',
    "â€�": '"',
    "â€“": "-",
    "â€”": "-",
}


def normalize(text: str) -> str:
    """Aggressive normalization for fuzzy phrase matching.

    Steps:
      1. NFKC unicode normalization (folds full-width chars, ligatures, etc.)
      2. Replace curly quotes/dashes/ellipsis with ASCII
      3. Replace common mojibake sequences
      4. Lowercase
      5. Collapse all whitespace runs (incl. newlines, tabs) to single spaces
      6. Strip leading/trailing whitespace
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    for src, dst in _MOJIBAKE_MAP.items():
        text = text.replace(src, dst)
    for src, dst in _QUOTE_MAP.items():
        text = text.replace(src, dst)
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# PDF loading
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_path: Path) -> str:
    """Return the full plain-text content of a PDF."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    parts: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            parts.append(page.get_text("text"))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Schema normalization — golden_set.json mixes two schemas.
# ---------------------------------------------------------------------------

def collect_keyword_assertions(test: dict) -> list[dict]:
    """Return a list of {'manual': filename, 'keyword': phrase, 'where': descr}
    for every expected_keywords assertion in this test case.

    Handles all schemas seen in golden_set.json:
      - top-level expected_keywords + manuals[] (batch 1)
      - top-level expected_keywords + expected_manual + manual (batch 2 single-turn)
      - turns[].expected_keywords inside assistant turns
      - turns[].expected_keywords + expected_manual on user turns (batch 2)
      - expected_keywords_for_q2 / expected_keywords_for_q3 / expected_keywords_for_final

    For "negative" cases (should_answer == False, or category contains "negative"
    or "vague_or_underspecified"), we expect zero keywords — those are
    "should refuse to answer" tests and we skip keyword validation.
    """
    out: list[dict] = []

    # Negative cases — should_answer=False or category indicating refusal
    cat = (test.get("category") or "").lower()
    is_negative = (
        test.get("should_answer") is False
        or "negative" in cat
        or "vague_or_underspecified" in cat
    )
    if is_negative:
        return []

    # Fall-back manuals list (used when an assertion doesn't carry its own)
    fallback_manuals: list[str] = []
    if test.get("manuals"):
        fallback_manuals = list(test["manuals"])
    elif test.get("manual"):
        fallback_manuals = [test["manual"]]
    elif test.get("expected_manual"):
        fallback_manuals = [test["expected_manual"]]

    # Top-level keywords (single-turn cases + some multi-turn final assertions)
    for key in ("expected_keywords", "expected_keywords_for_q2",
                "expected_keywords_for_q3", "expected_keywords_for_final"):
        if key in test and isinstance(test[key], list):
            manual = (
                test.get("expected_manual_for_q2")
                or test.get("expected_manual_for_q3")
                or test.get("expected_manual_for_final")
                or test.get("expected_manual")
                or test.get("manual")
                or (fallback_manuals[0] if len(fallback_manuals) == 1 else None)
            )
            for kw in test[key]:
                if not kw or not isinstance(kw, str):
                    continue
                out.append({
                    "manual": manual,
                    "keyword": kw,
                    "where": f"{test['id']} (top-level {key})",
                    "fallback_manuals": fallback_manuals,
                })

    # Turns-array keywords (multi-turn cases)
    for i, turn in enumerate(test.get("turns") or []):
        for key in ("expected_keywords",):
            kws = turn.get(key) or []
            for kw in kws:
                if not kw or not isinstance(kw, str):
                    continue
                out.append({
                    "manual": turn.get("expected_manual") or (
                        fallback_manuals[0] if len(fallback_manuals) == 1 else None
                    ),
                    "keyword": kw,
                    "where": f"{test['id']} (turn[{i}] {turn.get('role', '?')})",
                    "fallback_manuals": fallback_manuals,
                })

    return out


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(golden_path: Path, manuals_dir: Path) -> dict:
    if not golden_path.exists():
        raise FileNotFoundError(f"golden_set.json not found at {golden_path}")
    if not manuals_dir.exists():
        raise FileNotFoundError(f"Manuals directory not found at {manuals_dir}")

    with open(golden_path, "r", encoding="utf-8") as f:
        gold = json.load(f)

    # Load all PDFs we know about, plus normalize once
    referenced_manuals = {gold.get("manual_a_name"),
                          gold.get("manual_b_name"),
                          gold.get("manual_c_name")} - {None}

    pdf_texts: dict[str, str] = {}
    pdf_norm: dict[str, str] = {}
    missing_pdfs: list[str] = []
    for fname in referenced_manuals:
        if not fname:
            continue
        path = manuals_dir / fname
        if not path.exists():
            missing_pdfs.append(fname)
            continue
        try:
            raw = extract_pdf_text(path)
            pdf_texts[fname] = raw
            pdf_norm[fname] = normalize(raw)
        except Exception as exc:
            missing_pdfs.append(f"{fname} (error: {exc})")

    if missing_pdfs:
        print("WARN: missing or unreadable manuals:", missing_pdfs, file=sys.stderr)

    # Walk every test, every assertion
    results: list[dict] = []
    by_test: dict[str, list[dict]] = defaultdict(list)

    for test in gold["tests"]:
        for assertion in collect_keyword_assertions(test):
            manual = assertion["manual"]
            kw = assertion["keyword"]
            where = assertion["where"]

            outcome = {
                "test_id": test["id"],
                "category": test.get("category"),
                "where": where,
                "manual": manual,
                "keyword": kw,
                "found": False,
                "found_in": None,
                "reason": None,
            }

            kw_norm = normalize(kw)
            if not kw_norm:
                outcome["reason"] = "empty_keyword_after_normalization"
                results.append(outcome)
                by_test[test["id"]].append(outcome)
                continue

            # Try the cited manual first; fall back to any of the test's
            # candidate manuals if not found.
            candidates: list[str] = []
            if manual and manual in pdf_norm:
                candidates.append(manual)
            for fb in (assertion.get("fallback_manuals") or []):
                if fb in pdf_norm and fb not in candidates:
                    candidates.append(fb)
            # If nothing usable, search ALL loaded manuals as last resort
            if not candidates:
                candidates = list(pdf_norm.keys())

            for cand in candidates:
                if kw_norm in pdf_norm[cand]:
                    outcome["found"] = True
                    outcome["found_in"] = cand
                    if cand != manual:
                        outcome["reason"] = "found_in_other_manual"
                    break

            if not outcome["found"]:
                if manual and manual not in pdf_norm:
                    outcome["reason"] = f"cited_manual_not_loaded:{manual}"
                else:
                    outcome["reason"] = "phrase_not_found_verbatim"

            results.append(outcome)
            by_test[test["id"]].append(outcome)

    # Summary
    total = len(results)
    found = sum(1 for r in results if r["found"])
    missing = total - found
    found_in_other = sum(1 for r in results if r["found"] and r["reason"] == "found_in_other_manual")

    by_cat_summary: dict[str, dict] = defaultdict(lambda: {"total": 0, "found": 0})
    for r in results:
        cat = r["category"] or "unknown"
        by_cat_summary[cat]["total"] += 1
        if r["found"]:
            by_cat_summary[cat]["found"] += 1

    fully_clean_tests = sum(
        1 for tid, items in by_test.items() if all(r["found"] for r in items)
    )
    tests_with_issues = sum(
        1 for tid, items in by_test.items() if any(not r["found"] for r in items)
    )

    return {
        "summary": {
            "total_keyword_assertions": total,
            "verbatim_found": found,
            "missing": missing,
            "found_in_other_manual": found_in_other,
            "found_pct": round(100.0 * found / max(total, 1), 1),
            "tests_fully_clean": fully_clean_tests,
            "tests_with_issues": tests_with_issues,
            "missing_pdfs": missing_pdfs,
        },
        "by_category": {
            cat: {
                "total": v["total"],
                "found": v["found"],
                "pct": round(100.0 * v["found"] / max(v["total"], 1), 1),
            }
            for cat, v in by_cat_summary.items()
        },
        "results": results,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def write_reports(report: dict, txt_path: Path, json_path: Path) -> None:
    s = report["summary"]
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("GOLDEN SET — KEYWORD VERBATIM VALIDATION REPORT")
    lines.append("=" * 72)
    lines.append("")
    lines.append(f"Total keyword assertions checked: {s['total_keyword_assertions']}")
    lines.append(f"Found verbatim (after normalization): {s['verbatim_found']} ({s['found_pct']}%)")
    lines.append(f"Missing: {s['missing']}")
    lines.append(f"Found in DIFFERENT manual than cited: {s['found_in_other_manual']}")
    lines.append("")
    lines.append(f"Tests fully clean (every keyword found): {s['tests_fully_clean']}")
    lines.append(f"Tests with at least one issue: {s['tests_with_issues']}")
    if s.get("missing_pdfs"):
        lines.append("")
        lines.append("WARNING: missing/unreadable PDFs:")
        for m in s["missing_pdfs"]:
            lines.append(f"  - {m}")
    lines.append("")
    lines.append("-" * 72)
    lines.append("BY CATEGORY")
    lines.append("-" * 72)
    for cat in sorted(report["by_category"].keys()):
        v = report["by_category"][cat]
        lines.append(f"  {v['pct']:5.1f}%  ({v['found']:3d}/{v['total']:3d})  {cat}")
    lines.append("")
    lines.append("-" * 72)
    lines.append("MISSING / PROBLEMATIC ASSERTIONS")
    lines.append("-" * 72)
    misses = [r for r in report["results"] if not r["found"]]
    if not misses:
        lines.append("  (none — every keyword was found verbatim)")
    for r in misses:
        lines.append(
            f"  {r['test_id']}  [{r['category']}]  manual={r['manual']!r}"
        )
        lines.append(f"      keyword: {r['keyword']!r}")
        lines.append(f"      reason : {r['reason']}")
        lines.append(f"      where  : {r['where']}")
    lines.append("")
    lines.append("-" * 72)
    lines.append("ASSERTIONS FOUND IN A DIFFERENT MANUAL THAN CITED")
    lines.append("-" * 72)
    drift = [r for r in report["results"] if r["found"] and r["reason"] == "found_in_other_manual"]
    if not drift:
        lines.append("  (none)")
    for r in drift:
        lines.append(
            f"  {r['test_id']}  cited={r['manual']!r}  found_in={r['found_in']!r}"
        )
        lines.append(f"      keyword: {r['keyword']!r}")

    txt_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n".join(lines[:30]))
    print(f"\nFull report:")
    print(f"  Text: {txt_path}")
    print(f"  JSON: {json_path}")


def main() -> int:
    report = validate(GOLDEN, MANUALS_DIR)
    write_reports(report, REPORT_TXT, REPORT_JSON)
    return 0


if __name__ == "__main__":
    sys.exit(main())
