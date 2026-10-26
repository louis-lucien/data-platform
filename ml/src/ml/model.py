"""Définition et évaluation du modèle — logique ML pure, sans I/O base.

Modèle : RandomForest. Pourquoi ?
  - gère bien les features numériques d'échelles différentes (pas de normalisation
    obligatoire) ;
  - robuste au surapprentissage sur petit jeu ;
  - fournit l'IMPORTANCE des features (interprétabilité : on peut expliquer
    POURQUOI un compteur est signalé).

class_weight='balanced' : compense le déséquilibre (peu d'anomalies). Sans ça, le
modèle apprendrait surtout à dire "normal".
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score

from ml.features import FEATURE_COLUMNS


@dataclass
class Evaluation:
    precision: float      # parmi les compteurs SIGNALÉS, combien sont vraiment anormaux
    recall: float         # parmi les ANOMALIES réelles, combien le modèle a trouvées
    f1: float
    roc_auc: float
    n_test: int
    n_anomalies_test: int

    def as_dict(self) -> dict:
        return {"precision": round(self.precision, 3), "recall": round(self.recall, 3),
                "f1": round(self.f1, 3), "roc_auc": round(self.roc_auc, 3),
                "n_test": self.n_test, "n_anomalies_test": self.n_anomalies_test}


def make_model(seed: int = 42) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=200,
        max_depth=8,                 # borne la profondeur : évite le surapprentissage
        class_weight="balanced",     # compense le déséquilibre des classes
        random_state=seed,
        n_jobs=-1,
    )


def evaluate(model, X_test: pd.DataFrame, y_test: pd.Series) -> Evaluation:
    """Évalue sur precision/recall/F1/ROC-AUC (PAS l'accuracy : trompeuse ici)."""
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    # zero_division=0 : si aucun positif prédit, on renvoie 0 plutôt qu'une erreur.
    return Evaluation(
        precision=precision_score(y_test, y_pred, zero_division=0),
        recall=recall_score(y_test, y_pred, zero_division=0),
        f1=f1_score(y_test, y_pred, zero_division=0),
        roc_auc=roc_auc_score(y_test, y_proba) if y_test.nunique() > 1 else float("nan"),
        n_test=len(y_test),
        n_anomalies_test=int(y_test.sum()),
    )


def feature_importances(model) -> dict[str, float]:
    """Importance de chaque feature : explique ce qui pèse dans la décision."""
    return {name: round(float(imp), 3)
            for name, imp in sorted(zip(FEATURE_COLUMNS, model.feature_importances_),
                                    key=lambda t: t[1], reverse=True)}
