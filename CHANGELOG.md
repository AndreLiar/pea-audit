# Changelog

All notable changes to `pea-audit` are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is [SemVer](https://semver.org/).

## [0.2.1] — 2026-05-24

Docs-only patch. No code changes — bumps the README that ships with the wheel so the PyPI project page reflects the latest copy.

### Changed
- Absolute GitHub raw URL for the dashboard screenshot (was relative — broke PyPI rendering)
- Quickstart includes an async snippet (`aaudit_pdf` + `AsyncOllamaCloudClient` + `asyncio.gather`)
- Section reorder: *Why → Install → Quickstart* first; "Not a developer?" moved next to the reference-app section
- References to `examples/` directory + `cp positions.csv.example positions.csv` step
- New "Known limitations" section surfacing the LLM-variance caveat that was buried in CHANGELOG
- "Latest:" line near the title + CHANGELOG link in footer

## [0.2.0] — 2026-05-24

Senior-review fixes from the cold-reader pass. No breaking changes for ordinary library users (Enums subclass `str`, so `verdict.eligible == "yes"` still works), but the cache key format changed — see "Breaking" below.

### Added
- **Async API:** `aaudit_pdf` + `aaudit_ticker` + `AsyncOllamaCloudClient` + `AsyncVisionLLM` protocol. Use these in FastAPI handlers, batch processing, or anywhere blocking on the LLM would stall the event loop.
- **Type narrowing:** `Eligible`, `Confidence`, `Replication` exported as `str`-subclass `Enum`s. IDE autocomplete + typo protection at construction time (`PeaVerdict(eligible="maybe", ...)` now raises `ValueError`).
- **Prompt version in cache key:** `VerdictCache` takes an optional `prompt_version` arg in `get`/`put`/`get_by_path`/`cache_key`. Audits done under `v2` no longer get served to `v3` callers.
- **SSRF guard on `_download_kid`:** rejects non-http(s) schemes, enforces a 20 MB streaming size cap, verifies `Content-Type` looks like PDF before writing to disk. Matters because `KIDSource.url` is user-registrable.
- **LLM-touching unit tests** via a `FakeVisionLLM` (no real LLM calls). Covers `audit_pdf` cache hit/miss, ISIN reconciliation, citation-shape variance, error propagation, prompt-version cache invalidation, and 6 `_download_kid` paths (scheme rejection, MIME rejection, oversize, force-refresh, cache passthrough). +23 tests, total now **51**.
- **`examples/` directory:** 5 runnable demos (basic audit, audit-by-ticker, custom LLM, custom KID source, async batch) + `examples/README.md`.
- **Eval baseline snapshot + comparison:** `python evals/run.py --save-baseline` persists the current pass set; subsequent runs compare and exit `2` on regression (CI-friendly gate for prompt/model changes).
- **GitHub release for v0.1.0** + repo topics + homepage URL set.

### Changed
- **`requirements.txt` and `pyproject.toml`** now declare `fastapi[standard]` + `python-multipart` (used by the FastAPI service).
- Switched `pypdfium2` text extraction from `get_text_range()` (deprecated) to `get_text_bounded()`.

### Breaking
- **Cache key format changed.** Verdicts cached under `0.1.x` use `sha256(pdf_bytes)`; `0.2.0` uses `sha256(pdf_bytes + b"|" + prompt_version.encode())`. Old cache files are simply ignored (orphaned) — first re-audit repopulates the cache under the new key. If you want to reclaim disk, `rm -rf cache/audits/` before upgrading.

### Known LLM variance (no code fix)
Across repeated runs with the same prompt + model + PDFs, the eval pass rate oscillates between 11/13 and 13/13. The two flaky cases (iShares Core S&P 500 + iShares Nasdaq 100) sometimes return `replication: unknown` instead of `physical` — Gemma's `summary_fr` still reasons correctly ("il s'agit d'une réplication physique"), only the structured field wavers. The eligibility verdict is stable in all observed runs. v0.3 candidate fix: multi-sample voting (run N=3, take majority).

## [0.1.0] — 2026-05-24

Initial release. Published to PyPI: <https://pypi.org/project/pea-audit/0.1.0/>.

### Added
- `audit_pdf(pdf, llm, cache=None)` — main API for auditing a single KID/DIC PDF
- `audit_ticker(ticker, llm, kid_dir, cache=None)` — convenience for audit-by-ticker, downloads KID via the source registry
- `PeaVerdict`, `Citation`, `TickerAuditResult` dataclasses
- `VerdictCache(cache_dir)` — opt-in file-based cache keyed by `sha256(pdf_bytes)`
- `compare_verdicts(old, new, include_soft=False)` — hard-vs-soft field diff for re-audit detection
- `extract_isins(pdf_path)` + `isin_check_digit_valid(isin)` — Luhn-validated ISIN extraction from PDF text layer
- `VisionLLM` protocol — pluggable model backend
- `OllamaCloudClient` — default implementation (Gemma 4 31b-cloud) with `tenacity` retries on transient errors
- Optional Langfuse observability via `enable_langfuse()` (no-op when keys absent)
- `KIDSource` + `register_source` — pluggable issuer registry
- Built-in sources: Amundi (URL pattern), BNP Paribas (per-fund); helpers for BlackRock/iShares + Vanguard
- Versioned prompts under `pea_audit/prompts/audit_v{N}.md`; v2 ships as the default
- 13-case eval suite (`evals/`) covering eligible synthetic-swap + ineligible physical non-EEA across Amundi/BNP/iShares/Vanguard — **13/13 passing baseline**
- 28 unit tests (`tests/`) for ISIN, compare_verdicts, prompt loader — pure-function, no LLM
- MIT license
