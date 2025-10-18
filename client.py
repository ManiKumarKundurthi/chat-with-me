"""
Terminal-based WebSocket Chat Client - Role-Based with Auto URL Selection
"""
import socketio
import threading
import sys
from datetime import datetime
import getpass
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create a Socket.IO client
sio = socketio.Client()

# Client state
username = ""
connected = False
current_room = ""
is_admin = False

def clear_line():
    """Clear the current line in terminal"""
    sys.stdout.write('\r' + ' ' * 80 + '\r')
    sys.stdout.flush()

@sio.event
def connect():
    """Handle connection to server"""
    global connected
    connected = True
    print("\n✓ Connected to server successfully!")

@sio.event
def connection_response(data):
    """Handle connection response from server"""
    print(f"Session ID: {data.get('sid', 'Unknown')}")

@sio.event
def auth_failed(data):
    """Handle authentication failure"""
    print(f"\n✗ {data.get('message', 'Authentication failed')}")
    print("Disconnecting...")
    sio.disconnect()
    sys.exit(1)

@sio.event
def admin_connected(data):
    """Handle admin connection"""
    global is_admin, current_room
    is_admin = True
    current_room = "admin-lobby"

    print(f"\n{data.get('message', '')}")
    print("=" * 50)
    print("ADMIN COMMANDS:")
    print("  /list     - Show all waiting rooms")
    print("  /join <room_id> - Join a specific room")
    print("  quit      - Disconnect")
    print("=" * 50 + "\n")

@sio.event
def waiting_for_admin(data):
    """Handle user waiting in room"""
    global current_room
    current_room = data.get('room_id', '')

    print(f"\n{data.get('message', '')}")
    print("-" * 50)
    print("Waiting for Admin to join your room...")
    print("You'll be notified when Admin arrives.")
    print("-" * 50 + "\n")

@sio.event
def new_room_available(data):
    """Notify admin of new waiting room"""
    room_id = data.get('room_id', '')
    user = data.get('username', '')
    created = datetime.fromisoformat(data.get('created_at', '')).strftime('%H:%M:%S')

    clear_line()
    print(f"\n🔔 NEW ROOM: {room_id} | User: {user} | Time: {created}")
    print(f"   Type '/join {room_id}' to connect")
    print(f"{username}: ", end='', flush=True)

@sio.event
def rooms_list(data):
    """Display list of waiting rooms"""
    rooms = data.get('rooms', [])

    clear_line()
    print("\n" + "=" * 60)
    print("WAITING ROOMS:")
    print("=" * 60)

    if not rooms:
        print("  No rooms waiting")
    else:
        for room in rooms:
            room_id = room['room_id']
            user = room['username']
            created = datetime.fromisoformat(room['created_at']).strftime('%H:%M:%S')
            print(f"  Room ID: {room_id} | User: {user} | Created: {created}")
            print(f"          → Type '/join {room_id}' to connect")
            print()

    print("=" * 60 + "\n")
    print(f"{username}: ", end='', flush=True)

@sio.event
def joined_room(data):
    """Admin successfully joined a room"""
    global current_room
    current_room = data.get('room_id', '')
    user = data.get('username', '')

    clear_line()
    print(f"\n✓ {data.get('message', '')}")
    print(f"Now chatting with: {user}")
    print("-" * 50)
    print("Type your messages below. Type 'quit' to exit.")
    print("-" * 50 + "\n")

@sio.event
def admin_joined(data):
    """User notified that admin joined"""
    clear_line()
    print(f"\n✓ {data.get('message', '')}")
    print("-" * 50 + "\n")
    print(f"{username}: ", end='', flush=True)

@sio.event
def user_left(data):
    """Handle when other user leaves"""
    clear_line()
    print(f"\n>>> {data.get('message', 'User left')} <<<\n")
    if is_admin:
        print("Type /list to see other waiting rooms")
    print(f"{username}: ", end='', flush=True)

@sio.event
def system_message(data):
    """Handle system messages"""
    clear_line()
    print(f"\n[SYSTEM] {data.get('message', '')}")
    print(f"{username}: ", end='', flush=True)

@sio.event
def receive_message(data):
    """Handle incoming messages"""
    timestamp = datetime.fromisoformat(data['timestamp']).strftime('%H:%M:%S')
    sender = data['username']
    message = data['message']

    clear_line()
    print(f"[{timestamp}] {sender}: {message}")
    print(f"{username}: ", end='', flush=True)

@sio.event
def disconnect():
    """Handle disconnection from server"""
    global connected
    connected = False
    print("\n✗ Disconnected from server")

def send_messages():
    """Handle user input and send messages"""
    global username

    while connected:
        try:
            message = input(f"{username}: ")

            if message.lower() == 'quit':
                print("\nDisconnecting...")
                sio.disconnect()
                break

            if is_admin:
                if message.lower() == '/list':
                    sio.emit('list_rooms')
                    continue

                if message.lower().startswith('/join '):
                    room_id = message.split(' ', 1)[1].strip()
                    sio.emit('join_room_by_id', {'room_id': room_id})
                    continue

            if message.strip():
                sys.stdout.write('\033[F')
                clear_line()

                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"[{timestamp}] {username}: {message}")

                sio.emit('send_message', {'message': message})

        except KeyboardInterrupt:
            print("\n\nDisconnecting...")
            sio.disconnect()
            break
        except Exception as e:
            print(f"\nError: {e}")

def main():
    """Main client function"""
    global username, is_admin

    print("=" * 50)
    print("WebSocket Chat Client (Room Queue System)")
    print("=" * 50)

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

            print(f"\nAdmin Login")
            print(f"Username: {username}")
            password = getpass.getpass("Enter password: ")

            # Get admin server URL from environment
            server_url = os.getenv('ADMIN_SERVER_URL')
            print(f"Connecting to: {server_url}")

            break

        elif role_choice == '2':
            # Regular user
            is_admin = False
            username = input("\nEnter your name: ").strip()
            if not username:
                username = "Anonymous"

            password = ""  # No password for regular users

            # Get user server URL from environment
            server_url = os.getenv('USER_SERVER_URL')
            print(f"Connecting to: {server_url}")

            break

        else:
            print("Invalid choice. Please enter 1 or 2.")

    # Connect to server
    try:
        print(f"\nConnecting as {'Admin' if is_admin else 'User'}...")
        sio.connect(server_url)

        # Join the chat
        sio.emit('join_chat', {'username': username, 'password': password})

        # Start message sending thread
        message_thread = threading.Thread(target=send_messages, daemon=True)
        message_thread.start()

        # Keep the client running
        message_thread.join()

    except Exception as e:
        print(f"\n✗ Connection failed: {e}")
        print("\nMake sure the server is running and try again.")
        sys.exit(1)

if __name__ == '__main__':
    main()
