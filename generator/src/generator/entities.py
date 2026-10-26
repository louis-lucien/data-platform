"""Entités métier : réseau électrique, clients, compteurs, inspections terrain."""

import math
import unicodedata

import numpy as np
import pandas as pd
from faker import Faker

from generator import reference as ref
from generator.consumption import draw_daily_base


def allocate(total: int, weights: np.ndarray) -> np.ndarray:
    """Répartit `total` proportionnellement aux poids (méthode du plus fort reste : la somme est exacte)."""
    shares = total * weights / weights.sum()
    counts = np.floor(shares).astype(int)
    remainder = total - counts.sum()
    counts[np.argsort(shares - counts)[::-1][:remainder]] += 1
    return counts


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _phone(rng: np.random.Generator) -> str:
    digits = rng.integers(0, 10, 7)
    return f"+221 7{rng.choice([0, 6, 7, 8])}{digits[0]} {digits[1]}{digits[2]}{digits[3]} " \
           f"{digits[4]}{digits[5]} {digits[6]}{rng.integers(0, 10)}"


def build_network(regions: pd.DataFrame, n_clients: int, cfg: dict, rng: np.random.Generator):
    """Postes sources et transformateurs, dimensionnés selon la population de chaque région."""
    clients_per_region = allocate(n_clients, regions["population"].to_numpy(dtype=float))
    postes, transformateurs = [], []
    for region, n_region_clients in zip(regions.to_dict("records"), clients_per_region):
        suffix = region["code"][3:]
        n_postes = 1 + int(region["population"] // cfg["reseau"]["habitants_par_poste_source"])
        region_postes = [f"PS-{suffix}-{k:02d}" for k in range(1, n_postes + 1)]
        for k, poste_id in enumerate(region_postes, start=1):
            postes.append({
                "poste_id": poste_id,
                "nom": f"Poste {region['chef_lieu']} {k}",
                "region_code": region["code"],
                "tension_kv": 90,
                "capacite_mva": int(rng.choice([20, 40, 80])),
                "lat": round(region["lat"] + rng.normal(0, 0.05), 5),
                "lon": round(region["lon"] + rng.normal(0, 0.05), 5),
            })
        n_transfos = max(1, math.ceil(n_region_clients / cfg["reseau"]["clients_par_transformateur"]))
        for k in range(1, n_transfos + 1):
            transformateurs.append({
                "transformateur_id": f"TR-{suffix}-{k:03d}",
                "poste_id": region_postes[(k - 1) % n_postes],
                "region_code": region["code"],
                "capacite_kva": int(rng.choice(ref.CAPACITES_TRANSFORMATEURS_KVA)),
                "annee_mise_service": int(rng.integers(1995, 2025)),
                "lat": round(region["lat"] + rng.normal(0, 0.03), 5),
                "lon": round(region["lon"] + rng.normal(0, 0.03), 5),
            })
    return pd.DataFrame(postes), pd.DataFrame(transformateurs), clients_per_region


def build_clients_and_meters(regions: pd.DataFrame, clients_per_region: np.ndarray,
                             transformateurs: pd.DataFrame, cfg: dict,
                             rng: np.random.Generator, fake: Faker):
    """Un client = un compteur. Les colonnes préfixées par `_` sont internes (non exportées)."""
    type_names = list(cfg["types_clients"])
    type_weights = np.array([cfg["types_clients"][t] for t in type_names])
    clients, meters = [], []
    for region, count in zip(regions.to_dict("records"), clients_per_region):
        weights = type_weights.copy()
        if region["code"] in ref.URBAN_REGIONS:
            weights[type_names.index("agricole")] = 0
        region_transfos = transformateurs.loc[transformateurs["region_code"] == region["code"],
                                              "transformateur_id"].to_numpy()
        for _ in range(count):
            n = len(clients) + 1
            kind = str(rng.choice(type_names, p=weights / weights.sum()))
            prenom, nom = str(rng.choice(ref.PRENOMS)), str(rng.choice(ref.NOMS))
            client_id = f"CLI-{n:06d}"
            inscription = fake.date_between(start_date="-10y", end_date="-90d")
            clients.append({
                "client_id": client_id,
                "prenom": prenom,
                "nom": nom,
                "type_client": kind,
                "raison_sociale": f"Ets {nom} & Fils" if kind == "professionnel" else None,
                "telephone": _phone(rng),
                "email": f"{_ascii(prenom)}.{_ascii(nom)}{n}@"
                         f"{rng.choice(['gmail.com', 'yahoo.fr', 'outlook.com', 'orange.sn'])}",
                "adresse": f"{rng.choice(ref.QUARTIERS)}, {region['chef_lieu']}",
                "region_code": region["code"],
                "date_inscription": inscription,
            })
            meters.append({
                "compteur_id": f"CPT-{10_000_000 + n}",
                "numero_serie": fake.bothify("??#########").upper(),
                "client_id": client_id,
                "transformateur_id": str(rng.choice(region_transfos)),
                "modele": str(rng.choice(ref.MODELES_COMPTEURS)),
                "mode_facturation": "prepaye" if rng.random() < cfg["part_prepaye"][kind] else "postpaye",
                "puissance_kva": int(rng.choice(ref.PUISSANCES_KVA[kind])),
                "date_pose": fake.date_between(start_date=inscription, end_date="-60d"),
                "index_initial_kwh": round(float(rng.uniform(100, 30_000)), 2),
                "statut": "actif",
                "type_client": kind,
                "region_code": region["code"],
            })
    meters = pd.DataFrame(meters)
    meters["_base_kwh_jour"] = draw_daily_base(meters["type_client"].to_numpy(), rng)
    return pd.DataFrame(clients), meters


def inject_quality_issues(clients: pd.DataFrame, rates: dict, rng: np.random.Generator) -> pd.DataFrame:
    """Dégrade volontairement les données, comme dans un vrai système source : l'ETL devra les nettoyer."""
    clients = clients.copy()
    n = len(clients)

    def pick(rate):
        return rng.random(n) < rate

    clients.loc[pick(rates["email_manquant"]), "email"] = None
    bad_phone = pick(rates["telephone_mal_formate"])
    clients.loc[bad_phone, "telephone"] = (clients.loc[bad_phone, "telephone"]
                                           .str.replace("+221 ", "00221", regex=False)
                                           .str.replace(" ", "", regex=False))
    upper = pick(rates["nom_en_majuscules"])
    clients.loc[upper, "nom"] = clients.loc[upper, "nom"].str.upper()

    # Doublons : même personne réinscrite sous un nouvel identifiant, nom en majuscules
    duplicates = clients.sample(n=max(1, int(n * rates["doublons_clients"])),
                                random_state=int(rng.integers(1 << 31))).copy()
    duplicates["client_id"] = [f"CLI-{n + k:06d}" for k in range(1, len(duplicates) + 1)]
    duplicates["nom"] = duplicates["nom"].str.upper()
    return pd.concat([clients, duplicates], ignore_index=True)


def build_inspections(truth: list[dict], meters: pd.DataFrame, hours: pd.DatetimeIndex,
                      cfg: dict, rng: np.random.Generator, fake: Faker) -> list[dict]:
    """Rapports d'intervention terrain : documents à structure variable (cible : MongoDB).

    Ils fournissent les étiquettes du modèle ML : seule une partie des anomalies est inspectée,
    comme dans la réalité.
    """
    technicians = [{"matricule": f"TECH-{k:03d}", "nom": f"{rng.choice(ref.PRENOMS)} {rng.choice(ref.NOMS)}"}
                   for k in range(1, 13)]
    end = hours[-1]
    anomalous = {item["compteur_id"]: item for item in truth}
    visits = []

    for item in truth:
        if rng.random() < cfg["taux_detection_anomalies"]:
            date = item["debut"] + pd.Timedelta(days=int(rng.integers(2, 11)))
            if date <= end:
                visits.append((item["compteur_id"], date))
    normal_ids = meters.loc[~meters["compteur_id"].isin(anomalous), "compteur_id"].to_numpy()
    for meter_id in normal_ids[rng.random(len(normal_ids)) < cfg["taux_controle_aleatoire"]]:
        visits.append((meter_id, hours[int(rng.integers(len(hours)))]))

    reports = []
    for k, (meter_id, date) in enumerate(sorted(visits, key=lambda v: v[1]), start=1):
        report = {
            "inspection_id": f"INS-{k:05d}",
            "compteur_id": meter_id,
            "date_inspection": date.replace(hour=int(rng.integers(8, 18)), minute=int(rng.integers(0, 60))),
            "technicien": technicians[int(rng.integers(len(technicians)))],
            "photos": int(rng.integers(0, 6)),
        }
        kind = anomalous.get(meter_id, {}).get("type_anomalie")
        if kind in ("fraude_bypass", "fraude_intermittente"):
            report |= {
                "resultat": "fraude_confirmee",
                "type_anomalie": kind,
                "constat": {"scelle_casse": True, "derivation_detectee": kind == "fraude_bypass"},
                "actions": ["proces_verbal", "regularisation_facturee"],
                "montant_regularisation_fcfa": int(rng.integers(50, 500)) * 1000,
            }
        elif kind == "compteur_bloque":
            report |= {
                "resultat": "defaut_technique",
                "type_anomalie": kind,
                "constat": {"afficheur": "fige", "communication": "perdue"},
                "actions": ["remplacement_compteur"],
                "piece_remplacee": meters.loc[meters["compteur_id"] == meter_id, "modele"].iat[0],
            }
        else:
            report |= {"resultat": "conforme", "constat": {"scelle_intact": True}, "actions": []}
        if rng.random() < 0.3:
            report["commentaire"] = fake.sentence(nb_words=10)
        reports.append(report)
    return reports
