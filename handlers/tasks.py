import logging
from aiogram import Router, types, F, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from services.gemini_service import GeminiService
from services.ai_queue import ai_queue
from database.engine import session_scope
from database.models import Task, User
from sqlalchemy import select
from datetime import datetime, timedelta
import os

from utils.timezone import get_tashkent_time
#salom
router = Router()

@router.message(Command("task"))
async def handle_task_command(message: types.Message):
    """
    Handle /task command.
    Example: /task Buy milk tomorrow
    """
    text = message.text.replace("/task", "").strip()
    if not text:
        from utils.i18n import _
        lang = 'uz'
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
            u = res.scalars().first()
            if u and u.language: lang = u.language
        await message.answer(_('task_prompt', lang))
        return
    
    await process_task_creation(message, text)

# Handle text messages that might be tasks, but for now enforcing command or explicit context might be better.
# However, user said "Task Creation: Foydalanuvchi matn yoki ovoz orqali vazifa kiritganda..."
# To avoid conflict with Finance, let's use a keyword or specific command, OR generic text handler if not finance.
# But Finance handler takes ALL text currently. 
# Strategy: We can add a keyword check in Finance handler OR just strictly use /task for now.
# User request implies seamlessness. 
# Let's implement /task first. For voice, we can check if it contains task keywords if not finance.
# But given the complexity, let's stick to /task command for text, and maybe "Vazifa: ..." prefix support?

# Placeholder for voice - heavily dependent on unified routing.
# We will focus on text /task for this step as per plan.

async def process_task_creation(message: types.Message, text: str):
    try:
        from utils.i18n import _
        user_id = message.from_user.id
        lang = 'uz'
        
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = res.scalars().first()
            if user and user.language: lang = user.language
            
        data = await ai_queue.process(message, GeminiService.analyze_task, text)
        
        title = data.get("title")
        description = data.get("description")
        due_date_str = data.get("due_date")
        
        if not title:
            await message.answer(_('task_unrecognized', lang))
            return

        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        
        async with session_scope() as session:
            # Get User again in a new session block to actually add task
            res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = res.scalars().first()
            
            if not user:
                await message.answer(_('register_first', lang))
                return

            new_task = Task(
                user_id=user.id,
                title=title,
                description=description,
                due_date=due_date,
                is_completed=False,
                is_notified=False, # Explicitly set default
                created_at=get_tashkent_time() # Explicitly set creation time
            )
            
            try:
                session.add(new_task)
                await session.commit()
                
                msg = _('task_added', lang, title=title)
                if due_date:
                    msg += _('task_due', lang, due_date=due_date.strftime('%Y-%m-%d %H:%M'))
                
                await message.answer(msg, parse_mode="Markdown")

            except Exception as e:
                await session.rollback()
                import traceback
                traceback.print_exc()
                await message.answer(_('task_save_error', lang))
                
    except Exception as e:
        logging.error(f"Task creation error: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to uz if lang is not set
        from utils.i18n import _
        await message.answer(_('error_occurred', 'uz'))

from aiogram.types import CallbackQuery
from aiogram.filters.callback_data import CallbackData
from services.scheduler import TaskCallback

@router.callback_query(TaskCallback.filter())
async def handle_task_action(callback: CallbackQuery, callback_data: TaskCallback):
    try:
        from utils.i18n import _
        lang = 'uz'
        async with session_scope() as session:
            task = await session.get(Task, callback_data.task_id)
            if not task:
                await callback.answer(_('task_not_found', lang), show_alert=True)
                return

            res = await session.execute(select(User).where(User.id == task.user_id))
            user = res.scalars().first()
            if user and user.language: lang = user.language

            # Fetch Dream for context if needed
            from database.models import Dream
            stmt_dream = select(Dream).where(Dream.user_id == task.user_id, Dream.is_active == True)
            dream_res = await session.execute(stmt_dream)
            dream = dream_res.scalars().first()
            dream_name = dream.dream_name if dream else None

            action = callback_data.action
            
            markup = None
            msg_header = "❓"
            if action == "done":
                task.is_completed = True
                await session.commit()
                msg_header = _('task_done', lang)
                if dream:
                    markup = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=_('add_extra_dream_btn', lang), callback_data=f"add_extra_dream_{dream.id}")]
                    ])
            elif action == "missed":
                msg_header = _('task_missed', lang)
                # Keep is_completed False
            elif action == "later":
                msg_header = _('task_later', lang)
                # Keep is_completed False. Maybe reschedule? 
                # User didn't specify rescheduling logic, just feedback.
                # But 'later' implies it's still due or due later.
                # For now, just feedback.

            # Get Context-Aware Feedback
            feedback_text = await ai_queue.process(
                callback,
                GeminiService.provide_task_feedback,
                task_title=task.title,
                action=action,
                dream_name=dream_name
            )

            await callback.message.edit_text(f"{msg_header}\n\n📝 {task.title}\n\n🤖 {feedback_text}", parse_mode="Markdown", reply_markup=markup)
            await callback.answer()
            
    except Exception as e:
        logging.error(f"Task action error: {e}")
        from utils.i18n import _
        await callback.answer(_('error_occurred', 'uz'), show_alert=True)

