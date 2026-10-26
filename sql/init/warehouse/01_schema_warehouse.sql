-- =============================================================================
--  Data Warehouse PostgreSQL : schéma en étoile pour l'analyse
-- =============================================================================
--  SÉPARÉ de la base OLTP : l'OLTP sert le quotidien (écritures unitaires), le
--  warehouse sert l'analyse (lectures agrégées massives). Deux usages opposés,
--  deux modèles. Ici : un SCHÉMA EN ÉTOILE.
--
--    - Tables de DIMENSIONS : les axes d'analyse (temps, région, client, compteur).
--    - Tables de FAITS : les mesures (consommation), reliées aux dimensions.
--
--  Deux grains de faits (choix « couches de granularité ») :
--    - fait_consommation_horaire : grain fin, source de vérité.
--    - fait_consommation_jour     : AGRÉGAT journalier dérivé, rapide pour la BI.
--
--  Ce script crée la structure ; c'est l'ETL (etl/) qui la remplit, en
--  NETTOYANT au passage les défauts des sources (doublons clients, etc.).
--
--  Exécuté dans la base `warehouse` (DW_DB du .env).
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS dw;
SET search_path TO dw;

-- -----------------------------------------------------------------------------
--  DIMENSIONS
-- -----------------------------------------------------------------------------

-- Dimension temps : une ligne par jour. Pré-calculer mois/année/jour de semaine
-- évite de le refaire dans CHAQUE requête d'analyse (et permet des filtres simples).
CREATE TABLE dim_temps (
    date_id        DATE    PRIMARY KEY,       -- le jour lui-même sert de clé
    jour           SMALLINT NOT NULL,         -- 1..31
    mois           SMALLINT NOT NULL,         -- 1..12
    annee          SMALLINT NOT NULL,
    trimestre      SMALLINT NOT NULL,         -- 1..4
    jour_semaine   SMALLINT NOT NULL,         -- 1=lundi .. 7=dimanche
    est_weekend    BOOLEAN  NOT NULL,
    nom_mois       VARCHAR(12) NOT NULL
);

-- Dimension région : copie analytique du référentiel (dénormalisée pour l'analyse).
CREATE TABLE dim_region (
    region_code     VARCHAR(6)  PRIMARY KEY,
    nom             VARCHAR(60) NOT NULL,
    chef_lieu       VARCHAR(60),
    population      INTEGER,
    superficie_km2  INTEGER
);

-- Dimension client : version NETTOYÉE et dédoublonnée des clients.
-- Les doublons volontaires de la source (même personne, client_id différent, nom
-- en majuscules) sont éliminés par l'ETL : ici on n'attend que des clients uniques.
CREATE TABLE dim_client (
    client_id        VARCHAR(12) PRIMARY KEY,
    nom_complet      VARCHAR(120) NOT NULL,    -- prénom + nom normalisés
    type_client      VARCHAR(20)  NOT NULL,
    region_code      VARCHAR(6)   REFERENCES dim_region (region_code),
    email_valide     BOOLEAN      NOT NULL,    -- indicateur qualité (email présent & plausible)
    date_inscription DATE
);

-- Dimension compteur : attributs du compteur utiles à l'analyse.
CREATE TABLE dim_compteur (
    compteur_id       VARCHAR(16) PRIMARY KEY,
    client_id         VARCHAR(12) REFERENCES dim_client (client_id),
    region_code       VARCHAR(6)  REFERENCES dim_region (region_code),
    type_client       VARCHAR(20) NOT NULL,
    mode_facturation  VARCHAR(10) NOT NULL,
    puissance_kva     SMALLINT,
    transformateur_id VARCHAR(12)
);

-- -----------------------------------------------------------------------------
--  FAITS
-- -----------------------------------------------------------------------------

-- Grain fin : une ligne par compteur et par HEURE (source de vérité analytique).
CREATE TABLE fait_consommation_horaire (
    compteur_id   VARCHAR(16) NOT NULL REFERENCES dim_compteur (compteur_id),
    date_id       DATE        NOT NULL REFERENCES dim_temps (date_id),
    horodatage    TIMESTAMP   NOT NULL,
    energie_kwh   NUMERIC(10, 3) NOT NULL,     -- la MESURE (fait additif)
    tension_v     NUMERIC(6, 1),
    courant_a     NUMERIC(8, 2),
    PRIMARY KEY (compteur_id, horodatage)
);

-- Agrégat journalier : une ligne par compteur et par JOUR. DÉRIVÉ de l'horaire
-- (somme des kWh, moyennes électriques). Accélère fortement la BI mensuelle/régionale.
CREATE TABLE fait_consommation_jour (
    compteur_id      VARCHAR(16) NOT NULL REFERENCES dim_compteur (compteur_id),
    date_id          DATE        NOT NULL REFERENCES dim_temps (date_id),
    energie_kwh      NUMERIC(12, 3) NOT NULL,  -- somme des 24 heures
    tension_moy_v    NUMERIC(6, 1),
    courant_moy_a    NUMERIC(8, 2),
    nb_releves       SMALLINT    NOT NULL,     -- 24 attendus ; moins = données manquantes
    PRIMARY KEY (compteur_id, date_id)
);

-- -----------------------------------------------------------------------------
--  Index : on indexe les axes d'analyse les plus filtrés (temps, région, type).
-- -----------------------------------------------------------------------------
CREATE INDEX idx_fait_h_date      ON fait_consommation_horaire (date_id);
CREATE INDEX idx_fait_j_date      ON fait_consommation_jour     (date_id);
CREATE INDEX idx_dim_compteur_reg ON dim_compteur (region_code);
CREATE INDEX idx_dim_compteur_typ ON dim_compteur (type_client);
CREATE INDEX idx_dim_client_reg   ON dim_client   (region_code);
