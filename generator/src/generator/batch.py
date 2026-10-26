"""Génération batch complète : référentiels, historique de relevés, facturation, inspections.

Usage :
    python -m generator.batch --out ../data/raw
    python -m generator.batch --clients 200 --days 7 --offline
"""

import argparse
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

from generator import billing, consumption, entities
from generator.config import load_config
from generator.exporters import DataLakeWriter, network_to_xml
from generator.logging_setup import setup_logging
from generator.sources import weather as weather_source
from generator.sources import wikipedia

log = logging.getLogger("generator.batch")

CLIENT_COLUMNS = ["client_id", "prenom", "nom", "type_client", "raison_sociale", "telephone", "email",
                  "adresse", "region_code", "date_inscription"]
METER_COLUMNS = ["compteur_id", "numero_serie", "client_id", "transformateur_id", "modele", "mode_facturation",
                 "puissance_kva", "date_pose", "index_initial_kwh", "statut"]


@contextmanager
def step(name: str):
    started = time.perf_counter()
    log.info(f"Début : {name}", extra={"fields": {"etape": name}})
    yield
    duration = round(time.perf_counter() - started, 2)
    log.info(f"Fin : {name}", extra={"fields": {"etape": name, "duree_s": duration}})


def run(cfg: dict, out_dir: Path, offline: bool = False) -> Path:
    if not 1 <= cfg["history_days"] <= 90:
        raise ValueError("history_days doit être compris entre 1 et 90 (limite de l'API Open-Meteo)")

    # Un flux aléatoire indépendant par usage : ajouter un tirage dans un module
    # ne modifie pas les données produites par les autres.
    streams = np.random.SeedSequence(cfg["seed"]).spawn(6)
    rng_weather, rng_network, rng_clients, rng_usage, rng_billing, rng_ops = map(np.random.default_rng, streams)
    fake = Faker("fr_FR")
    fake.seed_instance(cfg["seed"])

    now = datetime.now(timezone.utc)
    today = pd.Timestamp.now().normalize()
    hours = pd.date_range(end=today - pd.Timedelta(hours=1), periods=cfg["history_days"] * 24, freq="h")
    writer = DataLakeWriter(out_dir, run_id=now.strftime("%Y%m%dT%H%M%SZ"), run_date=today.date())

    with step("référentiel régions (scraping)"):
        regions = wikipedia.get_regions(cfg["sources"], out_dir / "_cache", offline)
    with step("météo (API)"):
        weather = weather_source.get_weather(cfg["sources"], regions.to_dict("records"), hours, rng_weather, offline)
    with step("réseau électrique"):
        postes, transformateurs, clients_per_region = entities.build_network(regions, cfg["clients"], cfg, rng_network)
    with step("clients et compteurs"):
        clients, meters = entities.build_clients_and_meters(regions, clients_per_region, transformateurs,
                                                            cfg, rng_clients, fake)
    with step("historique des relevés"):
        readings, truth = consumption.simulate_history(meters, weather, hours, cfg["anomalies"], rng_usage)
    with step("facturation"):
        daily = billing.daily_consumption(readings)
        recharges = billing.build_recharges(meters, daily, cfg["tarifs"], rng_billing)
        invoices = billing.build_invoices(meters, daily, cfg["tarifs"], today, rng_billing)
    with step("inspections terrain"):
        inspections = entities.build_inspections(truth, meters, hours, cfg["inspections"], rng_ops, fake)
        clients = entities.inject_quality_issues(clients, cfg["qualite"], rng_ops)

    with step("export data lake"):
        writer.csv("regions", regions)                                     # scraping → CSV
        writer.json("meteo", weather.to_dict("records"))                   # API → JSON
        writer.xml("reseau", network_to_xml(regions, postes, transformateurs),
                   rows=len(postes) + len(transformateurs))                # export SIG → XML
        writer.csv("clients", clients[CLIENT_COLUMNS])                     # export CRM → CSV
        writer.json("compteurs", meters[METER_COLUMNS].to_dict("records"))  # plateforme compteurs → JSON
        writer.excel("facturation", {"recharges": recharges, "factures": invoices})  # service financier → Excel
        writer.yaml("tarifs", cfg["tarifs"])                               # grille tarifaire → YAML
        writer.json("inspections", inspections)                            # application terrain → JSON
        writer.csv_partitioned("releves", readings, "horodatage")          # historique compteurs → CSV/jour

    manifest = writer.write_manifest({
        "genere_le": now,
        "seed": cfg["seed"],
        "parametres": {"clients": cfg["clients"], "history_days": cfg["history_days"], "offline": offline},
        "periode": {"debut": hours[0], "fin": hours[-1]},
        "sources": {"regions": regions["source"].iat[0], "meteo": sorted(weather["source"].unique())},
        "volumes": {
            "regions": len(regions), "postes": len(postes), "transformateurs": len(transformateurs),
            "clients": len(clients), "compteurs": len(meters), "releves": len(readings),
            "recharges": len(recharges), "factures": len(invoices), "inspections": len(inspections),
            "anomalies_injectees": len(truth),
        },
    })
    log.info("Génération terminée", extra={"fields": {"manifeste": str(manifest)}})
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère le jeu de données batch de la plateforme énergie.")
    parser.add_argument("--config", help="chemin du fichier config.yaml")
    parser.add_argument("--out", default="data/raw", help="dossier racine de la zone raw")
    parser.add_argument("--clients", type=int, help="surcharge le nombre de clients")
    parser.add_argument("--days", type=int, help="surcharge la profondeur d'historique")
    parser.add_argument("--seed", type=int, help="surcharge la graine aléatoire")
    parser.add_argument("--offline", action="store_true", help="n'appelle aucune source externe")
    args = parser.parse_args()

    setup_logging("generator-batch")
    cfg = load_config(args.config)
    for key, value in {"clients": args.clients, "history_days": args.days, "seed": args.seed}.items():
        if value is not None:
            cfg[key] = value
    run(cfg, Path(args.out), args.offline)


if __name__ == "__main__":
    main()
