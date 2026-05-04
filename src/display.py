#!/usr/bin/env python3
"""
ADS-B + Drone Detection Field Display
Multi-sensor RF correlation engine
V1.2 - Professional field tool
"""
import pygame
import math
import time
import json
import urllib.request
import threading
import subprocess
import os
import shutil
from datetime import datetime, timezone
from collections import deque

# ─────────────────────────────────────────
# DISPLAY CONFIG
# ─────────────────────────────────────────
SCREEN_W, SCREEN_H = 800, 480
FPS = 30
TOP_BAR_H = 36
PANEL_W = 260
RADAR_X = PANEL_W
RADAR_W = SCREEN_W - PANEL_W
RADAR_H = SCREEN_H - TOP_BAR_H
MAX_RANGE_NM = 50
TRACK_HISTORY = 90
SPEED_VECTOR_SECS = 60
CONTACT_FADE_SECS = 15
CORR_WINDOW_SECS = 10
CORR_ALERT_SECS = 30
BOOT_DURATION = 3.0
CORR_LOG_FILE = "/home/pi/correlation_log.json"

# ─────────────────────────────────────────
# COLOR PALETTES
# ─────────────────────────────────────────
PALETTES = {
    "STANDARD": {
        "BG":           (6, 8, 6),
        "RADAR_BG":     (4, 10, 4),
        "PANEL_BG":     (6, 8, 6),
        "PRIMARY":      (210, 140, 0),
        "PRIMARY_DIM":  (120, 80, 0),
        "PRIMARY_DARK": (40, 26, 0),
        "WHITE":        (220, 220, 210),
        "GRAY":         (55, 55, 50),
        "DARK_GRAY":    (20, 20, 18),
        "SEPARATOR":    (40, 40, 35),
        "CONTACT_HI":   (180, 220, 255),
        "CONTACT_LO":   (255, 160, 80),
        "CONTACT_MID":  (180, 255, 180),
        "CONTACT_DIM":  (80, 110, 140),
        "RF_COLOR":     (200, 120, 30),
        "RF_DIM":       (100, 60, 15),
        "ALERT":        (220, 60, 60),
        "ALERT_DIM":    (100, 20, 20),
        "GREEN_OK":     (60, 180, 60),
        "CORR_HIGH":    (60, 200, 60),
        "CORR_MED":     (220, 180, 0),
        "CORR_LOW":     (220, 60, 60),
    },
    "FIELD": {
        "BG":           (0, 0, 0),
        "RADAR_BG":     (0, 0, 0),
        "PANEL_BG":     (0, 0, 0),
        "PRIMARY":      (255, 200, 0),
        "PRIMARY_DIM":  (180, 140, 0),
        "PRIMARY_DARK": (60, 40, 0),
        "WHITE":        (255, 255, 255),
        "GRAY":         (140, 140, 140),
        "DARK_GRAY":    (30, 30, 30),
        "SEPARATOR":    (80, 80, 80),
        "CONTACT_HI":   (255, 255, 255),
        "CONTACT_LO":   (255, 200, 100),
        "CONTACT_MID":  (200, 255, 200),
        "CONTACT_DIM":  (160, 160, 160),
        "RF_COLOR":     (255, 160, 0),
        "RF_DIM":       (180, 100, 0),
        "ALERT":        (255, 80, 80),
        "ALERT_DIM":    (180, 40, 40),
        "GREEN_OK":     (100, 255, 100),
        "CORR_HIGH":    (100, 255, 100),
        "CORR_MED":     (255, 220, 0),
        "CORR_LOW":     (255, 80, 80),
    },
    "NIGHT": {
        "BG":           (8, 0, 0),
        "RADAR_BG":     (6, 0, 0),
        "PANEL_BG":     (8, 0, 0),
        "PRIMARY":      (180, 30, 30),
        "PRIMARY_DIM":  (100, 15, 15),
        "PRIMARY_DARK": (30, 5, 5),
        "WHITE":        (200, 120, 120),
        "GRAY":         (80, 30, 30),
        "DARK_GRAY":    (20, 5, 5),
        "SEPARATOR":    (50, 15, 15),
        "CONTACT_HI":   (220, 100, 100),
        "CONTACT_LO":   (200, 80, 80),
        "CONTACT_MID":  (210, 90, 90),
        "CONTACT_DIM":  (120, 40, 40),
        "RF_COLOR":     (180, 60, 60),
        "RF_DIM":       (100, 30, 30),
        "ALERT":        (255, 60, 60),
        "ALERT_DIM":    (120, 20, 20),
        "GREEN_OK":     (160, 60, 60),
        "CORR_HIGH":    (160, 60, 60),
        "CORR_MED":     (180, 50, 50),
        "CORR_LOW":     (220, 40, 40),
    },
}

DISPLAY_MODES = ["STANDARD", "FIELD", "NIGHT"]
display_mode_index = 0

def C(key):
    return PALETTES[DISPLAY_MODES[display_mode_index]][key]

