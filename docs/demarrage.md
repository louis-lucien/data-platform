# Démarrage de la plateforme (étapes 3 & 4)

> Ce guide suppose **Docker Desktop déjà installé et fonctionnel**. Si vous
> partez d'une machine où C: est saturé (le cas du poste de développement
> initial), suivez d'abord [installation-docker.md](installation-docker.md)
> pour rediriger tout le stockage vers un autre disque.

## Vue d'ensemble

`docker compose up` démarre **6 bases** et les initialise automatiquement. Un
**7e conteneur jetable** (`init`) applique les schémas Cassandra et Neo4j (les
seules bases sans auto-init), puis s'arrête. Un **8e conteneur** (`loader`),
lancé à la demande, charge les données de `data/raw/` dans les 6 bases.

```
docker compose up -d            →  postgres, mysql, cassandra, mongo, neo4j, redis
                                   + init (applique les schémas Cassandra/Neo4j, puis s'arrête)

docker compose --profile load up loader
                                →  charge data/raw dans les 6 bases, puis s'arrête
```

## Prérequis

1. **Docker Desktop** installé et démarré (`docker version` répond).
2. **Les données générées** présentes dans `data/raw/`. Si ce n'est pas le cas :
   ```bash
   python -m venv .venv && .venv/Scripts/activate
   pip install -e "generator[dev]"
   python -m generator.batch --out data/raw
   ```

## Étape 1 — Configurer les secrets

```bash
cp .env.example .env
```

Ouvrez `.env` et **changez tous les `change_me`** par de vrais mots de passe.

> ⚠️ Pour Neo4j, le mot de passe se **fige au premier démarrage** du conteneur.
> Si vous le changez plus tard dans `.env`, il faudra réinitialiser le volume
> (`docker compose down -v`) pour que le nouveau soit pris en compte.

## Étape 2 — Démarrer les bases

```bash
docker compose up -d
```

Surveillez l'initialisation (Cassandra met ~1 min, c'est normal) :

```bash
docker compose ps                 # santé de chaque conteneur
docker compose logs -f init       # suit l'application des schémas Cassandra/Neo4j
```

Le conteneur `energy-init` doit finir avec « Initialisation terminee avec
succes » puis passer en `Exited (0)` — **c'est voulu**, il a fini son travail.

## Étape 3 — Charger les données

Une fois toutes les bases **saines** (`docker compose ps` les montre `healthy`) :

```bash
docker compose --profile load up loader
```

Le conteneur `loader` attend que tout soit prêt, charge les 6 bases, affiche un
récapitulatif par table, puis s'arrête. Le relancer est **sans danger** : tous
les chargeurs sont idempotents (ils ne créent pas de doublons).

> Le chargement des relevés dans Cassandra (~1,4 M de lignes) est le plus long.
> Le log affiche la progression jour par jour.

### Charger une seule base (débogage)

```bash
docker compose run --rm loader --only postgres
docker compose run --rm loader --only cassandra
```

## Étape 4 — Vérifier

```bash
# PostgreSQL : compter clients et compteurs
docker compose exec postgres psql -U platform -d energy \
  -c "SELECT (SELECT count(*) FROM oltp.clients) AS clients,
             (SELECT count(*) FROM oltp.compteurs) AS compteurs;"

# MySQL : recharges + factures
docker compose exec mysql mysql -u platform -p billing \
  -e "SELECT (SELECT count(*) FROM recharges) AS recharges,
             (SELECT count(*) FROM factures) AS factures;"

# Cassandra : relevés d'un compteur sur un jour
docker compose exec cassandra cqlsh -e \
  "SELECT count(*) FROM releves.releves_par_compteur
   WHERE compteur_id='CPT-10000001' AND jour='2026-08-27';"

# MongoDB : inspections par résultat
docker compose exec mongo mongosh terrain --quiet \
  --eval "db.inspections.countDocuments({resultat:'fraude_confirmee'})"

# Neo4j : impact d'une panne de poste (compteurs en aval)
docker compose exec neo4j cypher-shell -u neo4j -p <mdp> \
  "MATCH (:PosteSource {poste_id:'PS-DK-01'})-[:ALIMENTE*]->(c:Compteur) RETURN count(c);"

# Redis : dernier relevé amorcé d'un compteur
docker compose exec redis redis-cli HGETALL compteur:CPT-10000001:dernier
```

## Lancer tout d'un coup

```bash
docker compose up -d && docker compose --profile load up loader
```

## Arrêt / remise à zéro

```bash
docker compose down        # arrête, GARDE les données
docker compose down -v     # arrête, SUPPRIME les données (repart de zéro)
```
