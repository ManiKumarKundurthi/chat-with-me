"""
WebSocket Chat Server - Room Queue System for Admin with Authentication
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
from threading import Timer

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
cleanup_timers = {}

ADMIN_USERNAME = Config.ADMIN_USERNAME
ADMIN_PASSWORD_HASH = Config.ADMIN_PASSWORD_HASH

@app.route('/')
def index():
    """Serve the web chat client"""
    return render_template('chat.html')

@socketio.on('connect')
def handle_connect():
    """Handle new client connections"""
    print(f"\n[SERVER] New connection attempt from {request.sid}")
    emit('connection_response', {'status': 'connected', 'sid': request.sid})

def cleanup_abandoned_room(room_id):
    """Clean up room if user hasn't reconnected within timeout"""
    if room_id in waiting_rooms:
        room_info = waiting_rooms[room_id]
        session_id = room_info.get('session_id')
        
        if session_id not in active_users:
            print(f"[SERVER] Cleaning up abandoned waiting room: {room_id}")
            del waiting_rooms[room_id]
    
    if room_id in active_rooms:
        room_info = active_rooms[room_id]
        user_sid = room_info.get('user_sid')
        
        if user_sid not in active_users:
            print(f"[SERVER] Cleaning up abandoned active room: {room_id}")
            admin_sid = room_info.get('admin_sid')
            if admin_sid:
                socketio.emit('system_message', {
                    'message': f'{room_info.get("username")} did not reconnect. Room closed.'
                }, room=admin_sid)
            del active_rooms[room_id]
    
    if room_id in cleanup_timers:
        del cleanup_timers[room_id]

