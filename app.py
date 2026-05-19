"""
Apiterapia con Vero — Serveur Flask
=====================================
Développement local :
  python app.py
  → http://localhost:5001

Production (Vercel) :
  Le fichier vercel.json route toutes les requêtes vers ce fichier.
  L'objet WSGI `app` est détecté automatiquement par @vercel/python.

Stockage des rendez-vous :
  - Local      → appointments.json dans le même répertoire
  - Vercel     → /tmp/appointments.json (éphémère, par instance)
  - Fallback   → liste en mémoire si /tmp n'est pas accessible
"""

import os
import json
import urllib.parse
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Stockage résilient des rendez-vous
# ─────────────────────────────────────────────────────────────────────────────
# Sur Vercel, le système de fichiers est en lecture seule sauf /tmp.
# /tmp est éphémère (local à l'instance Serverless) mais ne génère jamais
# d'erreur 500. En développement local, on utilise le fichier appointments.json
# dans le même répertoire que app.py.

def _get_appointments_file():
    """Retourne le chemin du fichier de stockage adapté à l'environnement."""
    # En local, on utilise le dossier du projet
    local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'appointments.json')
    if os.path.exists(os.path.dirname(local_path)) and os.access(os.path.dirname(local_path), os.W_OK):
        try:
            # Teste si on peut écrire dans le dossier courant (local)
            test_path = os.path.join(os.path.dirname(local_path), '.write_test')
            with open(test_path, 'w') as f:
                f.write('ok')
            os.remove(test_path)
            return local_path
        except OSError:
            pass
    # Fallback Vercel → /tmp
    return '/tmp/appointments.json'

# Cache en mémoire (fallback si le disque est inaccessible)
_appointments_memory = []


def load_appointments():
    """Charge les rendez-vous depuis le disque. Retourne [] en cas d'erreur."""
    global _appointments_memory
    try:
        filepath = _get_appointments_file()
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    _appointments_memory = data
                    return data
    except Exception:
        pass
    return list(_appointments_memory)


def save_appointments(appointments):
    """Enregistre les rendez-vous sur disque et en mémoire."""
    global _appointments_memory
    _appointments_memory = list(appointments)
    try:
        filepath = _get_appointments_file()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(appointments, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # Mémoire suffisante si le disque est inaccessible


# ─────────────────────────────────────────────────────────────────────────────
# Gestionnaires d'erreurs — retournent toujours du JSON (jamais du HTML)
# ─────────────────────────────────────────────────────────────────────────────

@app.errorhandler(400)
def bad_request(e):
    return jsonify({'error': 'bad_request', 'message': str(e)}), 400

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'not_found', 'message': str(e)}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'error': 'method_not_allowed', 'message': str(e)}), 405

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'server_error', 'message': 'Error interno del servidor'}), 500

@app.errorhandler(Exception)
def unhandled_exception(e):
    app.logger.error(f'Exception non gérée : {e}', exc_info=True)
    return jsonify({'error': 'server_error', 'message': 'Error interno del servidor'}), 500


# ─────────────────────────────────────────────────────────────────────────────
# En-têtes anti-cache
# ─────────────────────────────────────────────────────────────────────────────

@app.after_request
def apply_no_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma']        = 'no-cache'
    response.headers['Expires']       = '0'
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/slots', methods=['GET'])
def get_slots():
    """Retourne les créneaux déjà réservés : [{"date":"…","time":"…"}, …]"""
    appointments = load_appointments()
    booked = [
        {'date': a['date'], 'time': a['time']}
        for a in appointments
        if 'date' in a and 'time' in a
    ]
    return jsonify(booked)


@app.route('/api/book', methods=['POST'])
def book():
    """
    Enregistre un rendez-vous.

    Corps JSON attendu :
      { "name": "…", "phone": "…", "date": "YYYY-MM-DD", "time": "HH:MM", "comment": "…" }

    Codes de retour :
      200 → succès  { success: true, whatsapp_url: "…" }
      400 → champs manquants ou JSON invalide
      409 → créneau déjà pris
    """
    data = request.get_json(silent=True)

    if not data:
        return jsonify({'error': 'invalid_json',
                        'message': 'Cuerpo de la petición inválido'}), 400

    name    = (data.get('name',    '') or '').strip()
    phone   = (data.get('phone',   '') or '').strip()
    date    = (data.get('date',    '') or '').strip()
    slot    = (data.get('time',    '') or '').strip()
    comment = (data.get('comment', '') or '').strip()

    if not all([name, phone, date, slot]):
        return jsonify({'error': 'missing_fields',
                        'message': 'Faltan campos obligatorios'}), 400

    appointments = load_appointments()

    # Anti-doublon côté serveur
    for appt in appointments:
        if appt.get('date') == date and appt.get('time') == slot:
            return jsonify({'error': 'duplicate',
                            'message': 'Este horario ya está reservado'}), 409

    appointments.append({
        'name':       name,
        'phone':      phone,
        'date':       date,
        'time':       slot,
        'comment':    comment,
        'created_at': datetime.now().isoformat()
    })
    save_appointments(appointments)

    # Message WhatsApp pré-rempli
    msg = (
        f"Hola Vero, me gustaría agendar una sesión de Apiterapia.\n\n"
        f"• *Nombre:* {name}\n"
        f"• *WhatsApp:* {phone}\n"
        f"• *Fecha deseada:* {date}\n"
        f"• *Horario:* {slot} hrs"
    )
    if comment:
        msg += f"\n• *Comentarios:* {comment}"

    whatsapp_url = f"https://wa.me/56939047200?text={urllib.parse.quote(msg)}"
    return jsonify({'success': True, 'whatsapp_url': whatsapp_url})


# ─────────────────────────────────────────────────────────────────────────────
# Exposition WSGI — requis par Vercel (@vercel/python)
# ─────────────────────────────────────────────────────────────────────────────

# Vercel détecte automatiquement l'objet `app` ou `application`.
# Cette ligne garantit la compatibilité avec les deux conventions.
application = app


# ─────────────────────────────────────────────────────────────────────────────
# Démarrage local uniquement
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    PORT = 5001
    print(f"\n{'='*56}")
    print(f"  ✅  Serveur Apiterapia prêt")
    print(f"  💻  Mac    → http://localhost:{PORT}")
    print(f"  📱  Mobile → http://<ton_IP>:{PORT}  (ipconfig getifaddr en0)")
    print(f"{'='*56}\n")
    app.run(debug=True, host='0.0.0.0', port=PORT, threaded=True)
