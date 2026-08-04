import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database.engine import session_scope
from database.models import User, Transaction, Dream, Task, Debt
from sqlalchemy import select, func, cast, Date
from datetime import datetime, time, timedelta
from services.gemini_service import GeminiService
import asyncio
import zoneinfo
from utils.timezone import get_tashkent_time

scheduler = AsyncIOScheduler(timezone=zoneinfo.ZoneInfo("Asia/Tashkent"))

async def weekly_summary_job(bot):
    """
    Runs every Saturday at 20:00 (UTC+5) to send a deep weekly AI analysis.
    Includes download buttons for PDF/Excel report.
    """
    tashkent_now = get_tashkent_time()
    today = tashkent_now.date()
    week_start = today - timedelta(days=7)
    start_of_period = datetime.combine(week_start, time.min)
    end_of_period = datetime.combine(today, time.max)

    async with session_scope() as session:
        # Haftalik AI tahlili premium imkoniyat — barcha foydalanuvchi uchun
        # Gemini chaqirish keraksiz xarajat va job'ning cho'zilib ketishiga sabab.
        result = await session.execute(
            select(User).where(User.premium_until > tashkent_now)
        )
        users = result.scalars().all()
        logging.info(f"Haftalik hisobot: {len(users)} premium foydalanuvchi uchun tayyorlanmoqda")

        for user in users:
            try:
                # 1. Income & Expenses for the week
                stmt_in = select(func.sum(Transaction.amount)).where(
                    Transaction.user_id == user.id,
                    Transaction.type == 'income',
                    Transaction.timestamp >= start_of_period,
                    Transaction.timestamp <= end_of_period
                )
                income = (await session.execute(stmt_in)).scalar() or 0.0

                stmt_ex = select(func.sum(Transaction.amount)).where(
                    Transaction.user_id == user.id,
                    Transaction.type == 'expense',
                    Transaction.timestamp >= start_of_period,
                    Transaction.timestamp <= end_of_period
                )
                expenses = (await session.execute(stmt_ex)).scalar() or 0.0

                daily_limit = user.daily_limit or 0

                # 2. Tasks for the week
                stmt_tasks_total = select(func.count(Task.id)).where(
                    Task.user_id == user.id,
                    Task.due_date >= start_of_period,
                    Task.due_date <= end_of_period
                )
                total_tasks = (await session.execute(stmt_tasks_total)).scalar() or 0

                stmt_tasks_done = select(func.count(Task.id)).where(
                    Task.user_id == user.id,
                    Task.due_date >= start_of_period,
                    Task.due_date <= end_of_period,
                    Task.is_completed == True
                )
                completed_tasks = (await session.execute(stmt_tasks_done)).scalar() or 0

                # 3. Active dream progress
                stmt_dream = select(Dream).where(Dream.user_id == user.id, Dream.is_active == True)
                dream = (await session.execute(stmt_dream)).scalars().first()

                dream_progress = 0
                dream_name = "Yo'q"
                dream_daily_target = 0
                if dream:
                    dream_name = dream.dream_name
                    if dream.total_amount > 0:
                        dream_progress = (dream.saved_amount / dream.total_amount) * 100
                    dream_daily_target = dream.daily_limit_target or 0

                # 4. Active debts count
                stmt_debts = select(func.count(Debt.id)).where(
                    Debt.user_id == user.id,
                    Debt.is_active == True
                )
                active_debts = (await session.execute(stmt_debts)).scalar() or 0

                # 5. Generate weekly AI summary
                summary_text = await GeminiService.generate_weekly_summary(
                    user_name=user.name or "Foydalanuvchi",
                    income=income,
                    expenses=expenses,
                    daily_limit=daily_limit,
                    completed_tasks=completed_tasks,
                    total_tasks=total_tasks,
                    dream_progress=round(dream_progress, 1),
                    dream_name=dream_name,
                    dream_daily_target=dream_daily_target,
                    active_debts=active_debts,
                    week_start=week_start.strftime('%d.%m.%Y'),
                    week_end=today.strftime('%d.%m.%Y')
                )

                # 6. Send to user with download buttons
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                report_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 O'tgan oy hisoboti", callback_data="report_last_month")],
                    [InlineKeyboardButton(text="📈 Bu oy (shu kungacha)", callback_data="report_this_month")]
                ])

                await bot.send_message(
                    user.telegram_id,
                    summary_text,
                    parse_mode="Markdown",
                    reply_markup=report_kb
                )

            except Exception as e:
                logging.error(f"Error sending weekly summary to {user.telegram_id}: {e}")

            # Telegram rate limit va Gemini kvotasini himoyalash
            await asyncio.sleep(0.1)

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData

