"""Modèle de consommation électrique horaire d'un compteur.

    énergie horaire = base journalière / 24
                      × profil horaire      (pic du soir chez les ménages, journée au bureau...)
                      × effet température   (climatisation, ventilateurs)
                      × effet jour          (bureaux fermés le dimanche...)
                      × bruit aléatoire

Les mêmes fonctions servent au batch (historique) et au streaming (temps réel),
ce qui garantit des données cohérentes entre les deux flux.
"""

import numpy as np
import pandas as pd

_RAW_PROFILES = {
    # 24 poids, de 0 h à 23 h
    "residentiel": [0.5, 0.4, 0.4, 0.4, 0.4, 0.5, 0.8, 1.0, 0.8, 0.7, 0.7, 0.8,
                    0.9, 0.9, 0.8, 0.8, 0.9, 1.1, 1.5, 1.9, 2.0, 1.8, 1.3, 0.8],
    "professionnel": [0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.6, 1.3, 1.6, 1.7, 1.7,
                      1.5, 1.5, 1.7, 1.7, 1.6, 1.4, 1.0, 0.6, 0.4, 0.4, 0.4, 0.4],
    "agricole": [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.5, 1.4, 1.8, 2.0, 2.0, 1.9,
                 1.6, 1.6, 1.9, 2.0, 1.8, 1.2, 0.4, 0.1, 0.1, 0.1, 0.1, 0.1],
}
# Normalisation : moyenne = 1, donc la somme sur 24 h vaut exactement la base journalière
HOURLY_PROFILES = {k: np.array(v) / np.mean(v) for k, v in _RAW_PROFILES.items()}

# Consommation journalière : loi log-normale (médiane kWh/jour, dispersion)
DAILY_BASE_KWH = {"residentiel": (5.0, 0.5), "professionnel": (40.0, 0.6), "agricole": (25.0, 0.5)}

REFERENCE_TEMP_C = 27.0
TEMP_SENSITIVITY = {"residentiel": 0.04, "professionnel": 0.03, "agricole": 0.01}  # +x % par °C

# Lundi=0 ... dimanche=6
WEEKDAY_FACTORS = {
    "residentiel": np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 1.15]),
    "professionnel": np.array([1.0, 1.0, 1.0, 1.0, 1.0, 0.7, 0.4]),
    "agricole": np.ones(7),
}

NOISE_SIGMA = 0.15
NOMINAL_VOLTAGE = 230.0


def draw_daily_base(client_types: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    base = np.empty(len(client_types))
    for kind, (median, sigma) in DAILY_BASE_KWH.items():
        mask = client_types == kind
        base[mask] = rng.lognormal(np.log(median), sigma, mask.sum())
    return base


def load_factor(client_type: str, hour, weekday, temperature):
    """Facteur multiplicatif sans bruit. Accepte des scalaires ou des tableaux numpy."""
    profile = HOURLY_PROFILES[client_type][hour]
    temp_effect = np.clip(1 + TEMP_SENSITIVITY[client_type] * (temperature - REFERENCE_TEMP_C), 0.7, 1.6)
    return profile * temp_effect * WEEKDAY_FACTORS[client_type][weekday]


def electrical_measures(energy_kwh, load_ratio, rng: np.random.Generator):
    """Tension (chute quand la charge augmente) et courant moyen sur l'heure (I = P / U)."""
    voltage = np.clip(rng.normal(NOMINAL_VOLTAGE, 3, np.shape(energy_kwh)) - 10 * load_ratio, 190, 250)
    current = energy_kwh * 1000 / voltage
    return voltage, current


def inject_anomalies(energy: np.ndarray, hour_of_day: np.ndarray, rates: dict,
                     rng: np.random.Generator) -> list[dict]:
    """Modifie `energy` en place et renvoie la vérité terrain (compteur, type, heure de début)."""
    n_meters, n_hours = energy.shape
    candidates = rng.permutation(n_meters)
    truth, cursor = [], 0
    for kind, rate in rates.items():
        count = int(round(rate * n_meters))
        for meter in candidates[cursor:cursor + count]:
            start = int(rng.integers(int(n_hours * 0.2), int(n_hours * 0.7)))
            if kind == "fraude_bypass":
                energy[meter, start:] *= rng.uniform(0.1, 0.4)
            elif kind == "fraude_intermittente":
                hours = hour_of_day[start:]
                night = (hours >= 20) | (hours < 6)
                energy[meter, start:][night & (rng.random(len(hours)) < 0.7)] = 0.0
            elif kind == "compteur_bloque":
                energy[meter, start:] = 0.0
            else:
                raise ValueError(f"type d'anomalie inconnu : {kind}")
            truth.append({"meter_idx": int(meter), "type_anomalie": kind, "debut_idx": start})
        cursor += count
    return truth


def simulate_history(meters: pd.DataFrame, weather: pd.DataFrame, hours: pd.DatetimeIndex,
                     anomaly_rates: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, list[dict]]:
    """Relevés horaires de tous les compteurs sur `hours`.

    `meters` doit contenir : compteur_id, type_client, region_code, _base_kwh_jour,
    puissance_kva, index_initial_kwh.
    """
    hour_of_day = hours.hour.to_numpy()
    weekday = hours.day_of_week.to_numpy()

    temps = (weather.pivot_table(index="horodatage", columns="region_code", values="temperature_c")
             .reindex(hours).interpolate(limit_direction="both"))
    temps = temps.reindex(columns=meters["region_code"].unique()).fillna(REFERENCE_TEMP_C)
    temperature = temps[meters["region_code"]].to_numpy().T  # (compteurs, heures)

    types = meters["type_client"].to_numpy()
    factors = np.empty(temperature.shape)
    for kind in HOURLY_PROFILES:
        mask = types == kind
        factors[mask] = load_factor(kind, hour_of_day[None, :], weekday[None, :], temperature[mask])

    base = meters["_base_kwh_jour"].to_numpy()[:, None] / 24
    energy = base * factors * rng.lognormal(0, NOISE_SIGMA, factors.shape)
    capacity = meters["puissance_kva"].to_numpy()[:, None] * 0.9  # kWh max en une heure
    energy = np.minimum(energy, capacity)

    truth = inject_anomalies(energy, hour_of_day, anomaly_rates, rng)

    voltage, current = electrical_measures(energy, energy / capacity, rng)
    index = meters["index_initial_kwh"].to_numpy()[:, None] + np.cumsum(energy, axis=1)

    readings = pd.DataFrame({
        "compteur_id": np.repeat(meters["compteur_id"].to_numpy(), len(hours)),
        "horodatage": np.tile(hours.to_numpy(), len(meters)),
        "energie_kwh": energy.ravel().round(3),
        "index_kwh": index.ravel().round(2),
        "tension_v": voltage.ravel().round(1),
        "courant_a": current.ravel().round(2),
    })
    for item in truth:
        item["compteur_id"] = meters["compteur_id"].iat[item["meter_idx"]]
        item["debut"] = hours[item.pop("debut_idx")]
    return readings, truth
