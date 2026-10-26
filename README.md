# Plateforme de données Énergie — Compteurs intelligents (Batch & Temps réel)

Plateforme complète de traitement de données d'un distributeur d'électricité :
relevés de compteurs intelligents en temps réel, gestion clients et facturation,
topologie du réseau électrique, détection d'anomalies (fraude, pannes).

Génération, ingestion multi-sources, streaming Kafka, orchestration Airflow,
Data Warehouse PostgreSQL, monitoring ELK, exploitation BI / Machine Learning.
Entièrement dockerisée.

## Cas d'usage métier

| Besoin | Réponse de la plateforme |
|---|---|
| Suivre la consommation en direct | Relevés compteurs via Kafka → Redis / Kibana |
| Analyser la consommation par zone et par heure | Data Warehouse + Power BI |
| Détecter fraudes et anomalies | Modèle ML sur l'historique de consommation |
| Comprendre l'impact d'un incident réseau | Graphe Neo4j : poste → transformateur → compteur |

## Architecture

```
SOURCES (Faker · Scraping Wikipédia · API météo Open-Meteo)
   │ batch (1x/h)                     │ streaming (3-10 s)
   ▼                                  ▼
Fichiers CSV/JSON/XLSX/XML/YAML     Kafka ── consumers ──► Redis · MongoDB · Elasticsearch
PostgreSQL · MySQL · MongoDB                                         │
Cassandra · Neo4j                                          Logstash ─┤
   │                                                                 ▼
   └──► Airflow (ETL) ──► PostgreSQL Data Warehouse            Kibana (monitoring)
                                   │
                                   ▼
                          Power BI · Modèle ML
```

## Structure du dépôt

