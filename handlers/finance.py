from aiogram import Router, types, F, Bot
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, WebAppInfo
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.gemini_service import GeminiService, safe_generate_content
from database.engine import session_scope
from database.models import Transaction, User, Dream, Debt, Task
from sqlalchemy import select, func, cast, Date
from datetime import datetime, date, timedelta
import os
import re
import logging
from services.ai_queue import ai_queue

class FinanceState(StatesGroup):
    waiting_for_due_date = State()
    waiting_for_task_time = State()
    waiting_for_currency_confirmation = State()

from utils.timezone import get_tashkent_time
from utils.premium import is_premium_active
from services.finance_service import record_transaction, is_income

router = Router()

def safe_parse_amount(val):
    if val is None: return 0.0
    if isinstance(val, (int, float)): return float(val)
    try:
        s = str(val).replace(' ', '').replace(',', '')
        s = re.sub(r'[^\d.]', '', s)
        return float(s) if s else 0.0
    except:
        return 0.0

def parse_ai_due_date(due_date_str):
    if not due_date_str or due_date_str in ["null", "None", ""]:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(due_date_str, fmt)
        except ValueError:
            pass
    # fallback partial string
    try:
        return datetime.strptime(due_date_str[:10], "%Y-%m-%d")
    except:
        return None

@router.message(F.text, FinanceState.waiting_for_due_date)
async def handle_due_date_input(message: types.Message, state: FSMContext):
    try:
        data_cache = await state.get_data()
        finance_data = data_cache.get("finance_data")
        
        if not finance_data:
            from utils.i18n import _
            await message.answer(_('error_try_again', 'uz'))
            await state.clear()
            return
            
        # Parse due date using safe_generate_content (goes through semaphore, not bypassing queue)
        # SECURITY FIX: replaced direct genai.GenerativeModel() call with safe_generate_content
        # to respect the global rate-limiting semaphore.
        ai_prompt = f"Extract a future date from this text: '{message.text[:200]}'. Return ONLY 'YYYY-MM-DD' format or 'null'. Current date: {get_tashkent_time().strftime('%Y-%m-%d')}."
        res = await safe_generate_content(ai_prompt)
        date_str = res.text.strip() if res else 'null'
        
        if date_str != 'null' and len(date_str) == 10:
            finance_data['due_date'] = date_str
            finance_data['needs_due_date'] = False
            await state.clear()
            await finalize_finance_record(message, finance_data, message.from_user.id)
        else:
            user_id = message.from_user.id
            async with session_scope() as session:
                result = await session.execute(select(User).where(User.telegram_id == user_id))
                user = result.scalars().first()
                if user and user.user_state == "test_expense":
                    user.user_state = "test_plan"
                    await session.commit()
                    data = await ai_queue.process(message, GeminiService.analyze_finance_text, message.text, daily_limit=user.daily_limit or 0, current_spending=0)
                    if isinstance(data, list):
                        data = data[0] if data else {}
                    amount = data.get("amount", "ma'lum summa") if data else "ma'lum summa"
                    category = data.get("category", "Sinov") if data else "Sinov"
                    from utils.i18n import _
                    lang = user.language or 'uz'
                    await message.reply(_('tutorial_expense_success', lang, amount=f"{amount:,.0f}", category=category))
                    return
                elif user and user.user_state == "test_plan":
                    user.user_state = "testing_done"
                    await session.commit()
                    from config import WEBAPP_URL
                    task_data = await ai_queue.process(message, GeminiService.analyze_task, message.text)
                    title = task_data.get("title", "Rejangiz") if task_data else "Rejangiz"
                    from utils.i18n import _
                    lang = user.language or 'uz'
                    await message.reply(_('tutorial_plan_success', lang, title=title))
                    return
            from utils.i18n import _
            await message.answer(_('error_date_format', 'uz'))
    except Exception as e:
        logging.error(f"Due date handler error for user {message.from_user.id}: {e}")
        await state.clear()
        from utils.i18n import _
        await message.answer(_('error_try_again', 'uz'))

@router.message(F.text, FinanceState.waiting_for_task_time)
async def handle_task_time_input(message: types.Message, state: FSMContext):
    try:
        data_cache = await state.get_data()
        task_id = data_cache.get("task_id")
        
        if not task_id:
            await state.clear()
            return

        # SECURITY FIX: replaced direct genai.GenerativeModel() call with safe_generate_content
        ai_prompt = f"Extract a future date and time from this text: '{message.text[:200]}'. Return ONLY 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD' format or 'null'. Current time: {get_tashkent_time().strftime('%Y-%m-%d %H:%M:%S')}."
        res = await safe_generate_content(ai_prompt)
        date_str = res.text.strip() if res else 'null'
        
        due_date = parse_ai_due_date(date_str)
        if due_date:
            async with session_scope() as session:
                task = await session.get(Task, task_id)
                if task:
                    task.due_date = due_date
                    await session.commit()
                    from utils.i18n import _
                    await message.reply(_('task_time_set', 'uz', time_str=due_date.strftime('%H:%M %d.%m.%Y')))
            await state.clear()
        else:
            from utils.i18n import _
            await message.reply(_('error_time_format', 'uz'))
    except Exception as e:
        logging.error(f"Task time handler error: {e}")
        await state.clear()
        
