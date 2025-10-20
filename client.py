"""
Terminal-based WebSocket Chat Client - Enhanced Version
Features: Role-based access, auto-reconnection, better error handling, typing indicators
"""
import socketio
import threading
import sys
from datetime import datetime
import getpass
import os
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Create a Socket.IO client with enhanced configuration
sio = socketio.Client(
    reconnection=True,
    reconnection_attempts=5,
    reconnection_delay=1,
    reconnection_delay_max=5,
    logger=False,
    engineio_logger=False
)

# Client state
username = ""
connected = False
current_room = ""
is_admin = False
typing_timer = None
is_typing = False
TYPING_TIMER_LENGTH = 2  # seconds

# ============================================
# UTILITY FUNCTIONS
# ============================================

def clear_line():
    """Clear the current line in terminal"""
    sys.stdout.write('\r' + ' ' * 100 + '\r')
    sys.stdout.flush()


def print_message(message, color=None):
    """Print colored message to terminal"""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'cyan': '\033[96m',
        'reset': '\033[0m'
    }
    
    if color and color in colors:
        print(f"{colors[color]}{message}{colors['reset']}")
    else:
        print(message)


def validate_input(text, max_length=1000):
    """Validate user input"""
    if not text:
        return False
    if len(text) > max_length:
        print_message(f"\n✗ Message too long (max {max_length} characters)", 'red')
        return False
    return True


# ============================================
# SOCKET.IO EVENT HANDLERS
# ============================================

@sio.event
def connect():
    """Handle connection to server"""
    global connected
    connected = True
    print_message("\n✓ Connected to server successfully!", 'green')


@sio.event
def connect_error(data):
    """Handle connection errors"""
    print_message(f"\n✗ Connection error: {data}", 'red')


@sio.event
def disconnect():
    """Handle disconnection from server"""
    global connected
    connected = False
    print_message("\n✗ Disconnected from server", 'red')


@sio.event
def connection_response(data):
    """Handle connection response from server"""
    session_id = data.get('sid', 'Unknown')
    print_message(f"Session ID: {session_id}", 'cyan')


@sio.event
def auth_failed(data):
    """Handle authentication failure"""
    print_message(f"\n✗ {data.get('message', 'Authentication failed')}", 'red')
    print_message("Disconnecting...", 'yellow')
    sio.disconnect()
    sys.exit(1)


@sio.event
def admin_connected(data):
    """Handle admin connection"""
    global is_admin, current_room
    is_admin = True
    current_room = "admin-lobby"

    print_message(f"\n{data.get('message', '')}", 'green')
    print("=" * 60)
    print_message("ADMIN COMMANDS:", 'cyan')
    print("  /list              - Show all waiting rooms")
    print("  /join <room_id>    - Join a specific room")
    print("  /refresh           - Refresh room list")
    print("  quit               - Disconnect")
    print("=" * 60 + "\n")


@sio.event
def waiting_for_admin(data):
    """Handle user waiting in room"""
    global current_room
    current_room = data.get('room_id', '')

    print_message(f"\n{data.get('message', '')}", 'yellow')
    print("-" * 60)
    print("Waiting for Admin to join your room...")
    print("You'll be notified when Admin arrives.")
    print("-" * 60 + "\n")


@sio.event
def new_room_available(data):
    """Notify admin of new waiting room"""
    room_id = data.get('room_id', '')
    user = data.get('username', '')
    created = datetime.fromisoformat(data.get('created_at', '')).strftime('%H:%M:%S')

    clear_line()
    print_message(f"\n🔔 NEW ROOM AVAILABLE", 'yellow')
    print_message(f"   Room ID: {room_id}", 'cyan')
    print_message(f"   User: {user} | Time: {created}", 'cyan')
    print_message(f"   Type '/join {room_id}' to connect\n", 'green')
    print(f"{username}: ", end='', flush=True)


