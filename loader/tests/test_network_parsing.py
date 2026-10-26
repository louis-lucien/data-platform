"""Test du parsing de la topologie réseau partagé par les chargeurs Postgres/Neo4j.

Le XML `reseau` est la source de vérité de la hiérarchie poste > transformateur.
On vérifie que le parsing en extrait les bons tuples, car toute la topologie
(et donc l'analyse d'impact de panne) en dépend.
"""

from loader.network import parse_network
from test_datalake import lake  # réutilise la fixture (petit data lake jouet)

__all__ = ["lake"]  # garde l'import "utilisé" pour les linters


def test_parse_network_extracts_poste_and_transfo(lake):
    postes, transfos = parse_network(lake)

    assert len(postes) == 1
    poste = postes[0]
    assert poste["poste_id"] == "PS-DK-01"
    assert poste["region_code"] == "SN-DK"
    assert poste["tension_kv"] == 90

    assert len(transfos) == 1
    tr = transfos[0]
    assert tr["transformateur_id"] == "TR-DK-001"
    assert tr["poste_id"] == "PS-DK-01"      # bien rattaché à son poste
    assert tr["region_code"] == "SN-DK"
    assert tr["capacite_kva"] == 160
