"""Point d'entrée de l'ETL : `python -m etl` ou commande `run-etl`.

Enchaîne Extract -> Transform -> Load et affiche un récapitulatif. C'est ce que
la tâche Airflow `lancer_etl` (étape 8) exécutera dans un conteneur.
"""

import logging
import sys
import time

import pandas as pd

from etl import extract, load, transform
from etl.config import Settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("etl")


def run(cfg: Settings) -> dict[str, int]:
    # -- EXTRACT --------------------------------------------------------------
    log.info("Extract : OLTP...")
    oltp = extract.extract_oltp(cfg)
    log.info("Extract : relevés (Cassandra)...")
    releves = extract.extract_releves(cfg)
    log.info(f"  {len(oltp['clients'])} clients, {len(oltp['compteurs'])} compteurs, "
             f"{len(releves)} relevés bruts")

    # -- TRANSFORM ------------------------------------------------------------
    log.info("Transform : nettoyage + agrégation...")
    clients_propres = transform.dedupe_clients(oltp["clients"])
    log.info(f"  clients après dédoublonnage : {len(clients_propres)} "
             f"(−{len(oltp['clients']) - len(clients_propres)} doublons)")

    dim_compteur = transform.build_dim_compteur(oltp["compteurs"], clients_propres)

    # Fait horaire : on ne garde que les relevés de compteurs présents dans dim_compteur
    # (intégrité référentielle du warehouse).
    compteurs_valides = set(dim_compteur["compteur_id"])
    releves = releves[releves["compteur_id"].isin(compteurs_valides)].copy()
    releves["horodatage"] = pd.to_datetime(releves["horodatage"])
    fait_horaire = releves.assign(date_id=releves["horodatage"].dt.date)[
        ["compteur_id", "date_id", "horodatage", "energie_kwh", "tension_v", "courant_a"]]
    fait_jour = transform.aggregate_daily(releves)

    dims = {
        "region": oltp["regions"],
        "temps": transform.build_dim_temps(fait_horaire["date_id"]),
        "client": transform.build_dim_client(clients_propres),
        "compteur": dim_compteur,
    }
    faits = {"horaire": fait_horaire, "jour": fait_jour}

    # -- LOAD -----------------------------------------------------------------
    log.info("Load : écriture dans le warehouse...")
    return load.load_warehouse(cfg, dims, faits)


def main(argv: list[str] | None = None) -> int:
    start = time.monotonic()
    try:
        counts = run(Settings())
    except Exception as exc:
        log.error(f"ECHEC ETL : {type(exc).__name__}: {exc}")
        return 1
    log.info(f"\nETL terminé en {time.monotonic() - start:.1f}s :")
    for table, n in counts.items():
        log.info(f"  {table:28s} {n:>10d} lignes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
