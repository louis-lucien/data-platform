"""Test de la chaîne modèle (make_model → fit → evaluate) sur données synthétiques.

Ne touche aucune base : on fabrique des features nettement séparables et on
vérifie que le modèle apprend et que l'évaluation renvoie des métriques sensées.
"""

import numpy as np
import pandas as pd

from ml.features import FEATURE_COLUMNS
from ml.model import make_model, evaluate, feature_importances


def _synthetic(n=200, seed=0):
    """Features séparables : les anomalies ont part_zero élevée + ratio_2de_1re bas."""
    rng = np.random.default_rng(seed)
    moitie = n // 2
    normal = pd.DataFrame({
        "conso_moy": rng.uniform(0.3, 0.6, moitie), "conso_std": rng.uniform(0.1, 0.2, moitie),
        "conso_max": rng.uniform(1.0, 2.0, moitie), "part_zero": np.zeros(moitie),
        "part_zero_nuit": np.zeros(moitie), "part_zero_jour": np.zeros(moitie),
        "ratio_2de_1re": rng.uniform(0.9, 1.1, moitie), "ratio_nuit_jour": rng.uniform(0.3, 0.6, moitie),
    })
    anomalie = pd.DataFrame({
        "conso_moy": rng.uniform(0.1, 0.25, moitie), "conso_std": rng.uniform(0.2, 0.4, moitie),
        "conso_max": rng.uniform(0.5, 1.0, moitie), "part_zero": rng.uniform(0.1, 0.4, moitie),
        "part_zero_nuit": rng.uniform(0.1, 0.5, moitie), "part_zero_jour": rng.uniform(0.0, 0.2, moitie),
        "ratio_2de_1re": rng.uniform(0.1, 0.4, moitie), "ratio_nuit_jour": rng.uniform(0.0, 0.2, moitie),
    })
    X = pd.concat([normal, anomalie], ignore_index=True)[FEATURE_COLUMNS]
    y = pd.Series([0] * moitie + [1] * moitie)
    return X, y


def test_model_learns_separable_data():
    from sklearn.model_selection import train_test_split
    X, y = _synthetic()
    # stratify : les deux classes présentes dans train ET test (sinon AUC = nan).
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=1, stratify=y)
    model = make_model(seed=1)
    model.fit(X_tr, y_tr)
    ev = evaluate(model, X_te, y_te)
    # Sur des données nettement séparables, on attend de bonnes métriques.
    assert ev.recall >= 0.8
    assert ev.precision >= 0.8
    assert 0.0 <= ev.roc_auc <= 1.0


def test_feature_importances_sum_to_one():
    X, y = _synthetic()
    model = make_model(seed=1)
    model.fit(X, y)
    imp = feature_importances(model)
    assert set(imp) == set(FEATURE_COLUMNS)
    assert abs(sum(imp.values()) - 1.0) < 0.05     # importances normalisées
