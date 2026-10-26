"""Producteur Kafka : émet les relevés et les alertes en temps réel.

Boucle : calcule un tick (tous les compteurs à l'instant t), publie chaque
relevé sur `meter-readings` et chaque alerte sur `meter-alerts`, attend un délai
aléatoire, avance d'une heure simulée, recommence.

Deux modes :
  - normal : publie réellement sur Kafka (nécessite le paquet kafka-python et un
    broker joignable) ;
  - --dry-run : n'ouvre PAS Kafka, affiche les événements à l'écran. Permet de
    tester le producteur SANS infrastructure (utile tant que Docker n'est pas là).

Le flux « avance » en temps simulé (une heure par tick) pour que les profils
jour/nuit soient visibles vite, tout en respectant une pause horloge réelle
entre deux envois (STREAM_MIN/MAX_INTERVAL).
"""

import argparse
import json
import logging
import os
import random
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from generator.logging_setup import setup_logging
from generator.streaming.meters import MeterFleet
from generator.streaming.tick import compute_tick, detect_alerts

log = logging.getLogger("generator.streaming")


def _latest_partition(entity_dir: Path, filename: str) -> Path:
    """Dernier fichier dt=... d'une entité du data lake."""
    parts = sorted(p for p in entity_dir.glob("dt=*") if p.is_dir())
    if not parts:
        raise FileNotFoundError(f"Aucune partition dans {entity_dir}")
    return parts[-1] / filename


class Emitter:
    """Destination des messages : Kafka en vrai, ou l'écran en --dry-run."""

    def __init__(self, dry_run: bool, bootstrap: str):
        self.dry_run = dry_run
        self.producer = None
        if not dry_run:
            # Import tardif : le --dry-run ne requiert pas kafka-python installé.
            try:
                from kafka import KafkaProducer
            except ImportError as exc:
                raise SystemExit(
                    "kafka-python n'est pas installé. Installez l'extra streaming "
                    "(pip install -e 'generator[streaming]') ou utilisez --dry-run."
                ) from exc
            self.producer = KafkaProducer(
                bootstrap_servers=bootstrap.split(","),
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
                # La clé = compteur_id : tous les relevés d'un compteur vont dans
                # la même partition Kafka, donc restent ORDONNÉS entre eux.
                key_serializer=lambda k: k.encode("utf-8"),
                acks="all",            # le broker confirme l'écriture (fiabilité)
                linger_ms=50,          # regroupe quelques messages (débit)
            )

    def send(self, topic: str, key: str, value: dict) -> None:
        if self.dry_run:
            print(f"[{topic}] {key} -> {json.dumps(value, ensure_ascii=False)}")
        else:
            self.producer.send(topic, key=key, value=value)

    def close(self) -> None:
        if self.producer is not None:
            self.producer.flush()
            self.producer.close()


def run(args) -> None:
    rng = np.random.default_rng(args.seed)
    data_root = Path(args.data_root)
    fleet = MeterFleet.from_datalake(
        _latest_partition(data_root / "compteurs", "compteurs.json"),
        _latest_partition(data_root / "clients", "clients.csv"),
        rng,
    )
    log.info("Parc chargé", extra={"fields": {"compteurs": len(fleet)}})

    topic_readings = os.getenv("KAFKA_TOPIC_READINGS", "meter-readings")
    topic_alerts = os.getenv("KAFKA_TOPIC_ALERTS", "meter-alerts")
    emitter = Emitter(args.dry_run, args.bootstrap)

    # Arrêt propre sur Ctrl-C : on vide le tampon Kafka avant de quitter.
    running = {"on": True}
    signal.signal(signal.SIGINT, lambda *_: running.update(on=False))

    # On démarre « maintenant » (heure pile) et on avance d'une heure par tick.
    moment = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    ticks_done = 0
    try:
        while running["on"]:
            readings = compute_tick(fleet, moment, rng)
            for r in readings:
                emitter.send(topic_readings, r["compteur_id"], r)
            alerts = detect_alerts(readings)
            for a in alerts:
                emitter.send(topic_alerts, a["compteur_id"], a)

            ticks_done += 1
            log.info("Tick émis", extra={"fields": {
                "horodatage": moment.isoformat(), "releves": len(readings),
                "alertes": len(alerts), "tick": ticks_done}})

            if args.max_ticks and ticks_done >= args.max_ticks:
                break
            moment += timedelta(hours=1)                      # temps simulé
            time.sleep(random.uniform(args.min_interval, args.max_interval))  # temps réel
    finally:
        emitter.close()
        log.info("Producteur arrêté", extra={"fields": {"ticks": ticks_done}})


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Producteur temps réel des relevés de compteurs.")
    parser.add_argument("--data-root", default="data/raw", help="racine du data lake (parc de compteurs)")
    parser.add_argument("--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
                        help="serveurs Kafka (host:port[,host:port])")
    parser.add_argument("--dry-run", action="store_true", help="afficher à l'écran au lieu d'envoyer sur Kafka")
    parser.add_argument("--max-ticks", type=int, help="s'arrêter après N ticks (utile pour tester)")
    parser.add_argument("--min-interval", type=float, default=float(os.getenv("STREAM_MIN_INTERVAL", "3")),
                        help="pause minimale entre deux ticks (s)")
    parser.add_argument("--max-interval", type=float, default=float(os.getenv("STREAM_MAX_INTERVAL", "10")),
                        help="pause maximale entre deux ticks (s)")
    parser.add_argument("--seed", type=int, default=42, help="graine aléatoire")
    args = parser.parse_args(argv)

    setup_logging("generator-streaming")
    run(args)


if __name__ == "__main__":
    sys.exit(main())
