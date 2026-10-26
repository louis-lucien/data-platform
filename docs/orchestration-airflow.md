# Orchestration des traitements batch avec Airflow (étape 8)

## L'idée en une phrase

Airflow **automatise et enchaîne** les traitements batch qu'on lançait à la main
(charger les bases, demain lancer l'ETL), à heure fixe, dans le bon ordre, avec
reprise en cas d'échec.

## DAG : le graphe des tâches

Un **DAG** (Directed Acyclic Graph) décrit des tâches et leurs dépendances. Le
nôtre ([airflow/dags/batch_ingestion.py](../airflow/dags/batch_ingestion.py)) :

```
[charger_bases]  ->  [ lancer_etl  (étape 9, en attente) ]
```

« Acyclique » = aucune boucle : une tâche ne peut pas dépendre d'elle-même.
Airflow en déduit l'ordre d'exécution et ce qui peut tourner en parallèle.

La tâche ETL est **déjà prévue** dans le code (commentée) : quand l'image
`energy-etl` existera (étape 9), on l'active et on branche la dépendance
`charger_bases >> lancer_etl`. On pose le chef d'orchestre avant la partition.

## Comment une tâche s'exécute : DockerOperator

Chaque tâche **lance un conteneur déjà construit** (ex. `energy-loader`) au lieu
d'exécuter le code dans Airflow. C'est un choix d'architecture important :

- Airflow **orchestre** (quand, ordre, reprise) ; le code métier reste dans ses
  paquets (`loader/`, `etl/`). Pas de duplication.
- L'image Airflow reste **légère** : pas besoin d'y installer pandas ni les 6
  drivers de base.
- Chaque tâche est **isolée** dans son conteneur.

Mécanisme : Airflow pilote le **démon Docker de l'hôte** via le socket
`/var/run/docker.sock` (monté dans les conteneurs Airflow). Il demande « lance
`energy-loader` », attend la fin, et marque la tâche réussie/échouée selon le
code de sortie.

> ⚠️ Monter le socket Docker donne à Airflow un contrôle quasi-root sur l'hôte.
> Acceptable en dev local ; en production on utilise des approches plus confinées
> (Docker-in-Docker isolé, exécuteur Kubernetes...).

## Architecture Docker (minimale, dev)

| Service | Rôle |
|---|---|
| `airflow-postgres` | base de **métadonnées** d'Airflow (DÉDIÉE, séparée du Postgres métier) |
| `airflow-init` | migrations + création de l'utilisateur admin, puis s'arrête |
| `airflow-webserver` | l'interface web (http://localhost:8080) |
| `airflow-scheduler` | déclenche les tâches selon le planning |

- **LocalExecutor** : les tâches tournent sur la même machine, pas besoin de
  Celery ni de Redis (inutiles à cette échelle).
- Airflow **2.10.5** : dernière 2.x stable, architecture classique bien
  documentée.

## Démarrer Airflow

```bash
# 1) Construire l'image Airflow dérivée + initialiser la base (une fois)
docker compose --profile airflow build
docker compose --profile airflow up airflow-init

# 2) Lancer le webserver + le scheduler
docker compose --profile airflow up -d airflow-webserver airflow-scheduler
```

Ouvrir **http://localhost:8080** (identifiants : `admin` / `admin`).

## Lancer le DAG

Dans l'UI, le DAG `batch_ingestion` apparaît (en pause par défaut). Activez-le
avec l'interrupteur, puis « Trigger DAG » pour un lancement immédiat, ou laissez
le planning (tous les jours à 2 h) s'en charger.

> Prérequis : l'image `energy-loader` doit être construite
> (`docker compose build loader`) et le data lake doit exister (générateur lancé).

## Vérifier

- **Graph view** / **Grid view** dans l'UI : l'état de chaque tâche (vert = OK).
- **Logs** d'une tâche : clic sur la tâche → Logs (on y voit la sortie du
  conteneur `energy-loader`, dont le récapitulatif par base).

## Dépannage ciblé

| Symptôme | Cause probable | Solution |
|---|---|---|
| Tâche échoue : `permission denied` sur `/var/run/docker.sock` | droits socket | le service tourne en `user: "50000:0"` (groupe root) ; sur certains hôtes, ajuster les droits du socket |
| `Mount source path ... does not exist` | `HOST_DATA_RAW` relatif mal résolu | mettre un chemin **absolu** dans `.env` |
| Conteneur de tâche ne joint pas les bases | mauvais réseau | vérifier `COMPOSE_PROJECT_NETWORK` (= `<dossier>_default`) |
| DAG absent de l'UI | erreur d'import | voir les logs du scheduler |