# ─────────────────────────────────────────
# UNITS
# ─────────────────────────────────────────
UNITS = ["NM", "MI", "KM"]
unit_index = 0
UNIT_FACTORS = {"NM": 1.0, "MI": 1.15078, "KM": 1.852}
RING_NM = [10, 20, 30, 40, 50]

def nm_to_unit(nm):
    u = UNITS[unit_index]
    return nm * UNIT_FACTORS[u], u

# ─────────────────────────────────────────
# PANEL VIEWS
# ─────────────────────────────────────────
PANEL_VIEWS = ["CONTACTS", "RF ACTIVITY", "SYSTEM"]
panel_view_index = 0

# ─────────────────────────────────────────
# SHARED STATE
# ─────────────────────────────────────────
aircraft_data = []
drone_data = []
gps_data = {"lat": 0.0, "lon": 0.0, "alt": 0.0, "fix": False}
selected_hex = None
heartbeat = True
last_update_time = 0.0
data_lock = threading.Lock()
track_history = {}
rf_events = deque()
radar_events = deque()
correlations = deque()
corr_log = []
rf_flash_timer = 0
shutdown_pending = False
shutdown_pending_time = 0
gps_reset_pending = False
gps_reset_pending_time = 0

# ─────────────────────────────────────────
# CORRELATION LOG PERSISTENCE
# ─────────────────────────────────────────
def save_corr_log():
    try:
        with open(CORR_LOG_FILE, "w") as f:
            json.dump(corr_log, f, indent=2)
    except:
        pass

def load_corr_log():
    global corr_log
    try:
        with open(CORR_LOG_FILE, "r") as f:
            corr_log = json.load(f)
    except:
        corr_log = []

# ─────────────────────────────────────────
# FETCH THREAD
# ─────────────────────────────────────────
def fetch_loop():
    global aircraft_data, drone_data, gps_data, last_update_time
    while True:
        try:
            with open("/run/dump1090/aircraft.json") as f:
                d = json.load(f)
                with data_lock:
                    aircraft_data = d.get("aircraft", [])
                    last_update_time = time.time()
        except:
            pass
        try:
            with urllib.request.urlopen("http://localhost:5001/api/location", timeout=2) as r:
                with data_lock:
                    gps_data = json.loads(r.read())
        except:
            pass
        try:
            with urllib.request.urlopen("http://localhost:5001/api/drone_detections", timeout=2) as r:
                new_drones = json.loads(r.read())
                with data_lock:
                    drone_data = new_drones[-20:]
                ingest_rf_events(new_drones[-5:])
        except:
            pass
        time.sleep(2)

# ─────────────────────────────────────────
# CORRELATION ENGINE
# ─────────────────────────────────────────
def ingest_rf_events(new_drones):
    global rf_flash_timer
    now = time.time()
    for d in new_drones:
        try:
            pwr = float(d.get("power", "0 dB").replace(" dB", ""))
            rf_events.append((now, d.get("freq", ""), pwr, d.get("band", "")))
            rf_flash_timer = FPS
        except:
            pass
    while rf_events and now - rf_events[0][0] > 60:
        rf_events.popleft()

def ingest_radar_event(hex_id, lat, lon):
    now = time.time()
    radar_events.append((now, hex_id, lat, lon))
    while radar_events and now - radar_events[0][0] > 60:
        radar_events.popleft()
    run_correlation()

def run_correlation():
    now = time.time()
    recent_rf = [e for e in rf_events if now - e[0] < CORR_WINDOW_SECS]
    recent_radar = [e for e in radar_events if now - e[0] < CORR_WINDOW_SECS]
    if not recent_rf or not recent_radar:
        return
    for rev in recent_radar:
        for rfev in recent_rf:
            dt = abs(rev[0] - rfev[0])
            if dt < CORR_WINDOW_SECS:
                confidence = max(10, 100 - int(dt * 8))
                msg = f"RF {rfev[1]} / {rev[1].upper()}  dt={dt:.1f}s"
                correlations.append((now, msg, confidence))
                entry = {
                    "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                    "rf_freq": rfev[1],
                    "rf_band": rfev[3],
                    "contact": rev[1],
                    "delta_secs": round(dt, 2),
                    "confidence": confidence
                }
                corr_log.append(entry)
                save_corr_log()
    while correlations and now - correlations[0][0] > CORR_ALERT_SECS:
        correlations.popleft()

def corr_color(confidence):
    if confidence >= 70:
        return C("CORR_HIGH")
    if confidence >= 40:
        return C("CORR_MED")
    return C("CORR_LOW")

# ─────────────────────────────────────────
# GEOMETRY
# ─────────────────────────────────────────
def lat_lon_to_radar(lat, lon, clat, clon, cx, cy, radius):
    dlat = lat - clat
    dlon = lon - clon
    dist_nm = math.sqrt(
        (dlat * 60) ** 2 +
        (dlon * 60 * math.cos(math.radians(clat))) ** 2
    )
    bearing = math.atan2(dlon * math.cos(math.radians(clat)), dlat)
    r = (dist_nm / MAX_RANGE_NM) * radius
    x = cx + r * math.sin(bearing)
    y = cy - r * math.cos(bearing)
    return x, y, dist_nm, math.degrees(bearing) % 360

