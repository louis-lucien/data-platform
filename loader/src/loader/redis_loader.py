"""Amorçage Redis : dernier relevé connu de chaque compteur.

Redis est un cache du PRÉSENT : normalement, c'est le streaming (étape 6) qui le
tient à jour. Mais au démarrage à froid, le cache est vide. On l'amorce donc
avec le DERNIER relevé de l'historique, pour que le dashboard ait quelque chose
à afficher avant le premier événement temps réel.

On respecte la convention de clés documentée dans sql/init/redis/README.md :
    compteur:<id>:dernier  (Hash)

On ne met PAS de TTL ici (ce sont des valeurs d'amorçage) ; le streaming, lui,
posera des TTL à chaque écriture.
"""

import pandas as pd
import redis

from loader.config import Settings
from loader.datalake import DataLake


def load(cfg: Settings, lake: DataLake) -> dict[str, int]:
    # Dernier relevé par compteur = la ligne au plus grand horodatage.
    # On balaie les partitions et on garde le maximum par compteur, sans tout
    # garder en mémoire (on ne conserve qu'une ligne par compteur).
    latest: dict[str, tuple] = {}
    for _day, df in lake.iter_csv_partitions("releves"):
        df["horodatage"] = pd.to_datetime(df["horodatage"])
        for row in df.itertuples(index=False):
            prev = latest.get(row.compteur_id)
            if prev is None or row.horodatage > prev[0]:
                latest[row.compteur_id] = (
                    row.horodatage, row.energie_kwh, row.index_kwh, row.tension_v, row.courant_a
                )

    client = redis.Redis(host=cfg.redis_host, port=cfg.redis_port, decode_responses=True)
    # pipeline = on envoie toutes les commandes d'un coup (1 aller-retour réseau).
    pipe = client.pipeline()
    for compteur_id, (ts, energie, index, tension, courant) in latest.items():
        pipe.hset(f"compteur:{compteur_id}:dernier", mapping={
            "horodatage": ts.isoformat(),
            "energie_kwh": energie,
            "index_kwh": index,
            "tension_v": tension,
            "courant_a": courant,
        })
    pipe.execute()
    return {"compteurs_amorces": len(latest)}
