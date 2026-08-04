"""
Shifrlash — shaxsiy ma'lumot bazada ochiq yotmasligi kerak.

`SmartEncryptedString` Fernet ishlatadi: yozishda shifrlaydi, o'qishda tiklaydi,
va tiklab bo'lmasa xom qiymatni qaytaradi (eski shifrlanmagan qatorlar uchun).
"""

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from database.models import Base, Debt, Task, Transaction, User
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


@pytest.mark.asyncio
async def test_ism_bazada_ochiq_yotmaydi(session):
    session.add(User(telegram_id=1, name="Jo'rabek", surname="Ismoilov"))
    await session.commit()

    # Xom SQL — ORM tiklashini chetlab o'tamiz
    xom = (await session.execute(text("SELECT name, surname FROM users WHERE telegram_id = 1"))).first()
    assert "Jo'rabek" not in str(xom[0]), "ism ochiq saqlangan!"
    assert "Ismoilov" not in str(xom[1]), "familiya ochiq saqlangan!"
    assert len(str(xom[0])) > 40  # Fernet token uzun


@pytest.mark.asyncio
async def test_ism_oqishda_tiklanadi(session):
    session.add(User(telegram_id=2, name="Jo'rabek", surname="Ismoilov"))
    await session.commit()
    session.expunge_all()

    user = (await session.execute(select(User).where(User.telegram_id == 2))).scalars().first()
    assert user.name == "Jo'rabek"
    assert user.surname == "Ismoilov"


@pytest.mark.asyncio
async def test_kirill_va_maxsus_belgilar(session):
    """O'zbek apostrofi, kirill, emoji — hammasi buzilmasdan qaytishi kerak."""
    nomlar = ["G'ulom", "Шерзод", "O'ktam-Aziz", "Test 🎯", "Ø'zbek"]
    for i, nom in enumerate(nomlar, start=10):
        session.add(User(telegram_id=i, name=nom))
    await session.commit()
    session.expunge_all()

    for i, nom in enumerate(nomlar, start=10):
        user = (await session.execute(select(User).where(User.telegram_id == i))).scalars().first()
        assert user.name == nom, f"{nom!r} buzildi -> {user.name!r}"


@pytest.mark.asyncio
async def test_qarzdor_ismi_shifrlanadi(session):
    """Regressiya: Debt.person ilgari ochiq saqlanardi."""
    session.add(User(telegram_id=3))
    await session.flush()
    session.add(Debt(user_id=1, person="Akmal aka", amount=500000))
    await session.commit()

    xom = (await session.execute(text("SELECT person FROM debts"))).scalar()
    assert "Akmal" not in str(xom), "qarzdor ismi ochiq saqlangan!"

    session.expunge_all()
    debt = (await session.execute(select(Debt))).scalars().first()
    assert debt.person == "Akmal aka"


@pytest.mark.asyncio
async def test_tranzaksiya_izohi_shifrlanadi(session):
    session.add(User(telegram_id=4))
    await session.flush()
    session.add(Transaction(user_id=1, amount=20000, type="expense",
                            description="Do'kondan non", ai_advice="Tejamkor bo'ling"))
    await session.commit()

    xom = (await session.execute(text("SELECT description, ai_advice FROM transactions"))).first()
    assert "non" not in str(xom[0])
    assert "Tejamkor" not in str(xom[1])

    session.expunge_all()
    tx = (await session.execute(select(Transaction))).scalars().first()
    assert tx.description == "Do'kondan non"
    assert tx.ai_advice == "Tejamkor bo'ling"


@pytest.mark.asyncio
async def test_vazifa_sarlavhasi_shifrlanadi(session):
    session.add(User(telegram_id=5))
    await session.flush()
    session.add(Task(user_id=1, title="Shifokorga borish", description="Soat 10 da"))
    await session.commit()

    xom = (await session.execute(text("SELECT title FROM tasks"))).scalar()
    assert "Shifokor" not in str(xom)

    session.expunge_all()
    task = (await session.execute(select(Task))).scalars().first()
    assert task.title == "Shifokorga borish"
    assert task.description == "Soat 10 da"


@pytest.mark.asyncio
async def test_eski_shifrlanmagan_qator_yiqilmaydi(session):
    """Shifrlash joriy qilinishidan oldingi qatorlar hali ham o'qilishi kerak."""
    session.add(User(telegram_id=6))
    await session.commit()
    await session.execute(text("UPDATE users SET name = 'EskiOchiqIsm' WHERE telegram_id = 6"))
    await session.commit()
    session.expunge_all()

    user = (await session.execute(select(User).where(User.telegram_id == 6))).scalars().first()
    assert user.name == "EskiOchiqIsm"   # xom holda qaytadi, xato bermaydi


@pytest.mark.asyncio
async def test_none_qiymat_shifrlanmaydi(session):
    session.add(User(telegram_id=7, name=None))
    await session.commit()
    session.expunge_all()

    user = (await session.execute(select(User).where(User.telegram_id == 7))).scalars().first()
    assert user.name is None
