"""Extraction (le « E » de l'ETL) : lire les sources.

Deux sources pour ce DW :
  - PostgreSQL OLTP : régions, clients, compteurs (les référentiels) ;
  - Cassandra       : relevés horaires (les faits de consommation).

On renvoie des DataFrames pandas, que le module transform nettoiera/agrégera.
"""

import pandas as pd
import psycopg
from cassandra.cluster import Cluster

from etl.config import Settings


def extract_oltp(cfg: Settings) -> dict[str, pd.DataFrame]:
    """Lit régions, clients et compteurs depuis la base OLTP (schéma oltp)."""
    conn_str = (f"host={cfg.pg_host} port={cfg.pg_port} dbname={cfg.oltp_db} "
                f"user={cfg.pg_user} password={cfg.pg_password}")
    with psycopg.connect(conn_str) as conn:
        regions = _read_sql(conn, "SELECT code AS region_code, nom, chef_lieu, population, "
                                  "superficie_km2 FROM oltp.regions")
        clients = _read_sql(conn, "SELECT client_id, prenom, nom, type_client, email, "
                                  "region_code, date_inscription FROM oltp.clients")
        compteurs = _read_sql(conn, "SELECT compteur_id, client_id, region_code, type_client, "
                                    "mode_facturation, puissance_kva, transformateur_id "
                                    "FROM oltp.compteurs")
    return {"regions": regions, "clients": clients, "compteurs": compteurs}


def _read_sql(conn: psycopg.Connection, query: str) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(query)
        cols = [d.name for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def extract_releves(cfg: Settings) -> pd.DataFrame:
    """Lit TOUS les relevés depuis Cassandra.

    Note : Cassandra n'aime pas les scans de table entiers (pas de WHERE sur la
    clé de partition). Pour un ETL complet on l'assume (traitement batch de nuit) ;
    un ETL incrémental ne lirait qu'une plage de jours.
    """
    cluster = Cluster([cfg.cassandra_host], port=cfg.cassandra_port)
    try:
        session = cluster.connect(cfg.cassandra_keyspace)
        session.default_fetch_size = 5000        # pagination : on ne charge pas tout d'un bloc
        rows = session.execute("SELECT compteur_id, horodatage, energie_kwh, "
                               "tension_v, courant_a FROM releves_par_compteur")
        data = [(r.compteur_id, r.horodatage, r.energie_kwh, r.tension_v, r.courant_a)
                for r in rows]
    finally:
        cluster.shutdown()
    return pd.DataFrame(data, columns=["compteur_id", "horodatage", "energie_kwh",
                                       "tension_v", "courant_a"])