@socketio.on('join_chat')
def handle_join(data):
    """Handle user joining - creates or rejoins room"""
    username = data.get('username', 'Anonymous')
    password = data.get('password', '')
    requested_room_id = data.get('room_id', None)  # Client sends preferred room ID
    session_id = request.sid

    # Admin authentication
    if username == ADMIN_USERNAME:
        if not password or not bcrypt.check_password_hash(ADMIN_PASSWORD_HASH, password):
            emit('auth_failed', {'message': 'Invalid credentials. Access denied.'})
            print(f"[SERVER] Failed admin login attempt from {session_id}")
            return

        active_users[session_id] = username
        print(f"[SERVER] Admin authenticated successfully (Session: {session_id})")
        emit('admin_connected', {
            'message': 'Connected as Admin. Use /list to see waiting rooms, /join <room_id> to enter a room.'
        })
    else:
        # Regular user - use their persistent room ID or create one
        active_users[session_id] = username
        
        # Use client-provided room_id if available, otherwise generate one
        if requested_room_id:
            room_id = requested_room_id
            
            # Cancel cleanup timer if user is reconnecting
            if room_id in cleanup_timers:
                cleanup_timers[room_id].cancel()
                del cleanup_timers[room_id]
                print(f"[SERVER] User {username} reconnecting - cancelled cleanup timer for room {room_id}")
            
            print(f"[SERVER] User {username} requesting specific room: {room_id}")
        else:
            # Fallback: generate room ID server-side (shouldn't happen with updated client)
            room_id = str(uuid.uuid4())[:8]
            print(f"[SERVER] Generated new room ID for {username}: {room_id}")
        
        # Check if this room already exists
        if room_id in waiting_rooms:
            # User is rejoining their existing waiting room
            print(f"[SERVER] {username} rejoining existing waiting room: {room_id}")
            waiting_rooms[room_id]['session_id'] = session_id
            session_rooms[session_id] = room_id
            join_room(room_id)
            
            emit('waiting_for_admin', {
                'room_id': room_id,
                'message': f'Reconnected to room. Waiting for Admin to join...'
            })
            
        elif room_id in active_rooms:
            # User is rejoining their active chat room
            print(f"[SERVER] {username} rejoining active room: {room_id}")
            active_rooms[room_id]['user_sid'] = session_id
            session_rooms[session_id] = room_id
            join_room(room_id)
            
            emit('waiting_for_admin', {
                'room_id': room_id,
                'message': f'Reconnected to chat with Admin'
            })
            
            # Notify admin about reconnection
            admin_sid = active_rooms[room_id].get('admin_sid')
            if admin_sid:
                emit('system_message', {
                    'message': f'✅ {username} has reconnected'
                }, room=admin_sid)
                
        else:
            # Create new waiting room
            waiting_rooms[room_id] = {
                'username': username,
                'session_id': session_id,
                'created_at': datetime.now().isoformat(),
                'room_id': room_id
            }

            session_rooms[session_id] = room_id
            join_room(room_id)

            print(f"[SERVER] {username} created room: {room_id} (Session: {session_id})")

            emit('waiting_for_admin', {
                'room_id': room_id,
                'message': f'Room created! Room ID: {room_id}. Waiting for Admin to join...'
            })

            # Notify all connected admins about new room
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
        emit('system_message', {'message': f'Room {room_id} not found or already active'})
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
        'message': f'Joined room {room_id} with {user_name}'
    })

    emit('admin_joined', {
        'message': 'Admin has joined the chat! You can start talking.'
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

@socketio.on('intentional_disconnect')
def handle_intentional_disconnect(data):
    """Handle explicit disconnect (user clicked disconnect button)"""
    session_id = request.sid
    username = data.get('username', 'Unknown')
    room_id = data.get('room_id')
    
    print(f"[SERVER] {username} intentionally disconnected from room {room_id}")
    
    # Cancel any cleanup timers
    if room_id and room_id in cleanup_timers:
        cleanup_timers[room_id].cancel()
        del cleanup_timers[room_id]
    
    # Immediately clean up the room
    if room_id in waiting_rooms:
        del waiting_rooms[room_id]
        print(f"[SERVER] Removed waiting room: {room_id}")
    
    if room_id in active_rooms:
        # Notify the other person
        admin_sid = active_rooms[room_id].get('admin_sid')
        user_sid = active_rooms[room_id].get('user_sid')
        
        if admin_sid == session_id:
            # Admin left intentionally
            if user_sid:
                emit('user_left', {
                    'username': 'Admin',
                    'message': 'Admin has ended the chat session.'
                }, room=user_sid)
        else:
            # User left intentionally
            if admin_sid:
                emit('user_left', {
                    'username': username,
                    'message': f'{username} has ended the chat session.'
                }, room=admin_sid)
        
        del active_rooms[room_id]
        print(f"[SERVER] Removed active room: {room_id}")

@socketio.on('page_closed')
def handle_page_closed(data):
    """Handle page close (tab/browser closed, not refresh)"""
    session_id = request.sid
    username = data.get('username', 'Unknown')
    room_id = data.get('room_id')
    
    print(f"[SERVER] {username} closed browser/tab - room {room_id}")
    
    # Cancel cleanup timer and remove immediately
    if room_id and room_id in cleanup_timers:
        cleanup_timers[room_id].cancel()
        del cleanup_timers[room_id]
    
    # Clean up room immediately
    if room_id in waiting_rooms:
        del waiting_rooms[room_id]
    
    if room_id in active_rooms:
        admin_sid = active_rooms[room_id].get('admin_sid')
        if admin_sid and admin_sid != session_id:
            emit('user_left', {
                'username': username,
                'message': f'{username} closed their browser/tab.'
            }, room=admin_sid)
        
        del active_rooms[room_id]

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection - only preserve rooms for refresh reconnects"""
    session_id = request.sid
    username = active_users.get(session_id, 'Unknown')
    room_id = session_rooms.get(session_id)

    print(f"[SERVER] {username} disconnected (Session: {session_id}) - assuming refresh")

    # Only give grace period for potential refresh reconnects
    if room_id:
        # Cancel any existing timer
        if room_id in cleanup_timers:
            cleanup_timers[room_id].cancel()
        
        # Give 10 seconds for refresh (shorter since page close is handled separately)
        timer = Timer(10.0, cleanup_abandoned_room, [room_id])
        timer.start()
        cleanup_timers[room_id] = timer
        
        if room_id in active_rooms:
            if active_rooms[room_id].get('user_sid') == session_id:
                print(f"[SERVER] User {username} disconnected (refresh expected) - 10s grace period")
                admin_sid = active_rooms[room_id].get('admin_sid')
                if admin_sid:
                    emit('system_message', {
                        'message': f'⚠️ {username} disconnected (refreshing page...)'
                    }, room=admin_sid)
                    
            elif active_rooms[room_id].get('admin_sid') == session_id:
                print(f"[SERVER] Admin disconnected from room {room_id}")
                user_sid = active_rooms[room_id].get('user_sid')
                user_name = active_rooms[room_id].get('username')
                
                waiting_rooms[room_id] = {
                    'username': user_name,
                    'session_id': user_sid,
                    'created_at': datetime.now().isoformat(),
                    'room_id': room_id
                }
                
                if user_sid:
                    emit('user_left', {
                        'username': 'Admin',
                        'message': 'Admin left. Waiting for admin to rejoin...'
                    }, room=user_sid)
                
                del active_rooms[room_id]
                if room_id in cleanup_timers:
                    cleanup_timers[room_id].cancel()
                    del cleanup_timers[room_id]
    
    if session_id in active_users:
        del active_users[session_id]
    if session_id in session_rooms:
        del session_rooms[session_id]


if __name__ == '__main__':
    print("=" * 50)
    print("WebSocket Chat Server (Room Queue System)")
    print("With Persistent Rooms & Smart Reconnection")
    print("=" * 50)

    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 10000)),
        debug=False
    )
