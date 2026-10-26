"""Écriture des fichiers dans une zone « raw » organisée comme un Data Lake.

    data/raw/<entité>/dt=<AAAA-MM-JJ>/<entité>.<format>
    data/raw/_runs/<run_id>.json      ← manifeste : ce qui a été produit, quand, combien de lignes

Le partitionnement `dt=` est la convention Hive/Spark : un traitement peut ne relire qu'un jour.
Le format de chaque entité imite le système qui la produirait dans la réalité.
"""

import json
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def _json_default(value):
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"type non sérialisable : {type(value)}")


class DataLakeWriter:
    def __init__(self, root: Path, run_id: str, run_date: date):
        self.root = Path(root)
        self.run_id = run_id
        self.run_date = run_date
        self.files: list[dict] = []

    def _target(self, entity: str, ext: str, partition: date | None = None) -> Path:
        path = self.root / entity / f"dt={partition or self.run_date}" / f"{entity}.{ext}"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _register(self, entity: str, path: Path, rows: int) -> None:
        self.files.append({
            "entite": entity,
            "chemin": path.relative_to(self.root).as_posix(),
            "lignes": rows,
            "octets": path.stat().st_size,
        })

    def csv(self, entity: str, df: pd.DataFrame) -> None:
        path = self._target(entity, "csv")
        df.to_csv(path, index=False, encoding="utf-8")
        self._register(entity, path, len(df))

    def csv_partitioned(self, entity: str, df: pd.DataFrame, date_column: str) -> None:
        """Un fichier par jour d'événement (et non par jour de génération)."""
        for day, part in df.groupby(df[date_column].dt.date):
            path = self._target(entity, "csv", partition=day)
            part.to_csv(path, index=False, encoding="utf-8")
            self._register(entity, path, len(part))

    def json(self, entity: str, records: list[dict]) -> None:
        path = self._target(entity, "json")
        path.write_text(json.dumps(records, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
        self._register(entity, path, len(records))

    def excel(self, entity: str, sheets: dict[str, pd.DataFrame]) -> None:
        path = self._target(entity, "xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name, index=False)
        self._register(entity, path, sum(len(df) for df in sheets.values()))

    def xml(self, entity: str, root: ET.Element, rows: int) -> None:
        path = self._target(entity, "xml")
        ET.indent(root)
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        self._register(entity, path, rows)

    def yaml(self, entity: str, data: dict) -> None:
        path = self._target(entity, "yaml")
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        self._register(entity, path, 1)

    def write_manifest(self, metadata: dict) -> Path:
        path = self.root / "_runs" / f"{self.run_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        manifest = {"run_id": self.run_id, **metadata, "fichiers": self.files}
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
        return path


def network_to_xml(regions: pd.DataFrame, postes: pd.DataFrame, transformateurs: pd.DataFrame) -> ET.Element:
    """Topologie hiérarchique région > poste source > transformateur (export type SIG)."""
    root = ET.Element("reseau", operateur="Distributeur fictif", pays="SN")
    for region in regions.itertuples():
        region_el = ET.SubElement(root, "region", code=region.code, nom=region.nom)
        for poste in postes[postes["region_code"] == region.code].itertuples():
            poste_el = ET.SubElement(region_el, "poste_source", id=poste.poste_id, tension_kv=str(poste.tension_kv),
                                     capacite_mva=str(poste.capacite_mva))
            ET.SubElement(poste_el, "nom").text = poste.nom
            ET.SubElement(poste_el, "position", lat=str(poste.lat), lon=str(poste.lon))
            for tr in transformateurs[transformateurs["poste_id"] == poste.poste_id].itertuples():
                ET.SubElement(poste_el, "transformateur", id=tr.transformateur_id,
                              capacite_kva=str(tr.capacite_kva), annee_mise_service=str(tr.annee_mise_service),
                              lat=str(tr.lat), lon=str(tr.lon))
    return root