class TaskCallback(CallbackData, prefix="task_cb"):
    action: str
    task_id: int

from sqlalchemy.orm import joinedload

async def check_due_tasks(bot):
    """
    Checks for tasks that are due and sends reminders.
    """
    now = get_tashkent_time()
    
    async with session_scope() as session:
        # Find tasks due in the past (up to now) that haven't been notified
        # And not completed
        stmt = select(Task).where(
            Task.due_date <= now,
            Task.is_notified == False,
            Task.is_completed == False,
            Task.due_date.is_not(None)
        ).options(joinedload(Task.user))
        
        result = await session.execute(stmt)
        tasks = result.scalars().all()
        
        for task in tasks:
            try:
                user = task.user
                if user and user.telegram_id:
                    # Generate AI Reminder with user name if possible
                    user_name = user.name or "Do'stim"
                    reminder_text = await GeminiService.generate_task_reminder(task.title, user_name)
                    
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="✅ Bajardim!", callback_data=TaskCallback(action="done", task_id=task.id).pack())
                        ],
                        [
                            InlineKeyboardButton(text="❌ Yo'q (Bajarilmadi)", callback_data=TaskCallback(action="missed", task_id=task.id).pack()),
                            InlineKeyboardButton(text="🕰 Keyinroq", callback_data=TaskCallback(action="later", task_id=task.id).pack())
                        ]
                    ])
                    
                    msg = f"⏰ **{reminder_text}**\n\n📝 Vazifa: **{task.title}**\n"
                    if getattr(task, 'description', None):
                        msg += f"ℹ️ {task.description}\n"
                    msg += f"📅 Muddat: {task.due_date.strftime('%H:%M %d.%m.%Y')}"
                    
                    try:
                        await bot.send_message(user.telegram_id, msg, reply_markup=kb, parse_mode="Markdown")
                        task.is_notified = True
                    except Exception as e:
                        logging.error(f"Failed to send task reminder to {user.telegram_id}: {e}")
            
            except Exception as e:
                logging.error(f"Error processing task {task.id}: {e}")
        
        await session.commit()

async def check_premium_requests(bot):
    """
    Checks for pending premium requests that have expired and processes them.
    Handles fraud strikes and account freezing.
    """
    from database.models import PremiumRequest, Settings
    from config import getenv
    now = get_tashkent_time()
    
    async with session_scope() as session:
        stmt = select(PremiumRequest).where(
            PremiumRequest.status == 'pending',
            PremiumRequest.expires_at <= now
        )
        requests = (await session.execute(stmt)).scalars().all()
        
        for req in requests:
            req.status = 'expired'
            
            res_user = await session.execute(select(User).where(User.id == req.user_id))
            user = res_user.scalars().first()
            if user and user.telegram_id:
                yesterday = now - timedelta(days=1)
                count_stmt = select(func.count(PremiumRequest.id)).where(
                    PremiumRequest.user_id == user.id,
                    PremiumRequest.status == 'expired',
                    PremiumRequest.expires_at >= yesterday
                )
                expired_count = (await session.execute(count_stmt)).scalar() or 0
                
                freeze_durations = [11, 90, 210, 36500] 
                
                is_frozen_now = False
                freeze_msg = ""
                if expired_count >= 3:
                    user.fraud_strikes += 1
                    strike_idx = min(user.fraud_strikes - 1, len(freeze_durations) - 1)
                    freeze_days = freeze_durations[strike_idx]
                    user.is_frozen = True
                    user.frozen_until = now + timedelta(days=freeze_days)
                    is_frozen_now = True
                    
                    res_set = await session.execute(select(Settings).where(Settings.key == 'admin_usernames'))
                    setting = res_set.scalars().first()
                    admin_names = setting.value if setting and setting.value else "@admin"
                    
                    lang = user.language or 'uz'
                    if lang == 'uz':
                        freeze_msg = f"⚠️ DIQQAT! Siz 1 kun ichida {expired_count} ta soxta Premium so'rov yubordingiz. Hisobingiz {freeze_days} kunga muzlatildi! Adminga murojaat: {admin_names}"
                    elif lang == 'ru':
                        freeze_msg = f"⚠️ ВНИМАНИЕ! Вы отправили {expired_count} ложных запросов Premium за 1 день. Ваш аккаунт заморожен на {freeze_days} дней! Администратор: {admin_names}"
                    else:
                        freeze_msg = f"⚠️ ATTENTION! You sent {expired_count} fake Premium requests in 1 day. Your account is frozen for {freeze_days} days! Admin: {admin_names}"
                
                try:
                    if is_frozen_now:
                        await bot.send_message(chat_id=user.telegram_id, text=freeze_msg)
                    else:
                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=f"⏳ {req.amount:,.0f} UZS to'lov uchun berilgan 15 daqiqa vaqt tugadi. To'lov so'rovi bekor qilindi."
                        )
                except:
                    pass
            
            # Update admin channel message
            if req.message_id:
                try:
                    res_set = await session.execute(select(Settings).where(Settings.key == 'premium_channel_id'))
                    setting = res_set.scalars().first()
                    channel_id = setting.value if setting and setting.value else getenv("premium_channel_id")
                    
                    if channel_id:
                        markup = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="❌ Muddati o'tdi", callback_data="none")]
                        ])
                        await bot.edit_message_reply_markup(
                            chat_id=channel_id,
                            message_id=req.message_id,
                            reply_markup=markup
                        )
                except Exception as e:
                    logging.error(f"Premium edit message error: {e}")
                    
        if requests:
            await session.commit()


