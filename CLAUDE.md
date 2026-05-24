# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current State

The repo currently contains only `ETFTracker.md` — a project spec (in French) describing intended architecture. The Python modules and `positions.csv` referenced below do not yet exist; they need to be created. When implementing, follow the contracts in the Architecture section so the decoupling holds.

## Commands

```bash
# Always run from the project root
pip install -r requirements.txt                   # install deps
cp .env.example .env                              # then put your Ollama key in .env
python cli.py                                     # console portfolio
streamlit run dashboard.py                        # web dashboard (Portefeuille + Audit PEA tabs)

# PEA audit (reads OLLAMA_API_KEY from .env automatically)
python audit_cli.py samples/amundi_pea_monde_kid.pdf   # audit a single PDF
python audit_portfolio.py                              # batch-audit every ticker in positions.csv
python audit_recheck.py                                # force-refresh KIDs, diff vs cached verdicts (monthly)

# Docker (one-click run)
docker compose up -d web                               # http://localhost:8502
docker compose run --rm recheck                        # run a re-audit in the container

# Eval suite — run before any prompt/model change to catch regressions
python evals/run.py                                    # ~13 cases; ~$0.20 of Gemma calls on cold cache, free thereafter
```

`OLLAMA_API_KEY` is loaded from `.env` at import time by `ollama_client.py`
(via python-dotenv). `.env` is gitignored. The portfolio tracking features
(`cli.py`, Portefeuille tab) work without the key.

No test suite, linter, or build step is defined.

## Architecture

The project is deliberately split so the data source can be swapped without touching downstream code. Preserve this decoupling when adding features.

```
ETFTracker/
├── pyproject.toml              ← packaging metadata — declares the pea-audit library
├── LICENSE                     ← MIT
├── positions.csv               ← user holdings (ticker, nom, nb_parts, prix_achat_moyen)
├── .env                        ← OLLAMA_API_KEY=…, optional LANGFUSE_* (apps load it; library doesn't)
│
├── cli.py                      ← entry: console portfolio
├── audit_cli.py                ← entry: audit a single PDF
├── audit_portfolio.py          ← entry: batch-audit every ticker in positions.csv
├── audit_recheck.py            ← entry: monthly re-audit (force-refresh + diff)
├── dashboard.py                ← entry: Streamlit (tabs Portefeuille + Audit PEA)
│
├── Dockerfile, docker-compose.yml, .dockerignore, crontab.example
│
├── pea_audit/                  ← THE LIBRARY (publishable as pip install pea-audit)
│   ├── __init__.py             ← public API exports
│   ├── core.py                 ← audit_pdf, PeaVerdict, Citation, schema
│   ├── ticker.py               ← audit_ticker, TickerAuditResult, KID download
│   ├── cache.py                ← VerdictCache (opt-in, sha256-keyed)
│   ├── compare.py              ← compare_verdicts (HARD vs SOFT field selection)
│   ├── isin.py                 ← extract_isins + Luhn check-digit validator
│   ├── pdf.py                  ← pdf_to_images via pypdfium2
│   ├── prompts.py              ← versioned prompt loader (audit_v{N}.md)
│   ├── llm/
│   │   ├── base.py             ← VisionLLM Protocol (the contract)
│   │   └── ollama.py           ← OllamaCloudClient + tenacity retries + optional Langfuse
│   ├── sources/
│   │   ├── base.py             ← KIDSource dataclass + register_source registry
│   │   ├── amundi.py / bnp.py  ← built-in registrations
│   │   └── blackrock.py / vanguard.py ← URL helpers (no auto-registration)
│   ├── prompts/                ← shipped with the package
│   │   ├── audit_v1.md         ← historical (11/13 baseline, rollback target)
│   │   └── audit_v2.md         ← current (13/13)
│   └── py.typed
│
├── etftracker/                 ← APP-specific helpers (not part of the library)
│   ├── __init__.py
│   ├── portfolio.py            ← portfolio valuation, pure
│   └── data_source.py          ← yfinance wrapper for live prices
│
├── evals/                      ← regression suite (uses pea_audit directly)
│   ├── run.py
│   ├── cases/*.yaml
│   └── data/                   ← downloaded PDFs (gitignored)
│
├── samples/amundi_pea_monde_kid.pdf
│
└── cache/                      ← runtime, gitignored
    ├── audits/                 ← verdicts keyed by sha256(pdf_bytes)[:16]
    ├── kids/                   ← downloaded KIDs, one per ticker
    ├── alerts/{date}.md        ← from monthly re-audit
    └── audit_history.json
```

### Library vs. app split

