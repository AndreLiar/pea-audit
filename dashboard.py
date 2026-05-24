"""Dashboard Streamlit : `streamlit run dashboard.py`."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# App loads env before importing pea_audit modules.
load_dotenv()

from pea_audit import (
    PeaVerdict,
    TickerAuditResult,
    VerdictCache,
    audit_pdf,
    audit_ticker,
    get_cached_verdict,
)
from pea_audit.llm import OllamaCloudClient, enable_langfuse

from etftracker.data_source import get_prices
from etftracker.portfolio import load_positions, totaux, valoriser

CACHE_DIR = Path("cache/audits")
KID_DIR = Path("cache/kids")


@st.cache_resource
def _llm() -> OllamaCloudClient:
    api_key = os.environ.get("OLLAMA_API_KEY")
    if not api_key:
        st.error("OLLAMA_API_KEY manquant — ajoute-le dans .env puis recharge.")
        st.stop()
    enable_langfuse()
    return OllamaCloudClient(api_key=api_key)


_audit_cache = VerdictCache(CACHE_DIR)

st.set_page_config(page_title="ETF Tracker", page_icon="📈", layout="wide")
st.title("📈 ETF Tracker")
st.caption("Cours différés (~15 min) via Yahoo Finance. Outil personnel, pas un conseil en investissement.")

tab_portfolio, tab_audit = st.tabs(["📊 Portefeuille", "🔍 Audit PEA"])


# ────────────────────────────── Onglet Portefeuille ──────────────────────────────


@st.cache_data(ttl=300)
def _charger() -> tuple[list, dict[str, float]]:
    positions = load_positions()
    prix = get_prices([p.ticker for p in positions])
    return positions, prix


with tab_portfolio:
    col_refresh, _ = st.columns([1, 5])
    if col_refresh.button("🔄 Rafraîchir les cours"):
        _charger.clear()

    try:
        positions, prix = _charger()
    except FileNotFoundError:
        st.error("`positions.csv` introuvable. Crée-le à la racine du projet.")
        st.stop()
    except ValueError as e:
        st.error(str(e))
        st.stop()

    manquants = [p.ticker for p in positions if p.ticker not in prix]
    if manquants:
        st.warning(f"Pas de prix récupéré pour : {', '.join(manquants)}")

    lignes = valoriser(positions, prix)
    t = totaux(lignes)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Coût investi", f"{t.cout_total:,.2f} €".replace(",", " "))
    c2.metric("Valeur actuelle", f"{t.valeur_actuelle:,.2f} €".replace(",", " "))
    c3.metric(
        "+/- Value",
        f"{t.plus_value:,.2f} €".replace(",", " "),
        delta=f"{t.plus_value_pct:+.2f} %" if t.plus_value_pct is not None else None,
    )
    c4.metric(
        "Lignes valorisées",
        f"{sum(1 for l in lignes if l.valeur_actuelle is not None)} / {len(lignes)}",
    )

    st.subheader("Détail des positions")

    _PEA_BADGE = {"yes": "✅", "no": "❌", "uncertain": "⚠️"}

    def _pea_cell(ticker: str) -> str:
        v = get_cached_verdict(ticker, cache=_audit_cache, kid_dir=KID_DIR)
        return _PEA_BADGE[v.eligible] if v is not None else "—"

    df = pd.DataFrame(
        [
            {
                "Ticker": l.ticker,
                "PEA": _pea_cell(l.ticker),
                "Nom": l.nom,
                "Parts": l.nb_parts,
                "PRU (€)": l.prix_achat_moyen,
                "Cours (€)": l.prix_actuel,
                "Valeur (€)": l.valeur_actuelle,
                "Coût (€)": l.cout_total,
                "+/- Value (€)": l.plus_value,
                "+/- Value (%)": l.plus_value_pct,
            }
            for l in lignes
        ]
    )
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "PEA": st.column_config.TextColumn(
                "PEA",
                help="Verdict éligibilité PEA (depuis le cache). "
                     "« — » = pas encore audité — va dans l'onglet Audit PEA.",
                width="small",
            ),
            "Parts": st.column_config.NumberColumn(format="%.2f"),
            "PRU (€)": st.column_config.NumberColumn(format="%.2f €"),
            "Cours (€)": st.column_config.NumberColumn(format="%.2f €"),
            "Valeur (€)": st.column_config.NumberColumn(format="%.2f €"),
            "Coût (€)": st.column_config.NumberColumn(format="%.2f €"),
            "+/- Value (€)": st.column_config.NumberColumn(format="%+.2f €"),
            "+/- Value (%)": st.column_config.NumberColumn(format="%+.2f %%"),
        },
    )
    if any(get_cached_verdict(l.ticker, cache=_audit_cache, kid_dir=KID_DIR) is None for l in lignes):
        st.caption("« — » dans la colonne PEA = pas encore audité. Lance "
                   "l'audit dans l'onglet 🔍 Audit PEA.")

    valorisees = [l for l in lignes if l.valeur_actuelle is not None]
    if valorisees:
        st.subheader("Répartition par ligne")
        repart = pd.DataFrame(
            {"Ligne": [l.nom for l in valorisees], "Valeur": [l.valeur_actuelle for l in valorisees]}
        ).set_index("Ligne")
        st.bar_chart(repart)


# ──────────────────────────────── Onglet Audit PEA ───────────────────────────────


_VERDICT_BANNER = {
    "yes": ("success", "✅ Éligible PEA"),
    "no": ("error", "❌ Non éligible PEA"),
    "uncertain": ("warning", "⚠️ Éligibilité incertaine — vérifie manuellement"),
}


def _render_verdict(v: PeaVerdict, *, nested: bool = False) -> None:
    """Render a verdict card. Set `nested=True` when already inside an expander
    (Streamlit forbids nesting), in which case the evidence is rendered inline."""
    kind, label = _VERDICT_BANNER[v.eligible]
    getattr(st, kind)(f"**{label}**  (confiance : {v.confidence})")

    if v.summary_fr:
        st.write(v.summary_fr)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Émetteur", v.issuer or "—")
    c2.metric("ISIN", v.isin or "—")
    c3.metric("Indice", v.underlying_index or "—")
    c4.metric("Réplication", v.replication.replace("_", " "))

    if v.evidence:
        if nested:
            st.markdown(f"**📑 Preuves citées ({len(v.evidence)}) :**")
            for c in v.evidence:
                st.markdown(f"- **Page {c.page}** — _« {c.quote} »_")
        else:
            with st.expander(f"📑 Preuves citées ({len(v.evidence)})", expanded=True):
                for c in v.evidence:
                    st.markdown(f"**Page {c.page}** — _« {c.quote} »_")

    if v.red_flags:
        st.warning("⚠️ Signaux d'alerte :\n\n" + "\n".join(f"- {f}" for f in v.red_flags))


_VERDICT_EMOJI = {"yes": "✅", "no": "❌", "uncertain": "⚠️"}


def _render_batch_summary(results: list[TickerAuditResult]) -> None:
    rows = []
    for r in results:
        if r.verdict is not None:
            rows.append({
                "Ticker": r.ticker,
                "Verdict": f"{_VERDICT_EMOJI[r.verdict.eligible]} {r.verdict.eligible}",
                "Confiance": r.verdict.confidence,
                "ISIN": r.verdict.isin,
                "Émetteur": r.verdict.issuer,
                "Indice": r.verdict.underlying_index,
                "Réplication": r.verdict.replication.replace("_", " "),
            })
        else:
            rows.append({
                "Ticker": r.ticker,
                "Verdict": "—",
                "Confiance": "",
                "ISIN": "",
                "Émetteur": "",
                "Indice": r.error or "?",
                "Réplication": "",
            })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    for r in results:
        if r.verdict is None:
            continue
        with st.expander(f"{_VERDICT_EMOJI[r.verdict.eligible]} {r.ticker} — détail"):
            _render_verdict(r.verdict, nested=True)


with tab_audit:
    st.markdown(
        "Audite l'éligibilité PEA des ETF — Gemma 4 lit le KID et cite "
        "verbatim les passages qui justifient le verdict."
    )
    st.caption(
        "L'éligibilité est jugée par le LLM — toujours vérifier contre le DIC "
        "avant d'acheter. L'ISIN est extrait du texte du PDF (déterministe)."
    )

    sub_batch, sub_single = st.tabs(["📁 Tout le portefeuille", "📄 Un fichier"])

    with sub_batch:
        st.write("Audite chaque ligne de `positions.csv` contre son KID officiel.")
        if st.button("🔍 Auditer tout le portefeuille", type="primary"):
            try:
                positions_for_audit = load_positions()
            except FileNotFoundError:
                st.error("`positions.csv` introuvable.")
                st.stop()

            progress = st.progress(0.0, text="Audit en cours…")
            results: list[TickerAuditResult] = []
            for i, p in enumerate(positions_for_audit):
                progress.progress(
                    i / len(positions_for_audit),
                    text=f"Audit de {p.ticker} ({i + 1}/{len(positions_for_audit)})…",
                )
                results.append(audit_ticker(
                    p.ticker, llm=_llm(), kid_dir=KID_DIR, cache=_audit_cache,
                ))
            progress.progress(1.0, text="Audit terminé.")
            progress.empty()

            _render_batch_summary(results)

    with sub_single:
        uploaded = st.file_uploader("DIC / KID PDF", type=["pdf"], key="audit_pdf")
        if uploaded is not None:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(uploaded.getbuffer())
                tmp_path = Path(tmp.name)

            with st.spinner(f"Analyse de {uploaded.name} via Gemma 4 31b-cloud…"):
                try:
                    verdict = audit_pdf(tmp_path, llm=_llm(), cache=_audit_cache)
                except RuntimeError as e:
                    st.error(str(e))
                    st.stop()
                except Exception as e:
                    st.exception(e)
                    st.stop()

            _render_verdict(verdict)
