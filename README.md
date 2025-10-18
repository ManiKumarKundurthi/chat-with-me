# Chat-With-Me 💬

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-socketio-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

A real-time WebSocket chat application with a room queue system where
users create chat rooms and wait for an admin to join. Built with
Flask-SocketIO for seamless real-time communication.

## ✨ Features

-   **Real-time Communication**: Instant messaging using WebSocket
    technology
-   **Room Queue System**: Users create rooms and admins select which
    room to join
-   **Role-Based Access**: Separate interfaces for Admin and regular
    Users
-   **Secure Authentication**: Admin login with bcrypt password hashing
-   **Terminal-Based Client**: Simple command-line interface for
    chatting
-   **Auto-Notifications**: Admins receive real-time alerts when new
    rooms are created
-   **Session Management**: Handles multiple concurrent chat sessions

## 🚀 Quick Start

### Prerequisites

-   Python 3.8 or higher
-   pip (Python package manager)

### Installation

1.  **Clone the repository**

    ``` bash
    git clone https://github.com/ManiKumarKundurthi/chat-with-me.git
    cd chat-with-me
    ```

2.  **Install dependencies**

    ``` bash
    pip install -r requirements.txt
    ```

3.  **Generate Admin Password Hash**

    ``` bash
    python password_hashing.py
    ```

    Replace `'YOUR_PASSWORD'` with your desired admin password. Copy the
    generated hash.

4.  **Configure Environment Variables** Create a `.env` file in the root
    directory:

    ``` bash
    ADMIN_SERVER_URL=http://localhost:5000
    USER_SERVER_URL=http://localhost:5000
    ADMIN_USERNAME=DARK
    ADMIN_PASSWORD_HASH=your_generated_hash_here
    ```

5.  **Run the Server**

    ``` bash
    python server.py
    ```

6.  **Run the Client** (in a separate terminal)

    ``` bash
    python client.py
    ```

## 📖 Usage

### For Users

1.  Run `client.py`
2.  Select option `2` (User)
3.  Enter your name
4.  Wait for admin to join your room
5.  Start chatting!

### For Admin

1.  Run `client.py`
2.  Select option `1` (Admin)
3.  Enter admin password
4.  Use commands:
    -   `/list` - View all waiting rooms
    -   `/join <room_id>` - Join a specific room
    -   Type messages to chat
    -   `quit` - Disconnect

## 🏗️ Project Structure

    chat-with-me/
    │
    ├── server.py
    ├── client.py
    ├── config.py
    ├── password_hashing.py
    ├── requirements.txt
    ├── .env
    └── README.md

## 🛠️ Technologies Used

-   **Flask**
-   **Flask-SocketIO**
-   **Flask-Bcrypt**
-   **python-socketio**
-   **eventlet**
-   **python-dotenv**

## 🔒 Security Features

-   **Bcrypt Password Hashing**
-   **Environment Variables**
-   **Session Management**
-   **CORS Protection**

## 📝 Configuration

Edit `config.py` to customize settings.

## 🐛 Troubleshooting

-   Ensure server is running
-   Check ports and `.env` file values

## 🤝 Contributing

1.  Fork the repository
2.  Create a branch
3.  Commit changes
4.  Push and open PR

## 📄 License

MIT License

## 👤 Author

**Your Name** - GitHub: [@ManiKumarKundurthi](https://github.com/ManiKumarKundurthi)

## 🙏 Acknowledgments

-   Flask-SocketIO community

------------------------------------------------------------------------

Made with ❤️ using Python and Flask-SocketIO
