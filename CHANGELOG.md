# Changelog

All notable changes to `pea-audit` are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is [SemVer](https://semver.org/).

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
