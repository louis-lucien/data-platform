# Data Warehouse & ETL (étape 9)

## L'idée en une phrase

Le Data Warehouse est une base **unique, nettoyée et modélisée pour l'analyse**,
alimentée par l'**ETL** qui extrait des sources, corrige les défauts, et agrège.

## OLTP vs Data Warehouse : deux mondes

| | OLTP (base `energy`) | Data Warehouse (base `warehouse`) |
|---|---|---|
| Usage | quotidien (écritures unitaires) | analyse (lectures agrégées) |
| Modèle | normalisé (3NF, anti-duplication) | **étoile** (dénormalisé pour la vitesse) |
| Données | brutes, avec défauts | **nettoyées** |

Les deux vivent sur le même serveur Postgres mais dans des **bases séparées**.

## Le schéma en étoile

```
        dim_temps                        dim_region
            \                               /
             \                             /
   fait_consommation_horaire  +  fait_consommation_jour
             /                             \
            /                               \
      dim_compteur  ───────────────────  dim_client
```

- **Dimensions** = les axes d'analyse (quand ? où ? qui ? quel compteur ?).
- **Faits** = les mesures (la consommation), reliées aux dimensions.
- **Deux grains de faits** (couches de granularité) :
  - `fait_consommation_horaire` : grain fin, **source de vérité** ;
  - `fait_consommation_jour` : **agrégat** dérivé (somme/jour), rapide pour la BI.

L'agrégat ne remplace pas le détail : il l'accélère. Une analyse mensuelle lit
`fait_consommation_jour` (60 000 lignes) au lieu de 1,4 M lignes horaires.

Schéma SQL : [sql/init/warehouse/01_schema_warehouse.sql](../sql/init/warehouse/01_schema_warehouse.sql).

## L'ETL : Extract → Transform → Load

Code : [etl/](../etl/src/etl/). Le point clé est le **Transform** — c'est là que
les défauts VOLONTAIRES des sources (promis depuis l'étape 2) sont enfin corrigés.

### Le nettoyage des clients (dédoublonnage)

La source contient 1010 clients, dont **10 doublons injectés** : le générateur a
recopié 10 clients existants sous un nouveau `client_id`, nom en MAJUSCULES.

- **Signature fiable d'un doublon** : même `email` ET même `date_inscription`
  qu'une autre ligne. (Les homonymes légitimes — `Adama Ba` à Dakar, fréquent —
  ont des emails/dates différents : ils sont **conservés**.)
- On garde l'original (plus petit `client_id`), on supprime la copie.
- On normalise les noms en casse titre (`DIATTA` → `Diatta`).

Résultat : **1000 clients uniques** dans `dim_client`.

### L'agrégation des relevés

Les relevés horaires (Cassandra) deviennent `fait_consommation_jour` :
- `energie_kwh` = **somme** des 24 heures (mesure *additive*) ;
- `tension/courant` = **moyennes** (mesures *non additives* : on ne somme pas des
  tensions !) ;
- `nb_releves` = combien d'heures remontées (24 attendu ; moins = données
  manquantes — un indicateur de qualité).

## Lancer l'ETL

### Via Docker (à la main)

```bash
docker compose --profile load up loader   # 1) remplir les sources
docker compose --profile load up etl      # 2) sources -> warehouse
```

### Via Airflow (orchestré)

Le DAG `batch_ingestion` enchaîne désormais `charger_bases >> lancer_etl`
automatiquement (étape 8).

## Explorer le résultat

```bash
docker compose exec postgres psql -U platform -d warehouse -c "
  SELECT c.type_client, ROUND(AVG(f.energie_kwh),2) AS kwh_moyen_jour
  FROM dw.fait_consommation_jour f
  JOIN dw.dim_compteur c ON c.compteur_id = f.compteur_id
  GROUP BY c.type_client ORDER BY kwh_moyen_jour DESC;"
```

Requêtes d'analyse prêtes à l'emploi :
[sql/analytics/exemples_requetes.sql](../sql/analytics/exemples_requetes.sql)
(consommation par région/mois, profil horaire, qualité des données...).

## Choix « full refresh »

L'ETL **vide puis recharge** (TRUNCATE + INSERT) à chaque exécution. Simple et
correct pour un batch complet. Un ETL incrémental (ne traiter que les nouveaux
jours) serait l'étape suivante en production.
