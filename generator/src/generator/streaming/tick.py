"""Calcul d'un « tick » : le relevé de tous les compteurs à un instant donné.

C'est l'équivalent temps réel d'UNE colonne de `simulate_history` (une heure,
tous les compteurs). On réutilise les mêmes briques physiques —
`load_factor`, `electrical_measures` — pour garantir que le live est cohérent
avec l'historique batch.

Deux sorties par tick :
  - les relevés (-> topic meter-readings) ;
  - les alertes détectées (-> topic meter-alerts), ex. tension hors bornes.
"""

from datetime import datetime

import numpy as np

from generator import consumption

# Seuils d'alerte (simples et explicites). La norme sénégalaise vise 230 V ±10 %.
TENSION_MIN = 207.0
TENSION_MAX = 253.0


def simulate_weather(region_codes: np.ndarray, moment: datetime,
                     rng: np.random.Generator) -> np.ndarray:
    """Température plausible par compteur, selon l'heure (cycle jour/nuit).

    En batch, la météo venait de l'API Open-Meteo. En temps réel, un flux de démo
    n'a pas besoin de la vraie météo : on simule un cycle journalier autour de la
    température de référence (plus frais la nuit, plus chaud l'après-midi).
    """
    hour = moment.hour + moment.minute / 60
    # Minimum vers 6 h, maximum vers 15 h : sinusoïde décalée.
    daily = 4.0 * np.sin((hour - 9) / 24 * 2 * np.pi)
    noise = rng.normal(0, 1.0, len(region_codes))
    return consumption.REFERENCE_TEMP_C + daily + noise


def compute_tick(fleet, moment: datetime, rng: np.random.Generator) -> list[dict]:
    """Relevés de tous les compteurs à `moment`. Met à jour l'index cumulé du parc."""
    hour = moment.hour
    weekday = moment.weekday()                       # lundi=0 ... dimanche=6
    temperature = simulate_weather(fleet.region_code, moment, rng)

    # Facteur de charge par compteur, selon son type (profil horaire + météo + jour).
    factors = np.empty(len(fleet))
    for kind in consumption.HOURLY_PROFILES:
        mask = fleet.type_client == kind
        if mask.any():
            factors[mask] = consumption.load_factor(kind, hour, weekday, temperature[mask])

    # Énergie de l'heure = base journalière / 24 × facteur × bruit log-normal.
    base_horaire = fleet.base_kwh_jour / 24
    energy = base_horaire * factors * rng.lognormal(0, consumption.NOISE_SIGMA, len(fleet))
    # Plafonnée par la puissance souscrite (comme en batch).
    capacity = fleet.puissance_kva * 0.9
    energy = np.minimum(energy, capacity)

    # L'index cumulé AVANCE (c'est un compteur : il ne recule jamais).
    fleet.index_kwh += energy

    voltage, current = consumption.electrical_measures(energy, energy / capacity, rng)

    horodatage = moment.isoformat()
    readings = []
    for i in range(len(fleet)):
        readings.append({
            "compteur_id": fleet.compteur_id[i],
            "horodatage": horodatage,
            "energie_kwh": round(float(energy[i]), 3),
            "index_kwh": round(float(fleet.index_kwh[i]), 2),
            "tension_v": round(float(voltage[i]), 1),
            "courant_a": round(float(current[i]), 2),
            "region_code": fleet.region_code[i],      # utile aux consumers (conso/région)
            "type_client": fleet.type_client[i],
        })
    return readings


def detect_alerts(readings: list[dict]) -> list[dict]:
    """Repère les relevés anormaux à transformer en alertes (topic meter-alerts).

    Détection SIMPLE et explicable à ce stade (règles de seuil). La détection
    fine par apprentissage (fraude, compteur bloqué) viendra avec le modèle ML
    (étape 10) ; ici on couvre les anomalies électriques évidentes.
    """
    alerts = []
    for r in readings:
        if r["tension_v"] < TENSION_MIN or r["tension_v"] > TENSION_MAX:
            alerts.append({
                "compteur_id": r["compteur_id"],
                "horodatage": r["horodatage"],
                "type_alerte": "tension_hors_bornes",
                "valeur": r["tension_v"],
                "seuil_min": TENSION_MIN,
                "seuil_max": TENSION_MAX,
                "region_code": r["region_code"],
            })
        elif r["energie_kwh"] == 0.0:
            # Index figé sur l'heure : possible compteur bloqué / coupure.
            alerts.append({
                "compteur_id": r["compteur_id"],
                "horodatage": r["horodatage"],
                "type_alerte": "conso_nulle",
                "valeur": 0.0,
                "region_code": r["region_code"],
            })
    return alerts
