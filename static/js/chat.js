/**
 * Chat Application - Client Side Logic
 * Handles WebSocket connections, UI updates, typing indicators, and admin dashboard
 */

// ============================================
// APPLICATION STATE
// ============================================
const ChatApp = {
    socket: null,
    isAdmin: false,
    username: '',
    availableRooms: {},
    currentRoomId: '',
    typingTimeout: null,
    isTyping: false,
    TYPING_TIMER_LENGTH: 2000 // 2 seconds
};

// ============================================
// INITIALIZATION
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
});

/**
 * Initialize all event listeners
 */
function initializeEventListeners() {
    // Role selection buttons
    document.querySelectorAll('.role-btn').forEach(btn => {
        btn.addEventListener('click', handleRoleSelection);
    });

    // Connect button
    document.getElementById('connectBtn').addEventListener('click', connect);

    // Disconnect button
    document.getElementById('disconnectBtn').addEventListener('click', disconnectChat);

    // Send message button
    document.getElementById('sendBtn').addEventListener('click', sendMessage);

    // Message input - Enter key and typing indicator
    const messageInput = document.getElementById('messageInput');
    messageInput.addEventListener('keypress', handleKeyPress);
    messageInput.addEventListener('input', handleTyping);

    // Room dropdown
    document.getElementById('roomDropdown').addEventListener('change', joinSelectedRoom);

    // Refresh rooms button
    const refreshBtn = document.getElementById('refreshRoomsBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshRooms);
    }

    // Username/password Enter key
    document.getElementById('username').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') connect();
    });
    document.getElementById('password').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') connect();
    });
}

// ============================================
// ROLE SELECTION
// ============================================
/**
 * Handle role selection (User vs Admin)
 */
function handleRoleSelection(event) {
    // Update active button
    document.querySelectorAll('.role-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');

    // Update form fields
    const role = event.target.dataset.role;
    ChatApp.isAdmin = (role === 'admin');

    document.getElementById('userFields').classList.toggle('hidden', ChatApp.isAdmin);
    document.getElementById('adminFields').classList.toggle('hidden', !ChatApp.isAdmin);
}

// ============================================
// CONNECTION MANAGEMENT
// ============================================
/**
 * Connect to the server
 */
function connect() {
    // Get credentials
    ChatApp.username = ChatApp.isAdmin 
        ? 'DARK' 
        : document.getElementById('username').value.trim();
    
    const password = ChatApp.isAdmin 
        ? document.getElementById('password').value 
        : '';

    // Validation
    if (!ChatApp.username) {
        alert('Please enter your name');
        return;
    }

    if (ChatApp.username.length > 50) {
        alert('Name is too long (max 50 characters)');
        return;
    }

    if (ChatApp.isAdmin && !password) {
        alert('Please enter admin password');
        return;
    }

    try {
        // Create socket connection with automatic protocol detection
        // Socket.IO automatically uses wss:// on HTTPS and ws:// on HTTP
        ChatApp.socket = io({
            transports: ['websocket', 'polling'],
            upgrade: true,
            reconnection: true,
            reconnectionAttempts: 5,
            reconnectionDelay: 1000
        });

        setupSocketListeners();

        // Send join request
        ChatApp.socket.emit('join_chat', { 
            username: ChatApp.username, 
            password: password 
        });

        // Switch to chat interface
        document.getElementById('loginBox').classList.add('hidden');
        document.getElementById('chatBox').classList.remove('hidden');
        
    } catch (error) {
        console.error('Connection error:', error);
        alert('Failed to connect to server. Please try again.');
    }
}

/**
 * Disconnect from chat
 */
function disconnectChat() {
    if (ChatApp.socket) {
        ChatApp.socket.disconnect();
    }
    
    document.getElementById('chatBox').classList.add('hidden');
    document.getElementById('loginBox').classList.add('hidden');
    showThankYouScreen();
}

// ============================================
// SOCKET.IO EVENT LISTENERS
// ============================================
/**
 * Setup all Socket.IO event listeners
 */