- **`pea_audit/`** is the standalone library — meant to be `pip install`-able. Defines two protocols (`VisionLLM`, `KIDSource`) so users can swap LLM providers (Claude vision, OpenAI, etc.) or add issuers (Lyxor, SPDR…) without touching the core. **Does not load `.env`**, **does not write to disk** unless given a `VerdictCache`.
- **`etftracker/`** is *this app's* helper code — portfolio valuation + yfinance. Not part of the library.
- **Entry points at root** (`cli.py`, `audit_cli.py`, etc.) glue them together: load `.env`, construct `OllamaCloudClient` + `VerdictCache`, call into the library. Always invoked from the project root so relative paths (`cache/`, `positions.csv`) resolve correctly.

### Extension points (use the library from your own code)

```python
from pathlib import Path
from pea_audit import audit_pdf, VerdictCache
from pea_audit.llm import OllamaCloudClient
from pea_audit.sources import register_source, KIDSource

# Add your own KID source for a ticker the library doesn't ship.
register_source(KIDSource(
    ticker="LYXOR.PA", isin="FR0010411884",
    url="https://...lyxor.kid.pdf", issuer="Lyxor",
))

llm = OllamaCloudClient(api_key="sk-...")
cache = VerdictCache(Path("./my-cache"))
verdict = audit_pdf("kid.pdf", llm=llm, cache=cache)
```

**Two decoupling contracts to preserve:**

1. `data_source.py` returns `dict {ticker: prix}`. Swap yfinance → Alpha Vantage / Marketstack without touching `portfolio.py`, `cli.py`, or `dashboard.py`.

2. `ollama_client.analyze_images(images, prompt, schema) -> dict` is the only place the Ollama SDK is imported. Swap Ollama Cloud → Claude vision / OpenAI / Gemini API by editing only this file; `pea_audit.py` stays unchanged.

`portfolio.py` and `pea_audit.py` should remain pure (no network, no Streamlit imports) so both CLI and Streamlit can consume them identically.

## Domain Notes

- **Audience:** long-term ETF investors holding through a **French PEA** (e.g. Trade Republic PEA from France). PEA-eligibility is the hard constraint — only synthetic UCITS replicating non-EU indexes (or physical EEA-equity ETFs) qualify. Example tickers in `positions.csv` (`EWLD.PA`, `PAEEM.PA`, `ESE.PA`, `PANX.PA`) reflect commonly PEA-eligible funds, but **eligibility can change** when issuers restructure — verify on the KIID/DIC.
- Quotes are delayed ~15 min via Yahoo Finance — this is intentional, not a bug. Do not add real-time/trading features.
- **Tickers** use Yahoo Finance suffixes by exchange: `.PA` (Paris) is the default for PEA-eligible funds. `.AS` / `.DE` / `.MI` exist but most PEA wrappers are listed in Paris.
- `yfinance` scrapes public Yahoo data and breaks periodically. If it fails, the intended fix is to wire a keyed API inside `data_source.py` — not to add fallback logic in `portfolio.py`.
- Tool is for personal tracking, not investment advice.

## LLM client (Ollama + Langfuse + tenacity)

`pea_audit/llm/ollama.py` — `OllamaCloudClient` is the only library module that imports the Ollama SDK. It implements the `VisionLLM` protocol from `pea_audit/llm/base.py`, so an app can plug in Claude, OpenAI, etc. by implementing the same protocol.

- **Retries** via `tenacity` — 3 attempts with exponential backoff (1s → 4s → 16s) on transient errors only (`ConnectionError`, `TimeoutError`, Ollama 5xx). 4xx and JSON parse errors do NOT retry — they won't self-resolve.
- **Observability** via Langfuse — opt-in via `enable_langfuse()` (apps call this after `load_dotenv()`). When the env vars are present, every `analyze_images` call is traced with model, input messages, output, and token usage. Silent no-op otherwise (no auth-error spam, no overhead).

The library NEVER calls `load_dotenv()` itself — apps are responsible. The `OllamaCloudClient` constructor requires an explicit `api_key` parameter.

To enable Langfuse: create a project at https://cloud.langfuse.com, drop `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` in `.env`, restart. `LANGFUSE_BASE_URL` is accepted as an alias for the canonical `LANGFUSE_HOST` (bridged in `enable_langfuse()`).

## Prompt versioning

Prompts live in `pea_audit/prompts/audit_v{N}.md` — markdown files with `## System prompt` and `## User prompt` sections — and are loaded by `pea_audit.prompts.load_prompt(version)`. The default active version is `pea_audit.core.DEFAULT_PROMPT_VERSION` (`"v2"`); callers can override via `audit_pdf(..., prompt_version="v3")`.

