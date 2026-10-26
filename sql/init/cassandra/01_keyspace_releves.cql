// ============================================================================
//  Cassandra : historique des relevés de compteurs (séries temporelles)
// ============================================================================
//  POURQUOI Cassandra ici ?
//    Les relevés sont le plus gros volume du projet : chaque compteur émet une
//    mesure par heure. 1 000 compteurs × 60 jours × 24 h = ~1,4 million de
//    lignes, et en temps réel ça n'arrête jamais. Cassandra est bâtie pour ça :
//    écriture massive distribuée, pas de goulot d'étranglement central.
//
//  LA RÈGLE D'OR CASSANDRA : on modélise à partir des REQUÊTES, pas des données.
//    En SQL on normalise puis on interroge comme on veut (au prix de jointures).
//    En Cassandra il n'y a ni jointure ni requête libre : la table DOIT être
//    dessinée pour la question qu'on lui posera. Ici la question métier est :
//      « donne-moi les relevés du compteur X entre deux dates »
//    => la clé de partition est le compteur, le tri interne est le temps.
//
//  Ce fichier (.cql) sera joué via cqlsh au démarrage (pas d'auto-init comme
//  Postgres/MySQL : on l'exécutera depuis un petit script d'attente, étape 4).
// ============================================================================

//  Keyspace = l'équivalent d'une "base". SimpleStrategy / RF=1 convient en
//  développement mono-nœud. En production on passerait à NetworkTopologyStrategy
//  avec un facteur de réplication >= 3 (tolérance aux pannes).
CREATE KEYSPACE IF NOT EXISTS releves
    WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE releves;

// ----------------------------------------------------------------------------
//  Table principale : relevés par compteur, triés par temps
// ----------------------------------------------------------------------------
//  Clé primaire décomposée :
//    - CLÉ DE PARTITION  (compteur_id, jour) : détermine SUR QUEL NŒUD vit la
//      donnée. On ajoute `jour` au compteur pour éviter une partition qui
//      grossirait à l'infini (une partition = idéalement < 100 Mo). C'est le
//      "time bucketing", pratique standard en séries temporelles.
//    - CLÉ DE CLUSTERING (horodatage) : ordonne les lignes DANS la partition.
//      CLUSTERING ORDER BY DESC => les relevés les plus récents en premier,
//      car c'est ce qu'on lit le plus souvent.
CREATE TABLE IF NOT EXISTS releves_par_compteur (
    compteur_id  text,
    jour         date,          // bucket temporel (AAAA-MM-JJ)
    horodatage   timestamp,
    energie_kwh  double,        // énergie consommée sur l'heure
    index_kwh    double,        // index cumulé du compteur
    tension_v    float,
    courant_a    float,
    PRIMARY KEY ((compteur_id, jour), horodatage)
) WITH CLUSTERING ORDER BY (horodatage DESC)
  AND comment = 'Historique horaire des compteurs, partitionne par compteur et par jour';

//  Requêtes typiques que ce modèle sert efficacement :
//    SELECT * FROM releves_par_compteur
//     WHERE compteur_id = 'CPT-10000001' AND jour = '2026-08-27';
//    SELECT * FROM releves_par_compteur
//     WHERE compteur_id = 'CPT-10000001' AND jour IN ('2026-08-27','2026-08-28');
//
//  Ce qu'on NE PEUT PAS faire (et c'est normal) : "tous les relevés d'une
//  région", ou "la conso totale de tous les compteurs à 20 h". Ces questions
//  d'ANALYSE relèvent du Data Warehouse (étape 9), pas de Cassandra.
