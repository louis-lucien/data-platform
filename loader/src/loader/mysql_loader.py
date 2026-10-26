"""Chargement MySQL : facturation (recharges prépayées + factures postpayées).

Le fichier source est un classeur Excel à deux feuilles (`recharges`, `factures`)
produit par le service financier simulé. On charge chaque feuille dans sa table.

Rappel d'architecture : compteur_id n'est PAS une clé étrangère ici (le compteur
vit dans PostgreSQL). On insère tel quel ; l'ETL vérifiera la cohérence inter-bases.
"""

import pandas as pd
import pymysql

from loader.config import Settings
from loader.datalake import DataLake


def _connect(cfg: Settings) -> pymysql.Connection:
    return pymysql.connect(
        host=cfg.mysql_host, port=cfg.mysql_port, database=cfg.mysql_db,
        user=cfg.mysql_user, password=cfg.mysql_password, charset="utf8mb4",
    )


def _none(df: pd.DataFrame) -> pd.DataFrame:
    """Remplace les NaN pandas par None (NULL SQL) — ex. date_paiement des impayées."""
    return df.astype(object).where(df.notna(), None)


def load(cfg: Settings, lake: DataLake) -> dict[str, int]:
    sheets = lake.read_excel("facturation")
    recharges = _none(sheets["recharges"])
    factures = _none(sheets["factures"])

    counts: dict[str, int] = {}
    with _connect(cfg) as conn:
        with conn.cursor() as cur:
            # -- recharges --
            cur.executemany(
                "INSERT IGNORE INTO recharges "
                "(recharge_id, compteur_id, horodatage, montant_fcfa, kwh_achetes, canal, code_recharge) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                [tuple(r) for r in recharges[
                    ["recharge_id", "compteur_id", "horodatage", "montant_fcfa",
                     "kwh_achetes", "canal", "code_recharge"]
                ].itertuples(index=False)],
            )
            counts["recharges"] = len(recharges)

            # -- factures --
            cur.executemany(
                "INSERT IGNORE INTO factures "
                "(facture_id, compteur_id, periode_debut, periode_fin, kwh_factures, montant_ht_fcfa, "
                "tva_fcfa, montant_ttc_fcfa, date_emission, date_echeance, statut, date_paiement) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                [tuple(r) for r in factures[
                    ["facture_id", "compteur_id", "periode_debut", "periode_fin", "kwh_factures",
                     "montant_ht_fcfa", "tva_fcfa", "montant_ttc_fcfa", "date_emission",
                     "date_echeance", "statut", "date_paiement"]
                ].itertuples(index=False)],
            )
            counts["factures"] = len(factures)
        conn.commit()
    return counts