@router.callback_query(F.data.startswith("add_extra_dream_"))
async def add_extra_dream_callback(call: types.CallbackQuery):
    try:
        from utils.i18n import _
        lang = 'uz'
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == call.from_user.id))
            user = res.scalars().first()
            if user and user.language: lang = user.language
            
        dream_id = int(call.data.split("_")[3])
        text = _('add_extra_dream_text', lang)
        
        await call.message.answer(text, parse_mode="Markdown")
        await call.answer()
        
    except Exception as e:
        logging.error(f"Extra dream callback error: {e}")
        from utils.i18n import _
        await call.answer(_('error_occurred', 'uz'), show_alert=True)

@router.callback_query(F.data == "daily_review_yes")
async def daily_review_yes_callback(call: types.CallbackQuery):
    try:
        from utils.i18n import _
        user_id = call.from_user.id
        from datetime import date
        today = get_tashkent_time().date()
        lang = 'uz'
        
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = res.scalars().first()
            if not user:
                await call.answer(_('user_not_found', lang))
                return
            lang = user.language or 'uz'

            from sqlalchemy import cast, Date
            stmt = select(Task).where(Task.user_id == user.id, cast(Task.due_date, Date) == today)
            tasks_today = (await session.execute(stmt)).scalars().all()
            
            if not tasks_today:
                await call.message.edit_text(_('no_tasks_today_review', lang))
                return
            
            # Copy tasks to tomorrow
            count = 0
            for t in tasks_today:
                new_due = t.due_date + timedelta(days=1) if t.due_date else None
                new_task = Task(
                    user_id=user.id,
                    title=t.title,
                    description=t.description,
                    due_date=new_due,
                    is_completed=False,
                    is_notified=False,
                    created_at=get_tashkent_time()
                )
                session.add(new_task)
                count += 1
            
            await session.commit()
            msg = _('tasks_moved_tomorrow', lang, count=count)
            await call.message.edit_text(msg)
            await call.answer()
            
    except Exception as e:
        logging.error(f"review_yes error: {e}")
        from utils.i18n import _
        await call.answer(_('error_occurred', 'uz'))

@router.callback_query(F.data == "daily_review_no")
async def daily_review_no_callback(call: types.CallbackQuery):
    try:
        user_id = call.from_user.id
        today = get_tashkent_time().date()
        
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = res.scalars().first()
            if not user: return
            
            from sqlalchemy import cast, Date
            stmt = select(Task).where(Task.user_id == user.id, cast(Task.due_date, Date) == today)
            tasks_today = (await session.execute(stmt)).scalars().all()
            
            lang = user.language or 'uz'
            if not tasks_today:
                await call.message.edit_text(_('no_plans_today', lang))
                return
            kb = []
            for t in tasks_today:
                kb.append([InlineKeyboardButton(text=f"🔄 {t.title}", callback_data=f"cp_task_{t.id}")])
            
            kb.append([InlineKeyboardButton(text=_('add_new_task_btn', lang), callback_data="add_new_task_prompt")])
            markup = InlineKeyboardMarkup(inline_keyboard=kb)
            
            await call.message.edit_text(
                _('repeat_tasks_prompt', lang),
                reply_markup=markup
            )
            await call.answer()
            
    except Exception as e:
        logging.error(f"review_no error: {e}")
        from utils.i18n import _
        await call.answer(_('error_occurred', 'uz'))

@router.callback_query(F.data.startswith("cp_task_"))
async def copy_task_callback(call: types.CallbackQuery):
    try:
        from utils.i18n import _
        task_id = int(call.data.replace("cp_task_", ""))
        user_id = call.from_user.id
        lang = 'uz'
        
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == user_id))
            user = res.scalars().first()
            if user and user.language: lang = user.language

            task = await session.get(Task, task_id)
            if not task:
                await call.answer(_('task_not_found', lang), show_alert=True)
                return
            
            # Create copy for tomorrow
            new_due = task.due_date + timedelta(days=1) if task.due_date else None
            new_task = Task(
                user_id=task.user_id,
                title=task.title,
                description=task.description,
                due_date=new_due,
                is_completed=False,
                is_notified=False,
                created_at=get_tashkent_time()
            )
            session.add(new_task)
            await session.commit()
            
            # Update inline button to show it's copied
            kb = call.message.reply_markup.inline_keyboard
            new_kb = []
            for row in kb:
                new_row = []
                for btn in row:
                    if btn.callback_data == call.data:
                        new_row.append(types.InlineKeyboardButton(text=_('task_moved_btn', lang, title=task.title), callback_data="ignore"))
                    else:
                        new_row.append(btn)
                new_kb.append(new_row)
                
            await call.message.edit_reply_markup(reply_markup=types.InlineKeyboardMarkup(inline_keyboard=new_kb))
            await call.answer(_('task_added_tomorrow', lang))
    except Exception as e:
        logging.error(f"copy_task error: {e}")
        from utils.i18n import _
        await call.answer(_('error_occurred', 'uz'))

@router.callback_query(F.data == "ignore")
async def ignore_callback(call: types.CallbackQuery):
    await call.answer()

@router.callback_query(F.data == "add_new_task_prompt")
async def add_new_task_prompt_callback(call: types.CallbackQuery):
    from utils.i18n import _
    lang = 'uz'
    async with session_scope() as session:
        res = await session.execute(select(User).where(User.telegram_id == call.from_user.id))
        user = res.scalars().first()
        if user and user.language: lang = user.language
    await call.message.answer(_('add_task_prompt', lang), parse_mode="Markdown")
    await call.answer()
