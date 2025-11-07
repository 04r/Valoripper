import requests
from . import constants, models, valapi

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

# Global variable to store the skin map (UUID: Name)
SKIN_MAP = {}

def load_skin_map():
    """Load cached Riot skin names from the Valorant API."""
    global SKIN_MAP
    
    # Try to load from cache first
    skin_data = valapi.load_cached('weapon_skins')
    
    # If not cached or empty, fetch from API
    if not skin_data:
        print("[*] Fetching skin data from Valorant API...")
        try:
            skin_data = valapi.fetch_and_cache('weapon_skins', 'weapons/skins')
        except Exception as e:
            print(f"[!] Failed to fetch skin data: {e}")
            return

    if skin_data and skin_data.get("status") == 200:
        # Map skin UUID to its display name
        skins = skin_data.get("data", [])
        for skin in skins:
            uuid = skin.get("uuid", "").lower()
            name = skin.get("displayName", "")
            if uuid and name:
                SKIN_MAP[uuid] = name
                # Also add levels (chromas) if they exist
                for level in skin.get("levels", []):
                    level_uuid = level.get("uuid", "").lower()
                    if level_uuid:
                        SKIN_MAP[level_uuid] = name
                # Add chromas
                for chroma in skin.get("chromas", []):
                    chroma_uuid = chroma.get("uuid", "").lower()
                    if chroma_uuid:
                        chroma_name = chroma.get("displayName", name)
                        SKIN_MAP[chroma_uuid] = chroma_name
        print(f"[+] Loaded {len(SKIN_MAP)} skin variants (including levels and chromas).")
    else:
        print("[!] Failed to load skin data from cache.")

def get_skin_name(skin_id):
    """Get skin name by UUID from the skin map."""
    if not skin_id:
        return "Unknown"
    
    sid = skin_id.lower()

    # Direct match
    name = SKIN_MAP.get(sid)
    if name:
        return name

    # Try partial match (first 8 chars of UUID)
    for k, v in SKIN_MAP.items():
        if k.startswith(sid[:8]) or sid.startswith(k[:8]):
            return v

    # If still not found, try to fetch it live
    if not SKIN_MAP:
        print("[!] Skin map is empty, attempting to load...")
        load_skin_map()
        return get_skin_name(skin_id)  # Retry after loading

    # Return shortened UUID if no match is found
    print(f"[!] Skin not found: {sid}")
    return f"Unknown ({sid[:8]})"

def get_real_region():
    """Fetch the correct region."""
    reg = getattr(constants, "REGION", None)
    if not reg or reg == "none":
        reg = getattr(constants, "SHARD", None)
    if not reg or reg == "none":
        reg = "eu"
    return reg.lower()

def _headers():
    """Build standard headers for Riot API requests."""
    return {
        "Authorization": f"Bearer {constants.ACCESS_TOKEN}",
        "X-Riot-Entitlements-JWT": constants.ENTITLEMENTS_TOKEN,
        "X-Riot-ClientPlatform": constants.PLATFORM,
        "X-Riot-ClientVersion": constants.VERSION,
    }

def detect_match():
    """Detect if player is in a match or range and return match ID."""
    # First try core-game (live match)
    url = f"https://glz-{constants.SHARD}-1.{get_real_region()}.a.pvp.net/core-game/v1/players/{constants.PUUID}"
    r = requests.get(url, headers=_headers(), verify=False)
    if r.status_code == 200:
        data = r.json()
        match_id = data.get("MatchID")
        if match_id:
            return True, match_id
    
    # If not in a live match, try pregame (agent select, etc)
    pregame_url = f"https://glz-{constants.SHARD}-1.{get_real_region()}.a.pvp.net/pregame/v1/players/{constants.PUUID}"
    r = requests.get(pregame_url, headers=_headers(), verify=False)
    if r.status_code == 200:
        data = r.json()
        match_id = data.get("MatchID")
        if match_id:
            return True, match_id
    
    raise Exception("Not in a match or range")

