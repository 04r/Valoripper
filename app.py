import tkinter as tk
from tkinter import ttk, font
import threading
import requests
from valorip import login, live_match, constants, valapi
from PIL import Image, ImageTk, ImageDraw, ImageFont
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
import math

requests.packages.urllib3.disable_warnings()

REGION_MAP = {
    "eu": "euw",
    "na": "na",
    "ap": "ap",
    "kr": "kr",
    "latam": "latam",
    "br": "br",
    "pbe": "pbe"
}

def get_real_region():
    reg = getattr(constants, "REGION", None)
    if not reg or reg == "none":
        reg = getattr(constants, "SHARD", None)
    if not reg or reg == "none":
        reg = "eu"
    return reg.lower()

def get_shared_host():
    reg = get_real_region()
    return REGION_MAP.get(reg, reg)

# Cache for images
image_cache = {}

def load_image_from_url(url, max_size=None, circle=False):
    """Download and resize image maintaining aspect ratio"""
    if url in image_cache:
        return image_cache[url]
    
    try:
        response = requests.get(url, timeout=10)
        img = Image.open(BytesIO(response.content))
        
        if circle:
            # Create circular mask
            size = min(img.size)
            mask = Image.new('L', (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)
            
            # Crop to square and apply mask
            img = img.crop(((img.width - size) // 2, (img.height - size) // 2,
                           (img.width + size) // 2, (img.height + size) // 2))
            
            output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            output.paste(img, (0, 0))
            output.putalpha(mask)
            img = output
        
        if max_size:
            img_width, img_height = img.size
            max_width, max_height = max_size
            
            width_ratio = max_width / img_width
            height_ratio = max_height / img_height
            scale_factor = min(width_ratio, height_ratio)
            
            new_width = int(img_width * scale_factor)
            new_height = int(img_height * scale_factor)
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        photo = ImageTk.PhotoImage(img)
        image_cache[url] = photo
        return photo
    except Exception as e:
        print(f"Error loading image: {e}")
        return None

def load_all_images_parallel(items):
    """Load all images in parallel"""
    images = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_item = {}
        for item in items:
            if item.get('image_url'):
                future = executor.submit(
                    load_image_from_url, 
                    item['image_url'], 
                    item.get('max_size'),
                    item.get('circle', False)
                )
                future_to_item[future] = item['id']
        
        for future in as_completed(future_to_item):
            item_id = future_to_item[future]
            try:
                img = future.result()
                if img:
                    images[item_id] = img
            except Exception as e:
                print(f"Error loading {item_id}: {e}")
    
    return images

# --- GUI setup ---
root = tk.Tk()
root.title("Valoripper")
root.geometry("1000x700")
root.configure(bg="#0f1419")
root.resizable(True, True)

# Custom fonts
try:
    title_font = font.Font(family="Segoe UI", size=32, weight="bold")
    header_font = font.Font(family="Segoe UI", size=14, weight="bold")
    body_font = font.Font(family="Segoe UI", size=10)
    small_font = font.Font(family="Segoe UI", size=8)
    tiny_font = font.Font(family="Segoe UI", size=7)
except:
    title_font = font.Font(size=32, weight="bold")
    header_font = font.Font(size=14, weight="bold")
    body_font = font.Font(size=10)
    small_font = font.Font(size=8)
    tiny_font = font.Font(size=7)

# Custom styling
style = ttk.Style()
style.theme_use('clam')

# Configure styles with modern colors
style.configure("TFrame", background="#0f1419")
style.configure("Card.TFrame", background="#1a1f26", relief="flat", borderwidth=0)
style.configure("TLabel", background="#0f1419", foreground="#ffffff", font=body_font)
style.configure("Header.TLabel", font=title_font, background="#0f1419", foreground="#ff4655")
style.configure("Subheader.TLabel", font=header_font, background="#1a1f26", foreground="#ffffff")
style.configure("Info.TLabel", font=body_font, background="#0f1419", foreground="#8b96a5")
style.configure("Status.TLabel", font=small_font, background="#1a1f26", foreground="#5cb85c")

# Header section
header_frame = ttk.Frame(root, style="TFrame", padding=(30, 20))
header_frame.pack(fill="x")

title_label = ttk.Label(header_frame, text="VALORIPPER", style="Header.TLabel")
title_label.pack(side="left")

status_label = ttk.Label(header_frame, text="● LIVE", style="Status.TLabel")
status_label.pack(side="right", padx=10)

# Match info section with gradient-like cards
info_frame = ttk.Frame(root, style="TFrame", padding=(30, 0, 30, 20))
info_frame.pack(fill="x")

# Create three info cards in a row
info_cards_frame = ttk.Frame(info_frame, style="TFrame")
info_cards_frame.pack(fill="x")

# Card 1 - Match Type
card1 = tk.Frame(info_cards_frame, bg="#1a1f26", height=80)
card1.pack(side="left", fill="both", expand=True, padx=(0, 10))

match_icon = ttk.Label(card1, text="⚔", font=("Segoe UI", 20), background="#1a1f26", foreground="#ff4655")
match_icon.pack(pady=(10, 0))

match_label = tk.Label(card1, text="Waiting...", font=body_font, bg="#1a1f26", fg="#ffffff")
match_label.pack(pady=(5, 10))

# Card 2 - Map
card2 = tk.Frame(info_cards_frame, bg="#1a1f26", height=80)
card2.pack(side="left", fill="both", expand=True, padx=5)

map_icon = ttk.Label(card2, text="🗺", font=("Segoe UI", 20), background="#1a1f26", foreground="#ff4655")
map_icon.pack(pady=(10, 0))

map_label = tk.Label(card2, text="...", font=body_font, bg="#1a1f26", fg="#ffffff")
map_label.pack(pady=(5, 10))

# Card 3 - Server
card3 = tk.Frame(info_cards_frame, bg="#1a1f26", height=80)
card3.pack(side="left", fill="both", expand=True, padx=(10, 0))

server_icon = ttk.Label(card3, text="🌐", font=("Segoe UI", 20), background="#1a1f26", foreground="#ff4655")
server_icon.pack(pady=(10, 0))

server_label = tk.Label(card3, text="...", font=body_font, bg="#1a1f26", fg="#ffffff")
server_label.pack(pady=(5, 10))

# Main content area
content_frame = ttk.Frame(root, style="TFrame", padding=(30, 0, 30, 30))
content_frame.pack(fill="both", expand=True)

# Players panel with modern design
players_container = tk.Frame(content_frame, bg="#1a1f26", bd=0)
players_container.pack(fill="both", expand=True)

# Header with better styling
players_header_frame = tk.Frame(players_container, bg="#252c35", height=50)
players_header_frame.pack(fill="x")
players_header_frame.pack_propagate(False)

players_header = tk.Label(
    players_header_frame, 
    text="PLAYERS IN MATCH", 
    font=header_font, 
    bg="#252c35", 
    fg="#ffffff",
    anchor="w"
)
players_header.pack(side="left", padx=20, pady=15)

# Modern scrollable players list using Canvas
players_canvas_frame = tk.Frame(players_container, bg="#1a1f26")
players_canvas_frame.pack(fill="both", expand=True, padx=15, pady=15)

players_canvas = tk.Canvas(players_canvas_frame, bg="#1a1f26", highlightthickness=0, bd=0)
players_scrollbar = tk.Scrollbar(players_canvas_frame, orient="vertical", command=players_canvas.yview, 
                                bg="#1a1f26", troughcolor="#0f1419", activebackground="#ff4655", width=12)
players_scrollbar.pack(side="right", fill="y")

players_canvas.pack(side="left", fill="both", expand=True)
players_canvas.configure(yscrollcommand=players_scrollbar.set)

# Frame inside canvas to hold player cards
players_inner_frame = tk.Frame(players_canvas, bg="#1a1f26")
players_canvas_window = players_canvas.create_window((0, 0), window=players_inner_frame, anchor="nw")

def on_players_configure(event):
    players_canvas.configure(scrollregion=players_canvas.bbox("all"))
    # Update canvas window width to match canvas width
    canvas_width = event.width
    players_canvas.itemconfig(players_canvas_window, width=canvas_width)

players_inner_frame.bind("<Configure>", on_players_configure)
players_canvas.bind("<Configure>", on_players_configure)

current_match_id = None
current_players = []
player_widgets = []

def get_agent_icon_url(character_id):
    """Get agent icon from Valorant API"""
    try:
        agents_data = valapi.load_cached('agents')
        if not agents_data:
            agents_data = valapi.fetch_and_cache('agents', 'agents')
        
        if agents_data and agents_data.get("status") == 200:
            for agent in agents_data.get("data", []):
                if agent.get("uuid", "").lower() == character_id.lower():
                    return agent.get("displayIcon")
    except:
        pass
    return None

def get_rank_icon_url(tier):
    """Get rank icon URL"""
    # Valorant rank tier icons from official API
    if tier == 0:
        return None
    
    # Ranks are numbered 3-27 (Iron 1 to Radiant)
    base_url = "https://media.valorant-api.com/competitivetiers/03621f52-342b-cf4e-4f86-9350a49c6d04"
    return f"{base_url}/{tier}/largeicon.png"

def create_player_card(parent, player, index):
    """Create a modern player card with icons"""
    # Card background with hover effect
    card = tk.Frame(parent, bg="#232a33", cursor="hand2", height=70)
    card.pack(fill="x", pady=5, padx=5)
    card.pack_propagate(False)
    
    # Hover effects
    def on_enter(e):
        card.config(bg="#2a313c")
    
    def on_leave(e):
        card.config(bg="#232a33")
    
    def on_click(e):
        show_loadout_popup(player)
    
    card.bind("<Enter>", on_enter)
    card.bind("<Leave>", on_leave)
    card.bind("<Button-1>", on_click)
    
    # Left section - Agent icon (circular)
    left_frame = tk.Frame(card, bg="#232a33", width=60)
    left_frame.pack(side="left", fill="y", padx=(10, 10))
    left_frame.pack_propagate(False)
    
    agent_label = tk.Label(left_frame, bg="#232a33", image="")
    agent_label.pack(expand=True)
    agent_label.bind("<Button-1>", on_click)
    
    # Middle section - Player info
    middle_frame = tk.Frame(card, bg="#232a33")
    middle_frame.pack(side="left", fill="both", expand=True)
    middle_frame.bind("<Button-1>", on_click)
    
    name_label = tk.Label(middle_frame, text=player.ign.username, 
                         font=body_font, bg="#232a33", fg="#ffffff", anchor="w")
    name_label.pack(anchor="w", pady=(12, 2))
    name_label.bind("<Button-1>", on_click)
    
    team_label = tk.Label(middle_frame, text=f"Team {player.team_id}", 
                         font=small_font, bg="#232a33", 
                         fg="#5cb85c" if player.team_id.lower() == "blue" else "#d9534f", 
                         anchor="w")
    team_label.pack(anchor="w", pady=(0, 12))
    team_label.bind("<Button-1>", on_click)
    
    # Right section - Rank badge
    right_frame = tk.Frame(card, bg="#232a33", width=60)
    right_frame.pack(side="right", fill="y", padx=(10, 15))
    right_frame.pack_propagate(False)
    
    rank_label = tk.Label(right_frame, bg="#232a33", image="")
    rank_label.pack(expand=True)
    rank_label.bind("<Button-1>", on_click)
    
    return card, agent_label, rank_label

def show_loadout_popup(player):
    """Show loadout popup with improved design"""
    popup = tk.Toplevel(root)
    popup.title(f"{player.ign.username}'s Profile")
    popup.geometry("1400x750")
    popup.configure(bg="#0f1419")
    popup.resizable(False, False)
    
    popup.images = {}
    
    loading_frame = tk.Frame(popup, bg="#0f1419")
    loading_frame.pack(fill="both", expand=True)
    
    loading_label = tk.Label(
        loading_frame,
        text="Loading profile...",
        font=header_font,
        bg="#0f1419",
        fg="#ffffff"
    )
    loading_label.pack(expand=True)
    
    def load_and_display():
        loadout_data = live_match.get_player_loadout_organized(current_match_id, player.puuid)
        
        if not loadout_data:
            loadout_data = {'player_card': None, 'weapons': [], 'melee': None, 'sprays': []}
        
        # Fetch player stats
        player_stats = None
        try:
            parts = player.ign.username.split('#')
            player_stats = live_match.get_player_stats(parts[0], parts[1] if len(parts) > 1 else 'NA1')
        except Exception as e:
            print(f"Stats fetch error: {e}")
        
        images_to_load = []
        
        if loadout_data.get('player_card'):
            images_to_load.append({'id': 'player_card', 'image_url': loadout_data['player_card'], 'max_size': (180, 280)})
        
        for i, weapon in enumerate(loadout_data.get('weapons', [])):
            if weapon.get('image_url'):
                images_to_load.append({'id': f'weapon_{i}', 'image_url': weapon['image_url'], 'max_size': (220, 110)})
        
        if loadout_data.get('melee') and loadout_data['melee'].get('image_url'):
            images_to_load.append({'id': 'melee', 'image_url': loadout_data['melee']['image_url'], 'max_size': (480, 150)})
        
        for i, spray in enumerate(loadout_data.get('sprays', [])):
            if spray.get('image_url'):
                images_to_load.append({'id': f'spray_{i}', 'image_url': spray['image_url'], 'max_size': (65, 65)})
        
        popup.images = load_all_images_parallel(images_to_load)
        loading_frame.destroy()
        
        # Main layout with modern design
        main = tk.Frame(popup, bg="#0f1419")
        main.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Top bar with player info
        top_bar = tk.Frame(main, bg="#1a1f26", height=100)
        top_bar.pack(fill="x", pady=(0, 15))
        top_bar.pack_propagate(False)
        
        # Player name and title
        name_frame = tk.Frame(top_bar, bg="#1a1f26")
        name_frame.pack(side="left", padx=20, pady=20)
        
        player_name = tk.Label(name_frame, text=player.ign.username, 
                              font=("Segoe UI", 18, "bold"), bg="#1a1f26", fg="#ffffff")
        player_name.pack(anchor="w")
        
        if player_stats:
            subtitle = tk.Label(name_frame, 
                              text=f"{player_stats.get('rank', 'Unranked')} • {player_stats.get('win_rate', 0)}% WR",
                              font=body_font, bg="#1a1f26", fg="#8b96a5")
            subtitle.pack(anchor="w")
        
        # Left sidebar
        left = tk.Frame(main, bg="#0f1419", width=200)
        left.pack(side="left", fill="y", padx=(0, 15))
        left.pack_propagate(False)
        
        if 'player_card' in popup.images:
            card_container = tk.Frame(left, bg="#1a1f26")
            card_container.pack(pady=(0, 15))
            
            card_lbl = tk.Label(card_container, image=popup.images['player_card'], bg="#1a1f26")
            card_lbl.pack(padx=10, pady=10)
        
        # Stats section
        if player_stats:
            stats_container = tk.Frame(left, bg="#1a1f26")
            stats_container.pack(fill="x", pady=(0, 15))
            
            stats_title = tk.Label(stats_container, text="COMPETITIVE STATS", 
                                  font=("Segoe UI", 9, "bold"), bg="#1a1f26", fg="#8b96a5")
            stats_title.pack(pady=(10, 10))
            
            def create_stat_row(parent, label, value, color="#ffffff"):
                row = tk.Frame(parent, bg="#1a1f26")
                row.pack(fill="x", padx=15, pady=3)
                
                tk.Label(row, text=label, font=small_font, bg="#1a1f26", fg="#8b96a5").pack(side="left")
                tk.Label(row, text=value, font=small_font, bg="#1a1f26", fg=color).pack(side="right")
            
            if player_stats.get('rank'):
                create_stat_row(stats_container, "Rank", player_stats['rank'], "#5cb85c")
            
            if player_stats.get('peak_rank'):
                create_stat_row(stats_container, "Peak", player_stats['peak_rank'], "#f0ad4e")
            
            if player_stats.get('win_rate') is not None:
                create_stat_row(stats_container, "Win Rate", f"{player_stats['win_rate']}%")
            
            if player_stats.get('kd') is not None:
                create_stat_row(stats_container, "K/D", str(player_stats['kd']))
            
            if player_stats.get('hs_rate') is not None:
                create_stat_row(stats_container, "Headshot%", f"{player_stats['hs_rate']}%")
        
        # Sprays section
        if loadout_data.get('sprays'):
            spray_container = tk.Frame(left, bg="#1a1f26")
            spray_container.pack(fill="x")
            
            spray_title = tk.Label(spray_container, text="SPRAYS", 
                                  font=("Segoe UI", 9, "bold"), bg="#1a1f26", fg="#8b96a5")
            spray_title.pack(pady=(10, 10))
            
            spray_grid = tk.Frame(spray_container, bg="#1a1f26")
            spray_grid.pack(pady=(0, 10))
            
            for i, spray in enumerate(loadout_data.get('sprays', [])):
                if f'spray_{i}' in popup.images:
                    spray_box = tk.Frame(spray_grid, bg="#0f1419", width=70, height=70)
                    spray_box.grid(row=i//2, column=i%2, padx=5, pady=5)
                    spray_box.pack_propagate(False)
                    s_lbl = tk.Label(spray_box, image=popup.images[f'spray_{i}'], bg="#0f1419")
                    s_lbl.place(relx=0.5, rely=0.5, anchor="center")
        
        # Right content - Loadout
        right = tk.Frame(main, bg="#0f1419")
        right.pack(side="left", fill="both", expand=True)
        
        # Weapons section
        weap_container = tk.Frame(right, bg="#1a1f26")
        weap_container.pack(fill="both", expand=True, pady=(0, 15))
        
        weap_title = tk.Label(weap_container, text="WEAPON LOADOUT", 
                             font=("Segoe UI", 12, "bold"), bg="#1a1f26", fg="#ffffff")
        weap_title.pack(anchor="w", padx=15, pady=(15, 10))
        
        weap_grid = tk.Frame(weap_container, bg="#1a1f26")
        weap_grid.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        row, col = 0, 0
        for i, weapon in enumerate(loadout_data.get('weapons', [])):
            card = tk.Frame(weap_grid, bg="#0f1419", width=230, height=135)
            card.grid(row=row, column=col, padx=5, pady=5)
            card.pack_propagate(False)
            card.grid_propagate(False)
            
            if f'weapon_{i}' in popup.images:
                img_lbl = tk.Label(card, image=popup.images[f'weapon_{i}'], bg="#0f1419")
                img_lbl.place(relx=0.5, rely=0.4, anchor="center")
            
            name_lbl = tk.Label(card, text=weapon['name'], font=tiny_font, 
                              bg="#0f1419", fg="#8b96a5", wraplength=220)
            name_lbl.place(relx=0.5, rely=0.85, anchor="center")
            
            col += 1
            if col >= 5:
                col = 0
                row += 1
        
        # Melee section
        if loadout_data.get('melee'):
            melee_container = tk.Frame(right, bg="#1a1f26")
            melee_container.pack(fill="x")
            
            melee_title = tk.Label(melee_container, text="MELEE", 
                                  font=("Segoe UI", 12, "bold"), bg="#1a1f26", fg="#ffffff")
            melee_title.pack(anchor="w", padx=15, pady=(15, 10))
            
            melee_card = tk.Frame(melee_container, bg="#0f1419", width=500, height=170)
            melee_card.pack(anchor="w", padx=15, pady=(0, 15))
            melee_card.pack_propagate(False)
            
            if 'melee' in popup.images:
                m_img = tk.Label(melee_card, image=popup.images['melee'], bg="#0f1419")
                m_img.place(relx=0.5, rely=0.4, anchor="center")
            
            m_name = tk.Label(melee_card, text=loadout_data['melee']['name'], 
                            font=tiny_font, bg="#0f1419", fg="#8b96a5")
            m_name.place(relx=0.5, rely=0.85, anchor="center")
    
    threading.Thread(target=load_and_display, daemon=True).start()

def refresh_data():
    global current_match_id, current_players, player_widgets
    try:
        login.ensure_logged_in()
        details, blue, red = live_match.get_live_match()
        match_label.config(text=details.game_mode)
        map_label.config(text=details.map_name)
        server_label.config(text=details.server.split('.')[-1].upper()[:15])

        _, match_id = live_match.detect_match()
        current_match_id = match_id
        current_players = blue + red

        # Clear existing player cards
        for widget in players_inner_frame.winfo_children():
            widget.destroy()
        
        player_widgets = []
        
        # Collect all agent/rank data to load in parallel
        images_to_load = []
        
        for i, p in enumerate(current_players):
            # Get character ID from match data
            try:
                url = f"https://glz-{constants.SHARD}-1.{get_real_region()}.a.pvp.net/core-game/v1/matches/{match_id}"
                headers = {
                    "Authorization": f"Bearer {constants.ACCESS_TOKEN}",
                    "X-Riot-Entitlements-JWT": constants.ENTITLEMENTS_TOKEN,
                }
                r = requests.get(url, headers=headers, verify=False, timeout=5)
                if r.status_code == 200:
                    match_data = r.json()
                    for player_data in match_data.get("Players", []):
                        if player_data.get("Subject") == p.puuid:
                            char_id = player_data.get("CharacterID")
                            if char_id:
                                agent_url = get_agent_icon_url(char_id)
                                if agent_url:
                                    images_to_load.append({
                                        'id': f'agent_{i}', 
                                        'image_url': agent_url, 
                                        'max_size': (50, 50),
                                        'circle': True
                                    })
                            
                            # Get rank tier
                            tier = player_data.get("SeasonalBadgeInfo", {}).get("Rank", 0)
                            if tier > 0:
                                rank_url = get_rank_icon_url(tier)
                                if rank_url:
                                    images_to_load.append({
                                        'id': f'rank_{i}',
                                        'image_url': rank_url,
                                        'max_size': (45, 45)
                                    })
                            break
            except:
                pass
        
        # Load all icons in parallel
        loaded_images = load_all_images_parallel(images_to_load)
        
        # Create player cards with loaded images
        for i, p in enumerate(current_players):
            card, agent_label, rank_label = create_player_card(players_inner_frame, p, i)
            
            # Set agent icon if loaded
            if f'agent_{i}' in loaded_images:
                agent_label.config(image=loaded_images[f'agent_{i}'])
                agent_label.image = loaded_images[f'agent_{i}']
            
            # Set rank icon if loaded
            if f'rank_{i}' in loaded_images:
                rank_label.config(image=loaded_images[f'rank_{i}'])
                rank_label.image = loaded_images[f'rank_{i}']
            
            player_widgets.append(card)
        
        # Update scroll region
        players_inner_frame.update_idletasks()
        players_canvas.configure(scrollregion=players_canvas.bbox("all"))
        
    except Exception as e:
        match_label.config(text=f"Error: {str(e)[:30]}")
    
    root.after(10000, refresh_data)

def init_app():
    print("[*] Initializing Valoripper...")
    valapi.ensure_static_data()
    live_match.load_skin_map()
    
    # Cache agents data for icons
    try:
        agents_data = valapi.load_cached('agents')
        if not agents_data:
            valapi.fetch_and_cache('agents', 'agents')
    except:
        pass
    
    print("[+] Ready!")

threading.Thread(target=init_app, daemon=True).start()
threading.Thread(target=refresh_data, daemon=True).start()
root.mainloop()