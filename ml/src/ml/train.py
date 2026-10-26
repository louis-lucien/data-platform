"""Entraînement du détecteur d'anomalies.

Enchaîne : charger relevés (DW) + inspections (Mongo) -> features -> jointure avec
les étiquettes (seuls les compteurs inspectés) -> split train/test -> entraînement
-> évaluation -> sauvegarde du modèle.

Le modèle entraîné est sauvegardé dans ml/models/ pour être réutilisé au scoring.
"""

import json
import logging
from pathlib import Path

import joblib
from sklearn.model_selection import train_test_split

from ml import data
from ml.features import build_features, labels_from_inspections, FEATURE_COLUMNS
from ml.model import make_model, evaluate, feature_importances

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("ml.train")

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
MODEL_PATH = MODEL_DIR / "detecteur_anomalies.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"


def train(releves, inspections, seed: int = 42):
    features = build_features(releves)
    labels = labels_from_inspections(inspections)

    # Jeu d'entraînement = compteurs À LA FOIS avec features et étiquette.
    dataset = features.merge(labels, on="compteur_id", how="inner")
    log.info(f"Compteurs étiquetés : {len(dataset)} "
             f"(dont {int(dataset['anomalie'].sum())} anomalies)")
    if dataset["anomalie"].nunique() < 2:
        raise ValueError("Pas assez de diversité (une seule classe) pour entraîner.")

    X = dataset[FEATURE_COLUMNS]
    y = dataset["anomalie"]
    # stratify : garde la même proportion d'anomalies dans train et test.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=seed, stratify=y)

    model = make_model(seed)
    model.fit(X_train, y_train)

    ev = evaluate(model, X_test, y_test)
    log.info(f"Évaluation (test) : {ev.as_dict()}")
    log.info(f"Importance des features : {feature_importances(model)}")
    return model, ev


def main() -> int:
    log.info("Chargement des données (DW + Mongo)...")
    releves = data.load_releves_from_dw()
    inspections = data.load_inspections_from_mongo()
    log.info(f"  {len(releves)} relevés, {len(inspections)} inspections")

    model, ev = train(releves, inspections)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(ev.as_dict(), indent=2), encoding="utf-8")
    log.info(f"Modèle sauvegardé : {MODEL_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