def get_live_match():
    """Get live match details and players."""
    in_match, match_id = detect_match()
    if not in_match:
        raise Exception("Not in a match")
    
    url = f"https://glz-{constants.SHARD}-1.{get_real_region()}.a.pvp.net/core-game/v1/matches/{match_id}"
    r = requests.get(url, headers=_headers(), verify=False)
    
    # If core-game fails, try pregame
    if r.status_code != 200:
        pregame_url = f"https://glz-{constants.SHARD}-1.{get_real_region()}.a.pvp.net/pregame/v1/matches/{match_id}"
        r = requests.get(pregame_url, headers=_headers(), verify=False)
        if r.status_code != 200:
            raise Exception(f"Failed to get match details (status {r.status_code})")
    
    data = r.json()
    
    # Parse match details
    game_mode = data.get("ModeID", data.get("Mode", "Unknown"))
    if "/" in game_mode:
        game_mode = game_mode.split("/")[-1].replace("GameMode_C", "").replace("GameMode", "")
    
    map_id = data.get("MapID", data.get("MapUrl", "Unknown"))
    if "/" in map_id:
        map_id = map_id.split("/")[-1]
    
    server = data.get("GamePodID", data.get("ProvisioningFlowID", "Unknown"))
    
    details = models.MatchDetails(
        game_mode=game_mode,
        map_name=map_id,
        server=server
    )
    
    # Collect all PUUIDs first for batch name lookup
    all_puuids = [p.get("Subject") for p in data.get("Players", data.get("AllyTeam", {}).get("Players", []))]
    
    # Also check for enemy team in pregame
    if "EnemyTeam" in data:
        all_puuids.extend([p.get("Subject") for p in data.get("EnemyTeam", {}).get("Players", [])])
    
    # Batch fetch all player names
    name_map = {}
    try:
        url = f"https://pd.{get_real_region()}.a.pvp.net/name-service/v2/players"
        r = requests.put(url, headers=_headers(), json=all_puuids, verify=False)
        if r.status_code == 200:
            name_data = r.json()
            for player_info in name_data:
                puuid = player_info.get("Subject")
                game_name = player_info.get("GameName", "")
                tag_line = player_info.get("TagLine", "")
                if game_name and tag_line:
                    name_map[puuid] = f"{game_name}#{tag_line}"
                elif game_name:
                    name_map[puuid] = game_name
    except Exception as e:
        print(f"Error batch fetching names: {e}")
    
    # Parse players
    blue_players = []
    red_players = []
    
    players_data = data.get("Players", [])
    
    # Handle pregame structure
    if not players_data:
        ally_players = data.get("AllyTeam", {}).get("Players", [])
        enemy_players = data.get("EnemyTeam", {}).get("Players", [])
        players_data = ally_players + enemy_players
    
    for player_data in players_data:
        puuid = player_data.get("Subject")
        team_id = player_data.get("TeamID", "Blue")
        
        # Get player name from the batch lookup or use fallback
        username = name_map.get(puuid, f"Player_{puuid[:8]}")
        
        player = models.Player(
            puuid=puuid,
            team_id=team_id,
            ign=models.IgnData(username=username),
            identity=models.IdentityData(name=username)
        )
        
        if team_id.lower() == "blue" or team_id.lower() == "ally":
            blue_players.append(player)
        else:
            red_players.append(player)
    
    # If no players found in teams, just add yourself for Range mode
    if not blue_players and not red_players:
        username = name_map.get(constants.PUUID, f"You")
        player = models.Player(
            puuid=constants.PUUID,
            team_id="Blue",
            ign=models.IgnData(username=username),
            identity=models.IdentityData(name=username)
        )
        blue_players.append(player)
    
    return details, blue_players, red_players

def get_player_loadout(match_id, puuid):
    """Fetch loadout IDs for a given player."""
    url = f"https://glz-{constants.SHARD}-1.{get_real_region()}.a.pvp.net/core-game/v1/matches/{match_id}/loadouts"
    try:
        r = requests.get(url, headers=_headers(), verify=False)
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
                            skin_name = get_skin_name(sid)
                            skins.append(skin_name)
                return skins or ["No skins equipped"]
        return ["Player not found in loadouts"]
    except Exception as e:
        return [f"Error: {e}"]

def get_skin_image_url(skin_id):
    """Get skin image URL from the cached skin data."""
    skin_data = valapi.load_cached('weapon_skins')
    if not skin_data:
        return None
    
    sid = skin_id.lower()
    
    for skin in skin_data.get("data", []):
        if skin.get("uuid", "").lower() == sid:
            return skin.get("displayIcon") or skin.get("chromas", [{}])[0].get("fullRender")
        
        for level in skin.get("levels", []):
            if level.get("uuid", "").lower() == sid:
                return level.get("displayIcon") or skin.get("chromas", [{}])[0].get("fullRender")
        
        for chroma in skin.get("chromas", []):
            if chroma.get("uuid", "").lower() == sid:
                return chroma.get("fullRender") or chroma.get("displayIcon")
    
    return None

