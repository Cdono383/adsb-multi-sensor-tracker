#!/usr/bin/env python3
import pygame
import math
import time
import json
import urllib.request
import threading
from datetime import datetime, timezone

# --- Config ---
SCREEN_W, SCREEN_H = 800, 480
FPS = 30
TOP_BAR_H = 36
PANEL_W = 260
RADAR_X = PANEL_W
RADAR_W = SCREEN_W - PANEL_W
RADAR_H = SCREEN_H - TOP_BAR_H
MAX_RANGE_NM = 50

# --- Amber phosphor palette ---
BG          = (6, 8, 6)
RADAR_BG    = (4, 10, 4)
AMBER       = (210, 140, 0)
AMBER_DIM   = (120, 80, 0)
AMBER_DARK  = (40, 26, 0)
WHITE       = (220, 220, 210)
GRAY        = (55, 55, 50)
DARK_GRAY   = (20, 20, 18)
CONTACT     = (180, 220, 255)
CONTACT_DIM = (80, 110, 140)
RF_COLOR    = (200, 120, 30)
RF_DIM      = (100, 60, 15)
SEPARATOR   = (40, 40, 35)
GREEN_DIM   = (0, 80, 30)

# --- Units ---
UNITS = ["NM", "MI", "KM"]
UNIT_INDEX = 0
UNIT_FACTORS = {"NM": 1.0, "MI": 1.15078, "KM": 1.852}
RING_DISTANCES_NM = [10, 20, 30, 40, 50]

# --- Shared state ---
aircraft_data = []
drone_data = []
gps_data = {"lat": 0.0, "lon": 0.0, "alt": 0.0, "fix": False}
heartbeat = True

def fetch_loop():
    global aircraft_data, drone_data, gps_data
    while True:
        try:
            with open("/run/dump1090/aircraft.json") as f:
                aircraft_data = json.load(f).get("aircraft", [])
        except:
            pass
        try:
            with urllib.request.urlopen("http://localhost:5001/api/location", timeout=2) as r:
                gps_data = json.loads(r.read())
        except:
            pass
        try:
            with urllib.request.urlopen("http://localhost:5001/api/drone_detections", timeout=2) as r:
                drone_data = json.loads(r.read())[-8:]
        except:
            pass
        time.sleep(2)

def nm_to_unit(nm):
    unit = UNITS[UNIT_INDEX]
    return nm * UNIT_FACTORS[unit], unit

def lat_lon_to_radar(lat, lon, clat, clon, cx, cy, radius):
    dlat = lat - clat
    dlon = lon - clon
    dist_nm = math.sqrt((dlat * 60) ** 2 + (dlon * 60 * math.cos(math.radians(clat))) ** 2)
    bearing = math.atan2(dlon * math.cos(math.radians(clat)), dlat)
    r = (dist_nm / MAX_RANGE_NM) * radius
    x = cx + r * math.sin(bearing)
    y = cy - r * math.cos(bearing)
    return x, y, dist_nm

def draw_signal_bars(surface, x, y, power_db, color):
    # Convert dB to 0-5 bar scale (-15dB = 1 bar, 0dB+ = 5 bars)
    bars = max(1, min(5, int((power_db + 20) / 4) + 1))
    for i in range(5):
        c = color if i < bars else DARK_GRAY
        pygame.draw.rect(surface, c, (x + i * 6, y - i * 2, 4, 8 + i * 2))

