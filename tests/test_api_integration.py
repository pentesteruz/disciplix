"""
API integratsiya testlari — haqiqiy HTTP so'rovlari, haqiqiy baza.

Bu testlar auth middleware, marshrutlar, servis qatlami va bazani birga
sinaydi. Ilgari loyihada bunday qamrov umuman yo'q edi.
"""

import pytest
import pytest_asyncio
from aiohttp import web

from tests.conftest_api import TEST_ADMIN_ID, FakeBot, make_init_data, make_test_engine

USER_ID = 555001


@pytest.fixture(autouse=True)
def toza_rate_limit():
    """
    Rate limit keshi modul darajasida — testlar orasida saqlanib qolsa,
    bir xil user_id bilan ketma-ket so'rov yuborgan testlar 429 oladi.
    """
    from web.routes import RATE_LIMIT_CACHE

    RATE_LIMIT_CACHE.clear()
    yield
    RATE_LIMIT_CACHE.clear()


@pytest_asyncio.fixture
async def app(monkeypatch):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from database import engine as db_engine
    from database.models import Base
    from web.routes import setup_routes

    test_engine = make_test_engine()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    monkeypatch.setattr(db_engine, "async_session_factory", factory)

    # Kurslarni qotiramiz — testlar tarmoqqa chiqmasligi kerak.
    from utils.currency import CurrencyConverter

    async def fake_rates():
        return {"USD": 1.0, "UZS": 12600.0, "EUR": 0.92}

    monkeypatch.setattr(CurrencyConverter, "get_rates", staticmethod(fake_rates))

    application = web.Application()
    application["bot"] = FakeBot()
    setup_routes(application)
    application["_engine"] = test_engine
    yield application
    await test_engine.dispose()


@pytest_asyncio.fixture
async def client(app, aiohttp_client):
    return await aiohttp_client(app)


def auth(user_id=USER_ID, **kw):
    return {"Authorization": make_init_data(user_id, **kw)}


# ─── Autentifikatsiya ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_initdatasiz_sorov_rad_etiladi(client):
    resp = await client.get(f"/api/dashboard?user_id={USER_ID}")
    assert resp.status == 401


@pytest.mark.asyncio
async def test_notogri_imzo_rad_etiladi(client):
    resp = await client.get(
        f"/api/dashboard?user_id={USER_ID}",
        headers={"Authorization": make_init_data(USER_ID, token="BOSHQA-TOKEN")},
    )
    assert resp.status == 401


@pytest.mark.asyncio
async def test_eski_initdata_rad_etiladi(client):
    """Replay himoyasi: 25 soatlik initData ishlamasligi kerak."""
    import time

    eski = int(time.time()) - 25 * 3600
    resp = await client.get(f"/api/dashboard?user_id={USER_ID}", headers=auth(auth_date=eski))
    assert resp.status == 401
    assert "expired" in (await resp.json())["error"].lower()


@pytest.mark.asyncio
async def test_boshqa_foydalanuvchi_malumotini_ololmaydi(client):
    """A foydalanuvchi B ning ma'lumotini so'ray olmaydi."""
    resp = await client.get("/api/dashboard?user_id=999999", headers=auth(USER_ID))
    assert resp.status == 403


@pytest.mark.asyncio
async def test_oddiy_foydalanuvchi_admin_apiga_kira_olmaydi(client):
    resp = await client.get("/api/mng-x89b2k1q/dashboard", headers=auth(USER_ID))
    assert resp.status == 403


@pytest.mark.asyncio
async def test_admin_admin_apiga_kiradi(client):
    resp = await client.get("/api/mng-x89b2k1q/dashboard", headers=auth(TEST_ADMIN_ID))
    assert resp.status == 200


# ─── Ro'yxatdan o'tish: ismlar va sonlar ─────────────────────────────────────

@pytest.mark.asyncio
async def test_royxatdan_otish_ism_va_sonlarni_togri_saqlaydi(client, app):
    resp = await client.post("/api/register", headers=auth(), json={
        "name": "Jo'rabek", "surname": "Ismoilov",
        "monthly_income": 5_000_000, "daily_limit": 150_000,
        "mode": "quick", "lang": "uz", "base_currency": "UZS",
    })
    assert resp.status == 200, await resp.text()
    data = await resp.json()
    assert data["daily_limit"] == 150_000

    from sqlalchemy import select
    from database.models import User

    async with app["_engine"].connect() as conn:
        pass

    from database.engine import session_scope
    async with session_scope() as session:
        user = (await session.execute(select(User).where(User.telegram_id == USER_ID))).scalars().first()
        # Ism shifrlangan holda saqlanadi, lekin o'qishda tiklanadi (apostrof bilan)
        assert user.name == "Jo'rabek"
        assert user.surname == "Ismoilov"
        assert float(user.monthly_income) == 5_000_000
        assert float(user.daily_limit) == 150_000
        assert user.premium_until is not None   # trial berilgan


