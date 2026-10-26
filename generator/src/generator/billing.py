"""Facturation : recharges des compteurs prépayés et factures mensuelles des postpayés.

Ces données alimentent le système de facturation (MySQL), distinct de la gestion clients (PostgreSQL).
"""

import math

import numpy as np
import pandas as pd

from generator import reference as ref


def tranche_amount(kwh: float, tranches: list[dict]) -> float:
    """Montant HT selon une tarification par tranches progressives."""
    total, lower = 0.0, 0.0
    for tranche in tranches:
        upper = tranche["jusqu_a_kwh"] if tranche["jusqu_a_kwh"] is not None else math.inf
        if kwh > lower:
            total += (min(kwh, upper) - lower) * tranche["prix_kwh"]
        lower = upper
    return round(total, 2)


def daily_consumption(readings: pd.DataFrame) -> pd.DataFrame:
    """Matrice compteur × jour (kWh)."""
    return (readings.assign(jour=readings["horodatage"].dt.normalize())
            .pivot_table(index="compteur_id", columns="jour", values="energie_kwh", aggfunc="sum"))


def _sts_token(rng: np.random.Generator) -> str:
    """Code de recharge à 20 chiffres, au format des compteurs prépayés (norme STS)."""
    return "-".join(f"{rng.integers(0, 10_000):04d}" for _ in range(5))


def build_recharges(meters: pd.DataFrame, daily: pd.DataFrame, tariffs: dict,
                    rng: np.random.Generator) -> pd.DataFrame:
    """Le client recharge quand son crédit passe sous un seuil personnel.

    Simplification assumée : le kWh prépayé est vendu au prix de la première tranche.
    """
    channels, channel_weights = zip(*ref.CANAUX_RECHARGE.items())
    rows = []
    for meter in meters[meters["mode_facturation"] == "prepaye"].itertuples():
        price = tariffs[meter.type_client][0]["prix_kwh"] * (1 + tariffs["tva"])
        threshold = rng.uniform(2, 10)
        credit = rng.uniform(0, 30)
        amounts = ref.MONTANTS_RECHARGE_FCFA if meter.type_client == "residentiel" else ref.MONTANTS_RECHARGE_FCFA[2:]
        for day, used in daily.loc[meter.compteur_id].items():
            credit -= used
            while credit < threshold:
                amount = int(rng.choice(amounts))
                kwh = round(amount / price, 2)
                credit += kwh
                rows.append({
                    "compteur_id": meter.compteur_id,
                    "horodatage": day + pd.Timedelta(minutes=int(rng.integers(7 * 60, 22 * 60))),
                    "montant_fcfa": amount,
                    "kwh_achetes": kwh,
                    "canal": str(rng.choice(channels, p=channel_weights)),
                    "code_recharge": _sts_token(rng),
                })
    recharges = pd.DataFrame(rows).sort_values("horodatage", ignore_index=True)
    recharges.insert(0, "recharge_id", [f"RCH-{k:07d}" for k in range(1, len(recharges) + 1)])
    return recharges


def build_invoices(meters: pd.DataFrame, daily: pd.DataFrame, tariffs: dict,
                   today: pd.Timestamp, rng: np.random.Generator) -> pd.DataFrame:
    """Une facture par compteur postpayé et par mois clos (le mois en cours n'est pas encore facturé)."""
    closed_days = [d for d in daily.columns if d.to_period("M") < today.to_period("M")]
    rows = []
    for meter in meters[meters["mode_facturation"] == "postpaye"].itertuples():
        usage = daily.loc[meter.compteur_id, closed_days]
        for period, days in usage.groupby(usage.index.to_period("M")):
            kwh = round(float(days.sum()), 2)
            amount_ht = tranche_amount(kwh, tariffs[meter.type_client])
            issued = period.end_time.normalize() + pd.Timedelta(days=3)
            due = issued + pd.Timedelta(days=15)
            if due > today:
                status, paid_on = "emise", None
            elif rng.random() < 0.85:
                status, paid_on = "payee", issued + pd.Timedelta(days=int(rng.integers(1, 25)))
            else:
                status, paid_on = "impayee", None
            rows.append({
                "facture_id": f"FAC-{period.strftime('%Y%m')}-{meter.compteur_id[4:]}",
                "compteur_id": meter.compteur_id,
                "periode_debut": days.index.min().date(),
                "periode_fin": days.index.max().date(),
                "kwh_factures": kwh,
                "montant_ht_fcfa": amount_ht,
                "tva_fcfa": round(amount_ht * tariffs["tva"], 2),
                "montant_ttc_fcfa": round(amount_ht * (1 + tariffs["tva"]), 2),
                "date_emission": issued.date(),
                "date_echeance": due.date(),
                "statut": status,
                "date_paiement": paid_on.date() if paid_on is not None else None,
            })
    return pd.DataFrame(rows)
