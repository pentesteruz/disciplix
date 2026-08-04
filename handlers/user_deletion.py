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
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = res.scalars().first()
            
            if not user:
                await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
                return
            
            # Delete everything related to user
            await session.execute(update(User).where(User.referred_by_id == user.id).values(referred_by_id=None))
            await session.execute(Dream.__table__.delete().where(Dream.user_id == user.id))
            await session.execute(Task.__table__.delete().where(Task.user_id == user.id))
            await session.execute(Finance.__table__.delete().where(Finance.user_id == user.id))
            await session.execute(Transaction.__table__.delete().where(Transaction.user_id == user.id))
            await session.execute(LifeSchedule.__table__.delete().where(LifeSchedule.user_id == user.id))
            await session.execute(DetailedExpenses.__table__.delete().where(DetailedExpenses.user_id == user.id))
            await session.execute(DreamProgress.__table__.delete().where(DreamProgress.user_id == user.id))
            await session.execute(Debt.__table__.delete().where(Debt.user_id == user.id))
            await session.execute(PremiumRequest.__table__.delete().where(PremiumRequest.user_id == user.id))
            await session.execute(WithdrawalRequest.__table__.delete().where(WithdrawalRequest.user_id == user.id))
            
            # Delete user
            await session.delete(user)
            await session.commit()
            
            await callback.message.edit_text("✅ Sizning barcha ma'lumotlaringiz tizimdan butunlay o'chirib tashlandi.")
            await callback.answer()
            
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
