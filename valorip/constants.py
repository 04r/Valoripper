from pathlib import Path

APP_NAME = "Valoripper"
APP_DATA_DIR = Path.home() / ".valoripper"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

# will be filled by login
ACCESS_TOKEN: str | None = None
ENTITLEMENTS_TOKEN: str | None = None
PUUID: str | None = None
REGION: str | None = None
SHARD: str | None = None

# these are copied from NOWT style
PLATFORM = (
    'ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQzLjEiLA0KCSJjbGllbnRWZXJzaW9uIjogIjEuMC4wLjAiDQp9'
)
VERSION = "release-10.09-shipping-15-1129237"
