"""Configuration des connexions aux bases, lue depuis les variables d'environnement.

Pourquoi l'environnement et pas un fichier codé en dur ? Parce que c'est ainsi
que Docker Compose fournit les secrets (via le .env) au conteneur `loader`, et
c'est la pratique standard « 12-factor » : aucun mot de passe dans le code.

Les valeurs par défaut (host=localhost) permettent aussi de lancer le chargeur
DEPUIS l'hôte (hors Docker), contre les ports publiés par le compose.
"""

import os
from dataclasses import dataclass


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    # Chemin du data lake à charger.
    data_root: str = _env("DATA_ROOT", "data/raw")

    # -- PostgreSQL (OLTP) ----------------------------------------------------
    pg_host: str = _env("POSTGRES_HOST", "localhost")
    pg_port: int = int(_env("POSTGRES_PORT", "5432"))
    pg_db: str = _env("POSTGRES_DB", "energy")
    pg_user: str = _env("POSTGRES_USER", "platform")
    pg_password: str = _env("POSTGRES_PASSWORD", "change_me")

    # -- MySQL (facturation) --------------------------------------------------
    mysql_host: str = _env("MYSQL_HOST", "localhost")
    mysql_port: int = int(_env("MYSQL_PORT", "3306"))
    mysql_db: str = _env("MYSQL_DATABASE", "billing")
    mysql_user: str = _env("MYSQL_USER", "platform")
    mysql_password: str = _env("MYSQL_PASSWORD", "change_me")

    # -- Cassandra (relevés) --------------------------------------------------
    cassandra_host: str = _env("CASSANDRA_HOST", "localhost")
    cassandra_port: int = int(_env("CASSANDRA_PORT", "9042"))
    cassandra_keyspace: str = _env("CASSANDRA_KEYSPACE", "releves")

    # -- MongoDB (inspections) ------------------------------------------------
    mongo_host: str = _env("MONGO_HOST", "localhost")
    mongo_port: int = int(_env("MONGO_PORT", "27017"))
    mongo_user: str = _env("MONGO_USER", "platform")
    mongo_password: str = _env("MONGO_PASSWORD", "change_me")
    mongo_db: str = _env("MONGO_DB", "terrain")

    # -- Neo4j (topologie) ----------------------------------------------------
    neo4j_uri: str = _env("NEO4J_URI", "bolt://localhost:7687")
    # NEO4J_AUTH a la forme "user/password" (format imposé par l'image Neo4j).
    neo4j_auth: str = _env("NEO4J_AUTH", "neo4j/change_me_neo4j")

    @property
    def neo4j_user(self) -> str:
        return self.neo4j_auth.split("/", 1)[0]

    @property
    def neo4j_password(self) -> str:
        return self.neo4j_auth.split("/", 1)[1]

    # -- Redis (cache) --------------------------------------------------------
    redis_host: str = _env("REDIS_HOST", "localhost")
    redis_port: int = int(_env("REDIS_PORT", "6379"))
