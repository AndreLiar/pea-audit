"""Récupération des prix. Seul module qui connaît yfinance.

Contrat : `get_prices(tickers)` renvoie toujours `dict[str, float]`.
Tant que ce contrat est respecté, on peut remplacer yfinance par n'importe
quelle autre source (Alpha Vantage, Marketstack...) sans toucher au reste.
"""

from __future__ import annotations

import yfinance as yf


def get_prices(tickers: list[str]) -> dict[str, float]:
    """Renvoie le dernier cours connu pour chaque ticker.

    Les tickers introuvables ou en erreur sont simplement absents du dict
    renvoyé — à charge de l'appelant de gérer le cas.
    """
    if not tickers:
        return {}

    prices: dict[str, float] = {}
    data = yf.download(
        tickers=tickers,
        period="5d",
        interval="1d",
        progress=False,
        auto_adjust=True,
        group_by="ticker",
    )

    if data is None or data.empty:
        return {}

    # yfinance renvoie une structure différente selon qu'il y a 1 ou N tickers.
    if len(tickers) == 1:
        ticker = tickers[0]
        close = data["Close"].dropna()
        if not close.empty:
            prices[ticker] = float(close.iloc[-1])
        return prices

    for ticker in tickers:
        try:
            close = data[ticker]["Close"].dropna()
            if not close.empty:
                prices[ticker] = float(close.iloc[-1])
        except (KeyError, IndexError):
            continue

    return prices
