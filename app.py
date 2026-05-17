"""
Apiterapia con Vero — Serveur Flask
=====================================
Lancer avec :  python app.py
Accessible depuis le réseau local (téléphone, etc.) sur http://<IP_locale>:5000
"""

from flask import Flask, render_template, request, jsonify
import json
import os
import urllib.parse
from datetime import datetime

app = Flask(__name__)

# Fichier où les rendez-vous sont sauvegardés
APPOINTMENTS_FILE = os.path.join(os.path.dirname(__file__), 'appointments.json')


# ── Helpers JSON ──────────────────────────────────────────────────────────────

def load_appointments():
    """Charge la liste des rendez-vous depuis le fichier JSON."""
    if not os.path.exists(APPOINTMENTS_FILE):
        return []
    with open(APPOINTMENTS_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return []


def save_appointments(appointments):
    """Sauvegarde la liste des rendez-vous dans le fichier JSON."""
    with open(APPOINTMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(appointments, f, ensure_ascii=False, indent=2)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    """Page principale — charge templates/index.html."""
    return render_template('index.html')


@app.route('/api/slots', methods=['GET'])
def get_slots():
    """
    Retourne la liste de tous les créneaux déjà réservés.
    Format : [{"date": "2025-07-14", "time": "10:00"}, ...]
    Le front-end les utilise pour griser les options dans le formulaire.
    """
    appointments = load_appointments()
    booked = [{'date': a['date'], 'time': a['time']} for a in appointments]
    return jsonify(booked)


@app.route('/api/book', methods=['POST'])
def book():
    """
    Reçoit un rendez-vous, vérifie l'absence de doublon,
    le sauvegarde dans appointments.json, et renvoie l'URL WhatsApp pré-remplie.

    Corps JSON attendu :
    {
        "name":    "Ana María",
        "phone":   "+56912345678",
        "date":    "2025-07-14",
        "time":    "10:00",
        "comment": "..."    (optionnel)
    }
    """
    data = request.get_json(silent=True)

    # Validation basique
    if not data:
        return jsonify({'error': 'invalid_json',
                        'message': 'Cuerpo de la petición inválido'}), 400

    name    = (data.get('name',    '') or '').strip()
    phone   = (data.get('phone',   '') or '').strip()
    date    = (data.get('date',    '') or '').strip()
    time    = (data.get('time',    '') or '').strip()
    comment = (data.get('comment', '') or '').strip()

    if not all([name, phone, date, time]):
        return jsonify({'error': 'missing_fields',
                        'message': 'Faltan campos obligatorios'}), 400

    appointments = load_appointments()

    # ── Anti-doublon ──────────────────────────────────────────────────────────
    for appt in appointments:
        if appt.get('date') == date and appt.get('time') == time:
            return jsonify({'error': 'duplicate',
                            'message': 'Este horario ya está reservado'}), 409

    # ── Sauvegarde ────────────────────────────────────────────────────────────
    new_appointment = {
        'name':       name,
        'phone':      phone,
        'date':       date,
        'time':       time,
        'comment':    comment,
        'created_at': datetime.now().isoformat()
    }
    appointments.append(new_appointment)
    save_appointments(appointments)

    # ── URL WhatsApp pré-remplie ──────────────────────────────────────────────
    message = (
        f"Hola Vero, me gustaría agendar una sesión de Apiterapia.\n\n"
        f"• *Nombre:* {name}\n"
        f"• *WhatsApp:* {phone}\n"
        f"• *Fecha deseada:* {date}\n"
        f"• *Horario:* {time} hrs"
    )
    if comment:
        message += f"\n• *Comentarios:* {comment}"

    whatsapp_url = f"https://wa.me/56939047200?text={urllib.parse.quote(message)}"

    return jsonify({'success': True, 'whatsapp_url': whatsapp_url})


# ── Point d'entrée ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Port 5001 — le port 5000 est réservé par AirPlay sur macOS Monterey et plus récent
    # Accès depuis ton téléphone (même Wi-Fi) : http://<IP_locale>:5001
    app.run(debug=True, host='0.0.0.0', port=5001)
