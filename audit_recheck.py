"""Re-audit mensuel : détecte les changements silencieux côté émetteur.

À chaque exécution :
  1. Force-télécharge le KID de chaque ticker (positions.csv).
  2. Compare le verdict actuel au précédent (cache/audit_history.json).
  3. Pour tout changement matériel (éligibilité, réplication, ISIN) : écrit
     une alerte dans cache/alerts/{YYYY-MM-DD}.md.
  4. Exit 0 si rien n'a changé, 2 si des changements matériels sont détectés
     (cron peut alors mailer via MAILTO).

Usage : `python audit_recheck.py`
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from pea_audit import (
    PeaVerdict,
    TickerAuditResult,
    VerdictCache,
    audit_ticker,
    compare_verdicts,
)
from pea_audit.llm import OllamaCloudClient, enable_langfuse

from etftracker.portfolio import load_positions

CACHE_DIR = Path("cache/audits")
KID_DIR = Path("cache/kids")
HISTORY_FILE = Path("cache/audit_history.json")
ALERTS_DIR = Path("cache/alerts")


def _load_history() -> dict[str, list[dict]]:
    if not HISTORY_FILE.exists():
        return {}
    return json.loads(HISTORY_FILE.read_text())


def _save_history(h: dict[str, list[dict]]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(h, ensure_ascii=False, indent=2))


def _verdict_to_history_entry(v: PeaVerdict) -> dict:
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "eligible": v.eligible,
        "replication": v.replication,
        "underlying_index": v.underlying_index,
        "issuer": v.issuer,
        "isin": v.isin,
    }


def _history_to_verdict(entry: dict) -> PeaVerdict:
    """Minimal PeaVerdict reconstruction — only hard fields matter for diffing."""
    return PeaVerdict(
        eligible=entry["eligible"],
        confidence="high",
        replication=entry["replication"],
        underlying_index=entry["underlying_index"],
        issuer=entry["issuer"],
        isin=entry["isin"],
    )


def _write_alert(changes: list[tuple[str, list[str], PeaVerdict]]) -> Path:
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    out = ALERTS_DIR / f"{today}.md"

    lines = [f"# Alertes audit PEA — {today}", ""]
    for ticker, diffs, new_v in changes:
        lines.append(f"## ⚠️ {ticker}")
        lines.append("")
        lines.append("**Changements matériels détectés :**")
        for d in diffs:
            lines.append(f"- {d}")
        lines.append("")
        lines.append(
            f"**Verdict actuel :** {new_v.eligible} ({new_v.replication}, "
            f"{new_v.underlying_index})"
        )
        if new_v.summary_fr:
            lines.append("")
            lines.append(f"> {new_v.summary_fr}")
        lines.append("")
    out.write_text("\n".join(lines))
    return out


def main() -> int:
    api_key = os.environ.get("OLLAMA_API_KEY")
    if not api_key:
        print("OLLAMA_API_KEY manquant — ajoute-le dans .env", file=sys.stderr)
        return 1

    llm = OllamaCloudClient(api_key=api_key)
    enable_langfuse()
    cache = VerdictCache(CACHE_DIR)

    positions = load_positions()
    history = _load_history()
    print(f"\n🔄 Re-audit de {len(positions)} positions ({date.today()})…\n")

    changes: list[tuple[str, list[str], PeaVerdict]] = []
    errors: list[TickerAuditResult] = []

    for p in positions:
        print(f"  {p.ticker:<10} ", end="", flush=True)
        r = audit_ticker(
            p.ticker, llm=llm, kid_dir=KID_DIR, cache=cache, force_refresh=True,
        )
        if r.verdict is None:
            errors.append(r)
            err = (r.error or "?").splitlines()[0]
            print(f"✗ {err}")
            continue

        prev_entries = history.get(p.ticker, [])
        if prev_entries:
            prev_verdict = _history_to_verdict(prev_entries[-1])
            diffs = compare_verdicts(prev_verdict, r.verdict)
            if diffs:
                changes.append((p.ticker, diffs, r.verdict))
                print(f"⚠️  {len(diffs)} changement(s) : {'; '.join(diffs)}")
            else:
                print("✓ stable")
        else:
            print("✓ baseline (première exécution)")

        history.setdefault(p.ticker, []).append(_verdict_to_history_entry(r.verdict))

    _save_history(history)
    print()

    if changes:
        alert_path = _write_alert(changes)
        print(f"⚠️  {len(changes)} ticker(s) avec changements — alerte écrite : {alert_path}")
    else:
        print("✅ Aucun changement matériel.")

    if errors:
        print(f"❌ {len(errors)} erreur(s) d'audit — vérifie les URLs dans pea_audit.sources.")

    print()
    if changes:
        return 2
    if errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
