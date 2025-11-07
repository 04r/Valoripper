import requests, base64, json, os

lockfile = os.path.expandvars(r"C:\Users\%USERNAME%\AppData\Local\Riot Games\Riot Client\Config\Lockfile")
with open(lockfile) as f:
    name, port, pid, password, proto = f.read().strip().split(":")

auth = base64.b64encode(f"riot:{password}".encode()).decode()
headers = {"Authorization": f"Basic {auth}"}
url = f"https://127.0.0.1:{port}/product-session/v1/external-sessions"

print(f"[DEBUG] Calling {url}")
r = requests.get(url, headers=headers, verify=False)
print(f"status={r.status_code}")
print(json.dumps(r.json(), indent=2))
