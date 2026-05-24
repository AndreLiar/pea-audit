"""Logique métier pure : chargement des positions et calculs de valorisation.

Aucun I/O réseau ici. Les prix arrivent en argument (`dict[ticker, prix]`),
peu importe leur provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class Position:
    ticker: str
    nom: str
    nb_parts: float
    prix_achat_moyen: float


@dataclass(frozen=True)
class Ligne:
    """Une position valorisée au prix courant."""

    ticker: str
    nom: str
    nb_parts: float
    prix_achat_moyen: float
    prix_actuel: float | None
    valeur_actuelle: float | None
    cout_total: float
    plus_value: float | None
    plus_value_pct: float | None


def load_positions(path: str | Path = "positions.csv") -> list[Position]:
    df = pd.read_csv(path)
    required = {"ticker", "nom", "nb_parts", "prix_achat_moyen"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes dans {path}: {sorted(missing)}")

    return [
        Position(
            ticker=str(row.ticker).strip(),
            nom=str(row.nom).strip(),
            nb_parts=float(row.nb_parts),
            prix_achat_moyen=float(row.prix_achat_moyen),
        )
        for row in df.itertuples(index=False)
    ]


def valoriser(positions: list[Position], prix: dict[str, float]) -> list[Ligne]:
    lignes: list[Ligne] = []
    for p in positions:
        cout_total = p.nb_parts * p.prix_achat_moyen
        prix_actuel = prix.get(p.ticker)

        if prix_actuel is None:
            lignes.append(
                Ligne(
                    ticker=p.ticker,
                    nom=p.nom,
                    nb_parts=p.nb_parts,
                    prix_achat_moyen=p.prix_achat_moyen,
                    prix_actuel=None,
                    valeur_actuelle=None,
                    cout_total=cout_total,
                    plus_value=None,
                    plus_value_pct=None,
                )
            )
            continue

        valeur = p.nb_parts * prix_actuel
        pv = valeur - cout_total
        pv_pct = (pv / cout_total * 100) if cout_total else None

        lignes.append(
            Ligne(
                ticker=p.ticker,
                nom=p.nom,
                nb_parts=p.nb_parts,
                prix_achat_moyen=p.prix_achat_moyen,
                prix_actuel=prix_actuel,
                valeur_actuelle=valeur,
                cout_total=cout_total,
                plus_value=pv,
                plus_value_pct=pv_pct,
            )
        )

    return lignes


@dataclass(frozen=True)
class Totaux:
    cout_total: float
    valeur_actuelle: float
    plus_value: float
    plus_value_pct: float | None


def totaux(lignes: list[Ligne]) -> Totaux:
    """Agrège uniquement les lignes dont on a pu obtenir un prix."""
    valorisees = [l for l in lignes if l.valeur_actuelle is not None]
    cout = sum(l.cout_total for l in valorisees)
    valeur = sum(l.valeur_actuelle for l in valorisees)  # type: ignore[misc]
    pv = valeur - cout
    pv_pct = (pv / cout * 100) if cout else None
    return Totaux(cout_total=cout, valeur_actuelle=valeur, plus_value=pv, plus_value_pct=pv_pct)
