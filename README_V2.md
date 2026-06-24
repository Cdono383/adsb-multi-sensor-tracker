# ADS-B Multi-Sensor Tracker — V2

## Overview

V2 is a fully portable, self-contained RF surveillance and aircraft tracking unit. It requires no internet connection, no external infrastructure, and no fixed installation — open the case, power it on, and it's operational within 30 seconds.

The system is designed to build passive situational awareness of the surrounding airspace and RF environment by receiving and decoding signals that are already being broadcast. Nothing is transmitted. Everything the system knows comes from listening.

---

## What It Does

- **ADS-B Aircraft Tracking** — Receives and decodes 1090 MHz ADS-B transmissions and plots aircraft positions on a range ring display centered on your current GPS coordinates. Contact list shows callsign, altitude, speed, bearing, and range in real time.
- **Drone Detection** — Passively monitors 433 MHz and 915 MHz bands for RF activity consistent with drone control signals. Detections are logged and displayed with signal strength.
- **RF Correlation Engine** — Automatically correlates RF detections with nearby ADS-B contacts and flags potential associations with a confidence score. Alerts are displayed on screen in real time.
- **GPS Positioning** — NEO-6M GPS module provides live position fix. All range and bearing calculations are relative to your current location.
- **Three Display Modes** — STANDARD, FIELD, and NIGHT modes optimized for different lighting conditions.
- **System Status Panel** — Real-time service health, CPU temperature, disk usage, uptime, and correlation event count.

---

## Hardware

| Component | Details |
|---|---|
| Compute | Raspberry Pi 4 (1GB RAM) |
| OS | Debian Trixie arm64 |
| Display | 7" DSI Touchscreen (720×1280) |
| SDR Dongles | RTL-SDR Blog V4 ×3 (SNs 00000001/00000002/00000003) |
| GPS | u-blox NEO-6M with active patch antenna |
| Power | Waveshare UPS HAT (B) with 18650 cells |
| Case | Pelican 1150 |
| Cooling | Aluminum heatsink |

**SDR Dongle Assignment:**
- `00000001` → 1090 MHz (ADS-B)
- `00000002` → 433 MHz (Drone detection)
- `00000003` → 915 MHz (Drone detection)

---

## Software Stack

- **dump1090** — Built from source (FlightAware fork) against osmocom librtlsdr
- **gps_service.py** — Flask API serving live GPS position from NEO-6M via UART (`/dev/ttyS0`)
- **drone_detector.py** — rtl_power scanner across 433 MHz and 915 MHz bands, logs detections and serves via API
- **display.py** — pygame-based radar display with touch input, RF correlation engine, and multi-mode rendering
- **adsb-web** — Lightweight HTTP server for optional web UI access

All four components run as systemd services and start automatically on boot.

---

## Display Controls

| Action | Function |
|---|---|
| Tap panel tabs | Switch between CONTACTS / RF ACTIVITY / SYSTEM |
| Tap radar contact | Select and display contact details |
| Tap UNIT label | Cycle distance units (NM / MI / KM) |
| Tap MODE label | Cycle display modes (STANDARD / FIELD / NIGHT) |
| Long press radar | Reset range to 50NM |
| SYSTEM → GPS RESET | Restart GPS service (tap, then confirm within 3 seconds) |
| SYSTEM → SHUTDOWN | Safe system shutdown (tap, then confirm within 3 seconds) |

---

## Known Issues / Lessons Learned

- **GPS Fix Delay** — The NEO-6M can take several minutes to acquire a fix after a cold start, particularly indoors. A GPS RESET button is included in the SYSTEM panel to restart the service if the module gets into a stuck state. Two-tap confirmation required to prevent accidental reset.
- **Display Glare** — The touchscreen glass reflects significantly in direct sunlight. FIELD and NIGHT modes improve contrast but glare remains a limitation of the current form factor. Addressed in V3 planning.
- **Soft Reboot** — The DSI display requires a 25-second initialization delay after a soft reboot before pygame can claim the framebuffer. Power cycling is more reliable for a clean restart. A startup delay in `.bash_profile` mitigates this.
- **librtlsdr Compatibility** — The Debian Trixie packaged librtlsdr (RTL-SDR Blog fork v2.0.2) is not compatible with dump1090-fa. Solution was to build osmocom librtlsdr from source and rebuild dump1090 against it.
- **pygame Framebuffer** — pygame must be installed from apt (not pip) to get framebuffer/KMS support on Debian. The pip wheel is a generic Linux build without display driver support.

---

## Field Test Results

- **Location:** Massachusetts, USA
- **Aircraft contacts:** Up to 17 simultaneous contacts observed
- **GPS fix:** Consistent 3D fix acquired outdoors within 2-3 minutes
- **RF activity:** Active 433 MHz detections with correlation alerts firing at 96%+ confidence
- **CPU temperature:** Stable at 57-62°C with heatsink installed
- **Display modes:** All three modes tested in field conditions

---

## V3 Planning — Mobile Listening Post v1

V3 shifts concept from a dedicated ADS-B tracker to a portable passive RF recon node. The goal is a consolidated, focused listening platform rather than an expanded version of V2.

**Architecture:**
- Raspberry Pi 4 with two RTL-SDR Blog V4 dongles
- Chain A: Fixed small 1090 MHz antenna — always-on ADS-B reception
- Chain B: Single compact wideband VHF/UHF antenna on its own bulkhead — web UI selectable decoder (APRS, ACARS, or other targets)
- GL.iNet Mango travel router for connectivity — allows a Toughpad, laptop, or any device to connect and access the web UI without relying on existing infrastructure
- Target runtime: 3 hours minimum on internal battery
- Ventilated rugged enclosure (Pelican case)
- Switched antenna bank — wired for but deferred to v2 of this platform
