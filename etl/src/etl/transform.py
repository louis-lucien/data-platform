"""Transformations (le « T » de l'ETL) : logique PURE, testable sans base.

On sépare volontairement la transformation (pandas, sans I/O) de l'extraction et
du chargement (qui parlent aux bases). Résultat : tout ce fichier se teste avec
de petits DataFrames, sans Postgres ni Cassandra.
"""

import re

import numpy as np
import pandas as pd

NOMS_MOIS = ["", "janvier", "février", "mars", "avril", "mai", "juin",
             "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

# Validation d'email volontairement simple (pas une RFC complète) : présence d'un
# @, d'un domaine avec un point. Suffisant pour un indicateur de qualité.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def dedupe_clients(clients: pd.DataFrame) -> pd.DataFrame:
    """Supprime les doublons injectés et normalise les clients.

    Signature d'un doublon injecté (cf. generator.inject_quality_issues) : même
    email ET même date_inscription qu'une ligne existante, mais client_id
    différent et nom passé en MAJUSCULES. On garde la PREMIÈRE occurrence (l'id
    d'origine, le plus petit) et on supprime les copies.

    Les homonymes légitimes (même nom mais email/date différents) sont CONSERVÉS.
    """
    clients = clients.sort_values("client_id").copy()
    # On ne dédoublonne que sur les lignes ayant un email (la signature s'appuie
    # dessus) ; les lignes sans email ne peuvent pas être des doublons injectés
    # (l'injection copie l'email d'origine).
    a_email = clients["email"].notna()
    doublons = clients[a_email].duplicated(subset=["email", "date_inscription"], keep="first")
    a_supprimer = doublons.reindex(clients.index, fill_value=False)
    propres = clients[~a_supprimer].copy()

    # Normalisation : nom/prénom en casse titre (corrige les noms en MAJUSCULES).
    propres["nom"] = propres["nom"].str.title().str.strip()
    propres["prenom"] = propres["prenom"].str.title().str.strip()
    return propres


def build_dim_client(clients_propres: pd.DataFrame) -> pd.DataFrame:
    """Construit dim_client à partir des clients nettoyés."""
    df = clients_propres
    return pd.DataFrame({
        "client_id": df["client_id"],
        "nom_complet": (df["prenom"] + " " + df["nom"]).str.strip(),
        "type_client": df["type_client"],
        "region_code": df["region_code"],
        # Indicateur qualité : l'email est-il présent ET plausible ?
        "email_valide": df["email"].apply(lambda e: bool(e) and bool(_EMAIL_RE.match(str(e)))),
        "date_inscription": pd.to_datetime(df["date_inscription"]).dt.date,
    })


def build_dim_temps(dates: pd.Series) -> pd.DataFrame:
    """Construit dim_temps à partir de l'ensemble des jours observés."""
    jours = pd.to_datetime(pd.Series(sorted(set(dates)))).dt.normalize()
    return pd.DataFrame({
        "date_id": jours.dt.date,
        "jour": jours.dt.day,
        "mois": jours.dt.month,
        "annee": jours.dt.year,
        "trimestre": jours.dt.quarter,
        "jour_semaine": jours.dt.day_of_week + 1,         # 1=lundi..7=dimanche
        "est_weekend": jours.dt.day_of_week >= 5,
        "nom_mois": jours.dt.month.map(lambda m: NOMS_MOIS[m]),
    })


def build_dim_compteur(compteurs: pd.DataFrame, clients_propres: pd.DataFrame) -> pd.DataFrame:
    """dim_compteur : garde les compteurs dont le client existe après dédoublonnage.

    Un compteur rattaché à un client-doublon supprimé serait orphelin. On
    réconcilie en ne gardant que les compteurs dont le client_id survit.
    """
    clients_valides = set(clients_propres["client_id"])
    df = compteurs[compteurs["client_id"].isin(clients_valides)].copy()
    return df[["compteur_id", "client_id", "region_code", "type_client",
               "mode_facturation", "puissance_kva", "transformateur_id"]]


def aggregate_daily(releves: pd.DataFrame) -> pd.DataFrame:
    """Agrège les relevés HORAIRES en consommation JOURNALIÈRE (fait_consommation_jour).

    energie : somme des 24 heures (fait additif).
    tension/courant : moyennes (faits NON additifs : on ne somme pas des tensions).
    nb_releves : combien d'heures remontées ce jour-là (24 attendu ; moins = trous).
    """
    r = releves.copy()
    r["horodatage"] = pd.to_datetime(r["horodatage"])
    r["date_id"] = r["horodatage"].dt.date
    g = r.groupby(["compteur_id", "date_id"])
    out = g.agg(
        energie_kwh=("energie_kwh", "sum"),
        tension_moy_v=("tension_v", "mean"),
        courant_moy_a=("courant_a", "mean"),
        nb_releves=("energie_kwh", "size"),
    ).reset_index()
    out["energie_kwh"] = out["energie_kwh"].round(3)
    out["tension_moy_v"] = out["tension_moy_v"].round(1)
    out["courant_moy_a"] = out["courant_moy_a"].round(2)
    return out
