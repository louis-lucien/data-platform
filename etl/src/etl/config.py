"""Configuration des connexions de l'ETL, lue depuis l'environnement (12-factor)."""

import os
from dataclasses import dataclass


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    # Source OLTP (clients, compteurs, régions, réseau).
    pg_host: str = _env("POSTGRES_HOST", "localhost")
    pg_port: int = int(_env("POSTGRES_PORT", "5432"))
    oltp_db: str = _env("POSTGRES_DB", "energy")
    pg_user: str = _env("POSTGRES_USER", "platform")
    pg_password: str = _env("POSTGRES_PASSWORD", "change_me")

    # Cible : le Data Warehouse (même serveur Postgres, autre base).
    dw_db: str = _env("DW_DB", "warehouse")

    # Source des relevés : Cassandra.
    cassandra_host: str = _env("CASSANDRA_HOST", "localhost")
    cassandra_port: int = int(_env("CASSANDRA_PORT", "9042"))
    cassandra_keyspace: str = _env("CASSANDRA_KEYSPACE", "releves")
