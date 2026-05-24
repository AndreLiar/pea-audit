"""Eval runner for the PEA audit pipeline.

Iterates every YAML case in evals/cases/, downloads the KID (cached under
evals/data/), runs audit_pdf, and asserts the verdict matches expectations.

Usage : `python evals/run.py`  (run from project root)
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

# Make the project root importable when run as `python evals/run.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv()

from pea_audit import PeaVerdict, VerdictCache, audit_pdf  # noqa: E402
from pea_audit.llm import OllamaCloudClient, enable_langfuse  # noqa: E402

CASES_DIR = Path("evals/cases")
DATA_DIR = Path("evals/data")
CACHE_DIR = Path("cache/audits")

_LLM: OllamaCloudClient | None = None
_CACHE = VerdictCache(CACHE_DIR)


def _get_llm() -> OllamaCloudClient:
    global _LLM
    if _LLM is None:
        api_key = os.environ.get("OLLAMA_API_KEY")
        if not api_key:
            raise RuntimeError("OLLAMA_API_KEY missing — add it to .env")
        enable_langfuse()
        _LLM = OllamaCloudClient(api_key=api_key)
    return _LLM


@dataclass
class CaseResult:
    name: str
    category: str
    passed: bool
    failures: list[str]
    verdict: PeaVerdict | None
    error: str | None = None


def _download_if_missing(url: str, dest: Path) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1024:
        return dest
    resp = requests.get(
        url,
        headers={"User-Agent": "ETFTracker-PEA-Eval/1.0"},
        timeout=30,
        allow_redirects=True,
    )
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest


def _run_case(case_path: Path) -> CaseResult:
    case = yaml.safe_load(case_path.read_text())
    name = case["name"]
    category = case.get("category", "uncategorized")
    expected = case.get("expected", {})
    expected_contains = case.get("expected_contains", {})

    pdf_path = DATA_DIR / f"{case_path.stem}.pdf"

    try:
        _download_if_missing(case["pdf_url"], pdf_path)
    except Exception as e:
        return CaseResult(name, category, False, [], None, f"téléchargement KID : {e}")

    try:
        verdict = audit_pdf(pdf_path, llm=_get_llm(), cache=_CACHE)
    except Exception as e:
        return CaseResult(name, category, False, [], None, f"audit : {e}")

    failures: list[str] = []

    # Hard assertions — exact match
    for field_name, expected_val in expected.items():
        actual = getattr(verdict, field_name, None)
        if actual != expected_val:
            failures.append(f"{field_name} : attendu {expected_val!r}, obtenu {actual!r}")

    # Soft assertions — substring (case-insensitive)
    for field_name, substring in expected_contains.items():
        actual = str(getattr(verdict, field_name, "") or "")
        if substring.lower() not in actual.lower():
            failures.append(
                f"{field_name} : attendu un substring {substring!r}, obtenu {actual!r}"
            )

    return CaseResult(name, category, not failures, failures, verdict)


_RESET = "\033[0m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_GREY = "\033[90m"
_BOLD = "\033[1m"


def main() -> int:
    case_files = sorted(CASES_DIR.glob("*.yaml"))
    if not case_files:
        print(f"Aucun cas dans {CASES_DIR}/", file=sys.stderr)
        return 1

    print(f"\n🧪 {len(case_files)} cas d'eval…\n")
    results: list[CaseResult] = []

    for cf in case_files:
        print(f"  {cf.stem:<40} ", end="", flush=True)
        r = _run_case(cf)
        results.append(r)
        if r.error:
            print(f"{_RED}ERROR{_RESET}  {r.error}")
        elif r.passed:
            print(f"{_GREEN}PASS{_RESET}")
        else:
            print(f"{_RED}FAIL{_RESET}")
            for f in r.failures:
                print(f"      {_GREY}↳ {f}{_RESET}")

    print()

    # Summary by category
    by_cat: dict[str, list[CaseResult]] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)

    print(f"{_BOLD}Résumé par catégorie :{_RESET}")
    for cat, rs in sorted(by_cat.items()):
        passed = sum(1 for r in rs if r.passed)
        print(f"  {cat:<35} {passed}/{len(rs)}")

    total_passed = sum(1 for r in results if r.passed)
    print()
    print(f"{_BOLD}Total : {total_passed}/{len(results)} cas réussis{_RESET}\n")

    return 0 if total_passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