@pytest.mark.asyncio
async def test_manfiy_summa_rad_etiladi(client):
    resp = await client.post("/api/register", headers=auth(), json={
        "name": "Test", "monthly_income": -100, "mode": "quick",
    })
    assert resp.status == 400
    assert "manfiy" in (await resp.json())["error"]


@pytest.mark.asyncio
async def test_qayta_royxatdan_otish_balansni_qayta_yozmaydi(client):
    """Regressiya: bu endpointni qayta chaqirib balansni tiklab bo'lmasligi kerak."""
    await client.post("/api/register", headers=auth(), json={
        "name": "Test", "monthly_income": 1_000_000, "daily_limit": 50_000, "mode": "quick",
    })
    resp = await client.post("/api/register", headers=auth(), json={
        "name": "Test", "monthly_income": 99_000_000, "daily_limit": 9_000_000, "mode": "quick",
    })
    assert resp.status == 200
    assert (await resp.json())["daily_limit"] == 50_000  # o'zgarmadi


# ─── Pul: qo'shish va hisoblash ──────────────────────────────────────────────

@pytest_asyncio.fixture
async def registered(client):
    await client.post("/api/register", headers=auth(), json={
        "name": "Test", "monthly_income": 3_000_000, "daily_limit": 100_000,
        "mode": "quick", "lang": "uz", "base_currency": "UZS",
    })
    from sqlalchemy import select
    from database.engine import session_scope
    from database.models import User
    async with session_scope() as session:
        return (await session.execute(select(User).where(User.telegram_id == USER_ID))).scalars().first()


@pytest.mark.asyncio
async def test_dashboard_sonlarni_togri_hisoblaydi(client, registered):
    from database.engine import session_scope
    from services.finance_service import record_transaction

    async with session_scope() as session:
        record_transaction(session, registered.id, 20_000, "Oziq-ovqat", "expense")
        record_transaction(session, registered.id, 5_000, "Transport", "expense")
        record_transaction(session, registered.id, 500_000, "Oylik", "income")
        await session.commit()

    resp = await client.get(f"/api/dashboard?user_id={USER_ID}", headers=auth())
    assert resp.status == 200, await resp.text()
    data = await resp.json()

    assert data["daily_expense"] == 25_000
    assert data["daily_income"] == 500_000
    assert data["daily_limit"] == 100_000
    assert len(data["today_transactions"]) == 3


@pytest.mark.asyncio
async def test_majburiy_xarajat_kunlik_limitdan_chiqariladi(client, registered):
    from database.engine import session_scope
    from services.finance_service import MANDATORY_CATEGORY, record_transaction

    async with session_scope() as session:
        record_transaction(session, registered.id, 800_000, MANDATORY_CATEGORY, "expense")
        record_transaction(session, registered.id, 30_000, "Oziq-ovqat", "expense")
        await session.commit()

    data = await (await client.get(f"/api/dashboard?user_id={USER_ID}", headers=auth())).json()
    # Ijara limitga kirmaydi, faqat ixtiyoriy sarf hisoblanadi
    assert data["daily_expense"] == 30_000
    assert data["is_over_limit"] is False


@pytest.mark.asyncio
async def test_tranzaksiya_izohi_saqlanadi_va_qaytadi(client, registered):
    """Regressiya: ilgari transactions.description bo'sh qolardi."""
    from database.engine import session_scope
    from services.finance_service import record_transaction

    async with session_scope() as session:
        record_transaction(session, registered.id, 27_000, "Texnologiya", "expense",
                           description="Hosting uchun to'lov")
        await session.commit()

    data = await (await client.get(f"/api/dashboard?user_id={USER_ID}", headers=auth())).json()
    assert data["today_transactions"][0]["title"] == "Hosting uchun to'lov"


