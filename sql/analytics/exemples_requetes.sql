-- =============================================================================
--  Requêtes d'analyse sur le Data Warehouse (schéma en étoile dw)
-- =============================================================================
--  Ces requêtes montrent la PUISSANCE du schéma en étoile : des questions métier
--  complexes deviennent de simples jointures fait × dimensions. Elles serviront
--  de base aux visualisations BI (étape 10).
--  À exécuter dans la base `warehouse` : SET search_path TO dw;
-- =============================================================================
SET search_path TO dw;

-- 1) Consommation totale par région et par mois (le classique BI).
SELECT r.nom AS region, t.annee, t.nom_mois,
       ROUND(SUM(f.energie_kwh), 1) AS kwh_total
FROM fait_consommation_jour f
JOIN dim_compteur c ON c.compteur_id = f.compteur_id
JOIN dim_region   r ON r.region_code = c.region_code
JOIN dim_temps    t ON t.date_id = f.date_id
GROUP BY r.nom, t.annee, t.mois, t.nom_mois
ORDER BY r.nom, t.annee, t.mois;

-- 2) Consommation moyenne par jour selon le type de client.
SELECT c.type_client,
       ROUND(AVG(f.energie_kwh), 2) AS kwh_moyen_par_jour
FROM fait_consommation_jour f
JOIN dim_compteur c ON c.compteur_id = f.compteur_id
GROUP BY c.type_client
ORDER BY kwh_moyen_par_jour DESC;

-- 3) Profil HORAIRE moyen (heure de la journée vs consommation) — grain fin.
--    Montre le pic du soir des ménages vs la journée des pros.
SELECT EXTRACT(HOUR FROM f.horodatage) AS heure,
       c.type_client,
       ROUND(AVG(f.energie_kwh), 3) AS kwh_moyen
FROM fait_consommation_horaire f
JOIN dim_compteur c ON c.compteur_id = f.compteur_id
GROUP BY heure, c.type_client
ORDER BY heure, c.type_client;

-- 4) Qualité des données : part de clients avec email valide, par région.
SELECT r.nom AS region,
       COUNT(*) AS nb_clients,
       SUM(CASE WHEN cl.email_valide THEN 1 ELSE 0 END) AS avec_email_valide,
       ROUND(100.0 * SUM(CASE WHEN cl.email_valide THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct
FROM dim_client cl
JOIN dim_region r ON r.region_code = cl.region_code
GROUP BY r.nom
ORDER BY pct;

-- 5) Jours avec des relevés manquants (qualité des séries temporelles).
--    nb_releves < 24 => des heures manquent ce jour-là.
SELECT f.date_id, COUNT(*) AS compteurs_incomplets
FROM fait_consommation_jour f
WHERE f.nb_releves < 24
GROUP BY f.date_id
ORDER BY f.date_id;