@sio.event
def rooms_list(data):
    """Display list of waiting rooms"""
    rooms = data.get('rooms', [])

    clear_line()
    print("\n" + "=" * 70)
    print_message("WAITING ROOMS:", 'cyan')
    print("=" * 70)

    if not rooms:
        print_message("  No rooms waiting", 'yellow')
    else:
        for idx, room in enumerate(rooms, 1):
            room_id = room['room_id']
            user = room['username']
            created = datetime.fromisoformat(room['created_at']).strftime('%H:%M:%S')
            print(f"\n  [{idx}] Room ID: {room_id}")
            print(f"      User: {user} | Created: {created}")
            print_message(f"      → Type '/join {room_id}' to connect", 'green')

    print("=" * 70 + "\n")
    print(f"{username}: ", end='', flush=True)


@sio.event
def joined_room(data):
    """Admin successfully joined a room"""
    global current_room
    current_room = data.get('room_id', '')
    user = data.get('username', '')

    clear_line()
    print_message(f"\n✓ {data.get('message', '')}", 'green')
    print_message(f"Now chatting with: {user}", 'cyan')
    print("-" * 60)
    print("Type your messages below. Type 'quit' to exit.")
    print("-" * 60 + "\n")


@sio.event
def admin_joined(data):
    """User notified that admin joined"""
    clear_line()
    print_message(f"\n✓ {data.get('message', '')}", 'green')
    print("-" * 60 + "\n")
    print(f"{username}: ", end='', flush=True)


@sio.event
def user_left(data):
    """Handle when other user leaves"""
    clear_line()
    print_message(f"\n>>> {data.get('message', 'User left')} <<<", 'red')
    if is_admin:
        print_message("Type /list to see other waiting rooms", 'yellow')
    print(f"\n{username}: ", end='', flush=True)


@sio.event
def system_message(data):
    """Handle system messages"""
    clear_line()
    print_message(f"\n[SYSTEM] {data.get('message', '')}", 'yellow')
    print(f"{username}: ", end='', flush=True)


@sio.event
def receive_message(data):
    """Handle incoming messages"""
    timestamp = datetime.fromisoformat(data['timestamp']).strftime('%H:%M:%S')
    sender = data['username']
    message = data['message']

    clear_line()
    print_message(f"[{timestamp}] {sender}: {message}", 'cyan')
    print(f"{username}: ", end='', flush=True)


@sio.event
def user_typing(data):
    """Handle typing indicator"""
    typing_user = data.get('username', 'User')
    clear_line()
    print_message(f"{typing_user} is typing...", 'magenta')
    print(f"{username}: ", end='', flush=True)


@sio.event
def user_stopped_typing(data):
    """Handle stopped typing"""
    clear_line()
    print(f"{username}: ", end='', flush=True)


# ============================================
# TYPING INDICATOR
# ============================================

def handle_typing():
    """Handle typing indicator"""
    global typing_timer, is_typing
    
    if not is_typing:
        is_typing = True
        sio.emit('typing', {'typing': True})
    
    # Cancel existing timer
    if typing_timer:
        typing_timer.cancel()
    
    # Set new timer to stop typing
    typing_timer = threading.Timer(TYPING_TIMER_LENGTH, stop_typing)
    typing_timer.start()


def stop_typing():
    """Stop typing indicator"""
    global is_typing
    if is_typing:
        is_typing = False
        sio.emit('typing', {'typing': False})


# ============================================
# MESSAGE SENDING
# ============================================

