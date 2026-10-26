"""Chargement PostgreSQL (schéma oltp) : référentiel réseau + clients + compteurs.

Ordre d'insertion imposé par les clés étrangères :
    regions -> postes_source -> transformateurs -> clients -> compteurs
On ne peut pas insérer un compteur avant son transformateur, ni un client avant
sa région. Cette couche respecte cet ordre.

Les données sont chargées BRUTES. En particulier, les clients contiennent des
DOUBLONS volontaires (même personne, client_id différent) : comme la clé primaire
est client_id, ces lignes entrent sans conflit — c'est voulu, l'ETL les
dédoublonnera plus tard.
"""

import psycopg
from psycopg.types.enum import register_enum, EnumInfo

from loader.config import Settings
from loader.datalake import DataLake
from loader.network import parse_network


def _connect(cfg: Settings) -> psycopg.Connection:
    return psycopg.connect(
        host=cfg.pg_host, port=cfg.pg_port, dbname=cfg.pg_db,
        user=cfg.pg_user, password=cfg.pg_password,
    )


def load(cfg: Settings, lake: DataLake) -> dict[str, int]:
    """Charge le schéma oltp. Renvoie le nombre de lignes par table."""
    regions = lake.read_csv("regions")
    clients = lake.read_csv("clients", keep_default_na=True)
    compteurs = lake.read_json("compteurs")
    postes_d, transfos_d = parse_network(lake)
    postes = [(p["poste_id"], p["nom"], p["region_code"], p["tension_kv"],
               p["capacite_mva"], p["lat"], p["lon"]) for p in postes_d]
    transfos = [(t["transformateur_id"], t["poste_id"], t["region_code"], t["capacite_kva"],
                 t["annee_mise_service"], t["lat"], t["lon"]) for t in transfos_d]

    counts: dict[str, int] = {}
    with _connect(cfg) as conn:
        conn.execute("SET search_path TO oltp")
        # Les types ENUM Postgres doivent être connus de psycopg pour l'insertion.
        for enum_name in ("type_client_enum", "mode_facturation_enum", "statut_compteur_enum"):
            info = EnumInfo.fetch(conn, enum_name)
            if info:
                register_enum(info, conn)

        with conn.cursor() as cur:
            # -- regions --
            rows = [
                (r.code, r.nom, r.chef_lieu, r.lat, r.lon, int(r.superficie_km2), int(r.population))
                for r in regions.itertuples()
            ]
            cur.executemany(
                "INSERT INTO regions (code, nom, chef_lieu, latitude, longitude, superficie_km2, population) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (code) DO NOTHING",
                rows,
            )
            counts["regions"] = len(rows)

            # -- postes_source --
            cur.executemany(
                "INSERT INTO postes_source (poste_id, nom, region_code, tension_kv, capacite_mva, latitude, longitude) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (poste_id) DO NOTHING",
                postes,
            )
            counts["postes_source"] = len(postes)

            # -- transformateurs --
            cur.executemany(
                "INSERT INTO transformateurs "
                "(transformateur_id, poste_id, region_code, capacite_kva, annee_mise_service, latitude, longitude) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (transformateur_id) DO NOTHING",
                transfos,
            )
            counts["transformateurs"] = len(transfos)

            # -- clients (données brutes, avec doublons et emails manquants) --
            # pandas lit les cases vides comme NaN ; on les repasse en None (NULL SQL).
            clients = clients.astype(object).where(clients.notna(), None)
            crows = [
                (c.client_id, c.prenom, c.nom, c.type_client, c.raison_sociale,
                 c.telephone, c.email, c.adresse, c.region_code, c.date_inscription)
                for c in clients.itertuples()
            ]
            cur.executemany(
                "INSERT INTO clients (client_id, prenom, nom, type_client, raison_sociale, "
                "telephone, email, adresse, region_code, date_inscription) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (client_id) DO NOTHING",
                crows,
            )
            counts["clients"] = len(crows)

            # -- compteurs --
            mrows = [
                (m["compteur_id"], m["numero_serie"], m["client_id"], m["transformateur_id"],
                 m["modele"], m["mode_facturation"], m["puissance_kva"], m["date_pose"],
                 m["index_initial_kwh"], m["statut"])
                for m in compteurs
            ]
            cur.executemany(
                "INSERT INTO compteurs (compteur_id, numero_serie, client_id, transformateur_id, "
                "modele, mode_facturation, puissance_kva, date_pose, index_initial_kwh, statut) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (compteur_id) DO NOTHING",
                mrows,
            )
            counts["compteurs"] = len(mrows)
        conn.commit()
    return counts
