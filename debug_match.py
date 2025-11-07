from valorip import login, constants, live_match
import requests, json

# make sure you're in a match before running
login.ensure_logged_in()

base = f"https://glz-{constants.SHARD}-1.{constants.REGION}.a.pvp.net"

# get the current match id from the player endpoint
r = requests.get(f"{base}/core-game/v1/players/{constants.PUUID}", headers=live_match._headers(), verify=False)
data = r.json()
match_id = data.get("MatchID")
print(f"[DEBUG] MatchID = {match_id}")

# fetch the full match info
r2 = requests.get(f"{base}/core-game/v1/matches/{match_id}", headers=live_match._headers(), verify=False)
print(f"[DEBUG] status: {r2.status_code}")
try:
    match_json = r2.json()
    open("match_debug.json", "w").write(json.dumps(match_json, indent=2))
    print("[SAVED] match_debug.json written")
except Exception as e:
    print("Failed to parse JSON:", e)
