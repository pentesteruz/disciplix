"""
Oylik oqimi.

Asosiy qoida: `monthly_income` balansga kirmaydi. Oylik kelganda foydalanuvchi
tasdiqlaydi va o'shanda haqiqiy kirim tranzaksiyasi yoziladi.
"""

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from database.models import Base, Transaction, User
from services import finance_service, salary_service
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
    u = User(telegram_id=1, monthly_income=5_000_000, daily_limit=100_000,
             salary_day=3, base_currency="UZS")
    session.add(u)
    await session.commit()
    return u


# ─── Sana hisobi ─────────────────────────────────────────────────────────────

def test_oddiy_oylik_sanasi():
    assert salary_service.resolve_salary_date(2026, 8, 3) == datetime(2026, 8, 3)


def test_fevralda_31_oyning_oxiriga_tushadi():
    """Regressiya: 31-fevral yo'q — oylik hech qachon kelmasdi."""
    assert salary_service.resolve_salary_date(2026, 2, 31) == datetime(2026, 2, 28)
    assert salary_service.resolve_salary_date(2028, 2, 31) == datetime(2028, 2, 29)  # kabisa


def test_30_kunlik_oyda_31():
    assert salary_service.resolve_salary_date(2026, 4, 31) == datetime(2026, 4, 30)


# ─── Qachon so'raladi ────────────────────────────────────────────────────────

def test_oylik_kunidan_oldin_soralmaydi(user):
    assert salary_service.is_salary_due(user, datetime(2026, 8, 2)) is False


def test_oylik_kunida_soraladi(user):
    assert salary_service.is_salary_due(user, datetime(2026, 8, 3)) is True


def test_kechikkan_kunlarda_ham_soraladi(user):
    """Oylik kechiksa, tizim so'rashda davom etadi."""
    assert salary_service.is_salary_due(user, datetime(2026, 8, 7)) is True


def test_tasdiqlangandan_keyin_soralmaydi(user):
    user.salary_confirmed_for = "2026-08"
    assert salary_service.is_salary_due(user, datetime(2026, 8, 5)) is False


def test_keyingi_oyda_yana_soraladi(user):
    user.salary_confirmed_for = "2026-08"
    assert salary_service.is_salary_due(user, datetime(2026, 9, 3)) is True


def test_oylik_kuni_belgilanmagan_bolsa_soralmaydi(session):
    u = User(telegram_id=2, salary_day=None)
    assert salary_service.is_salary_due(u, datetime(2026, 8, 3)) is False


def test_hisobot_bir_kun_oldin(user):
    assert salary_service.is_report_due(user, datetime(2026, 8, 2)) is True
    assert salary_service.is_report_due(user, datetime(2026, 8, 3)) is False
    assert salary_service.is_report_due(user, datetime(2026, 8, 1)) is False


# ─── Tasdiqlash ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tasdiqlash_kirim_tranzaksiyasi_yozadi(session, user):
    tx = salary_service.confirm_salary(session, user, now=datetime(2026, 8, 3))
    await session.commit()

    assert tx is not None
    assert float(tx.amount) == 5_000_000
    assert tx.type == "income"
    assert tx.category == "Oylik"
    assert user.salary_confirmed_for == "2026-08"

    balans = await finance_service.compute_balance(session, user.id)
    assert balans == 5_000_000


@pytest.mark.asyncio
async def test_ikki_marta_tasdiqlab_bolmaydi(session, user):
    """Regressiya: bir oy uchun ikkinchi tranzaksiya yozilmasligi kerak."""
    salary_service.confirm_salary(session, user, now=datetime(2026, 8, 3))
    await session.commit()

    ikkinchi = salary_service.confirm_salary(session, user, now=datetime(2026, 8, 4))
    await session.commit()

    assert ikkinchi is None
    soni = len((await session.execute(select(Transaction))).scalars().all())
    assert soni == 1


@pytest.mark.asyncio
async def test_keyingi_oy_alohida_yoziladi(session, user):
    salary_service.confirm_salary(session, user, now=datetime(2026, 8, 3))
    await session.commit()
    salary_service.confirm_salary(session, user, now=datetime(2026, 9, 3))
    await session.commit()

    soni = len((await session.execute(select(Transaction))).scalars().all())
    assert soni == 2
    assert user.salary_confirmed_for == "2026-09"


@pytest.mark.asyncio
async def test_boshqa_summa_moljalni_yangilaydi(session, user):
    """Oylik o'zgargan bo'lsa, kunlik limit hisobi ham yangilanishi kerak."""
    tx = salary_service.confirm_salary(session, user, amount=4_500_000,
                                       now=datetime(2026, 8, 3))
    await session.commit()

    assert float(tx.amount) == 4_500_000
    assert float(user.monthly_income) == 4_500_000


@pytest.mark.asyncio
async def test_nol_summa_yozilmaydi(session):
    u = User(telegram_id=3, monthly_income=0, salary_day=3)
    session.add(u)
    await session.commit()

    assert salary_service.confirm_salary(session, u, now=datetime(2026, 8, 3)) is None


# ─── Sarf bahosi ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("chiqim,kutilgan", [
    (4_500_000, "ko'p"),        # 3 000 000 rejadan ancha ko'p
    (2_000_000, "kam"),
    (3_000_000, "barqaror"),
])
def test_sarf_bahosi(chiqim, kutilgan):
    assert salary_service.spending_verdict(5_000_000, chiqim, 100_000) == kutilgan


def test_limitsiz_baho_berilmaydi():
    assert salary_service.spending_verdict(5_000_000, 1_000_000, 0) == "nomalum"


# ─── Ortiqcha pul ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ortiqcha_pul_hisobi(session, user):
    finance_service.record_transaction(session, user.id, 30_000, "Oziq-ovqat", "expense")
    await session.commit()

    ortiqcha = await finance_service.daily_surplus(session, user)
    assert ortiqcha == 70_000   # 100 000 limit − 30 000 sarf


@pytest.mark.asyncio
async def test_limitdan_oshsa_ortiqcha_yoq(session, user):
    finance_service.record_transaction(session, user.id, 150_000, "Oziq-ovqat", "expense")
    await session.commit()

    assert await finance_service.daily_surplus(session, user) == 0


@pytest.mark.asyncio
async def test_majburiy_xarajat_ortiqchani_kamaytirmaydi(session, user):
    finance_service.record_transaction(session, user.id, 800_000,
                                       finance_service.MANDATORY_CATEGORY, "expense")
    await session.commit()

    assert await finance_service.daily_surplus(session, user) == 100_000
