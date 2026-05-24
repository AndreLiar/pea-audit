# 📈 ETF Tracker

Petit suivi de portefeuille ETF en Python. Deux interfaces (console + dashboard web),
une seule logique métier. Conçu pour un investisseur **long terme** : cours différés,
suivi périodique, pas de trading.

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Édite `positions.csv` avec tes propres lignes :

```csv
ticker,nom,nb_parts,prix_achat_moyen
EWLD.PA,Amundi PEA Monde (MSCI World) UCITS,15,28.40
```

⚠️ **Trouve le bon ticker** sur https://finance.yahoo.com en cherchant ton ETF.
Le suffixe dépend de la place de cotation :

* `.PA` → Euronext Paris (par défaut pour les ETF éligibles PEA)
* `.AS` → Euronext Amsterdam
* `.DE` → Xetra (Allemagne)
* `.MI` → Borsa Italiana (Milan)

### Cas d'usage : PEA (Trade Republic, Bourse Direct, etc.)

Le projet est pensé pour un **PEA français** (compte fiscalement avantagé, plafond
150 000 €). Le PEA n'accepte que des actions/ETF de l'EEE ou des **UCITS synthétiques**
qui répliquent des indices hors-EEE tout en détenant ≥75 % d'actions européennes.

Exemples couramment éligibles PEA (à vérifier sur le DIC/KIID de l'émetteur) :

| Ticker      | Nom                                         | Indice répliqué         |
|-------------|---------------------------------------------|-------------------------|
| `EWLD.PA`   | Amundi PEA Monde UCITS                      | MSCI World (synth.)     |
| `ESE.PA`    | BNP Paribas Easy S&P 500 UCITS              | S&P 500 (synth.)        |
| `PANX.PA`   | Amundi PEA Nasdaq-100 UCITS                 | Nasdaq-100 (synth.)     |
| `PAEEM.PA`  | Amundi PEA MSCI Emerging Markets UCITS      | MSCI EM (synth.)        |
| `MEUD.PA`   | Amundi Stoxx Europe 600 UCITS               | Stoxx Europe 600        |

⚠️ L'éligibilité PEA peut changer si l'émetteur restructure le fonds. Vérifie
toujours sur le DIC du produit avant d'acheter — ce projet ne valide pas
l'éligibilité, il calcule juste la valorisation.

## Usage

**Version console :**

```bash
python cli.py
```

**Version dashboard web :**

```bash
streamlit run dashboard.py
```

**Audit PEA d'un ETF (avec Gemma 4 / Ollama Cloud) :**

```bash
cp .env.example .env                                    # puis colle ta clé Ollama Cloud dans .env
python audit_cli.py samples/amundi_pea_monde_kid.pdf    # audite un PDF
python audit_portfolio.py                               # audite tous les tickers de positions.csv
python audit_recheck.py                                 # force-refresh + diff vs précédent (à mettre en cron mensuel)
```

**Docker (un clic) :**

```bash
docker compose up -d web                # http://localhost:8502
docker compose run --rm recheck         # re-audit dans le conteneur (idem cron)
```

Le re-audit mensuel se programme via `crontab.example` (voir le fichier).
Sortie 0 si stable, 2 si changement matériel détecté (`MAILTO` du cron envoie alors un mail).

L'audit lit un DIC/KID PDF, détermine si le fonds est éligible PEA, et cite
verbatim les phrases du document qui le prouvent. Disponible aussi dans
l'onglet **🔍 Audit PEA** du dashboard (sous-onglets "Tout le portefeuille" et
"Un fichier").

Pour ajouter un nouveau ticker au mode batch : éditer `etftracker/kid_sources.py`
avec le ticker, l'ISIN, et l'URL du KID. Pour les ETF Amundi, l'URL suit le
pattern `https://www.amundietf.fr/pdfDocuments/kid-priips/{ISIN}/FRA/FRA`.

## Architecture (le découplage)

```
ETFTracker/
├── positions.csv                  ← tes données
├── .env                           ← OLLAMA_API_KEY=… (chargé auto, gitignored)
│
├── cli.py                         ← entrée : console portefeuille
├── audit_cli.py                   ← entrée : audit d'un PDF
├── audit_portfolio.py             ← entrée : audit batch de positions.csv
├── dashboard.py                   ← entrée : Streamlit
│
├── etftracker/                    ← package librairie
│   ├── portfolio.py               ← calculs : valorisation, plus-values
│   ├── pea_audit.py               ← logique d'audit PEA (PDF → PeaVerdict)
│   ├── data_source.py             ← récupération des prix (yfinance)
│   ├── ollama_client.py           ← wrapper Ollama Cloud Gemma 4
│   └── kid_sources.py             ← map ticker → URL KID
│
├── samples/                       ← KIDs de référence pour tests manuels
└── cache/                         ← runtime (gitignored)
    ├── audits/                    ← verdicts (par sha256 du PDF)
    └── kids/                      ← KIDs téléchargés (un par ticker)
```

Deux principes de découplage :

1. `etftracker.data_source` renvoie toujours un `dict {ticker: prix}`. Tant
   que ce contrat tient, tu peux changer de source (yfinance → Alpha Vantage,
   Marketstack...) sans toucher au reste.

2. `etftracker.ollama_client.analyze_images(...)` renvoie toujours un `dict`
   conforme à un JSON Schema. Tant que ce contrat tient, tu peux remplacer
   Ollama par Claude vision / OpenAI / Gemini sans toucher à `pea_audit.py`.

Les scripts d'entrée (`cli.py`, `dashboard.py`, etc.) restent à la racine
et s'exécutent toujours depuis la racine — les chemins relatifs (`cache/`,
`positions.csv`) en dépendent.

## Pistes d'évolution

* Historiser la valeur quotidienne dans une base SQLite → tracer une courbe d'évolution
* Ajouter le calcul de rendement annualisé (TRI / money-weighted return)
* Gérer plusieurs enveloppes (PEA, CTO, AV) avec une colonne supplémentaire
* Alerte e-mail/Telegram sur un seuil de variation
* Ajouter les dividendes / distributions

## Note importante

Cours **différés (~15 min)** via Yahoo Finance — largement suffisant pour du suivi
long terme. `yfinance` repose sur des données publiques Yahoo et peut casser
occasionnellement ; si c'est le cas, c'est le moment de brancher une vraie API à
clé dans `data_source.py`.

Ceci est un outil personnel de suivi, pas un conseil en investissement.
