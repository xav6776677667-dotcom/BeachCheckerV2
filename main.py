import flet as ft
import math
import time
import threading
import concurrent.futures
from datetime import datetime
import requests

# ---------------------------------------------------------------------------
# Settings & Data
# ---------------------------------------------------------------------------
REFRESH_SECONDS = 300

# Fallback coordinates (Cornwall, UK) if network location fails
FALLBACK_LAT = 50.503
FALLBACK_LON = -4.414

BEACHES = [
    {"name": "Looe Beach", "lat": 50.353, "lon": -4.454, "rating": 8.6, "parking": True, "lifeguard": False, "dogs": "Seasonal", "facilities": 9},
    {"name": "Seaton Beach", "lat": 50.361, "lon": -4.391, "rating": 9.2, "parking": True, "lifeguard": True, "dogs": "Yes", "facilities": 8},
    {"name": "Whitsand Bay", "lat": 50.334, "lon": -4.267, "rating": 9.8, "parking": True, "lifeguard": True, "dogs": "Yes", "facilities": 7},
    {"name": "Polperro Beach", "lat": 50.332, "lon": -4.518, "rating": 8.9, "parking": True, "lifeguard": False, "dogs": "Seasonal", "facilities": 8},
    {"name": "Portwrinkle", "lat": 50.356, "lon": -4.313, "rating": 9.0, "parking": True, "lifeguard": False, "dogs": "Yes", "facilities": 6},
    {"name": "Downderry Beach", "lat": 50.364, "lon": -4.366, "rating": 8.7, "parking": True, "lifeguard": False, "dogs": "Yes", "facilities": 6},
    {"name": "Tregantle Beach", "lat": 50.336, "lon": -4.294, "rating": 9.5, "parking": False, "lifeguard": False, "dogs": "Yes", "facilities": 5},
    {"name": "Readymoney Cove", "lat": 50.332, "lon": -4.640, "rating": 8.4, "parking": True, "lifeguard": False, "dogs": "Seasonal", "facilities": 7},
    {"name": "Polkerris Beach", "lat": 50.338, "lon": -4.687, "rating": 8.8, "parking": True, "lifeguard": False, "dogs": "Yes", "facilities": 8},
    {"name": "Par Beach", "lat": 50.346, "lon": -4.706, "rating": 8.5, "parking": True, "lifeguard": True, "dogs": "Seasonal", "facilities": 9},
]

# ---------------------------------------------------------------------------
# Core Data Logic 
# ---------------------------------------------------------------------------
def get_user_location():
    """Fetches user's rough location via IP for out-of-the-box cross-platform support."""
    try:
        res = requests.get("http://ip-api.com/json/", timeout=5).json()
        return res["lat"], res["lon"]
    except Exception:
        return FALLBACK_LAT, FALLBACK_LON

def km_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)

def crowd_level(distance, rating):
    hour = datetime.now().hour
    weekday = datetime.now().weekday()
    score = 0
    if rating >= 9.5: score += 4
    elif rating >= 9: score += 3
    elif rating >= 8: score += 2
    if weekday >= 5: score += 3
    if 11 <= hour <= 16: score += 3
    elif 17 <= hour <= 20: score += 1
    if distance < 12: score += 2
    elif distance < 20: score += 1
    
    if score <= 3: return "Quiet"
    if score <= 6: return "Moderate"
    return "Busy"

def beach_score(beach, distance, temp, wind, mode="default"):
    score = 50.0
    score -= distance * 1.1

    if mode == "surfer":
        score += beach["rating"] * 3.0
        if wind:
            if wind > 25: score += 15
            elif wind > 15: score += 8
            elif wind < 10: score -= 10
    elif mode == "foodie":
        score += beach["facilities"] * 4.0
        score += beach["rating"] * 2.0
        if beach["parking"]: score += 5
    elif mode == "soft_sand":
        score += beach["rating"] * 5.0
        if beach["lifeguard"]: score += 8
        if beach["parking"]: score += 6
        if wind and wind > 20: score -= 10 
    else: 
        score += beach["rating"] * 4.5
        score += beach["facilities"] * 1.2
        if beach["lifeguard"]: score += 6
        if beach["parking"]: score += 4
        if temp:
            if 18 <= temp <= 26: score += 8
            elif 15 <= temp < 18 or 26 < temp <= 28: score += 3
            elif temp < 12: score -= 8
        if wind:
            if wind < 15: score += 5
            elif wind > 30: score -= 10
            elif wind > 22: score -= 4

    return round(max(0, score), 1)

