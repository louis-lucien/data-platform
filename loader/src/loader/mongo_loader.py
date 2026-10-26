"""Chargement MongoDB : inspections terrain (documents à schéma variable).

On insère les documents JSON tels quels — c'est tout l'intérêt de MongoDB :
chaque inspection porte exactement ses champs (une fraude n'a pas les mêmes
clés qu'un contrôle conforme). Seule transformation nécessaire : convertir
`date_inspection` (chaîne ISO dans le JSON) en vrai type date BSON, pour que le
validateur de la collection (bsonType: 'date') l'accepte et qu'on puisse trier.
"""

from datetime import datetime

from pymongo import MongoClient

from loader.config import Settings
from loader.datalake import DataLake


def _client(cfg: Settings) -> MongoClient:
    return MongoClient(
        host=cfg.mongo_host, port=cfg.mongo_port,
        username=cfg.mongo_user, password=cfg.mongo_password,
    )


def load(cfg: Settings, lake: DataLake) -> dict[str, int]:
    inspections = lake.read_json("inspections")
    for doc in inspections:
        # ISO 8601 -> datetime (BSON date). fromisoformat gère "2026-08-27T13:12:00".
        doc["date_inspection"] = datetime.fromisoformat(doc["date_inspection"])
        # _id stable = inspection_id : rejouer le chargement ne crée pas de doublon.
        doc["_id"] = doc["inspection_id"]

    with _client(cfg) as client:
        coll = client[cfg.mongo_db]["inspections"]
        # replace_one(upsert) par _id : idempotent (relançable sans doublonner).
        for doc in inspections:
            coll.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    return {"inspections": len(inspections)}
