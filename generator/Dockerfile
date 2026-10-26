# =============================================================================
#  Image du producteur temps réel (étape 5)
# =============================================================================
#  Python 3.12 (stable, choix acté au CLAUDE.md). Installe le générateur avec
#  l'extra `streaming` (ajoute kafka-python). Le parc de compteurs (data/raw)
#  est monté en volume au runtime, pas copié dans l'image.
# =============================================================================
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY config.yaml ./

RUN pip install --no-cache-dir ".[streaming]"

# Par défaut : lance le producteur de flux. Les options (bootstrap, intervalles)
# viennent des variables d'environnement passées par le compose.
ENTRYPOINT ["python", "-m", "generator.streaming.producer"]
