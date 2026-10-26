"""Scoring : applique le modèle entraîné à TOUS les compteurs.

C'est la valeur métier finale : produire, pour chaque compteur, une PROBABILITÉ
d'anomalie, afin de prioriser les inspections terrain (on envoie les techniciens
là où le risque est le plus élevé, sans attendre qu'une panne soit signalée).

Le modèle est appliqué à tout le parc, y compris les compteurs JAMAIS inspectés —
c'est précisément là qu'il apporte de l'information nouvelle.
"""

import logging
from pathlib import Path

import joblib
import pandas as pd

from ml import data
from ml.features import build_features, FEATURE_COLUMNS
from ml.train import MODEL_PATH

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("ml.score")


def score(model, releves: pd.DataFrame, top: int | None = None) -> pd.DataFrame:
    """Renvoie les compteurs triés par probabilité d'anomalie décroissante."""
    features = build_features(releves)
    proba = model.predict_proba(features[FEATURE_COLUMNS])[:, 1]
    result = features[["compteur_id"]].copy()
    result["score_anomalie"] = proba.round(4)
    result = result.sort_values("score_anomalie", ascending=False, ignore_index=True)
    return result.head(top) if top else result


def main() -> int:
    if not Path(MODEL_PATH).exists():
        log.error(f"Modèle introuvable : {MODEL_PATH}. Lancez d'abord l'entraînement (ml-train).")
        return 1
    model = joblib.load(MODEL_PATH)
    releves = data.load_releves_from_dw()
    classement = score(model, releves, top=20)
    log.info("Top 20 des compteurs à inspecter en priorité :")
    for row in classement.itertuples(index=False):
        log.info(f"  {row.compteur_id}   score={row.score_anomalie:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
