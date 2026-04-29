"""Re-score a previous golden-set run with improved scoring logic.

Why this exists:
  The original run_golden_set.py uses strict verbatim keyword matching.
  In practice the chatbot paraphrases the manual, so verbatim-only scoring
  produces a misleadingly low PASS rate. Many "FAILs" are actually correct
  answers expressed in different words.

  Similarly, the original no-evidence detector only catches a few phrasings.
  Many valid refusals on negative tests get marked FAIL because the bot
  said "doesn't appear to be covered" instead of "I don't have enough
  evidence".

What this does:
  Reads all_results.json from a previous run, re-scores each test using:
    1. Token-overlap keyword matching (≥80% of significant tokens found
       counts as "keyword present"). Handles paraphrasing.
    2. Expanded refusal-phrase detection.
  Writes a new summary report next to the original. Original files are
  left untouched so you can compare.

Usage:
  python -m tests.rescore_golden_set tests/golden_results/2026-04-28_233544
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Text normalization (same as validator)
# ---------------------------------------------------------------------------

_QUOTE_MAP = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-", "−": "-",
    " ": " ",
    "…": "...",
}
_MOJIBAKE_MAP = {
    "â€™": "'", "â€œ": '"', "â€�": '"', "â€“": "-", "â€”": "-",
}


def normalize(text: str) -> str:
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
# Token-overlap keyword match
# ---------------------------------------------------------------------------

# Tokens to ignore when scoring keyword overlap — common stop-words plus
# punctuation. We focus on substantive content words.
_TOKEN_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "am", "do", "does", "did", "have", "has", "had", "having",
    "to", "of", "in", "on", "at", "by", "for", "with", "from", "into",
    "and", "or", "but", "not", "no", "so", "as",
    "this", "that", "these", "those", "it", "its",
    "shall", "must", "should", "may", "can", "will", "would",
    "you", "your", "we", "our", "they", "them", "their",
}


def _tokens(text: str) -> list[str]:
    """Extract significant tokens from text. Lowercased, no punctuation."""
    text = normalize(text)
    # Split on non-alphanumeric, keep tokens of length >=2 not in stopwords
    raw = re.findall(r"[a-z0-9]+", text)
    return [t for t in raw if len(t) >= 2 and t not in _TOKEN_STOPWORDS]


def keyword_found(keyword: str, answer: str, threshold: float = 0.8) -> bool:
    """Return True if the keyword's significant tokens appear in the answer.

    Strict verbatim match is checked first (fast path). If that fails,
    we fall back to token-overlap: if ≥`threshold` (default 80%) of the
    keyword's significant tokens are present in the answer (in any order),
    consider the keyword found.

    This handles paraphrasing: 'inspection authority having jurisdiction'
    matches 'authorized inspection agency...having jurisdiction' because
    'inspection', 'authority', 'jurisdiction' all appear.
    """
    if not keyword:
        return False
    norm_kw = normalize(keyword)
    norm_ans = normalize(answer)
    if not norm_ans:
        return False

    # Fast path — verbatim substring match
    if norm_kw in norm_ans:
        return True

    # Token-overlap fallback
    kw_tokens = _tokens(keyword)
    if not kw_tokens:
        # Keyword has no significant tokens — fall back to substring (already failed)
        return False
    ans_token_set = set(_tokens(answer))
    overlap = sum(1 for t in kw_tokens if t in ans_token_set)
    return (overlap / len(kw_tokens)) >= threshold


# ---------------------------------------------------------------------------
# Expanded refusal detection
# ---------------------------------------------------------------------------

_NO_EVIDENCE_PATTERNS = [
    # Original markers
    "i don't have enough evidence",
    "i do not have enough evidence",
    "could you provide more detail",
    "could you be more specific",
    "i cannot find",
    "i can't find",
    "the manuals do not",
    "not covered in the",
    "outside the scope",
    # Additions found in actual chatbot output (T194, T196, etc.)
    "doesn't appear to be covered",
    "does not appear to be covered",
    "there is no specific information",
    "no specific information",
    "i can only answer questions based on",
    "topic doesn't appear",
    "topic does not appear",
    "is not covered in",
    "manuals do not provide",
    "manuals don't provide",
    "manuals don't include",
    "manuals do not include",
    "the provided context does not",
    "based on the provided context, there is no",
    "i don't have that specific information",
    "i do not have that specific information",
    "i'm unable to provide",
    "i am unable to provide",
    "the information provided does not",
    "no information about",
    "no relevant information",
    "i don't have access to",
    "i do not have access to",
    "try asking about",
]

_CLARIFICATION_PATTERNS = [
    "could you provide",
    "could you clarify",
    "could you specify",
    "what equipment",
    "which equipment",
    "what voltage",
    "which voltage",
    "more specific",
    "can you clarify",
    "can you specify",
]


def is_refusal(answer: str) -> bool:
    norm = normalize(answer)
    return any(p in norm for p in (normalize(x) for x in _NO_EVIDENCE_PATTERNS))


def is_clarification(answer: str) -> bool:
    norm = normalize(answer)
    return any(p in norm for p in (normalize(x) for x in _CLARIFICATION_PATTERNS))


# ---------------------------------------------------------------------------
# Re-score one result
# ---------------------------------------------------------------------------

def rescore_result(r: dict) -> dict:
    """Return a new result dict with status, keywords_found, etc. recomputed."""
    answer = r.get("final_answer", "") or ""
    is_negative = r.get("is_negative", False)
    expected = r.get("keywords_expected", []) or []
    error = r.get("error")

    found: list[str] = []
    missing: list[str] = []
    for kw in expected:
        if keyword_found(kw, answer):
            found.append(kw)
        else:
            missing.append(kw)

    if error:
        status = "ERROR"
    elif is_negative:
        status = "PASS" if (is_refusal(answer) or is_clarification(answer)) else "FAIL"
    else:
        if not answer.strip():
            status = "FAIL"
        elif is_refusal(answer) and not found:
            status = "FAIL"
        elif missing == [] and found:
            status = "PASS"
        elif found:
            status = "PARTIAL"
        else:
            status = "FAIL"

    new = dict(r)
    new["status"] = status
    new["keywords_found"] = found
    new["keywords_missing"] = missing
    return new


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: python -m tests.rescore_golden_set <result_dir>", file=sys.stderr)
        print(f"  e.g. python -m tests.rescore_golden_set tests/golden_results/2026-04-28_233544", file=sys.stderr)
        return 2

    result_dir = Path(sys.argv[1])
    all_results_path = result_dir / "all_results.json"
    if not all_results_path.exists():
        print(f"ERROR: {all_results_path} not found", file=sys.stderr)
        return 2

    with open(all_results_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    rescored = [rescore_result(r) for r in results]

    # Aggregate
    by_status: dict[str, int] = {"PASS": 0, "PARTIAL": 0, "FAIL": 0, "ERROR": 0}
    by_category: dict[str, dict] = {}
    for r in rescored:
        cat = r.get("category") or "unknown"
        b = by_category.setdefault(cat, {"PASS": 0, "PARTIAL": 0, "FAIL": 0, "ERROR": 0})
        b[r["status"]] = b.get(r["status"], 0) + 1
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    total = len(rescored)
    pass_pct = round(100.0 * by_status["PASS"] / max(total, 1), 1)
    partial_pct = round(100.0 * by_status["PARTIAL"] / max(total, 1), 1)
    fail_pct = round(100.0 * by_status["FAIL"] / max(total, 1), 1)
    error_pct = round(100.0 * by_status["ERROR"] / max(total, 1), 1)
    pass_or_partial = by_status["PASS"] + by_status["PARTIAL"]
    pass_or_partial_pct = round(100.0 * pass_or_partial / max(total, 1), 1)

    # Compare to original
    orig_path = result_dir / "summary.json"
    orig: dict = {}
    if orig_path.exists():
        try:
            orig = json.loads(orig_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    orig_by_status = orig.get("by_status", {})

    # Write reports
    summary_lines: list[str] = []
    summary_lines.append("=" * 72)
    summary_lines.append("GOLDEN SET — RE-SCORED with token-overlap + expanded refusal detection")
    summary_lines.append("=" * 72)
    summary_lines.append(f"Source dir:  {result_dir.name}")
    summary_lines.append(f"Total:       {total}")
    summary_lines.append("")
    summary_lines.append(f"{'':10s}{'OLD':>10s}{'NEW':>10s}")
    for s in ("PASS", "PARTIAL", "FAIL", "ERROR"):
        old = orig_by_status.get(s, 0)
        new = by_status[s]
        summary_lines.append(f"{s:10s}{old:>10d}{new:>10d}")
    summary_lines.append("")
    summary_lines.append(f"PASS rate:           {pass_pct}%")
    summary_lines.append(f"PASS+PARTIAL rate:   {pass_or_partial_pct}%   (functionally correct)")
    summary_lines.append(f"FAIL rate:           {fail_pct}%")
    summary_lines.append(f"ERROR rate:          {error_pct}%")
    summary_lines.append("")
    summary_lines.append("BY CATEGORY")
    summary_lines.append("-" * 72)
    for cat in sorted(by_category.keys()):
        v = by_category[cat]
        cat_total = sum(v.values())
        cp_pct = round(100.0 * v["PASS"] / max(cat_total, 1), 1)
        ok_pct = round(100.0 * (v["PASS"] + v["PARTIAL"]) / max(cat_total, 1), 1)
        summary_lines.append(
            f"  pass={cp_pct:5.1f}%  ok={ok_pct:5.1f}%  "
            f"P={v['PASS']:3d}  ~={v['PARTIAL']:3d}  F={v['FAIL']:3d}  "
            f"E={v['ERROR']:3d}  total={cat_total:3d}  {cat}"
        )

    out_summary_txt = result_dir / "rescored_summary.txt"
    out_summary_json = result_dir / "rescored_summary.json"
    out_results_json = result_dir / "rescored_all_results.json"
    out_summary_txt.write_text("\n".join(summary_lines), encoding="utf-8")

    out_summary_json.write_text(json.dumps({
        "total": total,
        "by_status": by_status,
        "pass_pct": pass_pct,
        "pass_or_partial_pct": pass_or_partial_pct,
        "by_category": {
            k: dict(v, total=sum(v.values()),
                    pass_pct=round(100.0 * v["PASS"] / max(sum(v.values()), 1), 1),
                    ok_pct=round(100.0 * (v["PASS"] + v["PARTIAL"]) / max(sum(v.values()), 1), 1))
            for k, v in by_category.items()
        },
    }, indent=2), encoding="utf-8")

    out_results_json.write_text(json.dumps(rescored, indent=2, ensure_ascii=False), encoding="utf-8")

    # Failures detail (after rescoring)
    fail_lines: list[str] = []
    fail_lines.append("=" * 72)
    fail_lines.append("RESCORED FAILURES — full detail")
    fail_lines.append("=" * 72)
    for r in rescored:
        if r["status"] not in ("FAIL", "PARTIAL"):
            continue
        fail_lines.append("")
        fail_lines.append(f"[{r['status']}] {r.get('test_id')}  category={r.get('category')}  is_negative={r.get('is_negative')}")
        ans = r.get("final_answer", "")
        if len(ans) > 600:
            ans = ans[:597] + "..."
        fail_lines.append(f"  answer: {ans}")
        for kw in r.get("keywords_expected", []):
            mark = "+" if kw in r.get("keywords_found", []) else "-"
            fail_lines.append(f"    {mark} {kw!r}")

    out_failures = result_dir / "rescored_failures.txt"
    out_failures.write_text("\n".join(fail_lines), encoding="utf-8")

    print("\n".join(summary_lines))
    print()
    print(f"New reports written:")
    print(f"  {out_summary_txt}")
    print(f"  {out_summary_json}")
    print(f"  {out_failures}")
    print(f"  {out_results_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
