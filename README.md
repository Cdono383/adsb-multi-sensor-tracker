# ADS-B Multi-Sensor Tracker with Drone Detection Web UI

A portable, battery-powered, fully offline multi-sensor aircraft and drone detection system built on a Raspberry Pi Zero 2W. Tracks ADS-B aircraft, monitors 433 MHz and 915 MHz RF bands for drone activity, correlates detections across sensors, and displays everything on a live web interface with offline OpenStreetMap tiles.

Built as V1 of an ongoing hardware/software project. V2 will feature a Raspberry Pi 4, 7" DSI touchscreen with a custom pygame radar display, Pelican hard case, and UPS HAT for field deployment.

![Web UI Screenshot](images/webui.png)

---

## Features

- **ADS-B Aircraft Tracking** — Real-time aircraft reception via RTL-SDR Blog V4 dongle and dump1090-fa
- **Drone Detection** — Simultaneous scanning of 433 MHz and 915 MHz bands for drone/RC control link activity
- **RF Correlation Engine** — Automatically correlates RF bursts with radar contacts and logs events with confidence scores
- **Live Web UI** — SkyAware-based map with offline OSM tiles, live GPS position, range rings, and a drone detection overlay panel
- **GPS Integration** — u-blox NEO-6M provides live position via custom Flask API
- **Fully Offline** — No internet required. All tiles, data, and services run locally on the Pi
- **Field Ready** — Auto-connects to known WiFi networks, falls back to hotspot mode, accessible via `adsb-tracker.local` using mDNS
- **Auto-start** — All services managed by systemd, start on boot automatically

---

## Hardware

| Component | Details |
|---|---|
| Raspberry Pi Zero 2W | Main compute |
| RTL-SDR Blog V4 (x3) | SDR dongles (SN: 00000001, 00000002, 00000003) |
| 1090 MHz ADS-B Antenna | Aircraft tracking |
| 433 MHz Antenna | Drone/RC detection |
| 915 MHz Antenna | Drone/RC detection |
| u-blox NEO-6M GPS | Soldered directly to GPIO (UART) |
| USB OTG Hub | Connects all three dongles |
| 10,000 mAh Power Bank | Battery power |
| 64GB A2 microSD | Storage |

---

## Software Stack

| Component | Purpose |
|---|---|
| Debian Trixie (arm64) | OS |
| dump1090-fa (source build) | ADS-B decoder |
| rtl-sdr | SDR driver |
| Flask + flask-cors | GPS and drone detection API |
| Python HTTP Server | Web UI host |
| OpenLayers (SkyAware) | Web map interface |
| OpenStreetMap raster tiles | Offline map tiles |
| systemd | Service management |
| avahi-daemon | mDNS (`adsb-tracker.local`) |

---

## System Architecture

┌─────────────────────────────────────────────────────┐
│                  Raspberry Pi Zero 2W                │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ Dongle 1 │  │ Dongle 2 │  │ Dongle 3 │          │
│  │ 1090 MHz │  │ 433  MHz │  │ 915  MHz │          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
│       │              │              │                │
│  ┌────▼─────┐  ┌─────▼──────────────▼────┐         │
│  │ dump1090 │  │     drone_detector.py    │         │
│  │ :30005   │  │     rtl_power scanner    │         │
│  └────┬─────┘  └─────────────┬────────────┘         │
│       │                       │                     │
│  ┌────▼───────────────────────▼────────────────┐    │
│  │              gps_service.py (Flask :5001)   │    │
│  │   /api/location   /api/drone_detections     │    │
│  └────────────────────────────┬────────────────┘    │
│                                │                    │
│  ┌─────────────────────────────▼──────────────┐     │
│  │         Python HTTP Server (:8080)          │     │
│  │         SkyAware Web UI + OSM Tiles         │     │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌──────────────┐                                   │
│  │ u-blox NEO-6M│ → UART /dev/ttyS0                │
│  └──────────────┘                                   │
└─────────────────────────────────────────────────────┘


