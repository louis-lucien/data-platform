"""Scraping du tableau des régions du Sénégal sur Wikipédia (superficie, population).

Bonnes pratiques appliquées :
- User-Agent explicite (exigé par la politique de Wikimédia) ;
- cache local : la page n'est téléchargée qu'une fois par période (cache_ttl_heures) ;
- jointure sur le code ISO 3166-2 (stable) plutôt que sur le nom (accents, orthographe) ;
- repli sur les données de référence si la page est inaccessible ou a changé de structure.
"""

import logging
import re
import time
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from generator.reference import REGIONS
from generator.sources import http_session

log = logging.getLogger(__name__)

ISO_CODE = re.compile(r"^SN-[A-Z]{2}$")


def _to_int(text: str) -> int | None:
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


def parse_regions_table(html: str) -> pd.DataFrame:
    """Extrait code ISO, superficie et population la plus récente de chaque région."""
    soup = BeautifulSoup(html, "html.parser")
    for sup in soup.select("sup.reference"):  # supprime les renvois de notes [1], [2]...
        sup.decompose()

    rows = []
    for table in soup.select("table.wikitable"):
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            iso = next((i for i, c in enumerate(cells) if ISO_CODE.match(c)), None)
            if iso is None or len(cells) < iso + 3:
                continue
            numbers = [_to_int(c) for c in cells[iso + 1:]]
            rows.append({
                "code": cells[iso],
                "superficie_km2": numbers[0],
                "population": numbers[-1],  # dernière colonne = recensement le plus récent
            })
        if rows:
            break
    return pd.DataFrame(rows)


def _fetch_html(cfg: dict, cache_file: Path) -> str:
    ttl_seconds = cfg["cache_ttl_heures"] * 3600
    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < ttl_seconds:
        log.info("Page Wikipédia lue depuis le cache", extra={"fields": {"cache": str(cache_file)}})
        return cache_file.read_text(encoding="utf-8")

    response = http_session(cfg["user_agent"]).get(cfg["wikipedia_url"], timeout=cfg["timeout_secondes"])
    response.raise_for_status()
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(response.text, encoding="utf-8")
    log.info("Page Wikipédia téléchargée", extra={"fields": {"octets": len(response.text)}})
    return response.text


def get_regions(cfg: dict, cache_dir: Path, offline: bool = False) -> pd.DataFrame:
    """Référentiel des régions enrichi par Wikipédia. Colonne `source` = provenance de la population."""
    reference = pd.DataFrame(REGIONS)
    if offline:
        return reference.assign(superficie_km2=pd.NA, source="reference")

    try:
        scraped = parse_regions_table(_fetch_html(cfg, cache_dir / "wikipedia_regions.html"))
        missing = set(reference["code"]) - set(scraped.get("code", []))
        if missing:
            raise ValueError(f"régions absentes du tableau scrapé : {sorted(missing)}")
    except Exception:
        log.warning("Scraping Wikipédia impossible, repli sur les données de référence", exc_info=True)
        return reference.assign(superficie_km2=pd.NA, source="reference")

    merged = reference.drop(columns="population").merge(scraped, on="code", how="left")
    return merged.assign(source="wikipedia")