@router.callback_query(F.data == "start_tutorial_cb")
async def start_tutorial_callback(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    async with session_scope() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalars().first()
        if user:
            user.user_state = "tutorial_step_1"
            await session.commit()
            from utils.i18n import _
            lang = user.language or 'uz'
            await callback.message.reply(_('tutorial_step_1_prompt', lang))
            await callback.answer()
            return
    from utils.i18n import _
    await callback.answer(_('user_not_found', 'uz'), show_alert=True)

@router.message(F.text)
async def handle_text_finance(message: types.Message, state: FSMContext):
    # Skip AI processing for commands
    if message.text.startswith('/'):
        # For admin commands, provide unauthorized message if not an admin
        if message.text in ["/adminpanelkubu", "/adminkubu"]:
            from handlers.admin_panel import is_admin
            if not is_admin(message.from_user.id):
                from utils.i18n import _
                await message.answer(_('admin_unauthorized', 'uz'))
        return

    try:
        user_id = message.from_user.id
        
        # 0. Fetch User Context and Check State
        state_data = await state.get_data()
        history = state_data.get("chat_history", [])
        chat_history_str = "\\n".join(history[-5:])

        daily_limit = 0
        current_spending = 0
        dream_info = None
        tutorial_step = None

        async with session_scope() as session:
            result = await session.execute(select(User).where(User.telegram_id == user_id))
            user = result.scalars().first()
            
            if user:
                tutorial_step = user.user_state

                daily_limit = user.daily_limit or 0
                today = get_tashkent_time().date()
                stmt = select(func.sum(Transaction.amount)).where(
                    Transaction.user_id == user.id,
                    Transaction.type == 'expense',
                    cast(Transaction.timestamp, Date) == today
                )
                res = await session.execute(stmt)
                current_spending = float(res.scalar() or 0.0)

                stmt_dream = select(Dream).where(Dream.user_id == user.id, Dream.is_active == True).order_by(Dream.created_at.desc()).limit(1)
                res_dream = await session.execute(stmt_dream)
                dream = res_dream.scalars().first()
                
                if dream:
                    dream_info = {
                        "name": dream.dream_name,
                        "total_amount": dream.total_amount,
                        "saved_amount": dream.saved_amount,
                        "daily_limit_target": dream.daily_limit_target
                    }

        # === TEST OQIMI: test_expense va test_plan state ===
        if tutorial_step == "test_expense":
            # AI bilan tahlil qilamiz lekin bazaga saqlamaymiz
            data = await ai_queue.process(
                message, GeminiService.analyze_finance_text,
                message.text, daily_limit=35000, current_spending=0
            )
            # Normalize: AI may return a list of actions
            if isinstance(data, list):
                data = data[0] if data else {}
            amount = data.get("amount", 35000) if data else 35000
            category = data.get("category", "Ovqat") if data else "Ovqat"
            
            # State ni test_plan ga o'tkazamiz
            async with session_scope() as session:
                u = (await session.execute(select(User).where(User.telegram_id == user_id))).scalars().first()
                if u:
                    u.user_state = "test_plan"
                    await session.commit()
            
            from utils.i18n import _
            lang = u.language if 'u' in locals() and u else 'uz'
            await message.reply(_('tutorial_expense_success', lang, amount=f"{amount:,.0f}", category=category))
            return

        if tutorial_step == "test_plan":
            # AI bilan reja tahlil qilamiz lekin bazaga saqlamaymiz
            task_data = await ai_queue.process(message, GeminiService.analyze_task, message.text)
            title = task_data.get("title", "Rejangiz") if task_data else "Rejangiz"
            
            # State ni testing_done ga o'tkazamiz
            async with session_scope() as session:
                u = (await session.execute(select(User).where(User.telegram_id == user_id))).scalars().first()
                if u:
                    u.user_state = "testing_done"
                    await session.commit()
            
            # Reja haqida javob berish
            await message.reply(
                f"'{title}' sizning rejangizga qo'shildi! 🏃\u200d\u2642\ufe0f\n\n"
                f"Zo'r! Siz botni sinab ko'rdingiz. "
                f"Endi to'liq imkoniyatlardan foydalanish uchun maxfiylik siyosatini tasdiqlang."
            )
            
            # Privacy Policy ko'rsatish
            policy_text = (
                "🔒 <b>Maxfiylik Siyosati (Privacy Policy)</b>\n\n"
                "Botimizdan foydalanishdan oldin quyidagi qoidalarga rozilik bildirishingiz kerak:\n"
                "1. Bot sizning kiritgan barcha moliyaviy ma'lumotlaringizni xavfsiz saqlaydi va uchinchi shaxslarga bermaydi.\n"
                "2. Siz xohlagan vaqtda adminga murojaat qilib barcha ma'lumotlaringizni o'chirib yuborishingiz mumkin.\n"
                "3. <b>DIQQAT:</b> Soxta referallar orqali foyda ko'rishga urinish yoki 1 kun ichida 3 marta va undan ortiq soxta Premium to'lov so'rovlarini yuborib to'lamaslik hisobingiz muzlatilishiga olib keladi.\n\n"
                "Qoidalarga rozi bo'lsangiz, tugmani bosing."
            )
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Tanishdim va qabul qilaman", callback_data="accept_privacy_policy")]
            ])
            await message.answer(policy_text, reply_markup=markup, parse_mode="HTML")
            return
        #        # 1. Analyze text with Gemini Router
        data_list = await ai_queue.process(
            message,
            GeminiService.analyze_finance_text,
            message.text, 
            daily_limit=daily_limit, 
            current_spending=current_spending, 
            dream_info=dream_info,
            chat_history=chat_history_str
        )
        
        if not data_list or not isinstance(data_list, list):
            if isinstance(data_list, dict):
                data_list = [data_list]
            else:
                from utils.i18n import _
                lang = 'uz' # We don't have user.language easily accessible here, wait we do at line 182
                lang = user.language if 'user' in locals() and user else 'uz'
                await message.answer(_('finance_error_parse', lang))
                return

        all_ai_advice = []
        needs_webapp_button = False
        report_requested = False

        for data in data_list:
            action = data.get("action", "chat")
            ai_advice = data.get("ai_advice", "")

            if action == "start_tutorial":
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎓 O'rganish", callback_data="start_tutorial_cb")]
                ])
                await message.answer(ai_advice, reply_markup=kb)
                continue

            elif action == "generate_report":
                if ai_advice:
                    all_ai_advice.append(ai_advice)
                report_requested = True
                continue

            elif action == "bot_support":
                if ai_advice:
                    all_ai_advice.append(ai_advice)
                # Automatically provide the WebApp button if kabinet is mentioned or general
                needs_webapp_button = True
                continue

            # 2. Route Action
            elif action == "save_expense":
                amount = safe_parse_amount(data.get("amount", 0))
                if amount > 0:
                    can_save = True
                    async with session_scope() as session:
                        u_res = await session.execute(select(User).where(User.telegram_id == user_id))
                        u = u_res.scalars().first()
                        is_premium_active = u.is_premium or (u.premium_until and u.premium_until > get_tashkent_time())
                        if u and not is_premium_active:
                            from datetime import date
                            today = get_tashkent_time().date()
                            start_of_month = today.replace(day=1)
                            stmt = select(func.count(Transaction.id)).where(
                                Transaction.user_id == u.id,
                                Transaction.type == 'expense',
                                cast(Transaction.timestamp, Date) >= start_of_month
                            )
                            c_res = await session.execute(stmt)
                            expense_count = c_res.scalar() or 0
                            if expense_count >= 10:
                                can_save = False
                                from utils.i18n import _
                                lang = u.language if u else 'uz'
                                all_ai_advice.append(_('free_limit_reached', lang))

                    if can_save:
                        await process_finance_record(message, data, state)
                        # Tutorial logic
                    if tutorial_step == "tutorial_step_1":
                        async with session_scope() as session:
                            u = (await session.execute(select(User).where(User.telegram_id == user_id))).scalars().first()
                            if u:
                                u.user_state = "tutorial_step_2"
                                await session.commit()
                                from datetime import timedelta
                                tutorial_time = get_tashkent_time() + timedelta(hours=5)
                                from utils.i18n import _
                                lang = u.language if u else 'uz'
                                all_ai_advice.append(_('tutorial_step_2_prompt', lang, tutorial_str=tutorial_str))
                    if ai_advice:
                        all_ai_advice.append(ai_advice)
                else:
                    if ai_advice:
                        all_ai_advice.append(ai_advice)
                    
            elif action == "add_to_dream":
                amount = safe_parse_amount(data.get("amount", 0))
                if amount > 0:
                    async with session_scope() as session:
                        result = await session.execute(select(User).where(User.telegram_id == user_id))
                        user = result.scalars().first()
                        if user:
                            stmt = select(Dream).where(Dream.user_id == user.id, Dream.is_active == True).order_by(Dream.created_at.desc()).limit(1)
                            res = await session.execute(stmt)
                            dream = res.scalars().first()
                            if dream:
                                dream.saved_amount += amount
                                dream.extra_savings = (dream.extra_savings or 0) + amount
                                await session.commit()
                                if ai_advice:
                                    from utils.i18n import _
                                    lang = user.language if user else 'uz'
                                    all_ai_advice.append(_('added_to_dream_box', lang, amount=f"{amount:,.0f}", advice=ai_advice))
                            else:
                                from utils.i18n import _
                                lang = user.language if user else 'uz'
                                all_ai_advice.append(_('no_active_dream_box', lang))
                else:
                    if ai_advice:
                        all_ai_advice.append(ai_advice)

            elif action == "add_task":
                async with session_scope() as session:
                    result = await session.execute(select(User).where(User.telegram_id == user_id))
                    user = result.scalars().first()
                    if not user:
                        is_user_valid = False
                        is_prem = False
                        user_lang = 'uz'
                    else:
                        is_user_valid = True
                        is_prem = user.is_premium or (user.premium_until and user.premium_until > get_tashkent_time())
                        user_lang = user.language or 'uz'

                if is_user_valid:
                    if not is_prem:
                        from utils.i18n import _
                        all_ai_advice.append(_('premium_task_only', user_lang))
                        needs_webapp_button = True
                    else:
                        task_title = data.get("task", "Yangi vazifa")
                        try:
                            task_data = await ai_queue.process(message, GeminiService.analyze_task, task_title)
                            if task_data and task_data.get("title"):
                                task_title = task_data.get("title")
                            task_description = task_data.get("description") if task_data else None
                            due_date_str = (task_data.get("due_date") if task_data else None) or data.get("due_date")
                        except Exception:
                            due_date_str = data.get("due_date")
                            task_description = None

                        if due_date_str == "needs_clarification":
                            from utils.i18n import _
                            all_ai_advice.append(_('task_time_clarify', user_lang))
                        else:
                            due_date = parse_ai_due_date(due_date_str)
                            task_saved_id = None
                            async with session_scope() as session:
                                res_u = await session.execute(select(User).where(User.telegram_id == user_id))
                                u_db = res_u.scalars().first()
                                if u_db:
                                    new_task = Task(user_id=u_db.id, title=task_title, description=task_description, due_date=due_date, is_ai_generated=True, is_notified=False, is_completed=False, created_at=get_tashkent_time())
                                    session.add(new_task)
                                    await session.commit()
                                    task_saved_id = new_task.id

                            if task_saved_id:
                                from utils.i18n import _
                                if due_date:
                                    all_ai_advice.append(_('task_time_accepted', user_lang, advice=ai_advice, time_str=due_date.strftime('%H:%M %d.%m.%Y')))
                                elif due_date_str == "past_date":
                                    all_ai_advice.append(_('task_past_time', user_lang))
                                    await state.set_state(FinanceState.waiting_for_task_time)
                                    await state.update_data(task_id=task_saved_id)
                                else:
                                    all_ai_advice.append(_('task_saved_no_time', user_lang, advice=ai_advice))
                                    await state.set_state(FinanceState.waiting_for_task_time)
                                    await state.update_data(task_id=task_saved_id)

                    if tutorial_step == "tutorial_step_2":
                        async with session_scope() as session_t:
                            u = (await session_t.execute(select(User).where(User.telegram_id == user_id))).scalars().first()
                            if u:
                                u.user_state = "tutorial_step_3"
                                await session_t.commit()
                                from utils.i18n import _
                                lang = u.language if u else 'uz'
                                all_ai_advice.append(_('tutorial_step_3_prompt', lang))

            elif action == "manage_debt":
                async with session_scope() as session:
                    result = await session.execute(select(User).where(User.telegram_id == user_id))
                    user = result.scalars().first()
                    if user:
                        if not is_premium_active(user):
                            ai_advice = "⚠️ **Qarzlar hisobi** bo'limi faqat Premium foydalanuvchilar uchun ochiq. /premium orqali obuna bo'ling."
                        else:
                            count_stmt = select(func.count(Debt.id)).where(
                                Debt.user_id == user.id,
                                func.extract('month', Debt.created_at) == now_tz.month,
                                func.extract('year', Debt.created_at) == now_tz.year
                            )
                            month_count = (await session.execute(count_stmt)).scalar() or 0
                            if month_count >= 5:
                                ai_advice = "⚠️ Premium obunachilar uchun oylik qarz yozish limiti (5 ta) tugadi."
                            else:
                                person = data.get("person", "Noma'lum shaxs")
                                amount = safe_parse_amount(data.get("amount", 0))
                                d_type = data.get("type", "loaned")
                                due_date_str = data.get("due_date")
                                due_date = parse_ai_due_date(due_date_str)
                                new_debt = Debt(user_id=user.id, person=person, amount=amount, type=d_type, due_date=due_date)
                                session.add(new_debt)
                                await session.commit()
                if ai_advice:
                    all_ai_advice.append(ai_advice)

            else: # chat
                if ai_advice:
                    all_ai_advice.append(ai_advice)

        # 3. Join AI Advice and send
        if all_ai_advice:
            final_text = "\n\n---\n\n".join(all_ai_advice)
            from handlers.start import get_main_keyboard
            
            # Setup keyboard
            kb = get_main_keyboard(user_id, 'uz')
            
            if needs_webapp_button:
                from config import WEBAPP_URL
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⚡️ Kabinetga kirish", web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={user_id}"))]
                ])

            if report_requested:
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 O'tgan oy hisoboti", callback_data="report_last_month")],
                    [InlineKeyboardButton(text="📈 Bu oy (shu kungacha)", callback_data="report_this_month")]
                ])

            await message.answer(final_text, reply_markup=kb)

        # 4. Save Chat History
        history.append(f"User: {message.text}")
        if data_list and len(data_list) > 0 and data_list[0].get("ai_advice"):
            history.append(f"AI: {data_list[0].get('ai_advice')}")
        
        await state.update_data(chat_history=history[-6:])

    except Exception as e:
        # SECURITY FIX: log full error internally, show generic message to user
        logging.exception(f"HANDLER ERROR for user {message.from_user.id}:")
        from utils.i18n import _
        await message.answer(_('error_text_handler', 'uz', error="Ichki xatolik"))



