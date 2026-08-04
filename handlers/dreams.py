from aiogram import Router, types, F
from services.gemini_service import GeminiService
from services.ai_queue import ai_queue
from database.engine import session_scope
from database.models import Dream, User, DreamProgress
from sqlalchemy import select
from utils.timezone import get_tashkent_time
from services.scheduler import DreamCheckCallback
from datetime import datetime, timedelta

router = Router()
@router.message(F.text.contains("niyat qildim")) # Simple heuristic, or catch-all 'ai_chat'
async def handle_dream_text(message: types.Message):
    # User input example: "iPhone 16 olishni niyat qildim narxi 1200 dollar 100 kun"
    
    user_id = message.from_user.id
    async with session_scope() as session:
        result = await session.execute(select(User).where(User.telegram_id == user_id))
        user = result.scalars().first()
        if not user:
            from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
            from config import WEBAPP_URL
            
            from utils.i18n import _
            kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=_('register_btn', 'uz'), web_app=WebAppInfo(url=f"{WEBAPP_URL}/register"))]],
                resize_keyboard=True
            )
            await message.answer(_('register_first_alert', 'uz'), reply_markup=kb)
            return
            
        # Try to parse as dream
        data = await ai_queue.process(message, GeminiService.analyze_dream, message.text)
        
        if data and data.get('dream_name') and data.get('total_amount'):
            name = data['dream_name']
            price = float(data['total_amount'])
            days = int(data.get('days', 30)) # default 30 days
            daily_req = price / days if days > 0 else price
            
            # Calculate deadline based on days
            deadline = get_tashkent_time() + timedelta(days=days)

            new_dream = Dream(
                user_id=user.id,
                dream_name=name,
                total_amount=price,
                saved_amount=0.0, # Renamed from current_amount
                deadline=deadline,
                daily_limit_target=daily_req,
                is_active=True,
                extra_savings=0.0,
                created_at=get_tashkent_time() # Explicitly set creation time
            )
            try:
                session.add(new_dream)
                await session.commit()
                
                from utils.i18n import _
                lang = user.language or 'uz'
                await message.answer(_('dream_added', lang, name=name, price=price, days=days, daily_req=daily_req))
            except Exception as e:
                await session.rollback()
                import traceback
                traceback.print_exc()
                from utils.i18n import _
                lang = user.language or 'uz'
                await message.answer(_('dream_save_error', lang))
        else:
             from utils.i18n import _
             lang = user.language or 'uz' if 'user' in locals() and user else 'uz'
             await message.answer(_('dream_parse_error', lang))

@router.callback_query(DreamCheckCallback.filter())
async def handle_dream_check_callback(callback: types.CallbackQuery, callback_data: DreamCheckCallback):
    try:
        from utils.i18n import _
        lang = 'uz'
        async with session_scope() as session:
            dream = await session.get(Dream, callback_data.dream_id)
            if not dream:
                await callback.answer(_('dream_not_found', lang), show_alert=True)
                return

            res = await session.execute(select(User).where(User.id == dream.user_id))
            user = res.scalars().first()
            if user and user.language: lang = user.language

            from datetime import datetime, timedelta
            target_date = datetime.strptime(callback_data.date, "%Y-%m-%d")

            if callback_data.action == "yes":
                start_of_target_day = datetime(target_date.year, target_date.month, target_date.day)
                end_of_target_day = start_of_target_day + timedelta(days=1)
                
                # Check if already paid for THAT specific day
                stmt_existing = select(DreamProgress).where(
                    DreamProgress.dream_id == dream.id,
                    DreamProgress.date >= start_of_target_day,
                    DreamProgress.date < end_of_target_day,
                    DreamProgress.is_paid == True
                )
                existing = (await session.execute(stmt_existing)).scalars().first()
                
                if existing:
                    await callback.message.edit_text(_('dream_already_paid_today', lang))
                else:
                    dream.saved_amount += dream.daily_limit_target
                    prog = DreamProgress(
                        user_id=dream.user_id,
                        dream_id=dream.id,
                        amount=dream.daily_limit_target,
                        date=start_of_target_day,
                        is_paid=True
                    )
                    session.add(prog)
                    session.add(dream)
                    await session.commit()
                    await callback.message.edit_text(_('dream_paid_today_success', lang))
            
            elif callback_data.action == "no":
                # Push the deadline by 1 day
                from datetime import timedelta
                if dream.deadline:
                    dream.deadline += timedelta(days=1)
                session.add(dream)
                await session.commit()
                
                new_date_str = dream.deadline.strftime("%d-%B") if dream.deadline else "Noma'lum"
                
                await callback.message.edit_text(_('dream_missed_today', lang))
            
            await callback.answer()
    except Exception as e:
        import traceback
        traceback.print_exc()
        from utils.i18n import _
        await callback.answer(_('error_occurred', 'uz'), show_alert=True)

@router.callback_query(F.data == "start_dream_now")
async def handle_start_dream_now(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    
    user_id = callback.from_user.id
    async with session_scope() as session:
        result = await session.execute(select(User).where(User.telegram_id == user_id))
        user = result.scalars().first()
        
        if user and not user.phone_number:
            lang = user.language or 'uz'
            from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
            from config import WEBAPP_URL
            from utils.i18n import _
            kn = [
                [KeyboardButton(text=_('register_btn', lang), web_app=WebAppInfo(url=f"{WEBAPP_URL}/web/register?user_id={user_id}&lang={lang}"))]
            ]
            keyboard = ReplyKeyboardMarkup(keyboard=kn, resize_keyboard=True)
            await callback.message.answer(
                _('dream_started_unregistered', lang), 
                reply_markup=keyboard
            )
        else:
            lang = user.language if user else 'uz'
            from utils.i18n import _
            await callback.message.reply(_('dream_started_registered', lang))

    await callback.answer()
