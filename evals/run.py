"""Eval runner for the PEA audit pipeline.

Iterates every YAML case in evals/cases/, downloads the KID (cached under
evals/data/), runs audit_pdf, and asserts the verdict matches expectations.

Usage :
    python evals/run.py                  # run + compare against baseline
    python evals/run.py --save-baseline  # persist current pass-set as baseline
    python evals/run.py --no-baseline    # ignore baseline (raw pass/fail only)

Exit codes :
    0  all cases pass AND no regression vs baseline
    1  one or more cases fail (no baseline yet, or hard-fail)
    2  regression vs baseline (a previously-passing case now fails)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
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
BASELINE_FILE = Path("evals/baseline.json")

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


def _load_baseline() -> dict | None:
    if not BASELINE_FILE.exists():
        return None
    return json.loads(BASELINE_FILE.read_text())


def _save_baseline(results: list[CaseResult]) -> None:
    snapshot = {
        "pass_rate": f"{sum(1 for r in results if r.passed)}/{len(results)}",
        "cases": {r.name: {"passed": r.passed, "category": r.category} for r in results},
    }
    BASELINE_FILE.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))


def _compare_to_baseline(results: list[CaseResult], baseline: dict) -> tuple[list[str], list[str]]:
    """Return (regressed, fixed) — case names that flipped state vs baseline."""
    regressed: list[str] = []
    fixed: list[str] = []
    base_cases = baseline.get("cases", {})
    for r in results:
        was = base_cases.get(r.name, {}).get("passed")
        if was is None:
            continue  # new case — not a regression
        if was and not r.passed:
            regressed.append(r.name)
        elif not was and r.passed:
            fixed.append(r.name)
    return regressed, fixed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--save-baseline", action="store_true",
                    help="Persist current results as the new baseline.")
    ap.add_argument("--no-baseline", action="store_true",
                    help="Ignore the baseline file (raw pass/fail only).")
    args = ap.parse_args()

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
    print(f"{_BOLD}Total : {total_passed}/{len(results)} cas réussis{_RESET}")

    # ── Baseline handling ─────────────────────────────────────────────────────
    if args.save_baseline:
        _save_baseline(results)
        print(f"\n💾 Baseline sauvegardée : {BASELINE_FILE} ({total_passed}/{len(results)})")
        return 0 if total_passed == len(results) else 1

    if args.no_baseline:
        return 0 if total_passed == len(results) else 1

    baseline = _load_baseline()
    if baseline is None:
        print(f"\n{_GREY}ℹ︎ Pas de baseline. Lance --save-baseline pour en créer une.{_RESET}")
        return 0 if total_passed == len(results) else 1

    base_pass_rate = baseline.get("pass_rate", "?/?")
    regressed, fixed = _compare_to_baseline(results, baseline)

    print(f"\n{_BOLD}vs baseline :{_RESET} {base_pass_rate} → {total_passed}/{len(results)}")
    if fixed:
        print(f"  {_GREEN}+ fixed   ({len(fixed)}):{_RESET} {', '.join(fixed)}")
    if regressed:
        print(f"  {_RED}- REGRESSED ({len(regressed)}):{_RESET} {', '.join(regressed)}")
        print(f"\n{_RED}❌ Regression vs baseline — refuser de merger / publier.{_RESET}\n")
        return 2
    if not fixed and not regressed:
        print(f"  {_GREY}(stable — no flips){_RESET}")

    print()
    return 0 if total_passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