---

## Services

All four services are managed by systemd and start automatically on boot:

| Service | Description | Port |
|---|---|---|
| `dump1090` | ADS-B receiver and decoder | 30005 |
| `gps-service` | GPS NMEA parser and REST API | 5001 |
| `drone-detector` | 433/915 MHz RF scanner | — |
| `adsb-web` | Web UI file server | 8080 |

Check status:
```bash
sudo systemctl status dump1090 gps-service drone-detector adsb-web
```

---

## Web UI

Access the web interface from any device on the same network:

 http://adsb-tracker.local:8080


The drone detection panel appears in the bottom-left corner of the map and updates every 10 seconds with live RF detections.

---

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/location` | Current GPS position `{lat, lon, alt, fix}` |
| `GET /api/drone_detections` | Last 50 RF detections `[{time, band, freq, power}]` |

---

## Installation

### Prerequisites

- Raspberry Pi Zero 2W with Debian Trixie
- Three RTL-SDR Blog V4 dongles
- RTL-SDR kernel module blacklisted

Blacklist the kernel module:
```bash
echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/blacklist-rtl.conf
```

### Build dump1090 from source

```bash
sudo apt install -y git cmake libusb-1.0-0-dev
git clone https://github.com/flightaware/dump1090
cd dump1090
cmake . && make
sudo make install
```

### Install dependencies

```bash
sudo apt install -y python3-flask python3-serial rtl-sdr screen avahi-daemon
sudo pip3 install flask-cors --break-system-packages
```

### Clone this repository

```bash
git clone https://github.com/Cdono383/adsb-multi-sensor-tracker.git
cd adsb-multi-sensor-tracker
```

### Configure

Edit `src/gps_service.py` and update the serial port if needed (default `/dev/ttyS0`).

Edit `dump1090.service` and update `--lat` and `--lon` with your location.

### Install services

```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dump1090 gps-service drone-detector adsb-web
sudo systemctl start dump1090 gps-service drone-detector adsb-web
```

### Download offline map tiles

```bash
python3 src/download_tiles.py
```

---

## Field Use

The Pi automatically connects to known WiFi networks. Away from home networks it falls back to a hotspot:

- **SSID:** `adsb-tracker`
- **Password:** `adsbtracker123`
- **SSH:** `ssh pi@10.0.0.1`
- **Web UI:** `http://10.0.0.1:8080`

On a shared network use mDNS:
```bash
ssh pi@adsb-tracker.local
```

---

## Dongle Assignment

| Serial | Band | Purpose |
|---|---|---|
| 00000001 | 1090 MHz | ADS-B aircraft tracking |
| 00000002 | 433 MHz | Drone/RC control link detection |
| 00000003 | 915 MHz | Drone/LoRa detection |

---

## RF Correlation Engine

The drone detector maintains a rolling 60-second timeline of RF events and radar contacts. When an RF burst and a new radar contact appear within 10 seconds of each other, the system logs a correlation event with a confidence score.

Correlation log saved to: `/home/pi/correlation_log.json`

---

## Roadmap

### V1 (Current) ✅
- Raspberry Pi Zero 2W
- Three RTL-SDR dongles
- Web UI with drone detection panel
- GPS integration
- RF correlation engine
- Offline map tiles

### V2 (In Progress)
- Raspberry Pi 4
- 7" DSI touchscreen
- Custom pygame radar display (STANDARD / FIELD / NIGHT modes)
- Pelican hard case with SMA bulkhead connectors
- UPS HAT for clean field power management
- External GPS antenna

### V3 (Planned)
- Compact Linux handheld platform (GPD MicroPC / Clockwork Pi uConsole)
- Fully integrated portable unit

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Author

**Casey** — [@Cdono383](https://github.com/Cdono383)

Built through iterative hardware/software development as a learning project combining SDR, embedded Linux, RF signal processing, and web development.