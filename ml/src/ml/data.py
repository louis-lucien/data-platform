"""Accès aux données du ML : relevés (features) et inspections (étiquettes).

Les relevés viennent du Data Warehouse (fait_consommation_horaire) : données
déjà nettoyées, donc features cohérentes avec le reste de la plateforme. Les
étiquettes viennent des inspections dans MongoDB.
"""

import os

import pandas as pd


def _pg_conn_str() -> str:
    return (f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
            f"port={os.getenv('POSTGRES_PORT', '5432')} "
            f"dbname={os.getenv('DW_DB', 'warehouse')} "
            f"user={os.getenv('POSTGRES_USER', 'platform')} "
            f"password={os.getenv('POSTGRES_PASSWORD', 'change_me')}")


def load_releves_from_dw() -> pd.DataFrame:
    """Lit les relevés horaires depuis le Data Warehouse (pour construire les features)."""
    import psycopg      # import paresseux : la logique pure (features) n'en dépend pas
    with psycopg.connect(_pg_conn_str()) as conn, conn.cursor() as cur:
        cur.execute("SELECT compteur_id, horodatage, energie_kwh, tension_v "
                    "FROM dw.fait_consommation_horaire")
        cols = [d.name for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def load_inspections_from_mongo() -> list[dict]:
    """Lit les inspections depuis MongoDB (pour construire les étiquettes)."""
    from pymongo import MongoClient
    client = MongoClient(
        host=os.getenv("MONGO_HOST", "localhost"),
        port=int(os.getenv("MONGO_PORT", "27017")),
        username=os.getenv("MONGO_USER", "platform"),
        password=os.getenv("MONGO_PASSWORD", "change_me"),
    )
    try:
        coll = client[os.getenv("MONGO_DB", "terrain")]["inspections"]
        return list(coll.find({}, {"compteur_id": 1, "resultat": 1, "_id": 0}))
    finally:
        client.close()
