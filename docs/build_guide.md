# V1 Build Guide

## Overview
This guide covers the physical build of V1 — a portable ADS-B and drone detection system built around a Raspberry Pi Zero 2W.

## Components
- Raspberry Pi Zero 2W
- 3x RTL-SDR Blog V4 dongles
- USB OTG hub
- u-blox NEO-6M GPS module (GY-GPS6MV2)
- 1090 MHz ADS-B antenna
- 433 MHz antenna
- 915 MHz antenna
- 10,000 mAh power bank
- 64GB A2 microSD card

## GPIO Wiring — GPS Module
The NEO-6M is connected to the Pi Zero 2W GPIO header via jumper wires.

| NEO-6M Pin | Pi GPIO Pin | Function |
|---|---|---|
| VCC | Pin 1 (3.3V) | Power |
| GND | Pin 6 (GND) | Ground |
| TX | Pin 10 (GPIO 15 / RXD) | Serial RX |
| RX | Pin 8 (GPIO 14 / TXD) | Serial TX |

Reference: https://pinout.xyz (GPIO on right, HDMI on left, Pin 1 top-left)

## OS Setup
- Flash Debian Trixie (64-bit) using Raspberry Pi Imager
- Pre-configure WiFi credentials in Imager before flashing
- Enable SSH in Imager

## Key Configuration Notes
- Blacklist `dvb_usb_rtl28xxu` kernel module or dump1090 cannot access dongles
- dump1090 must be built from source on Debian Trixie — the packaged `readsb` lacks RTL-SDR support
- Disable `gpsd` and `serial-getty@ttyS0` — both conflict with the custom GPS service
- GPS serial port: `/dev/ttyS0` at 9600 baud

## Dongle Serial Numbers
Assign serial numbers to dongles using `rtl_eeprom` so services always use the correct dongle regardless of USB enumeration order:
```bash
rtl_eeprom -d 0 -s 00000001  # ADS-B dongle
rtl_eeprom -d 1 -s 00000002  # 433 MHz dongle
rtl_eeprom -d 2 -s 00000003  # 915 MHz dongle
```

## Network Setup
The Pi uses NetworkManager with the following network priority:
1. Home WiFi (autoconnect)
2. Phone hotspot (autoconnect)
3. Hotspot fallback (priority -10)

Access via mDNS on any shared network:  ssh pi@adsb-tracker.local        http://adsb-tracker.local:8080                                                                                                                               ##Known Issues / Lessons Learned
- Debian Trixie has package gaps for SDR work — build dump1090 from source
- pmtiles/mbtiles vector tiles are incompatible with raster XYZ approach — use raster OSM tiles
- Flask route/variable naming collisions cause non-obvious JSON errors — name functions carefully
