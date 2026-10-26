"""Consumer Redis : meter-readings -> cache temps réel.

Rôle : tenir à jour le « maintenant » pour un dashboard / une API.
Respecte la convention de clés définie à l'étape 3 (sql/init/redis/README.md) :

  compteur:<id>:dernier          Hash   dernier relevé du compteur (+ TTL)
  region:<code>:conso_live       String kWh cumulés de la région sur l'heure courante
  region:<code>:compteurs_actifs Set    compteurs ayant émis récemment (+ TTL)

La conso live est RELATIVE À L'HEURE COURANTE : quand l'heure du relevé change,
on repart de zéro (sinon le cumul grossirait sans fin). On détecte le changement
d'heure via une clé qui mémorise l'heure en cours par région.
"""

import logging

from consumers.base import run_consumer, bootstrap_servers
from consumers.logging_setup import setup_logging

log = logging.getLogger("consumers.redis")

# Durées de vie (secondes). Le cache ne garde que le présent : une donnée qui
# n'est plus rafraîchie finit par disparaître plutôt que de « mentir ».
TTL_DERNIER = 6 * 3600          # un compteur muet depuis 6 h sort du cache
TTL_CONSO_LIVE = 2 * 3600       # marge au-delà de l'heure pour absorber le retard


class RedisHandler:
    group_id = "redis-live"
    topics = ["meter-readings"]

    def __init__(self, client):
        self.r = client

    def handle(self, msg: dict) -> None:
        compteur_id = msg["compteur_id"]
        region = msg.get("region_code", "inconnue")
        heure = msg["horodatage"][:13]     # "2026-10-26T12" : la tranche horaire

        pipe = self.r.pipeline()           # tout le traitement d'un message en 1 aller-retour

        # 1) Dernier relevé du compteur (hash) + TTL de fraîcheur.
        cle_dernier = f"compteur:{compteur_id}:dernier"
        pipe.hset(cle_dernier, mapping={
            "horodatage": msg["horodatage"],
            "energie_kwh": msg["energie_kwh"],
            "index_kwh": msg["index_kwh"],
            "tension_v": msg["tension_v"],
            "courant_a": msg["courant_a"],
        })
        pipe.expire(cle_dernier, TTL_DERNIER)

        # 2) Conso live de la région, remise à zéro au changement d'heure.
        cle_conso = f"region:{region}:conso_live"
        cle_heure = f"region:{region}:heure_courante"
        if self.r.get(cle_heure) != heure:
            # Nouvelle heure : on réinitialise le cumul et on mémorise l'heure.
            pipe.set(cle_heure, heure, ex=TTL_CONSO_LIVE)
            pipe.set(cle_conso, 0, ex=TTL_CONSO_LIVE)
        pipe.incrbyfloat(cle_conso, float(msg["energie_kwh"]))

        # 3) Compteurs actifs de la région (set), pour un décompte temps réel.
        cle_actifs = f"region:{region}:compteurs_actifs"
        pipe.sadd(cle_actifs, compteur_id)
        pipe.expire(cle_actifs, TTL_CONSO_LIVE)

        pipe.execute()

    def close(self) -> None:
        self.r.close()


def build_handler() -> RedisHandler:
    import os
    import redis
    client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        decode_responses=True,
    )
    return RedisHandler(client)


def main() -> None:
    setup_logging("consumer-redis")
    run_consumer(build_handler(), bootstrap_servers(), log)


if __name__ == "__main__":
    main()