class DreamCheckCallback(CallbackData, prefix="drm_chk2"):
    action: str
    dream_id: int
    date: str

async def daily_dream_check_job(bot):
    """
    Checks if users saved money for their active dream today. 
    If they haven't saved, prompts with Yes/No/Tomorrow.
    Runs at 20:30.
    """
    tashkent_now = get_tashkent_time()
    today = tashkent_now.date()
    start_of_day = datetime.combine(today, time.min)

    async with session_scope() as session:
        # Get all users who have an active dream
        stmt = select(Dream).where(Dream.is_active == True).options(joinedload(Dream.user))
        dreams = (await session.execute(stmt)).scalars().all()
        
        for dream in dreams:
            user = dream.user
            if not user: continue
            
            # Check if there is a 'save_expense' related to dream today. 
            # Or simpler: assume we just ask them every night if they hit their daily target.
            
            date_str = today.strftime('%Y-%m-%d')
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Ha, soldim", callback_data=DreamCheckCallback(action="yes", dream_id=dream.id, date=date_str).pack())],
                [InlineKeyboardButton(text="❌ Yo'q, solmadim", callback_data=DreamCheckCallback(action="no", dream_id=dream.id, date=date_str).pack())]
            ])
            
            msg = f"Bugun orzu qutisi uchun pul ajratdingizmi? 💰\nMaqsad: {dream.dream_name} ({dream.daily_limit_target:,.0f} so'm)"
            
            try:
                await bot.send_message(user.telegram_id, msg, reply_markup=kb)
            except Exception as e:
                logging.error(f"Failed to send dream prompt to {user.telegram_id}: {e}")

