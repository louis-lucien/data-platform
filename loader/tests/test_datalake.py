"""Tests de la logique du chargeur qui ne dépend PAS d'une base.

On vérifie la lecture du data lake et le parsing de la topologie réseau, sur un
petit data lake fabriqué à la volée (pas besoin de Docker ni de données réelles).
Les chargeurs eux-mêmes (écriture en base) sont testés manuellement une fois les
conteneurs lancés, via `python -m loader --only <base>`.
"""

import json

import pandas as pd
import pytest

from loader.datalake import DataLake


@pytest.fixture
def lake(tmp_path):
    """Construit un data lake minimal : regions, reseau.xml, compteurs, releves (2 jours)."""
    root = tmp_path / "raw"

    # regions
    reg_dir = root / "regions" / "dt=2026-01-01"
    reg_dir.mkdir(parents=True)
    pd.DataFrame([{"code": "SN-DK", "nom": "Dakar", "chef_lieu": "Dakar",
                   "lat": 14.7, "lon": -17.4, "superficie_km2": 547, "population": 3630323}]
                 ).to_csv(reg_dir / "regions.csv", index=False)

    # reseau.xml : 1 region > 1 poste > 1 transfo
    net_dir = root / "reseau" / "dt=2026-01-01"
    net_dir.mkdir(parents=True)
    (net_dir / "reseau.xml").write_text(
        "<?xml version='1.0' encoding='utf-8'?>"
        "<reseau operateur='X' pays='SN'>"
        "<region code='SN-DK' nom='Dakar'>"
        "<poste_source id='PS-DK-01' tension_kv='90' capacite_mva='20'>"
        "<nom>Poste Dakar 1</nom><position lat='14.7' lon='-17.4'/>"
        "<transformateur id='TR-DK-001' capacite_kva='160' annee_mise_service='2000' lat='14.7' lon='-17.4'/>"
        "</poste_source></region></reseau>", encoding="utf-8")

    # compteurs.json
    cpt_dir = root / "compteurs" / "dt=2026-01-01"
    cpt_dir.mkdir(parents=True)
    (cpt_dir / "compteurs.json").write_text(json.dumps([
        {"compteur_id": "CPT-10000001", "transformateur_id": "TR-DK-001"}
    ]), encoding="utf-8")

    # releves : 2 partitions (2 jours)
    for day in ("2026-01-01", "2026-01-02"):
        d = root / "releves" / f"dt={day}"
        d.mkdir(parents=True)
        pd.DataFrame([{"compteur_id": "CPT-10000001", "horodatage": f"{day} 00:00:00",
                       "energie_kwh": 0.1, "index_kwh": 100.0, "tension_v": 230.0, "courant_a": 0.4}]
                     ).to_csv(d / "releves.csv", index=False)

    return DataLake(root)


def test_missing_root_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        DataLake(tmp_path / "inexistant")


def test_read_csv_latest_partition(lake):
    df = lake.read_csv("regions")
    assert list(df["code"]) == ["SN-DK"]


def test_read_xml_root(lake):
    root = lake.read_xml_root("reseau")
    assert root.find("region").get("code") == "SN-DK"


def test_iter_partitions_in_order(lake):
    days = [day for day, _ in lake.iter_csv_partitions("releves")]
    assert days == ["2026-01-01", "2026-01-02"]  # triées croissant


def test_missing_entity_raises(lake):
    with pytest.raises(FileNotFoundError):
        lake.read_csv("entite_absente")
