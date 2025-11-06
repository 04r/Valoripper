import json
from pathlib import Path
import requests

from . import constants

_session = requests.Session()

def _cache_path(name: str) -> Path:
    return constants.APP_DATA_DIR / f"{name}.json"

def fetch_and_cache(name: str, endpoint: str) -> dict:
    """
    Equivalent to their "CheckAndUpdateJsonAsync" -> download into local folder.
    """
    url = f"https://valorant-api.com/v1/{endpoint}"  # Updated API endpoint for skins
    resp = _session.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    path = _cache_path(name)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data

def load_cached(name: str) -> dict | None:
    path = _cache_path(name)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None

def ensure_static_data():
    """
    Minimal set: agents, weapons, playercards, sprays
    """
    try:
        fetch_and_cache("weapons", "weapons/skins")  # Direct call to fetch skins data
    except Exception:
        # fine, we'll work with what we have
        pass
