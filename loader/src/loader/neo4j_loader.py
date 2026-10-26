"""Chargement Neo4j : topologie du réseau sous forme de graphe.

On crée les nœuds (Region, PosteSource, Transformateur, Compteur) et les
relations ALIMENTE qui les relient en chaîne :

    (Region)-[:ALIMENTE]->(PosteSource)-[:ALIMENTE]->(Transformateur)-[:ALIMENTE]->(Compteur)

C'est cette chaîne qui rend l'analyse d'impact de panne triviale (un simple
parcours de chemin), contrairement à des jointures SQL en cascade.

Idempotent grâce à MERGE : rejouer le chargement ne duplique ni nœuds ni liens
(les contraintes d'unicité posées à l'init garantissent l'identité).
"""

from neo4j import GraphDatabase

from loader.config import Settings
from loader.datalake import DataLake
from loader.network import parse_network


def _parse(lake: DataLake):
    """Lit regions.csv + reseau.xml + compteurs.json pour reconstituer la hiérarchie."""
    regions = lake.read_csv("regions")[["code", "nom"]].to_dict("records")
    # parse_network renvoie tous les attributs ; Neo4j n'a besoin que des liens.
    postes_d, transfos_d = parse_network(lake)
    postes = [{"poste_id": p["poste_id"], "nom": p["nom"], "region_code": p["region_code"]}
              for p in postes_d]
    transfos = [{"transformateur_id": t["transformateur_id"], "poste_id": t["poste_id"]}
                for t in transfos_d]
    # Compteur -> transformateur (le lien terminal de la chaîne).
    compteurs = [{"compteur_id": m["compteur_id"], "transformateur_id": m["transformateur_id"]}
                 for m in lake.read_json("compteurs")]
    return regions, postes, transfos, compteurs


# Requêtes Cypher paramétrées. UNWIND = insertion par lot (une requête pour N lignes),
# bien plus rapide qu'une requête par nœud.
_Q_REGIONS = "UNWIND $rows AS r MERGE (n:Region {code: r.code}) SET n.nom = r.nom"
_Q_POSTES = """
UNWIND $rows AS r
MERGE (p:PosteSource {poste_id: r.poste_id}) SET p.nom = r.nom
WITH p, r MATCH (reg:Region {code: r.region_code})
MERGE (reg)-[:ALIMENTE]->(p)
"""
_Q_TRANSFOS = """
UNWIND $rows AS r
MERGE (t:Transformateur {transformateur_id: r.transformateur_id})
WITH t, r MATCH (p:PosteSource {poste_id: r.poste_id})
MERGE (p)-[:ALIMENTE]->(t)
"""
_Q_COMPTEURS = """
UNWIND $rows AS r
MERGE (c:Compteur {compteur_id: r.compteur_id})
WITH c, r MATCH (t:Transformateur {transformateur_id: r.transformateur_id})
MERGE (t)-[:ALIMENTE]->(c)
"""


def load(cfg: Settings, lake: DataLake) -> dict[str, int]:
    regions, postes, transfos, compteurs = _parse(lake)
    with GraphDatabase.driver(cfg.neo4j_uri, auth=(cfg.neo4j_user, cfg.neo4j_password)) as driver:
        with driver.session() as session:
            session.run(_Q_REGIONS, rows=regions)
            session.run(_Q_POSTES, rows=postes)
            session.run(_Q_TRANSFOS, rows=transfos)
            # Les compteurs peuvent être nombreux : on insère par paquets.
            for i in range(0, len(compteurs), 5000):
                session.run(_Q_COMPTEURS, rows=compteurs[i:i + 5000])
    return {"Region": len(regions), "PosteSource": len(postes),
            "Transformateur": len(transfos), "Compteur": len(compteurs)}
