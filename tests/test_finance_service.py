"""
Moliyaviy hisob-kitob servisi.

Ilgari bu mantiq uch joyda, uch xil yozilgan edi va turli natija berardi:
`handle_dashboard_stats` `Transaction` dan, `handle_finance_stats` va
`handle_user_data` esa `Finance` dan o'qirdi. Endi bitta manba.

Testlar haqiqiy SQLite bazada ishlaydi — mock emas, chunki asosiy xavf
so'rovlarning o'zida.
"""

from datetime import timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from database.models import Base, Transaction, User
from services import finance_service
from utils.timezone import get_tashkent_time


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def user(session):
    u = User(telegram_id=555, base_currency="UZS", active_currencies="UZS")
    session.add(u)
    await session.commit()
    return u


async def add_tx(session, user, amount, tx_type="expense", category="Oziq-ovqat",
                 currency="UZS", when=None):
    tx = Transaction(
        user_id=user.id, amount=amount, type=tx_type, category=category,
        currency=currency, timestamp=when or get_tashkent_time(),
    )
    session.add(tx)
    await session.commit()
    return tx


@pytest.mark.asyncio
async def test_kunlik_yigindilar(session, user):
    await add_tx(session, user, 20000, "expense")
    await add_tx(session, user, 5000, "expense")
    await add_tx(session, user, 100000, "income")

    totals = await finance_service.daily_totals(session, user.id)
    assert totals.expense == 25000
    assert totals.income == 100000
    assert totals.net == 75000


@pytest.mark.asyncio
async def test_kechagi_yozuv_bugunga_kirmaydi(session, user):
    await add_tx(session, user, 20000, "expense", when=get_tashkent_time() - timedelta(days=1))
    await add_tx(session, user, 7000, "expense")

    totals = await finance_service.daily_totals(session, user.id)
    assert totals.expense == 7000


@pytest.mark.asyncio
async def test_majburiy_xarajat_kunlik_limitga_kirmaydi(session, user):
    """Ijara/soliq foydalanuvchi ixtiyoridagi sarf emas, shuning uchun limitdan tashqarida."""
    await add_tx(session, user, 500000, "expense", category=finance_service.MANDATORY_CATEGORY)
    await add_tx(session, user, 20000, "expense", category="Oziq-ovqat")

    totals = await finance_service.daily_totals(session, user.id)
    assert totals.expense == 520000            # umumiy sarf
    assert totals.discretionary_expense == 20000  # limitga kiradigani


@pytest.mark.asyncio
async def test_eski_tur_nomlari_qollab_quvvatlanadi(session, user):
    """Bazada 'chiqim' va 'kirim' kabi eski qiymatlar bor."""
    await add_tx(session, user, 10000, "chiqim")
    await add_tx(session, user, 30000, "kirim")
    await add_tx(session, user, 5000, "daromad")

    totals = await finance_service.daily_totals(session, user.id)
    assert totals.expense == 10000
    assert totals.income == 35000


@pytest.mark.asyncio
async def test_valyuta_boyicha_balans(session, user):
    await add_tx(session, user, 100000, "income", currency="UZS")
    await add_tx(session, user, 30000, "expense", currency="UZS")
    await add_tx(session, user, 50, "expense", currency="USD")

    balances = await finance_service.balances_by_currency(session, user.id)
    assert balances["UZS"] == {"income": 100000.0, "expense": 30000.0}
    assert balances["USD"] == {"income": 0.0, "expense": 50.0}


@pytest.mark.asyncio
async def test_boshqa_foydalanuvchi_qatorlari_aralashmaydi(session, user):
    boshqa = User(telegram_id=999, base_currency="UZS")
    session.add(boshqa)
    await session.commit()

    await add_tx(session, user, 10000, "expense")
    await add_tx(session, boshqa, 999999, "expense")

    totals = await finance_service.daily_totals(session, user.id)
    assert totals.expense == 10000


@pytest.mark.asyncio
async def test_record_transaction_turni_normallashtiradi(session, user):
    tx = finance_service.record_transaction(
        session, user_id=user.id, amount=1000, category="Test",
        tx_type="kirim", description="izoh", ai_advice="maslahat",
    )
    await session.commit()

    assert tx.type == "income"          # normallashtirilgan
    assert tx.description == "izoh"     # ilgari bu maydon bo'sh qolardi
    assert tx.ai_advice == "maslahat"
    assert tx.timestamp is not None


@pytest.mark.asyncio
async def test_oxirgi_tranzaksiyalar_tartibi(session, user):
    hozir = get_tashkent_time()
    await add_tx(session, user, 100, when=hozir - timedelta(hours=2))
    await add_tx(session, user, 200, when=hozir - timedelta(hours=1))
    await add_tx(session, user, 300, when=hozir)

    oxirgilar = await finance_service.recent_transactions(session, user.id, limit=2)
    assert [float(t.amount) for t in oxirgilar] == [300, 200]


@pytest.mark.asyncio
async def test_bosh_bazada_nol_qaytaradi(session, user):
    totals = await finance_service.daily_totals(session, user.id)
    assert totals.income == 0
    assert totals.expense == 0
    assert await finance_service.balances_by_currency(session, user.id) == {}