@router.message(F.voice)
async def handle_voice_finance(message: types.Message, bot: Bot, state: FSMContext):
    try:
        user_id = message.from_user.id
        
        async with session_scope() as session:
            u_res = await session.execute(select(User).where(User.telegram_id == user_id))
            u = u_res.scalars().first()
            is_premium_active = u.is_premium or (u.premium_until and u.premium_until > get_tashkent_time())
            if not u or not is_premium_active:
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💎 Premium sotib olish", callback_data="buy_premium")]
                ])
                from utils.i18n import _
                lang = u.language if u else 'uz'
                await message.reply(_('premium_voice_only', lang), reply_markup=markup)
                return

        # 0. Fetch User Context and Chat History
        state_data = await state.get_data()
        history = state_data.get("chat_history", [])
        chat_history_str = "\\n".join(history[-5:])

        daily_limit = 0
        current_spending = 0
        dream_info = None
        tutorial_step = None

        async with session_scope() as session:
            result = await session.execute(select(User).where(User.telegram_id == user_id))
            user = result.scalars().first()
            
            if user:
                tutorial_step = user.user_state
                daily_limit = user.daily_limit or 0
                today = get_tashkent_time().date()
                stmt = select(func.sum(Transaction.amount)).where(
                    Transaction.user_id == user.id,
                    Transaction.type == 'expense',
                    cast(Transaction.timestamp, Date) == today
                )
                res = await session.execute(stmt)
                current_spending = float(res.scalar() or 0.0)

                stmt_dream = select(Dream).where(Dream.user_id == user.id, Dream.is_active == True).order_by(Dream.created_at.desc()).limit(1)
                res_dream = await session.execute(stmt_dream)
                dream = res_dream.scalars().first()
                
                if dream:
                    dream_info = {
                        "name": dream.dream_name,
                        "total_amount": dream.total_amount,
                        "saved_amount": dream.saved_amount,
                        "daily_limit_target": dream.daily_limit_target
                    }

        # Download voice file — unique path in temp dir, guaranteed cleanup via finally
        voice = message.voice
        file_info = await bot.get_file(voice.file_id)
        # SECURITY FIX: unique temp path (no filename collision), cleaned up in finally block
        import tempfile, uuid
        local_path = os.path.join(tempfile.gettempdir(), f"voice_{uuid.uuid4().hex}.ogg")
        await bot.download_file(file_info.file_path, local_path)

        try:
            # === TEST OQIMI (voice) ===
            if tutorial_step == "test_expense":
                data = await ai_queue.process(
                    message, GeminiService.analyze_finance_audio,
                    local_path, daily_limit=35000, current_spending=0
                )
                # Normalize: AI may return a list of actions
                if isinstance(data, list):
                    data = data[0] if data else {}
                amount = data.get("amount", 35000) if data else 35000
                category = data.get("category", "Ovqat") if data else "Ovqat"
                async with session_scope() as session:
                    u = (await session.execute(select(User).where(User.telegram_id == user_id))).scalars().first()
                    if u:
                        u.user_state = "test_plan"
                        await session.commit()
                from utils.i18n import _
                lang = u.language if 'u' in locals() and u else 'uz'
                await message.reply(_('tutorial_expense_success', lang, amount=f"{amount:,.0f}", category=category))
                return

            if tutorial_step == "test_plan":
                data = await ai_queue.process(
                    message, GeminiService.analyze_finance_audio,
                    local_path, daily_limit=0, current_spending=0
                )
                # Normalize: AI may return a list of actions
                if isinstance(data, list):
                    data = data[0] if data else {}
                title = data.get("task", "Rejangiz") if data else "Rejangiz"
                lang = 'uz'
                async with session_scope() as session:
                    u = (await session.execute(select(User).where(User.telegram_id == user_id))).scalars().first()
                    if u:
                        u.user_state = "testing_done"
                        lang = u.language or 'uz'
                        await session.commit()
                from utils.i18n import _
                await message.reply(_('tutorial_plan_success_privacy', lang, title=title))
                policy_text = _('privacy_policy_text', lang)
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=_('privacy_policy_accept', lang), callback_data="accept_privacy_policy")]
                ])
                await message.answer(policy_text, reply_markup=markup, parse_mode="HTML")
                return
            # === TEST OQIMI TUGADI ===

            data_list = await ai_queue.process(
                message,
                GeminiService.analyze_finance_audio,
                local_path, 
                daily_limit=daily_limit, 
                current_spending=current_spending, 
                dream_info=dream_info,
                chat_history=chat_history_str
            )
            
            if not data_list or not isinstance(data_list, list):
                if isinstance(data_list, dict):
                    data_list = [data_list]
                else:
                    from utils.i18n import _
                    lang = 'uz'
                    if 'user' in locals() and user: lang = user.language
                    await message.answer(_('finance_error_parse', lang))
                    return

            all_ai_advice = []
            needs_webapp_button = False
            report_requested = False

            for data in data_list:
                action = data.get("action", "chat")
                ai_advice = data.get("ai_advice", "")

                if action == "start_tutorial":
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🎓 O'rganish", callback_data="start_tutorial_cb")]
                    ])
                    await message.answer(ai_advice, reply_markup=kb)
                    continue

                elif action == "generate_report":
                    if ai_advice:
                        all_ai_advice.append(ai_advice)
                    report_requested = True
                    continue

                elif action == "bot_support":
                    if ai_advice:
                        all_ai_advice.append(ai_advice)
                    needs_webapp_button = True
                    continue

                # Route Action
                elif action == "save_expense":
                    amount = safe_parse_amount(data.get("amount", 0))
                    if amount > 0:
                        await process_finance_record(message, data, state)
                        # Tutorial logic
                        if tutorial_step == "tutorial_step_1":
                            async with session_scope() as session:
                                u = (await session.execute(select(User).where(User.telegram_id == user_id))).scalars().first()
                                if u:
                                    u.user_state = "tutorial_step_2"
                                    await session.commit()
                                    from datetime import timedelta
                                    tutorial_time = get_tashkent_time() + timedelta(hours=5)
                                    tutorial_str = f"{tutorial_time.hour}:{tutorial_time.minute:02d}"
                                    from utils.i18n import _
                                    lang = u.language if u else 'uz'
                                    all_ai_advice.append(_('tutorial_step_2_prompt', lang, tutorial_str=tutorial_str))
                        if ai_advice:
                            all_ai_advice.append(ai_advice)
                    else:
                        if ai_advice:
                            all_ai_advice.append(ai_advice)
                        
                elif action == "add_to_dream":
                    amount = safe_parse_amount(data.get("amount", 0))
                    if amount > 0:
                        async with session_scope() as session:
                            result = await session.execute(select(User).where(User.telegram_id == user_id))
                            user = result.scalars().first()
                            if user:
                                stmt = select(Dream).where(Dream.user_id == user.id, Dream.is_active == True).order_by(Dream.created_at.desc()).limit(1)
                                res = await session.execute(stmt)
                                dream = res.scalars().first()
                                if dream:
                                    dream.saved_amount += amount
                                    dream.extra_savings = (dream.extra_savings or 0) + amount
                                    await session.commit()
                                    if ai_advice:
                                        from utils.i18n import _
                                        lang = user.language if user else 'uz'
                                        all_ai_advice.append(_('added_to_dream_box', lang, amount=f"{amount:,.0f}", advice=ai_advice))
                                else:
                                    from utils.i18n import _
                                    lang = user.language if user else 'uz'
                                    all_ai_advice.append(_('no_active_dream_box', lang))
                    else:
                        if ai_advice:
                            all_ai_advice.append(ai_advice)

                elif action == "add_task":
                    async with session_scope() as session:
                        result = await session.execute(select(User).where(User.telegram_id == user_id))
                        user = result.scalars().first()
                        user_lang = (user.language or 'uz') if user else 'uz'

                    task_title = data.get("task", "Yangi vazifa")
                    try:
                        task_data = await ai_queue.process(message, GeminiService.analyze_task, task_title)
                        if task_data and task_data.get("title"):
                            task_title = task_data.get("title")
                        task_description = task_data.get("description") if task_data else None
                        due_date_str = (task_data.get("due_date") if task_data else None) or data.get("due_date")
                    except Exception:
                        due_date_str = data.get("due_date")
                        task_description = None

                    if due_date_str == "needs_clarification":
                        from utils.i18n import _
                        all_ai_advice.append(_('task_time_clarify', user_lang))
                    else:
                        due_date = parse_ai_due_date(due_date_str)
                        task_saved_id = None
                        async with session_scope() as session:
                            res_u = await session.execute(select(User).where(User.telegram_id == user_id))
                            u_db = res_u.scalars().first()
                            if u_db:
                                new_task = Task(user_id=u_db.id, title=task_title, description=task_description, due_date=due_date, is_ai_generated=True, is_notified=False, is_completed=False, created_at=get_tashkent_time())
                                session.add(new_task)
                                await session.commit()
                                task_saved_id = new_task.id

                        if task_saved_id:
                            from utils.i18n import _
                            if due_date:
                                all_ai_advice.append(_('task_time_accepted', user_lang, advice=ai_advice, time_str=due_date.strftime('%H:%M %d.%m.%Y')))
                            elif due_date_str == "past_date":
                                all_ai_advice.append(_('task_past_time', user_lang))
                                await state.set_state(FinanceState.waiting_for_task_time)
                                await state.update_data(task_id=task_saved_id)
                            else:
                                all_ai_advice.append(_('task_saved_no_time', user_lang, advice=ai_advice))
                                await state.set_state(FinanceState.waiting_for_task_time)
                                await state.update_data(task_id=task_saved_id)

                    if tutorial_step == "tutorial_step_2":
                        async with session_scope() as session_t:
                            u = (await session_t.execute(select(User).where(User.telegram_id == user_id))).scalars().first()
                            if u:
                                u.user_state = "tutorial_step_3"
                                await session_t.commit()
                                from utils.i18n import _
                                lang = u.language if u else 'uz'
                                all_ai_advice.append(_('tutorial_step_3_prompt', lang))

                elif action == "manage_debt":
                    async with session_scope() as session:
                        result = await session.execute(select(User).where(User.telegram_id == user_id))
                        user = result.scalars().first()
                        if user:
                            if not is_premium_active(user):
                                ai_advice = "⚠️ **Qarzlar hisobi** bo'limi faqat Premium foydalanuvchilar uchun ochiq. /premium orqali obuna bo'ling."
                            else:
                                count_stmt = select(func.count(Debt.id)).where(
                                    Debt.user_id == user.id,
                                    func.extract('month', Debt.created_at) == now_tz.month,
                                    func.extract('year', Debt.created_at) == now_tz.year
                                )
                                month_count = (await session.execute(count_stmt)).scalar() or 0
                                if month_count >= 5:
                                    ai_advice = "⚠️ Premium obunachilar uchun oylik qarz yozish limiti (5 ta) tugadi."
                                else:
                                    person = data.get("person", "Noma'lum shaxs")
                                    amount = safe_parse_amount(data.get("amount", 0))
                                    d_type = data.get("type", "loaned")
                                    due_date_str = data.get("due_date")
                                    due_date = parse_ai_due_date(due_date_str)
                                    new_debt = Debt(user_id=user.id, person=person, amount=amount, type=d_type, due_date=due_date)
                                    session.add(new_debt)
                                    await session.commit()
                    if ai_advice:
                        all_ai_advice.append(ai_advice)

                else: # chat
                    if ai_advice:
                        all_ai_advice.append(ai_advice)

            if all_ai_advice:
                final_text = "\n\n---\n\n".join(all_ai_advice)
                from handlers.start import get_main_keyboard
                kb = get_main_keyboard(user_id, 'uz')
                
                if needs_webapp_button:
                    from config import WEBAPP_URL
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="⚡️ Kabinetga kirish", web_app=WebAppInfo(url=f"{WEBAPP_URL}?user_id={user_id}"))]
                    ])

                if report_requested:
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📊 O'tgan oy hisoboti", callback_data="report_last_month")],
                        [InlineKeyboardButton(text="📈 Bu oy (shu kungacha)", callback_data="report_this_month")]
                    ])

                await message.answer(final_text, reply_markup=kb)

            # Save Chat History
            history.append(f"User: (Ovozli xabar)")
            if data_list and len(data_list) > 0 and data_list[0].get("ai_advice"):
                history.append(f"AI: {data_list[0].get('ai_advice')}")
            
            await state.update_data(chat_history=history[-6:])
        finally:
            if os.path.exists(local_path):
                os.remove(local_path)

    except Exception as e:
        # SECURITY FIX: log full error internally, show generic message to user
        logging.exception(f"VOICE HANDLER MAIN ERROR for user {message.from_user.id}:")
        from utils.i18n import _
        await message.answer(_('voice_error_parse', 'uz', error="Ovozli xabarni qayta ishlashda xatolik"))


