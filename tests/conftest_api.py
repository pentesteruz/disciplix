"""
API integratsiya testlari uchun umumiy asboblar.

Bu yerda haqiqiy aiohttp ilovasi haqiqiy SQLite bazasi bilan ko'tariladi va
haqiqiy imzolangan Telegram initData bilan so'rov yuboriladi. Ya'ni auth
middleware, marshrutlar, servis qatlami va baza — hammasi birga sinaladi.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

TEST_BOT_TOKEN = "123456:TEST-TOKEN-FOR-UNIT-TESTS"
TEST_ADMIN_ID = 1


def make_init_data(user_id: int, auth_date: int = None, token: str = TEST_BOT_TOKEN) -> str:
    """
    Telegram WebApp initData'ni haqiqiy imzo bilan yasaydi.

    Imzo aynan Telegram hisoblagan usulda hisoblanadi, shuning uchun test
    auth middleware'ni chetlab o'tmaydi — uni haqiqatan o'tadi.
    """
    payload = {
        "user": json.dumps({"id": user_id, "first_name": "Test", "language_code": "uz"}),
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAETest",
    }
    check_string = "\n".join(f"{k}={payload[k]}" for k in sorted(payload))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    payload["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(payload)


def make_test_engine():
    """
    Bitta ulanishda saqlanadigan in-memory baza.

    StaticPool bo'lmasa, har ulanish yangi bo'sh baza olardi va jadvallar
    yo'qolardi.
    """
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


class FakeBot:
    """Telegram'ga chiqmaydi — yuborilgan xabarlarni yozib boradi."""

    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append({"chat_id": chat_id, "text": text, **kwargs})
        return {"message_id": len(self.sent)}

    async def send_video(self, chat_id, video, **kwargs):
        self.sent.append({"chat_id": chat_id, "video": video, **kwargs})
        return {"message_id": len(self.sent)}

    async def edit_message_reply_markup(self, **kwargs):
        return None
