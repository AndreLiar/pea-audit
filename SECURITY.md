# Security Policy

## Supported versions

The latest released `0.x` version receives security fixes. Older `0.x` releases
do not — the project is pre-1.0 and the API may shift between minor versions.

| Version | Supported |
|---------|-----------|
| 0.2.x   | ✅        |
| 0.1.x   | ❌        |

## Reporting a vulnerability

**Please do not file a public GitHub issue for security reports.**

Email **kanmegnea@gmail.com** with:

- A description of the vulnerability and its potential impact
- Steps to reproduce (or a proof-of-concept if you have one)
- The affected version(s)

You should get an acknowledgement within **7 days**. If the report is valid, I'll
work on a fix and coordinate disclosure timing with you. Patches typically ship
as a `0.x.y+1` release with the fix flagged in `CHANGELOG.md`.

## Areas worth probing

Most user-facing surface that touches the network or filesystem:

- `pea_audit.ticker._download_kid` — fetches `KIDSource.url` over HTTP. Hardened
  in v0.2.0 against SSRF (http/https only, 20 MB cap, MIME check), but the URL
  itself is user-registrable via `register_source(...)`. Reports of bypasses
  to the size cap, MIME check, or scheme allowlist are welcome.
- `pea_audit.cache.VerdictCache` — writes JSON to a user-supplied `cache_dir`.
  Don't pass a path under user control.
- `pea_audit.prompts.load_prompt` — reads markdown from the package's
  `prompts/` directory. The default `prompts_dir` is package-internal; callers
  supplying a custom directory should treat it like any other config source.

The FastAPI service (`api.py`) accepts PDF uploads. It's intended as a personal
tool behind `API_TOKEN` auth — please don't deploy it publicly without
considering rate limiting and abuse protection.
