# =============================================================================
#  Image du service `loader` : charge data/raw dans les 6 bases
# =============================================================================
#  Python 3.12 (et non 3.14) : version stable, bien supportée par tous les
#  pilotes de base (cassandra-driver notamment). Le venv local du projet utilise
#  3.14, mais DANS Docker on fige 3.12 — c'est le choix acté au CLAUDE.md.
# =============================================================================
FROM python:3.12-slim

WORKDIR /app

# On installe d'abord SEULEMENT les métadonnées du paquet pour profiter du cache
# Docker : tant que pyproject.toml ne change pas, la couche d'install est
# réutilisée (build plus rapide).
COPY pyproject.toml ./
COPY src ./src

# Installation du paquet et de ses pilotes de base.
RUN pip install --no-cache-dir .

# Les données (data/raw) et la config viennent de volumes/variables au runtime
# (voir docker-compose.yml), pas de l'image : l'image reste légère et générique.
ENTRYPOINT ["python", "-m", "loader"]
