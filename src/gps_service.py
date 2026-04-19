#!/usr/bin/env python3
import serial
import threading
from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)
location = {"lat": 0.0, "lon": 0.0, "alt": 0.0, "fix": False}

def parse_nmea(line):
    try:
        if line.startswith('$GPRMC') or line.startswith('$GNRMC'):
            parts = line.split(',')
            if parts[2] == 'A':
                lat = float(parts[3][:2]) + float(parts[3][2:]) / 60
                if parts[4] == 'S':
                    lat = -lat
                lon = float(parts[5][:3]) + float(parts[5][3:]) / 60
                if parts[6] == "W":
                    lon = -lon
                location['lat'] = round(lat, 6)
                location['lon'] = round(lon, 6)
                location['fix'] = True
        if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
            parts = line.split(',')
            if parts[9]:
                location['alt'] = float(parts[9])
    except:
        pass

def gps_thread():
    ser = serial.Serial('/dev/ttyS0', 9600, timeout=1)
    while True:
        try:
            line = ser.readline().decode('ascii', errors='ignore').strip()
            parse_nmea(line)
        except:
            pass

@app.route('/api/location')
def get_location():
    return jsonify(location)

@app.route('/api/drone_detections')
def get_drone_detections():
    detections = []
    try:
        with open('/home/pi/drone_detections.log', 'r') as f:
            lines = f.readlines()
        for line in lines[-50:]:
            parts = line.strip().split(' | ')
            if len(parts) == 4:
                detections.append({
                    "time": parts[0],
                    "band": parts[1],
                    "freq": parts[2],
                    "power": parts[3]
                })
    except:
        pass
    return jsonify(detections)

t = threading.Thread(target=gps_thread, daemon=True)
t.start()
app.run(host='0.0.0.0', port=5001)
