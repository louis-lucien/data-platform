"""Tests du producteur temps réel (étape 5).

On teste la logique PURE (calcul d'un tick, détection d'alertes) sans Kafka :
le modèle physique est partagé avec le batch, donc ces tests protègent les deux.
"""

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from generator.streaming.meters import MeterFleet
from generator.streaming.tick import compute_tick, detect_alerts, TENSION_MIN, TENSION_MAX


def _fleet(n=50):
    meters = pd.DataFrame({
        "compteur_id": [f"CPT-{i:08d}" for i in range(n)],
        "type_client": (["residentiel", "professionnel", "agricole"] * n)[:n],
        "region_code": ["SN-DK"] * n,
        "puissance_kva": [6.0] * n,
        "index_initial_kwh": [1000.0] * n,
    })
    return MeterFleet(meters, np.random.default_rng(0))


def test_tick_emits_one_reading_per_meter():
    fleet = _fleet(50)
    readings = compute_tick(fleet, datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
                            np.random.default_rng(1))
    assert len(readings) == 50
    assert {"compteur_id", "horodatage", "energie_kwh", "index_kwh",
            "tension_v", "courant_a"} <= readings[0].keys()


def test_index_only_increases():
    """L'index d'un compteur ne doit JAMAIS reculer d'un tick à l'autre."""
    fleet = _fleet(20)
    rng = np.random.default_rng(2)
    moment = datetime(2026, 1, 1, 8, tzinfo=timezone.utc)
    before = fleet.index_kwh.copy()
    for _ in range(5):
        compute_tick(fleet, moment, rng)
    assert np.all(fleet.index_kwh >= before)


def test_detect_alert_on_voltage_out_of_bounds():
    low = {"compteur_id": "C1", "horodatage": "t", "tension_v": TENSION_MIN - 1,
           "energie_kwh": 0.5, "region_code": "SN-DK"}
    high = {"compteur_id": "C2", "horodatage": "t", "tension_v": TENSION_MAX + 1,
            "energie_kwh": 0.5, "region_code": "SN-DK"}
    ok = {"compteur_id": "C3", "horodatage": "t", "tension_v": 230.0,
          "energie_kwh": 0.5, "region_code": "SN-DK"}
    alerts = detect_alerts([low, high, ok])
    assert {a["compteur_id"] for a in alerts} == {"C1", "C2"}
    assert all(a["type_alerte"] == "tension_hors_bornes" for a in alerts)


def test_detect_alert_on_zero_consumption():
    r = {"compteur_id": "C9", "horodatage": "t", "tension_v": 230.0,
         "energie_kwh": 0.0, "region_code": "SN-DK"}
    alerts = detect_alerts([r])
    assert len(alerts) == 1
    assert alerts[0]["type_alerte"] == "conso_nulle"
