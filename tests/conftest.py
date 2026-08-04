"""
Testlar uchun umumiy sozlamalar.

config.py import paytida DATABASE_URL va ENCRYPTION_KEY talab qiladi, shuning uchun
ular haqiqiy modullar yuklanishidan oldin o'rnatiladi. Testlar hech qachon
production bazasiga ulanmasligi kerak — shu sababli in-memory SQLite ishlatiladi.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("BOT_TOKEN", "123456:TEST-TOKEN-FOR-UNIT-TESTS")
os.environ.setdefault("ADMIN_IDS", "1")

if not os.environ.get("ENCRYPTION_KEY"):
    from cryptography.fernet import Fernet

    os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
