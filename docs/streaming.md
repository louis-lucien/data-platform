# Flux temps réel : producteur Kafka (étape 5)

## L'idée en une phrase

Jusqu'ici tout était **batch** (un gros paquet d'un coup). Le producteur ajoute
le **temps réel** : les compteurs continuent d'émettre des relevés, en continu,
sur un **bus d'événements Kafka**, comme le feraient de vrais compteurs
intelligents.

## Pourquoi Kafka (et pas écrire direct dans les bases) ?

Kafka est un **tapis roulant** entre ceux qui produisent des événements et ceux
qui les consomment :

- le producteur ne sait pas (et n'a pas à savoir) qui lira : **découplage** ;
- si un lecteur tombe ou prend du retard, les messages **restent** dans Kafka ;
- **plusieurs** lecteurs peuvent traiter le même flux différemment (Redis pour
  le direct, Elasticsearch pour le monitoring, détection d'alertes…).

Deux topics (deux « files ») :

| Topic | Contenu |
|---|---|
| `meter-readings` | chaque relevé horaire de chaque compteur |
| `meter-alerts` | anomalies détectées (tension hors bornes, consommation nulle) |

## Le point fort : cohérence batch ↔ temps réel

Le producteur **réutilise le modèle physique du batch** (`generator.consumption` :
profils horaires, effet température, bruit). Les relevés temps réel **prolongent**
l'historique : mêmes compteurs (lus depuis `data/raw/compteurs.json`), même
« personnalité » de consommation, index cumulé qui reprend là où il en était.
Un professionnel consomme plus en journée, un ménage le soir — en live comme en
batch.

## Tester SANS Kafka (mode dry-run)

Tant que Docker/Kafka ne tournent pas, on peut voir le flux à l'écran :

```bash
pip install -e "generator[streaming]"     # ou, pour le dry-run seul, sans extra
python -m generator.streaming.producer --dry-run --max-ticks 3 \
       --min-interval 0 --max-interval 0
```

Chaque ligne `[meter-readings] CPT-... -> {...}` est un message qui PARTIRAIT sur
Kafka. `--max-ticks` limite le nombre de cycles ; sans lui, le flux est infini
(Ctrl-C pour arrêter proprement).

## Lancer le vrai flux (avec Docker)

```bash
docker compose up -d                        # démarre Kafka + crée les topics
docker compose --profile stream up producer # lance le producteur sur Kafka
```

Le producteur tourne en continu. Pour observer ce qui circule dans un topic :

```bash
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 --topic meter-readings --from-beginning --max-messages 5
```

## Comment « avance » le temps

Pour voir vite les profils jour/nuit, le producteur avance d'**une heure simulée
par tick**, tout en respectant une **pause horloge réelle** de quelques secondes
entre deux ticks (réglable : `STREAM_MIN_INTERVAL` / `STREAM_MAX_INTERVAL`). En
quelques minutes, on parcourt donc une journée entière de consommation.

## Les consumers (étape 6)

Un consumer **lit** un topic et en fait quelque chose. Chaque consumer appartient
à un **groupe** distinct : deux groupes lisent chacun l'INTÉGRALITÉ du flux (ils
ne se partagent pas les messages). C'est ce qui permet à plusieurs usages de
traiter les mêmes relevés indépendamment.

| Consumer | Groupe | Lit | Fait quoi |
|---|---|---|---|
| `consumer-redis` | `redis-live` | `meter-readings` | dernier relevé + conso live/région dans Redis |
| `consumer-mongo` | `mongo-alertes` | `meter-alerts` | historise chaque alerte dans MongoDB |

> Elasticsearch sera alimenté par **Logstash** à l'étape 7 (stack ELK), comme le
> montre le schéma d'architecture — pas par un consumer Python.

### Lancer la chaîne temps réel complète

Le profil `stream` démarre le producteur ET les deux consumers d'un coup :

```bash
docker compose up -d                          # bases + Kafka + topics
docker compose --profile stream up            # producteur + consumer-redis + consumer-mongo
```

### Vérifier de bout en bout

```bash
# Redis : dernier relevé d'un compteur, mis à jour en direct
docker compose exec redis redis-cli HGETALL compteur:CPT-10000001:dernier
# Redis : consommation live d'une région sur l'heure courante
docker compose exec redis redis-cli GET region:SN-DK:conso_live

# MongoDB : alertes reçues
docker compose exec mongo mongosh terrain --quiet \
  --eval "db.alertes.find().sort({recu_le:-1}).limit(3).toArray()"
```

### Tester la logique SANS Kafka

La logique de chaque consumer est isolée du transport Kafka (`consumers/base.py`),
donc testable avec de faux Redis/Mongo :

```bash
pip install -e "consumers[dev]"
pytest consumers
```

## Fiabilité : « au moins une fois »

Les consumers ne confirment (`commit`) un lot de messages qu'APRÈS l'avoir traité.
Si un consumer plante en plein traitement, les messages non confirmés seront
relus au redémarrage : on ne perd pas de données (quitte à en retraiter).
