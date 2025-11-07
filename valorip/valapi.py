import json
from pathlib import Path
import requests

from . import constants

_session = requests.Session()

def _cache_path(name: str) -> Path:
    return constants.APP_DATA_DIR / f"{name}.json"

def fetch_and_cache(name: str, endpoint: str) -> dict:
    """
    Fetch data from Valorant API and cache it locally.
    """
    url = f"https://valorant-api.com/v1/{endpoint}"
    print(f"[*] Fetching from {url}")
    resp = _session.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    path = _cache_path(name)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[+] Cached {name} data to {path}")
    return data

def load_cached(name: str) -> dict | None:
    path = _cache_path(name)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[!] Error reading cache {name}: {e}")
            return None
    return None

def ensure_static_data():
    """
    Ensure weapon skins, player cards, and sprays data are available.
    """
    try:
        # Check and fetch weapon skins
        if not load_cached('weapon_skins'):
            print("[*] No cached skin data found, fetching...")
            fetch_and_cache('weapon_skins', 'weapons/skins')
        
        # Check and fetch player cards
        if not load_cached('playercards'):
            print("[*] No cached player card data found, fetching...")
            fetch_and_cache('playercards', 'playercards')
        
        # Check and fetch sprays
        if not load_cached('sprays'):
            print("[*] No cached spray data found, fetching...")
            fetch_and_cache('sprays', 'sprays')
            
    except Exception as e:
        print(f"[!] Failed to ensure static data: {e}")