def send_messages():
    """Handle user input and send messages"""
    global username

    while connected:
        try:
            message = input(f"{username}: ")

            # Handle quit command
            if message.lower() == 'quit':
                print_message("\nDisconnecting...", 'yellow')
                sio.disconnect()
                break

            # Admin commands
            if is_admin:
                if message.lower() == '/list' or message.lower() == '/refresh':
                    sio.emit('list_rooms')
                    continue

                if message.lower().startswith('/join '):
                    room_id = message.split(' ', 1)[1].strip()
                    if room_id:
                        sio.emit('join_room_by_id', {'room_id': room_id})
                    else:
                        print_message("Usage: /join <room_id>", 'red')
                    continue
                
                if message.lower() == '/help':
                    print("\nAvailable Commands:")
                    print("  /list or /refresh  - Show waiting rooms")
                    print("  /join <room_id>    - Join a room")
                    print("  quit               - Exit\n")
                    continue

            # Validate message
            if not validate_input(message):
                continue

            # Stop typing indicator
            stop_typing()

            # Clear the input line and show sent message
            sys.stdout.write('\033[F')  # Move cursor up
            clear_line()

            timestamp = datetime.now().strftime('%H:%M:%S')
            print_message(f"[{timestamp}] {username}: {message}", 'blue')

            # Send message to server
            sio.emit('send_message', {'message': message})
            
            # Trigger typing indicator for next input
            if message.strip():
                handle_typing()

        except KeyboardInterrupt:
            print_message("\n\nDisconnecting...", 'yellow')
            sio.disconnect()
            break
        except EOFError:
            print_message("\n\nInput stream closed. Disconnecting...", 'yellow')
            sio.disconnect()
            break
        except Exception as e:
            print_message(f"\nError: {e}", 'red')


# ============================================
# MAIN FUNCTION
# ============================================

def main():
    """Main client function"""
    global username, is_admin

    print("=" * 60)
    print_message("WebSocket Chat Client - Enhanced Version", 'cyan')
    print("=" * 60)

    # Ask user role
    print("\nSelect your role:")
    print("1. Admin")
    print("2. User")

    while True:
        role_choice = input("\nEnter your choice (1 or 2): ").strip()

        if role_choice == '1':
            # Admin login
            is_admin = True
            username = os.getenv('ADMIN_USERNAME', 'DARK')

            print_message(f"\nAdmin Login", 'yellow')
            print(f"Username: {username}")
            password = getpass.getpass("Enter password: ")

            if not password:
                print_message("Password cannot be empty", 'red')
                continue

            # Get admin server URL from environment
            server_url = os.getenv('ADMIN_SERVER_URL', 'http://localhost:5000')
            print_message(f"Connecting to: {server_url}", 'cyan')

            break

        elif role_choice == '2':
            # Regular user
            is_admin = False
            username = input("\nEnter your name: ").strip()
            
            if not username:
                username = "Anonymous"
            
            if len(username) > 50:
                print_message("Name too long (max 50 characters)", 'red')
                continue

            password = ""  # No password for regular users

            # Get user server URL from environment
            server_url = os.getenv('USER_SERVER_URL', 'http://localhost:5000')
            print_message(f"Connecting to: {server_url}", 'cyan')

            break

        else:
            print_message("Invalid choice. Please enter 1 or 2.", 'red')

    # Connect to server
    try:
        print_message(f"\nConnecting as {'Admin' if is_admin else 'User'}...", 'yellow')
        
        # Connect with timeout
        sio.connect(server_url, wait_timeout=10)

        # Join the chat
        sio.emit('join_chat', {'username': username, 'password': password})

        # Start message sending thread
        message_thread = threading.Thread(target=send_messages, daemon=True)
        message_thread.start()

        # Keep the client running
        message_thread.join()

    except socketio.exceptions.ConnectionError as e:
        print_message(f"\n✗ Connection failed: {e}", 'red')
        print_message("\nPossible issues:", 'yellow')
        print("  1. Server is not running")
        print("  2. Incorrect server URL")
        print("  3. Network connectivity issues")
        print("  4. Firewall blocking the connection")
        sys.exit(1)
    except KeyboardInterrupt:
        print_message("\n\nExiting...", 'yellow')
        if sio.connected:
            sio.disconnect()
        sys.exit(0)
    except Exception as e:
        print_message(f"\n✗ Unexpected error: {e}", 'red')
        if sio.connected:
            sio.disconnect()
        sys.exit(1)
    finally:
        # Cleanup
        if typing_timer:
            typing_timer.cancel()
        print_message("\nGoodbye! 👋", 'green')


if __name__ == '__main__':
    main()
