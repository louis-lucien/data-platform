# =============================================================================
#  Pilotage de la plateforme — raccourcis pour les scénarios courants
# =============================================================================
#  `make <cible>`. Sous Windows sans make, utiliser platform.ps1 (mêmes cibles).
#  Les profils Docker évitent de tout démarrer : on ne lance que le nécessaire.
# =============================================================================
.PHONY: help build up down reset generate load stream ml airflow ps logs smoke

help:            ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

build:           ## Construit les images applicatives (loader, etl, generator, consumers, ml, airflow)
	docker compose --profile load --profile stream --profile ml --profile airflow build

up:              ## Démarre le socle : 6 bases + Kafka + ELK + init automatiques
	docker compose up -d

down:            ## Arrête tout (conserve les données)
	docker compose --profile load --profile stream --profile ml --profile airflow down

reset:           ## Arrête tout et SUPPRIME les données (volumes) — repart de zéro
	docker compose --profile load --profile stream --profile ml --profile airflow down -v

generate:        ## Génère le data lake (hors Docker, via le venv local)
	python -m generator.batch --out data/raw

load:            ## Pipeline batch : charge les 6 bases, puis ETL vers le warehouse, puis vues BI
	docker compose --profile load up loader
	docker compose --profile load up etl
	docker compose --profile load up bi-init

stream:          ## Démarre le temps réel : producteur + consumers (Redis, Mongo)
	docker compose --profile stream up -d

ml:              ## Entraîne le détecteur d'anomalies puis score le parc
	docker compose --profile ml up ml-train
	docker compose --profile ml up ml-score

airflow:         ## Démarre Airflow (init + webserver + scheduler) — UI sur :8080
	docker compose --profile airflow up airflow-init
	docker compose --profile airflow up -d airflow-webserver airflow-scheduler

ps:              ## État et santé de tous les conteneurs
	docker compose --profile load --profile stream --profile ml --profile airflow ps

logs:            ## Suit les logs du socle
	docker compose logs -f

smoke:           ## Vérifie que chaque base répond (après `make up`)
	bash scripts/smoke_test.sh
