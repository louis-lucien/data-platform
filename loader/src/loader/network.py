"""Parsing de la topologie réseau depuis reseau.xml (logique pure, sans driver).

Partagé par les chargeurs Postgres et Neo4j. Isolé ici pour deux raisons :
  1. ne pas dupliquer le parcours du XML entre les deux chargeurs ;
  2. rester testable SANS aucun pilote de base installé (c'est de la logique pure).
"""

from loader.datalake import DataLake


def parse_network(lake: DataLake) -> tuple[list[dict], list[dict]]:
    """Extrait postes et transformateurs du fichier reseau.xml (export type SIG).

    Renvoie deux listes de dictionnaires (postes, transformateurs). Les chargeurs
    en tirent les tuples/paramètres dont ils ont besoin.
    """
    root = lake.read_xml_root("reseau")
    postes, transfos = [], []
    for region in root.findall("region"):
        rcode = region.get("code")
        for poste in region.findall("poste_source"):
            pos = poste.find("position")
            postes.append({
                "poste_id": poste.get("id"),
                "nom": poste.findtext("nom"),
                "region_code": rcode,
                "tension_kv": int(poste.get("tension_kv")),
                "capacite_mva": int(poste.get("capacite_mva")),
                "lat": float(pos.get("lat")),
                "lon": float(pos.get("lon")),
            })
            for tr in poste.findall("transformateur"):
                transfos.append({
                    "transformateur_id": tr.get("id"),
                    "poste_id": poste.get("id"),
                    "region_code": rcode,
                    "capacite_kva": int(tr.get("capacite_kva")),
                    "annee_mise_service": int(tr.get("annee_mise_service")),
                    "lat": float(tr.get("lat")),
                    "lon": float(tr.get("lon")),
                })
    return postes, transfos
