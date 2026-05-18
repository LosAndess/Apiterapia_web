"""
Apiterapia con Vero — Serveur Flask
=====================================
Lancer avec :  python app.py

Le serveur écoute sur :
  → http://localhost:5001      (Mac)
  → http://<IP_locale>:5001    (mobile sur le même Wi-Fi)

IP locale : ipconfig getifaddr en0
"""

from flask import Flask, render_template, request, jsonify
import json
import os
import urllib.parse
from datetime import datetime

app = Flask(__name__)

# Chemin absolu vers appointments.json — même répertoire que ce fichier,
# peu importe depuis quel dossier le terminal est lancé.
APPOINTMENTS_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'appointments.json')
)


# ─────────────────────────────────────────────────────────────────────────────
# Gestionnaires d'erreurs globaux
# Garantissent que Flask retourne TOUJOURS du JSON, jamais une page HTML.
# Sans ça, une exception Python dans une route renvoie du HTML → le JS ne
# peut pas parser → SyntaxError → "Error de conexión" affiché à tort.
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
# En-têtes anti-cache (appliqués sur toutes les réponses)
# ─────────────────────────────────────────────────────────────────────────────

@app.after_request
def apply_no_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma']        = 'no-cache'
    response.headers['Expires']       = '0'
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Helpers JSON
# ─────────────────────────────────────────────────────────────────────────────

def load_appointments():
    """Charge les rendez-vous. Retourne [] si fichier absent ou corrompu."""
    if not os.path.exists(APPOINTMENTS_FILE):
        return []
    with open(APPOINTMENTS_FILE, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, ValueError):
            return []


def save_appointments(appointments):
    """Écrit la liste dans appointments.json (création automatique si absent)."""
    with open(APPOINTMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(appointments, f, ensure_ascii=False, indent=2)


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
      400 → champs manquants
      409 → créneau déjà pris
      500 → erreur serveur
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

    # Vérification anti-doublon : on relit le fichier depuis le disque
    # à chaque requête — jamais depuis un cache mémoire.
    appointments = load_appointments()

    for appt in appointments:
        if appt.get('date') == date and appt.get('time') == slot:
            return jsonify({'error': 'duplicate',
                            'message': 'Este horario ya está reservado'}), 409

    # Sauvegarde
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
# Démarrage
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    PORT = 5001

    print(f"\n{'='*56}")
    print(f"  ✅  Serveur Apiterapia prêt")
    print(f"  📂  JSON  → {APPOINTMENTS_FILE}")
    print(f"  💻  Mac   → http://localhost:{PORT}")
    print(f"  📱  Mobile → http://<ton_IP>:{PORT}")
    print(f"  ⚠️   Mode  → DEBUG (désactiver avant mise en ligne)")
    print(f"{'='*56}\n")

    # debug=True : affiche les erreurs Python dans le terminal
    # → indispensable pour diagnostiquer les problèmes en développement
    app.run(debug=True, host='0.0.0.0', port=PORT, threaded=True)
