import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from database.models import Base
from config import DB_NAME
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, AsyncIterator

engine_kwargs: dict[str, Any] = {
    "echo": False,
}

if not DB_NAME.startswith("sqlite"):
    engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 30,
        "pool_timeout": 30,
        "pool_recycle": 1800
    })

engine = create_async_engine(DB_NAME, **engine_kwargs)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """
    Sessiya olishning to'g'ri usuli.

    `get_session()` bilan farqi: u async generator bo'lgani uchun
    `async for session in get_session(): ... return` naqshida chaqiruvchi
    `return` qilsa, generator tashlab ketiladi va `async with` ning yopilishi
    faqat axlat yig'ilganda bajariladi. Yuklama ostida bu ulanishlar pulini
    tugatishi mumkin. `async with session_scope()` esa har doim yopadi.

        async with session_scope() as session:
            ...
            return web.json_response(...)   # sessiya baribir yopiladi
    """
    async with async_session_factory() as session:
        yield session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    ESKIRGAN: `session_scope()` dan foydalaning.

    Bu generator `async for ... : ... return` naqshida sessiyani deterministik
    yopmaydi. Faqat hali ko'chirilmagan chaqiruvlar uchun turibdi.
    """
    async with async_session_factory() as session:
        yield session

async def init_db():
    # PostgreSQL muhitida mavjud jadvallarni tekshirish va avtomatik tuzatish:
    # Agar 'users' yoki 'dreams' jadvallari allaqachon mavjud bo'lsa, ammo ularda 'id' ustuni
    # bo'lmasa, Base.metadata.create_all xatolik (foreign key constraint does not exist) beradi.
    if not DB_NAME.startswith("sqlite"):
        try:
            # 1. users jadvalini tekshirish:
            # Agar 'users' jadvali mavjud bo'lsa, lekin unda 'telegram_id' ustuni bo'lmasa,
            # demak bu jadval Disciplix botiga tegishli emas (boshqa template yoki eski mos kelmaydigan jadval).
            # Unda bot foydalanuvchilari bo'lishi mumkin emas, chunki bot faqat telegram_id bilan ishlaydi.
            # Shuning uchun uni CASCADE bilan o'chiramiz, shunda Base.metadata.create_all uni to'liq
            # va to'g'ri sxema bilan qayta yaratadi.
            async with engine.begin() as conn:
                res = await conn.execute(text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'users';"
                ))
                user_cols = {r[0].lower() for r in res.fetchall()}

                if user_cols and "telegram_id" not in user_cols:
                    logging.warning(
                        f"DIAGNOSTIC: 'users' jadvalida 'telegram_id' topilmadi (ustunlar: {list(user_cols)})! "
                        "Ushbu mos kelmaydigan jadval toza qayta yaratish uchun o'chirilmoqda (DROP TABLE users CASCADE)..."
                    )
                    await conn.execute(text("DROP TABLE IF EXISTS users CASCADE;"))
                    user_cols = set()

                if user_cols and "id" not in user_cols:
                    try:
                        await conn.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_pkey CASCADE;"))
                    except Exception:
                        pass
                    try:
                        await conn.execute(text("""
                            DO $$
                            DECLARE r RECORD;
                            BEGIN
                                FOR r IN (
                                    SELECT conname FROM pg_constraint 
                                    WHERE conrelid = 'users'::regclass AND contype = 'p'
                                ) LOOP
                                    EXECUTE 'ALTER TABLE users DROP CONSTRAINT IF EXISTS ' || quote_ident(r.conname) || ' CASCADE;';
                                END LOOP;
                            END $$;
                        """))
                    except Exception:
                        pass
                    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS id SERIAL;"))
                    await conn.execute(text("ALTER TABLE users ADD PRIMARY KEY (id);"))
                    logging.info("users jadvaliga id SERIAL PRIMARY KEY qo'shildi.")

            # 2. dreams jadvalini tekshirish: agar 'id' bo'lmasa, tuzatish
            async with engine.begin() as conn:
                res = await conn.execute(text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'dreams';"
                ))
                dream_cols = {r[0].lower() for r in res.fetchall()}
                if dream_cols and "id" not in dream_cols:
                    await conn.execute(text("DROP TABLE IF EXISTS dreams CASCADE;"))
        except Exception as e:
            logging.error(f"PostgreSQL oldindan tekshirishda xatolik yuz berdi: {e}", exc_info=True)

    async with engine.begin() as conn:
        # Create all tables defined in models
        await conn.run_sync(Base.metadata.create_all)
        logging.info("DATABASE SYNC COMPLETE: Tables created/verified.")

    # Run each migration in its own connection to avoid InFailedSQLTransaction cascade
    async def add_column_if_not_exists(table, column, col_type):
        """
        Safely add a column. Each call uses its own connection so a failure
        does not poison subsequent migrations.
        PostgreSQL type mapping: DATETIME -> TIMESTAMP
        """
        pg_type = col_type.replace("DATETIME", "TIMESTAMP")
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {pg_type};")
                )
        except Exception as e:
            logging.error(f"Migration error for {table}.{column}: {e}")

    await add_column_if_not_exists("tasks",    "is_ai_generated",  "BOOLEAN DEFAULT FALSE")
    await add_column_if_not_exists("tasks",    "is_notified",       "BOOLEAN DEFAULT FALSE")
    await add_column_if_not_exists("tasks",    "description",       "VARCHAR")
    await add_column_if_not_exists("dreams",   "extra_savings",     "FLOAT DEFAULT 0.0")
    await add_column_if_not_exists("dreams",   "deadline",          "TIMESTAMP")
    await add_column_if_not_exists("dreams",   "cancel_requested",  "BOOLEAN DEFAULT FALSE")
    await add_column_if_not_exists("dreams",   "icon",              "VARCHAR")
    await add_column_if_not_exists("dreams",   "icon_bg",           "VARCHAR")
    await add_column_if_not_exists("dreams",   "icon_color",        "VARCHAR")
    await add_column_if_not_exists("users",    "is_frozen",         "BOOLEAN DEFAULT FALSE")
    await add_column_if_not_exists("users",    "referral_code",     "VARCHAR UNIQUE")
    await add_column_if_not_exists("users",    "referred_by_id",    "INTEGER REFERENCES users(id)")
    await add_column_if_not_exists("users",    "bonus_balance",     "FLOAT DEFAULT 0.0")
    await add_column_if_not_exists("users",    "user_state",        "VARCHAR DEFAULT 'onboarding'")
    await add_column_if_not_exists("finances", "currency",          "VARCHAR DEFAULT 'UZS'")
    await add_column_if_not_exists("finances", "ai_advice",         "VARCHAR")
    await add_column_if_not_exists("finances", "due_date",          "TIMESTAMP")
    await add_column_if_not_exists("transactions", "currency",      "VARCHAR DEFAULT 'UZS'")
    await add_column_if_not_exists("transactions", "due_date",      "TIMESTAMP")
    # finances jadvalidan ko'chirilgan maydon (scripts/consolidate_transactions.py)
    await add_column_if_not_exists("transactions", "ai_advice",     "VARCHAR")
    await add_column_if_not_exists("users",    "frozen_until",      "TIMESTAMP")
    await add_column_if_not_exists("users",    "fraud_strikes",     "INTEGER DEFAULT 0")
    await add_column_if_not_exists("users",    "accepted_policy",   "BOOLEAN DEFAULT FALSE")
    # DEFAULT yo'q: CURRENT_TIMESTAMP server UTC vaqtini beradi, ORM esa Toshkent
    # vaqtini yozadi — ilgari shu sabab bitta ustunda 5 soat farqli sanalar bo'lgan.
    await add_column_if_not_exists("users",    "last_active",       "TIMESTAMP")
    await add_column_if_not_exists("users",    "created_at",        "TIMESTAMP")
    await add_column_if_not_exists("users",    "active_currencies", "VARCHAR DEFAULT 'UZS'")
    await add_column_if_not_exists("users",    "base_currency",     "VARCHAR DEFAULT 'UZS'")
    await add_column_if_not_exists("premium_requests", "created_at","TIMESTAMP")
    # Oylik oqimi va ortiqcha pul ko'rsatkichi
    await add_column_if_not_exists("users",    "salary_day",          "INTEGER")
    await add_column_if_not_exists("users",    "salary_confirmed_for","VARCHAR")
    await add_column_if_not_exists("users",    "saved_surplus",       "NUMERIC(16,2) DEFAULT 0")
    await add_column_if_not_exists("users",    "surplus_asked_on",    "TIMESTAMP")

    # Create withdrawal_requests table separately
    try:
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS withdrawal_requests (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    amount NUMERIC(16, 2) NOT NULL,
                    card_number VARCHAR NOT NULL,
                    status VARCHAR DEFAULT 'pending',
                    message_id INTEGER,
                    created_at TIMESTAMP
                );
            """))
    except Exception as e:
        logging.error(f"DB INIT ERROR (withdrawal_requests): {e}")

    # Alter float columns to numeric safely (PostgreSQL specific)
    async def alter_column_type_to_numeric(table, column):
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE NUMERIC(16, 2) USING {column}::numeric;")
                )
                logging.info(f"Altered column {table}.{column} to NUMERIC(16, 2).")
        except Exception:
            pass

    numeric_columns = [
        ("users", "daily_limit"),
        ("users", "balance"),
        ("users", "fixed_expenses_total"),
        ("users", "daily_income"),
        ("users", "monthly_income"),
        ("users", "bonus_balance"),
        ("dreams", "total_amount"),
        ("dreams", "saved_amount"),
        ("dreams", "daily_limit_target"),
        ("dreams", "extra_savings"),
        ("transactions", "amount"),
        ("detailed_expenses", "amount"),
        ("dream_progress", "amount"),
        ("finances", "amount"),
        ("debts", "amount"),
        ("premium_requests", "amount"),
        ("withdrawal_requests", "amount"),
    ]
    for table, column in numeric_columns:
        await alter_column_type_to_numeric(table, column)

    logging.info("Auto-migrations executed successfully.")

async def dispose_db():
    await engine.dispose()
