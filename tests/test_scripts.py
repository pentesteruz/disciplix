"""
Migratsiya skriptlari — ular real foydalanuvchi ma'lumotiga tegadi,
shuning uchun xulq-atvori aniq qotirilishi kerak.

Har bir skript uchun tekshiriladi:
  - quruq ishlash hech narsani o'zgartirmaydi,
  - --apply to'g'ri qatorlarni o'zgartiradi,
  - tegmasligi kerak bo'lgan qatorlarga tegmaydi.
"""

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from database.models import Base, Finance, PremiumRequest, Task, Transaction, User
from tests.conftest_api import make_test_engine
from utils.timezone import get_tashkent_time


@pytest_asyncio.fixture
async def db(monkeypatch):
    from database import engine as db_engine

    engine = make_test_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_engine, "async_session_factory", factory)
    yield factory
    await engine.dispose()


# ─── sync_premium_flags ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_premium_bayrogi_moslashtiriladi(db):
    from scripts.sync_premium_flags import sync

    hozir = get_tashkent_time()
    async with db() as s:
        s.add_all([
            User(telegram_id=1, is_premium=True, premium_until=hozir - timedelta(days=5)),   # tugagan
            User(telegram_id=2, is_premium=True, premium_until=None),                        # legacy
            User(telegram_id=3, is_premium=False, premium_until=hozir + timedelta(days=5)),  # faol
            User(telegram_id=4, is_premium=True, premium_until=hozir + timedelta(days=5)),   # to'g'ri
        ])
        await s.commit()

    # Quruq ishlash — hech narsa o'zgarmaydi
    await sync(apply=False)
    async with db() as s:
        users = {u.telegram_id: u for u in (await s.execute(select(User))).scalars()}
        assert users[1].is_premium is True

    await sync(apply=True)
    async with db() as s:
        users = {u.telegram_id: u for u in (await s.execute(select(User))).scalars()}
        assert users[1].is_premium is False   # muddati tugagan
        assert users[2].is_premium is False   # sanasiz bayroq huquq bermaydi
        assert users[3].is_premium is True    # faol obuna bayroqni oladi
        assert users[4].is_premium is True    # o'zgarmaydi


# ─── consolidate_transactions ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_izohlar_finances_dan_kochiriladi(db):
    from scripts.consolidate_transactions import consolidate

    tosh = datetime(2026, 6, 27, 15, 36, 38)
    utc = datetime(2026, 6, 27, 10, 36, 38)   # ayni hodisa, 5 soat farq

    async with db() as s:
        s.add(User(telegram_id=1))
        await s.flush()
        s.add(Finance(user_id=1, amount=27000, category="Texnologiya", item_type="expense",
                      description="Hosting uchun to'lov", ai_advice="Yaxshi", entry_time=tosh))
        s.add(Transaction(user_id=1, amount=27000, category="Texnologiya", type="expense",
                          description=None, ai_advice=None, timestamp=utc))
        await s.commit()

    await consolidate(apply=False)
    async with db() as s:
        tx = (await s.execute(select(Transaction))).scalars().first()
        assert tx.description is None      # quruq ishlash yozmadi

    await consolidate(apply=True)
    async with db() as s:
        tx = (await s.execute(select(Transaction))).scalars().first()
        assert tx.description == "Hosting uchun to'lov"
        assert tx.ai_advice == "Yaxshi"


@pytest.mark.asyncio
async def test_mos_kelmagan_summa_juftlashmaydi(db):
    """Summa boshqa bo'lsa juft deb hisoblanmasligi kerak."""
    from scripts.consolidate_transactions import consolidate

    async with db() as s:
        s.add(User(telegram_id=1))
        await s.flush()
        s.add(Finance(user_id=1, amount=27000, item_type="expense", description="Bir",
                      entry_time=datetime(2026, 6, 27, 15, 0)))
        s.add(Transaction(user_id=1, amount=99999, type="expense",
                          timestamp=datetime(2026, 6, 27, 10, 0)))
        await s.commit()

    await consolidate(apply=True)
    async with db() as s:
        tx = (await s.execute(select(Transaction))).scalars().first()
        assert tx.description is None   # juft topilmagani uchun tegilmadi


@pytest.mark.asyncio
async def test_mavjud_izoh_ustiga_yozilmaydi(db):
    from scripts.consolidate_transactions import consolidate

    async with db() as s:
        s.add(User(telegram_id=1))
        await s.flush()
        s.add(Finance(user_id=1, amount=100, item_type="expense", description="Eski",
                      entry_time=datetime(2026, 6, 27, 15, 0)))
        s.add(Transaction(user_id=1, amount=100, type="expense", description="Yangi",
                          timestamp=datetime(2026, 6, 27, 10, 0)))
        await s.commit()

    await consolidate(apply=True)
    async with db() as s:
        tx = (await s.execute(select(Transaction))).scalars().first()
        assert tx.description == "Yangi"   # to'ldirilgan maydon tegilmaydi


