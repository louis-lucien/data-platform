"""Lecture du data lake : encapsule la convention `data/raw/<entité>/dt=.../`.

Les chargeurs ne doivent PAS connaître l'arborescence des fichiers : ils
demandent « les clients », « les relevés du 2026-08-27 », et cette couche
retourne un DataFrame ou des enregistrements. Si la convention de nommage du
data lake change un jour, on ne corrige qu'ICI.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd


class DataLake:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        if not self.root.exists():
            raise FileNotFoundError(
                f"Data lake introuvable : {self.root}. "
                "Avez-vous lancé le générateur (python -m generator.batch --out data/raw) ?"
            )

    # -- Repérage des partitions ---------------------------------------------
    def _partitions(self, entity: str) -> list[Path]:
        """Dossiers dt=... d'une entité, triés par date croissante."""
        base = self.root / entity
        if not base.exists():
            return []
        return sorted(p for p in base.glob("dt=*") if p.is_dir())

    def _latest_file(self, entity: str, ext: str) -> Path:
        """Fichier de la partition la plus récente (entités non partitionnées par événement).

        regions, clients, compteurs... sont réécrits en entier à chaque run : on
        prend donc simplement la dernière partition disponible.
        """
        parts = self._partitions(entity)
        if not parts:
            raise FileNotFoundError(f"Aucune partition pour l'entité '{entity}' dans {self.root}")
        path = parts[-1] / f"{entity}.{ext}"
        if not path.exists():
            raise FileNotFoundError(f"Fichier attendu absent : {path}")
        return path

    # -- Lecteurs par format --------------------------------------------------
    def read_csv(self, entity: str, **kwargs) -> pd.DataFrame:
        return pd.read_csv(self._latest_file(entity, "csv"), **kwargs)

    def read_json(self, entity: str) -> list[dict]:
        return json.loads(self._latest_file(entity, "json").read_text(encoding="utf-8"))

    def read_excel(self, entity: str) -> dict[str, pd.DataFrame]:
        """Toutes les feuilles du classeur, en {nom_feuille: DataFrame}."""
        return pd.read_excel(self._latest_file(entity, "xlsx"), sheet_name=None)

    def read_xml_root(self, entity: str) -> ET.Element:
        return ET.parse(self._latest_file(entity, "xml")).getroot()

    # -- Entités partitionnées par jour d'événement (relevés) -----------------
    def iter_csv_partitions(self, entity: str):
        """Génère (jour, DataFrame) pour chaque partition dt=... d'une entité.

        Les relevés comptent des dizaines de partitions (une par jour) et des
        millions de lignes au total : on les traite partition par partition pour
        ne jamais tout charger en mémoire d'un coup.
        """
        for part in self._partitions(entity):
            day = part.name.removeprefix("dt=")
            path = part / f"{entity}.csv"
            if path.exists():
                yield day, pd.read_csv(path)
