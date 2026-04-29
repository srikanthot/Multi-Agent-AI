"""Run the 200-test golden set against the live backend and produce a report.

USAGE
-----
On your office laptop (where .env has real Azure credentials):

    cd backend
    python -m tests.run_golden_set

Optional flags:
    --base-url http://localhost:8000   (default: http://localhost:8000)
    --limit 20                          (run only first N tests; useful for smoke tests)
    --category single_direct_factual    (run only this category)
    --concurrency 4                     (parallel requests; default: 1)
    --skip-validator                    (don't pre-check keywords against PDFs)

The runner DOES NOT START THE BACKEND. Make sure your backend is running first:
    cd backend
    uvicorn main:app --reload

OUTPUT
------
Writes timestamped reports to backend/tests/golden_results/<timestamp>/:
    summary.txt      — human-readable per-category pass/fail
    summary.json     — machine-readable; diff against prior runs
    failures.txt     — full detail of every failing test (question, expected
                       keywords, actual answer, retrieved chunks if available)

SCORING
-------
For positive cases (should_answer=true / not negative):
    PASS  if answer is non-empty AND ALL expected_keywords are in the answer
    PARTIAL if at least one expected_keyword is in the answer
    FAIL  if no expected_keywords are in the answer, or canned no-evidence msg returned

For negative cases (should_answer=false / category contains "negative" or "vague"):
    PASS  if the answer is the canned "I don't have enough evidence" or asks for
          clarification
    FAIL  if the answer attempts to answer with content
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

# Re-use the normalizer from the validator so PDF text and chatbot text are
# normalized identically — same encoding fixes, same case folding.
sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.validate_golden_set import normalize  # noqa: E402


# ---------------------------------------------------------------------------
# Paths / config
# ---------------------------------------------------------------------------

HERE = Path(__file__).parent
GOLDEN = HERE / "golden_set.json"
RESULTS_ROOT = HERE / "golden_results"

DEFAULT_BASE_URL = "http://localhost:8000"
CHAT_ENDPOINT = "/chat"
CHAT_STREAM_ENDPOINT = "/chat/stream"

# Markers that indicate the bot refused to answer / had no evidence
_NO_EVIDENCE_MARKERS = [
    "i don't have enough evidence",
    "i do not have enough evidence",
    "could you provide more detail",
    "could you be more specific",
    "i cannot find",
    "i can't find",
    "the manuals do not",
    "not covered in the",
    "outside the scope",
]

# Markers that indicate the bot asked for clarification (good for vague queries)
_CLARIFICATION_MARKERS = [
    "could you provide",
    "could you clarify",
    "could you specify",
    "what equipment",
    "which equipment",
    "what voltage",
    "which voltage",
    "more specific",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TurnSpec:
    role: str
    content: Optional[str] = None
    expected_keywords: list[str] = field(default_factory=list)
    expected_manual: Optional[str] = None


@dataclass
class TestSpec:
    """Normalized form of a golden_set.json test entry — handles both schemas."""
    id: str
    category: str
    is_negative: bool
    questions: list[str]                    # all user messages, in order
    expected_keywords: list[str]            # for the FINAL user message (positive cases)
    expected_manual: Optional[str]          # cited source for the final answer
    raw_test: dict                          # the original entry, for debugging


@dataclass
class TestResult:
    test_id: str
    category: str
    status: str                              # PASS / PARTIAL / FAIL / ERROR
    is_negative: bool
    final_answer: str
    keywords_expected: list[str]
    keywords_found: list[str]
    keywords_missing: list[str]
    chat_history: list[dict]
    error: Optional[str] = None
    elapsed_ms: int = 0
    citations: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Schema normalization
# ---------------------------------------------------------------------------

NEGATIVE_CATEGORY_HINTS = ("negative", "vague_or_underspecified")


def _is_negative_test(test: dict) -> bool:
    cat = (test.get("category") or "").lower()
    if test.get("should_answer") is False:
        return True
    return any(h in cat for h in NEGATIVE_CATEGORY_HINTS)


def normalize_test(test: dict) -> TestSpec:
    """Convert a raw test dict (either schema) into a TestSpec."""
    is_negative = _is_negative_test(test)

    # Single-turn cases
    if "question" in test and not test.get("turns"):
        return TestSpec(
            id=test["id"],
            category=test.get("category", "unknown"),
            is_negative=is_negative,
            questions=[test["question"]],
            expected_keywords=test.get("expected_keywords") or [],
            expected_manual=test.get("expected_manual") or test.get("manual") or (
                (test.get("manuals") or [None])[0]
            ),
            raw_test=test,
        )

    # Multi-turn cases — build the user-message sequence and pick out the
    # expected keywords for the FINAL user turn (which is what the test
    # actually scores).
    questions: list[str] = []
    final_keywords: list[str] = []
    final_manual: Optional[str] = None

    for turn in test.get("turns") or []:
        if turn.get("role") == "user":
            content = turn.get("content")
            if content:
                questions.append(content)
            # Some batch-2 cases attach expected_keywords to the user turn itself
            if turn.get("expected_keywords"):
                final_keywords = list(turn["expected_keywords"])
            if turn.get("expected_manual"):
                final_manual = turn["expected_manual"]

    # Top-level expected_keywords / *_for_q2 / *_for_q3 / *_for_final win
    # over what we picked from the last user turn (batch-1 cases).
    for key in ("expected_keywords_for_final", "expected_keywords_for_q3",
                "expected_keywords_for_q2", "expected_keywords"):
        if test.get(key):
            final_keywords = list(test[key])
            break
    for key in ("expected_manual_for_final", "expected_manual_for_q3",
                "expected_manual_for_q2", "expected_manual"):
        if test.get(key):
            final_manual = test[key]
            break
    if not final_manual:
        manuals = test.get("manuals") or []
        if len(manuals) == 1:
            final_manual = manuals[0]
        elif manuals:
            final_manual = manuals[-1]  # cross-manual pivot — Q2 likely in last

    return TestSpec(
        id=test["id"],
        category=test.get("category", "unknown"),
        is_negative=is_negative,
        questions=questions,
        expected_keywords=final_keywords,
        expected_manual=final_manual,
        raw_test=test,
    )


# ---------------------------------------------------------------------------
# Backend interaction
# ---------------------------------------------------------------------------

async def call_chat_endpoint(
    client: httpx.AsyncClient,
    base_url: str,
    question: str,
    session_id: Optional[str],
) -> dict:
    """POST a single question to the backend's non-streaming /chat endpoint.

    Returns dict with: answer, session_id, citations.
    """
    payload: dict[str, Any] = {"question": question}
    if session_id:
        payload["session_id"] = session_id
    resp = await client.post(
        f"{base_url}{CHAT_ENDPOINT}",
        json=payload,
        timeout=httpx.Timeout(180.0),
    )
    resp.raise_for_status()
    return resp.json()


async def run_test(
    spec: TestSpec,
    client: httpx.AsyncClient,
    base_url: str,
) -> TestResult:
    """Run all turns of a test sequentially, score the final answer."""
    start = time.monotonic()
    session_id: Optional[str] = None
    history: list[dict] = []
    final_answer: str = ""
    citations: list[dict] = []
    error: Optional[str] = None

    try:
        for q in spec.questions:
            response = await call_chat_endpoint(client, base_url, q, session_id)
            session_id = response.get("session_id") or response.get("thread_id") or session_id
            answer = response.get("answer", "")
            history.append({"role": "user", "content": q})
            history.append({"role": "assistant", "content": answer})
            final_answer = answer
            citations = response.get("citations") or []
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    elapsed_ms = int((time.monotonic() - start) * 1000)

    # Score
    norm_answer = normalize(final_answer)
    is_no_evidence = any(m in norm_answer for m in (normalize(x) for x in _NO_EVIDENCE_MARKERS))
    is_clarification = any(m in norm_answer for m in (normalize(x) for x in _CLARIFICATION_MARKERS))

    keywords_found: list[str] = []
    keywords_missing: list[str] = []
    for kw in spec.expected_keywords:
        if normalize(kw) in norm_answer:
            keywords_found.append(kw)
        else:
            keywords_missing.append(kw)

    if error:
        status = "ERROR"
    elif spec.is_negative:
        # Negative tests pass when bot refuses or asks for clarification
        status = "PASS" if (is_no_evidence or is_clarification) else "FAIL"
    else:
        if not final_answer.strip():
            status = "FAIL"
        elif is_no_evidence and not keywords_found:
            status = "FAIL"
        elif keywords_missing == [] and keywords_found:
            status = "PASS"
        elif keywords_found:
            status = "PARTIAL"
        else:
            status = "FAIL"

    return TestResult(
        test_id=spec.id,
        category=spec.category,
        status=status,
        is_negative=spec.is_negative,
        final_answer=final_answer,
        keywords_expected=spec.expected_keywords,
        keywords_found=keywords_found,
        keywords_missing=keywords_missing,
        chat_history=history,
        error=error,
        elapsed_ms=elapsed_ms,
        citations=citations,
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

async def run_all(
    specs: list[TestSpec],
    base_url: str,
    concurrency: int,
) -> list[TestResult]:
    """Run all tests with bounded concurrency."""
    sem = asyncio.Semaphore(concurrency)
    results: list[TestResult] = []

    async with httpx.AsyncClient() as client:
        async def _bounded(spec: TestSpec, idx: int) -> None:
            async with sem:
                print(f"[{idx + 1:>3}/{len(specs)}] {spec.id}  {spec.category}", flush=True)
                r = await run_test(spec, client, base_url)
                results.append(r)
                marker = {"PASS": "✓", "PARTIAL": "~", "FAIL": "✗", "ERROR": "!"}.get(r.status, "?")
                print(f"    {marker} {r.status:7s}  ({r.elapsed_ms} ms)", flush=True)

        tasks = [_bounded(s, i) for i, s in enumerate(specs)]
        await asyncio.gather(*tasks)

    # Sort results by spec order (concurrency may have completed them in any order)
    spec_index = {s.id: i for i, s in enumerate(specs)}
    results.sort(key=lambda r: spec_index.get(r.test_id, 1e9))
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def write_reports(results: list[TestResult], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Summary stats
    by_category: dict[str, dict] = {}
    by_status: dict[str, int] = {"PASS": 0, "PARTIAL": 0, "FAIL": 0, "ERROR": 0}
    for r in results:
        cat = r.category
        b = by_category.setdefault(cat, {"PASS": 0, "PARTIAL": 0, "FAIL": 0, "ERROR": 0})
        b[r.status] = b.get(r.status, 0) + 1
        by_status[r.status] = by_status.get(r.status, 0) + 1

    total = len(results)
    pass_pct = round(100.0 * by_status["PASS"] / max(total, 1), 1)
    partial_pct = round(100.0 * by_status["PARTIAL"] / max(total, 1), 1)
    fail_pct = round(100.0 * by_status["FAIL"] / max(total, 1), 1)
    error_pct = round(100.0 * by_status["ERROR"] / max(total, 1), 1)

    # Text summary
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("GOLDEN SET — LIVE BACKEND TEST RUN")
    lines.append("=" * 72)
    lines.append(f"Timestamp:  {out_dir.name}")
    lines.append(f"Total:      {total}")
    lines.append(f"PASS:       {by_status['PASS']} ({pass_pct}%)")
    lines.append(f"PARTIAL:    {by_status['PARTIAL']} ({partial_pct}%)")
    lines.append(f"FAIL:       {by_status['FAIL']} ({fail_pct}%)")
    lines.append(f"ERROR:      {by_status['ERROR']} ({error_pct}%)")
    lines.append("")
    lines.append("BY CATEGORY")
    lines.append("-" * 72)
    for cat in sorted(by_category.keys()):
        v = by_category[cat]
        cat_total = sum(v.values())
        cat_pass_pct = round(100.0 * v["PASS"] / max(cat_total, 1), 1)
        lines.append(
            f"  {cat_pass_pct:5.1f}%  pass={v['PASS']:3d}  partial={v['PARTIAL']:3d}  "
            f"fail={v['FAIL']:3d}  err={v['ERROR']:3d}  total={cat_total:3d}  {cat}"
        )
    (out_dir / "summary.txt").write_text("\n".join(lines), encoding="utf-8")

    # JSON summary (for diffing across runs)
    summary_json = {
        "timestamp": out_dir.name,
        "total": total,
        "by_status": by_status,
        "pass_pct": pass_pct,
        "by_category": {k: dict(v, total=sum(v.values())) for k, v in by_category.items()},
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Failures detail
    fail_lines: list[str] = []
    fail_lines.append("=" * 72)
    fail_lines.append("FAILURES — full detail")
    fail_lines.append("=" * 72)
    for r in results:
        if r.status not in ("FAIL", "ERROR", "PARTIAL"):
            continue
        fail_lines.append("")
        fail_lines.append(f"[{r.status}] {r.test_id}  category={r.category}  is_negative={r.is_negative}")
        fail_lines.append(f"  elapsed: {r.elapsed_ms} ms")
        if r.error:
            fail_lines.append(f"  ERROR: {r.error}")
        fail_lines.append(f"  chat history:")
        for msg in r.chat_history:
            content = msg["content"]
            if len(content) > 400:
                content = content[:397] + "..."
            fail_lines.append(f"    {msg['role']}: {content}")
        fail_lines.append(f"  expected keywords ({len(r.keywords_expected)}):")
        for kw in r.keywords_expected:
            mark = "+" if kw in r.keywords_found else "-"
            fail_lines.append(f"    {mark} {kw!r}")
    (out_dir / "failures.txt").write_text("\n".join(fail_lines), encoding="utf-8")

    # Raw all-results JSON
    (out_dir / "all_results.json").write_text(
        json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Print summary to stdout
    print()
    print("\n".join(lines))
    print()
    print(f"Reports written to: {out_dir}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run golden_set.json against the live backend.")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL,
                   help="Backend base URL (default: %(default)s)")
    p.add_argument("--limit", type=int, default=None,
                   help="Run only first N tests (for smoke testing)")
    p.add_argument("--category", default=None,
                   help="Run only tests in this category")
    p.add_argument("--ids", default=None,
                   help="Comma-separated list of specific test IDs to run, e.g. T001,T042")
    p.add_argument("--concurrency", type=int, default=1,
                   help="Parallel requests (default: 1; raise carefully)")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if not GOLDEN.exists():
        print(f"ERROR: golden_set.json not found at {GOLDEN}", file=sys.stderr)
        return 2

    with open(GOLDEN, "r", encoding="utf-8") as f:
        gold = json.load(f)

    # Convert all 200 entries into normalized TestSpec objects
    specs = [normalize_test(t) for t in gold["tests"]]

    # Filtering
    if args.category:
        specs = [s for s in specs if s.category == args.category]
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",") if x.strip()}
        specs = [s for s in specs if s.id in wanted]
    if args.limit:
        specs = specs[: args.limit]

    if not specs:
        print("No tests selected after filtering.", file=sys.stderr)
        return 2

    print(f"Running {len(specs)} tests against {args.base_url} with concurrency={args.concurrency}")
    print()

    # Quick health check
    try:
        with httpx.Client(timeout=10) as c:
            r = c.get(args.base_url + "/health")
            print(f"Health check: HTTP {r.status_code}")
    except Exception as exc:
        print(f"WARNING: health check failed: {exc}")
        print("(continuing anyway — the /health endpoint may not exist)")
    print()

    results = asyncio.run(run_all(specs, args.base_url, args.concurrency))

    # Write reports under tests/golden_results/<timestamp>/
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_dir = RESULTS_ROOT / timestamp
    write_reports(results, out_dir)

    # Exit code = 1 if any failures, 0 if all pass
    failures = sum(1 for r in results if r.status in ("FAIL", "ERROR"))
    return 1 if failures > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