def draw_top_bar(surface, fonts, gps, hb):
    pygame.draw.rect(surface, DARK_GRAY, (0, 0, SCREEN_W, TOP_BAR_H))
    pygame.draw.line(surface, SEPARATOR, (0, TOP_BAR_H - 1), (SCREEN_W, TOP_BAR_H - 1), 1)

    f = fonts["small"]

    if gps["fix"]:
        lat_str = f"LAT  {gps['lat']:>10.5f}"
        lon_str = f"LON  {gps['lon']:>10.5f}"
        alt_str = f"ALT  {gps['alt']:.0f}m"
        coord_color = AMBER
    else:
        lat_str = "LAT  --"
        lon_str = "LON  --"
        alt_str = "ALT  --"
        coord_color = AMBER_DIM

    surface.blit(f.render(lat_str, True, coord_color), (10, 10))
    surface.blit(f.render(lon_str, True, coord_color), (175, 10))
    surface.blit(f.render(alt_str, True, coord_color), (340, 10))

    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    time_surf = f.render(now, True, WHITE)
    surface.blit(time_surf, (SCREEN_W // 2 + 60, 10))

    # Heartbeat
    hb_color = AMBER if hb else AMBER_DARK
    pygame.draw.circle(surface, hb_color, (SCREEN_W - 16, TOP_BAR_H // 2), 5)
    pygame.draw.circle(surface, AMBER_DIM, (SCREEN_W - 16, TOP_BAR_H // 2), 5, 1)

def draw_panel(surface, fonts, aircraft, drones):
    pygame.draw.rect(surface, BG, (0, TOP_BAR_H, PANEL_W, SCREEN_H - TOP_BAR_H))
    pygame.draw.line(surface, SEPARATOR, (PANEL_W - 1, TOP_BAR_H), (PANEL_W - 1, SCREEN_H), 1)

    f = fonts["small"]
    ft = fonts["tiny"]
    y = TOP_BAR_H + 10

    # Contacts header
    ac_with_pos = len([a for a in aircraft if "lat" in a and "lon" in a])
    header = f"── CONTACTS  {len(aircraft):02d} / POS {ac_with_pos:02d} ──"
    surface.blit(f.render(header, True, AMBER_DIM), (8, y))
    y += 20

    for ac in aircraft[:9]:
        ident = ac.get("flight", ac.get("hex", "??????")).strip() or ac.get("hex", "??????")
        alt = ac.get("alt_baro", ac.get("alt_geom", None))
        spd = ac.get("gs", None)
        alt_str = f"{int(alt):>6,}" if isinstance(alt, (int, float)) else "      "
        spd_str = f"{int(spd):>3}kt" if isinstance(spd, (int, float)) else "   --"
        has_pos = "lat" in ac and "lon" in ac
        color = CONTACT if has_pos else CONTACT_DIM
        surface.blit(ft.render(f"{ident:<8} {alt_str}ft {spd_str}", True, color), (8, y))
        y += 16

    y += 6
    pygame.draw.line(surface, SEPARATOR, (8, y), (PANEL_W - 8, y), 1)
    y += 8

    # RF Activity header
    surface.blit(f.render("── RF ACTIVITY ──", True, AMBER_DIM), (8, y))
    y += 20

    for d in drones[-7:]:
        t = d.get("time", "")[-8:]
        freq = d.get("freq", "").replace(" MHz", "")
        pwr_str = d.get("power", "0 dB").replace(" dB", "")
        try:
            pwr = float(pwr_str)
        except:
            pwr = -20.0
        surface.blit(ft.render(f"{t}  {freq} MHz", True, RF_COLOR), (8, y))
        draw_signal_bars(surface, 190, y + 2, pwr, RF_COLOR)
        y += 16

def draw_radar(surface, fonts, aircraft, gps):
    global UNIT_INDEX
    f = fonts["small"]
    ft = fonts["tiny"]

    rx = RADAR_X
    ry = TOP_BAR_H
    rw = RADAR_W
    rh = RADAR_H

    pygame.draw.rect(surface, RADAR_BG, (rx, ry, rw, rh))

    cx = rx + rw // 2
    cy = ry + rh // 2
    radius = min(rw, rh) // 2 - 24

    # Range rings
    for dist_nm in RING_DISTANCES_NM:
        r = int(radius * dist_nm / MAX_RANGE_NM)
        pygame.draw.circle(surface, GRAY, (cx, cy), r, 1)
        dist_val, unit = nm_to_unit(dist_nm)
        label = f"{dist_val:.0f}"
        surf = ft.render(label, True, GRAY)
        surface.blit(surf, (cx + r + 2, cy - 7))

    # Cardinal bearing marks
    for angle, label in [(0, "N"), (90, "E"), (180, "S"), (270, "W")]:
        rad = math.radians(angle)
        x1 = cx + int((radius - 8) * math.sin(rad))
        y1 = cy - int((radius - 8) * math.cos(rad))
        x2 = cx + int((radius + 4) * math.sin(rad))
        y2 = cy - int((radius + 4) * math.cos(rad))
        pygame.draw.line(surface, AMBER_DIM, (x1, y1), (x2, y2), 1)
        lx = cx + int((radius + 14) * math.sin(rad))
        ly = cy - int((radius + 14) * math.cos(rad))
        surf = ft.render(label, True, AMBER_DIM)
        surface.blit(surf, (lx - surf.get_width() // 2, ly - surf.get_height() // 2))

    # Outer ring
    pygame.draw.circle(surface, AMBER_DIM, (cx, cy), radius, 1)

    # Center cross
    pygame.draw.line(surface, AMBER_DIM, (cx - 6, cy), (cx + 6, cy), 1)
    pygame.draw.line(surface, AMBER_DIM, (cx, cy - 6), (cx, cy + 6), 1)
    pygame.draw.circle(surface, AMBER, (cx, cy), 3)

    # Unit toggle
    unit_label = f"UNIT  [{UNITS[UNIT_INDEX]}]"
    u_surf = ft.render(unit_label, True, AMBER_DIM)
    surface.blit(u_surf, (rx + 6, SCREEN_H - 20))

    # No fix indicator
    if not gps["fix"]:
        msg = ft.render("NO GPS FIX", True, AMBER_DIM)
        surface.blit(msg, (cx - msg.get_width() // 2, cy + radius + 6))
        return

    # Aircraft
    for ac in aircraft:
        if "lat" not in ac or "lon" not in ac:
            continue
        x, y, dist_nm = lat_lon_to_radar(
            ac["lat"], ac["lon"],
            gps["lat"], gps["lon"],
            cx, cy, radius
        )
        if dist_nm > MAX_RANGE_NM:
            continue
        ix, iy = int(x), int(y)
        pygame.draw.circle(surface, CONTACT, (ix, iy), 4)
        pygame.draw.circle(surface, CONTACT_DIM, (ix, iy), 4, 1)
        ident = ac.get("flight", ac.get("hex", "")).strip()
        if ident:
            surface.blit(ft.render(ident, True, CONTACT_DIM), (ix + 7, iy - 5))

def main():
    global heartbeat, UNIT_INDEX

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("ADS-B Tracker")
    clock = pygame.time.Clock()

    fonts = {
        "small": pygame.font.SysFont("monospace", 15, bold=True),
        "tiny":  pygame.font.SysFont("monospace", 12),
    }

    t = threading.Thread(target=fetch_loop, daemon=True)
    t.start()

    hb_timer = 0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if RADAR_X < mx < RADAR_X + 100 and SCREEN_H - 30 < my < SCREEN_H:
                    UNIT_INDEX = (UNIT_INDEX + 1) % len(UNITS)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    pygame.quit()
                    return
                if event.key == pygame.K_u:
                    UNIT_INDEX = (UNIT_INDEX + 1) % len(UNITS)

        hb_timer += 1
        if hb_timer >= FPS:
            heartbeat = not heartbeat
            hb_timer = 0

        screen.fill(BG)
        draw_top_bar(screen, fonts, gps_data, heartbeat)
        draw_panel(screen, fonts, aircraft_data, drone_data)
        draw_radar(screen, fonts, aircraft_data, gps_data)

        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__":
    main()