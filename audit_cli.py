"""CLI : `python audit_cli.py path/to/dic.pdf`."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# App loads its own env; library doesn't.
load_dotenv()

from pea_audit import PeaVerdict, VerdictCache, audit_pdf
from pea_audit.llm import OllamaCloudClient, enable_langfuse

CACHE_DIR = Path("cache/audits")

_BADGE = {
    "yes": "\033[32m✅ ÉLIGIBLE PEA\033[0m",
    "no": "\033[31m❌ NON ÉLIGIBLE\033[0m",
    "uncertain": "\033[33m⚠️  INCERTAIN\033[0m",
}


def render(v: PeaVerdict) -> str:
    lines = [
        "",
        f"  {_BADGE[v.eligible]}    (confiance : {v.confidence})",
        "",
        f"  Émetteur     : {v.issuer}",
        f"  ISIN         : {v.isin}",
        f"  Indice       : {v.underlying_index}",
        f"  Réplication  : {v.replication}",
        "",
        f"  {v.summary_fr}",
        "",
    ]
    if v.evidence:
        lines.append("  Preuves :")
        for c in v.evidence:
            quote = c.quote.replace("\n", " ").strip()
            if len(quote) > 120:
                quote = quote[:117] + "…"
            lines.append(f"    p.{c.page} — « {quote} »")
        lines.append("")
    if v.red_flags:
        lines.append("  ⚠️  Signaux d'alerte :")
        for f in v.red_flags:
            lines.append(f"    • {f}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python audit_cli.py <path-to-dic.pdf>", file=sys.stderr)
        return 2

    pdf_path = Path(argv[1])
    if not pdf_path.exists():
        print(f"Fichier introuvable : {pdf_path}", file=sys.stderr)
        return 1

    api_key = os.environ.get("OLLAMA_API_KEY")
    if not api_key:
        print("OLLAMA_API_KEY manquant — ajoute-le dans .env", file=sys.stderr)
        return 1

    llm = OllamaCloudClient(api_key=api_key)
    enable_langfuse()  # opt-in; no-op if Langfuse keys absent
    cache = VerdictCache(CACHE_DIR)

    print(f"📄 Audit de : {pdf_path}")
    verdict = audit_pdf(pdf_path, llm=llm, cache=cache)
    print(render(verdict))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
