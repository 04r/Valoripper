import os, base64, requests, json
from . import constants

requests.packages.urllib3.disable_warnings()


def ensure_logged_in():
    """Read Riot Client lockfile, get tokens, and detect region/shard (like NOWT)."""
    if constants.ACCESS_TOKEN and constants.PUUID:
        return

    lockfile_path = os.path.expandvars(
        r"%LOCALAPPDATA%\Riot Games\Riot Client\Config\lockfile"
    )
    with open(lockfile_path, "r", encoding="utf-8") as f:
        name, pid, port, password, proto = f.read().strip().split(":")

    auth = base64.b64encode(f"riot:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}

    # 1) get entitlements + access token
    ent = requests.get(
        f"https://127.0.0.1:{port}/entitlements/v1/token",
        headers=headers,
        verify=False,
    ).json()

    constants.ACCESS_TOKEN = ent["accessToken"]
    constants.ENTITLEMENTS_TOKEN = ent["token"]
    constants.PUUID = ent["subject"]

    # 2) detect region from product-session (this is what NOWT does)
    try:
        sess = requests.get(
            f"https://127.0.0.1:{port}/product-session/v1/external-sessions",
            headers=headers,
            verify=False,
        ).json()

        valorant = sess.get("valorant") or {}
        args = valorant.get("launchConfiguration", {}).get("arguments", [])
        region, shard = "eu", "eu"
        for arg in args:
            if arg.startswith("--region="):
                region = arg.split("=", 1)[1]
            if arg.startswith("--shard="):
                shard = arg.split("=", 1)[1]
        constants.REGION = region
        constants.SHARD = shard
    except Exception:
        # fallback
        constants.REGION = constants.REGION or "eu"
        constants.SHARD = constants.SHARD or "eu"

    print(
        f"[+] Logged in! Region={constants.REGION} Shard={constants.SHARD} PUUID={constants.PUUID[:8]}..."
    )
