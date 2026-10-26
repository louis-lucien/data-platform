# =============================================================================
#  Image du ML : entraînement et scoring du détecteur d'anomalies
# =============================================================================
#  Python 3.12 stable. Installe scikit-learn + les drivers pour lire le DW
#  (Postgres) et les inspections (Mongo). Le modèle entraîné est écrit dans
#  /app/models (monté en volume pour le conserver entre les runs).
# =============================================================================
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

# Par défaut : entraînement. Le service "ml-score" surcharge la commande.
ENTRYPOINT ["python", "-m"]
CMD ["ml.train"]
