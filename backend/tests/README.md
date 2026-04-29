# Tests — overview and how to run

This directory contains three layers of tests, ordered from cheapest (no
credentials, milliseconds) to most expensive (real Azure calls, money + time).

| Layer | What it tests | Needs Azure? | Time | Cost |
|---|---|---|---|---|
| Unit + mocked integration (existing) | Pure-logic helpers, mocked pipeline | No | ~2 sec | $0 |
| Golden-set keyword validator | Expected keywords are verbatim in PDFs | No | ~5 sec | $0 |
| Golden-set runner (this file) | End-to-end backend behaviour | **Yes** | ~10-20 min | ~$0.50-2.00 |

---

## 1. Unit + mocked integration (always run)

Run any time you change code:

```
cd backend
python -m pytest tests/unit/ tests/integration/ -q
```

Should report `127 passed, 4 skipped` in ~2 seconds. Zero Azure calls.

---

## 2. Golden-set keyword validator (run after editing the test set)

Validates that every `expected_keywords` phrase in `golden_set.json` actually
appears verbatim in the cited PDF. Catches ChatGPT hallucinations before you
spend money on a real test run.

**Pre-req:** drop the three PDFs into `tests/fixtures/manuals/` (gitignored —
each developer keeps their own local copy).

```
cd backend
python -m tests.validate_golden_set
```

Output written to:
- `tests/golden_validation_report.txt` — human-readable
- `tests/golden_validation_report.json` — machine-readable

If you see misses, either:
- Edit the offending entries in `golden_set.json` to use the exact PDF wording, OR
- Ask ChatGPT to regenerate just those test IDs with verbatim phrases

A run with the current 200-test set finds **601 of 605 keywords verbatim
(99.3%)**. Four minor paraphrases are flagged in the report — they're low-
priority quality issues, not blockers.

---

## 3. Golden-set runner — RUN ON OFFICE LAPTOP ONLY

Hits the live backend with all 200 test cases and produces a pass/fail report
per category. **This is the production-readiness measurement.**

### Pre-flight checklist

1. **Confirm IT/security policy.** This makes real calls to your PSEG Azure
   resources from whatever machine you run it on. Run it on your office
   laptop with the corporate `.env` already in place — same machine you'd
   normally develop on.

2. **Confirm `.env` is present** at `backend/.env` with all required Azure
   credentials.

3. **Confirm your backend builds cleanly:**
   ```
   cd backend
   python -m pytest tests/unit/ tests/integration/ -q
   ```
   should still show `127 passed, 4 skipped`.

4. **Start the backend in one terminal:**
   ```
   cd backend
   uvicorn main:app --reload
   ```
   Wait until you see `Uvicorn running on http://127.0.0.1:8000`.

### Smoke test (do this first)

Run only 5 tests to confirm the runner works end-to-end before committing
to a full 200-test run:

```
cd backend
python -m tests.run_golden_set --limit 5
```

Expected output:
- 5 lines, each ending in PASS / PARTIAL / FAIL / ERROR
- A summary table at the end
- A new folder under `tests/golden_results/<timestamp>/` with the report

If the smoke test ERRORs on every case, the backend isn't reachable or
the `/chat` endpoint signature changed. Fix that before running the full
suite.

### Full run

```
cd backend
python -m tests.run_golden_set
```

This sequentially runs all 200 cases (some are multi-turn, so total HTTP
requests are ~340). At default `concurrency=1` it takes ~15-25 minutes
depending on Azure latency. Estimated cost: **$0.50-2.00**.

For faster runs, raise concurrency carefully — Azure OpenAI rate limits
will throttle aggressive concurrency:

```
python -m tests.run_golden_set --concurrency 4
```

### Other useful flags

```
# Run just one category
python -m tests.run_golden_set --category single_direct_factual

# Run specific test IDs
python -m tests.run_golden_set --ids T001,T042,T146

# Point at a different host (e.g. deployed instance)
python -m tests.run_golden_set --base-url https://my-app.azurewebsites.us
```

### Reading the output

After every run, `tests/golden_results/<timestamp>/` contains:
- `summary.txt` — high-level pass rates by category
- `summary.json` — same data, structured (use to diff across runs)
- `failures.txt` — every failing test with full chat history and missing keywords
- `all_results.json` — raw per-test data for ad-hoc analysis

**Compare runs over time:**
```
diff tests/golden_results/2026-04-28_*/summary.txt \
     tests/golden_results/2026-05-05_*/summary.txt
```

The pass-rate-per-category number is what you optimize. Pick the category
with the lowest pass rate as the next ticket.

---

## Layout

```
backend/tests/
├── README.md                          ← you are here
├── conftest.py                        ← pytest config (dummy env vars for unit tests)
├── golden_set.json                    ← 200 test cases (committed)
├── validate_golden_set.py             ← keyword-vs-PDF validator (no Azure needed)
├── run_golden_set.py                  ← live-backend test runner (Azure required)
├── golden_validation_report.txt       ← latest validator output (overwritten each run)
├── golden_validation_report.json      ← machine-readable version
├── golden_results/                    ← per-run reports (gitignored)
│   └── <timestamp>/
│       ├── summary.txt
│       ├── summary.json
│       ├── failures.txt
│       └── all_results.json
├── fixtures/
│   └── manuals/                       ← PDFs (gitignored)
│       ├── ED-DC-IRE.pdf
│       ├── gas_appliances_gas_piping.pdf
│       └── pepp_manual_new.pdf
├── unit/                              ← pure-logic tests (existing)
│   ├── test_query_rewriter_standalone.py
│   └── test_query_rewriter_validator.py
└── integration/                       ← mocked pipeline tests (existing)
    ├── test_long_distance_anaphora.py
    ├── test_pipeline_fallback_retrieval.py
    ├── test_rewrite_query_with_mocked_llm.py
    └── test_topic_switch_e2e.py
```

---

## Discipline going forward

1. **Run unit + integration tests on every commit.** ~2 seconds, $0.
2. **Run keyword validator any time you edit `golden_set.json`.** ~5 seconds, $0.
3. **Run the live runner before every production deploy.** ~15-25 min, ~$1.
4. **Save every run's `summary.json` so trends are visible over weeks.**

Done correctly, this loop transforms "we think the chatbot is at 70-90%"
into "we measured 84.5% pass on 2026-04-28 and 86.8% on 2026-05-05; the
fix moved the needle".
