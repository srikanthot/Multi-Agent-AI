# Local PDF manuals — DO NOT COMMIT

This folder holds the source PDFs that the golden-set keyword validator and
the optional retrieval ground-truth tooling read from disk. The PDFs are
**deliberately gitignored** — see `.gitignore` at the repo root.

## Why local-only

1. PSEG technical manuals are confidential — they should not live in git history.
2. PDFs are large binary files (10-20 MB each); committing them bloats every
   future clone and gives no version-control benefit (git cannot diff PDFs).
3. Each developer either pulls fresh copies from the official PSEG document
   store or copies them from a teammate.

## What goes here

The current `tests/golden_set.json` references these three files by exact
filename. Drop them in this folder with the same names:

- `ED-DC-IRE.pdf` — Electric Distribution / Installation Requirements for Electric service
- `gas_appliances_gas_piping.pdf` — Gas Appliances and Gas Piping
- `pepp_manual_new.pdf` — PEPP / 26.4 kV Customer Substation manual

If you change the filenames, update the `manual_a_name` / `manual_b_name` /
`manual_c_name` fields at the top of `tests/golden_set.json` to match.

## Verifying the PDFs are in place

After dropping the three files here, run:

```
ls backend/tests/fixtures/manuals/
```

You should see all three `.pdf` files plus this `README.md`.

The keyword-validator script (will be added next) will fail loudly if any
referenced manual is missing, with a clear "expected file not found" message —
no silent test corruption.