async def check_due_debts(bot):
    """
    Checks for debts that are due today and notifies the user.
    Runs daily at 10:00.
    """
    tashkent_now = get_tashkent_time()
    today = tashkent_now.date()
    start_of_day = datetime.combine(today, time.min)
    end_of_day = datetime.combine(today, time.max)
    
    async with session_scope() as session:
        # Active debts due today
        stmt = select(Debt).where(
            Debt.is_active == True,
            Debt.due_date >= start_of_day,
            Debt.due_date <= end_of_day
        ).options(joinedload(Debt.user))
        
        debts = (await session.execute(stmt)).scalars().all()
        for debt in debts:
            user = debt.user
            if not user: continue
            
            action_text = "olish" if debt.type == "loaned" else "qaytarish"
            msg = f"📢 **Qarz eslatmasi!**\n\nSizning bugun {debt.person}dan {debt.amount:,.0f} so'm qarzni {action_text} rejangiz bor edi. Buni yoddan chiqarmadingizmi? 💸"
            
            try:
                await bot.send_message(user.telegram_id, msg, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Failed to send debt reminder to {user.telegram_id}: {e}")

async def check_fixed_expenses_job(bot):
    """
    Checks for fixed expenses due today (matching the day of the month) and notifies the user.
    Runs daily at 09:00.
    """
    tashkent_now = get_tashkent_time()
    today_day_str = str(tashkent_now.day)
    
    async with session_scope() as session:
        # Active fixed expenses due today
        from database.models import DetailedExpenses
        stmt = select(DetailedExpenses).where(
            DetailedExpenses.due_date == today_day_str
        ).options(joinedload(DetailedExpenses.user))
        
        expenses = (await session.execute(stmt)).scalars().all()
        for exp in expenses:
            user = exp.user
            if not user: continue
            
            msg = f"📢 **Majburiy to'lov eslatmasi!**\n\nBugun **{exp.name}** uchun **{exp.amount:,.0f} so'm** to'lov kuningiz. Buni amalga oshirishni yoddan chiqarmang! 💸"
            
            try:
                await bot.send_message(user.telegram_id, msg, parse_mode="Markdown")
            except Exception as e:
                logging.error(f"Failed to send fixed expense reminder to {user.telegram_id}: {e}")
async def check_inactive_users_job(bot):
    """
    Checks for users who have been inactive for between 2 and 3 days,
    and sends them an AI-generated call-to-action message.
    Runs daily at 15:00.
    """
    tashkent_now = get_tashkent_time()
    two_days_ago = tashkent_now - timedelta(days=2)
    three_days_ago = tashkent_now - timedelta(days=3)

    async with session_scope() as session:
        # Select active users inactive between 2 and 3 days ago
        stmt = select(User).where(
            User.last_active >= three_days_ago,
            User.last_active < two_days_ago,
            User.is_frozen == False,
            User.is_archived == False
        )
        res = await session.execute(stmt)
        users = res.scalars().all()

        for user in users:
            try:
                # Find active dream
                stmt_dream = select(Dream).where(
                    Dream.user_id == user.id,
                    Dream.is_active == True
                )
                dream = (await session.execute(stmt_dream)).scalars().first()

                dream_name = None
                dream_total = 0.0
                dream_saved = 0.0
                dream_daily_target = 0.0

                if dream:
                    dream_name = dream.dream_name
                    dream_total = dream.total_amount or 0.0
                    dream_saved = dream.saved_amount or 0.0
                    dream_daily_target = dream.daily_limit_target or 0.0

                user_name = user.name or "Do'stim"
                user_lang = user.language or 'uz'
                
                reminder_text = await GeminiService.generate_inactivity_reminder(
                    user_name=user_name,
                    balance=user.balance or 0.0,
                    daily_limit=user.daily_limit or 0.0,
                    dream_name=dream_name,
                    dream_total=dream_total,
                    dream_saved=dream_saved,
                    dream_daily_target=dream_daily_target,
                    language=user_lang
                )

                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=reminder_text,
                    parse_mode="Markdown"
                )
                logging.info(f"Sent inactivity reminder to user {user.telegram_id}")

            except Exception as e:
                logging.error(f"Error processing inactivity reminder for {user.telegram_id}: {e}")

async def salary_due_job(bot):
    """
    Oylik kuni kelganda so'raydi. Avtomatik yozmaydi — oylik kechikishi yoki
    boshqa summada tushishi mumkin, avtomatik yozilsa balansda yo'q pul paydo
    bo'lardi.
    """
    from handlers.salary import salary_keyboard
    from services import salary_service

    now = get_tashkent_time()
    async with session_scope() as session:
        users = (await session.execute(
            select(User).where(User.salary_day.is_not(None))
        )).scalars().all()

        soralganlar = [u for u in users if salary_service.is_salary_due(u, now)]

    logging.info(f"Oylik so'rovi: {len(soralganlar)} foydalanuvchi")
    for user in soralganlar:
        kutilgan = float(user.monthly_income or 0)
        try:
            await bot.send_message(
                user.telegram_id,
                f"💼 Bugun oylik kuningiz.\n\n"
                f"Kutilgan summa: <b>{kutilgan:,.0f}</b> so'm.\n"
                f"Oyligingiz tushdimi?",
                parse_mode="HTML",
                reply_markup=salary_keyboard(),
            )
        except Exception as e:
            logging.error(f"Oylik so'rovi yuborilmadi {user.telegram_id}: {e}")
        await asyncio.sleep(0.05)


