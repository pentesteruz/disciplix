from os import getenv
from dotenv import load_dotenv

load_dotenv()
#salom
BOT_TOKEN = getenv("BOT_TOKEN", "").strip('\"\'')
GEMINI_API_KEY = getenv("GEMINI_API_KEY", "").strip('\"\'')
DB_NAME = getenv("DATABASE_URL", "").strip('\"\'')
if not DB_NAME:
    raise ValueError("DATABASE_URL muhit o'zgaruvchisi (environment variable) topilmadi! Iltimos .env faylga yoki Railway Variablesga qo'shing.")

# Fix for SQLAlchemy: postgres:// -> postgresql+asyncpg://
if DB_NAME.startswith("postgres://"):
    DB_NAME = DB_NAME.replace("postgres://", "postgresql+asyncpg://", 1)
elif DB_NAME.startswith("postgresql://") and "+asyncpg" not in DB_NAME:
     DB_NAME = DB_NAME.replace("postgresql://", "postgresql+asyncpg://", 1)
ADMIN_IDS = [int(id) for id in getenv("ADMIN_IDS", "").split(",") if id]
SUPPORT_GROUP_ID = int(getenv("SUPPORT_GROUP_ID", "0"))
WEBAPP_URL = getenv("WEBAPP_URL", "").strip('\"\'')
if WEBAPP_URL and not WEBAPP_URL.startswith("http"):
    WEBAPP_URL = f"https://{WEBAPP_URL}"
if WEBAPP_URL and WEBAPP_URL.endswith("/"):
    WEBAPP_URL = WEBAPP_URL.rstrip("/")

API_ID = getenv("API_ID")
API_HASH = getenv("API_HASH")
PHONE_NUMBER = getenv("PHONE_NUMBER")
SMS_BOT_USERNAME = getenv("SMS_BOT_USERNAME")
