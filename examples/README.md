# Examples

| File | What it shows |
|---|---|
| `01_basic_audit.py` | Minimal end-to-end: audit a single PDF |
| `02_audit_by_ticker.py` | Use the built-in KIDSource registry to audit by ticker |
| `03_custom_llm.py` | Implement the `VisionLLM` protocol with your own backend |
| `04_custom_kid_source.py` | Register a `KIDSource` for an issuer the library doesn't ship |
| `05_async_batch.py` | Concurrent audits with `aaudit_ticker` + `AsyncOllamaCloudClient` |

All examples require `OLLAMA_API_KEY` in env except `03_custom_llm.py` (which stubs the LLM).

### If you installed via PyPI

```bash
pip install pea-audit
OLLAMA_API_KEY=... python examples/01_basic_audit.py
```

### If you cloned this repo for local development

`pea_audit` is in the working tree, not installed system-wide — add the project root to `PYTHONPATH`:

```bash
PYTHONPATH=. OLLAMA_API_KEY=... python examples/01_basic_audit.py
```

Or `pip install -e .` once and the examples work without `PYTHONPATH`.
