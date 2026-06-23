from flask import Flask, jsonify, render_template
import sqlite3
import os

app = Flask(__name__, template_folder='../frontend/templates')

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'smart_classroom.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/data')
def get_data():
    """Son 100 sensör kaydı."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM sensor_data ORDER BY time DESC LIMIT 100"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/summary')
def get_summary():
    """Gün sonu özet: enerji, tasarruf, CO2, kişi."""
    conn = get_db()
    row = conn.execute("""
        SELECT
            COUNT(*)                        AS total_records,
            MAX(people)                     AS peak_occupancy,
            ROUND(AVG(people), 1)           AS avg_occupancy,
            ROUND(MAX(co2), 1)              AS max_co2,
            ROUND(AVG(co2), 1)              AS avg_co2,
            ROUND(MAX(temperature), 1)      AS max_temp,
            ROUND(AVG(temperature), 1)      AS avg_temp,
            ROUND(MAX(energy), 1)           AS smart_energy_wh,
            SUM(hvac_on)                    AS hvac_on_minutes,
            MAX(trash_count)                AS max_trash,
            MAX(trash_count)                AS total_trashed
        FROM sensor_data
    """).fetchone()
    conn.close()
    data = dict(row)

    # Klasik sistem tahmini (sabit güç × süre)
    CLASSIC_POWER_W = 4 * 18 + 2200   # 4 LED bölge + HVAC
    hours = (data['total_records'] or 0) * 60 / 3600
    data['classic_energy_wh'] = round(CLASSIC_POWER_W * hours, 1)
    data['savings_wh'] = round(data['classic_energy_wh'] - (data['smart_energy_wh'] or 0), 1)
    data['savings_pct'] = round(
        data['savings_wh'] / data['classic_energy_wh'] * 100, 1
    ) if data['classic_energy_wh'] > 0 else 0

    return jsonify(data)


@app.route('/api/alerts')
def get_alerts():
    """Tüm uyarılar."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM alerts ORDER BY time DESC"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/energy')
def get_energy():
    """Saatlik enerji karşılaştırması (akıllı vs klasik)."""
    conn = get_db()
    rows = conn.execute("""
        SELECT
            CAST(time/3600 AS INTEGER)  AS hour_idx,
            ROUND(AVG(energy), 2)       AS smart_avg_wh,
            ROUND(AVG(people), 1)       AS avg_people,
            ROUND(AVG(co2), 0)          AS avg_co2,
            ROUND(AVG(hvac_on)*100, 0)  AS hvac_pct
        FROM sensor_data
        GROUP BY hour_idx
        ORDER BY hour_idx
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/status')
def get_status():
    """Son anlık durum."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM sensor_data ORDER BY time DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row is None:
        return jsonify({'error': 'Henüz veri yok. Simülasyonu çalıştırın.'})
    return jsonify(dict(row))


if __name__ == '__main__':
    app.run(debug=True, port=5000)
