"""Tests de la LOGIQUE des consumers, sans Kafka ni base réelle.

On remplace Redis et MongoDB par des doubles (fakes) minimaux qui enregistrent
ce qu'on leur demande. Possible uniquement parce que la logique est isolée du
transport Kafka (voir consumers/base.py).
"""

import pytest

from consumers.redis_consumer import RedisHandler
from consumers.mongo_consumer import MongoHandler


# --------------------------------------------------------------------------- #
#  Faux Redis : un pipeline qui applique les commandes sur un dict en mémoire.
# --------------------------------------------------------------------------- #
class FakeRedis:
    def __init__(self):
        self.hashes: dict[str, dict] = {}
        self.strings: dict[str, str] = {}
        self.sets: dict[str, set] = {}
        self.expirations: dict[str, int] = {}

    def get(self, key):
        return self.strings.get(key)

    def pipeline(self):
        return FakePipeline(self)

    def close(self):
        pass


class FakePipeline:
    def __init__(self, store: FakeRedis):
        self.s = store

    def hset(self, key, mapping):
        self.s.hashes.setdefault(key, {}).update(mapping)

    def expire(self, key, ttl):
        self.s.expirations[key] = ttl

    def set(self, key, value, ex=None):
        self.s.strings[key] = str(value)

    def incrbyfloat(self, key, amount):
        self.s.strings[key] = str(float(self.s.strings.get(key, 0)) + amount)

    def sadd(self, key, member):
        self.s.sets.setdefault(key, set()).add(member)

    def execute(self):
        pass


def _reading(compteur="CPT-1", region="SN-DK", heure="2026-10-26T12", energie=1.5):
    return {"compteur_id": compteur, "region_code": region,
            "horodatage": f"{heure}:00:00+00:00", "energie_kwh": energie,
            "index_kwh": 100.0, "tension_v": 230.0, "courant_a": 6.5}


def test_redis_writes_last_reading_with_ttl():
    r = FakeRedis()
    RedisHandler(r).handle(_reading())
    assert r.hashes["compteur:CPT-1:dernier"]["energie_kwh"] == 1.5
    assert r.expirations["compteur:CPT-1:dernier"] > 0        # TTL posé


def test_redis_accumulates_region_consumption():
    r = FakeRedis()
    h = RedisHandler(r)
    h.handle(_reading(compteur="CPT-1", energie=1.0))
    h.handle(_reading(compteur="CPT-2", energie=2.5))
    # Deux compteurs, même heure, même région -> cumul.
    assert float(r.strings["region:SN-DK:conso_live"]) == pytest.approx(3.5)
    assert r.sets["region:SN-DK:compteurs_actifs"] == {"CPT-1", "CPT-2"}


def test_redis_resets_consumption_on_new_hour():
    r = FakeRedis()
    h = RedisHandler(r)
    h.handle(_reading(heure="2026-10-26T12", energie=5.0))
    assert float(r.strings["region:SN-DK:conso_live"]) == pytest.approx(5.0)
    # L'heure change -> le cumul repart de zéro, pas d'empilement.
    h.handle(_reading(heure="2026-10-26T13", energie=2.0))
    assert float(r.strings["region:SN-DK:conso_live"]) == pytest.approx(2.0)


# --------------------------------------------------------------------------- #
#  Faux Mongo : une collection qui garde les documents insérés dans une liste.
# --------------------------------------------------------------------------- #
class FakeCollection:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        self.docs.append(doc)


def test_mongo_inserts_alert_with_reception_time():
    coll = FakeCollection()
    MongoHandler(coll).handle({
        "compteur_id": "CPT-9", "horodatage": "2026-10-26T20:00:00+00:00",
        "type_alerte": "tension_hors_bornes", "valeur": 260.0, "region_code": "SN-DK",
    })
    assert len(coll.docs) == 1
    doc = coll.docs[0]
    assert doc["type_alerte"] == "tension_hors_bornes"
    assert "recu_le" in doc                      # horodatage d'ingestion ajouté
    assert "horodatage_dt" in doc                # chaîne ISO convertie en date


def test_mongo_handles_alert_without_timestamp():
    coll = FakeCollection()
    MongoHandler(coll).handle({"compteur_id": "CPT-9", "type_alerte": "conso_nulle"})
    assert coll.docs[0]["type_alerte"] == "conso_nulle"   # pas de crash sans horodatage
