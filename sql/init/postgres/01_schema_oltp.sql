-- =============================================================================
--  Base OLTP PostgreSQL : gestion opérationnelle du distributeur
-- =============================================================================
--  OLTP = Online Transaction Processing : la base « vivante » du métier, celle
--  qui enregistrerait au quotidien les clients et les compteurs. Elle est
--  SÉPARÉE du Data Warehouse (base `warehouse`), qui servira à l'analyse.
--
--  Principe de modélisation retenu : on NE recopie PAS les fichiers sources
--  colonne par colonne. Le fichier compteurs.json contient par exemple
--  `type_client` et `region_code`, mais ces informations appartiennent au
--  client. En relationnel on ne duplique pas une donnée : on la relie par une
--  clé étrangère et on la retrouve par jointure. C'est la 3e forme normale.
--
--  Ce script est exécuté automatiquement par le conteneur `postgres` au tout
--  premier démarrage (dossier /docker-entrypoint-initdb.d), dans la base
--  définie par POSTGRES_DB. Il est donc idempotent-friendly : on crée un schéma
--  dédié plutôt que de polluer `public`.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS oltp;
SET search_path TO oltp;

-- -----------------------------------------------------------------------------
--  Référentiel géographique et topologie du réseau
-- -----------------------------------------------------------------------------
--  region > poste source > transformateur > compteur : c'est la hiérarchie
--  physique du réseau électrique. Neo4j la stockera comme un graphe (pour
--  l'analyse d'impact de panne) ; ici on la garde en relationnel car c'est
--  aussi un simple référentiel que les clients/compteurs doivent respecter.

CREATE TABLE regions (
    -- Code ISO 3166-2 (SN-DK, SN-TH...) : identifiant naturel, stable et lisible.
    code            VARCHAR(6)   PRIMARY KEY,
    nom             VARCHAR(60)  NOT NULL,
    chef_lieu       VARCHAR(60)  NOT NULL,
    latitude        NUMERIC(8, 5),
    longitude       NUMERIC(8, 5),
    superficie_km2  INTEGER,
    population       INTEGER      CHECK (population >= 0)
);

CREATE TABLE postes_source (
    poste_id      VARCHAR(12)  PRIMARY KEY,          -- ex. PS-DK-01
    nom           VARCHAR(80)  NOT NULL,
    region_code   VARCHAR(6)   NOT NULL REFERENCES regions (code),
    tension_kv    SMALLINT     NOT NULL,
    capacite_mva  SMALLINT,
    latitude      NUMERIC(8, 5),
    longitude     NUMERIC(8, 5)
);

CREATE TABLE transformateurs (
    transformateur_id    VARCHAR(12)  PRIMARY KEY,   -- ex. TR-DK-001
    poste_id             VARCHAR(12)  NOT NULL REFERENCES postes_source (poste_id),
    region_code          VARCHAR(6)   NOT NULL REFERENCES regions (code),
    capacite_kva         SMALLINT,
    annee_mise_service   SMALLINT     CHECK (annee_mise_service BETWEEN 1950 AND 2100),
    latitude             NUMERIC(8, 5),
    longitude            NUMERIC(8, 5)
);

-- -----------------------------------------------------------------------------
--  Clients et compteurs (cœur métier)
-- -----------------------------------------------------------------------------
--  ATTENTION : ces tables reçoivent des données NETTOYÉES. Le fichier source
--  `clients.csv` contient des défauts VOLONTAIRES (emails manquants, téléphones
--  mal formatés, doublons). Ces défauts sont traités par l'ETL ; ici on pose
--  les contraintes de la base « propre » que l'ETL doit faire respecter.
--  Un email manquant reste toléré (NULL autorisé) : c'est une donnée réellement
--  absente en source, pas une erreur de format.

-- On fige la liste des types de clients par un type énuméré : impossible
-- d'insérer une valeur fantaisiste, et c'est auto-documenté.
CREATE TYPE type_client_enum   AS ENUM ('residentiel', 'professionnel', 'agricole');
CREATE TYPE mode_facturation_enum AS ENUM ('prepaye', 'postpaye');
CREATE TYPE statut_compteur_enum  AS ENUM ('actif', 'inactif', 'remplace');

CREATE TABLE clients (
    client_id        VARCHAR(12)  PRIMARY KEY,       -- ex. CLI-000001
    prenom           VARCHAR(60)  NOT NULL,
    nom              VARCHAR(60)  NOT NULL,
    type_client      type_client_enum NOT NULL,
    raison_sociale   VARCHAR(120),                   -- NULL sauf professionnels
    telephone        VARCHAR(20),
    email            VARCHAR(120),                   -- NULL toléré (voir plus haut)
    adresse          VARCHAR(160),
    region_code      VARCHAR(6)   NOT NULL REFERENCES regions (code),
    date_inscription DATE         NOT NULL
);

CREATE TABLE compteurs (
    compteur_id        VARCHAR(16)  PRIMARY KEY,     -- ex. CPT-10000001
    numero_serie       VARCHAR(20)  NOT NULL UNIQUE, -- identité physique de l'appareil
    -- Un client = un compteur dans ce projet. On le garantit par la contrainte
    -- UNIQUE sur client_id : un même client ne peut pas avoir deux compteurs.
    client_id          VARCHAR(12)  NOT NULL UNIQUE REFERENCES clients (client_id),
    transformateur_id  VARCHAR(12)  NOT NULL REFERENCES transformateurs (transformateur_id),
    modele             VARCHAR(40),
    mode_facturation   mode_facturation_enum NOT NULL,
    puissance_kva      SMALLINT     NOT NULL CHECK (puissance_kva > 0),
    date_pose          DATE         NOT NULL,
    index_initial_kwh  NUMERIC(12, 2) NOT NULL CHECK (index_initial_kwh >= 0),
    statut             statut_compteur_enum NOT NULL DEFAULT 'actif'
);

-- -----------------------------------------------------------------------------
--  Index : on indexe ce que les requêtes filtrent/joignent le plus souvent.
-- -----------------------------------------------------------------------------
--  Une clé étrangère n'est PAS indexée automatiquement par PostgreSQL. Sans
--  index, « tous les compteurs d'un transformateur » (requête clé pour
--  l'analyse de panne) scannerait toute la table. On les ajoute donc.
CREATE INDEX idx_postes_region        ON postes_source   (region_code);
CREATE INDEX idx_transfos_poste       ON transformateurs (poste_id);
CREATE INDEX idx_transfos_region      ON transformateurs (region_code);
CREATE INDEX idx_clients_region       ON clients         (region_code);
CREATE INDEX idx_clients_type         ON clients         (type_client);
CREATE INDEX idx_compteurs_transfo    ON compteurs       (transformateur_id);
CREATE INDEX idx_compteurs_mode       ON compteurs       (mode_facturation);
