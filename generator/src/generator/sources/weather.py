"""Météo horaire par région via l'API Open-Meteo (gratuite, sans clé).

La température influence la consommation (climatisation, ventilation) :
c'est une variable explicative précieuse pour le modèle ML.
"""

import logging

import numpy as np
import pandas as pd

from generator.sources import http_session

log = logging.getLogger(__name__)

TIMEZONE = "Africa/Dakar"  # GMT toute l'année, pas d'heure d'été


def fetch_region_weather(session, cfg: dict, region: dict, past_days: int) -> pd.DataFrame:
    params = {
        "latitude": region["lat"],
        "longitude": region["lon"],
        "hourly": "temperature_2m,relative_humidity_2m",
        "past_days": past_days,
        "forecast_days": 1,
        "timezone": TIMEZONE,
    }
    response = session.get(cfg["open_meteo_url"], params=params, timeout=cfg["timeout_secondes"])
    response.raise_for_status()
    hourly = response.json()["hourly"]
    return pd.DataFrame({
        "region_code": region["code"],
        "horodatage": pd.to_datetime(hourly["time"]),
        "temperature_c": hourly["temperature_2m"],
        "humidite_pct": hourly["relative_humidity_2m"],
        "source": "open-meteo",
    })


def synthetic_weather(region: dict, hours: pd.DatetimeIndex, rng: np.random.Generator) -> pd.DataFrame:
    """Repli hors-ligne : cycle jour/nuit plausible (min vers 6 h, max vers 15 h)."""
    base = 27 + (16.5 - region["lat"]) * 0.8  # le sud-est est plus chaud que la côte
    daily_cycle = 4.5 * np.sin((hours.hour.to_numpy() - 9) / 24 * 2 * np.pi)
    return pd.DataFrame({
        "region_code": region["code"],
        "horodatage": hours,
        "temperature_c": np.round(base + daily_cycle + rng.normal(0, 0.8, len(hours)), 1),
        "humidite_pct": np.clip(rng.normal(60, 12, len(hours)), 15, 100).round(),
        "source": "synthetique",
    })


def get_weather(cfg: dict, regions: list[dict], hours: pd.DatetimeIndex,
                rng: np.random.Generator, offline: bool = False) -> pd.DataFrame:
    past_days = min(92, (pd.Timestamp.now().normalize() - hours[0].normalize()).days + 1)
    session = None if offline else http_session(cfg["user_agent"])
    frames = []
    for region in regions:
        try:
            if offline:
                raise ConnectionError("mode hors-ligne")
            frame = fetch_region_weather(session, cfg, region, past_days)
        except Exception as exc:
            log.warning("Météo indisponible, repli synthétique",
                        extra={"fields": {"region": region["code"], "erreur": str(exc)}})
            frame = synthetic_weather(region, hours, rng)
        frames.append(frame[frame["horodatage"].between(hours[0], hours[-1])])
    return pd.concat(frames, ignore_index=True)
