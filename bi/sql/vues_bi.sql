-- =============================================================================
--  Vues BI : couche sémantique prête pour Power BI / Metabase / Superset
-- =============================================================================
--  Pourquoi des VUES ? Pour que l'outil BI importe une table nommée et parlante
--  (ex. vue_conso_region_mois) au lieu de recopier une requête SQL complexe.
--  Les vues vivent DANS le Data Warehouse : une seule source de vérité, partagée
--  par Power BI ET le dashboard HTML de démonstration (bi/dashboard/).
--
--  À exécuter dans la base `warehouse` après l'ETL :
--    docker compose exec postgres psql -U platform -d warehouse -f /bi/vues_bi.sql
--  (ou via le service bi-init du compose).
-- =============================================================================
SET search_path TO dw;

-- 1) Consommation totale par région et par mois ------------------------------
CREATE OR REPLACE VIEW vue_conso_region_mois AS
SELECT r.region_code,
       r.nom                         AS region,
       t.annee,
       t.mois,
       t.nom_mois,
       ROUND(SUM(f.energie_kwh), 1)  AS kwh_total,
       COUNT(DISTINCT f.compteur_id) AS nb_compteurs
FROM fait_consommation_jour f
JOIN dim_compteur c ON c.compteur_id = f.compteur_id
JOIN dim_region   r ON r.region_code = c.region_code
JOIN dim_temps    t ON t.date_id     = f.date_id
GROUP BY r.region_code, r.nom, t.annee, t.mois, t.nom_mois;

-- 2) Profil horaire moyen par type de client ---------------------------------
--    Montre le pic du soir des ménages vs la journée des professionnels.
CREATE OR REPLACE VIEW vue_profil_horaire AS
SELECT EXTRACT(HOUR FROM f.horodatage)::INT AS heure,
       c.type_client,
       ROUND(AVG(f.energie_kwh), 3)         AS kwh_moyen
FROM fait_consommation_horaire f
JOIN dim_compteur c ON c.compteur_id = f.compteur_id
GROUP BY heure, c.type_client;

-- 3) Consommation moyenne par jour selon le type de client -------------------
CREATE OR REPLACE VIEW vue_conso_par_type AS
SELECT c.type_client,
       COUNT(DISTINCT c.compteur_id)     AS nb_compteurs,
       ROUND(AVG(f.energie_kwh), 2)      AS kwh_moyen_jour,
       ROUND(SUM(f.energie_kwh), 1)      AS kwh_total
FROM fait_consommation_jour f
JOIN dim_compteur c ON c.compteur_id = f.compteur_id
GROUP BY c.type_client;

-- 4) Qualité des données clients par région ----------------------------------
CREATE OR REPLACE VIEW vue_qualite_clients AS
SELECT r.nom                                                           AS region,
       COUNT(*)                                                        AS nb_clients,
       SUM(CASE WHEN cl.email_valide THEN 1 ELSE 0 END)                AS avec_email_valide,
       ROUND(100.0 * SUM(CASE WHEN cl.email_valide THEN 1 ELSE 0 END)
             / COUNT(*), 1)                                            AS pct_email_valide
FROM dim_client cl
JOIN dim_region r ON r.region_code = cl.region_code
GROUP BY r.nom;

-- 5) Synthèse par région (pour une carte / vue d'ensemble) -------------------
CREATE OR REPLACE VIEW vue_synthese_region AS
SELECT r.region_code,
       r.nom                              AS region,
       r.population,
       COUNT(DISTINCT c.compteur_id)      AS nb_compteurs,
       ROUND(SUM(f.energie_kwh), 1)       AS kwh_total,
       ROUND(AVG(f.tension_moy_v), 1)     AS tension_moyenne
FROM dim_region r
LEFT JOIN dim_compteur c           ON c.region_code = r.region_code
LEFT JOIN fait_consommation_jour f ON f.compteur_id = c.compteur_id
GROUP BY r.region_code, r.nom, r.population;
