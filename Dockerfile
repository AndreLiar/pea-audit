# syntax=docker/dockerfile:1.7
# ETFTracker — image unique pour Streamlit + scripts CLI/audit.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true

WORKDIR /app

# Dépendances système minimales (curl pour healthcheck éventuel).
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# Installer les deps Python d'abord pour profiter du cache Docker tant que
# requirements.txt ne change pas.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Library + app helpers.
COPY pea_audit/ ./pea_audit/
COPY etftracker/ ./etftracker/
COPY cli.py audit_cli.py audit_portfolio.py audit_recheck.py dashboard.py api.py ./
COPY positions.csv ./

# cache/ est attendu en volume — on le crée pour qu'il existe au premier run.
RUN mkdir -p cache/audits cache/kids cache/alerts

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fs http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
