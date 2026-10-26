"""Point d'entrée du chargeur : `python -m loader` ou commande `load-all`.

Charge le data lake dans les 6 bases, dans un ordre logique, et affiche un
récapitulatif. Chaque base peut être chargée seule (--only) pour le débogage.

Exemples :
    python -m loader                         # tout charger (data/raw par défaut)
    python -m loader --data-root data/raw    # chemin explicite
    python -m loader --only postgres mysql   # seulement ces bases
"""

import argparse
import sys
import time

from loader.config import Settings
from loader.datalake import DataLake
from loader import (
    postgres_loader, mysql_loader, cassandra_loader,
    mongo_loader, neo4j_loader, redis_loader,
)

# Ordre d'exécution. Les bases sont indépendantes entre elles (pas de FK
# inter-bases), mais on met le référentiel relationnel d'abord, puis le reste.
LOADERS = {
    "postgres": postgres_loader.load,
    "mysql": mysql_loader.load,
    "neo4j": neo4j_loader.load,
    "mongo": mongo_loader.load,
    "cassandra": cassandra_loader.load,   # le plus long : vers la fin
    "redis": redis_loader.load,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Charge data/raw dans les bases de la plateforme.")
    parser.add_argument("--data-root", default=None,
                        help="Racine du data lake (défaut : variable DATA_ROOT ou data/raw).")
    parser.add_argument("--only", nargs="+", choices=list(LOADERS),
                        help="Ne charger que ces bases (défaut : toutes).")
    args = parser.parse_args(argv)

    cfg = Settings(data_root=args.data_root) if args.data_root else Settings()
    lake = DataLake(cfg.data_root)
    targets = args.only or list(LOADERS)

    print(f"==> Chargement depuis '{cfg.data_root}' vers : {', '.join(targets)}")
    failures = []
    for name in targets:
        print(f"\n--- {name} ---")
        start = time.monotonic()
        try:
            counts = LOADERS[name](cfg, lake)
            elapsed = time.monotonic() - start
            detail = ", ".join(f"{k}={v}" for k, v in counts.items())
            print(f"    OK ({elapsed:.1f}s) : {detail}")
        except Exception as exc:  # on continue les autres bases, on signale à la fin
            print(f"    ECHEC : {type(exc).__name__}: {exc}", file=sys.stderr)
            failures.append(name)

    print("\n==> Termine.", "Toutes les bases chargees." if not failures
          else f"ECHECS : {', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
