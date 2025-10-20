"""
WebSocket Chat Server - Enhanced with Security & Features
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
import html
from collections import defaultdict
import time
import requests  # For Telegram API
import threading  # For async notifications

app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config.from_object(Config)

# CORS configuration for Render.com deployment
ALLOWED_ORIGINS = [
    "https://chat-with-mani.onrender.com",
    "http://localhost:5000",
]

socketio = SocketIO(
    app, 
    cors_allowed_origins=ALLOWED_ORIGINS,
    ping_timeout=60,
    ping_interval=25
)
bcrypt = Bcrypt(app)

# Store room information
waiting_rooms = {}
active_rooms = {}
active_users = {}
session_rooms = {}
typing_status = {}

# Rate limiting storage
rate_limit_storage = defaultdict(lambda: {'count': 0, 'reset_time': time.time()})

ADMIN_USERNAME = Config.ADMIN_USERNAME
ADMIN_PASSWORD_HASH = Config.ADMIN_PASSWORD_HASH

# Rate limiting constants
MESSAGE_RATE_LIMIT = 10
RATE_LIMIT_WINDOW = 60


# ============================================
# NEW: TELEGRAM NOTIFICATION MODULE
# ============================================

def send_telegram_notification(message_text, parse_mode='Markdown'):
    """
    Send notification to admin via Telegram bot
    Runs asynchronously to not block the main thread
    """
    if not Config.TELEGRAM_NOTIFICATIONS_ENABLED:
        return
    
    def send_async():
        try:
            url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                'chat_id': Config.TELEGRAM_CHAT_ID,
                'text': message_text,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=5)
            
            if response.status_code == 200:
                print(f"[TELEGRAM] Notification sent successfully")
            else:
                print(f"[TELEGRAM] Failed to send: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"[TELEGRAM] Error sending notification: {e}")
    
    # Run in separate thread to not block
    thread = threading.Thread(target=send_async, daemon=True)
    thread.start()


def format_telegram_new_user(username, room_id):
    """Format notification for new user joining"""
    current_time = datetime.now().strftime('%I:%M %p')
    dashboard_url = Config.ADMIN_SERVER_URL or "http://localhost:5000"
    
    message = f"""🔔 *New Chat Request*

👤 *User:* {username}
🆔 *Room:* `{room_id}`
⏰ *Time:* {current_time}

[🔗 Open Dashboard]({dashboard_url})"""
    
    return message


def format_telegram_user_waiting(username, room_id, wait_minutes):
    """Format notification for user waiting too long"""
    dashboard_url = Config.ADMIN_SERVER_URL or "http://localhost:5000"
    
    message = f"""⚠️ *User Waiting {wait_minutes}+ Minutes!*

👤 *User:* {username}
🆔 *Room:* `{room_id}`
⏰ *Waiting:* {wait_minutes} minutes

🔥 *High Priority*
[🔗 Open Dashboard Now]({dashboard_url})"""
    
    return message


def format_telegram_queue_status():
    """Format notification with current queue status"""
    dashboard_url = Config.ADMIN_SERVER_URL or "http://localhost:5000"
    waiting_count = len(waiting_rooms)
    
    if waiting_count == 0:
        return None
    
    message = f"""📊 *Queue Status*

🔢 *{waiting_count} users waiting*

