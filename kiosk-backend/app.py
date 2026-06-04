import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit, disconnect
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'fallback-key')

# Allow connections across the local network
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Global Server State to track connected hosts
connected_hosts = set()
PASSWORD = os.getenv('ROOM_PASSWORD', 'default_password')

@app.route('/')
def root():
    # Force authentication check
    if not session.get('authenticated'):
        return redirect(url_for('login_page'))
    return render_template('index.html', role=session.get('role'))

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        data = request.get_json() or {}
        password_input = data.get('password')
        role_input = data.get('role')

        if password_input != PASSWORD:
            return jsonify({'success': False, 'message': 'Invalid password.'}), 401

        if role_input == 'host' and len(connected_hosts) >= 2:
            return jsonify({'success': False, 'message': 'Room full: Maximum of 2 Hosts already active.'}), 400

        session['authenticated'] = True
        session['role'] = role_input
        session['name'] = data.get('name', 'Anonymous')
        return jsonify({'success': True})

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# --- Socket.IO Connection Management ---

@socketio.on('connect')
def handle_connect():
    role = session.get('role')
    auth = session.get('authenticated')

    if not auth or not role:
        return False 

    if role == 'host':
        if len(connected_hosts) < 2:
            connected_hosts.add(request.sid)
            emit('server_status', {'hosts_count': len(connected_hosts)}, broadcast=True)
        else:
            disconnect()

@socketio.on('ready-to-stream')
def handle_ready(data):
    role = session.get('role')
    name = session.get('name', 'Anonymous')
    # Tell all EXISTING clients that a newcomer arrived so they can call them
    emit('peer-joined', {'id': request.sid, 'role': role, 'name': name}, broadcast=True, include_self=False)

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in connected_hosts:
        connected_hosts.remove(request.sid)
        emit('server_status', {'hosts_count': len(connected_hosts)}, broadcast=True)
    
    emit('peer-left', request.sid, broadcast=True)

@socketio.on('signal')
def handle_signal(data):
    target_sid = data.get('target')
    payload = {
        'sender': request.sid,
        'role': session.get('role'),
        'name': session.get('name', 'Anonymous'),
        'sdp': data.get('sdp'),
        'candidate': data.get('candidate')
    }
    if target_sid:
        emit('signal', payload, to=target_sid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)