# ==================== QARZ TIZIMI (DEBTS) ====================

class DebtActionCallback(CallbackData, prefix="debt_act"):
    action: str  # "paid" | "delete"
    debt_id: int

@router.message(Command("debts"))
@router.message(F.text.in_(["💸 Qarzlarim", "My debts", "Мои долги"]))
async def show_debts(message: types.Message):
    """Foydalanuvchining barcha faol qarzlarini ko'rsatadi."""
    user_id = message.from_user.id
    try:
        async with session_scope() as session:
            result = await session.execute(select(User).where(User.telegram_id == user_id))
            user = result.scalars().first()
            if not user:
                from utils.i18n import _
                await message.answer(_('user_not_found', 'uz'))
                return

            stmt = select(Debt).where(Debt.user_id == user.id, Debt.is_active == True).order_by(Debt.created_at.desc())
            debts = (await session.execute(stmt)).scalars().all()

            if not debts:
                from utils.i18n import _
                lang = user.language or 'uz'
                await message.answer(_('no_active_debt_with_hint', lang))
                return

            # Categorize
            loaned = [d for d in debts if d.type == "loaned"]   # Men berdim
            borrowed = [d for d in debts if d.type == "borrowed"]  # Men oldim

            from utils.i18n import _
            lang = user.language or 'uz'
            text = _('debts_list_title', lang)
            buttons = []

            if loaned:
                text += _('loaned_title', lang)
                for d in loaned:
                    due = f" | Muddat: {d.due_date.strftime('%d.%m.%Y')}" if d.due_date else ""
                    text += f"  • {d.person}: `{d.amount:,.0f}` so'm{due}\n"
                    buttons.append([InlineKeyboardButton(
                        text=_('debt_paid_btn', lang, person=d.person),
                        callback_data=DebtActionCallback(action="paid", debt_id=d.id).pack()
                    )])

            if borrowed:
                text += _('borrowed_title', lang)
                for d in borrowed:
                    due = f" | Muddat: {d.due_date.strftime('%d.%m.%Y')}" if d.due_date else ""
                    text += f"  • {d.person}dan: `{d.amount:,.0f}` so'm{due}\n"
                    buttons.append([InlineKeyboardButton(
                        text=_('debt_repaid_btn', lang, person=d.person),
                        callback_data=DebtActionCallback(action="paid", debt_id=d.id).pack()
                    )])

            total_loaned = sum(d.amount for d in loaned)
            total_borrowed = sum(d.amount for d in borrowed)
            text += _('debts_total_summary', lang, total_loaned=total_loaned, total_borrowed=total_borrowed)

            kb = InlineKeyboardMarkup(inline_keyboard=buttons)
            await message.answer(text, parse_mode="Markdown", reply_markup=kb)

    except Exception as e:
        import logging
        logging.exception("DEBTS HANDLER ERROR:")
        from utils.i18n import _
        await message.answer(_('debt_error_view', 'uz'))


