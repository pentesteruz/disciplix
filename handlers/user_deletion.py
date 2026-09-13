from aiogram import Router, F, types
from database.engine import session_scope
from sqlalchemy import select, update
from database.models import User, Dream, Task, Finance, Transaction, LifeSchedule, DetailedExpenses, DreamProgress, Debt, PremiumRequest, WithdrawalRequest
import logging

router = Router()

@router.callback_query(F.data.startswith("confirm_delete_yes_"))
async def process_confirm_delete_yes(callback: types.CallbackQuery):
    telegram_id = int(callback.data.split("_")[-1])
    
    # Faqat xabarni olgan foydalanuvchining o'zi tasdiqlay olishi kerak
    if callback.from_user.id != telegram_id:
        await callback.answer("Siz bu harakatni amalga oshira olmaysiz.", show_alert=True)
        return

    try:
        from handlers.admin_panel import delete_user_data
        ok = await delete_user_data(telegram_id)
        if ok:
            await callback.message.edit_text("✅ Sizning barcha ma'lumotlaringiz tizimdan butunlay o'chirib tashlandi.")
            await callback.answer()
        else:
            await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
    except Exception as e:
        logging.error(f"Error deleting user {telegram_id}: {e}")
        await callback.message.edit_text("❌ O'chirishda xatolik yuz berdi. Iltimos, keyinroq urunib ko'ring.")

@router.callback_query(F.data.startswith("confirm_delete_no_"))
async def process_confirm_delete_no(callback: types.CallbackQuery):
    telegram_id = int(callback.data.split("_")[-1])
    
    if callback.from_user.id != telegram_id:
        await callback.answer("Siz bu harakatni amalga oshira olmaysiz.", show_alert=True)
        return
        
    await callback.message.edit_text("❌ Ma'lumotlaringiz o'chirilishi bekor qilindi. Barchasi xavfsiz saqlanmoqda.")
    await callback.answer()
