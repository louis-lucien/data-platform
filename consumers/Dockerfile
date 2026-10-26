# =============================================================================
#  Image des consumers Kafka (étape 6)
# =============================================================================
#  Une seule image pour les deux consumers (Redis, Mongo) : ils partagent le
#  même code. On choisit lequel lancer via la commande du service (compose).
#  Python 3.12 (stable), cohérent avec le reste de la plateforme.
# =============================================================================
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

# Pas d'ENTRYPOINT fixe : chaque service du compose précise le module à lancer
# (python -m consumers.redis_consumer, ou .mongo_consumer).
