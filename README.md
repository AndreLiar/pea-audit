# pea-audit

[![PyPI](https://img.shields.io/pypi/v/pea-audit.svg)](https://pypi.org/project/pea-audit/)
[![Python](https://img.shields.io/pypi/pyversions/pea-audit.svg)](https://pypi.org/project/pea-audit/)
[![CI](https://github.com/AndreLiar/pea-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/AndreLiar/pea-audit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Audit French **PEA** (Plan d'Épargne en Actions) eligibility of ETFs by reading their **KID** (Key Information Document) with a vision LLM. Tells you whether a fund is actually eligible for a French PEA account — with verbatim citations from the document.

```
$ python audit_cli.py samples/amundi_pea_monde_kid.pdf
📄 Audit de : samples/amundi_pea_monde_kid.pdf

  ✅ ÉLIGIBLE PEA    (confiance : high)

  Émetteur     : Amundi
  ISIN         : FR001400U5Q4
  Indice       : MSCI World Index EUR
  Réplication  : synthetic_swap

  Le fonds est éligible au PEA car il utilise une réplication synthétique
  via swap (IFT) avec un panier d'actions européennes ≥75%.

  Preuves :
    p.1 — « Le Fonds est éligible au Plan d'Épargne en Actions français (PEA) ... »
    p.1 — « La performance sera échangée contre celle de l'Indice de Référence ... »
```

## Why

PEA eligibility is opaque and *changes silently* — issuers re-domicile, swap counterparties, switch to ESG-screened variants, and rename funds (e.g. Amundi PEA Nasdaq-100 silently became "Amundi PEA US Tech Screened" under the same ticker). Brokers don't always flag this. `pea-audit` reads each fund's KID directly and tells you what the document actually says, with quotes you can verify.

## Install

```bash
pip install pea-audit
```

Optional extras:

```bash
pip install 'pea-audit[observability]'  # adds Langfuse for LLM tracing
pip install 'pea-audit[evals]'           # adds pyyaml for the eval suite
pip install 'pea-audit[dev]'             # everything above + python-dotenv
```

## Quickstart

```python
from pathlib import Path
from pea_audit import audit_pdf, VerdictCache
from pea_audit.llm import OllamaCloudClient

# Default backend: Ollama Cloud running Gemma 4 31b
llm = OllamaCloudClient(api_key="sk-...")  # from https://ollama.com/settings/keys

# Cache is opt-in. Library never writes to disk unless you supply one.
cache = VerdictCache(Path("./cache"))

verdict = audit_pdf("path/to/kid.pdf", llm=llm, cache=cache)

print(verdict.eligible)        # "yes" | "no" | "uncertain"
print(verdict.replication)     # "physical" | "synthetic_swap" | "unknown"
print(verdict.isin)            # deterministic — extracted from PDF text + Luhn-validated
for c in verdict.evidence:
    print(f"  p.{c.page}: « {c.quote} »")
```

### Audit by ticker (built-in URL registry)

```python
from pea_audit import audit_ticker, VerdictCache
from pea_audit.llm import OllamaCloudClient

llm = OllamaCloudClient(api_key="sk-...")
cache = VerdictCache(Path("./cache"))

result = audit_ticker("EWLD.PA", llm=llm, kid_dir=Path("./kids"), cache=cache)
print(result.verdict.eligible)  # "yes"
```

Built-ins ship for the most common French ETFs (Amundi PEA range, BNP Paribas Easy). Add more:

```python
from pea_audit.sources import register_source, KIDSource

register_source(KIDSource(
    ticker="LYX.PA",
    isin="FR0010411884",
    url="https://www.lyxoretf.fr/.../kid.pdf",
    issuer="Lyxor",
))
```

## Architecture

Two protocols make this library extensible without forking:

### `VisionLLM` — swap the model

```python
from typing import Any, Protocol

class VisionLLM(Protocol):
    def analyze_images(
        self,
        images: list[bytes],
        prompt: str,
        schema: dict[str, Any],
        system: str | None = None,
    ) -> dict[str, Any]: ...
```

The default `OllamaCloudClient` wraps Gemma 4 via Ollama Cloud with `tenacity` retries on transient errors and optional Langfuse tracing. Anyone can implement this protocol to plug in Claude vision, GPT-4o, Gemini, a local Ollama instance, etc.

### `KIDSource` — add issuers

```python
from pea_audit.sources import register_source, KIDSource, get_source, all_sources
```

A registry of ticker → KID URL mappings. Ships builtins for Amundi (URL pattern), BNP Paribas (per-fund UUIDs); URL helpers for BlackRock/iShares + Vanguard are importable but don't auto-register (most of their funds are PEA-ineligible — they're for testing the negative path).

## Eval baseline

The repo ships **13 regression cases** under `evals/cases/*.yaml` — 7 PEA-eligible synthetic-swap, 6 ineligible physical non-EEA — covering Amundi, BNP, BlackRock/iShares, Vanguard. Current baseline on Gemma 4 31b-cloud: **13/13 (100%)**. Run before any prompt or model change:

```bash
python evals/run.py
```

## Production niceties

- **Retries on transient errors** — `tenacity` with exponential backoff (1s → 4s → 16s), only on network/timeout/5xx (not on 4xx or schema errors that won't self-resolve)
- **Optional observability** — Langfuse traces per LLM call (model, input/output, tokens, latency). Activates when `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` are set, silent no-op otherwise
- **Deterministic ISINs** — vision misreads of the 12-char ISIN string are corrected by regex-extracting candidates from the PDF text layer and validating with the Luhn check digit
- **Versioned prompts** — `pea_audit/prompts/audit_v{N}.md` files, selected via `prompt_version=` parameter; rollback is a config change, not a code edit
- **Hard vs soft fields in diffs** — `compare_verdicts()` defaults to comparing only categorical fields (`eligible`, `replication`, `isin`) so monthly re-audit doesn't false-fire on LLM rephrasing of free-text issuer/index names

## Reference app: ETFTracker

The repo also ships a personal-tool app that consumes the library: a French ETF portfolio tracker with a Streamlit dashboard, monthly re-audit cron, FastAPI service, and Docker compose deployment. See `ETFTracker.md` (French) for that side.

To run it: `cp positions.csv.example positions.csv`, edit with your own holdings, `cp .env.example .env` with your Ollama key, then `docker compose up -d web` or `streamlit run dashboard.py`.

## Publishing checklist (maintainer)

PyPI publication uses [trusted publishers](https://docs.pypi.org/trusted-publishers/) (OIDC) — no API token secret needed in CI.

One-time setup:

1. Create the project on https://pypi.org (or first on https://test.pypi.org for a dry-run)
2. Add a Trusted Publisher pointing to `release.yml` in this repo, environment `pypi`
3. In GitHub repo settings, create the `pypi` environment (no secrets needed)

Per-release:

```bash
# 1. Update version in pyproject.toml + add entry to CHANGELOG.md
# 2. Verify it builds + tests pass
python -m build
pytest tests/

# 3. Tag and push — CI takes over
git tag v0.1.0
git push origin v0.1.0
```

The `release.yml` workflow builds the wheel + sdist and publishes to PyPI automatically on tag push.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE).

## Disclaimer

This is a personal-finance tool. The LLM-judged eligibility verdict is informational, not regulatory advice — always cross-check against the actual DIC/KID before buying.