def get_player_loadout_organized(match_id, puuid):
    """Fetch loadout organized by category."""
    result = {'player_card': None, 'weapons': [], 'melee': None, 'sprays': []}
    
    try:
        match_url = f"https://glz-{constants.SHARD}-1.{get_real_region()}.a.pvp.net/core-game/v1/matches/{match_id}"
        match_r = requests.get(match_url, headers=_headers(), verify=False, timeout=10)
        
        if match_r.status_code != 200:
            match_url = f"https://glz-{constants.SHARD}-1.{get_real_region()}.a.pvp.net/pregame/v1/matches/{match_id}"
            match_r = requests.get(match_url, headers=_headers(), verify=False, timeout=10)
        
        if match_r.status_code == 200:
            match_data = match_r.json()
            players = match_data.get("Players", [])
            
            if not players:
                ally_players = match_data.get("AllyTeam", {}).get("Players", [])
                enemy_players = match_data.get("EnemyTeam", {}).get("Players", [])
                players = ally_players + enemy_players
            
            for player in players:
                if player.get("Subject") == puuid:
                    card_id = player.get("PlayerIdentity", {}).get("PlayerCardID")
                    if card_id:
                        result['player_card'] = get_player_card_image(card_id)
                    break
        
        url = f"https://glz-{constants.SHARD}-1.{get_real_region()}.a.pvp.net/core-game/v1/matches/{match_id}/loadouts"
        r = requests.get(url, headers=_headers(), verify=False, timeout=10)
        
        if r.status_code != 200:
            pers_url = f"https://pd.{get_real_region()}.a.pvp.net/personalization/v2/players/{constants.PUUID}/playerloadout"
            r = requests.get(pers_url, headers=_headers(), verify=False, timeout=10)
            
            if r.status_code == 200:
                data = r.json()
                guns = data.get("Guns", [])
                for gun in guns:
                    display_id = gun.get("ChromaID") or gun.get("SkinID")
                    
                    if display_id:
                        skin_name = get_skin_name(display_id)
                        image_url = get_skin_image_url(display_id)
                        gun_id = gun.get("ID", "")
                        
                        if is_melee_weapon(gun_id):
                            result['melee'] = {'name': skin_name, 'image_url': image_url}
                        else:
                            result['weapons'].append({'name': skin_name, 'image_url': image_url})
                
                sprays = data.get("Sprays", [])
                for spray in sprays:
                    spray_id = spray.get("EquippedSprayID")
                    if spray_id:
                        spray_info = get_spray_info(spray_id)
                        if spray_info:
                            result['sprays'].append(spray_info)
                
                if not result['player_card']:
                    identity = data.get("Identity", {})
                    card_id = identity.get("PlayerCardID")
                    if card_id:
                        result['player_card'] = get_player_card_image(card_id)
                
                return result
        
        if r.status_code == 200:
            data = r.json()
            for entry in data.get("Loadouts", []):
                if entry.get("Subject") == puuid:
                    items = entry.get("Loadout", {}).get("Items", {})
                    
                    for weapon_id, wdata in items.items():
                        sockets = wdata.get("Sockets", {})
                        skin_socket = sockets.get("3ad1b2b2-acdb-4524-852f-954a76ddae0a")
                        
                        if skin_socket:
                            sid = skin_socket.get("Item", {}).get("ID")
                            if sid:
                                skin_name = get_skin_name(sid)
                                image_url = get_skin_image_url(sid)
                                
                                if is_melee_weapon(weapon_id):
                                    result['melee'] = {'name': skin_name, 'image_url': image_url}
                                else:
                                    result['weapons'].append({'name': skin_name, 'image_url': image_url})
                    
                    sprays_data = entry.get("Loadout", {}).get("Sprays", [])
                    for spray in sprays_data:
                        spray_id = spray.get("EquippedSprayID")
                        if spray_id:
                            spray_info = get_spray_info(spray_id)
                            if spray_info:
                                result['sprays'].append(spray_info)
                    
                    break
        
        return result
        
    except Exception as e:
        print(f"Error getting organized loadout: {e}")
        return result

def is_melee_weapon(weapon_id):
    """Check if weapon ID is a melee weapon"""
    melee_uuid = "2f59173c-4bed-b6c3-2191-dea9b58be9c7"
    weapon_lower = weapon_id.lower()
    
    if melee_uuid in weapon_lower:
        return True
    
    melee_keywords = ['melee', 'knife', 'blade', 'axe', 'sword', 'dagger', 'katana']
    return any(keyword in weapon_lower for keyword in melee_keywords)

