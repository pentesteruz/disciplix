"""Ephemeral local API benchmark. Never use against production."""

import asyncio
import hashlib
import hmac
import json
import os
import sys
import time
import traceback
import types
from collections import Counter
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = r"C:\Users\user\AppData\Local\Temp\disciplix-load.sqlite3"


def setup_environment():
    try:
        os.remove(DB_PATH)
    except FileNotFoundError:
        pass
    os.environ.update(
        {
            "DATABASE_URL": "sqlite+aiosqlite:///" + DB_PATH.replace("\\", "/"),
            "BOT_TOKEN": "123456:TEST-TOKEN-FOR-LOAD-TESTS",
            "ADMIN_IDS": "1",
            "ENCRYPTION_KEY": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
            "WEBAPP_URL": "https://example.test",
        }
    )
    gemini = types.ModuleType("services.gemini_service")

    async def safe_generate_content(*args, **kwargs):
        return None

    gemini.safe_generate_content = safe_generate_content
    sys.modules["services.gemini_service"] = gemini


setup_environment()

from aiohttp import ClientSession, TCPConnector, web
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

from database import engine as database_engine
from database.models import Base, Transaction, User
from utils.timezone import get_tashkent_time
from web.routes import RATE_LIMIT_CACHE, setup_routes


def auth_header(user_id: int) -> dict[str, str]:
    data = {
        "user": json.dumps({"id": user_id, "first_name": "Load"}, separators=(",", ":")),
        "auth_date": str(int(time.time())),
        "query_id": "load",
    }
    data_check = "\n".join(f"{key}={data[key]}" for key in sorted(data))
    secret = hmac.new(b"WebAppData", os.environ["BOT_TOKEN"].encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return {"Authorization": urlencode(data)}


def percentile(values: list[float], ratio: float) -> float:
    ordered = sorted(values)
    return ordered[int((len(ordered) - 1) * ratio)]


class FakeBot:
    async def send_message(self, *args, **kwargs):
        return None


async def main():
    engine = create_async_engine(
        os.environ["DATABASE_URL"],
        poolclass=AsyncAdaptedQueuePool,
        pool_size=20,
        max_overflow=30,
        pool_timeout=30,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    database_engine.async_session_factory = factory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    now = get_tashkent_time()
    async with factory() as session:
        users = [
            User(
                telegram_id=5_000_000 + index,
                name=f"Load {index}",
                phone_number=f"tg_{index}",
                user_state="registered",
                accepted_policy=True,
                language="uz",
                base_currency="UZS",
                active_currencies="UZS",
                daily_limit=100_000,
                premium_until=now + timedelta(days=14),
            )
            for index in range(1_100)
        ]
        session.add_all(users)
        await session.flush()
        session.add_all(
            [
                Transaction(
                    user_id=user.id,
                    amount=50_000,
                    currency="UZS",
                    category="Seed",
                    type="income",
                    description="seed",
                    timestamp=now,
                )
                for user in users
            ]
        )
        await session.commit()

    app = web.Application()
    app["bot"] = FakeBot()
    setup_routes(app)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0, backlog=2_048)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"

    async def run_scenario(kind: str, concurrent: int):
        RATE_LIMIT_CACHE.clear()
        async with ClientSession(
            connector=TCPConnector(
                limit=concurrent + 50,
                limit_per_host=concurrent + 50,
                force_close=True,
            )
        ) as client:
            async def send_one(index: int):
                user_id = 5_000_000 + index
                started = time.perf_counter()
                try:
                    if kind == "dashboard":
                        async with client.get(
                            f"{base_url}/api/dashboard?user_id={user_id}",
                            headers=auth_header(user_id),
                        ) as response:
                            await response.read()
                            return str(response.status), (time.perf_counter() - started) * 1000, None
                    async with client.post(
                        f"{base_url}/api/tasks/{user_id}",
                        headers=auth_header(user_id),
                        json={"title": f"Load {user_id}", "description": "benchmark"},
                    ) as response:
                        await response.read()
                        return str(response.status), (time.perf_counter() - started) * 1000, None
                except Exception as error:
                    return "EXC", (time.perf_counter() - started) * 1000, type(error).__name__

            started = time.perf_counter()
            results = await asyncio.gather(*(send_one(index) for index in range(concurrent)))
            elapsed = time.perf_counter() - started

        latencies = [result[1] for result in results]
        print(
            json.dumps(
                {
                    "type": kind,
                    "concurrent": concurrent,
                    "statuses": dict(Counter(result[0] for result in results)),
                    "total_s": round(elapsed, 3),
                    "rps": round(concurrent / elapsed, 1),
                    "p50_ms": round(percentile(latencies, 0.50), 1),
                    "p95_ms": round(percentile(latencies, 0.95), 1),
                    "max_ms": round(max(latencies), 1),
                    "exceptions": dict(Counter(result[2] for result in results if result[2])),
                }
            ),
            flush=True,
        )

    for concurrency in (100, 250, 500, 750, 1_000):
        await run_scenario("dashboard", concurrency)
    for concurrency in (50, 100, 250, 500):
        await run_scenario("task_create", concurrency)

    await runner.cleanup()
    await engine.dispose()
    try:
        os.remove(DB_PATH)
    except OSError:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except BaseException:
        traceback.print_exc()
        raise
