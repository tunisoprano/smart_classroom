# -*- coding: utf-8 -*-
"""
Akıllı Sınıf Dijital İkiz Simülasyonu
Sensör parametreleri gerçek datasheet değerlerine dayanmaktadır.
"""

import numpy as np
import heapq
import math
import sqlite3
import os
from collections import deque

# ─────────────────────────────────────────
# VERİTABANI
# ─────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'smart_classroom.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.executescript("""
DROP TABLE IF EXISTS sensor_data;
DROP TABLE IF EXISTS alerts;

CREATE TABLE sensor_data (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    time        REAL,
    co2         REAL,
    temperature REAL,
    humidity    REAL,
    light_lux   REAL,
    current     REAL,
    energy      REAL,
    classic_energy REAL,
    people      INTEGER,
    trash_count INTEGER,
    light_zones INTEGER,
    hvac_on     INTEGER
);

CREATE TABLE alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    time        REAL,
    alert_type  TEXT,
    message     TEXT
);
""")
conn.commit()


# ─────────────────────────────────────────
# OLAY ZAMANLAYICI (DES)
# ─────────────────────────────────────────
class TimeLine:
    def __init__(self):
        self.data = {}
        self.heap = []

    def add(self, event):
        t = event.time
        if t not in self.data:
            self.data[t] = deque()
            heapq.heappush(self.heap, t)
        self.data[t].append(event)

    def pop(self):
        while self.heap:
            t = self.heap[0]
            if t not in self.data:
                heapq.heappop(self.heap)
                continue
            q = self.data[t]
            ev = q.popleft()
            if not q:
                del self.data[t]
                heapq.heappop(self.heap)
            return t, ev
        return None, None


class Event:
    def __init__(self, name, timeline, time, params, proc, **kwargs):
        self.name     = name
        self.timeline = timeline
        self.time     = time
        self.params   = params
        self.proc     = proc
        self.__dict__.update(kwargs)

    def run(self):
        if self.proc:
            self.proc(self.timeline, self.time, self.params, self)


# ─────────────────────────────────────────
# SENSÖR SINIFLARI  (Datasheet Tabanlı)
# ─────────────────────────────────────────

class DHT22Sensor:
    """
    Datasheet: Aosong DHT22/AM2302
    Sıcaklık hassasiyeti : ±0.5°C   → std = 0.25
    Nem hassasiyeti      : ±2 % RH  → std = 1.0
    Gürültü: Normal dağılım
    """
    TEMP_STD = 0.25
    HUM_STD  = 1.0

    def read_temperature(self, true_temp):
        return round(true_temp + np.random.normal(0, self.TEMP_STD), 1)

    def read_humidity(self, true_hum):
        return round(float(np.clip(true_hum + np.random.normal(0, self.HUM_STD), 0, 100)), 1)


class MQ135Sensor:
    """
    Datasheet: Winsen MQ-135
    CO2 doğruluk    : ±15 ppm @ oda sıcaklığı
    Sıcaklık drift  : +1.5 ppm/°C (25°C baz)
    Gürültü: Normal + sıcaklık kayması
    """
    BASE_STD         = 15.0
    TEMP_DRIFT_COEFF = 1.5

    def read(self, true_co2, ambient_temp=25.0):
        drift = self.TEMP_DRIFT_COEFF * (ambient_temp - 25.0)
        return round(max(400.0, true_co2 + np.random.normal(drift, self.BASE_STD)), 1)


class BH1750Sensor:
    """
    Datasheet: ROHM BH1750FVI
    Doğruluk : ±20% (tipik ±10%) → std = %8 rölatif
    Gürültü  : Çarpımsal Normal
    """
    REL_STD = 0.08

    def read(self, true_lux):
        return round(float(np.clip(true_lux * np.random.normal(1.0, self.REL_STD), 0, 65535)), 0)


class ACS712Sensor:
    """
    Datasheet: Allegro ACS712-05B
    Gürültü : ~6.5 mA RMS → std = 0.05 A
    """
    NOISE_STD = 0.05

    def read(self, true_current):
        return round(max(0.0, true_current + np.random.normal(0, self.NOISE_STD)), 3)


class UltrasonicHCSR04:
    """
    Datasheet: HC-SR04
    Hassasiyet : ±3 mm → std = 1.5 mm
    """
    DIST_STD = 0.0015

    def read(self, true_distance):
        return round(max(0.0, true_distance + np.random.normal(0, self.DIST_STD)), 4)


# ─────────────────────────────────────────
# AJAN SINIFLARI
# ─────────────────────────────────────────

class OccupantAgent:
    """
    Ortalama insan CO2 üretimi:
    ~200 ml/nefes × 15 nefes/dk = 3000 ml/dk
    8x6x3 m³ sınıf hacminde: ~0.008 ppm/kişi/saniye
    """
    CO2_RATE_PPM_PER_SEC = 0.008

    def __init__(self, agent_id):
        self.agent_id = agent_id

    def co2_emission(self, dt):
        return self.CO2_RATE_PPM_PER_SEC * dt


class SmartLight:
    WATTAGE = 18.0  # LED panel (klasik floresan 40W yerine)

    def __init__(self, zone_id):
        self.zone_id = zone_id
        self.is_on   = False

    def power(self):
        return self.WATTAGE if self.is_on else 0.0


class HVACSystem:
    WATTAGE    = 2200.0  # W  (9000 BTU split klima)
    EVAC_RATE  =  5.0    # ppm/saniye CO2 tahliyesi
    COOL_RATE  =  0.08   # °C/dakika soğutma

    def __init__(self):
        self.is_on = False

    def power(self):
        return self.WATTAGE if self.is_on else 0.0

    def evacuate(self, dt):
        return self.EVAC_RATE * dt if self.is_on else 0.0

    def cool(self, dt):
        return self.COOL_RATE * (dt / 60.0) if self.is_on else 0.0


# ─────────────────────────────────────────
# EŞİK TABANLI KARAR ALGORİTMASI
# ─────────────────────────────────────────
class ThresholdController:
    """
    Karar kuralları (histerezisli eşik tabanlı):

    HVAC:
        AÇIK  → CO2 ≥ 1000 ppm  (ASHRAE 62.1)  VEYA  sıcaklık ≥ 26°C
        KAPALI→ CO2 ≤  700 ppm  VE sıcaklık ≤ 23°C

    Aydınlatma (bölgesel):
        AÇIK  → Bölgede kişi var VE ortam ışığı < 300 lux
        KAPALI→ Bölge boş  VEYA ortam ışığı ≥ 500 lux
    """
    CO2_ON_THRESH  = 1000.0
    CO2_OFF_THRESH =  700.0
    TEMP_ON_THRESH =   26.0
    TEMP_OFF_THRESH=   23.0
    LUX_ON_THRESH  =  300.0
    LUX_OFF_THRESH =  500.0

    def decide_hvac(self, co2, temp, hvac_on):
        if co2 >= self.CO2_ON_THRESH or temp >= self.TEMP_ON_THRESH:
            return True
        if co2 <= self.CO2_OFF_THRESH and temp <= self.TEMP_OFF_THRESH:
            return False
        return hvac_on  # histerezis

    def decide_light(self, zone_occupied, lux, light_on):
        if not zone_occupied:
            return False
        if lux < self.LUX_ON_THRESH:
            return True
        if lux >= self.LUX_OFF_THRESH:
            return False
        return light_on  # histerezis


# ─────────────────────────────────────────
# GÜNLÜK EĞRİLER (09:00 – 17:00)
# ─────────────────────────────────────────
# Her saat için geliş yoğunluğu (kişi/saat)
HOURLY_ARRIVAL_RATES  = [0, 4, 8, 6, 3, 5, 7, 2]
# Doğal ışık (lux) — güneşli İstanbul günü
NATURAL_LIGHT_BY_HOUR = [150, 250, 450, 650, 750, 700, 500, 250]
# Dış sıcaklık (°C)
OUTDOOR_TEMP_BY_HOUR  = [18, 20, 22, 25, 27, 28, 26, 24]

# ─────────────────────────────────────────
# SİMÜLASYON KURULUMLARI
# ─────────────────────────────────────────
SIM_DURATION = 28800.0   # 8 saat
ENV_INTERVAL =    60.0   # 1 dakika
GRID_VOLTAGE =   220.0   # V
ROOM_VOLUME  =   144.0   # m³ (8×6×3)

lights     = [SmartLight(i) for i in range(4)]
hvac       = HVACSystem()
controller = ThresholdController()
sensors    = {
    'dht22'     : DHT22Sensor(),
    'mq135'     : MQ135Sensor(),
    'bh1750'    : BH1750Sensor(),
    'acs712'    : ACS712Sensor(),
    'ultrasonic': UltrasonicHCSR04(),
}

simParams = {
    'Duration'        : SIM_DURATION,
    'EnvInterval'     : ENV_INTERVAL,
    'TrueCO2'         : 415.0,
    'TrueTemp'        : 20.0,
    'TrueHumidity'    : 45.0,
    'Occupants'       : [],
    'TotalArrivals'   : 0,
    'MaxOccupancy'    : 40,
    'TotalEnergy_Wh'  : 0.0,
    'ClassicEnergy_Wh': 0.0,
    # Geri dönüşüm kutusu
    'BinHeight'       : 0.8,     # m
    'BinCount'        : 0,
    'BinMax'          : 40,
    'TrashThickness'  : 0.02,    # m (ezilmiş pet şişe/ambalaj)
    'TotalTrashed'    : 0,
    # Cihazlar
    'Lights'          : lights,
    'HVAC'            : hvac,
    'Controller'      : controller,
    'Sensors'         : sensors,
    'AlertCount'      : 0,
}


# ─────────────────────────────────────────
# YARDIMCILAR
# ─────────────────────────────────────────
def hour_idx(t):
    return min(7, int(t // 3600))

def natural_light(t):
    base = NATURAL_LIGHT_BY_HOUR[hour_idx(t)]
    return max(0.0, base + np.random.normal(0, base * 0.05))

def outdoor_temp(t):
    return OUTDOOR_TEMP_BY_HOUR[hour_idx(t)] + np.random.normal(0, 0.3)

def log_alert(t, atype, msg):
    cursor.execute("INSERT INTO alerts (time,alert_type,message) VALUES (?,?,?)", (t, atype, msg))
    conn.commit()


# ─────────────────────────────────────────
# PROSEDÜRLER
# ─────────────────────────────────────────
def arrival_proc(tl, t, p, ev):
    occ = OccupantAgent(f"P{p['TotalArrivals']+1}")
    p['Occupants'].append(occ)
    p['TotalArrivals'] += 1

    # %25 ihtimalle çöp atar
    if np.random.rand() < 0.25:
        tl.add(Event('Trash', tl, t + np.random.uniform(5, 120), p, trash_proc))

    # Kalma süresi Normal(90dk, 30dk), min 30dk
    stay = max(1800, np.random.normal(5400, 1800))
    leave_t = t + stay
    if leave_t < p['Duration']:
        tl.add(Event('Depart', tl, leave_t, p, depart_proc, agent=occ))

    # Bir sonraki geliş
    rate = HOURLY_ARRIVAL_RATES[hour_idx(t)]
    if rate > 0 and len(p['Occupants']) < p['MaxOccupancy']:
        interval = 3600.0 / rate
        next_t = t + np.random.exponential(interval)
        if next_t < p['Duration']:
            tl.add(Event('Arrive', tl, next_t, p, arrival_proc))


def depart_proc(tl, t, p, ev):
    if ev.agent in p['Occupants']:
        p['Occupants'].remove(ev.agent)


def trash_proc(tl, t, p, ev):
    if p['BinCount'] < p['BinMax']:
        p['BinCount'] += 1
        p['TotalTrashed'] += 1
        level = p['BinCount'] * p['TrashThickness']
        fill_pct = (level / p['BinHeight']) * 100
        if p['BinCount'] >= p['BinMax']:
            log_alert(t, 'BIN_FULL', f'Geri dönüşüm kutusu doldu! (%{fill_pct:.0f})')
            tl.add(Event('EmptyBin', tl, t + 600, p, empty_bin_proc))
        elif fill_pct >= 80:
            log_alert(t, 'BIN_WARNING', f'Geri dönüşüm kutusu %{fill_pct:.0f} dolu.')


def empty_bin_proc(tl, t, p, ev):
    p['BinCount'] = 0


def env_update_proc(tl, t, p, ev):
    dt       = p['EnvInterval']
    occs     = p['Occupants']
    n        = len(occs)
    ctrl     = p['Controller']
    s        = p['Sensors']

    # ── CO2 ──────────────────────────────────────
    p['TrueCO2'] += sum(o.co2_emission(dt) for o in occs)
    p['TrueCO2'] -= p['HVAC'].evacuate(dt)
    p['TrueCO2']  = max(415.0, p['TrueCO2'])

    # ── Sıcaklık ─────────────────────────────────
    body_heat  = n * 0.05 * (dt / 60.0)
    hvac_cool  = p['HVAC'].cool(dt)
    wall_xchg  = (outdoor_temp(t) - p['TrueTemp']) * 0.003 * (dt / 60.0)
    p['TrueTemp'] = float(np.clip(p['TrueTemp'] + body_heat - hvac_cool + wall_xchg, 15.0, 38.0))

    # ── Nem ──────────────────────────────────────
    hum_d = n * 0.2 * (dt / 60.0) - 0.05 * (dt / 60.0)
    p['TrueHumidity'] = float(np.clip(p['TrueHumidity'] + hum_d, 20.0, 90.0))

    # ── Doğal ışık ───────────────────────────────
    true_lux = natural_light(t)

    # ── KARAR ALGORİTMASI ────────────────────────
    p['HVAC'].is_on = ctrl.decide_hvac(p['TrueCO2'], p['TrueTemp'], p['HVAC'].is_on)

    zones_needed = 0 if n == 0 else min(4, math.ceil(n / 10))
    for i, light in enumerate(p['Lights']):
        light.is_on = ctrl.decide_light(i < zones_needed, true_lux, light.is_on)

    # ── Enerji ───────────────────────────────────
    active_lights = sum(1 for l in p['Lights'] if l.is_on)
    total_power_w = sum(l.power() for l in p['Lights']) + p['HVAC'].power()
    p['TotalEnergy_Wh']   += total_power_w * (dt / 3600.0)
    classic_power = 4 * SmartLight.WATTAGE + HVACSystem.WATTAGE
    p['ClassicEnergy_Wh'] += classic_power * (dt / 3600.0)

    true_current = total_power_w / GRID_VOLTAGE

    # ── Sensör okumaları ─────────────────────────
    meas_temp = s['dht22'].read_temperature(p['TrueTemp'])
    meas_hum  = s['dht22'].read_humidity(p['TrueHumidity'])
    meas_co2  = s['mq135'].read(p['TrueCO2'], p['TrueTemp'])
    meas_lux  = s['bh1750'].read(true_lux)
    meas_cur  = s['acs712'].read(true_current)

    # Çöp kutusu doluluk seviyesi (ultrasonic)
    bin_level = p['BinCount'] * p['TrashThickness']
    _ = s['ultrasonic'].read(p['BinHeight'] - bin_level)  # sensör okuması (log için)

    # ── Uyarılar (saatte bir kez) ─────────────────
    current_hour = int(t // 3600)
    if p['TrueCO2'] >= 1000.0:
        if current_hour != p.get('LastCO2AlertHour', -1):
            log_alert(t, 'HIGH_CO2', f"CO2 kritik: {p['TrueCO2']:.0f} ppm")
            p['LastCO2AlertHour'] = current_hour
            p['AlertCount'] += 1
    if p['TrueTemp'] >= 35.0:
        if current_hour != p.get('LastTempAlertHour', -1):
            log_alert(t, 'HIGH_TEMP', f"Sıcaklık yüksek: {p['TrueTemp']:.1f}°C")
            p['LastTempAlertHour'] = current_hour

    # ── Veritabanı ───────────────────────────────
    cursor.execute("""
        INSERT INTO sensor_data
        (time,co2,temperature,humidity,light_lux,current,energy,classic_energy,
         people,trash_count,light_zones,hvac_on)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (t, meas_co2, meas_temp, meas_hum, meas_lux, meas_cur,
          p['TotalEnergy_Wh'], p['ClassicEnergy_Wh'],
          n, p['BinCount'], active_lights, 1 if p['HVAC'].is_on else 0))
    conn.commit()

    # ── Saatlik rapor ────────────────────────────
    if t > 0 and t % 3600 < dt:
        saat = hour_idx(t) + 9
        savings = p['ClassicEnergy_Wh'] - p['TotalEnergy_Wh']
        pct = savings / p['ClassicEnergy_Wh'] * 100 if p['ClassicEnergy_Wh'] > 0 else 0
        bin_fill = (p['BinCount'] / p['BinMax']) * 100
        print(f"\n[{saat:02d}:00]  Kişi:{n:2d}  CO2:{meas_co2:5.0f}ppm  "
              f"Sıcaklık:{meas_temp:.1f}°C  Işık:{active_lights}/4  "
              f"HVAC:{'ON ' if p['HVAC'].is_on else 'OFF'}  "
              f"Çöp:%{bin_fill:.0f}  Tasarruf:%{pct:.1f}")

    next_t = t + dt
    if next_t <= p['Duration']:
        tl.add(Event('EnvUpdate', tl, next_t, p, env_update_proc))


