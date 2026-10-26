"""Squelette commun à tous les consumers : la plomberie Kafka.

On sépare volontairement deux choses :
  - le TRANSPORT (se connecter à Kafka, boucler, décoder le JSON, committer) —
    ici, générique, écrit une seule fois ;
  - la LOGIQUE (que faire d'un message) — propre à chaque consumer, passée sous
    forme d'un objet « handler ».

Avantage : la logique de chaque consumer est testable SANS Kafka (on appelle
`handler.handle(message)` directement), et la plomberie n'est jamais dupliquée.
"""

import json
import logging
import os
import signal
from typing import Protocol


class Handler(Protocol):
    """Contrat d'un traitement de messages. Chaque consumer en fournit un."""

    group_id: str          # groupe Kafka (deux groupes lisent chacun TOUT le flux)
    topics: list[str]      # topics auxquels s'abonner

    def handle(self, message: dict) -> None:
        """Traite un message déjà décodé (dict). Peut lever : la boucle loguera."""
        ...

    def close(self) -> None:
        """Libère les ressources (connexion base...)."""
        ...


def run_consumer(handler: Handler, bootstrap: str, log: logging.Logger) -> None:
    """Boucle de consommation : lit les topics du handler et lui passe chaque message.

    enable_auto_commit=False : on ne confirme la lecture d'un message qu'APRÈS
    l'avoir traité avec succès. Si le consumer plante en plein traitement, le
    message sera relu au redémarrage (sémantique « au moins une fois »).
    """
    from kafka import KafkaConsumer

    consumer = KafkaConsumer(
        *handler.topics,
        bootstrap_servers=bootstrap.split(","),
        group_id=handler.group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",     # au premier lancement, repartir du début
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        key_deserializer=lambda k: k.decode("utf-8") if k else None,
    )
    log.info("Consumer démarré", extra={"fields": {
        "groupe": handler.group_id, "topics": handler.topics}})

    running = {"on": True}
    signal.signal(signal.SIGINT, lambda *_: running.update(on=False))
    signal.signal(signal.SIGTERM, lambda *_: running.update(on=False))

    processed = 0
    try:
        while running["on"]:
            # poll : récupère un lot de messages, ou rien au bout du timeout.
            batch = consumer.poll(timeout_ms=1000)
            for _partition, records in batch.items():
                for record in records:
                    try:
                        handler.handle(record.value)
                        processed += 1
                    except Exception as exc:
                        # On loggue et on continue : un message malformé ne doit
                        # pas bloquer tout le flux. (En prod : file morte / DLQ.)
                        log.error("Message ignoré", extra={"fields": {
                            "erreur": f"{type(exc).__name__}: {exc}"}})
            if batch:
                consumer.commit()         # on confirme le lot une fois traité
    finally:
        consumer.close()
        handler.close()
        log.info("Consumer arrêté", extra={"fields": {"traites": processed}})


def bootstrap_servers() -> str:
    """Adresse des brokers Kafka, depuis l'environnement (défaut : hôte local)."""
    return os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
