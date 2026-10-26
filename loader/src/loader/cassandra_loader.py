"""Chargement Cassandra : historique horaire des relevés (le plus gros volume).

Stratégie mémoire : on lit les relevés PARTITION PAR PARTITION (un fichier par
jour dans le data lake) et on les écrit au fur et à mesure. On ne charge JAMAIS
les ~1,4 million de lignes d'un coup.

Stratégie performance : requête PRÉPARÉE (le plan est calculé une fois, réutilisé
des millions de fois) + écritures CONCURRENTES par lots (execute_concurrent).
C'est exactement le genre d'écriture massive pour laquelle Cassandra est faite.

Rappel du modèle : clé de partition (compteur_id, jour), tri par horodatage.
Le `jour` (bucket) se déduit de l'horodatage de chaque relevé.
"""

import pandas as pd
from cassandra.cluster import Cluster
from cassandra.concurrent import execute_concurrent_with_args

from loader.config import Settings
from loader.datalake import DataLake

_INSERT = (
    "INSERT INTO releves_par_compteur "
    "(compteur_id, jour, horodatage, energie_kwh, index_kwh, tension_v, courant_a) "
    "VALUES (?, ?, ?, ?, ?, ?, ?)"
)


def load(cfg: Settings, lake: DataLake) -> dict[str, int]:
    cluster = Cluster([cfg.cassandra_host], port=cfg.cassandra_port)
    total = 0
    try:
        session = cluster.connect(cfg.cassandra_keyspace)
        prepared = session.prepare(_INSERT)

        for day, df in lake.iter_csv_partitions("releves"):
            ts = pd.to_datetime(df["horodatage"])
            # Chaque ligne devient un tuple de paramètres pour la requête préparée.
            params = [
                (row.compteur_id, t.date(), t.to_pydatetime(),
                 float(row.energie_kwh), float(row.index_kwh),
                 float(row.tension_v), float(row.courant_a))
                for row, t in zip(df.itertuples(index=False), ts)
            ]
            # concurrency : nombre de requêtes en vol simultanément (débit élevé).
            execute_concurrent_with_args(session, prepared, params, concurrency=100)
            total += len(params)
            print(f"    [cassandra] {day} : {len(params)} releves charges")
    finally:
        cluster.shutdown()
    return {"releves": total}
