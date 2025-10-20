"""
Configuration file for the chat application
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    WEBSOCKET_HOST = '0.0.0.0'
    WEBSOCKET_PORT = int(os.environ.get('PORT', 10000))

    # Server URLs - will be updated after deployment
    ADMIN_SERVER_URL = os.getenv('ADMIN_SERVER_URL')
    USER_SERVER_URL = os.getenv('USER_SERVER_URL')

    # Admin credentials
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'DARK')
    ADMIN_PASSWORD_HASH = os.getenv('ADMIN_PASSWORD_HASH', '')

    # Flask secret key for sessions
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(24).hex())

    # NEW: Telegram Configuration
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    TELEGRAM_NOTIFICATIONS_ENABLED = os.getenv('TELEGRAM_NOTIFICATIONS_ENABLED', 'false').lower() == 'true'