# ─────────────────────────────────────────
# ÇALIŞTIR
# ─────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 60)
    print("  AKILLI SINIF DİJİTAL İKİZ — 8 SAATLİK SİMÜLASYON")
    print("  09:00 – 17:00")
    print("=" * 60)

    tl = TimeLine()
    tl.add(Event('Arrive',    tl, 3600.0,              simParams, arrival_proc))
    tl.add(Event('EnvUpdate', tl, simParams['EnvInterval'], simParams, env_update_proc))

    while tl.data:
        t, ev = tl.pop()
        if ev:
            ev.run()

    savings = simParams['ClassicEnergy_Wh'] - simParams['TotalEnergy_Wh']
    pct     = savings / simParams['ClassicEnergy_Wh'] * 100 if simParams['ClassicEnergy_Wh'] > 0 else 0

    print("\n" + "=" * 60)
    print("  SONUÇ")
    print("=" * 60)
    print(f"  Toplam gelen kişi         : {simParams['TotalArrivals']}")
    print(f"  Toplam atılan çöp         : {simParams['TotalTrashed']}")
    print(f"  Akıllı sistem enerjisi    : {simParams['TotalEnergy_Wh']:.1f} Wh")
    print(f"  Klasik sistem (referans)  : {simParams['ClassicEnergy_Wh']:.1f} Wh")
    print(f"  Enerji tasarrufu          : {savings:.1f} Wh  (%{pct:.1f})")
    print(f"  Toplam CO2 / ısı uyarısı  : {simParams['AlertCount']}")
    print("=" * 60)

    conn.close()