@router.callback_query(DebtActionCallback.filter())
async def handle_debt_action(callback: CallbackQuery, callback_data: DebtActionCallback):
    """Qarzni 'qaytarildi' deb belgilash."""
    try:
        async with session_scope() as session:
            debt = await session.get(Debt, callback_data.debt_id)
            if not debt:
                from utils.i18n import _
                await callback.answer(_('debt_not_found', 'uz'), show_alert=True)
                return

            # SECURITY FIX: verify ownership before modifying debt record
            # Prevents any user from closing another user's debt via crafted callback data
            owner_res = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
            owner = owner_res.scalars().first()
            if not owner or debt.user_id != owner.id:
                await callback.answer("Ruxsat yo'q.", show_alert=True)
                return

            debt.is_active = False
            await session.commit()

            from utils.i18n import _
            lang = 'uz'
            res = await session.execute(select(User).where(User.id == debt.user_id))
            user = res.scalars().first()
            if user and user.language: lang = user.language

            # Action text requires specific logic or handled gracefully
            action_text = "qaytardi" if debt.type == "loaned" else "qaytardim"
            if lang == 'ru': action_text = "вернул" if debt.type == "loaned" else "вернул"
            if lang == 'en': action_text = "returned" if debt.type == "loaned" else "returned"
            
            await callback.message.edit_text(
                _('debt_closed_msg', lang, person=debt.person, action_text=action_text, amount=debt.amount),
                parse_mode="Markdown"
            )
            await callback.answer(_('debt_closed_success', lang))

    except Exception as e:
        import logging
        logging.exception("DEBT ACTION ERROR:")
        from utils.i18n import _
        await callback.answer(_('error_occurred', 'uz'), show_alert=True)


