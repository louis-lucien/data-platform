import numpy as np
import pandas as pd
import pytest

from generator import billing, consumption, entities
from generator.batch import run
from generator.config import load_config
from generator.sources.wikipedia import parse_regions_table


def test_hourly_profiles_preserve_daily_total():
    for profile in consumption.HOURLY_PROFILES.values():
        assert len(profile) == 24
        assert profile.mean() == pytest.approx(1.0)


def test_heat_increases_residential_load():
    cool = consumption.load_factor("residentiel", 20, 2, 25.0)
    hot = consumption.load_factor("residentiel", 20, 2, 35.0)
    assert hot > cool


@pytest.mark.parametrize("kind", ["fraude_bypass", "fraude_intermittente", "compteur_bloque"])
def test_anomalies_reduce_measured_energy(kind):
    rng = np.random.default_rng(0)
    energy = np.ones((100, 240))
    truth = consumption.inject_anomalies(energy, np.arange(240) % 24, {kind: 0.05}, rng)
    assert len(truth) == 5
    for item in truth:
        assert energy[item["meter_idx"], item["debut_idx"]:].mean() < 1.0


def test_allocate_is_exact_and_proportional():
    counts = entities.allocate(1000, np.array([3.0, 1.0, 1.0]))
    assert counts.sum() == 1000
    assert counts[0] == 600


@pytest.mark.parametrize("kwh, expected", [(100, 100 * 91), (200, 150 * 91 + 50 * 136),
                                           (300, 150 * 91 + 100 * 136 + 50 * 149)])
def test_progressive_tariff(kwh, expected):
    tranches = [{"jusqu_a_kwh": 150, "prix_kwh": 91}, {"jusqu_a_kwh": 250, "prix_kwh": 136},
                {"jusqu_a_kwh": None, "prix_kwh": 149}]
    assert billing.tranche_amount(kwh, tranches) == expected


def test_parse_regions_table_handles_double_header_and_footnotes():
    html = """
    <table class="wikitable">
      <tr><th>Nom</th><th>Codes</th><th>Superficie</th><th>Population</th></tr>
      <tr><th>ANSD</th><th>ISO</th><th>km2</th><th>2013<sup class="reference">[2]</sup></th><th>2018</th></tr>
      <tr><td>Dakar</td><td>01</td><td>SN-DK</td><td>547</td><td>3&#160;137&#160;196</td><td>3&#160;630&#160;323</td></tr>
    </table>"""
    regions = parse_regions_table(html)
    assert regions.to_dict("records") == [{"code": "SN-DK", "superficie_km2": 547, "population": 3_630_323}]


@pytest.fixture(scope="module")
def small_run(tmp_path_factory):
    cfg = load_config() | {"clients": 60, "history_days": 3}
    out = tmp_path_factory.mktemp("raw")
    run(cfg, out, offline=True)
    return out


def test_batch_produces_every_format(small_run):
    extensions = {p.suffix for p in small_run.rglob("*.*") if "_runs" not in p.parts}
    assert {".csv", ".json", ".xml", ".xlsx", ".yaml"} <= extensions


def test_meter_index_is_consistent_with_energy(small_run):
    readings = pd.concat((pd.read_csv(p) for p in small_run.glob("releves/dt=*/releves.csv")), ignore_index=True)
    readings = readings.sort_values(["compteur_id", "horodatage"], ignore_index=True)
    delta = readings.groupby("compteur_id")["index_kwh"].diff().dropna()
    energy = readings.loc[delta.index, "energie_kwh"]
    assert np.allclose(delta, energy, atol=0.02)
    assert (delta >= 0).all()  # un index de compteur ne recule jamais
