"""DAG d'ingestion batch : orchestre le remplissage des bases à partir du data lake.

Un DAG (Directed Acyclic Graph) décrit des tâches et leurs dépendances. Ici,
l'enchaînement métier est simple et linéaire :

    [charger les 6 bases]  ->  [ (futur) ETL vers le Data Warehouse ]

CHOIX D'ARCHITECTURE : chaque tâche lance un CONTENEUR déjà construit
(DockerOperator), au lieu d'exécuter le code Python dans Airflow lui-même.
Airflow ORCHESTRE (quand, dans quel ordre, relancer si échec) ; le code métier
reste dans ses paquets (loader/, etl/). Avantages : image Airflow légère, pas de
duplication, chaque tâche isolée dans son conteneur.

Prérequis côté exécution : les images `energy-loader` (et plus tard `energy-etl`)
doivent avoir été construites (`docker compose build loader`), et le data lake
doit exister (générateur lancé). La génération n'est PAS dans ce DAG : on part
du principe que les données sources existent déjà (comme un vrai système source).
"""

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

# Réseau Docker du projet : les conteneurs lancés par les tâches doivent pouvoir
# joindre les bases (postgres, mysql...). On les attache donc au réseau du compose.
# Compose nomme le réseau "<dossier>_default" ; paramétrable via l'environnement.
PROJECT_NETWORK = os.getenv("COMPOSE_PROJECT_NETWORK", "data-platform_default")

# Chemin ABSOLU du data lake SUR L'HÔTE. Piège du DockerOperator : le bind mount
# est résolu par le démon Docker (donc côté hôte), PAS dans le conteneur Airflow.
# On passe donc le chemin hôte explicitement (injecté par le compose).
HOST_DATA_RAW = os.getenv("HOST_DATA_RAW", "/data/raw")

# Les variables de connexion aux bases, passées aux conteneurs de tâches. Elles
# reprennent les noms de service comme hôtes (réseau Docker interne).
DB_ENV = {
    "DATA_ROOT": "/data/raw",
    "POSTGRES_HOST": "postgres", "MYSQL_HOST": "mysql", "CASSANDRA_HOST": "cassandra",
    "MONGO_HOST": "mongo", "NEO4J_URI": "bolt://neo4j:7687", "REDIS_HOST": "redis",
    # Les secrets (mots de passe, noms de bases) sont relayés depuis
    # l'environnement du scheduler Airflow (injectés par le compose, cf. .env).
    "POSTGRES_DB": os.getenv("POSTGRES_DB", "energy"),
    "POSTGRES_USER": os.getenv("POSTGRES_USER", "platform"),
    "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
    "DW_DB": os.getenv("DW_DB", "warehouse"),
    "MYSQL_DATABASE": os.getenv("MYSQL_DATABASE", "billing"),
    "MYSQL_USER": os.getenv("MYSQL_USER", "platform"),
    "MYSQL_PASSWORD": os.getenv("MYSQL_PASSWORD", ""),
    "MONGO_USER": os.getenv("MONGO_USER", "platform"),
    "MONGO_PASSWORD": os.getenv("MONGO_PASSWORD", ""),
    "NEO4J_AUTH": os.getenv("NEO4J_AUTH", "neo4j/change_me_neo4j"),
}

default_args = {
    "owner": "data-platform",
    "retries": 2,                          # une tâche qui échoue est relancée 2 fois
    "retry_delay": timedelta(minutes=2),   # ... avec 2 min d'écart (laisse le temps aux bases)
}

with DAG(
    dag_id="batch_ingestion",
    description="Charge le data lake dans les 6 bases, puis (à venir) lance l'ETL.",
    default_args=default_args,
    # Tous les jours à 2 h du matin (heure creuse). None = lancement manuel seulement.
    schedule="0 2 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,                         # ne pas rattraper les jours passés
    tags=["batch", "ingestion"],
) as dag:

    # Paramètres communs à toutes les tâches DockerOperator.
    docker_common = dict(
        docker_url="unix://var/run/docker.sock",   # démon Docker de l'hôte (socket monté)
        network_mode=PROJECT_NETWORK,              # pour joindre les bases
        auto_remove="success",                     # conteneur supprimé si succès
        mount_tmp_dir=False,                       # requis quand le démon n'est pas "local" à Airflow
        # Bind mount du data lake (source = chemin HÔTE, cf. HOST_DATA_RAW).
        mounts=[Mount(source=HOST_DATA_RAW, target="/data/raw",
                      type="bind", read_only=True)],
    )

    # -- Tâche 1 : charger les 6 bases depuis le data lake --------------------
    charger_bases = DockerOperator(
        task_id="charger_bases",
        image="energy-loader:latest",
        environment=DB_ENV,
        **docker_common,
    )

    # -- Tâche 2 : ETL vers le Data Warehouse (étape 9) -----------------------
    # Lit les sources remplies par la tâche 1, nettoie/agrège, écrit le warehouse.
    # L'ETL n'a pas besoin du bind mount du data lake (il lit les BASES, pas les
    # fichiers) : on redéfinit les paramètres Docker sans le mount.
    lancer_etl = DockerOperator(
        task_id="lancer_etl",
        image="energy-etl:latest",
        environment=DB_ENV,
        docker_url="unix://var/run/docker.sock",
        network_mode=PROJECT_NETWORK,
        auto_remove="success",
        mount_tmp_dir=False,
    )

    # L'ETL ne démarre qu'APRÈS le chargement réussi des bases sources.
    charger_bases >> lancer_etl
