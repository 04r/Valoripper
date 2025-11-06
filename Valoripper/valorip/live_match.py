import os
import json
import requests
from . import constants, models, login, valapi
import tkinter

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

# Global variable to store the skin map (UUID: Name)
SKIN_MAP = {}

def load_skin_map():
    """Load cached Riot skin names from the local content_cache.json."""
    global SKIN_MAP
    skin_data = valapi.load_cached('weapons')  # Load the skin data from the cache

    if skin_data:
        # Map skin UUID to its display name
        SKIN_MAP = {skin["uuid"]: skin["displayName"] for skin in skin_data["data"]}
        print(f"[+] Loaded {len(SKIN_MAP)} cached skin names.")
    else:
        print("[!] Failed to load skin data from cache.")

def get_skin_name(skin_id):
    """Get skin name by UUID from the skin map."""
    if not skin_id:
        return "Unknown"
    sid = skin_id.lower()

    # Return the skin name if found
    name = SKIN_MAP.get(sid)
    if name:
        return name

    # Optional: check if there's a partial match based on UUID prefix
    for k, v in SKIN_MAP.items():
        if sid.startswith(k[:8]):
            return v

    # Return UUID if no match is found
    print(f"Skin not found, returning UUID: {sid[:8]}")
    return sid[:8]

def get_player_loadouts(match_id, puuid):
    """Fetch loadout IDs for a given player index."""
    url = f"https://glz-{constants.SHARD}-1.{get_real_region()}.a.pvp.net/core-game/v1/matches/{match_id}/loadouts"
    headers = {
        "Authorization": f"Bearer {constants.ACCESS_TOKEN}",
        "X-Riot-Entitlements-JWT": constants.ENTITLEMENTS_TOKEN,
        "X-Riot-ClientPlatform": constants.PLATFORM,
        "X-Riot-ClientVersion": constants.VERSION,
    }
    try:
        r = requests.get(url, headers=headers, verify=False)
        if r.status_code != 200:
            return [f"Failed to get loadouts ({r.status_code})"]
        data = r.json()
        for entry in data.get("Loadouts", []):
            if entry.get("Subject") == puuid:
                items = entry.get("Loadout", {}).get("Items", {})
                skins = []
                for weapon, wdata in items.items():
                    sockets = wdata.get("Sockets", {})
                    socket = sockets.get("3ad1b2b2-acdb-4524-852f-954a76ddae0a")
                    if socket:
                        sid = socket.get("Item", {}).get("ID")
                        if sid:
                            skins.append(get_skin_name(sid))
                return skins or ["No skins equipped"]
        return ["Player not found in loadouts"]
    except Exception as e:
        return [f"Error: {e}"]

def get_real_region():
    """Fetch the correct region."""
    reg = getattr(constants, "REGION", None)
    if not reg or reg == "none":
        reg = getattr(constants, "SHARD", None)
    if not reg or reg == "none":
        reg = "eu"
    return reg.lower()

# --- GUI setup ---
root = tkinter.Tk()
root.title("Valoripper")
root.geometry("720x540")
root.configure(bg="#121212")

style = tkinter.ttk.Style()
style.configure("TLabel", background="#121212", foreground="white", font=("Segoe UI", 10))
style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), background="#121212", foreground="white")

tkinter.ttk.Label(root, text="Valoripper", style="Header.TLabel").pack(anchor="w", padx=10, pady=(10, 5))
match_label = tkinter.ttk.Label(root, text="Match: ..."); match_label.pack(anchor="w", padx=10)
map_label = tkinter.ttk.Label(root, text="Map: ..."); map_label.pack(anchor="w", padx=10)
server_label = tkinter.ttk.Label(root, text="Server: ..."); server_label.pack(anchor="w", padx=10, pady=(0, 10))

main_frame = tkinter.ttk.Frame(root, padding=10)
main_frame.pack(fill="both", expand=True)

left_frame = tkinter.ttk.Frame(main_frame)
left_frame.pack(side="left", fill="both", expand=True)
tkinter.ttk.Label(left_frame, text="Players").pack(anchor="w")
players_list = tkinter.Listbox(left_frame, bg="#1e1e1e", fg="white", selectbackground="#333333", relief="flat")
players_list.pack(fill="both", expand=True, padx=(0, 5))

right_frame = tkinter.ttk.Frame(main_frame)
right_frame.pack(side="left", fill="both", expand=True)
tkinter.ttk.Label(right_frame, text="Loadout").pack(anchor="w")
skins_list = tkinter.Listbox(right_frame, bg="#1e1e1e", fg="white", selectbackground="#333333", relief="flat")
skins_list.pack(fill="both", expand=True, padx=(5, 0))

current_match_id = None
current_players = []

def refresh_data():
    global current_match_id, current_players
    try:
        login.ensure_logged_in()
        details, blue, red = live_match.get_live_match()
        match_label.config(text=f"Match: {details.game_mode}")
        map_label.config(text=f"Map: {details.map_name}")
        server_label.config(text=f"Server: {details.server}")

        _, match_id = live_match.detect_match()
        current_match_id = match_id
        current_players = blue + red

        players_list.delete(0, tkinter.END)
        for p in current_players:
            players_list.insert(tkinter.END, p.ign.username)
    except Exception as e:
        match_label.config(text=f"Error: {e}")
    root.after(10000, refresh_data)

def on_player_select(event):
    global current_match_id, current_players
    selection = players_list.curselection()
    if not selection or not current_match_id:
        return
    index = selection[0]
    player = current_players[index]
    puuid = player.puuid
    skins_list.delete(0, tkinter.END)
    skins_list.insert(tkinter.END, f"Fetching {player.ign.username}'s loadout...")
    def worker():
        loadout = get_player_loadout(current_match_id, puuid)
        skins_list.delete(0, tkinter.END)
        for item in loadout:
            skins_list.insert(tkinter.END, f"• {item}")
    threading.Thread(target=worker, daemon=True).start()

players_list.bind("<<ListboxSelect>>", on_player_select)
threading.Thread(target=load_skin_map, daemon=True).start()
threading.Thread(target=refresh_data, daemon=True).start()
root.mainloop()
