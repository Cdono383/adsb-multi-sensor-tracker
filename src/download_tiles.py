import os
import urllib.request
import math
import time

def deg2num(lat, lon, zoom):
    lat_r = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(lat_r) + 1/math.cos(lat_r)) / math.pi) / 2 * n)
    return x, y

tile_dir = "/home/pi/dump1090/public_html/tiles"
os.makedirs(tile_dir, exist_ok=True)

regions = [
    # (name, min_lat, max_lat, min_lon, max_lon, min_zoom, max_zoom)
    ("North America low detail",  15.0,  72.0, -170.0,  -50.0, 1,  7),
    ("North America medium",      24.0,  60.0, -130.0,  -60.0, 8,  9),
    ("Northeast US + E. Canada",  40.0,  50.0,  -80.0,  -60.0, 10, 11),
    ("New England high detail",   41.0,  47.5,  -73.5,  -66.5, 12, 14),
]

total_downloaded = 0

for name, min_lat, max_lat, min_lon, max_lon, z_min, z_max in regions:
    print(f"\nDownloading: {name} (zoom {z_min}-{z_max})")
    for zoom in range(z_min, z_max + 1):
        x1, y1 = deg2num(max_lat, min_lon, zoom)
        x2, y2 = deg2num(min_lat, max_lon, zoom)
        total = (x2 - x1 + 1) * (y2 - y1 + 1)
        print(f"  Zoom {zoom}: {total} tiles")
        count = 0
        for x in range(x1, x2 + 1):
            for y in range(y1, y2 + 1):
                path = f"{tile_dir}/{zoom}/{x}"
                os.makedirs(path, exist_ok=True)
                dest = f"{path}/{y}.png"
                if not os.path.exists(dest):
                    url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
                    try:
                        req = urllib.request.Request(url, headers={'User-Agent': 'ADS-B-Tracker/1.0'})
                        with urllib.request.urlopen(req, timeout=10) as r, open(dest, 'wb') as f:
                            f.write(r.read())
                        total_downloaded += 1
                        time.sleep(0.05)
                    except:
                        pass
                count += 1
            if count % 100 == 0:
                print(f"    {count}/{total} processed...")

print(f"\nDone. {total_downloaded} new tiles downloaded.")
