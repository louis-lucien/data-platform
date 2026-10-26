"""Consumer MongoDB : meter-alerts -> collection `alertes`.

Rôle : historiser les alertes brutes émises par le producteur (tension hors
bornes, consommation nulle...). MongoDB convient car les alertes ont une
structure variable selon leur type (comme les inspections). La collection
`alertes` a été créée à l'étape 3 (sql/init/mongo/01_init_inspections.js).

On ajoute un champ `recu_le` (horodatage de réception) : utile pour mesurer la
latence entre l'émission et l'ingestion, et pour trier les alertes récentes.
"""

import logging
from datetime import datetime, timezone

from consumers.base import run_consumer, bootstrap_servers
from consumers.logging_setup import setup_logging

log = logging.getLogger("consumers.mongo")


class MongoHandler:
    group_id = "mongo-alertes"
    topics = ["meter-alerts"]

    def __init__(self, collection):
        self.collection = collection

    def handle(self, msg: dict) -> None:
        doc = dict(msg)                                  # copie : on ne mute pas l'entrée
        doc["recu_le"] = datetime.now(timezone.utc)
        # Horodatage de l'alerte en vraie date BSON (tri/filtre temporel efficace).
        if "horodatage" in doc:
            try:
                doc["horodatage_dt"] = datetime.fromisoformat(doc["horodatage"])
            except (ValueError, TypeError):
                pass                                     # on garde la chaîne telle quelle
        self.collection.insert_one(doc)

    def close(self) -> None:
        self.collection.database.client.close()


def build_handler() -> MongoHandler:
    import os
    from pymongo import MongoClient
    client = MongoClient(
        host=os.getenv("MONGO_HOST", "localhost"),
        port=int(os.getenv("MONGO_PORT", "27017")),
        username=os.getenv("MONGO_USER", "platform"),
        password=os.getenv("MONGO_PASSWORD", "change_me"),
    )
    collection = client[os.getenv("MONGO_DB", "terrain")]["alertes"]
    return MongoHandler(collection)


def main() -> None:
    setup_logging("consumer-mongo")
    run_consumer(build_handler(), bootstrap_servers(), log)


if __name__ == "__main__":
    main()
