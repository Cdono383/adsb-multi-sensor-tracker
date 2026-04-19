#!/usr/bin/env python3
import subprocess
import csv
import time
import threading
import os
from datetime import datetime

DONGLES = {
    "433MHz": {"serial": "00000002", "freq_start": "433.05M", "freq_end": "434.79M", "step": "10k"},
    "915MHz": {"serial": "00000003", "freq_start": "902M", "freq_end": "928M", "step": "25k"},
}

THRESHOLD_DB = -10.0
LOG_FILE = "/home/pi/drone_detections.log"

def log_detection(band, freq_mhz, power_db):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} | {band} | {freq_mhz:.3f} MHz | {power_db:.1f} dB"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def scan_band(name, config):
    outfile = f"/tmp/scan_{name}.csv"
    last_mtime = 0
    while True:
        cmd = [
            "rtl_power",
            "-d", config["serial"],
            "-f", f"{config['freq_start']}:{config['freq_end']}:{config['step']}",
            "-g", "40", "-i", "1", "-e", "3", outfile
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            mtime = os.path.getmtime(outfile)
            if mtime == last_mtime:
                continue
            last_mtime = mtime
            best = {}
            with open(outfile, "r") as f:
                for row in csv.reader(f):
                    if len(row) < 7:
                        continue
                    freq_low = float(row[2])
                    freq_step = float(row[4])
                    for i, pwr in enumerate(float(x) for x in row[6:]):
                        if pwr > THRESHOLD_DB:
                            freq_mhz = round((freq_low + i * freq_step) / 1e6, 3)
                            if freq_mhz not in best or pwr > best[freq_mhz]:
                                best[freq_mhz] = pwr
            for freq_mhz, pwr in sorted(best.items()):
                log_detection(name, freq_mhz, pwr)
        except Exception:
            pass
        time.sleep(6)

print("Drone detector starting...")
for name, config in DONGLES.items():
    t = threading.Thread(target=scan_band, args=(name, config), daemon=True)
    t.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopped.")
