"""Construction des features (caractéristiques) par compteur — logique pure.

Une ligne = un compteur, décrite par son PROFIL de consommation. Les features
sont choisies pour capturer les SIGNATURES des anomalies injectées :

  - compteur_bloque        -> beaucoup d'heures à zéro, en continu.
  - fraude_intermittente   -> zéros concentrés la NUIT.
  - fraude_bypass          -> CHUTE de consommation (2e moitié << 1re moitié).

Aucune feature ne dépend de l'inspection : pas de fuite de données.
Testable sans base (on passe un DataFrame de relevés).
"""

import numpy as np
import pandas as pd


def build_features(releves: pd.DataFrame) -> pd.DataFrame:
    """Agrège les relevés horaires en une ligne de features par compteur.

    `releves` doit contenir : compteur_id, horodatage, energie_kwh, tension_v.
    """
    r = releves.copy()
    r["horodatage"] = pd.to_datetime(r["horodatage"])
    r["heure"] = r["horodatage"].dt.hour
    r["est_nuit"] = (r["heure"] >= 20) | (r["heure"] < 6)
    # Rang temporel relatif de chaque relevé (0 = début, 1 = fin) pour détecter
    # une chute dans le temps (bypass qui démarre en cours d'historique).
    r = r.sort_values(["compteur_id", "horodatage"])

    lignes = []
    for compteur_id, g in r.groupby("compteur_id", sort=False):
        energie = g["energie_kwh"].to_numpy()
        n = len(energie)
        moitie = n // 2
        conso_1re = energie[:moitie].mean() if moitie else 0.0
        conso_2de = energie[moitie:].mean() if moitie else energie.mean()
        nuit = g["est_nuit"].to_numpy()

        lignes.append({
            "compteur_id": compteur_id,
            # Niveau et variabilité
            "conso_moy": energie.mean(),
            "conso_std": energie.std(),
            "conso_max": energie.max(),
            # Heures à zéro : signature forte de compteur_bloque / intermittente
            "part_zero": float((energie == 0).mean()),
            "part_zero_nuit": float((energie[nuit] == 0).mean()) if nuit.any() else 0.0,
            "part_zero_jour": float((energie[~nuit] == 0).mean()) if (~nuit).any() else 0.0,
            # Chute dans le temps : signature de bypass (2de moitié bien plus basse)
            "ratio_2de_1re": float(conso_2de / conso_1re) if conso_1re > 0 else 1.0,
            # Ratio nuit/jour : une conso nocturne anormalement basse
            "ratio_nuit_jour": _ratio(energie[nuit], energie[~nuit]),
        })
    return pd.DataFrame(lignes)


def _ratio(nuit: np.ndarray, jour: np.ndarray) -> float:
    m_jour = jour.mean() if len(jour) else 0.0
    m_nuit = nuit.mean() if len(nuit) else 0.0
    return float(m_nuit / m_jour) if m_jour > 0 else 0.0


# Les colonnes utilisées par le modèle (ordre figé : entraînement = scoring).
FEATURE_COLUMNS = [
    "conso_moy", "conso_std", "conso_max",
    "part_zero", "part_zero_nuit", "part_zero_jour",
    "ratio_2de_1re", "ratio_nuit_jour",
]


def labels_from_inspections(inspections: list[dict]) -> pd.DataFrame:
    """Transforme les inspections en étiquettes binaires par compteur.

    resultat == 'conforme'  -> 0 (normal)
    resultat != 'conforme'  -> 1 (anomalie : fraude ou défaut technique)

    Seuls les compteurs INSPECTÉS reçoivent une étiquette (le reste est inconnu).
    Si un compteur a plusieurs inspections, une seule anomalie suffit à l'étiqueter 1.
    """
    rows = [{"compteur_id": ins["compteur_id"],
             "anomalie": 0 if ins.get("resultat") == "conforme" else 1}
            for ins in inspections]
    if not rows:
        return pd.DataFrame(columns=["compteur_id", "anomalie"])
    df = pd.DataFrame(rows)
    return df.groupby("compteur_id", as_index=False)["anomalie"].max()
