"""État du parc de compteurs pour le flux temps réel.

Le producteur fait « vivre » les compteurs déjà générés (data/raw/compteurs.json).
Chaque compteur garde un ÉTAT : son index cumulé (en kWh), qui ne doit faire que
monter, relevé après relevé — un compteur ne redémarre jamais à zéro.

On réutilise `_base_kwh_jour` (la consommation journalière de référence tirée au
batch) pour que chaque compteur garde sa « personnalité » de consommation.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from generator.consumption import draw_daily_base


class MeterFleet:
    """Le parc de compteurs et leur état courant (index cumulé)."""

    def __init__(self, meters: pd.DataFrame, rng: np.random.Generator):
        # Colonnes utiles au modèle de consommation. On garde tout en tableaux
        # numpy alignés (une position = un compteur) : calcul vectorisé rapide.
        self.compteur_id = meters["compteur_id"].to_numpy()
        self.type_client = meters["type_client"].to_numpy()
        self.region_code = meters["region_code"].to_numpy()
        self.puissance_kva = meters["puissance_kva"].to_numpy(dtype=float)
        # Index courant = index initial du compteur (le live reprend là où on est).
        self.index_kwh = meters["index_initial_kwh"].to_numpy(dtype=float).copy()
        # Base journalière : réutilise le tirage du batch si présent, sinon on le
        # retire de la même loi (cohérence garantie par consumption.draw_daily_base).
        if "_base_kwh_jour" in meters:
            self.base_kwh_jour = meters["_base_kwh_jour"].to_numpy(dtype=float)
        else:
            self.base_kwh_jour = draw_daily_base(self.type_client, rng)

    def __len__(self) -> int:
        return len(self.compteur_id)

    @classmethod
    def from_datalake(cls, compteurs_json: Path, clients_csv: Path,
                      rng: np.random.Generator) -> "MeterFleet":
        """Charge le parc en JOIGNANT compteurs.json et clients.csv.

        Le fichier compteurs.json n'embarque PAS type_client ni region_code : ils
        ont été retirés à l'export car ils appartiennent au client (modèle
        relationnel, 3e forme normale). Le producteur en a pourtant besoin pour
        choisir le bon profil de consommation. On les récupère donc par jointure
        sur client_id — exactement la réconciliation qu'imposent des sources
        normalisées.
        """
        meters = pd.DataFrame(json.loads(Path(compteurs_json).read_text(encoding="utf-8")))
        clients = pd.read_csv(clients_csv, usecols=["client_id", "type_client", "region_code"])
        # Les doublons volontaires de clients partagent la même personne mais un
        # client_id distinct ; chaque compteur pointe vers un seul client_id, donc
        # on dédoublonne côté clients par sécurité avant la jointure.
        clients = clients.drop_duplicates("client_id")
        meters = meters.merge(clients, on="client_id", how="left")
        # Filet de sécurité : un compteur sans type (jointure ratée) serait ignoré
        # du modèle. On le signale plutôt que de produire un relevé incohérent.
        if meters["type_client"].isna().any():
            manquants = int(meters["type_client"].isna().sum())
            raise ValueError(f"{manquants} compteur(s) sans type_client après jointure clients")
        return cls(meters, rng)
