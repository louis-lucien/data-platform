-- =============================================================================
--  Bascule vers la base `warehouse` et applique son schéma en étoile
-- =============================================================================
--  \connect change de base DANS le même run psql d'init. On applique ensuite le
--  schéma canonique (monté en lecture seule dans le conteneur) via \i, pour NE
--  PAS dupliquer le fichier de schéma (une seule source de vérité : warehouse/).
--
--  Préfixe « 02 » : après la création de la base (00) et le schéma OLTP (01).
-- =============================================================================

\connect warehouse

\i /warehouse-sql/01_schema_warehouse.sql
