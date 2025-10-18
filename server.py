"""
WebSocket Chat Server - Simple Room Queue System for Admin
"""
# MUST be first - before any other imports
import eventlet
eventlet.monkey_patch()

from flask import Flask, request, render_template
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime
import uuid
from config import Config
from flask_bcrypt import Bcrypt
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config.from_object(Config)
socketio = SocketIO(app, cors_allowed_origins="*")
bcrypt = Bcrypt(app)

# Store room information
waiting_rooms = {}
active_rooms = {}
active_users = {}
session_rooms = {}

ADMIN_USERNAME = Config.ADMIN_USERNAME
ADMIN_PASSWORD_HASH = Config.ADMIN_PASSWORD_HASH

@app.route('/')
def index():
    """Serve the web chat client"""
    return render_template('chat.html')

@socketio.on('connect')
def handle_connect():
    """Handle new client connections"""
    print(f"\n[SERVER] New connection from {request.sid}")
    emit('connection_response', {'status': 'connected', 'sid': request.sid})

@socketio.on('join_chat')
def handle_join(data):
    """Handle user joining - creates room"""
    username = data.get('username', 'Anonymous')
    password = data.get('password', '')
    session_id = request.sid

    # Admin authentication
    if username == ADMIN_USERNAME:
        if not password or not bcrypt.check_password_hash(ADMIN_PASSWORD_HASH, password):
            emit('auth_failed', {'message': 'Invalid credentials. Access denied.'})
            print(f"[SERVER] Failed admin login from {session_id}")
            return

        active_users[session_id] = username
        print(f"[SERVER] Admin authenticated (Session: {session_id})")
        emit('admin_connected', {
            'message': 'Connected as Admin'
        })
    else:
        # Regular user creates a new room
        active_users[session_id] = username
        room_id = str(uuid.uuid4())[:8]

        waiting_rooms[room_id] = {
            'username': username,
            'session_id': session_id,
            'created_at': datetime.now().isoformat(),
            'room_id': room_id
        }

        session_rooms[session_id] = room_id
        join_room(room_id)

        print(f"[SERVER] {username} created room: {room_id}")

        emit('waiting_for_admin', {
            'room_id': room_id,
            'message': f'Room created! Waiting for Admin to join...'
        })

        # Notify all connected admins
        for sid, uname in active_users.items():
            if uname == ADMIN_USERNAME:
                emit('new_room_available', {
                    'room_id': room_id,
                    'username': username,
                    'created_at': waiting_rooms[room_id]['created_at']
                }, room=sid)

@socketio.on('list_rooms')
def handle_list_rooms():
    """Admin requests list of waiting rooms"""
    session_id = request.sid
    username = active_users.get(session_id)

    if username != ADMIN_USERNAME:
        emit('system_message', {'message': 'Only Admin can list rooms'})
        return

    rooms_list = []
    for room_id, info in waiting_rooms.items():
        rooms_list.append({
            'room_id': room_id,
            'username': info['username'],
            'created_at': info['created_at']
        })

    emit('rooms_list', {'rooms': rooms_list})

@socketio.on('join_room_by_id')
def handle_admin_join_room(data):
    """Admin joins a specific room by room_id"""
    session_id = request.sid
    username = active_users.get(session_id)
    room_id = data.get('room_id')

    if username != ADMIN_USERNAME:
        emit('system_message', {'message': 'Only Admin can join rooms'})
        return

    if room_id not in waiting_rooms:
        emit('system_message', {'message': f'Room {room_id} not found'})
        return

    room_info = waiting_rooms.pop(room_id)
    user_sid = room_info['session_id']
    user_name = room_info['username']

    active_rooms[room_id] = {
        'admin_sid': session_id,
        'user_sid': user_sid,
        'username': user_name
    }

    session_rooms[session_id] = room_id
    join_room(room_id)

    print(f"[SERVER] Admin joined room: {room_id} with {user_name}")

    emit('joined_room', {
        'room_id': room_id,
        'username': user_name,
        'message': f'Joined room with {user_name}'
    })

    emit('admin_joined', {
        'message': 'Admin has joined the chat!'
    }, room=user_sid)

@socketio.on('send_message')
def handle_message(data):
    """Handle incoming messages"""
    session_id = request.sid
    username = active_users.get(session_id, 'Anonymous')
    message_text = data.get('message', '')
    room_id = session_rooms.get(session_id)

    if not message_text.strip():
        return

    if not room_id:
        emit('system_message', {'message': 'You are not in any room yet'})
        return

    if room_id in waiting_rooms:
        emit('system_message', {'message': 'Waiting for Admin to join...'})
        return

    if room_id not in active_rooms:
        emit('system_message', {'message': 'Room is no longer active'})
        return

    message_obj = {
        'username': username,
        'message': message_text,
        'timestamp': datetime.now().isoformat(),
        'room_id': room_id
    }

    print(f"[Room:{room_id}] {username}: {message_text}")

    emit('receive_message', message_obj, room=room_id, include_self=False)

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    session_id = request.sid
    username = active_users.get(session_id, 'Unknown')
    room_id = session_rooms.get(session_id)

    # Remove waiting rooms
    rooms_to_remove = [rid for rid, info in waiting_rooms.items() if info['session_id'] == session_id]
    for rid in rooms_to_remove:
        del waiting_rooms[rid]
        print(f"[SERVER] Removed waiting room: {rid}")

    # Handle active rooms
    if room_id and room_id in active_rooms:
        emit('user_left', {
            'username': username,
            'message': f'{username} has left the chat'
        }, room=room_id, include_self=False)

        del active_rooms[room_id]
        print(f"[SERVER] Room {room_id} closed")

    # Cleanup
    if session_id in active_users:
        del active_users[session_id]
    if session_id in session_rooms:
        del session_rooms[session_id]

    print(f"[SERVER] {username} disconnected")


if __name__ == '__main__':
    print("=" * 50)
    print("WebSocket Chat Server - Simple Version")
    print("=" * 50)

    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 10000)),
        debug=False
    )