def get_weather(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m,weather_code&timezone=Europe/London"
        data = requests.get(url, timeout=12).json()
        cur = data["current"]
        return {"temp": round(cur["temperature_2m"], 1), "wind": round(cur["wind_speed_10m"], 1)}
    except Exception:
        return {"temp": None, "wind": None}

def fetch_beach_data(beach, user_lat, user_lon, mode="default"):
    dist = km_distance(user_lat, user_lon, beach["lat"], beach["lon"])
    weather = get_weather(beach["lat"], beach["lon"])
    crowd = crowd_level(dist, beach["rating"])
    score = beach_score(beach, dist, weather["temp"], weather["wind"], mode)
    return {
        "name": beach["name"],
        "distance": dist,
        "crowd": crowd,
        "temp": weather["temp"],
        "wind": weather["wind"],
        "score": score,
        "raw_beach": beach
    }

# ---------------------------------------------------------------------------
# UI Helpers
# ---------------------------------------------------------------------------
def get_crowd_badge(crowd):
    colors = {
        "Quiet": (ft.colors.GREEN_300, ft.colors.GREEN_900),
        "Moderate": (ft.colors.ORANGE_300, ft.colors.ORANGE_900),
        "Busy": (ft.colors.RED_300, ft.colors.RED_900)
    }
    text_color, bg_color = colors.get(crowd, (ft.colors.GREY_400, ft.colors.GREY_900))
    return ft.Container(
        content=ft.Text(crowd, size=11, color=text_color, weight="bold"),
        bgcolor=bg_color,
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
        border_radius=16
    )

# ---------------------------------------------------------------------------
# Main App Class
# ---------------------------------------------------------------------------
class BeachMonitorApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Beach Monitor"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = "#0d1117"
        
        # State Variables
        self.user_lat = FALLBACK_LAT
        self.user_lon = FALLBACK_LON
        self.all_data = []
        self.sort_col = "score"
        self.sort_asc = False
        self.search_query = ""
        self.active_mode = "default"
        self.is_loading = False

        self.build_ui()
        self.show_terms_dialog()

    def show_terms_dialog(self):
        """Displays a modal dialog asking the user to accept T&C before using the app."""
        
        def open_terms_link(e):
            self.page.launch_url("https://example.com/terms-of-service")

        def accept_terms(e):
            self.tc_dialog.open = False
            self.page.update()
            self.start_app_logic()

        self.tc_dialog = ft.AlertDialog(
            modal=True,
            bgcolor="#161b22",
            title=ft.Text("Welcome to Beach Monitor \u26f1\ufe0f", weight="bold", color="white"),
            content=ft.Text(
                "Before we dive in, we need to access your rough network location to calculate distance to nearby beaches. "
                "By continuing, you accept our Terms of Service & Privacy Policy.",
                color="#8b949e"
            ),
            actions=[
                ft.TextButton("Read Terms", on_click=open_terms_link, icon=ft.icons.OPEN_IN_NEW),
                ft.ElevatedButton("Accept & Continue", on_click=accept_terms, bgcolor="#5b8cff", color="white"),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        self.page.dialog = self.tc_dialog
        self.tc_dialog.open = True
        self.page.update()

    def start_app_logic(self):
        """Runs only after T&C are accepted."""
        # 1. Fetch user's actual location
        self.show_snackbar("Locating you...", icon=ft.icons.LOCATION_SEARCHING, color=ft.colors.BLUE_400)
        self.user_lat, self.user_lon = get_user_location()
        
        # 2. Start initial data load in background
        threading.Thread(target=self.background_loop, daemon=True).start()

    def build_ui(self):
        # 1. Native App Bar
        self.page.appbar = ft.AppBar(
            title=ft.Text("Beach Monitor", weight="bold", color="#5b8cff"),
            center_title=False,
            bgcolor="#161b22",
            actions=[
                ft.IconButton(
                    icon=ft.icons.REFRESH_ROUNDED, 
                    tooltip="Refresh Data", 
                    on_click=self.manual_refresh,
                    icon_color="#5b8cff"
                ),
                ft.Container(width=10) # Right padding
            ],
        )

        # 2. Controls (Mode, Search, Sort)
        controls_container = ft.Container(
            padding=ft.padding.only(left=16, right=16, top=16, bottom=8),
            content=ft.Column([
                self.build_mode_dropdown(),
                ft.Row([self.build_search_box(), self.build_sort_dropdown()], spacing=12),
            ], spacing=12)
        )

        # 3. Progress Bar (Hidden by default)
        self.progress_bar = ft.ProgressBar(color="#5b8cff", bgcolor="#161b22", visible=False)

        # 4. List View for Cards
        self.cards_list = ft.ListView(
            expand=True,
            spacing=16,
            padding=ft.padding.all(16)
        )

        # Assemble Page layout
        self.page.add(
            ft.SafeArea(
                ft.Column([
                    controls_container,
                    self.progress_bar,
                    self.cards_list
                ], expand=True)
            )
        )

    def build_mode_dropdown(self):
        return ft.Dropdown(
            value="default",
            height=50,
            bgcolor="#161b22",
            border_color="#30363d",
            border_radius=8,
            options=[
                ft.dropdown.Option("default", "⚖️  Balanced Mode"),
                ft.dropdown.Option("surfer", "🏄  I'm a Surfer"),
                ft.dropdown.Option("foodie", "🍔  I'm a Foodie"),
                ft.dropdown.Option("soft_sand", "🏖️  I like Soft Sand"),
            ],
            on_change=self.on_mode_change
        )

    def build_search_box(self):
        return ft.TextField(
            hint_text="Search...",
            on_change=self.on_search,
            expand=True,
            height=45,
            content_padding=12,
            bgcolor="#161b22",
            border_color="#30363d",
            border_radius=8,
            prefix_icon=ft.icons.SEARCH_ROUNDED,
        )

    def build_sort_dropdown(self):
        return ft.Dropdown(
            value="score",
            width=130,
            height=45,
            bgcolor="#161b22",
            border_color="#30363d",
            border_radius=8,
            content_padding=10,
            options=[
                ft.dropdown.Option("score", "Score"),
                ft.dropdown.Option("distance", "Distance"),
                ft.dropdown.Option("temp", "Temp"),
                ft.dropdown.Option("wind", "Wind"),
            ],
            on_change=self.on_sort_change
        )

    def show_snackbar(self, message, icon=ft.icons.CHECK_CIRCLE, color=ft.colors.GREEN_400):
        self.page.snack_bar = ft.SnackBar(
            content=ft.Row([
                ft.Icon(icon, color=color),
                ft.Text(message, color=ft.colors.WHITE)
            ]),
            bgcolor="#161b22",
            behavior=ft.SnackBarBehavior.FLOATING,
            duration=2500
        )
        self.page.snack_bar.open = True
        self.page.update()

    # --- Interaction Handlers ---
    def on_mode_change(self, e):
        self.active_mode = e.control.value
        for item in self.all_data:
            item["score"] = beach_score(
                item["raw_beach"], item["distance"], item["temp"], item["wind"], mode=self.active_mode
            )
        self.render_cards()

    def on_search(self, e):
        self.search_query = e.control.value.lower()
        self.render_cards()

    def on_sort_change(self, e):
        self.sort_col = e.control.value
        self.sort_asc = True if self.sort_col in ["distance", "wind"] else False
        self.render_cards()

    def manual_refresh(self, e):
        if not self.is_loading:
            threading.Thread(target=self.fetch_all_data, daemon=True).start()

    # --- Data Fetching ---
    def fetch_all_data(self):
        self.is_loading = True
        self.progress_bar.visible = True
        self.page.update()

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                # Passing user's dynamic location to the fetcher
                futures = [pool.submit(fetch_beach_data, beach, self.user_lat, self.user_lon, self.active_mode) for beach in BEACHES]
                self.all_data = [f.result() for f in concurrent.futures.as_completed(futures)]
            
            timestamp = time.strftime("%I:%M %p")
            self.show_snackbar(f"Live data updated at {timestamp}")
        except Exception:
            self.show_snackbar("Network error. Could not update.", icon=ft.icons.ERROR, color=ft.colors.RED_400)
        finally:
            self.is_loading = False
            self.progress_bar.visible = False
            self.render_cards()

    def background_loop(self):
        # Initial load immediately, then every X seconds without blocking
        self.fetch_all_data()
        while True:
            time.sleep(REFRESH_SECONDS)
            self.fetch_all_data()

    # --- Rendering ---
    def render_cards(self):
        filtered = [b for b in self.all_data if self.search_query in b["name"].lower()]
        
        def sort_key(row):
            val = row.get(self.sort_col)
            return val if val is not None else (0 if self.sort_asc else float('inf'))
            
        filtered.sort(key=sort_key, reverse=not self.sort_asc)

        self.cards_list.controls.clear()

        # Handle Empty State
        if not filtered:
            self.cards_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.SEARCH_OFF_ROUNDED, size=50, color="#30363d"),
                        ft.Text("No beaches match your search.", color="#7c8698", size=16)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.alignment.center,
                    padding=ft.padding.only(top=50)
                )
            )
            self.page.update()
            return

        # Render Data Cards
        for data in filtered:
            score_color = "#2ecc71" if data["score"] >= 70 else ("#ff5f5f" if data["score"] < 45 else "#e8ebf1")

            card = ft.Container(
                bgcolor="#161b22",
                border=ft.border.all(1, "#30363d"),
                border_radius=16,
                padding=16,
                shadow=ft.BoxShadow(spread_radius=1, blur_radius=10, color="#05070a", offset=ft.Offset(0, 4)),
                content=ft.Column([
                    ft.Row([
                        ft.Text(data["name"], size=18, weight="w600", color="white", expand=True),
                        ft.Container(
                            content=ft.Text(str(data["score"]), color=score_color, weight="bold", size=16),
                            bgcolor="#0d1117",
                            padding=ft.padding.symmetric(horizontal=12, vertical=6),
                            border_radius=8
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                    ft.Divider(color="#21262d", height=16),

                    ft.Row([
                        # Left block: Location and Weather
                        ft.Column([
                            ft.Row([
                                ft.Icon(ft.icons.LOCATION_ON_ROUNDED, size=16, color="#5b8cff"),
                                ft.Text(f"{data['distance']} km away", size=13, color="#8b949e"),
                            ], spacing=6),
                            ft.Row([
                                ft.Icon(ft.icons.THERMOSTAT_ROUNDED, size=16, color="#ff7b72"),
                                ft.Text(f"{data['temp']}°C" if data['temp'] else "N/A", size=13, color="#8b949e"),
                                ft.Container(width=4), # spacer
                                ft.Icon(ft.icons.AIR_ROUNDED, size=16, color="#a5d6ff"),
                                ft.Text(f"{data['wind']} km/h" if data['wind'] else "N/A", size=13, color="#8b949e"),
                            ], spacing=6),
                        ], spacing=8),
                        
                        # Right block: Badge
                        get_crowd_badge(data["crowd"])
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.END)
                ], spacing=4)
            )
            self.cards_list.controls.append(card)

        self.page.update()

# Run Application
if __name__ == "__main__":
    ft.app(target=lambda page: BeachMonitorApp(page))
