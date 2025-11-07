import tkinter as tk
from tkinter import ttk
import threading
import requests
from valorip import login, live_match, constants, valapi
from PIL import Image, ImageTk
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed

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

# --- GUI setup ---
root = tk.Tk()
root.title("Valoripper")
root.geometry("900x600")
root.configure(bg="#0f1923")
root.resizable(True, True)

# Custom styling
style = ttk.Style()
style.theme_use('clam')

# Configure styles
style.configure("TFrame", background="#0f1923")
style.configure("Card.TFrame", background="#1c2b36", relief="flat")
style.configure("TLabel", background="#0f1923", foreground="#ffffff", font=("Segoe UI", 10))
style.configure("Header.TLabel", font=("Segoe UI Semibold", 24), background="#0f1923", foreground="#ff4655")
style.configure("Subheader.TLabel", font=("Segoe UI", 11, "bold"), background="#1c2b36", foreground="#ffffff")
style.configure("Info.TLabel", font=("Segoe UI", 9), background="#0f1923", foreground="#b0b8c1")

# Header section
header_frame = ttk.Frame(root, style="TFrame", padding=(20, 15))
header_frame.pack(fill="x")

title_label = ttk.Label(header_frame, text="VALORIPPER", style="Header.TLabel")
title_label.pack(side="left")

# Match info section
info_frame = ttk.Frame(root, style="TFrame", padding=(20, 0, 20, 15))
info_frame.pack(fill="x")

info_container = ttk.Frame(info_frame, style="Card.TFrame", padding=15)
info_container.pack(fill="x")

match_label = ttk.Label(info_container, text="Match: Waiting...", style="Info.TLabel")
match_label.grid(row=0, column=0, sticky="w", padx=(0, 20))

map_label = ttk.Label(info_container, text="Map: ...", style="Info.TLabel")
map_label.grid(row=0, column=1, sticky="w", padx=(0, 20))

server_label = ttk.Label(info_container, text="Server: ...", style="Info.TLabel")
server_label.grid(row=0, column=2, sticky="w")

info_container.columnconfigure(0, weight=1)
info_container.columnconfigure(1, weight=1)
info_container.columnconfigure(2, weight=1)

# Main content area
content_frame = ttk.Frame(root, style="TFrame", padding=(20, 0, 20, 20))
content_frame.pack(fill="both", expand=True)

# Players panel (full width now)
players_container = ttk.Frame(content_frame, style="Card.TFrame")
players_container.pack(fill="both", expand=True)

players_header = ttk.Label(players_container, text="PLAYERS", style="Subheader.TLabel", padding=(15, 12))
players_header.pack(fill="x")

players_frame = ttk.Frame(players_container, style="Card.TFrame", padding=(0, 0, 0, 10))
players_frame.pack(fill="both", expand=True)

# Custom listbox with scrollbar
players_scroll = tk.Scrollbar(players_frame, bg="#1c2b36", troughcolor="#0f1923", 
                              activebackground="#ff4655", width=12)
players_scroll.pack(side="right", fill="y", padx=(0, 10))

players_list = tk.Listbox(
    players_frame,
    bg="#162029",
    fg="#ffffff",
    selectbackground="#ff4655",
    selectforeground="#ffffff",
    relief="flat",
    font=("Segoe UI", 10),
    borderwidth=0,
    highlightthickness=0,
    activestyle="none",
    yscrollcommand=players_scroll.set
)
players_list.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 0))
players_scroll.config(command=players_list.yview)

current_match_id = None
current_players = []

def load_image_from_url(url, max_size=None):
    """Download and resize image maintaining aspect ratio"""
    try:
        response = requests.get(url, timeout=10)
        img = Image.open(BytesIO(response.content))
        
        if max_size:
            img_width, img_height = img.size
            max_width, max_height = max_size
            
            width_ratio = max_width / img_width
            height_ratio = max_height / img_height
            scale_factor = min(width_ratio, height_ratio)
            
            new_width = int(img_width * scale_factor)
            new_height = int(img_height * scale_factor)
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        return ImageTk.PhotoImage(img)
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
                future = executor.submit(load_image_from_url, item['image_url'], item.get('max_size'))
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

