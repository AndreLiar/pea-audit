# Contributing to pea-audit

Thanks for considering a contribution! This document covers the most common changes.

## Dev setup

```bash
git clone <repo>
cd <repo>
pip install -e '.[dev,evals]'
cp .env.example .env  # fill in OLLAMA_API_KEY for eval runs
```

Run the test suite (fast, no LLM):

```bash
pytest tests/ -v
```

Run the full eval suite (~$0.20 first run, free on cache hit):

```bash
python evals/run.py
```

## Adding a KID source (new issuer or ticker)

Most contributions are likely additions to `pea_audit/sources/`. Pattern:

1. **Find the canonical KID URL.** Search the issuer's site for the fund's "Document d'Informations Clés" / "Key Information Document" PDF in French. Verify with `curl -fsSL -o /tmp/x.pdf <url> && file /tmp/x.pdf` that you get a real PDF (some issuer sites gate KIDs behind JS disclaimer pages).

2. **Add the entry.** Either extend an existing issuer module (`amundi.py`, `bnp.py`) or create a new one. For URL-pattern issuers, expose a helper:

```python
# pea_audit/sources/myissuer.py
from .base import KIDSource, register_source

def myissuer_url(isin: str) -> str:
    return f"https://.../{isin}/kid.pdf"

register_source(KIDSource(
    ticker="XYZ.PA",
    isin="FR0012345678",
    url=myissuer_url("FR0012345678"),
    issuer="MyIssuer",
))
```

3. **Auto-register from the package.** If you created a new module, import it in `pea_audit/sources/__init__.py` so it loads on `import pea_audit.sources`.

4. **Add an eval case** under `evals/cases/{slug}.yaml`. This is the part that proves the audit gets the right answer for your ticker.

## Adding a vision LLM backend

Implement the `VisionLLM` protocol from `pea_audit/llm/base.py`:

```python
class MyVisionLLM:
    def analyze_images(self, images, prompt, schema, system=None):
        ...
```

Smoke-test it against a sample KID:

```python
from pea_audit import audit_pdf
verdict = audit_pdf("samples/amundi_pea_monde_kid.pdf", llm=MyVisionLLM())
```

Then run `python evals/run.py` with a patched runner (swap `OllamaCloudClient` for yours) to compare your backend's pass rate against the baseline.

## Changing the prompt

**Always create a new version file** — never edit `audit_v{N}.md` in place:

1. `cp pea_audit/prompts/audit_v{N}.md pea_audit/prompts/audit_v{N+1}.md`
2. Edit `audit_v{N+1}.md`. Update the changelog header.
3. Bump `DEFAULT_PROMPT_VERSION` in `pea_audit/core.py`.
4. `rm -rf cache/audits/` (cache is byte-keyed on the PDF, not the prompt — flush forces re-audit with the new prompt).
5. Run `python evals/run.py`. It must stay at 13/13 — or you must document the new baseline.

The old version file stays around as a rollback target. To roll back: change `DEFAULT_PROMPT_VERSION` back, bust cache, done.

## Pull request checklist

- [ ] `pytest tests/ -v` passes
- [ ] `python evals/run.py` passes (or you've explained why a case must change)
- [ ] If you added a public function/class, added a docstring with at least one usage example
- [ ] If you added a dependency, added it to `pyproject.toml` under the right extras group
- [ ] Updated `CHANGELOG.md`
