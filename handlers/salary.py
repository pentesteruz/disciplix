"""
Oylik tasdiqlash va ortiqcha pul tugmalari.

Ikkala oqim ham scheduler yuborgan xabarga javob beradi:
  - oylik tushdimi? (oylik kuni)
  - bugun ishlatmagan pulingizni tejaganga qo'shaymizmi? (21:00)
"""

import logging

from aiogram import F, Router, types
from sqlalchemy import select

from database.engine import session_scope
from database.models import User
from services import finance_service, salary_service
from utils.timezone import get_tashkent_time

router = Router()


def salary_keyboard() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ Ha, tushdi", callback_data="salary_yes")],
        [types.InlineKeyboardButton(text="✏️ Boshqa summa", callback_data="salary_edit")],
        [types.InlineKeyboardButton(text="🕰 Hali tushmadi", callback_data="salary_not_yet")],
    ])


def surplus_keyboard(amount: float) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=f"💰 Ha, {amount:,.0f} ni tejaganga qo'sh",
                                    callback_data="surplus_save")],
        [types.InlineKeyboardButton(text="➕ Yo'q, xarajat qo'shishni unutdim",
                                    callback_data="surplus_forgot")],
    ])


@router.callback_query(F.data == "salary_yes")
async def salary_confirmed(call: types.CallbackQuery):
    async with session_scope() as session:
        user = (await session.execute(
            select(User).where(User.telegram_id == call.from_user.id)
        )).scalars().first()
        if not user:
            await call.answer("Foydalanuvchi topilmadi.", show_alert=True)
            return

        tx = salary_service.confirm_salary(session, user)
        if tx is None:
            await call.answer("Bu oy uchun oylik allaqachon belgilangan.", show_alert=True)
            return

        await finance_service.sync_balance_cache(session, user)
        await session.commit()
        summa = float(tx.amount)

    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.message.answer(
        f"✅ {summa:,.0f} so'm oylik kirim sifatida yozildi.\n\n"
        "Endi balansingiz va kunlik limitingiz shu summadan hisoblanadi."
    )
    await call.answer()


@router.callback_query(F.data == "salary_not_yet")
async def salary_postponed(call: types.CallbackQuery):
    """
    Hech narsa yozilmaydi. Scheduler ertaga yana so'raydi, chunki
    salary_confirmed_for hali shu oyga belgilanmagan.
    """
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.message.answer(
        "Tushunarli. Oylik tushganda menga ayting yoki ertaga yana so'rayman.\n\n"
        "Balansga yo'q pulni qo'shib qo'ymaslik uchun shunday qilamiz."
    )
    await call.answer()


@router.callback_query(F.data == "salary_edit")
async def salary_edit_prompt(call: types.CallbackQuery):
    await call.message.answer(
        "Qancha tushdi? Shunchaki summani yozing, masalan: <code>4 500 000 oylik tushdi</code>",
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "surplus_save")
async def surplus_saved(call: types.CallbackQuery):
    async with session_scope() as session:
        user = (await session.execute(
            select(User).where(User.telegram_id == call.from_user.id)
        )).scalars().first()
        if not user:
            await call.answer("Foydalanuvchi topilmadi.", show_alert=True)
            return

        ortiqcha = await finance_service.daily_surplus(session, user)
        if ortiqcha <= 0:
            await call.answer("Bugun ortiqcha pul qolmadi.", show_alert=True)
            return

        user.saved_surplus = float(user.saved_surplus or 0) + ortiqcha
        jami = float(user.saved_surplus)
        await session.commit()

    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.message.answer(
        f"💰 {ortiqcha:,.0f} so'm tejalganlar hisobiga qo'shildi.\n"
        f"Jami tejagansiz: <b>{jami:,.0f}</b> so'm.\n\n"
        "<i>Eslatma: bu pul sizning hamyoningizda — bu shunchaki hisob-kitob.</i>",
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "surplus_forgot")
async def surplus_forgot(call: types.CallbackQuery):
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.message.answer(
        "Yaxshi, unutgan xarajatlaringizni hozir yozing — men qo'shib qo'yaman.\n"
        "Masalan: <code>25 ming taksiga</code>",
        parse_mode="HTML",
    )
    await call.answer()
