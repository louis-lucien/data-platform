-- =============================================================================
--  Création de la base `warehouse` (Data Warehouse)
-- =============================================================================
--  Le conteneur Postgres crée automatiquement UNE base (POSTGRES_DB = energy,
--  l'OLTP). Le Data Warehouse est une base SÉPARÉE sur le même serveur : on la
--  crée ici. Préfixe « 00 » : ce script passe AVANT le schéma OLTP (01_...).
--
--  Le schéma en étoile lui-même (tables dim_/fait_) est dans
--  02_warehouse_schema.sql, joué juste après, qui se connecte à cette base.
-- =============================================================================

CREATE DATABASE warehouse;

COMMENT ON DATABASE warehouse IS 'Data Warehouse analytique (schéma en étoile dw).';
