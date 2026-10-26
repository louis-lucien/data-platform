"""Sources de données externes : scraping web et API."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def http_session(user_agent: str) -> requests.Session:
    """Session HTTP avec nouvelles tentatives (backoff exponentiel) sur erreurs réseau et 429/5xx."""
    retry = Retry(total=3, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = user_agent
    return session