@pytest.mark.asyncio
async def test_valyuta_konversiyasi_umumiy_hisobda(client, registered):
    from database.engine import session_scope
    from services.finance_service import record_transaction

    async with session_scope() as session:
        record_transaction(session, registered.id, 100, "Test", "income", currency="USD")
        await session.commit()

    data = await (await client.get(f"/api/dashboard?user_id={USER_ID}", headers=auth())).json()
    umumiy = [c for c in data["currency_balances"] if c["total"]][0]
    # Faqat 100 USD = 1 260 000 UZS. monthly_income bu yerga QO'SHILMAYDI.
    assert umumiy["income"] == pytest.approx(1_260_000)


@pytest.mark.asyncio
async def test_oylik_ikki_marta_hisoblanmaydi(client, registered):
    """
    Asosiy regressiya: ro'yxatdan o'tishda aytilgan oylik (3 000 000) balansga
    kirmasligi kerak. Foydalanuvchi "oylik oldim" desa, faqat o'sha tranzaksiya
    hisoblanadi — ilgari summa ikki marta chiqardi.
    """
    data = await (await client.get(f"/api/dashboard?user_id={USER_ID}", headers=auth())).json()
    assert data["balance"] == 0, "oylik balansga qo'shilib qolgan"

    from database.engine import session_scope
    from services.finance_service import record_transaction

    async with session_scope() as session:
        record_transaction(session, registered.id, 3_000_000, "Oylik", "income")
        await session.commit()

    data = await (await client.get(f"/api/dashboard?user_id={USER_ID}", headers=auth())).json()
    assert data["balance"] == 3_000_000, "oylik ikki marta hisoblandi"


# ─── Rejalar ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reja_qoshiladi_va_royxatda_chiqadi(client, registered):
    resp = await client.post(f"/api/tasks/{USER_ID}", headers=auth(), json={
        "title": "Ertalab yugurish", "description": "7:00 da", "due_date": "2026-08-05T07:00:00",
    })
    assert resp.status == 200, await resp.text()

    data = await (await client.get(f"/api/tasks/{USER_ID}", headers=auth())).json()
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["title"] == "Ertalab yugurish"


@pytest.mark.asyncio
async def test_bosh_reja_rad_etiladi(client, registered):
    resp = await client.post(f"/api/tasks/{USER_ID}", headers=auth(), json={"title": "   "})
    assert resp.status == 400


@pytest.mark.asyncio
async def test_boshqa_odamning_rejasini_yopa_olmaydi(client, registered):
    await client.post(f"/api/tasks/{USER_ID}", headers=auth(), json={"title": "Meniki"})

    from sqlalchemy import select
    from database.engine import session_scope
    from database.models import Task
    async with session_scope() as session:
        task = (await session.execute(select(Task))).scalars().first()

    resp = await client.post(f"/api/tasks/complete/{task.id}", headers=auth(777888))
    assert resp.status in (403, 404)


# ─── Orzular ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_orzu_yaratiladi_va_pul_qoshiladi(client, registered):
    resp = await client.post(f"/api/dreams/{USER_ID}", headers=auth(), json={
        "name": "Mashina", "amount": 100_000_000, "deadline": "2027-01-01", "daily_limit": 50_000,
    })
    assert resp.status == 200, await resp.text()

    dream = (await (await client.get(f"/api/dreams/{USER_ID}", headers=auth())).json())["dream"]
    assert dream["name"] == "Mashina"
    assert dream["total"] == 100_000_000
    assert dream["saved"] == 0

    resp = await client.post(f"/api/dreams/{dream['id']}/progress", headers=auth(),
                             json={"amount": 50_000, "is_daily": True})
    assert resp.status == 200
    assert (await resp.json())["new_saved"] == 50_000


@pytest.mark.asyncio
async def test_manfiy_orzu_summasi_rad_etiladi(client, registered):
    resp = await client.post(f"/api/dreams/{USER_ID}", headers=auth(), json={
        "name": "Yomon", "amount": -5, "deadline": "2027-01-01", "daily_limit": 100,
    })
    assert resp.status == 400


@pytest.mark.asyncio
async def test_yigilmagan_orzuni_yakunlab_bolmaydi(client, registered):
    await client.post(f"/api/dreams/{USER_ID}", headers=auth(), json={
        "name": "Uy", "amount": 1_000_000, "deadline": "2027-01-01", "daily_limit": 1000,
    })
    dream = (await (await client.get(f"/api/dreams/{USER_ID}", headers=auth())).json())["dream"]
    resp = await client.post(f"/api/dreams/{dream['id']}/complete", headers=auth())
    assert resp.status == 400
