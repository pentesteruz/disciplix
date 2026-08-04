import os
import logging
from dotenv import load_dotenv
from sqlalchemy.types import TypeDecorator, String, Text
from cryptography.fernet import Fernet, InvalidToken

# Load environment variables
load_dotenv()

# Read the key from environment
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")

if not ENCRYPTION_KEY:
    raise ValueError(
        "⚠️  KRITIK XATOLIK: ENCRYPTION_KEY muhit o'zgaruvchisi o'rnatilmagan! "
        "Xavfsizlik nuqtai nazaridan tizim ishga tushmaydi. "
        "Iltimos, .env fayliga ENCRYPTION_KEY qo'shing."
    )

try:
    fernet = Fernet(ENCRYPTION_KEY.encode())
except Exception as e:
    raise ValueError(
        f"❌ KRITIK XATOLIK: ENCRYPTION_KEY noto'g'ri formatda: {e}. Tizim ishga tushmaydi!"
    )

class SmartEncryptedString(TypeDecorator):
    """
    Symmetric encryption using AES-256 (Fernet).
    Gracefully falls back to plain text if decryption fails (e.g., legacy data).
    Used for shorter strings like names.
    """
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if not fernet:
            return value
        return fernet.encrypt(value.encode('utf-8')).decode('utf-8')

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not fernet:
            return value
        try:
            return fernet.decrypt(value.encode('utf-8')).decode('utf-8')
        except (InvalidToken, TypeError, ValueError):
            return value

class SmartEncryptedText(TypeDecorator):
    """
    Symmetric encryption using AES-256 (Fernet).
    Used for longer strings like descriptions.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if not fernet:
            return value
        return fernet.encrypt(value.encode('utf-8')).decode('utf-8')

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not fernet:
            return value
        try:
            return fernet.decrypt(value.encode('utf-8')).decode('utf-8')
        except (InvalidToken, TypeError, ValueError):
            return value
