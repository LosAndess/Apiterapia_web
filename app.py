"""
Apiterapia con Vero — Serveur Flask
=====================================
Lancer avec :  python app.py

Le serveur écoute simultanément sur DEUX ports :
  → http://localhost:5001      (navigateur de ton Mac)
  → http://<IP_locale>:8080    (téléphone sur le même Wi-Fi)

Pour trouver ton IP locale : ipconfig getifaddr en0
"""

from flask import Flask, render_template, request, jsonify
import json
import os
import urllib.parse
import threading
from datetime import datetime
from werkzeug.serving import make_server

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

def start_server(port):
    """Lance une instance du serveur sur le port donné (sans reloader)."""
    server = make_server('0.0.0.0', port, app)
    server.serve_forever()

if __name__ == '__main__':
    PORT_MAC    = 5001   # Accès local sur ton Mac  → http://localhost:5001
    PORT_MOBILE = 8080   # Accès depuis ton téléphone → http://<IP_locale>:8080

    # Lancer le port 5001 dans un thread secondaire
    t = threading.Thread(target=start_server, args=(PORT_MAC,), daemon=True)
    t.start()

    print(f"\n{'='*52}")
    print(f"  ✅  Serveur Apiterapia lancé sur 2 ports")
    print(f"  💻  Mac     → http://localhost:{PORT_MAC}")
    print(f"  📱  Mobile  → http://<ton_IP_locale>:{PORT_MOBILE}")
    print(f"  (IP locale : lance 'ipconfig getifaddr en0' dans un autre terminal)")
    print(f"{'='*52}\n")

    # Lancer le port 8080 sur le thread principal (bloquant)
    start_server(PORT_MOBILE)