class CurrencyConfirmationCallback(CallbackData, prefix="cur_conf"):
    action: str
    currency: str

@router.callback_query(CurrencyConfirmationCallback.filter())
async def handle_currency_confirmation(callback: CallbackQuery, callback_data: CurrencyConfirmationCallback, state: FSMContext):
    user_id = callback.from_user.id
    data_cache = await state.get_data()
    finance_data = data_cache.get("temp_finance_data")
    
    if not finance_data:
        from utils.i18n import _
        await callback.answer(_('error_try_again', 'uz'), show_alert=True)
        await state.clear()
        return
        
    action = callback_data.action
    currency = callback_data.currency
    
    if action == "yes":
        async with session_scope() as session:
            result = await session.execute(select(User).where(User.telegram_id == user_id))
            user = result.scalars().first()
            if user:
                active = getattr(user, 'active_currencies', '') or 'UZS'
                active_list = [c.strip().upper() for c in active.split(',') if c.strip()]
                if currency not in active_list:
                    active_list.append(currency)
                    user.active_currencies = ','.join(active_list)
                    await session.commit()
            
        from utils.i18n import _
        lang = user.language if 'user' in locals() and user else 'uz'
        await callback.message.edit_text(_('new_currency_saved', lang, currency=currency))
        await finalize_finance_record(callback.message, finance_data, user_id)
    else:
        from utils.i18n import _
        lang = 'uz'
        await callback.message.edit_text(_('new_currency_rejected', lang))
        await finalize_finance_record(callback.message, finance_data, user_id)
        
    await state.clear()