| Dossier | Rôle |
|---|---|
| `generator/` | Production des données : génération Faker, scraping, appels API + producteur Kafka temps réel (`generator/streaming/`) |
| `loader/` | Chargement de `data/raw` vers les 6 bases (PostgreSQL, MySQL, Cassandra, MongoDB, Neo4j, Redis) |
| `consumers/` | Consommateurs Kafka : relevés → Redis (live), alertes → MongoDB (Elastic via Logstash à l'étape 7) |
| `etl/` | ETL : sources (OLTP + Cassandra) → Data Warehouse, avec nettoyage/dédoublonnage |
| `airflow/` | Orchestration batch : DAGs + image Airflow dérivée (DockerOperator) |
| `sql/init/` | Scripts de création des schémas (sources + Data Warehouse) |
| `sql/analytics/` | Requêtes d'analyse d'exemple sur le schéma en étoile |
| `scripts/init/` | Conteneur jetable d'init (applique les schémas Cassandra/Neo4j) |
| `docs/` | Guides d'installation Docker et de démarrage |
| `config/logstash/` | Pipeline Logstash (Kafka → Elasticsearch) |
| `config/kibana/` | Pré-configuration Kibana (data views) |
| `ml/` | Détection d'anomalies : features (DW) + étiquettes (inspections), entraînement, scoring |
| `bi/` | Vues SQL (couche sémantique Power BI) + dashboard HTML de démonstration |
| `docs/` | Schéma d'architecture, rapport technique |
| `data/` | Fichiers générés localement (non versionnés) |

## Démarrage rapide

```bash
cp .env.example .env     # puis changer les mots de passe

# Pilote unique (make, ou .\platform.ps1 sous Windows) :
make build               # construit les images applicatives
make generate            # génère le data lake
make up                  # démarre le socle (bases + Kafka + ELK)
make load                # charge les bases + ETL + vues BI
make stream              # temps réel (producteur + consumers)
make ml                  # entraîne + score la détection d'anomalies
```

Guides : [exploitation complète](docs/exploitation-complete.md) ·
[démarrage](docs/demarrage.md) ·
[installation Docker si C: saturé](docs/installation-docker.md).

### Installation Python (tout le projet, sans Docker)

```bash
python -m venv .venv && .venv/Scripts/activate      # Linux/Mac : source .venv/bin/activate
pip install -r requirements.txt                     # toutes les dépendances des 5 paquets
```

### Générateur batch (sans Docker)

```bash
python -m generator.batch --out data/raw            # 1 000 clients, 60 jours d'historique
python -m generator.batch --clients 100 --days 5 --offline   # test rapide sans réseau
pytest generator                                     # tests automatisés
```

| Fichier produit | Format | Système simulé |
|---|---|---|
| `regions` | CSV | Scraping Wikipédia (superficie, population) |
| `meteo` | JSON | API Open-Meteo (température, humidité horaires) |
| `reseau` | XML | Export SIG : région > poste source > transformateur |
| `clients` | CSV | Export CRM (avec défauts de qualité volontaires) |
| `compteurs` | JSON | Plateforme de gestion des compteurs |
| `facturation` | Excel | Service financier : recharges prépayées + factures postpayées |
| `tarifs` | YAML | Grille tarifaire (fictive) |
| `inspections` | JSON | Application des techniciens terrain (étiquettes ML) |
| `releves` | CSV / jour | Historique horaire des compteurs |

Chaque exécution écrit un manifeste dans `data/raw/_runs/` (volumes, sources, période).

## Avancement

- [x] Étape 1 — Planification & architecture
- [x] Étape 2 — Génération de données (Faker, scraping, API, multi-formats)
- [x] Étape 3 — Stockage multi-bases *(schémas des 6 bases + chargeur `loader/` data lake → bases, 6 tests)*
- [x] Étape 4 — Dockerisation des bases *(docker-compose 6 bases + conteneur `init` (schémas Cassandra/Neo4j) + conteneur `loader` ; guides [docs/](docs/) ; validé hors exécution, à lancer sur une machine avec Docker)*
- [x] Étape 5 — Producteur Kafka *(flux temps réel réutilisant `consumption.py` ; topics `meter-readings`/`meter-alerts` ; mode `--dry-run` testable sans Docker ; Kafka KRaft + topics dans le compose ; [docs/streaming.md](docs/streaming.md))*
- [x] Étape 6 — Consumers Kafka *(relevés → Redis cache live, alertes → MongoDB ; squelette commun testable sans Kafka, 5 tests ; services dans le compose, profil `stream`)*
- [x] Étape 7 — Stack ELK *(Elasticsearch + Logstash + Kibana ; pipeline Kafka → index `releves-*`/`alertes-*` ; data views Kibana auto ; sécurité désactivée en dev ; [docs/monitoring-elk.md](docs/monitoring-elk.md))*
- [x] Étape 8 — Orchestration Airflow *(DAG `batch_ingestion` via DockerOperator ; Airflow 2.10.5 LocalExecutor + métabase dédiée ; place prête pour l'ETL ; profil `airflow` ; [docs/orchestration-airflow.md](docs/orchestration-airflow.md))*
- [x] Étape 9 — Data Warehouse *(schéma en étoile dim/fait, 2 grains horaire+jour ; ETL E-T-L avec dédoublonnage clients (1010→1000) et agrégation ; 6 tests ; tâche Airflow activée ; [docs/data-warehouse.md](docs/data-warehouse.md))*
- [x] Étape 10 — BI / ML *(BI : vues SQL + dashboard HTML sur données réelles. ML : features DW + étiquettes inspections → RandomForest binaire évalué precision/recall, scoring du parc. 7 tests ; [docs/bi-ml.md](docs/bi-ml.md))*
- [x] Étape 11 — Dockerisation complète *(25 services en 5 profils ; pilote unique `make`/`platform.ps1` ; smoke test des 10 bases ; tags d'images cohérents avec le DAG ; [docs/exploitation-complete.md](docs/exploitation-complete.md))*
- [x] Étape 12 — Rapport *(rapport technique et pédagogique à deux niveaux : [docs/rapport.pdf](docs/rapport.pdf), régénérable depuis [docs/rapport.html](docs/rapport.html) via `scripts/build_rapport_pdf.sh`)*
