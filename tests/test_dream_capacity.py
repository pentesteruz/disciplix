"""
Orzu kunlik sig'imi.

Ilgari 50/100/150% variantlari har safar TO'LIQ kunlik limitdan hisoblanardi.
Ikkinchi orzu qo'shilganda ham birinchisi bilan bir xil summalar chiqardi,
holbuki birinchi orzu sig'imning bir qismini allaqachon band qilgan edi.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from database.models import Base, Dream, User
from services import dream_service
from tests.conftest_api import make_test_engine


@pytest_asyncio.fixture
async def session():
    engine = make_test_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def user(session):
    u = User(telegram_id=1, daily_limit=100_000, base_currency="UZS")
    session.add(u)
    await session.commit()
    return u


async def add_dream(session, user, daily_target, active=True):
    session.add(Dream(user_id=user.id, dream_name="Orzu", total_amount=1_000_000,
                      saved_amount=0, daily_limit_target=daily_target, is_active=active))
    await session.commit()


@pytest.mark.asyncio
async def test_birinchi_orzu_toliq_limitdan_hisoblanadi(session, user):
    cap = await dream_service.get_capacity(session, user)
    assert cap.available == 100_000
    assert [o["amount"] for o in cap.options] == [50_000, 100_000, 150_000]


@pytest.mark.asyncio
async def test_ikkinchi_orzu_qolgan_sigimdan_hisoblanadi(session, user):
    """Asosiy regressiya: 50 000 band bo'lgach, variantlar 25/50/75 bo'lishi kerak."""
    await add_dream(session, user, 50_000)

    cap = await dream_service.get_capacity(session, user)
    assert cap.committed == 50_000
    assert cap.available == 50_000
    assert [o["amount"] for o in cap.options] == [25_000, 50_000, 75_000]


@pytest.mark.asyncio
async def test_uchinchi_orzu_yana_kamayadi(session, user):
    await add_dream(session, user, 50_000)
    await add_dream(session, user, 25_000)

    cap = await dream_service.get_capacity(session, user)
    assert cap.committed == 75_000
    assert cap.available == 25_000
    assert [o["amount"] for o in cap.options] == [12_500, 25_000, 37_500]


@pytest.mark.asyncio
async def test_yakunlangan_orzu_sigimni_band_qilmaydi(session, user):
    await add_dream(session, user, 50_000, active=False)

    cap = await dream_service.get_capacity(session, user)
    assert cap.committed == 0
    assert cap.available == 100_000


@pytest.mark.asyncio
async def test_sigim_toliq_band_bolganda(session, user):
    await add_dream(session, user, 100_000)

    cap = await dream_service.get_capacity(session, user)
    assert cap.available == 0
    assert cap.is_full is True

    ruxsat, xabar = dream_service.validate_daily_target(cap, 10_000)
    assert ruxsat is False
    assert "to'liq band" in xabar


@pytest.mark.asyncio
async def test_sigimdan_oshsa_ogohlantiradi_lekin_taqiqlamaydi(session, user):
    """150% ataylab sig'imdan oshadi — bu foydalanuvchining tanlovi."""
    await add_dream(session, user, 50_000)
    cap = await dream_service.get_capacity(session, user)

    ruxsat, xabar = dream_service.validate_daily_target(cap, 75_000)
    assert ruxsat is True
    assert xabar is not None
    assert "25,000 oshadi" in xabar


@pytest.mark.asyncio
async def test_sigim_ichida_bolsa_ogohlantirish_yoq(session, user):
    await add_dream(session, user, 50_000)
    cap = await dream_service.get_capacity(session, user)

    ruxsat, xabar = dream_service.validate_daily_target(cap, 30_000)
    assert ruxsat is True
    assert xabar is None


@pytest.mark.asyncio
async def test_manfiy_summa_rad_etiladi(session, user):
    cap = await dream_service.get_capacity(session, user)
    ruxsat, xabar = dream_service.validate_daily_target(cap, 0)
    assert ruxsat is False


@pytest.mark.asyncio
async def test_limit_belgilanmagan_bolsa_tekshirilmaydi(session):
    """Kunlik limit hali yo'q foydalanuvchini bloklamaymiz."""
    u = User(telegram_id=2, daily_limit=0)
    session.add(u)
    await session.commit()

    cap = await dream_service.get_capacity(session, u)
    ruxsat, xabar = dream_service.validate_daily_target(cap, 999_999)
    assert ruxsat is True
    assert xabar is None


@pytest.mark.asyncio
async def test_150_foiz_belgisi_qoyiladi(session, user):
    cap = await dream_service.get_capacity(session, user)
    belgilar = [o["exceeds_capacity"] for o in cap.options]
    assert belgilar == [False, False, True]