async def process_finance_record(message: types.Message, data: dict, state: FSMContext):
    user_id = message.from_user.id
    currency = data.get("currency", "UZS").strip().upper()
    if currency != "UZS":
        async with session_scope() as session:
            result = await session.execute(select(User).where(User.telegram_id == user_id))
            user = result.scalars().first()
            if user:
                active_currencies = getattr(user, 'active_currencies', '') or 'UZS'
                active_list = [c.strip().upper() for c in active_currencies.split(',') if c.strip()]
                if currency not in active_list:
                    await state.set_state(FinanceState.waiting_for_currency_confirmation)
                    await state.update_data(temp_finance_data=data)
                    
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Ha", callback_data=CurrencyConfirmationCallback(action="yes", currency=currency).pack()),
                         InlineKeyboardButton(text="Yo'q", callback_data=CurrencyConfirmationCallback(action="no", currency=currency).pack())]
                    ])
                    from utils.i18n import _
                    lang = user.language if user else 'uz'
                    await message.answer(_('new_currency_prompt', lang, currency=currency), reply_markup=kb)
                    return
            
    await finalize_finance_record(message, data, user_id)

async def finalize_finance_record(message: types.Message, data: dict, user_id: int = None):
    user_id = user_id or message.from_user.id
    async with session_scope() as session:
        try:
            # 1. Foydalanuvchini topish
            result = await session.execute(select(User).where(User.telegram_id == user_id))
            user = result.scalars().first()
            
            if not user:
                from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
                from config import WEBAPP_URL
                kb = ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="📝 Ro'yxatdan o'tish", web_app=WebAppInfo(url=f"{WEBAPP_URL}/web/register?user_id={user_id}"))]],
                    resize_keyboard=True
                )
                await message.answer("⚠️ Iltimos, avval ro'yxatdan o'ting:", reply_markup=kb)
                return

            # 2. Ma'lumotlarni tayyorlash
            amount = safe_parse_amount(data.get("amount", 0))
            category = data.get("category") or "Noma'lum" # Default to Unknown if missing/empty
            description = data.get("description") or "Noma'lum" # Default to Unknown if missing/empty
            
            # Item type logic: unknown -> expense
            raw_type = data.get("item_type", "")
            if not raw_type or raw_type.lower() not in ["income", "expense", "kirim", "chiqim", "daromad"]:
                item_type = "expense"
            else:
                item_type = raw_type

            ai_advice = data.get("ai_advice")
            currency = data.get("currency", "UZS")
            due_date = parse_ai_due_date(data.get("due_date"))

            # 3. Yagona jadvalga yozish (ilgari finances + transactions ga ikki marta yozilardi)
            new_trans = record_transaction(
                session,
                user_id=user.id,
                amount=amount,
                category=category,
                tx_type=item_type,
                currency=currency,
                description=description,
                ai_advice=ai_advice,
                due_date=due_date,
            )

            # 4. Balansni yangilash
            if is_income(item_type):
                user.balance += amount
            else:
                user.balance -= amount

            # Bazaga yuborishni majburlash
            await session.flush()
            # Tasdiqlash
            await session.commit()

            import logging
            logging.info(f"Yangi xarajat bazaga yozildi: {amount} {currency} ({category}) - ID: {new_trans.id}")

        except Exception as e:
            await session.rollback()
            # SECURITY FIX: log full error internally, never expose DB details to user
            logging.exception(f"DATABASE ERROR IN FINANCE for user {user_id}:")
            await message.answer("⚠️ Ma'lumotni saqlashda xatolik yuz berdi. Iltimos keyinroq qayta urinib ko'ring.")


# Callback Data Structure
class DreamOptionCallback(CallbackData, prefix="dream_opt"):
    action: str # "deadline" or "daily"
    amount: float
    dream_id: int

