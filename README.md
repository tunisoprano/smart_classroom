# Akıllı Sınıf Otomasyon ve Analiz Sistemi

Üniversite sınıflarının enerji tüketimini, doluluk oranına göre aydınlatma,
iklimlendirme ve çevre sensörlerini otomatik kontrol ederek optimize eden;
tüketim verilerini analiz edip tasarruf raporu sunan dijital ikiz sistemi.

---

## Proje Yapısı

```
smart_classroom/
├── simulation/
│   └── dijital_ikiz.py   # DES+ABM hibrit simülasyon motoru
├── backend/
│   └── app.py            # Flask REST API
├── frontend/
│   └── templates/
│       └── index.html    # Web dashboard
├── database/
│   └── smart_classroom.db  # SQLite (simülasyon sonrası oluşur)
├── requirements.txt
└── README.md
```

---

## Kullanılan Sensörler ve Datasheet Parametreleri

| Sensör    | Ölçüm          | Doğruluk       | Gürültü Modeli       |
|-----------|----------------|----------------|----------------------|
| DHT22     | Sıcaklık / Nem | ±0.5°C / ±2%RH | Normal(0, 0.25)      |
| MQ-135    | CO₂ (ppm)      | ±15 ppm        | Normal(drift, 15)    |
| BH1750    | Işık (lux)     | ±8% göreceli   | Çarpımsal Normal     |
| ACS712-5B | Akım (A)       | ±50 mA         | Normal(0, 0.05)      |
| HC-SR04   | Mesafe (m)     | ±1.5 mm        | Normal(0, 0.0015)    |

## Karar Algoritması (Threshold + Histerezis)

**HVAC:**
- CO₂ ≥ 1000 ppm → Havalandırma AÇIK  (ASHRAE 62.1)
- CO₂ ≤  700 ppm → Havalandırma KAPALI
- Arada → Mevcut durum korunur (histerezis)

**Aydınlatma:**
- Bölge dolu + ortam ışığı < 300 lux → Işık AÇIK
- Bölge boş veya ortam ışığı ≥ 500 lux → Işık KAPALI

---

## Kurulum ve Çalıştırma

```bash
pip install -r requirements.txt

# 1. Simülasyonu çalıştır (veritabanını doldurur)
python simulation/dijital_ikiz.py

# 2. API ve dashboard'u başlat
python backend/app.py

# 3. Tarayıcıda aç
# http://localhost:5000
```

## API Endpointleri

| Endpoint       | Açıklama                              |
|----------------|---------------------------------------|
| GET /          | Web dashboard                         |
| GET /api/data  | Son 100 sensör kaydı (JSON)           |
| GET /api/summary | Gün özeti + enerji tasarruf raporu  |
| GET /api/alerts  | CO₂ ve doluluk uyarıları            |
| GET /api/energy  | Saatlik enerji karşılaştırması      |
| GET /api/status  | Son anlık sensör durumu             |

---

## Geliştiriciler

| İsim | Bölüm | Katkı |
|------|-------|-------|
| ... | Bilgisayar Müh. | Simülasyon motoru, Flask API, veritabanı |
| ... | Elektrik-Elektronik | Sensör modelleri, datasheet analizi, devre tasarımı |
| ... | Endüstri Müh. | Enerji verimliliği analizi, tasarruf algoritması |
