// ============================================================================
//  Neo4j : topologie du réseau électrique (graphe)
// ============================================================================
//  POURQUOI un graphe ici ?
//    La question métier est : « si ce poste source tombe, QUELS COMPTEURS sont
//    coupés ? » et inversement « ce compteur dépend de quel transformateur, de
//    quel poste ? ». C'est une question de CHEMINS dans une hiérarchie :
//
//        (Region) -[:ALIMENTE]-> (PosteSource)
//                 -[:ALIMENTE]-> (Transformateur)
//                 -[:ALIMENTE]-> (Compteur)
//
//    En SQL, "tous les compteurs sous le poste PS-DK-01" = plusieurs jointures.
//    En graphe, on PARCOURT les relations : c'est naturel, lisible et rapide,
//    et ça reste simple même si demain la hiérarchie gagne un niveau.
//
//  Ce que ce script fait : il pose les CONTRAINTES et INDEX (le "schéma léger"
//  de Neo4j). Il ne CHARGE PAS les nœuds : la topologie sera peuplée par l'ETL
//  à partir du fichier source `reseau.xml`. Un graphe sans garde-fou se remplit
//  vite de doublons ; ces contraintes l'évitent dès le départ.
//
//  Exécution : via cypher-shell au démarrage (script d'attente, étape 4).
// ============================================================================

// ----------------------------------------------------------------------------
//  Contraintes d'unicité = identité des nœuds
// ----------------------------------------------------------------------------
//  En Neo4j, une contrainte d'unicité crée AUSSI un index : poser la contrainte
//  suffit (pas besoin d'un CREATE INDEX séparé sur la même propriété).
//  "IF NOT EXISTS" rend le script rejouable sans erreur (idempotent).

CREATE CONSTRAINT region_code IF NOT EXISTS
    FOR (r:Region) REQUIRE r.code IS UNIQUE;

CREATE CONSTRAINT poste_id IF NOT EXISTS
    FOR (p:PosteSource) REQUIRE p.poste_id IS UNIQUE;

CREATE CONSTRAINT transformateur_id IF NOT EXISTS
    FOR (t:Transformateur) REQUIRE t.transformateur_id IS UNIQUE;

CREATE CONSTRAINT compteur_id IF NOT EXISTS
    FOR (c:Compteur) REQUIRE c.compteur_id IS UNIQUE;

// ----------------------------------------------------------------------------
//  Mémo : requêtes d'analyse d'impact que ce modèle rend triviales
// ----------------------------------------------------------------------------
//  Une fois la topologie chargée par l'ETL, on pourra par exemple répondre à :
//
//  -- Tous les compteurs coupés si le poste PS-DK-01 tombe :
//     MATCH (:PosteSource {poste_id:'PS-DK-01'})
//           -[:ALIMENTE*]->(c:Compteur)
//     RETURN count(c);
//
//  -- Remonter la chaîne d'alimentation d'un compteur (diagnostic de panne) :
//     MATCH path = (r:Region)-[:ALIMENTE*]->(c:Compteur {compteur_id:'CPT-10000001'})
//     RETURN path;
//
//  Le `*` (chemin de longueur variable) est exactement ce qu'un graphe fait
//  bien et qu'un SQL rendrait pénible (jointures récursives).