function setupSocketListeners() {
    ChatApp.socket.on('connect', handleConnect);
    ChatApp.socket.on('disconnect', handleDisconnect);
    ChatApp.socket.on('connect_error', handleConnectionError);
    ChatApp.socket.on('auth_failed', handleAuthFailed);
    ChatApp.socket.on('admin_connected', handleAdminConnected);
    ChatApp.socket.on('waiting_for_admin', handleWaitingForAdmin);
    ChatApp.socket.on('admin_joined', handleAdminJoined);
    ChatApp.socket.on('joined_room', handleJoinedRoom);
    ChatApp.socket.on('new_room_available', handleNewRoomAvailable);
    ChatApp.socket.on('rooms_list', handleRoomsList);
    ChatApp.socket.on('receive_message', handleReceiveMessage);
    ChatApp.socket.on('system_message', handleSystemMessage);
    ChatApp.socket.on('user_left', handleUserLeft);
    ChatApp.socket.on('user_typing', handleUserTyping);
    ChatApp.socket.on('user_stopped_typing', handleUserStoppedTyping);
}

// ============================================
// SOCKET EVENT HANDLERS
// ============================================
function handleConnect() {
    console.log('Connected to server');
    showStatus('Connected', 'connected');
}

function handleDisconnect() {
    console.log('Disconnected from server');
    showStatus('Disconnected - Attempting to reconnect...', 'waiting');
}

function handleConnectionError(error) {
    console.error('Connection error:', error);
    showStatus('Connection failed. Please check your internet.', 'waiting');
}

function handleAuthFailed(data) {
    alert(data.message);
    location.reload();
}

function handleAdminConnected(data) {
    showStatus('Connected as Admin - Managing Chats', 'connected');
    
    document.getElementById('commands').classList.remove('hidden');
    document.getElementById('adminDashboard').classList.remove('hidden');
    document.getElementById('welcomeMessage').classList.add('hidden');
    
    // Request room list
    ChatApp.socket.emit('list_rooms');
}

function handleWaitingForAdmin(data) {
    ChatApp.currentRoomId = data.room_id;
    showStatus(data.message, 'waiting');
    
    document.getElementById('welcomeMessage').classList.remove('hidden');
    addMessage(data.message, 'system');
}

function handleAdminJoined(data) {
    showStatus('Admin has joined! You can start chatting.', 'connected');
    document.getElementById('welcomeMessage').classList.add('hidden');
    addMessage('✅ ' + data.message, 'system');
    
    // Focus on message input
    document.getElementById('messageInput').focus();
}

function handleJoinedRoom(data) {
    ChatApp.currentRoomId = data.room_id;
    showStatus(`💬 Chatting with: ${data.username}`, 'connected');
    
    document.getElementById('adminDashboard').classList.add('hidden');
    addMessage(`✅ ${data.message}`, 'system');
    
    // Update active chats count
    updateDashboardStats();
    
    // Focus on message input
    document.getElementById('messageInput').focus();
}

function handleNewRoomAvailable(data) {
    addMessage(`🔔 New user waiting: ${data.username}`, 'system');
    
    ChatApp.availableRooms[data.room_id] = {
        username: data.username,
        created_at: data.created_at
    };
    
    updateRoomDropdown();
    updateDashboardStats();
    
    // Play notification sound (optional)
    playNotificationSound();
}

function handleRoomsList(data) {
    ChatApp.availableRooms = {};
    
    data.rooms.forEach(room => {
        ChatApp.availableRooms[room.room_id] = {
            username: room.username,
            created_at: room.created_at
        };
    });
    
    updateRoomDropdown();
    updateDashboardStats();
}

