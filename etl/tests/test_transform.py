"""Tests des transformations ETL — sans aucune base (logique pandas pure).

Ce sont les tests les plus importants du projet : ils garantissent que le
NETTOYAGE (dédoublonnage) et l'AGRÉGATION sont corrects avant d'écrire dans le
Data Warehouse.
"""

import pandas as pd

from etl.transform import (
    dedupe_clients, build_dim_client, build_dim_temps,
    build_dim_compteur, aggregate_daily,
)


def test_dedupe_removes_injected_duplicate_keeps_homonym():
    clients = pd.DataFrame([
        # Original + son doublon injecté (même email + date, nom en MAJUSCULES, id plus grand).
        {"client_id": "CLI-000009", "prenom": "Adama", "nom": "Diatta",
         "type_client": "residentiel", "email": "adama.diatta9@yahoo.fr",
         "region_code": "SN-DK", "date_inscription": "2025-12-26"},
        {"client_id": "CLI-001006", "prenom": "Adama", "nom": "DIATTA",
         "type_client": "residentiel", "email": "adama.diatta9@yahoo.fr",
         "region_code": "SN-DK", "date_inscription": "2025-12-26"},
        # Homonyme LÉGITIME : même nom mais email ET date différents -> à garder.
        {"client_id": "CLI-000133", "prenom": "Adama", "nom": "Diatta",
         "type_client": "residentiel", "email": "adama.diatta133@orange.sn",
         "region_code": "SN-DK", "date_inscription": "2024-06-14"},
    ])
    propres = dedupe_clients(clients)
    ids = set(propres["client_id"])
    assert "CLI-000009" in ids          # original gardé
    assert "CLI-001006" not in ids      # doublon injecté supprimé
    assert "CLI-000133" in ids          # homonyme légitime conservé
    assert len(propres) == 2
    # Le nom est normalisé en casse titre (plus de MAJUSCULES).
    assert set(propres["nom"]) == {"Diatta"}


def test_dedupe_keeps_clients_without_email():
    clients = pd.DataFrame([
        {"client_id": "CLI-1", "prenom": "A", "nom": "B", "type_client": "residentiel",
         "email": None, "region_code": "SN-DK", "date_inscription": "2020-01-01"},
        {"client_id": "CLI-2", "prenom": "C", "nom": "D", "type_client": "residentiel",
         "email": None, "region_code": "SN-DK", "date_inscription": "2020-01-01"},
    ])
    # Deux clients sans email, même date : ce ne sont PAS des doublons injectés.
    assert len(dedupe_clients(clients)) == 2


def test_dim_client_email_validity_flag():
    clients = pd.DataFrame([
        {"client_id": "CLI-1", "prenom": "A", "nom": "B", "type_client": "residentiel",
         "email": "a.b@mail.com", "region_code": "SN-DK", "date_inscription": "2020-01-01"},
        {"client_id": "CLI-2", "prenom": "C", "nom": "D", "type_client": "residentiel",
         "email": None, "region_code": "SN-DK", "date_inscription": "2020-01-01"},
        {"client_id": "CLI-3", "prenom": "E", "nom": "F", "type_client": "residentiel",
         "email": "pas-un-email", "region_code": "SN-DK", "date_inscription": "2020-01-01"},
    ])
    dim = build_dim_client(dedupe_clients(clients)).set_index("client_id")
    assert dim.loc["CLI-1", "email_valide"] is True or dim.loc["CLI-1", "email_valide"]
    assert not dim.loc["CLI-2", "email_valide"]      # email manquant
    assert not dim.loc["CLI-3", "email_valide"]      # email mal formé


def test_dim_temps_flags_weekend_and_month_name():
    dates = ["2026-01-03", "2026-01-05"]   # 3 jan = samedi, 5 jan = lundi
    dim = build_dim_temps(pd.Series(dates)).set_index("date_id")
    import datetime as dt
    assert dim.loc[dt.date(2026, 1, 3), "est_weekend"]
    assert not dim.loc[dt.date(2026, 1, 5), "est_weekend"]
    assert dim.loc[dt.date(2026, 1, 3), "nom_mois"] == "janvier"


def test_dim_compteur_drops_orphans():
    compteurs = pd.DataFrame([
        {"compteur_id": "CPT-1", "client_id": "CLI-1", "region_code": "SN-DK",
         "type_client": "residentiel", "mode_facturation": "prepaye",
         "puissance_kva": 6, "transformateur_id": "TR-1"},
        {"compteur_id": "CPT-2", "client_id": "CLI-SUPPRIME", "region_code": "SN-DK",
         "type_client": "residentiel", "mode_facturation": "prepaye",
         "puissance_kva": 6, "transformateur_id": "TR-1"},
    ])
    clients_propres = pd.DataFrame([{"client_id": "CLI-1"}])
    dim = build_dim_compteur(compteurs, clients_propres)
    assert list(dim["compteur_id"]) == ["CPT-1"]     # CPT-2 orphelin écarté


def test_aggregate_daily_sums_energy_and_counts():
    releves = pd.DataFrame([
        {"compteur_id": "CPT-1", "horodatage": "2026-01-01 00:00:00",
         "energie_kwh": 1.0, "tension_v": 230.0, "courant_a": 4.0},
        {"compteur_id": "CPT-1", "horodatage": "2026-01-01 01:00:00",
         "energie_kwh": 2.0, "tension_v": 220.0, "courant_a": 8.0},
    ])
    agg = aggregate_daily(releves)
    assert len(agg) == 1
    row = agg.iloc[0]
    assert row["energie_kwh"] == 3.0          # somme (additif)
    assert row["tension_moy_v"] == 225.0      # moyenne (non additif)
    assert row["nb_releves"] == 2
