"""
Sessiya hayot sikli.

Ilgari kod `async for session in get_session(): ... return` naqshini ishlatardi.
Bu naqshda chaqiruvchi `return` qilsa, async generator tashlab ketiladi va uning
`async with` bloki faqat axlat yig'ilganda yopiladi. Yuklama ostida bu ulanishlar
pulini tugatishi mumkin edi.
"""

import pytest
from sqlalchemy import select

from database import engine as db_engine


@pytest.mark.asyncio
async def test_session_scope_return_dan_keyin_ham_yopadi(monkeypatch):
    """Asosiy regressiya: blok ichidan return qilinsa ham sessiya yopilishi kerak."""
    yopilgan = []

    class KuzatuvchiSessiya:
        def __init__(self):
            self.closed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            self.closed = True
            yopilgan.append(self)

    monkeypatch.setattr(db_engine, "async_session_factory", lambda: KuzatuvchiSessiya())

    async def handler():
        async with db_engine.session_scope() as session:
            return "javob"

    natija = await handler()

    assert natija == "javob"
    assert len(yopilgan) == 1
    assert yopilgan[0].closed is True


@pytest.mark.asyncio
async def test_eski_generator_return_da_yopmaydi(monkeypatch):
    """
    Nima uchun ko'chirish kerak bo'lganini hujjatlashtiradi: eski naqsh
    `return` da sessiyani deterministik yopmaydi.
    """
    yopilgan = []

    class KuzatuvchiSessiya:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            yopilgan.append(self)

    monkeypatch.setattr(db_engine, "async_session_factory", lambda: KuzatuvchiSessiya())

    async def eski_handler():
        async for session in db_engine.get_session():
            return "javob"

    await eski_handler()

    # Generator tashlab ketildi — yopilish darhol sodir bo'lmadi.
    assert yopilgan == []


@pytest.mark.asyncio
async def test_xatolik_bolganda_ham_yopiladi(monkeypatch):
    yopilgan = []

    class KuzatuvchiSessiya:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            yopilgan.append(exc[0])

    monkeypatch.setattr(db_engine, "async_session_factory", lambda: KuzatuvchiSessiya())

    with pytest.raises(ValueError):
        async with db_engine.session_scope():
            raise ValueError("sinov")

    assert len(yopilgan) == 1
    assert yopilgan[0] is ValueError


@pytest.mark.asyncio
async def test_haqiqiy_sessiya_qaytaradi():
    """Haqiqiy AsyncSession beradi va blokdan chiqqach uni yopadi."""
    from sqlalchemy.ext.asyncio import AsyncSession

    async with db_engine.session_scope() as session:
        assert isinstance(session, AsyncSession)
        assert (await session.execute(select(1))).scalar() == 1

    # Yopilgandan keyin sessiya yangi ish boshlamaydi.
    assert not session.in_transaction()
