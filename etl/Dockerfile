# =============================================================================
#  Image du service ETL (étape 9)
# =============================================================================
#  Python 3.12 stable. Installe le paquet etl et ses dépendances (pandas + les
#  drivers Postgres et Cassandra). C'est l'image lancée par la tâche Airflow
#  `lancer_etl`, ou à la main via le profil "load".
# =============================================================================
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

ENTRYPOINT ["python", "-m", "etl"]