function handleReceiveMessage(data) {
    const timestamp = new Date(data.timestamp).toLocaleTimeString([], { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
    
    addMessage(`${data.username}: ${data.message}`, 'other', timestamp);
    
    // Hide typing indicator when message received
    hideTypingIndicator();
}

function handleSystemMessage(data) {
    addMessage(data.message, 'system');
}

function handleUserLeft(data) {
    addMessage(data.message, 'system');
    
    if (ChatApp.isAdmin) {
        document.getElementById('adminDashboard').classList.remove('hidden');
        ChatApp.socket.emit('list_rooms');
    }
    
    // Hide typing indicator
    hideTypingIndicator();
}

function handleUserTyping(data) {
    showTypingIndicator(data.username);
}

function handleUserStoppedTyping(data) {
    hideTypingIndicator();
}

// ============================================
// MESSAGE HANDLING
// ============================================
/**
 * Send a message
 */
function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    if (message.length > 1000) {
        alert('Message is too long (max 1000 characters)');
        return;
    }
    
    // Stop typing indicator
    stopTyping();
    
    // Send message
    ChatApp.socket.emit('send_message', { message });
    
    // Display own message
    const timestamp = new Date().toLocaleTimeString([], { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
    addMessage(`You: ${message}`, 'own', timestamp);
    
    // Clear input
    input.value = '';
}

/**
 * Handle key press in message input
 */
function handleKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

/**
 * Add message to chat display
 */
function addMessage(text, type, timestamp = null) {
    const messagesDiv = document.getElementById('messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    if (timestamp && type !== 'system') {
        const timeSpan = document.createElement('div');
        timeSpan.style.fontSize = '11px';
        timeSpan.style.opacity = '0.7';
        timeSpan.style.marginTop = '4px';
        timeSpan.textContent = timestamp;
        
        const textNode = document.createTextNode(text);
        messageDiv.appendChild(textNode);
        messageDiv.appendChild(timeSpan);
    } else {
        messageDiv.textContent = text;
    }
    
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// ============================================
// TYPING INDICATOR
// ============================================
/**
 * Handle typing in message input
 */
function handleTyping() {
    if (!ChatApp.currentRoomId || !ChatApp.socket) return;
    
    // Send typing start event if not already typing
    if (!ChatApp.isTyping) {
        ChatApp.isTyping = true;
        ChatApp.socket.emit('typing', { typing: true });
    }
    
    // Clear existing timeout
    clearTimeout(ChatApp.typingTimeout);
    
    // Set new timeout to stop typing after inactivity
    ChatApp.typingTimeout = setTimeout(() => {
        stopTyping();
    }, ChatApp.TYPING_TIMER_LENGTH);
}

/**
 * Stop typing indicator
 */
function stopTyping() {
    if (ChatApp.isTyping && ChatApp.socket) {
        ChatApp.isTyping = false;
        ChatApp.socket.emit('typing', { typing: false });
    }
    clearTimeout(ChatApp.typingTimeout);
}

/**
 * Show typing indicator
 */
function showTypingIndicator(username) {
    const indicator = document.getElementById('typingIndicator');
    const userSpan = document.getElementById('typingUser');
    
    userSpan.textContent = username;
    indicator.classList.remove('hidden');
}

/**
 * Hide typing indicator
 */
function hideTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    indicator.classList.add('hidden');
}

// ============================================
// ADMIN DASHBOARD
// ============================================
/**
 * Update room dropdown for admin
 */
function updateRoomDropdown() {
    const dropdown = document.getElementById('roomDropdown');
    const roomInfo = document.getElementById('roomInfo');
    
    if (!dropdown) return;
    
    dropdown.innerHTML = '<option value="">-- Select a room to join --</option>';
    
    const roomCount = Object.keys(ChatApp.availableRooms).length;
    
    if (roomCount === 0) {
        roomInfo.textContent = 'No users waiting. Rooms will appear here when users connect.';
        dropdown.disabled = true;
    } else {
        roomInfo.textContent = `${roomCount} user(s) waiting to chat with you`;
        dropdown.disabled = false;
        
        Object.entries(ChatApp.availableRooms).forEach(([roomId, info]) => {
            const option = document.createElement('option');
            option.value = roomId;
            const time = new Date(info.created_at).toLocaleTimeString();
            option.textContent = `${info.username} (Room: ${roomId.substring(0, 8)}... at ${time})`;
            dropdown.appendChild(option);
        });
    }
}

/**
 * Update dashboard statistics
 */
function updateDashboardStats() {
    const waitingCount = document.getElementById('waitingCount');
    const activeCount = document.getElementById('activeCount');
    
    if (waitingCount) {
        waitingCount.textContent = Object.keys(ChatApp.availableRooms).length;
    }
    
    if (activeCount) {
        const isInActiveChat = ChatApp.currentRoomId && !ChatApp.availableRooms[ChatApp.currentRoomId];
        activeCount.textContent = isInActiveChat ? '1' : '0';
    }
}

/**
 * Join selected room from dropdown
 */
function joinSelectedRoom() {
    const dropdown = document.getElementById('roomDropdown');
    const roomId = dropdown.value;
    
    if (!roomId) return;
    
    ChatApp.socket.emit('join_room_by_id', { room_id: roomId });
    delete ChatApp.availableRooms[roomId];
    updateRoomDropdown();
    updateDashboardStats();
}

/**
 * Refresh room list
 */
function refreshRooms() {
    if (ChatApp.socket && ChatApp.isAdmin) {
        ChatApp.socket.emit('list_rooms');
        
        // Visual feedback
        const btn = document.getElementById('refreshRoomsBtn');
        const originalText = btn.textContent;
        btn.textContent = '🔄 Refreshing...';
        btn.disabled = true;
        
        setTimeout(() => {
            btn.textContent = originalText;
            btn.disabled = false;
        }, 1000);
    }
}

// ============================================
// UI HELPERS
// ============================================
/**
 * Show status message
 */
function showStatus(message, type) {
    const statusDiv = document.getElementById('status');
    statusDiv.textContent = message;
    statusDiv.className = `status ${type}`;
}

/**
 * Play notification sound (optional)
 */
function playNotificationSound() {
    // You can add a notification sound here
    // For example: new Audio('/static/notification.mp3').play();
    console.log('New room notification');
}

/**
 * Show thank you screen after disconnect
 */
function showThankYouScreen() {
    const container = document.querySelector('.container');
    
    const thankYouHTML = `
        <div class="login-box" style="text-align: center; animation: scaleIn 0.6s ease-out;">
            <div style="font-size: 70px; margin-bottom: 20px; animation: pulse 2s infinite;">🎉</div>
            <h1 style="color: #4ade80; margin-bottom: 15px; font-size: 32px;">Thank You for Chatting!</h1>
            <p style="color: #b0b3b8; font-size: 16px; line-height: 1.8; margin-bottom: 30px;">
                ${ChatApp.isAdmin ? 
                    'Your session has ended. Thank you for helping our users!' : 
                    'We appreciate you taking the time to connect with us. Your chat session has ended.'}
            </p>
            
            <div style="background: linear-gradient(135deg, #1e3a5f 0%, #1e40af 100%); padding: 25px; border-radius: 12px; margin-bottom: 30px; border: 2px solid #0084ff; box-shadow: 0 4px 20px rgba(0, 132, 255, 0.3);">
                <p style="color: #60a5fa; font-size: 15px; margin-bottom: 15px; font-weight: 600;">
                    ⭐ Like this project? Check out the source code!
                </p>
                <a href="https://github.com/ManiKumarKundurthi/chat-with-me" 
                   target="_blank"
                   style="display: inline-block; background: linear-gradient(135deg, #0084ff 0%, #0066cc 100%); color: white; padding: 14px 35px; 
                          border-radius: 10px; text-decoration: none; font-weight: bold; font-size: 15px;
                          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); box-shadow: 0 4px 15px rgba(0, 132, 255, 0.3);">
                    🔗 View on GitHub
                </a>
            </div>
            
            <button onclick="location.reload()" 
                    style="background: linear-gradient(135deg, #4ade80 0%, #22c55e 100%); color: #0a0a0a; font-weight: bold; font-size: 16px; box-shadow: 0 4px 15px rgba(74, 222, 128, 0.3);">
                ↻ Start New Chat
            </button>
        </div>
        
        <style>
            a:hover {
                transform: translateY(-2px) !important;
                box-shadow: 0 8px 25px rgba(0, 132, 255, 0.5) !important;
            }
        </style>
    `;
    
    container.innerHTML = thankYouHTML;
}

// ============================================
// UTILITY FUNCTIONS
// ============================================
/**
 * Escape HTML to prevent XSS
 * Note: We're already using textContent in addMessage which auto-escapes,
 * but this is here for any future use cases
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Log for debugging
 */
function log(message, data = null) {
    if (data) {
        console.log(`[ChatApp] ${message}`, data);
    } else {
        console.log(`[ChatApp] ${message}`);
    }
}

// ============================================
// ERROR HANDLING
// ============================================
window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
});

// ============================================
// EXPORTS (if using modules)
// ============================================
// If you want to use ES6 modules later, uncomment:
// export { ChatApp, connect, sendMessage, disconnectChat };