def bearing_str(deg):
    dirs = ["N","NE","E","SE","S","SW","W","NW"]
    return dirs[int((deg + 22.5) / 45) % 8]

def altitude_color(alt_ft):
    if alt_ft is None:
        return C("CONTACT_DIM")
    if alt_ft < 5000:
        return C("CONTACT_LO")
    if alt_ft < 18000:
        return C("CONTACT_MID")
    return C("CONTACT_HI")

# ─────────────────────────────────────────
# SIGNAL BARS
# ─────────────────────────────────────────
def draw_signal_bars(surface, x, y, power_db, color):
    bars = max(1, min(5, int((power_db + 20) / 4) + 1))
    for i in range(5):
        c = color if i < bars else C("DARK_GRAY")
        pygame.draw.rect(surface, c, (x + i * 6, y - i * 2, 4, 8 + i * 2))

# ─────────────────────────────────────────
# BOOT SCREEN
# ─────────────────────────────────────────
def draw_boot_screen(surface, fonts, progress):
    surface.fill((0, 0, 0))
    f = fonts["small"]
    ft = fonts["tiny"]
    cx = SCREEN_W // 2
    cy = SCREEN_H // 2

    title = fonts["small"].render("ADS-B MULTI-SENSOR FIELD SYSTEM", True, (210, 140, 0))
    surface.blit(title, (cx - title.get_width() // 2, cy - 60))

    version = ft.render("V1.2  //  INITIALIZING SYSTEMS", True, (120, 80, 0))
    surface.blit(version, (cx - version.get_width() // 2, cy - 35))

    checks = [
        "LOADING CORRELATION ENGINE",
        "STARTING RF MONITORS",
        "CONNECTING GPS SERVICE",
        "INITIALIZING RADAR DISPLAY",
    ]
    num_done = int(progress * len(checks))
    for i, check in enumerate(checks):
        if i < num_done:
            col = (60, 180, 60)
            status = "OK"
        elif i == num_done:
            col = (210, 140, 0)
            status = "..."
        else:
            col = (40, 40, 40)
            status = "--"
        line = ft.render(f"  {check:<35} [{status}]", True, col)
        surface.blit(line, (cx - line.get_width() // 2, cy + i * 20))

    # Progress bar
    bar_w = 400
    bar_x = cx - bar_w // 2
    bar_y = cy + 110
    pygame.draw.rect(surface, (40, 26, 0), (bar_x, bar_y, bar_w, 8))
    pygame.draw.rect(surface, (210, 140, 0), (bar_x, bar_y, int(bar_w * progress), 8))
    pygame.draw.rect(surface, (120, 80, 0), (bar_x, bar_y, bar_w, 8), 1)

# ─────────────────────────────────────────
# TOP BAR
# ─────────────────────────────────────────
def draw_top_bar(surface, fonts, gps, hb):
    pygame.draw.rect(surface, C("DARK_GRAY"), (0, 0, SCREEN_W, TOP_BAR_H))
    pygame.draw.line(surface, C("SEPARATOR"), (0, TOP_BAR_H - 1), (SCREEN_W, TOP_BAR_H - 1), 1)
    f = fonts["small"]
    ft = fonts["tiny"]

    if gps["fix"]:
        lat_str = f"LAT {gps['lat']:>10.5f}"
        lon_str = f"LON {gps['lon']:>11.5f}"
        alt_str = f"ALT {gps['alt']:.0f}m"
        cc = C("PRIMARY")
    else:
        lat_str = "LAT  -------"
        lon_str = "LON  --------"
        alt_str = "ALT  --"
        cc = C("PRIMARY_DIM")

    surface.blit(f.render(lat_str, True, cc), (8, 10))
    surface.blit(f.render(lon_str, True, cc), (170, 10))
    surface.blit(f.render(alt_str, True, cc), (340, 10))

    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    t_surf = f.render(now, True, C("WHITE"))
    surface.blit(t_surf, (SCREEN_W // 2 + 30, 10))

    age = time.time() - last_update_time if last_update_time else 99
    age_color = C("GREEN_OK") if age < 5 else C("ALERT")
    surface.blit(ft.render(f"UPD {age:.0f}s", True, age_color), (SCREEN_W - 88, 6))
    surface.blit(ft.render(DISPLAY_MODES[display_mode_index], True, C("PRIMARY_DIM")), (SCREEN_W - 88, 20))

    hb_color = C("PRIMARY") if hb else C("PRIMARY_DARK")
    pygame.draw.circle(surface, hb_color, (SCREEN_W - 8, TOP_BAR_H // 2), 5)
    pygame.draw.circle(surface, C("PRIMARY_DIM"), (SCREEN_W - 8, TOP_BAR_H // 2), 5, 1)

# ─────────────────────────────────────────
# PANEL
# ─────────────────────────────────────────
def draw_panel(surface, fonts, aircraft, drones, gps):
    pygame.draw.rect(surface, C("PANEL_BG"), (0, TOP_BAR_H, PANEL_W, SCREEN_H - TOP_BAR_H))
    pygame.draw.line(surface, C("SEPARATOR"), (PANEL_W - 1, TOP_BAR_H), (PANEL_W - 1, SCREEN_H), 1)

    ft = fonts["tiny"]
    f = fonts["small"]
    view = PANEL_VIEWS[panel_view_index]

    # Tabs with contact badge
    tab_w = PANEL_W // len(PANEL_VIEWS)
    ac_count = len(aircraft)
    for i, v in enumerate(PANEL_VIEWS):
        active = i == panel_view_index
        col = C("PRIMARY") if active else C("PRIMARY_DIM")
        label = v[:4]
        if v == "CONTACTS" and ac_count > 0:
            label = f"{v[:4]} {ac_count:02d}"
        surf = ft.render(label, True, col)
        surface.blit(surf, (i * tab_w + 4, TOP_BAR_H + 4))
        if active:
            pygame.draw.line(surface, C("PRIMARY"),
                (i * tab_w, TOP_BAR_H + 18),
                ((i + 1) * tab_w - 2, TOP_BAR_H + 18), 1)

    y = TOP_BAR_H + 24
    pygame.draw.line(surface, C("SEPARATOR"), (0, y), (PANEL_W, y), 1)
    y += 6

    if view == "CONTACTS":
        draw_panel_contacts(surface, fonts, aircraft, gps, y)
    elif view == "RF ACTIVITY":
        draw_panel_rf(surface, fonts, drones, y)
    elif view == "SYSTEM":
        draw_panel_system(surface, fonts, gps, y)

def draw_panel_contacts(surface, fonts, aircraft, gps, y):
    global selected_hex
    f = fonts["small"]
    ft = fonts["tiny"]

    ac_pos = [a for a in aircraft if "lat" in a and "lon" in a]
    surface.blit(f.render(f"CONTACTS {len(aircraft):02d}  POS {len(ac_pos):02d}", True, C("PRIMARY_DIM")), (6, y))
    y += 20

    sel = next((a for a in aircraft if a.get("hex") == selected_hex), None)
    if sel:
        ident = sel.get("flight", sel.get("hex", "")).strip() or sel.get("hex", "")
        alt = sel.get("alt_baro", sel.get("alt_geom", None))
        spd = sel.get("gs", None)
        hdg = sel.get("track", None)
        alt_str = f"{int(alt):,}ft" if isinstance(alt, (int, float)) else "--"
        spd_str = f"{int(spd)}kt" if isinstance(spd, (int, float)) else "--"
        hdg_str = f"{int(hdg):03d}°" if isinstance(hdg, (int, float)) else "--"

        pygame.draw.rect(surface, C("PRIMARY_DARK"), (2, y, PANEL_W - 4, 76))
        pygame.draw.rect(surface, C("PRIMARY_DIM"), (2, y, PANEL_W - 4, 76), 1)
        surface.blit(f.render(f"► {ident}", True, C("PRIMARY")), (6, y + 3))
        surface.blit(ft.render(f"ALT  {alt_str}", True, C("WHITE")), (6, y + 20))
        surface.blit(ft.render(f"SPD  {spd_str}", True, C("WHITE")), (6, y + 34))
        surface.blit(ft.render(f"HDG  {hdg_str}", True, C("WHITE")), (6, y + 48))
        if gps["fix"] and "lat" in sel:
            _, _, dist_nm, brg = lat_lon_to_radar(
                sel["lat"], sel["lon"],
                gps["lat"], gps["lon"],
                0, 0, 1
            )
            dist_val, unit = nm_to_unit(dist_nm)
            surface.blit(ft.render(f"RNG  {dist_val:.1f}{unit}", True, C("WHITE")), (135, y + 20))
            surface.blit(ft.render(f"BRG  {int(brg):03d}°", True, C("WHITE")), (135, y + 34))
            surface.blit(ft.render(f"     {bearing_str(brg)}", True, C("WHITE")), (135, y + 48))
        y += 82
        pygame.draw.line(surface, C("SEPARATOR"), (0, y), (PANEL_W, y), 1)
        y += 4

    for ac in aircraft[:10]:
        ident = ac.get("flight", ac.get("hex", "??????")).strip() or ac.get("hex", "??????")
        alt = ac.get("alt_baro", ac.get("alt_geom", None))
        spd = ac.get("gs", None)
        alt_str = f"{int(alt):>6,}" if isinstance(alt, (int, float)) else "      "
        spd_str = f"{int(spd):>3}kt" if isinstance(spd, (int, float)) else "  --"
        has_pos = "lat" in ac and "lon" in ac
        is_sel = ac.get("hex") == selected_hex
        col = C("PRIMARY") if is_sel else (C("CONTACT_HI") if has_pos else C("CONTACT_DIM"))
        prefix = "►" if is_sel else " "
        surface.blit(ft.render(f"{prefix}{ident:<8}{alt_str}ft {spd_str}", True, col), (4, y))
        y += 16
        if y > SCREEN_H - 50:
            break

    # Correlation alert box
    if correlations:
        latest = correlations[-1]
        age = time.time() - latest[0]
        if age < CORR_ALERT_SECS:
            flash = int(time.time() * 2) % 2 == 0
            conf = latest[2]
            col = corr_color(conf) if not flash else C("ALERT")
            pygame.draw.rect(surface, C("ALERT_DIM"), (2, SCREEN_H - 46, PANEL_W - 4, 42))
            pygame.draw.rect(surface, col, (2, SCREEN_H - 46, PANEL_W - 4, 42), 1)
            surface.blit(f.render("⚠ CORRELATED ACTIVITY", True, col), (6, SCREEN_H - 44))
            surface.blit(ft.render(f"CONF {conf}%", True, corr_color(conf)), (6, SCREEN_H - 28))
            surface.blit(ft.render(latest[1][:32], True, C("WHITE")), (6, SCREEN_H - 14))

def draw_panel_rf(surface, fonts, drones, y):
    ft = fonts["tiny"]
    f = fonts["small"]
    surface.blit(f.render("RF ACTIVITY", True, C("PRIMARY_DIM")), (6, y))
    y += 20
    for d in reversed(drones[-14:]):
        t = d.get("time", "")[-8:]
        freq = d.get("freq", "").replace(" MHz", "")
        band = d.get("band", "")
        pwr_str = d.get("power", "0 dB").replace(" dB", "")
        try:
            pwr = float(pwr_str)
        except:
            pwr = -20.0
        surface.blit(ft.render(f"{t}  {freq}MHz", True, C("RF_COLOR")), (4, y))
        surface.blit(ft.render(band, True, C("RF_DIM")), (4, y + 12))
        draw_signal_bars(surface, 180, y + 2, pwr, C("RF_COLOR"))
        y += 28
        if y > SCREEN_H - 10:
            break

def draw_panel_system(surface, fonts, gps, y):
    ft = fonts["tiny"]
    f = fonts["small"]
    surface.blit(f.render("SYSTEM STATUS", True, C("PRIMARY_DIM")), (6, y))
    y += 20

    fix_str = "3D FIX" if gps["fix"] else "NO FIX"
    fix_col = C("GREEN_OK") if gps["fix"] else C("ALERT")
    surface.blit(ft.render(f"GPS      {fix_str}", True, fix_col), (6, y))
    y += 18

    services = [
        ("DUMP1090", "dump1090"),
        ("GPS-SVC",  "gps-service"),
        ("DRONE",    "drone-detector"),
        ("WEB",      "adsb-web"),
    ]
    for label, svc in services:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", svc],
                capture_output=True, text=True, timeout=1
            )
            active = result.stdout.strip() == "active"
        except:
            active = False
        col = C("GREEN_OK") if active else C("ALERT")
        status = "  OK" if active else "FAIL"
        surface.blit(ft.render(f"{label:<10} {status}", True, col), (6, y))
        y += 16

    y += 4
    pygame.draw.line(surface, C("SEPARATOR"), (4, y), (PANEL_W - 8, y), 1)
    y += 8

    try:
        total, used, free = shutil.disk_usage("/")
        pct = used / total * 100
        col = C("ALERT") if pct > 85 else C("GREEN_OK")
        surface.blit(ft.render(f"DISK     {free//1024//1024//1024:.0f}GB free", True, col), (6, y))
        y += 16
        bar_w = PANEL_W - 20
        pygame.draw.rect(surface, C("DARK_GRAY"), (6, y, bar_w, 6))
        pygame.draw.rect(surface, col, (6, y, int(bar_w * pct / 100), 6))
        y += 12
    except:
        pass

    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as tf:
            temp_c = int(tf.read().strip()) / 1000
        col = C("ALERT") if temp_c > 70 else C("GREEN_OK")
        surface.blit(ft.render(f"CPU TEMP {temp_c:.1f}C", True, col), (6, y))
        y += 16
    except:
        pass

    try:
        with open("/proc/uptime") as uf:
            secs = float(uf.read().split()[0])
        h, m = int(secs // 3600), int((secs % 3600) // 60)
        surface.blit(ft.render(f"UPTIME   {h}h {m}m", True, C("PRIMARY_DIM")), (6, y))
        y += 16
    except:
        pass

    surface.blit(ft.render(f"CORR LOG {len(corr_log)} events", True, C("PRIMARY_DIM")), (6, y))

    # ── Fixed-position buttons anchored to bottom of panel ──
    now = time.time()

    # GPS RESET button at fixed y = SCREEN_H - 84
    gps_y = SCREEN_H - 84
    if gps_reset_pending and now - gps_reset_pending_time < 3:
        flash = int(now * 2) % 2 == 0
        col = C("CORR_MED") if flash else C("PRIMARY_DIM")
        pygame.draw.rect(surface, C("PRIMARY_DARK"), (4, gps_y, PANEL_W - 8, 28))
        pygame.draw.rect(surface, col, (4, gps_y, PANEL_W - 8, 28), 2)
        surface.blit(fonts["small"].render("TAP AGAIN TO RESET GPS", True, col), (8, gps_y + 6))
    else:
        pygame.draw.rect(surface, C("DARK_GRAY"), (4, gps_y, PANEL_W - 8, 28))
        pygame.draw.rect(surface, C("PRIMARY_DIM"), (4, gps_y, PANEL_W - 8, 28), 1)
        surface.blit(fonts["small"].render("GPS RESET", True, C("PRIMARY_DIM")), (8, gps_y + 6))

    # SHUTDOWN button at fixed y = SCREEN_H - 48
    shut_y = SCREEN_H - 48
    if shutdown_pending and now - shutdown_pending_time < 3:
        flash = int(now * 2) % 2 == 0
        col = C("ALERT") if flash else C("ALERT_DIM")
        pygame.draw.rect(surface, C("ALERT_DIM"), (4, shut_y, PANEL_W - 8, 28))
        pygame.draw.rect(surface, col, (4, shut_y, PANEL_W - 8, 28), 2)
        surface.blit(fonts["small"].render("TAP AGAIN TO SHUTDOWN", True, col), (8, shut_y + 6))
    else:
        pygame.draw.rect(surface, C("DARK_GRAY"), (4, shut_y, PANEL_W - 8, 28))
        pygame.draw.rect(surface, C("GRAY"), (4, shut_y, PANEL_W - 8, 28), 1)
        surface.blit(fonts["small"].render("SHUTDOWN", True, C("GRAY")), (8, shut_y + 6))

# ─────────────────────────────────────────
# RADAR
# ─────────────────────────────────────────
def draw_radar(surface, fonts, aircraft, gps, frame):
    global selected_hex, rf_flash_timer
    ft = fonts["tiny"]
    f = fonts["small"]

    pygame.draw.rect(surface, C("RADAR_BG"), (RADAR_X, TOP_BAR_H, RADAR_W, RADAR_H))

    cx = RADAR_X + RADAR_W // 2
    cy = TOP_BAR_H + RADAR_H // 2
    radius = min(RADAR_W, RADAR_H) // 2 - 28

    # RF flash ring on new detection
    if rf_flash_timer > 0:
        alpha = int(120 * rf_flash_timer / FPS)
        flash_col = (*C("RF_COLOR")[:3],)
        pygame.draw.circle(surface, flash_col, (cx, cy), radius // 4, 2)
        rf_flash_timer -= 1

    # Range rings — label at 45deg, every other ring
    line_w = 2 if DISPLAY_MODES[display_mode_index] == "FIELD" else 1
    for i, dist_nm in enumerate(RING_NM):
        r = int(radius * dist_nm / MAX_RANGE_NM)
        pygame.draw.circle(surface, C("GRAY"), (cx, cy), r, line_w)
        if i % 2 == 1:
            dist_val, unit = nm_to_unit(dist_nm)
            label = f"{dist_val:.0f}{unit}"
            surf = ft.render(label, True, C("GRAY"))
            angle = math.radians(45)
            lx = cx + int(r * math.sin(angle)) + 3
            ly = cy - int(r * math.cos(angle)) - surf.get_height() - 2
            surface.blit(surf, (lx, ly))

    # Cardinal marks — pushed further out to avoid S overlap
    for angle, label in [(0, "N"), (90, "E"), (180, "S"), (270, "W")]:
        rad = math.radians(angle)
        inner = radius - 10
        outer = radius + 4
        x1 = cx + int(inner * math.sin(rad))
        y1 = cy - int(inner * math.cos(rad))
        x2 = cx + int(outer * math.sin(rad))
        y2 = cy - int(outer * math.cos(rad))
        pygame.draw.line(surface, C("PRIMARY_DIM"), (x1, y1), (x2, y2), 1)
        lsurf = ft.render(label, True, C("PRIMARY_DIM"))
        lx = cx + int((radius + 16) * math.sin(rad))
        ly = cy - int((radius + 16) * math.cos(rad))
        # Offset S label up slightly to clear bottom bar
        if angle == 180:
            ly -= lsurf.get_height()
        surface.blit(lsurf, (lx - lsurf.get_width() // 2, ly - lsurf.get_height() // 2))

    # Outer ring
    pygame.draw.circle(surface, C("PRIMARY_DIM"), (cx, cy), radius, 1)

    # Center crosshair
    pygame.draw.line(surface, C("PRIMARY_DIM"), (cx - 8, cy), (cx + 8, cy), 1)
    pygame.draw.line(surface, C("PRIMARY_DIM"), (cx, cy - 8), (cx, cy + 8), 1)
    pygame.draw.circle(surface, C("PRIMARY"), (cx, cy), 3)

    # Altitude legend
    legend_x = RADAR_X + 6
    legend_y = SCREEN_H - 82
    surface.blit(ft.render("ALT", True, C("GRAY")), (legend_x, legend_y))
    for i, (label, key) in enumerate([("HI >18k", "CONTACT_HI"), ("MID", "CONTACT_MID"), ("LO <5k", "CONTACT_LO")]):
        pygame.draw.circle(surface, C(key), (legend_x + 4, legend_y + 14 + i * 12), 3)
        surface.blit(ft.render(label, True, C(key)), (legend_x + 10, legend_y + 8 + i * 12))
   
    # Bottom labels
    unit_label = f"UNIT [{UNITS[unit_index]}]  RNG {MAX_RANGE_NM}NM"
    surface.blit(ft.render(unit_label, True, C("PRIMARY_DIM")), (RADAR_X + 6, SCREEN_H - 18))
    mode_surf = ft.render(f"[M] {DISPLAY_MODES[display_mode_index]}", True, C("PRIMARY_DIM"))
    surface.blit(mode_surf, (SCREEN_W - mode_surf.get_width() - 6, SCREEN_H - 18))

    if not gps["fix"]:
        msg = f.render("NO GPS FIX", True, C("PRIMARY_DIM"))
        surface.blit(msg, (cx - msg.get_width() // 2, cy + radius + 8))
        return

    now = time.time()
    for ac in aircraft:
        if "lat" not in ac or "lon" not in ac:
            continue
        x, y, dist_nm, brg = lat_lon_to_radar(
            ac["lat"], ac["lon"],
            gps["lat"], gps["lon"],
            cx, cy, radius
        )
        if dist_nm > MAX_RANGE_NM:
            continue

        ix, iy = int(x), int(y)
        hex_id = ac.get("hex", "")
        alt = ac.get("alt_baro", ac.get("alt_geom", None))
        is_sel = hex_id == selected_hex

        ingest_radar_event(hex_id, ac["lat"], ac["lon"])

        # Track history
        if hex_id not in track_history:
            track_history[hex_id] = deque(maxlen=TRACK_HISTORY)
        track_history[hex_id].append((ix, iy))
        track = list(track_history[hex_id])
        if len(track) > 1:
            for ti in range(1, len(track)):
                alpha_frac = ti / len(track)
                base = C("CONTACT_DIM")
                col = tuple(int(c * alpha_frac * 0.6) for c in base)
                pygame.draw.line(surface, col, track[ti-1], track[ti], 1)

        # Speed vector
        spd = ac.get("gs", None)
        hdg = ac.get("track", None)
        if spd and hdg:
            spd_nm_per_sec = spd / 3600
            vec_nm = spd_nm_per_sec * SPEED_VECTOR_SECS
            vec_r = (vec_nm / MAX_RANGE_NM) * radius
            vrad = math.radians(hdg)
            vx = ix + int(vec_r * math.sin(vrad))
            vy = iy - int(vec_r * math.cos(vrad))
            pygame.draw.line(surface, C("CONTACT_DIM"), (ix, iy), (vx, vy), 1)

        # Contact dot
        dot_color = altitude_color(alt)
        dot_size = 5 if is_sel else 4
        pygame.draw.circle(surface, dot_color, (ix, iy), dot_size)
        if is_sel:
            pygame.draw.circle(surface, C("PRIMARY"), (ix, iy), dot_size + 4, 1)

        # Callsign
        ident = ac.get("flight", hex_id).strip()
        if ident:
            label_col = C("PRIMARY") if is_sel else C("CONTACT_DIM")
            surface.blit(ft.render(ident, True, label_col), (ix + 7, iy - 5))

# ─────────────────────────────────────────
# INPUT
# ─────────────────────────────────────────
long_press_start = None
long_press_pos = None
LONG_PRESS_MS = 800

def finger_to_surface(fx, fy):
    """Convert normalized FINGERDOWN coords (0-1) to logical surface pixel coords.
    The surface is rendered at 800x480, rotated 90° CCW, then scaled to 720x1280.
    This reverses that transform so touch coords map correctly to surface space.
    """
    mx = int((1.0 - fy) * SCREEN_W)
    my = int(fx * SCREEN_H)
    return mx, my

def handle_click(mx, my, aircraft, gps):
    """Handle a click/touch at logical surface coordinates (mx, my)."""
    global unit_index, display_mode_index, panel_view_index
    global selected_hex, MAX_RANGE_NM, long_press_start, long_press_pos
    global shutdown_pending, shutdown_pending_time
    global gps_reset_pending, gps_reset_pending_time

    cx = RADAR_X + RADAR_W // 2
    cy = TOP_BAR_H + RADAR_H // 2
    radius = min(RADAR_W, RADAR_H) // 2 - 28

    if panel_view_index == PANEL_VIEWS.index("SYSTEM") and 0 < mx < PANEL_W:
        now = time.time()

        # GPS RESET button hit area
        if SCREEN_H - 84 < my < SCREEN_H - 56:
            if gps_reset_pending and now - gps_reset_pending_time < 3:
                subprocess.run(["sudo", "systemctl", "restart", "gps-service"])
                gps_reset_pending = False
            else:
                gps_reset_pending = True
                gps_reset_pending_time = now
            shutdown_pending = False
            return

        # SHUTDOWN button hit area
        if SCREEN_H - 48 < my < SCREEN_H - 20:
            if shutdown_pending and now - shutdown_pending_time < 3:
                subprocess.run(["sudo", "shutdown", "now"])
            else:
                shutdown_pending = True
                shutdown_pending_time = now
            gps_reset_pending = False
            return

    # Reset pending states if tapping elsewhere
    shutdown_pending = False
    gps_reset_pending = False

    if RADAR_X < mx < RADAR_X + 160 and SCREEN_H - 28 < my < SCREEN_H:
        unit_index = (unit_index + 1) % len(UNITS)
    elif SCREEN_W - 120 < mx < SCREEN_W and SCREEN_H - 28 < my < SCREEN_H:
        display_mode_index = (display_mode_index + 1) % len(DISPLAY_MODES)
    elif 0 < mx < PANEL_W and TOP_BAR_H < my < TOP_BAR_H + 24:
        tab_w = PANEL_W // len(PANEL_VIEWS)
        panel_view_index = min(mx // tab_w, len(PANEL_VIEWS) - 1)
    elif mx > RADAR_X and gps["fix"]:
        best_hex = None
        best_dist = 20
        for ac in aircraft:
            if "lat" not in ac or "lon" not in ac:
                continue
            x, y, dist_nm, _ = lat_lon_to_radar(
                ac["lat"], ac["lon"],
                gps["lat"], gps["lon"],
                cx, cy, radius
            )
            sd = math.sqrt((mx - x)**2 + (my - y)**2)
            if sd < best_dist:
                best_dist = sd
                best_hex = ac.get("hex")
        selected_hex = best_hex
        if best_hex:
            panel_view_index = PANEL_VIEWS.index("CONTACTS")
    long_press_start = pygame.time.get_ticks()
    long_press_pos = (mx, my)

def handle_events(events, aircraft, gps):
    global unit_index, display_mode_index, panel_view_index
    global selected_hex, MAX_RANGE_NM
    global long_press_start, long_press_pos

    cx = RADAR_X + RADAR_W // 2
    cy = TOP_BAR_H + RADAR_H // 2
    radius = min(RADAR_W, RADAR_H) // 2 - 28

    for event in events:
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_q:
                return False
            if event.key == pygame.K_u:
                unit_index = (unit_index + 1) % len(UNITS)
            if event.key == pygame.K_m:
                display_mode_index = (display_mode_index + 1) % len(DISPLAY_MODES)
            if event.key == pygame.K_LEFT:
                panel_view_index = (panel_view_index - 1) % len(PANEL_VIEWS)
            if event.key == pygame.K_RIGHT:
                panel_view_index = (panel_view_index + 1) % len(PANEL_VIEWS)
            if event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                MAX_RANGE_NM = max(10, MAX_RANGE_NM - 5)
            if event.key == pygame.K_MINUS:
                MAX_RANGE_NM = min(100, MAX_RANGE_NM + 5)
            if event.key == pygame.K_r:
                MAX_RANGE_NM = 50

        # Mouse click (desktop/testing)
        if event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos
            handle_click(mx, my, aircraft, gps)

        if event.type == pygame.MOUSEBUTTONUP:
            long_press_start = None

        # Touchscreen finger events
        if event.type == pygame.FINGERDOWN:
            mx, my = finger_to_surface(event.x, event.y)
            handle_click(mx, my, aircraft, gps)

        if event.type == pygame.FINGERUP:
            long_press_start = None

    if long_press_start:
        held = pygame.time.get_ticks() - long_press_start
        if held > LONG_PRESS_MS and long_press_pos[0] > RADAR_X:
            MAX_RANGE_NM = 50
            long_press_start = None

    return True

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    global heartbeat

    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    surface = pygame.Surface((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("ADS-B Tracker")
    clock = pygame.time.Clock()

    fonts = {
        "small": pygame.font.SysFont("monospace", 15, bold=True),
        "tiny":  pygame.font.SysFont("monospace", 12),
    }

    load_corr_log()

    # Boot screen
    boot_start = time.time()
    while time.time() - boot_start < BOOT_DURATION:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
        progress = (time.time() - boot_start) / BOOT_DURATION
        draw_boot_screen(surface, fonts, progress)
        rotated = pygame.transform.rotate(surface, 90)
        scaled = pygame.transform.scale(rotated, (720, 1280))
        screen.blit(scaled, (0, 0))
        pygame.display.flip()
        clock.tick(FPS)

    # Start fetch thread after boot
    t = threading.Thread(target=fetch_loop, daemon=True)
    t.start()

    hb_timer = 0
    frame = 0
    running = True

    while running:
        events = pygame.event.get()
        with data_lock:
            ac = list(aircraft_data)
            dr = list(drone_data)
            gps = dict(gps_data)

        running = handle_events(events, ac, gps)

        hb_timer += 1
        if hb_timer >= FPS:
            heartbeat = not heartbeat
            hb_timer = 0

        surface.fill(C("BG"))
        draw_top_bar(surface, fonts, gps, heartbeat)
        draw_panel(surface, fonts, ac, dr, gps)
        draw_radar(surface, fonts, ac, gps, frame)
        rotated = pygame.transform.rotate(surface, 90)
        scaled = pygame.transform.scale(rotated, (720, 1280))
        screen.blit(scaled, (0, 0))
        pygame.display.flip()
        clock.tick(FPS)
        frame += 1

    pygame.quit()

if __name__ == "__main__":
    main()