# ─── backfill_timezones ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_eski_sanalar_suriladi_yangilariga_tegilmaydi(db):
    from scripts.backfill_timezones import backfill

    cutoff = datetime(2026, 8, 3, 12, 0)
    eski = datetime(2026, 6, 27, 10, 36, 38)    # UTC, cutoff'dan oldin
    yangi = datetime(2026, 8, 4, 9, 0, 0)       # cutoff'dan keyin

    async with db() as s:
        s.add(User(telegram_id=1, created_at=eski))
        s.add(User(telegram_id=2, created_at=yangi))
        await s.flush()
        s.add(Transaction(user_id=1, amount=100, type="expense", timestamp=eski))
        s.add(Transaction(user_id=1, amount=200, type="expense", timestamp=yangi))
        await s.commit()

    await backfill(cutoff, apply=True)

    async with db() as s:
        users = {u.telegram_id: u for u in (await s.execute(select(User))).scalars()}
        assert users[1].created_at == eski + timedelta(hours=5)   # surildi
        assert users[2].created_at == yangi                        # tegilmadi

        txs = sorted((await s.execute(select(Transaction))).scalars(), key=lambda t: t.amount)
        assert txs[0].timestamp == eski + timedelta(hours=5)
        assert txs[1].timestamp == yangi


@pytest.mark.asyncio
async def test_vazifa_sanasiga_tegilmaydi(db):
    """
    Regressiya: tasks.created_at kod tomonidan Toshkent vaqtida yoziladi.
    Uni surish ma'lumotni buzardi.
    """
    from scripts.backfill_timezones import backfill

    tosh = datetime(2026, 6, 27, 15, 38, 46)
    async with db() as s:
        s.add(User(telegram_id=1))
        await s.flush()
        s.add(Task(user_id=1, title="Sport", created_at=tosh))
        await s.commit()

    await backfill(datetime(2026, 8, 3, 12, 0), apply=True)

    async with db() as s:
        task = (await s.execute(select(Task))).scalars().first()
        assert task.created_at == tosh, "vazifa sanasi surilib ketdi!"


@pytest.mark.asyncio
async def test_quruq_ishlash_hech_narsani_ozgartirmaydi(db):
    from scripts.backfill_timezones import backfill

    eski = datetime(2026, 6, 27, 10, 0)
    async with db() as s:
        s.add(User(telegram_id=1, created_at=eski))
        await s.commit()

    await backfill(datetime(2026, 8, 3, 12, 0), apply=False)

    async with db() as s:
        user = (await s.execute(select(User))).scalars().first()
        assert user.created_at == eski


@pytest.mark.asyncio
async def test_backfill_natijasi_finances_bilan_moslashadi(db):
    """
    Eng kuchli tekshiruv: surishdan keyin transactions.timestamp
    finances.entry_time bilan aynan mos tushishi kerak.
    """
    from scripts.backfill_timezones import backfill

    tosh = datetime(2026, 6, 27, 15, 36, 38)
    utc = datetime(2026, 6, 27, 10, 36, 38)

    async with db() as s:
        s.add(User(telegram_id=1))
        await s.flush()
        s.add(Finance(user_id=1, amount=27000, item_type="expense", entry_time=tosh))
        s.add(Transaction(user_id=1, amount=27000, type="expense", timestamp=utc))
        await s.commit()

    await backfill(datetime(2026, 8, 3, 12, 0), apply=True)

    async with db() as s:
        fin = (await s.execute(select(Finance))).scalars().first()
        tx = (await s.execute(select(Transaction))).scalars().first()
        assert tx.timestamp == fin.entry_time


# ─── recalculate_balances ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_balans_tranzaksiyalardan_qayta_hisoblanadi(db):
    """
    Regressiya: eski balans oylik bilan urug'lantirilgan va ikki marta
    hisoblangan. Qayta hisoblashdan keyin u faqat tranzaksiyalardan kelishi kerak.
    """
    from scripts.recalculate_balances import recalculate

    async with db() as s:
        # Eski holat: balans oylik bilan urug'lantirilgan
        s.add(User(telegram_id=1, monthly_income=5_000_000, balance=5_000_000,
                   base_currency="UZS"))
        await s.flush()
        s.add(Transaction(user_id=1, amount=5_000_000, type="income", category="Oylik",
                          timestamp=get_tashkent_time()))
        s.add(Transaction(user_id=1, amount=200_000, type="expense", category="Oziq-ovqat",
                          timestamp=get_tashkent_time()))
        await s.commit()

    await recalculate(apply=False)
    async with db() as s:
        u = (await s.execute(select(User))).scalars().first()
        assert float(u.balance) == 5_000_000   # quruq ishlash tegmadi

    await recalculate(apply=True)
    async with db() as s:
        u = (await s.execute(select(User))).scalars().first()
        # 5 000 000 kirim − 200 000 chiqim. Oylik ENDI ikki marta qo'shilmaydi.
        assert float(u.balance) == 4_800_000


@pytest.mark.asyncio
async def test_tranzaksiyasiz_foydalanuvchi_nolga_tushadi(db):
    from scripts.recalculate_balances import recalculate

    async with db() as s:
        s.add(User(telegram_id=1, monthly_income=3_000_000, balance=3_000_000))
        await s.commit()

    await recalculate(apply=True)
    async with db() as s:
        u = (await s.execute(select(User))).scalars().first()
        assert float(u.balance) == 0