**Workflow for a prompt change:**

1. Copy `prompts/audit_v{N}.md` → `prompts/audit_v{N+1}.md`, edit it. Keep `v{N}` as a rollback target.
2. Bump `DEFAULT_PROMPT_VERSION = "v{N+1}"` in `pea_audit/core.py` (or pass `prompt_version=` per call).
3. `rm -rf cache/audits/` (cache is byte-keyed on PDF, not prompt — flush forces re-audit).
4. `python evals/run.py` — must stay at 13/13 (or document the new baseline).

**Rollback:** change `PROMPT_VERSION` to the previous version, bust cache, done. No code touched.

## Eval baseline

`evals/cases/*.yaml` defines regression cases; `evals/run.py` runs them and reports pass rate per category. Run before any prompt/model change to catch silent regressions.

**Last known baseline (Gemma 4 31b-cloud, 2026-05):**

| Category | Pass | Cases |
|---|---|---|
| `eligible_synthetic_swap` | 7/7 | Amundi PEA Monde, PEA EM, PEA S&P 500, PEA Nasdaq-100 (FR0011871110), PEA US Tech (current PANX), MSCI World Swap II, EWLD LU; BNP Easy S&P 500 |
| `ineligible_physical_non_eea` | 6/6 | iShares Core S&P 500, MSCI World, MSCI EM IMI, Nasdaq 100; Vanguard S&P 500, FTSE All-World |
| **Total** | **13/13 (100%)** | |

**History of the prompt that gets this baseline.** The first version of the system prompt got 11/13 — iShares Core S&P 500 and Nasdaq 100 returned `replication: unknown` because the model was being conservative when the KID didn't print "physique" verbatim. A targeted prompt addition closed the gap: explicit guidance that "no swap/synthetic language + an index = physical replication by default" (the standard for iShares Core, Vanguard, Lyxor Core, SPDR Core). The eval verified the change didn't regress any of the 11 previously-passing cases. **Always run `python evals/run.py` after any prompt or model change.**

**To add new cases:** drop a `evals/cases/{slug}.yaml` with `pdf_url`, `expected.eligible/replication/isin` (hard), and `expected_contains.issuer/underlying_index` (soft substring). Run `python evals/run.py`.

## Monthly re-audit

`audit_recheck.py` force-refreshes every KID, re-audits, and compares against the previous verdict stored in `cache/audit_history.json`. Material changes are written to `cache/alerts/{YYYY-MM-DD}.md` and the script exits non-zero so cron `MAILTO` fires.

**Important:** `compare_verdicts` only diffs the *hard* fields — `eligible`, `replication`, `isin`. The *soft* fields (`issuer`, `underlying_index`) are free-text and drift between LLM runs ("BNP Paribas" vs "BNP Paribas Asset Management" are the same thing), so they'd cause false-positive alerts every month. Pass `include_soft=True` to `compare_verdicts` when debugging, never in the cron.

Scheduling: see `crontab.example`. The Docker variant is cleanest because it isolates the Python environment: `0 9 1 * * cd PROJECT_DIR && docker compose run --rm recheck`.

## PEA Audit — known limitations

- **ISIN handling (mitigated).** Gemma 4 vision sometimes misreads the 12-char ISIN. `pea_audit.extract_isins()` extracts ISIN candidates from `pypdfium2`'s text layer with Luhn check-digit validation, injects them into the prompt as a hint, and `_reconcile_isin()` overrides Gemma's vision-read with the deterministic value if it doesn't match an extracted candidate. Fallback: if the PDF has no text layer (scanned image), reconciliation is a no-op and Gemma's vision read is kept.
- **Cache invalidation.** Cached by `sha256(pdf_bytes)[:16]`. If the issuer reissues the same KID with a new date, the hash differs and we re-audit. To force re-audit on the same PDF: delete the file under `cache/audits/`. To force re-download of a KID: delete the file under `cache/kids/`.
- **No deterministic eligibility check.** The eligibility verdict itself is LLM-judged. Always cross-check against the actual DIC for any holding you act on.
- **`kid_sources.py` is a static map.** It must be edited by hand when adding a new ticker. Auto-discovery (search the issuer's site for the KID URL) is intentionally not implemented — the issuer sites are JS-rendered and scraping is brittle. Adding a ticker is cheap; mis-attributing a KID to the wrong ticker is dangerous. Always verify by curl-probing the URL and reading the first page of the PDF.

## Language

Project documentation and the spec are in French. Match existing language when editing user-facing strings (CLI output, dashboard labels, README).