"""
    
    # List up to 5 users
    room_list = list(waiting_rooms.items())[:5]
    for room_id, info in room_list:
        username = info['username']
        created = datetime.fromisoformat(info['created_at'])
        wait_time = (datetime.now() - created).total_seconds() / 60
        message += f"• {username} ({int(wait_time)}m)\n"
    
    if waiting_count > 5:
        message += f"• +{waiting_count - 5} more...\n"
    
    message += f"\n[🔗 Open Dashboard]({dashboard_url})"
    
    return message


# ============================================
# EXISTING FUNCTIONS (with Telegram additions)
# ============================================

def rate_limit_check(session_id, limit=MESSAGE_RATE_LIMIT, window=RATE_LIMIT_WINDOW):
    """Check if user has exceeded rate limit"""
    current_time = time.time()
    user_data = rate_limit_storage[session_id]
    
    if current_time - user_data['reset_time'] > window:
        user_data['count'] = 0
        user_data['reset_time'] = current_time
    
    if user_data['count'] >= limit:
        return False
    
    user_data['count'] += 1
    return True


def sanitize_input(text, max_length=1000):
    """Sanitize and validate user input"""
    if not text or not isinstance(text, str):
        return None
    
    text = text.strip()[:max_length]
    text = html.escape(text)
    
    return text if text else None


def cleanup_old_rooms():
    """Remove rooms older than 2 hours"""
    from datetime import timedelta
    now = datetime.now()
    
    for room_id in list(waiting_rooms.keys()):
        created = datetime.fromisoformat(waiting_rooms[room_id]['created_at'])
        if now - created > timedelta(hours=2):
            print(f"[CLEANUP] Removing stale room: {room_id}")
            del waiting_rooms[room_id]


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
    username = sanitize_input(data.get('username', 'Anonymous'), max_length=50)
    password = data.get('password', '')
    session_id = request.sid
    
    if not username:
        emit('auth_failed', {'message': 'Invalid username'})
        return

    # Admin authentication
    if username == ADMIN_USERNAME:
        if not password or not bcrypt.check_password_hash(ADMIN_PASSWORD_HASH, password):
            emit('auth_failed', {'message': 'Invalid credentials. Access denied.'})
            print(f"[SERVER] Failed admin login from {session_id}")
            return

        active_users[session_id] = username
        print(f"[SERVER] Admin authenticated (Session: {session_id})")
        
        cleanup_old_rooms()
        
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

        # NEW: Send Telegram notification
        notification_message = format_telegram_new_user(username, room_id)
        send_telegram_notification(notification_message)
        print(f"[TELEGRAM] Notification sent for user: {username}")

        # Notify all connected admins
        for sid, uname in active_users.items():
            if uname == ADMIN_USERNAME:
                emit('new_room_available', {
                    'room_id': room_id,
                    'username': username,
                    'created_at': waiting_rooms[room_id]['created_at']
                }, room=sid)


# ... REST OF YOUR EXISTING server.py CODE STAYS THE SAME ...
# (All other @socketio.on handlers remain unchanged)

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
    """Handle incoming messages with rate limiting and validation"""
    session_id = request.sid
    username = active_users.get(session_id, 'Anonymous')
    message_text = sanitize_input(data.get('message', ''))
    room_id = session_rooms.get(session_id)

    if not rate_limit_check(session_id):
        emit('system_message', {
            'message': 'Rate limit exceeded. Please slow down.'
        })
        return

    if not message_text:
        emit('system_message', {'message': 'Message cannot be empty'})
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

    typing_key = f"{room_id}:{session_id}"
    if typing_key in typing_status:
        del typing_status[typing_key]
        emit('user_stopped_typing', {'username': username}, room=room_id, include_self=False)

    emit('receive_message', message_obj, room=room_id, include_self=False)


@socketio.on('typing')
def handle_typing(data):
    """Handle typing indicator"""
    session_id = request.sid
    username = active_users.get(session_id, 'Anonymous')
    room_id = session_rooms.get(session_id)
    is_typing = data.get('typing', False)

    if not room_id or room_id not in active_rooms:
        return

    typing_key = f"{room_id}:{session_id}"

    if is_typing:
        typing_status[typing_key] = True
        emit('user_typing', {'username': username}, room=room_id, include_self=False)
    else:
        if typing_key in typing_status:
            del typing_status[typing_key]
        emit('user_stopped_typing', {'username': username}, room=room_id, include_self=False)


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    session_id = request.sid
    username = active_users.get(session_id, 'Unknown')
    room_id = session_rooms.get(session_id)

    if room_id:
        typing_key = f"{room_id}:{session_id}"
        if typing_key in typing_status:
            del typing_status[typing_key]

    rooms_to_remove = [rid for rid, info in waiting_rooms.items() if info['session_id'] == session_id]
    for rid in rooms_to_remove:
        del waiting_rooms[rid]
        print(f"[SERVER] Removed waiting room: {rid}")

    if room_id and room_id in active_rooms:
        emit('user_left', {
            'username': username,
            'message': f'{username} has left the chat'
        }, room=room_id, include_self=False)

        del active_rooms[room_id]
        print(f"[SERVER] Room {room_id} closed")

    if session_id in active_users:
        del active_users[session_id]
    if session_id in session_rooms:
        del session_rooms[session_id]
    if session_id in rate_limit_storage:
        del rate_limit_storage[session_id]

    print(f"[SERVER] {username} disconnected")


if __name__ == '__main__':
    print("=" * 50)
    print("WebSocket Chat Server - Enhanced Version")
    if Config.TELEGRAM_NOTIFICATIONS_ENABLED:
        print("✅ Telegram Notifications: ENABLED")
    else:
        print("⚠️  Telegram Notifications: DISABLED")
    print("=" * 50)

    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 10000)),
        debug=False
    )
