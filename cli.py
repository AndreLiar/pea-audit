"""Affichage console du portefeuille."""

from __future__ import annotations

from etftracker.data_source import get_prices
from etftracker.portfolio import Ligne, Totaux, load_positions, totaux, valoriser


def _fmt_eur(v: float | None) -> str:
    return f"{v:>12,.2f} €".replace(",", " ") if v is not None else f"{'n/a':>14}"


def _fmt_pct(v: float | None) -> str:
    return f"{v:>+7.2f} %" if v is not None else f"{'n/a':>9}"


def afficher(lignes: list[Ligne], t: Totaux) -> None:
    print()
    print(f"{'Ticker':<10} {'Nom':<32} {'Parts':>7} {'PRU':>10} {'Cours':>10} "
          f"{'Valeur':>14} {'+/- Value':>14} {'%':>9}")
    print("-" * 110)

    for l in lignes:
        print(
            f"{l.ticker:<10} {l.nom[:32]:<32} {l.nb_parts:>7.2f} "
            f"{l.prix_achat_moyen:>10.2f} "
            f"{(f'{l.prix_actuel:>10.2f}' if l.prix_actuel is not None else f'{chr(0x2014):>10}')} "
            f"{_fmt_eur(l.valeur_actuelle)} "
            f"{_fmt_eur(l.plus_value)} "
            f"{_fmt_pct(l.plus_value_pct)}"
        )

    print("-" * 110)
    print(
        f"{'TOTAL':<10} {'':<32} {'':>7} {'':>10} {'':>10} "
        f"{_fmt_eur(t.valeur_actuelle)} {_fmt_eur(t.plus_value)} {_fmt_pct(t.plus_value_pct)}"
    )
    print(f"Coût total investi : {_fmt_eur(t.cout_total).strip()}")
    print()


def main() -> None:
    positions = load_positions()
    prix = get_prices([p.ticker for p in positions])

    manquants = [p.ticker for p in positions if p.ticker not in prix]
    if manquants:
        print(f"⚠️  Pas de prix pour : {', '.join(manquants)}")

    lignes = valoriser(positions, prix)
    afficher(lignes, totaux(lignes))


if __name__ == "__main__":
    main()
