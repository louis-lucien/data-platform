"""Chargement de la configuration (fichier YAML, chemin surchargeable par variable d'environnement)."""

import os
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


def load_config(path: str | Path | None = None) -> dict:
    path = Path(path or os.getenv("GENERATOR_CONFIG", DEFAULT_CONFIG_PATH))
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