@router.message(Command("invest_dream"))
async def handle_invest_dream_command(message: types.Message):
    try:
        # Parse amount from command: /invest_dream 50000
        args = message.text.split()
        if len(args) < 2:
            from utils.i18n import _
            await message.answer(_('invest_dream_prompt', 'uz'))
            return
        
        try:
            amount = float(args[1])
        except ValueError:
            from utils.i18n import _
            await message.answer(_('invest_dream_invalid_amount', 'uz'))
            return

        user_id = message.from_user.id
        async with session_scope() as session:
            # Find active dream
            stmt_dream = select(Dream).where(
                Dream.user_id == select(User.id).where(User.telegram_id == user_id).scalar_subquery(),
                Dream.is_active == True
            ).order_by(Dream.created_at.desc()).limit(1)
            res_dream = await session.execute(stmt_dream)
            dream = res_dream.scalars().first()
            
            if not dream:
                from utils.i18n import _
                lang = 'uz'
                res = await session.execute(select(User).where(User.id == user_id))
                user = res.scalars().first()
                if user and user.language: lang = user.language
                await message.answer(_('no_active_dream', lang))
                return

            # Analyze impact with Gemini
            analysis_text = await ai_queue.process(
                message,
                GeminiService.analyze_extra_savings_impact,
                dream_name=dream.dream_name,
                total_amount=dream.total_amount,
                saved_amount=dream.saved_amount, # corrected kwarg
                daily_limit=dream.daily_limit_target,
                deadline=dream.deadline,
                extra_amount=amount
            )

            from utils.i18n import _
            lang = 'uz'
            res = await session.execute(select(User).where(User.id == user_id))
            user = res.scalars().first()
            if user and user.language: lang = user.language
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=_('dream_option_deadline', lang), 
                        callback_data=DreamOptionCallback(action="deadline", amount=amount, dream_id=dream.id).pack()
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=_('dream_option_daily', lang), 
                        callback_data=DreamOptionCallback(action="daily", amount=amount, dream_id=dream.id).pack()
                    )
                ]
            ])
            
            await message.answer(analysis_text, reply_markup=kb, parse_mode="Markdown")

    except Exception as e:
        logging.error(f"Invest dream error: {e}")
        from utils.i18n import _
        await message.answer(_('error_occurred', 'uz'))

@router.callback_query(DreamOptionCallback.filter())
async def handle_dream_option_selection(callback: CallbackQuery, callback_data: DreamOptionCallback):
    try:
        async with session_scope() as session:
            dream = await session.get(Dream, callback_data.dream_id)
            if not dream:
                from utils.i18n import _
                await callback.answer(_('dream_not_found', 'uz'), show_alert=True)
                return

            extra_amount = callback_data.amount
            
            # Update common fields
            dream.saved_amount += extra_amount
            dream.extra_savings = (dream.extra_savings or 0) + extra_amount
            
            from utils.i18n import _
            lang = 'uz'
            res = await session.execute(select(User).where(User.id == dream.user_id))
            user = res.scalars().first()
            if user and user.language: lang = user.language

            msg = ""
            if callback_data.action == "deadline":
                remaining = dream.total_amount - dream.saved_amount
                if remaining <= 0:
                     days_needed = 0
                     dream.is_active = False
                     msg = _('dream_achieved', lang)
                else:
                     days_needed = int(remaining / dream.daily_limit_target) if dream.daily_limit_target > 0 else 0
                     from datetime import timedelta
                     dream.deadline = get_tashkent_time() + timedelta(days=days_needed)
                     msg = _('dream_deadline_reduced', lang, days=days_needed)

            elif callback_data.action == "daily":
                remaining_days = (dream.deadline - get_tashkent_time()).days
                if remaining_days <= 0:
                    remaining_days = 1 
                
                remaining_amount = dream.total_amount - dream.saved_amount
                if remaining_amount <= 0:
                    dream.is_active = False
                    dream.daily_limit_target = 0
                    msg = _('dream_achieved', lang)
                else:
                    new_daily = remaining_amount / remaining_days
                    dream.daily_limit_target = new_daily
                    msg = _('dream_daily_reduced', lang, amount=new_daily)

            session.add(dream)
            await session.commit()
            
            await callback.message.edit_text(msg) # Replace Gemini analysis with confirmation
            await callback.answer()

    except Exception as e:
        logging.error(f"Creation option error: {e}")
        try:
            from utils.error_sender import send_error_to_channel
            await send_error_to_channel(callback.message.bot, e, "Finance Callback Options", callback.from_user.id)
        except Exception:
            pass
        from utils.i18n import _
        await callback.answer(_('error_occurred', 'uz'), show_alert=True)


from utils.report_generator import generate_excel_report, generate_pdf_report
from aiogram.types import BufferedInputFile
from datetime import timedelta
import calendar

@router.callback_query(F.data.in_(["report_last_month", "report_this_month", "report_weekly"]))
async def handle_report_generation(callback: CallbackQuery):
    from utils.i18n import _
    await callback.message.edit_text(_('report_generating', 'uz'))
    user_id = callback.from_user.id
    action = callback.data
    
    tashkent_now = get_tashkent_time()
    
    if action == "report_this_month":
        start_date = tashkent_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = tashkent_now
    elif action == "report_last_month":
        # First day of this month
        first_of_this = tashkent_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = first_of_this - timedelta(seconds=1)
        start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else: # report_weekly
        start_date = (tashkent_now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = tashkent_now

    try:
        async with session_scope() as session:
            result = await session.execute(select(User).where(User.telegram_id == user_id))
            user = result.scalars().first()
            if not user:
                from utils.i18n import _
                await callback.message.edit_text(_('user_not_found', 'uz'))
                return

            stmt_tx = select(Transaction).where(
                Transaction.user_id == user.id,
                Transaction.timestamp >= start_date,
                Transaction.timestamp <= end_date
            )
            transactions = (await session.execute(stmt_tx)).scalars().all()

            stmt_tasks = select(Task).where(
                Task.user_id == user.id,
                Task.created_at >= start_date,
                Task.created_at <= end_date
            )
            tasks = (await session.execute(stmt_tasks)).scalars().all()
            
            user_name = user.name or "Hurmatli foydalanuvchi"
            
            # Generate files
            excel_bytes = await generate_excel_report(transactions, tasks, start_date, end_date, lang=user.language or 'uz')
            pdf_bytes = generate_pdf_report(transactions, tasks, start_date, end_date, user_name=user_name)
            
            excel_file = BufferedInputFile(excel_bytes.read(), filename=f"Hisobot_{start_date.strftime('%Y-%m-%d')}.xlsx")
            pdf_file = BufferedInputFile(pdf_bytes.read(), filename=f"Hisobot_{start_date.strftime('%Y-%m-%d')}.pdf")
            
            await callback.message.delete()
            await callback.message.answer_document(document=excel_file, caption=f"📊 Excell farmatidagi hisobot ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})")
            await callback.message.answer_document(document=pdf_file, caption=f"📄 PDF farmatidagi hisobot ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')})")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        await callback.message.edit_text("⚠️ Hisobot yuklashda xatolik yuz berdi.")