def show_loadout_popup(player):
    """Show loadout popup matching NOWT's exact layout"""
    popup = tk.Toplevel(root)
    popup.title(f"{player.ign.username}'s Loadout")
    popup.geometry("1350x720")
    popup.configure(bg="#2b3442")
    popup.resizable(False, False)
    
    popup.images = {}
    
    loading_frame = tk.Frame(popup, bg="#2b3442")
    loading_frame.pack(fill="both", expand=True)
    
    loading_label = tk.Label(
        loading_frame,
        text="Loading...",
        font=("Segoe UI", 12),
        bg="#2b3442",
        fg="#ffffff"
    )
    loading_label.pack(expand=True)
    
    def load_and_display():
        loadout_data = live_match.get_player_loadout_organized(current_match_id, player.puuid)
        
        if not loadout_data:
            loadout_data = {'player_card': None, 'weapons': [], 'melee': None, 'sprays': []}
        
        # Fetch player stats with Henrik API key
        player_stats = None
        try:
            player_stats = live_match.get_player_stats(player.ign.username.split('#')[0], player.ign.username.split('#')[1] if '#' in player.ign.username else 'NA1')
        except:
            pass
        
        images_to_load = []
        
        if loadout_data.get('player_card'):
            images_to_load.append({'id': 'player_card', 'image_url': loadout_data['player_card'], 'max_size': (160, 260)})
        
        for i, weapon in enumerate(loadout_data.get('weapons', [])):
            if weapon.get('image_url'):
                images_to_load.append({'id': f'weapon_{i}', 'image_url': weapon['image_url'], 'max_size': (200, 100)})
        
        if loadout_data.get('melee') and loadout_data['melee'].get('image_url'):
            images_to_load.append({'id': 'melee', 'image_url': loadout_data['melee']['image_url'], 'max_size': (450, 140)})
        
        for i, spray in enumerate(loadout_data.get('sprays', [])):
            if spray.get('image_url'):
                images_to_load.append({'id': f'spray_{i}', 'image_url': spray['image_url'], 'max_size': (60, 60)})
        
        popup.images = load_all_images_parallel(images_to_load)
        loading_frame.destroy()
        
        # Main layout
        main = tk.Frame(popup, bg="#2b3442")
        main.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Left sidebar
        left = tk.Frame(main, bg="#2b3442", width=180)
        left.pack(side="left", fill="y", padx=(0, 15))
        left.pack_propagate(False)
        
        if 'player_card' in popup.images:
            card_bg = tk.Frame(left, bg="#1e2732", bd=0, highlightthickness=0)
            card_bg.pack(pady=(0, 8))
            card_lbl = tk.Label(card_bg, image=popup.images['player_card'], bg="#1e2732")
            card_lbl.pack(padx=3, pady=3)
            
            name = tk.Label(left, text=player.ign.username, font=("Segoe UI", 9, "bold"), bg="#2b3442", fg="#ffffff", wraplength=170)
            name.pack(pady=(0, 3))
            
            # Display stats if available
            if player_stats:
                stats_frame = tk.Frame(left, bg="#1e2732", bd=0)
                stats_frame.pack(fill="x", pady=(0, 12), padx=5)
                
                # Rank
                if player_stats.get('rank') and player_stats['rank'] != 'Unranked':
                    rank_label = tk.Label(stats_frame, text=f"Rank: {player_stats['rank']}", 
                                         font=("Segoe UI", 7), bg="#1e2732", fg="#b8c5d6", anchor="w")
                    rank_label.pack(fill="x", padx=5, pady=1)
                
                # Peak Rank
                if player_stats.get('peak_rank') and player_stats['peak_rank'] not in ['Unknown', 'Unranked']:
                    peak_label = tk.Label(stats_frame, text=f"Peak: {player_stats['peak_rank']}", 
                                         font=("Segoe UI", 7), bg="#1e2732", fg="#b8c5d6", anchor="w")
                    peak_label.pack(fill="x", padx=5, pady=1)
                
                # Win Rate - check if not None instead of truthy
                if player_stats.get('win_rate') is not None:
                    wr_label = tk.Label(stats_frame, text=f"Win Rate: {player_stats['win_rate']}%", 
                                       font=("Segoe UI", 7), bg="#1e2732", fg="#b8c5d6", anchor="w")
                    wr_label.pack(fill="x", padx=5, pady=1)
                
                # Headshot Rate - check if not None
                if player_stats.get('hs_rate') is not None:
                    hs_label = tk.Label(stats_frame, text=f"HS%: {player_stats['hs_rate']}%", 
                                       font=("Segoe UI", 7), bg="#1e2732", fg="#b8c5d6", anchor="w")
                    hs_label.pack(fill="x", padx=5, pady=1)
                
                # K/D Ratio - check if not None
                if player_stats.get('kd') is not None:
                    kd_label = tk.Label(stats_frame, text=f"K/D: {player_stats['kd']}", 
                                       font=("Segoe UI", 7), bg="#1e2732", fg="#b8c5d6", anchor="w")
                    kd_label.pack(fill="x", padx=5, pady=1)
            else:
                pass  # Don't show "Stats unavailable" message
        
        if loadout_data.get('sprays'):
            spray_title = tk.Label(left, text="SPRAYS", font=("Segoe UI", 8, "bold"), bg="#2b3442", fg="#8b96a3")
            spray_title.pack(anchor="w", pady=(0, 6))
            
            spray_grid = tk.Frame(left, bg="#2b3442")
            spray_grid.pack()
            
            for i, spray in enumerate(loadout_data.get('sprays', [])):
                if f'spray_{i}' in popup.images:
                    spray_box = tk.Frame(spray_grid, bg="#1e2732", width=65, height=65)
                    spray_box.grid(row=i//2, column=i%2, padx=2, pady=2)
                    spray_box.pack_propagate(False)
                    s_lbl = tk.Label(spray_box, image=popup.images[f'spray_{i}'], bg="#1e2732")
                    s_lbl.place(relx=0.5, rely=0.5, anchor="center")
        
        # Right content
        right = tk.Frame(main, bg="#2b3442")
        right.pack(side="left", fill="both", expand=True)
        
        # Weapons
        weap_title = tk.Label(right, text="WEAPONS", font=("Segoe UI", 10, "bold"), bg="#2b3442", fg="#ffffff")
        weap_title.pack(anchor="w", pady=(0, 8))
        
        weap_grid = tk.Frame(right, bg="#2b3442")
        weap_grid.pack(fill="both", expand=True)
        
        row, col = 0, 0
        for i, weapon in enumerate(loadout_data.get('weapons', [])):
            # Fixed size card
            card = tk.Frame(weap_grid, bg="#1e2732", width=215, height=125)
            card.grid(row=row, column=col, padx=3, pady=3)
            card.pack_propagate(False)
            card.grid_propagate(False)
            
            if f'weapon_{i}' in popup.images:
                img_lbl = tk.Label(card, image=popup.images[f'weapon_{i}'], bg="#1e2732")
                img_lbl.place(relx=0.5, rely=0.35, anchor="center")
            
            name_lbl = tk.Label(card, text=weapon['name'], font=("Segoe UI", 7), bg="#1e2732", fg="#ffffff", wraplength=205)
            name_lbl.place(relx=0.5, rely=0.85, anchor="center")
            
            col += 1
            if col >= 5:
                col = 0
                row += 1
        
        # Melee
        if loadout_data.get('melee'):
            melee_title = tk.Label(right, text="MELEE", font=("Segoe UI", 10, "bold"), bg="#2b3442", fg="#ffffff")
            melee_title.pack(anchor="w", pady=(12, 8))
            
            melee_card = tk.Frame(right, bg="#1e2732", width=470, height=160)
            melee_card.pack(anchor="w")
            melee_card.pack_propagate(False)
            
            if 'melee' in popup.images:
                m_img = tk.Label(melee_card, image=popup.images['melee'], bg="#1e2732")
                m_img.place(relx=0.5, rely=0.35, anchor="center")
            
            m_name = tk.Label(melee_card, text=loadout_data['melee']['name'], font=("Segoe UI", 7), bg="#1e2732", fg="#1e2732")
            m_name.place(relx=0.5, rely=0.85, anchor="center")
    
    threading.Thread(target=load_and_display, daemon=True).start()

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

        players_list.delete(0, tk.END)
        for p in current_players:
            players_list.insert(tk.END, f"  {p.ign.username}")
    except Exception as e:
        match_label.config(text=f"Error: {str(e)[:50]}")
    root.after(10000, refresh_data)

def on_player_select(event):
    global current_match_id, current_players
    selection = players_list.curselection()
    if not selection or not current_match_id:
        return
    index = selection[0]
    player = current_players[index]
    show_loadout_popup(player)

players_list.bind("<<ListboxSelect>>", on_player_select)

def init_app():
    print("[*] Initializing Valoripper...")
    valapi.ensure_static_data()
    live_match.load_skin_map()
    print("[+] Ready!")

threading.Thread(target=init_app, daemon=True).start()
threading.Thread(target=refresh_data, daemon=True).start()
root.mainloop()