def get_player_card_image(card_id):
    """Get player card large image URL"""
    try:
        card_data = valapi.load_cached('playercards')
        if not card_data:
            card_data = valapi.fetch_and_cache('playercards', 'playercards')
        
        if card_data and card_data.get("status") == 200:
            for card in card_data.get("data", []):
                if card.get("uuid", "").lower() == card_id.lower():
                    return card.get("largeArt") or card.get("wideArt")
        
        return None
    except Exception as e:
        print(f"Error getting player card: {e}")
        return None

def get_spray_info(spray_id):
    """Get spray name and image URL"""
    try:
        spray_data = valapi.load_cached('sprays')
        if not spray_data:
            spray_data = valapi.fetch_and_cache('sprays', 'sprays')
        
        if spray_data and spray_data.get("status") == 200:
            for spray in spray_data.get("data", []):
                if spray.get("uuid", "").lower() == spray_id.lower():
                    return {
                        'name': spray.get("displayName", "Unknown Spray"),
                        'image_url': spray.get("fullTransparentIcon") or spray.get("displayIcon")
                    }
        
        return None
    except Exception as e:
        print(f"Error getting spray info: {e}")
        return None

def get_player_stats(username, tag):
    """Fetch player stats using Henrik's Valorant API with authentication"""
    try:
        if '#' in username:
            parts = username.split('#', 1)
            username = parts[0]
            tag = parts[1] if len(parts) > 1 else tag
        
        # URL encode the name and tag properly
        import urllib.parse
        username_encoded = urllib.parse.quote(username)
        tag_encoded = urllib.parse.quote(tag)
        
        print(f"[DEBUG] Fetching stats for {username}#{tag}")
        
        # API Key header
        headers = {
            'Authorization': 'HDEV-f74a6b23-0fa4-462a-812a-7fc63acc7ee1'
        }
        
        stats = {
            'rank': None,
            'peak_rank': None,
            'win_rate': None,
            'hs_rate': None,
            'kd': None
        }
        
        # Get MMR/Rank data - Using v3 endpoint (this shows current rank properly)
        mmr_url = f"https://api.henrikdev.xyz/valorant/v3/mmr/eu/pc/{username_encoded}/{tag_encoded}"
        print(f"[DEBUG] MMR URL: {mmr_url}")
        
        try:
            mmr_response = requests.get(mmr_url, headers=headers, timeout=10)
            print(f"[DEBUG] MMR status: {mmr_response.status_code}")
            
            if mmr_response.status_code == 200:
                mmr_data = mmr_response.json()
                
                if mmr_data.get('status') == 200:
                    data = mmr_data.get('data', {})
                    
                    # Get rank from 'current' not 'current_data'
                    current = data.get('current', {})
                    tier_info = current.get('tier', {})
                    
                    rank_name = tier_info.get('name', 'Unranked')
                    rr = current.get('rr', 0)
                    
                    print(f"[DEBUG] Rank fields - tier: {tier_info}, rank_name: {rank_name}, rr: {rr}")
                    
                    if rank_name and rank_name != 'Unranked':
                        stats['rank'] = f"{rank_name} ({rr} RR)"
                    else:
                        stats['rank'] = 'Unranked'
                    
                    # Get peak rank
                    peak = data.get('peak', {})
                    peak_tier = peak.get('tier', {})
                    stats['peak_rank'] = peak_tier.get('name', 'Unknown')
                    
                    # Get current act stats from seasonal data
                    seasonal = data.get('seasonal', [])
                    current_act_short = None
                    if seasonal and len(seasonal) > 0:
                        current_act_data = seasonal[-1]  # Last entry is current act
                        current_act_short = current_act_data.get('season', {}).get('short')
                        act_wins = current_act_data.get('wins', 0)
                        act_games = current_act_data.get('games', 0)
                        
                        if act_games > 0:
                            stats['win_rate'] = round((act_wins / act_games) * 100, 1)
                        
                        print(f"[DEBUG] Act stats from MMR - Wins: {act_wins}/{act_games}, WR: {stats['win_rate']}%")
                    
                    print(f"[DEBUG] Final rank: {stats['rank']}, Peak: {stats['peak_rank']}")
        except Exception as e:
            print(f"[DEBUG] MMR fetch failed: {e}")
            import traceback
            traceback.print_exc()
        
        # First, get the player's PUUID using the account endpoint
        account_url = f"https://api.henrikdev.xyz/valorant/v1/account/{username_encoded}/{tag_encoded}"
        print(f"[DEBUG] Account URL: {account_url}")
        
        player_puuid = None
        try:
            account_response = requests.get(account_url, headers=headers, timeout=10)
            print(f"[DEBUG] Account status: {account_response.status_code}")
            
            if account_response.status_code == 200:
                account_data = account_response.json()
                if account_data.get('status') == 200:
                    player_puuid = account_data.get('data', {}).get('puuid')
                    print(f"[DEBUG] Found PUUID: {player_puuid[:8] if player_puuid else None}...")
        except Exception as e:
            print(f"[DEBUG] Account fetch failed: {e}")
        
        # If we couldn't get PUUID, skip match history
        if not player_puuid:
            print("[DEBUG] Could not fetch PUUID, skipping match history")
            # Return stats if we got at least something from MMR
            if any(v is not None for v in stats.values()):
                return stats
            return None
        
        # Get match history stats using v3 by-puuid endpoint with the actual PUUID
        # Request more matches for better stats coverage (up to 100)
        matches_url = f"https://api.henrikdev.xyz/valorant/v3/by-puuid/matches/eu/{player_puuid}?mode=competitive&size=100"
        print(f"[DEBUG] Matches URL: {matches_url}")
        
        try:
            matches_response = requests.get(matches_url, headers=headers, timeout=30)
            print(f"[DEBUG] Matches status: {matches_response.status_code}")
            
            if matches_response.status_code == 200:
                matches_data = matches_response.json()
                if matches_data.get('status') == 200:
                    matches_list = matches_data.get('data', [])
                    print(f"[DEBUG] Found {len(matches_list)} recent matches")
                    
                    # Debug: Check structure of first match
                    if matches_list and len(matches_list) > 0:
                        first_match = matches_list[0]
                        print(f"[DEBUG] First match keys: {list(first_match.keys())}")
                        
                        # Check players structure - it's likely a dict with team names as keys
                        if 'players' in first_match:
                            players_data = first_match['players']
                            print(f"[DEBUG] Players type: {type(players_data)}")
                            if isinstance(players_data, dict):
                                print(f"[DEBUG] Players dict keys: {list(players_data.keys())}")
                                # Get first team's players
                                first_team = list(players_data.keys())[0]
                                first_team_players = players_data[first_team]
                                if isinstance(first_team_players, list) and len(first_team_players) > 0:
                                    first_player = first_team_players[0]
                                    print(f"[DEBUG] First player keys: {list(first_player.keys())}")
                    
                    # Calculate stats from all recent matches
                    total_kills = 0
                    total_deaths = 0
                    total_hs = 0
                    total_body = 0
                    total_leg = 0
                    match_count = 0
                    
                    for match in matches_list:
                        players_data = match.get('players', {})
                        
                        # Players is a dict with team names as keys (e.g., 'red', 'blue', 'all_players')
                        # Skip 'all_players' to avoid double counting
                        if isinstance(players_data, dict):
                            found_in_match = False
                            # Iterate through all teams (skip 'all_players' to avoid duplicates)
                            for team_name, team_players in players_data.items():
                                if team_name == 'all_players' or found_in_match:
                                    continue
                                    
                                if not isinstance(team_players, list):
                                    continue
                                    
                                for player in team_players:
                                    if not isinstance(player, dict):
                                        continue
                                        
                                    player_name = player.get('name', '')
                                    player_tag = player.get('tag', '')
                                    
                                    # Match by name and tag
                                    if player_name.lower() == username.lower() and player_tag.lower() == tag.lower():
                                        stats_data = player.get('stats', {})
                                        kills = stats_data.get('kills', 0)
                                        deaths = stats_data.get('deaths', 0)
                                        hs = stats_data.get('headshots', 0)
                                        body = stats_data.get('bodyshots', 0)
                                        leg = stats_data.get('legshots', 0)
                                        
                                        total_kills += kills
                                        total_deaths += deaths
                                        total_hs += hs
                                        total_body += body
                                        total_leg += leg
                                        match_count += 1
                                        found_in_match = True
                                        break
                    
                    # Calculate stats
                    if total_deaths > 0:
                        stats['kd'] = round(total_kills / total_deaths, 2)
                    
                    total_shots = total_hs + total_body + total_leg
                    if total_shots > 0:
                        stats['hs_rate'] = round((total_hs / total_shots) * 100, 1)
                    
                    print(f"[DEBUG] Totals from {match_count} matches - K:{total_kills} D:{total_deaths} HS:{total_hs}/{total_shots}")
                    print(f"[DEBUG] Final stats - KD: {stats['kd']}, HS: {stats['hs_rate']}%")
        except Exception as e:
            print(f"[DEBUG] Matches fetch failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Return stats if we got at least something
        if any(v is not None for v in stats.values()):
            return stats
        
        return None
        
    except Exception as e:
        print(f"[ERROR] Failed to fetch stats: {e}")
        import traceback
        traceback.print_exc()
        return None