async def monthly_report_job(bot):
    """Oylik tushishidan bir kun oldin o'tgan oy hisoboti."""
    from services import finance_service, salary_service

    now = get_tashkent_time()
    async with session_scope() as session:
        users = (await session.execute(
            select(User).where(User.salary_day.is_not(None))
        )).scalars().all()

        hisobotlar = []
        for user in users:
            if not salary_service.is_report_due(user, now):
                continue
            base = (user.base_currency or "UZS").upper()
            davr_boshi = now - timedelta(days=30)
            totals = await finance_service.totals_for_period(
                session, user.id, davr_boshi, now, base
            )
            baho = salary_service.spending_verdict(
                totals.income, totals.expense, float(user.daily_limit or 0)
            )
            hisobotlar.append((user, totals, baho))

    izohlar = {
        "ko'p": "O'tgan oy rejadagidan ko'proq sarfladingiz. Keyingi oyda eng katta "
                "kategoriyangizni qisqartirishga harakat qiling.",
        "kam": "Ajoyib! Rejadagidan kam sarfladingiz. Ortiqcha pulni orzuingizga "
               "yo'naltirsangiz, maqsadga tezroq yetasiz.",
        "barqaror": "Sarfingiz barqaror — reja bo'yicha ketyapsiz. Shu tarzda davom eting.",
        "nomalum": "Kunlik limitingiz belgilanmagan, shuning uchun taqqoslay olmadim.",
    }

    logging.info(f"Oylik hisobot: {len(hisobotlar)} foydalanuvchi")
    for user, totals, baho in hisobotlar:
        matn = (
            f"📊 <b>O'tgan oy hisoboti</b>\n\n"
            f"Kirim:  <b>{totals.income:,.0f}</b>\n"
            f"Chiqim: <b>{totals.expense:,.0f}</b>\n"
            f"Farq:   <b>{totals.net:,.0f}</b>\n\n"
            f"Baho: <b>{baho}</b>\n{izohlar[baho]}\n\n"
            f"Ertaga oylik kuningiz — yangi oyga tayyormisiz?"
        )
        try:
            await bot.send_message(user.telegram_id, matn, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Oylik hisobot yuborilmadi {user.telegram_id}: {e}")
        await asyncio.sleep(0.05)


async def daily_surplus_job(bot):
    """
    21:00 da: kunlik limitdan ortib qolgan bo'lsa so'raydi.

    Ikkita ehtimolni ajratadi — foydalanuvchi haqiqatan tejadimi, yoki
    xarajatini qo'shishni unutdimi. Ikkinchisi ma'lumot sifatining eng katta
    muammosi.
    """
    from handlers.salary import surplus_keyboard
    from services import finance_service

    now = get_tashkent_time()
    bugun = now.date()
    async with session_scope() as session:
        users = (await session.execute(
            select(User).where(User.daily_limit > 0)
        )).scalars().all()

        soraladi = []
        for user in users:
            if user.surplus_asked_on and user.surplus_asked_on.date() == bugun:
                continue   # bugun allaqachon so'ralgan
            ortiqcha = await finance_service.daily_surplus(session, user)
            if ortiqcha > 0:
                soraladi.append((user.telegram_id, ortiqcha))
                user.surplus_asked_on = now
        await session.commit()

    logging.info(f"Ortiqcha pul so'rovi: {len(soraladi)} foydalanuvchi")
    for telegram_id, ortiqcha in soraladi:
        try:
            await bot.send_message(
                telegram_id,
                f"🌙 Bugun kunlik limitingizdan <b>{ortiqcha:,.0f}</b> so'm ortib qoldi.\n\n"
                f"Rostdan tejadingizmi, yoki xarajat qo'shishni unutdingizmi?",
                parse_mode="HTML",
                reply_markup=surplus_keyboard(ortiqcha),
            )
        except Exception as e:
            logging.error(f"Ortiqcha pul so'rovi yuborilmadi {telegram_id}: {e}")
        await asyncio.sleep(0.05)


def start_scheduler(bot):
    # Weekly summary on Saturday at 20:00 (Shanba kuni soat 20:00 UTC+5)
    scheduler.add_job(weekly_summary_job, 'cron', day_of_week='sat', hour=20, minute=0, args=[bot])
    
    # Dream check at 20:30
    scheduler.add_job(daily_dream_check_job, 'cron', hour=20, minute=30, args=[bot])
    
    # Debt check at 10:00
    scheduler.add_job(check_due_debts, 'cron', hour=10, minute=0, args=[bot])
    
    # Fixed expenses check at 09:00
    scheduler.add_job(check_fixed_expenses_job, 'cron', hour=9, minute=0, args=[bot])
    
    # Check tasks every minute
    scheduler.add_job(check_due_tasks, 'interval', minutes=1, args=[bot])

    # Check premium requests every minute
    scheduler.add_job(check_premium_requests, 'interval', minutes=1, args=[bot])
    
    # Inactivity check daily at 15:00
    scheduler.add_job(check_inactive_users_job, 'cron', hour=15, minute=0, args=[bot])

    # Oylik: hisobot bir kun oldin (10:00), tasdiqlash oylik kuni (10:00)
    scheduler.add_job(monthly_report_job, 'cron', hour=10, minute=0, args=[bot])
    scheduler.add_job(salary_due_job, 'cron', hour=10, minute=30, args=[bot])

    # Kunlik ortiqcha pul so'rovi — 21:00
    scheduler.add_job(daily_surplus_job, 'cron', hour=21, minute=0, args=[bot])

    scheduler.start()
