"""Chargement (le « L » de l'ETL) : écrire dimensions et faits dans le warehouse.

Ordre imposé par les clés étrangères du schéma en étoile :
    dim_region, dim_temps -> dim_client -> dim_compteur -> faits

Stratégie « full refresh » : on VIDE puis on recharge (TRUNCATE + INSERT). Simple
et correct pour un ETL batch complet. Un ETL incrémental ferait des UPSERT ciblés.
"""

import psycopg

from etl.config import Settings


def _conn_str(cfg: Settings) -> str:
    return (f"host={cfg.pg_host} port={cfg.pg_port} dbname={cfg.dw_db} "
            f"user={cfg.pg_user} password={cfg.pg_password}")


def _insert(cur, table: str, df, columns: list[str]) -> int:
    if df.empty:
        return 0
    placeholders = ",".join(["%s"] * len(columns))
    rows = [tuple(r) for r in df[columns].itertuples(index=False)]
    cur.executemany(f"INSERT INTO dw.{table} ({','.join(columns)}) VALUES ({placeholders})", rows)
    return len(rows)


def load_warehouse(cfg: Settings, dims: dict, faits: dict) -> dict[str, int]:
    """Charge tout le warehouse en une transaction (tout ou rien)."""
    counts: dict[str, int] = {}
    with psycopg.connect(_conn_str(cfg)) as conn:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO dw")
            # Vidage dans l'ordre inverse des dépendances (faits d'abord).
            cur.execute("TRUNCATE fait_consommation_horaire, fait_consommation_jour, "
                        "dim_compteur, dim_client, dim_temps, dim_region RESTART IDENTITY CASCADE")

            counts["dim_region"] = _insert(cur, "dim_region", dims["region"],
                ["region_code", "nom", "chef_lieu", "population", "superficie_km2"])
            counts["dim_temps"] = _insert(cur, "dim_temps", dims["temps"],
                ["date_id", "jour", "mois", "annee", "trimestre", "jour_semaine",
                 "est_weekend", "nom_mois"])
            counts["dim_client"] = _insert(cur, "dim_client", dims["client"],
                ["client_id", "nom_complet", "type_client", "region_code",
                 "email_valide", "date_inscription"])
            counts["dim_compteur"] = _insert(cur, "dim_compteur", dims["compteur"],
                ["compteur_id", "client_id", "region_code", "type_client",
                 "mode_facturation", "puissance_kva", "transformateur_id"])
            counts["fait_horaire"] = _insert(cur, "fait_consommation_horaire", faits["horaire"],
                ["compteur_id", "date_id", "horodatage", "energie_kwh", "tension_v", "courant_a"])
            counts["fait_jour"] = _insert(cur, "fait_consommation_jour", faits["jour"],
                ["compteur_id", "date_id", "energie_kwh", "tension_moy_v",
                 "courant_moy_a", "nb_releves"])
        conn.commit()
    return counts
