"""Tests des features ML et des étiquettes — sans base, sans sklearn.

On vérifie que les features capturent bien les signatures des anomalies
(heures à zéro, chute de consommation) et que les étiquettes sont correctes.
"""

import numpy as np
import pandas as pd

from ml.features import build_features, labels_from_inspections, FEATURE_COLUMNS


def _releves(compteur, energie, debut="2026-01-01"):
    """Fabrique des relevés horaires à partir d'une liste d'énergies."""
    horaires = pd.date_range(debut, periods=len(energie), freq="h")
    return pd.DataFrame({
        "compteur_id": compteur,
        "horodatage": horaires,
        "energie_kwh": energie,
        "tension_v": 230.0,
    })


def test_normal_meter_has_no_zeros_and_stable_ratio():
    # Consommation régulière, jamais nulle.
    rng = np.random.default_rng(0)
    energie = rng.uniform(0.3, 0.6, 48)
    feats = build_features(_releves("CPT-N", energie)).set_index("compteur_id")
    assert feats.loc["CPT-N", "part_zero"] == 0.0
    assert 0.7 < feats.loc["CPT-N", "ratio_2de_1re"] < 1.4   # pas de chute


def test_blocked_meter_detected_by_zeros():
    # Compteur bloqué : moitié normale, puis que des zéros.
    energie = list(np.full(24, 0.5)) + list(np.zeros(24))
    feats = build_features(_releves("CPT-B", energie)).set_index("compteur_id")
    assert feats.loc["CPT-B", "part_zero"] == 0.5
    assert feats.loc["CPT-B", "ratio_2de_1re"] == 0.0        # 2de moitié nulle


def test_bypass_detected_by_consumption_drop():
    # Bypass : conso divisée par ~4 en 2e moitié.
    energie = list(np.full(24, 1.0)) + list(np.full(24, 0.25))
    feats = build_features(_releves("CPT-F", energie)).set_index("compteur_id")
    assert feats.loc["CPT-F", "ratio_2de_1re"] < 0.3         # forte chute


def test_feature_columns_all_present():
    feats = build_features(_releves("CPT-X", [0.5] * 24))
    for col in FEATURE_COLUMNS:
        assert col in feats.columns


def test_labels_binary_and_deduplicated():
    inspections = [
        {"compteur_id": "CPT-1", "resultat": "conforme"},
        {"compteur_id": "CPT-2", "resultat": "fraude_confirmee"},
        {"compteur_id": "CPT-3", "resultat": "defaut_technique"},
        # CPT-2 réinspecté conforme : le max garde l'anomalie (1).
        {"compteur_id": "CPT-2", "resultat": "conforme"},
    ]
    labels = labels_from_inspections(inspections).set_index("compteur_id")
    assert labels.loc["CPT-1", "anomalie"] == 0
    assert labels.loc["CPT-2", "anomalie"] == 1      # une anomalie suffit
    assert labels.loc["CPT-3", "anomalie"] == 1
    assert len(labels) == 3                          # dédoublonné par compteur
