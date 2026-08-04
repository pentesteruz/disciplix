from aiohttp import web
from sqlalchemy import select, func, text, or_
from database.engine import session_scope
from database.models import User, Finance, Task, Dream, DreamProgress, Settings, PromoCode, Transaction, CurrencyConversionLog
from datetime import datetime, timedelta
import asyncio
import json
import logging
import os
import time
from urllib.parse import parse_qsl

from aiogram.utils.web_app import safe_parse_webapp_init_data
from config import BOT_TOKEN, ADMIN_IDS, WEBAPP_URL
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from utils.i18n import _
from utils.currency import CurrencyConverter, CurrencyRateUnavailable
from utils.premium import is_premium_active
from utils.timezone import get_tashkent_time
from services import dream_service, finance_service
from handlers.start import get_main_keyboard
from services.gemini_service import safe_generate_content

# Telegram initData imzosi abadiy amal qiladi — auth_date'ni o'zimiz tekshirmasak,
# bir marta oqib ketgan satr cheksiz qayta ishlatiladi (replay).
INIT_DATA_MAX_AGE_SECONDS = 24 * 60 * 60


def check_init_data_freshness(init_data: str) -> bool:
    """auth_date INIT_DATA_MAX_AGE_SECONDS ichida bo'lsa True. Imzo alohida tekshiriladi."""
    try:
        auth_date = int(dict(parse_qsl(init_data)).get("auth_date", ""))
    except (ValueError, TypeError):
        return False
    age = time.time() - auth_date
    return -300 <= age <= INIT_DATA_MAX_AGE_SECONDS


# Bitta foydalanuvchi kiritishi mumkin bo'lgan eng katta summa (1 trillion).
MAX_MONEY_VALUE = 1_000_000_000_000


def _parse_money(raw, field_name: str) -> float:
    """Klientdan kelgan pul qiymatini tekshiradi. Nomaqbul bo'lsa ValueError."""
    try:
        value = float(raw)
    except (ValueError, TypeError):
        raise ValueError(f"{field_name} haqiqiy son bo'lishi kerak")
    if value != value or value in (float('inf'), float('-inf')):
        raise ValueError(f"{field_name} haqiqiy son bo'lishi kerak")
    if value < 0:
        raise ValueError(f"{field_name} manfiy bo'lishi mumkin emas")
    if value > MAX_MONEY_VALUE:
        raise ValueError(f"{field_name} juda katta")
    return value


def _serialize_transaction(tx) -> dict:
    """Transaction'ni API javobi uchun bir xil shaklga keltiradi."""
    return {
        "id": tx.id,
        "amount": tx.amount,
        "currency": tx.currency,
        "category": tx.category,
        "type": tx.type,
        "description": tx.description,
        "time": tx.timestamp.strftime("%H:%M") if tx.timestamp else "",
        "due_date": tx.due_date.strftime("%Y-%m-%d") if tx.due_date else None,
    }

# is_premium_active endi utils.premium'dan keladi (yagona manba).

def get_last_active_str(last_active_dt):
    if not last_active_dt:
        return "Noma'lum"
    # Using simple naive datetime difference assuming both are similar timezone or naive
    diff = get_tashkent_time() - last_active_dt
    days = diff.days
    if days < 1:
        return "Bugun"
    elif days == 1:
        return "Kecha"
    else:
        return f"{days} kun oldin"

async def handle_dashboard_stats(request):
    try:
        telegram_id = request.query.get('user_id')
        if not telegram_id:
             return web.json_response({"error": "Missing user_id"}, status=400)
        
        try:
            telegram_id = int(telegram_id)
        except ValueError:
             return web.json_response({"error": "Invalid user_id format"}, status=400)
             
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = res.scalars().first()
            
            if not user or not user.phone_number:
                 return web.json_response({"error": "User not found"}, status=404)
            
            today = get_tashkent_time()
            if not is_premium_active(user):
                 return web.json_response({"error": "Premium required"}, status=403)
            
            start_of_day, _ = finance_service.day_bounds(today)

            active_cur_str = getattr(user, 'active_currencies', "UZS")
            active_currencies = [c.strip().upper() for c in active_cur_str.split(',')] if active_cur_str else ["UZS"]
            base_currency = getattr(user, 'base_currency', "UZS").upper()

            # Kunlik kirim/chiqim. daily_expense majburiy xarajatlarni hisobga olmaydi —
            # ular foydalanuvchi ixtiyoridagi sarf emas, shuning uchun limitga kirmaydi.
            daily = await finance_service.daily_totals(session, user.id, base_currency)
            daily_expense = daily.discretionary_expense
            daily_income = daily.income

            # Compute Balances per currency
            balances = {curr: {'income': 0.0, 'expense': 0.0} for curr in active_currencies}
            if base_currency not in balances:
                balances[base_currency] = {'income': 0.0, 'expense': 0.0}

            # monthly_income BALANSGA QO'SHILMAYDI — u faqat kunlik limitni
            # hisoblash uchun mo'ljal. Ilgari u shu yerda qo'shilar edi va
            # foydalanuvchi "oylik oldim" deganda summa ikki marta hisoblanardi.
            # Oylik tushganda u haqiqiy kirim tranzaksiyasi sifatida yoziladi.
            for f_cur, totals in (await finance_service.balances_by_currency(session, user.id)).items():
                bucket = balances.setdefault(f_cur, {'income': 0.0, 'expense': 0.0})
                bucket['income'] += totals['income']
                bucket['expense'] += totals['expense']

            currency_balances = []
            total_balance_base = 0.0
            total_income_base = 0.0
            total_expense_base = 0.0
            
            # Build list over ACTIVE currencies
            for cur in active_currencies:
                data = balances.get(cur, {'income': 0.0, 'expense': 0.0})
                inc = float(data['income'])
                exp = float(data['expense'])
                amount = inc - exp
                currency_balances.append({
                    "currency": cur,
                    "label": f"Balans ({cur})",
                    "amount": round(amount, 2),
                    "income": round(inc, 2),
                    "expense": round(exp, 2),
                    "total": False
                })
            
            # Form the final Total Base Currency card
            for cur, data in balances.items():
                inc = float(data['income'])
                exp = float(data['expense'])
                amt_inc = await CurrencyConverter.convert(inc, cur, base_currency)
                amt_exp = await CurrencyConverter.convert(exp, cur, base_currency)
                total_income_base += amt_inc
                total_expense_base += amt_exp
                total_balance_base += (amt_inc - amt_exp)
                
            currency_balances.append({
                "currency": base_currency,
                "label": "Umumiy Hisob",
                "amount": round(total_balance_base, 2),
                "income": round(total_income_base, 2),
                "expense": round(total_expense_base, 2),
                "total": True
            })

            # Dreams
            stmt_dreams = select(Dream).where(Dream.user_id == user.id, Dream.is_active == True).order_by(Dream.created_at.desc())
            dreams = (await session.execute(stmt_dreams)).scalars().all()
            dreams_data = []
            for d in dreams:
                progress = (d.saved_amount / d.total_amount) * 100 if d.total_amount > 0 else 0
                days_left = (d.deadline - today).days if d.deadline else 30
                if days_left < 0: days_left = 0
                dreams_data.append({
                    "id": d.id,
                    "title": d.dream_name,
                    "target": d.total_amount,
                    "current": d.saved_amount,
                    "progress_percent": round(progress, 1),
                    "daily_limit_target": d.daily_limit_target,
                    "daysRemaining": days_left,
                    "icon": d.icon or "car",
                    "iconBg": d.icon_bg or "bg-primary/10",
                    "iconColor": d.icon_color or "text-primary",
                    "cancel_requested": d.cancel_requested
                })

            # Tasks
            end_of_day = datetime(today.year, today.month, today.day, 23, 59, 59)
            stmt_tasks = select(Task).where(Task.user_id == user.id, Task.is_completed == False).order_by(Task.created_at.desc())
            tasks = (await session.execute(stmt_tasks)).scalars().all()
            tasks_data = [{"id": t.id, "title": t.title, "date": t.due_date.strftime('%H:%M') if t.due_date else "", "is_completed": t.is_completed, "description": getattr(t, 'description', getattr(t, 'title', ""))} for t in tasks]

            # Dynamic Discipline Score over the last 7 days
            discipline_score = 100.0
            history_start = today - timedelta(days=7)

            # 1. Tasks logic
            stmt_tasks_history = select(Task).where(
                Task.user_id == user.id,
                Task.due_date >= history_start,
                Task.due_date < end_of_day
            )
            history_tasks = (await session.execute(stmt_tasks_history)).scalars().all()
            for t in history_tasks:
                if t.is_completed:
                    discipline_score += 5
                elif t.due_date and t.due_date < today:
                    discipline_score -= 10

            # Weekly Data (last 7 days, summed in base_currency)
            weekly_data = []
            uzbek_days = {"Mon": "Dush", "Tue": "Sesh", "Wed": "Chor", "Thu": "Pay", "Fri": "Jum", "Sat": "Shan", "Sun": "Yak"}
            
            stmt_weekly = select(Transaction.amount, Transaction.type, Transaction.currency, Transaction.timestamp).where(
                Transaction.user_id == user.id,
                Transaction.timestamp >= history_start
            )
            weekly_finances = (await session.execute(stmt_weekly)).all()
            
            for i in range(6, -1, -1):
                d_date = today - timedelta(days=i)
                d_start = datetime(d_date.year, d_date.month, d_date.day)
                d_end = d_start + timedelta(days=1)
                
                ex_sum = 0.0
                in_sum = 0.0
                for fw_amt, fw_type, fw_cur, fw_time in weekly_finances:
                    if d_start <= fw_time < d_end:
                        fw_cur = (fw_cur or "UZS").upper()
                        fw_amt_base = await CurrencyConverter.convert(fw_amt, fw_cur, base_currency)
                        if fw_type in ['expense', 'chiqim']:
                            ex_sum += fw_amt_base
                        else:
                            in_sum += fw_amt_base
                
                # 2. Daily Limit logic
                if user.daily_limit > 0 and ex_sum > user.daily_limit:
                    discipline_score -= 10
                
                day_str = d_date.strftime("%a")
                weekly_data.append({
                    "day": uzbek_days.get(day_str, day_str),
                    "income": in_sum,
                    "expense": ex_sum
                })

            # 1.5 Dream Logic: Check missed dream progress
            stmt_active_dream = select(Dream).where(Dream.user_id == user.id, Dream.is_active == True)
            active_dream = (await session.execute(stmt_active_dream)).scalars().first()
            if active_dream:
                stmt_dream_hist = select(DreamProgress).where(
                    DreamProgress.dream_id == active_dream.id,
                    DreamProgress.date >= history_start,
                    DreamProgress.date < start_of_day, # up to yesterday
                    DreamProgress.is_paid == True
                )
                progress_dates = (await session.execute(stmt_dream_hist)).scalars().all()
                paid_days = set(d.date.strftime('%Y-%m-%d') for d in progress_dates if d.date)
                
                for i in range(1, 8):
                    check_date_obj = (today - timedelta(days=i))
                    if active_dream.created_at and check_date_obj.date() < active_dream.created_at.date():
                        continue
                    check_date = check_date_obj.strftime('%Y-%m-%d')
                    if check_date not in paid_days:
                        discipline_score -= 10

            discipline_score = max(0, min(100, int(discipline_score)))
            streak = discipline_score / 10.0

            # Transactions
            today_transactions = []
            history_transactions = []
            stmt_tx = select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.timestamp.desc()).limit(20)
            finances = (await session.execute(stmt_tx)).scalars().all()
            for f in finances:
                is_income = f.type in ['income', 'kirim', 'daromad']
                tx_cur = getattr(f, 'currency', 'UZS') or 'UZS'
                item = {
                    "id": f.id,
                    "title": f.description or f.category or ("Kirim" if is_income else "Xarajat"),
                    "category": f.category or "Boshqa",
                    "amount": f.amount if is_income else -f.amount,
                    "currency": tx_cur,
                    "time": f.timestamp.strftime("%d.%m.%Y %H:%M") if f.timestamp else "",
                    "date": f.timestamp.strftime("%d.%m.%Y") if f.timestamp else "",
                    "icon": "shopping-bag",
                    "iconBg": "bg-primary/10" if is_income else "bg-amber-100",
                    "iconColor": "text-primary" if is_income else "text-amber-600",
                }
                if f.timestamp and f.timestamp >= start_of_day:
                    today_transactions.append(item)
                else:
                    history_transactions.append(item)

            # AI Tip Logic
            is_over_limit = daily_expense > user.daily_limit
            progress_pct = (daily_expense / user.daily_limit * 100) if user.daily_limit > 0 else 0
            if is_over_limit:
                ai_tip = f"Diqqat: Kunlik limitdan {round(progress_pct - 100)}% oshdingiz! Iltimos, tejamkorroq bo'ling."
            else:
                ai_tip = "Ajoyib! Shu tarzda davom eting. 🔥 Pul tejalmoqda."

            return web.json_response({
                "balance": total_balance_base,
                "currency_balances": currency_balances,
                "base_currency": base_currency,
                "daily_limit": user.daily_limit,
                "daily_expense": daily_expense,
                "daily_income": daily_income,
                "currency": base_currency,
                "dreams": dreams_data,
                "tasks": tasks_data,
                "weekly_data": weekly_data,
                "today_transactions": today_transactions,
                "history_transactions": history_transactions,
                "ai_tip": ai_tip,
                "is_over_limit": is_over_limit,
                "streak": streak,
                "user_language": getattr(user, 'language', 'uz')
            })
    except CurrencyRateUnavailable as e:
        # Noto'g'ri balans ko'rsatgandan ko'ra ochiq xato qaytargan xavfsizroq.
        logging.error(f"Dashboard currency error: {e}")
        return web.json_response(
            {"error": "Valyuta kurslari hozir mavjud emas. Biroz kuting va qayta urinib ko'ring."},
            status=503,
        )
    except Exception as e:
        logging.exception(f"Dashboard API Error: {e}")
        return web.json_response({"error": "Internal server error. Please try again later."}, status=500)

async def handle_finance_stats(request):
    try:
        user_id = request.match_info.get('user_id')
        if not user_id:
            return web.json_response({"error": "Missing user_id"}, status=400)

        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == int(user_id)))
            user = res.scalars().first()
            
            if not user or not user.phone_number:
                 return web.json_response({"error": "User not found"}, status=404)

            base_currency = (getattr(user, 'base_currency', 'UZS') or 'UZS').upper()
            start_of_day, _ = finance_service.day_bounds()

            daily = await finance_service.daily_totals(session, user.id, base_currency)
            monthly = await finance_service.monthly_totals(session, user.id, base_currency)
            todays = await finance_service.transactions_since(session, user.id, start_of_day)

            return web.json_response({
                "balance": user.balance,
                "daily_limit": user.daily_limit,
                "daily_expense": daily.expense,
                "daily_income": daily.income,
                "monthly_expense": monthly.expense,
                "monthly_income": monthly.income,
                "currency": base_currency,
                "transactions": [_serialize_transaction(t) for t in todays]
            })

    except Exception as e:
        logging.error(f"Finance API Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_complete_task(request):
    try:
        task_id = request.match_info.get('task_id')
        if not task_id:
            return web.json_response({"error": "Missing task_id"}, status=400)

        telegram_user_id = request.get('telegram_user_id')

        async with session_scope() as session:
            task = await session.get(Task, int(task_id))
            if not task:
                return web.json_response({"error": "Task not found"}, status=404)

            # Verify task belongs to the authenticated user
            if not telegram_user_id:
                return web.json_response({"error": "Unauthorized. InitData missing."}, status=401)
                
            res = await session.execute(select(User).where(User.telegram_id == telegram_user_id))
            owner = res.scalars().first()
            if not owner or task.user_id != owner.id:
                return web.json_response({"error": "Forbidden"}, status=403)

            task.is_completed = True
            await session.commit()
            return web.json_response({"status": "success"})

    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_tasks_list(request):
    try:
        user_id = request.match_info.get('user_id')
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == int(user_id)))
            user = res.scalars().first()
            if not user or not user.phone_number:
                return web.json_response({"error": "User not found"}, status=404)

            today = get_tashkent_time()
            end_of_day = datetime(today.year, today.month, today.day, 23, 59, 59)
            
            stmt = select(Task).where(
                Task.user_id == user.id,
                Task.is_completed == False 
            ).order_by(Task.due_date)
            
            tasks = (await session.execute(stmt)).scalars().all()
            
            tasks_data = [{
                "id": t.id,
                "title": t.title,
                "date": t.due_date.strftime('%Y-%m-%d %H:%M') if t.due_date else "",
                "is_completed": t.is_completed,
                "is_ai": t.is_ai_generated
            } for t in tasks]
            
            return web.json_response({"tasks": tasks_data})
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_create_task(request):
    try:
        user_id = request.match_info.get('user_id')
        data = await request.json()
        title = data.get('title')
        description = data.get('description', '')
        due_date_str = data.get('due_date')
        
        if not title or not title.strip():
            return web.json_response({"error": "Title required"}, status=400)
        if len(title) > 500:
            return web.json_response({"error": "Title juda uzun (maksimum 500 belgi)"}, status=400)

        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == int(user_id)))
            user = res.scalars().first()
            if not user or not user.phone_number:
                return web.json_response({"error": "User not found"}, status=404)

            if not is_premium_active(user):
                stmt = select(func.count(Task.id)).where(Task.user_id == user.id, Task.is_completed == False)
                task_count = (await session.execute(stmt)).scalar() or 0
                if task_count >= 5:
                    return web.json_response({"error": "Bitta vaqtning o'zida maksimal 5 ta reja kiritish mumkin. Premium sotib oling yoki eski rejalaringizni bajaring!"}, status=403)

            due_date = None
            if due_date_str:
                try:
                    due_date = datetime.fromisoformat(due_date_str)
                except ValueError:
                    pass

            new_task = Task(
                user_id=user.id,
                title=title,
                description=description,
                due_date=due_date,
                is_completed=False,
                created_at=get_tashkent_time()
            )
            session.add(new_task)
            await session.commit()
            return web.json_response({"status": "success", "id": new_task.id})
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_get_dream(request):
    try:
        user_id = request.match_info.get('user_id')
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == int(user_id)))
            user = res.scalars().first()
            if not user or not user.phone_number:
                return web.json_response({"error": "User not found"}, status=404)

            stmt = select(Dream).where(Dream.user_id == user.id, Dream.is_active == True).order_by(Dream.id.desc())
            dream = (await session.execute(stmt)).scalars().first()
            
            if not dream:
                return web.json_response({"dream": None})

            # Check if paid today
            today_start = get_tashkent_time().replace(hour=0, minute=0, second=0, microsecond=0)
            stmt_prog = select(DreamProgress).where(
                DreamProgress.dream_id == dream.id,
                DreamProgress.date >= today_start
            )
            progress_today = (await session.execute(stmt_prog)).scalars().first()
            
            return web.json_response({
                "dream": {
                    "id": dream.id,
                    "name": dream.dream_name,
                    "total": dream.total_amount,
                    "saved": dream.saved_amount,
                    "daily_target": dream.daily_limit_target,
                    "paid_today": bool(progress_today),
                    "cancel_requested": dream.cancel_requested
                }
            })
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_dream_capacity(request):
    """
    Yangi orzu uchun taklif qilinadigan kunlik summalarni qaytaradi.

    Variantlar QOLGAN sig'imdan hisoblanadi — ilgari ular har safar to'liq
    kunlik limitdan hisoblanardi va ikkinchi orzuga ham birinchisi bilan bir
    xil summalar taklif qilinardi.
    """
    try:
        user_id = request.match_info.get('user_id')
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == int(user_id)))
            user = res.scalars().first()
            if not user or not user.phone_number:
                return web.json_response({"error": "User not found"}, status=404)

            capacity = await dream_service.get_capacity(session, user)
            return web.json_response({
                "daily_limit": capacity.daily_limit,
                "committed": capacity.committed,
                "available": capacity.available,
                "is_full": capacity.is_full,
                "options": capacity.options,
            })
    except Exception as e:
        logging.error(f"Dream capacity error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)


async def handle_dream_cancel_request(request):
    try:
        dream_id = request.match_info.get('id')
        telegram_user_id = request.get('telegram_user_id')
        if not telegram_user_id:
            return web.json_response({"error": "Unauthorized. InitData missing."}, status=401)

        async with session_scope() as session:
            dream = await session.get(Dream, int(dream_id))
            if not dream:
                return web.json_response({"error": "Dream not found"}, status=404)
            
            res = await session.execute(select(User).where(User.telegram_id == telegram_user_id))
            owner = res.scalars().first()
            if not owner or dream.user_id != owner.id:
                return web.json_response({"error": "Forbidden"}, status=403)
            
            dream.cancel_requested = True
            await session.commit()
            return web.json_response({"status": "success"})
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_set_main_dream(request):
    try:
        dream_id = request.match_info.get('id')
        telegram_user_id = request.get('telegram_user_id')
        if not telegram_user_id:
            return web.json_response({"error": "Unauthorized. InitData missing."}, status=401)

        async with session_scope() as session:
            dream = await session.get(Dream, int(dream_id))
            if not dream:
                return web.json_response({"error": "Dream not found"}, status=404)
            
            res = await session.execute(select(User).where(User.telegram_id == telegram_user_id))
            owner = res.scalars().first()
            if not owner or dream.user_id != owner.id:
                return web.json_response({"error": "Forbidden"}, status=403)
            
            # Setting created_at to now pushes it to the top
            dream.created_at = get_tashkent_time()
            await session.commit()
            return web.json_response({"status": "success"})
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_create_dream(request):
    try:
        user_id = request.match_info.get('user_id')
        data = await request.json()
        name = data.get('name', '').strip()
        amount = float(data.get('amount', 0))
        deadline_str = data.get('deadline')
        daily_limit_target = float(data.get('daily_limit', 0))
        
        icon = data.get('icon', 'car')
        icon_bg = data.get('iconBg', 'bg-primary/10')
        icon_color = data.get('iconColor', 'text-primary')
        
        if not name or not name.strip():
            return web.json_response({"error": "Orzu nomi kiritilishi shart!"}, status=400)
        if len(name) > 200:
            return web.json_response({"error": "Orzu nomi juda uzun (maksimum 200 belgi)"}, status=400)
        if amount <= 0:
            return web.json_response({"error": "Orzu summasi noldan katta bo'lishi kerak!"}, status=400)
        if amount > 1_000_000_000_000:  # 1 trillion UZS limit
            return web.json_response({"error": "Orzu summasi juda katta!"}, status=400)
        if not deadline_str or daily_limit_target <= 0:
            return web.json_response({"error": "Vaqt va kunlik limit kiritilishi shart!"}, status=400)

        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == int(user_id)))
            user = res.scalars().first()
            if not user or not user.phone_number:
                return web.json_response({"error": "User not found"}, status=404)

            # Kunlik sig'im tekshiruvi: faol orzular allaqachon band qilgan
            # summani hisobga oladi, aks holda bajarib bo'lmaydigan majburiyat
            # yaratiladi.
            capacity = await dream_service.get_capacity(session, user)
            ruxsat, ogohlantirish = dream_service.validate_daily_target(capacity, daily_limit_target)
            if not ruxsat:
                return web.json_response({"error": ogohlantirish}, status=400)

            if not is_premium_active(user):
                today = get_tashkent_time()
                start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                stmt = select(func.count(Dream.id)).where(Dream.user_id == user.id, Dream.created_at >= start_of_month)
                dream_count = (await session.execute(stmt)).scalar() or 0
                if dream_count >= 1:
                    return web.json_response({"error": "Oylik bepul 1 ta orzu kiritish limitingiz tugagan. Cheksiz qo'shish uchun Premium oling!"}, status=403)
            
            deadline = None
            if deadline_str:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
            
            new_dream = Dream(
                user_id=user.id,
                dream_name=name,
                total_amount=amount,
                saved_amount=0,
                daily_limit_target=daily_limit_target,
                is_active=True,
                deadline=deadline,
                icon=icon,
                icon_bg=icon_bg,
                icon_color=icon_color
            )
            session.add(new_dream)
            await session.commit()

            return web.json_response({"status": "success", "warning": ogohlantirish})
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_dream_progress(request):
    try:
        dream_id = request.match_info.get('id')
        telegram_user_id = request.get('telegram_user_id')
        data = await request.json()
        amount = float(data.get('amount', 0))
        if amount <= 0:
            return web.json_response({"error": "Summa noldan katta bo'lishi kerak"}, status=400)
        is_daily = data.get('is_daily', False) # New flag from frontend
        
        async with session_scope() as session:
            dream = await session.get(Dream, int(dream_id))
            if not dream:
                return web.json_response({"error": "Dream not found"}, status=404)
            
            if not telegram_user_id:
                return web.json_response({"error": "Unauthorized. InitData missing."}, status=401)
                
            res = await session.execute(select(User).where(User.telegram_id == telegram_user_id))
            owner = res.scalars().first()
            if not owner or dream.user_id != owner.id:
                return web.json_response({"error": "Forbidden"}, status=403)
            
            # Check if daily payment was already made today
            if is_daily:
                today = get_tashkent_time()
                start_of_day = datetime(today.year, today.month, today.day)
                
                # Look for an existing payment today
                stmt = select(DreamProgress).where(
                    DreamProgress.dream_id == dream.id,
                    DreamProgress.date >= start_of_day,
                    DreamProgress.is_paid == True
                )
                existing = (await session.execute(stmt)).scalars().first()
                if existing:
                    return web.json_response({"error": "Siz bugungi limitni bajardingiz, endi qo'shimcha pul qo'shish bilan qilsangiz bo'ladi."}, status=400)
            
            dream.saved_amount += amount
            
            prog = DreamProgress(
                user_id=dream.user_id,
                dream_id=dream.id,
                amount=amount,
                date=get_tashkent_time(), # Explicitly save Tashkent time
                is_paid=True
            )
            session.add(prog)
            await session.commit()
            return web.json_response({"status": "success", "new_saved": dream.saved_amount})
    except Exception as e:
        logging.error(f"Dream progress error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_index(request):
    base_dir = os.getcwd()
    index_path = os.path.join(base_dir, "web2", "out", "index.html")
    alt_index = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web2", "out", "index.html")

    if os.path.exists(index_path):
        return web.FileResponse(index_path)
    if os.path.exists(alt_index):
        return web.FileResponse(alt_index)

    # Yo'llar va papka ro'yxati faqat logga — javobda server tuzilishini oshkor qilmaymiz.
    logging.error(
        "Web app build topilmadi. CWD=%s tekshirilgan=%s alt=%s", base_dir, index_path, alt_index
    )
    return web.Response(text="Web app is not available.", status=404)

async def handle_admin_index(request):
    admin_path = os.path.join("web2", "out", "admin.html")
    if os.path.exists(admin_path):
        return web.FileResponse(admin_path)
    # Fallback to index if admin.html doesn't exist (Next.js might put it in admin/index.html)
    alt_path = os.path.join("web2", "out", "admin", "index.html")
    if os.path.exists(alt_path):
        return web.FileResponse(alt_path)
    return await handle_index(request)

RATE_LIMIT_CACHE = {}
RATE_LIMIT_MAX_REQUESTS = 15
RATE_LIMIT_WINDOW = 5 # seconds

@web.middleware
async def auth_middleware(request, handler):
    # Only protect API routes
    if not request.path.startswith('/api/'):
        return await handler(request)

    # Allow CORS preflight without auth
    if request.method == "OPTIONS":
        return web.Response(status=204)

    init_data = request.headers.get("Authorization")

    if not init_data:
        return web.json_response({"error": "Unauthorized. Missing initData."}, status=401)

    try:
        parsed_data = safe_parse_webapp_init_data(token=BOT_TOKEN, init_data=init_data)
        if not check_init_data_freshness(init_data):
            return web.json_response({"error": "Unauthorized. initData expired."}, status=401)
        telegram_user_id = parsed_data.user.id

        # Admin routes check
        if request.path.startswith('/api/mng-x89b2k1q/'):
            if telegram_user_id not in ADMIN_IDS:
                return web.json_response({"error": "Forbidden. Admin access required."}, status=403)

        user_id_param = request.match_info.get('user_id') or request.query.get('user_id')
        if user_id_param and str(user_id_param).isdigit():
            if int(user_id_param) != telegram_user_id and telegram_user_id not in ADMIN_IDS:
                return web.json_response({"error": "Forbidden. User mismatch."}, status=403)

        now = time.time()
        # Kesh o'sib ketmasligi uchun eskirgan yozuvlarni chiqaramiz. Butun keshni
        # tozalash mumkin emas — u paytda hamma bir vaqtda limitdan xalos bo'ladi.
        if len(RATE_LIMIT_CACHE) > 10000:
            for cached_id, stamps in list(RATE_LIMIT_CACHE.items()):
                if not stamps or now - stamps[-1] >= RATE_LIMIT_WINDOW:
                    del RATE_LIMIT_CACHE[cached_id]

        # Rate Limiting (Simple In-Memory)
        user_requests = [t for t in RATE_LIMIT_CACHE.get(telegram_user_id, []) if now - t < RATE_LIMIT_WINDOW]

        if len(user_requests) >= RATE_LIMIT_MAX_REQUESTS:
            RATE_LIMIT_CACHE[telegram_user_id] = user_requests
            return web.json_response({"error": "Too Many Requests. Please slow down."}, status=429)

        user_requests.append(now)
        RATE_LIMIT_CACHE[telegram_user_id] = user_requests

        request['telegram_user_id'] = telegram_user_id

    except ValueError:
        return web.json_response({"error": "Unauthorized. Invalid initData signature."}, status=401)
    except Exception as e:
        logging.error(f"Auth error: {e}")
        return web.json_response({"error": "Internal auth error."}, status=500)

    return await handler(request)

async def handle_update_lang(request):
    try:
        user_id = request.match_info.get('user_id')
        data = await request.json()
        lang = data.get('lang')
        
        if not user_id or not lang:
            return web.json_response({"error": "Missing user_id or lang"}, status=400)
            
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == int(user_id)))
            user = res.scalars().first()
            if not user:
                return web.json_response({"error": "User not found"}, status=404)
                
            user.language = lang
            await session.commit()
            
            return web.json_response({"status": "success", "lang": lang})
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_update_base_currency(request):
    try:
        user_id = request.match_info.get('user_id')
        data = await request.json()
        base_currency = data.get('base_currency')
        
        if not user_id or not base_currency:
            return web.json_response({"error": "Missing user_id or base_currency"}, status=400)
            
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == int(user_id)))
            user = res.scalars().first()
            if not user:
                return web.json_response({"error": "User not found"}, status=404)
                
            base_currency = base_currency.upper()
            old_currency = getattr(user, 'base_currency', 'UZS') or 'UZS'

            if old_currency != base_currency:
                from utils.currency import CurrencyConverter

                res_dreams = await session.execute(select(Dream).where(Dream.user_id == user.id, Dream.is_active == True))
                active_dreams = res_dreams.scalars().all()

                # Qayta yozishdan oldingi holatni saqlaymiz — kurs keyin o'zgargani uchun
                # teskari konversiya asl summani qaytarmaydi.
                snapshot = {
                    "user": {
                        "balance": user.balance,
                        "monthly_income": user.monthly_income,
                        "daily_limit": user.daily_limit,
                    },
                    "dreams": [
                        {
                            "id": d.id,
                            "total_amount": d.total_amount,
                            "saved_amount": d.saved_amount,
                            "daily_limit_target": d.daily_limit_target,
                        }
                        for d in active_dreams
                    ],
                }
                rate = await CurrencyConverter.convert(1.0, old_currency, base_currency)

                session.add(CurrencyConversionLog(
                    user_id=user.id,
                    from_currency=old_currency,
                    to_currency=base_currency,
                    rate=rate,
                    snapshot=json.dumps(snapshot, default=str),
                ))

                # Convert user static values
                if getattr(user, 'balance', None):
                    user.balance = user.balance * rate
                if getattr(user, 'monthly_income', None):
                    user.monthly_income = user.monthly_income * rate
                if getattr(user, 'daily_limit', None):
                    user.daily_limit = user.daily_limit * rate

                # Convert active dreams
                for dream in active_dreams:
                    if getattr(dream, 'total_amount', None):
                        dream.total_amount = dream.total_amount * rate
                    if getattr(dream, 'saved_amount', None):
                        dream.saved_amount = dream.saved_amount * rate
                    if getattr(dream, 'daily_limit_target', None):
                        dream.daily_limit_target = dream.daily_limit_target * rate

            user.base_currency = base_currency
            
            active = getattr(user, 'active_currencies', '') or 'UZS'
            active_list = [c.strip().upper() for c in active.split(',') if c.strip()]
            if base_currency not in active_list:
                active_list.append(base_currency)
                user.active_currencies = ','.join(active_list)
                
            await session.commit()
            return web.json_response({"status": "success", "base_currency": base_currency, "active_currencies": user.active_currencies})
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_help_request(request):
    try:
        user_id = request.match_info.get('user_id')
        
        if not user_id:
            return web.json_response({"error": "Missing user_id"}, status=400)
            
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == int(user_id)))
            user = res.scalars().first()
            if not user:
                return web.json_response({"error": "User not found"}, status=404)
                
            bot = request.app.get('bot')
            if bot:
                from utils.i18n import _
                lang = user.language or 'uz'
                
                # Fetch settings for info
                info_res = await session.execute(select(Settings).where(Settings.key == 'info_text'))
                info_setting = info_res.scalars().first()
                video_res = await session.execute(select(Settings).where(Settings.key == 'info_video_id'))
                video_setting = video_res.scalars().first()
                
                info_raw = info_setting.value if info_setting else "O'rnatilmagan"
                if info_raw == "O'chirilgan":
                    text = ""
                elif info_raw and info_raw != "O'rnatilmagan":
                    text = info_raw
                else:
                    text = _("info_welcome", lang)
                
                video_raw = video_setting.value if video_setting else "O'rnatilmagan"
                video_id = None if video_raw in ("O'rnatilmagan", "O'chirilgan", None, "") else video_raw
                
                if not video_id and not text:
                    text = _("info_welcome", lang)
                
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=_("support_btn", lang), callback_data="reask_support")]
                ])
                
                try:
                    if video_id:
                        await bot.send_video(chat_id=int(user_id), video=video_id, caption=text, reply_markup=markup, parse_mode="HTML")
                    else:
                        await bot.send_message(chat_id=int(user_id), text=text, reply_markup=markup, parse_mode="HTML")
                except Exception as bot_err:
                    logging.error(f"Failed to send help to {user_id}: {bot_err}")
                
            return web.json_response({"status": "success"})
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_buy_premium_request(request):
    try:
        telegram_id = request.query.get('user_id')
        if not telegram_id:
            return web.json_response({"error": "Missing user_id"}, status=400)
        telegram_id = int(telegram_id)
        
        bot = request.app.get('bot')
        
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = res.scalars().first()
            if not user:
                return web.json_response({"error": "User not found"}, status=404)
                
            from utils.i18n import _
            from utils.timezone import get_tashkent_time
            lang = user.language or 'uz'
            text = _('premium_menu_title', lang)
            text += _('premium_menu_desc', lang)
            
            now = get_tashkent_time()
            if user.premium_until and user.premium_until > now:
                days_left = (user.premium_until - now).days
                text += _('premium_days_left', lang, days=days_left)
            else:
                text += _('premium_not_active', lang)
            
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=_('premium_buy_btn', lang), callback_data="buy_premium")]
            ])
            
            try:
                await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML", reply_markup=markup)
            except Exception as e:
                logging.error(f"Failed to send premium menu to {telegram_id}: {e}")
                
            return web.json_response({"success": True})
    except Exception as e:
        logging.exception(f"Buy premium request error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_register(request):
    """Register a user via the web app form. Saves data directly to DB."""
    try:
        import string, random
        from database.models import DetailedExpenses
        data = await request.json()

        telegram_id = request.get('telegram_user_id')
        if not telegram_id:
            return web.json_response({"error": "Unauthorized user."}, status=401)
        telegram_id = int(telegram_id)
        
        # Prevent overriding another user's profile
        provided_id = data.get('telegram_id')
        if provided_id and str(provided_id).isdigit() and int(provided_id) != telegram_id:
            return web.json_response({"error": "Mismatched telegram ID."}, status=403)

        name = data.get('name', '').strip()
        surname = data.get('surname', '').strip()
        try:
            monthly_income = _parse_money(data.get('monthly_income', 0), "monthly_income")
            fixed_expenses_total = _parse_money(data.get('fixed_expenses_total', 0), "fixed_expenses_total")
            requested_daily_limit = _parse_money(data.get('daily_limit', 0), "daily_limit")
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=400)

        mode = data.get('mode', 'quick')
        if mode not in ('quick', 'detailed'):
            return web.json_response({"error": "mode 'quick' yoki 'detailed' bo'lishi kerak"}, status=400)

        ref_code = data.get('ref')
        lang = data.get('lang', 'uz')
        if lang not in ('uz', 'ru', 'en'):
            lang = 'uz'
        base_currency = data.get('base_currency', 'UZS').upper()

        name = name[:100] or "Foydalanuvchi"
        surname = surname[:100]

        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = res.scalars().first()

            if not user:
                referred_by_id = None
                if ref_code:
                    ref_res = await session.execute(select(User).where(User.referral_code == ref_code))
                    referrer = ref_res.scalars().first()
                    # Prevent self-referral
                    if referrer and referrer.telegram_id != telegram_id:
                        referred_by_id = referrer.id
                user = User(
                    telegram_id=telegram_id,
                    referral_code=''.join(random.choices(string.ascii_letters + string.digits, k=8)),
                    referred_by_id=referred_by_id,
                    language=lang,
                    base_currency=base_currency,
                    active_currencies=base_currency
                )
                session.add(user)
            else:
                user.language = lang
                user.base_currency = base_currency
                active_list = [c.strip().upper() for c in (getattr(user, 'active_currencies', '') or 'UZS').split(',') if c.strip()]
                if base_currency not in active_list:
                    active_list.append(base_currency)
                    user.active_currencies = ','.join(active_list)

            # Allaqachon ro'yxatdan o'tgan foydalanuvchi uchun bu endpoint moliyaviy
            # maydonlarni qayta yozmasligi kerak — aks holda uni qayta chaqirib
            # balans va limitni ixtiyoriy qiymatga tiklash mumkin bo'lardi.
            already_registered = user.user_state == 'registered'

            user.name = name
            user.surname = surname
            if not already_registered:
                user.monthly_income = monthly_income
                user.registration_mode = mode
                user.fixed_expenses_total = fixed_expenses_total
                # Balans 0 dan boshlanadi. Oylik bu yerda balansga qo'shilmaydi —
                # u kelganda haqiqiy kirim tranzaksiyasi sifatida yoziladi.
                user.balance = 0.0
                user.user_state = 'registered'
            # Mark as registered so they can use the app immediately
            if not user.phone_number:
                user.phone_number = f'tg_{telegram_id}'

            # Give configurable premium trial on first registration.
            # premium_until hech qachon tozalanmaydi — bo'shligi "hech qachon
            # premium bo'lmagan" degani, shuning uchun trial faqat bir marta beriladi.
            if not user.premium_until:
                from datetime import timedelta
                
                res_set = await session.execute(select(Settings).where(Settings.key == 'trial_premium_days'))
                trial_setting = res_set.scalars().first()
                trial_days = 3
                if trial_setting and trial_setting.value.isdigit():
                    trial_days = int(trial_setting.value)
                    
                user.premium_until = get_tashkent_time() + timedelta(days=trial_days)

            await session.flush()

            if not already_registered:
                if mode == 'quick':
                    user.daily_limit = requested_daily_limit
                else:
                    expenses = data.get('expenses', [])
                    if not isinstance(expenses, list):
                        return web.json_response({"error": "expenses ro'yxat bo'lishi kerak"}, status=400)
                    for exp in expenses[:100]:
                        if not isinstance(exp, dict) or not str(exp.get('name', '')).strip():
                            return web.json_response({"error": "Har bir xarajatda 'name' bo'lishi kerak"}, status=400)
                        try:
                            exp_amount = _parse_money(exp.get('amount', 0), "expenses.amount")
                        except ValueError as e:
                            return web.json_response({"error": str(e)}, status=400)
                        session.add(DetailedExpenses(
                            user_id=user.id,
                            name=str(exp['name']).strip()[:200],
                            amount=exp_amount,
                            due_date=str(exp.get('day', ''))[:20]
                        ))
                    remaining = monthly_income - user.fixed_expenses_total
                    user.daily_limit = round(remaining / 30, 2) if remaining > 0 else 0

            await session.commit()
            
            # Send message to user via Bot
            bot = request.app.get('bot')
            if bot:
                lang = user.language or 'uz'
                is_real_phone = user.phone_number and not user.phone_number.startswith('tg_')
                
                try:
                    texts_reg = {
                        'uz': "Ro'yxatdan o'tish muvaffaqiyatli yakunlandi!",
                        'ru': "Регистрация успешно завершена!",
                        'en': "Registration completed successfully!"
                    }
                    response_text = texts_reg.get(lang, texts_reg['uz'])
                    if user.registration_mode == 'detailed':
                        limit_text = f"\\n\\nSizning hisoblangan kunlik limitigingiz: {user.daily_limit:,.0f} so'm." if lang == 'uz' else (f"\\n\\nВаш расчетный дневной лимит: {user.daily_limit:,.0f} сум." if lang == 'ru' else f"\\n\\nYour calculated daily limit: {user.daily_limit:,.0f} UZS.")
                        response_text += limit_text
                    
                    if not getattr(user, 'accepted_policy', False):
                        # Show privacy policy automatically right after register
                        texts = {
                            'uz': "Ajoyib! Endi davom etishingiz uchun Maxfiylik siyosatimizga (Privacy Policy) rozilik bildirishingiz kerak.",
                            'ru': "Отлично! Для продолжения вы должны согласиться с нашей Политикой конфиденциальности.",
                            'en': "Great! To continue, you must agree to our Privacy Policy."
                        }
                        policy_msg = texts.get(lang, texts['uz'])
                        btn_uz, btn_ru, btn_en = "✅ Roziman", "✅ Согласен(на)", "✅ I Agree"
                        btn_msg = {'uz': btn_uz, 'ru': btn_ru, 'en': btn_en}.get(lang, btn_uz)
                        
                        from config import WEBAPP_URL
                        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                        from aiogram.types.web_app_info import WebAppInfo
                        
                        markup = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="📄 Privacy Policy", web_app=WebAppInfo(url=f"{WEBAPP_URL}/privacy?lang={lang}"))],
                            [InlineKeyboardButton(text=btn_msg, callback_data="accept_privacy_policy")]
                        ])
                        await bot.send_message(chat_id=telegram_id, text=response_text + "\\n\\n" + policy_msg, reply_markup=markup, parse_mode="HTML")
                    else:
                        from handlers.start import get_main_keyboard
                        await bot.send_message(chat_id=telegram_id, text=response_text, reply_markup=get_main_keyboard(telegram_id, lang))

                    # Reward referrer
                    if user.referred_by_id:
                        res_referrer = await session.execute(select(User).where(User.id == user.referred_by_id))
                        referrer = res_referrer.scalars().first()
                        if referrer:
                            referrer_lang = referrer.language or 'uz'
                            individual_msg = "🎉 Tabriklaymiz! Sizning taklifingiz orqali yangi do'stingiz ro'yxatdan o'tdi." if referrer_lang == 'uz' else ("🎉 Поздравляем! По вашей ссылке зарегистрировался новый друг." if referrer_lang == 'ru' else "🎉 Congratulations! A new friend registered via your invite link.")
                            try:
                                await bot.send_message(chat_id=referrer.telegram_id, text=individual_msg)
                            except:
                                pass
                                
                            count_res = await session.execute(select(func.count(User.id)).where(User.referred_by_id == referrer.id))
                            actual_ref_count = count_res.scalar() or 0
                            
                            ref_count_res = await session.execute(select(Settings).where(Settings.key == 'ref_count'))
                            ref_count_setting = ref_count_res.scalars().first()
                            ref_req = int(ref_count_setting.value) if ref_count_setting and ref_count_setting.value else 4
                            
                            ref_days_res = await session.execute(select(Settings).where(Settings.key == 'ref_days'))
                            ref_days_setting = ref_days_res.scalars().first()
                            ref_days = int(ref_days_setting.value) if ref_days_setting and ref_days_setting.value else 3
                            
                            if actual_ref_count > 0 and actual_ref_count % ref_req == 0:
                                if not referrer.premium_until or referrer.premium_until < get_tashkent_time():
                                    from datetime import timedelta
                                    referrer.premium_until = get_tashkent_time() + timedelta(days=ref_days)
                                else:
                                    from datetime import timedelta
                                    referrer.premium_until += timedelta(days=ref_days)
                                
                                await session.commit()
                                try:
                                    from utils.i18n import _
                                    bonus_msg = _('referrer_bonus', referrer_lang, count=actual_ref_count, req=ref_req, days=ref_days)
                                    await bot.send_message(
                                        chat_id=referrer.telegram_id, 
                                        text=bonus_msg
                                    )
                                except Exception as e:
                                    logging.error(f"Failed to send bonus message to referrer: {e}")
                except Exception as bot_err:
                    logging.error(f"Failed to send registration message to {telegram_id}: {bot_err}")

            return web.json_response({
                "status": "success",
                "daily_limit": user.daily_limit,
                "premium_until": user.premium_until.isoformat() if user.premium_until else None
            })
    except Exception as e:
        logging.exception(f"Registration error: {e}")
        return web.json_response({"error": "Internal server error. Please try again later."}, status=500)

async def handle_profile_stats(request):
    try:
        user_id = request.match_info.get('user_id')
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == int(user_id)))
            user = res.scalars().first()
            if not user or not user.phone_number: return web.json_response({"error": "User not found"}, status=404)
            
            # Simple tasks count
            stmt_tasks = select(func.count(Task.id)).where(Task.user_id == user.id)
            total_tasks = (await session.execute(stmt_tasks)).scalar() or 0
            
            stmt_tasks_done = select(func.count(Task.id)).where(Task.user_id == user.id, Task.is_completed == True)
            done_tasks = (await session.execute(stmt_tasks_done)).scalar() or 0
            
            tasks_completed_pct = round((done_tasks / total_tasks * 100)) if total_tasks > 0 else 0

            # Referrals list
            stmt_refs = select(User).where(User.referred_by_id == user.id).order_by(User.id.desc()).limit(5)
            refs = (await session.execute(stmt_refs)).scalars().all()
            
            total_refs_stmt = select(func.count(User.id)).where(User.referred_by_id == user.id)
            total_refs = (await session.execute(total_refs_stmt)).scalar() or 0
            
            # Get Referral settings
            ref_days_res = await session.execute(select(Settings).where(Settings.key == 'ref_days'))
            ref_days_setting = ref_days_res.scalars().first()
            ref_days = int(ref_days_setting.value) if ref_days_setting and ref_days_setting.value else 3
            
            ref_req_res = await session.execute(select(Settings).where(Settings.key == 'ref_count'))
            ref_req_setting = ref_req_res.scalars().first()
            ref_req = int(ref_req_setting.value) if ref_req_setting and ref_req_setting.value else 4

            uz_months = {
                1: 'Yan', 2: 'Fev', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Iyun',
                7: 'Iyul', 8: 'Avg', 9: 'Sen', 10: 'Okt', 11: 'Noya', 12: 'Dek'
            }
            
            def format_date(dt):
                if not dt: return "Noma'lum"
                return f"{dt.day} {uz_months.get(dt.month, '')}"
                
            referrals = [{"id": r.id, "name": getattr(r, 'name', "User") or "User", "date": format_date(r.created_at)} for r in refs]

            return web.json_response({
                "name": getattr(user, 'name', "Foydalanuvchi") or getattr(user, 'surname', "Foydalanuvchi") or "Foydalanuvchi",
                "proStatus": "Pro" if is_premium_active(user) else "Free",
                "disciplineLevel": "O'rtacha",
                "aiAnalysis": "Intizomingiz yaxshi, lekin xarajatlarni biroz nazorat qilish tavsiya etiladi.",
                "totalSaved": getattr(user, 'balance', 0),
                "tasksCompleted": tasks_completed_pct,
                "spendingStatus": "Yaxshi", 
                "referral": {
                    "code": getattr(user, 'referral_code', str(getattr(user, 'telegram_id', '0'))),
                    "earnings": getattr(user, 'bonus_balance', 0.0),
                    "invitedCount": total_refs,
                    "recentInvites": referrals,
                    "bonusDays": ref_days,
                    "bonusReq": ref_req
                },
                "user_language": getattr(user, 'language', 'uz')
            })
    except Exception as e:
        logging.exception(f"Profile stats error: {e}")
        return web.json_response({"error": "Internal server error. Please try again later."}, status=500)

def setup_routes(app):
    app.middlewares.append(auth_middleware)

    # Static WebApp serving — detect build output path
    base_dir = os.getcwd()
    static_path = os.path.join(base_dir, "web2", "out")
    alt_static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web2", "out")

    final_static_path = None
    if os.path.exists(static_path):
        final_static_path = static_path
    elif os.path.exists(alt_static_path):
        final_static_path = alt_static_path

    if final_static_path:
        logging.info(f"DEBUG: SERVING STATIC FROM: {final_static_path}")
        # Serve /_next chunk assets (JS, CSS bundles)
        app.router.add_static('/_next', os.path.join(final_static_path, '_next'))

    # ── API Routes FIRST — must be before SPA wildcard ──────────────────────
    app.router.add_post('/api/register', handle_register)
    app.router.add_post('/api/buy_premium', handle_buy_premium_request)
    app.router.add_get('/api/dashboard', handle_dashboard_stats)
    app.router.add_get('/api/finance/{user_id}', handle_finance_stats)
    app.router.add_get('/api/tasks/{user_id}', handle_tasks_list)
    app.router.add_post('/api/tasks/{user_id}', handle_create_task)
    app.router.add_post('/api/tasks/complete/{task_id}', handle_complete_task)
    app.router.add_get('/api/dreams/{user_id}', handle_get_dream)
    app.router.add_post('/api/dreams/{user_id}', handle_create_dream)
    app.router.add_get('/api/dreams/{user_id}/capacity', handle_dream_capacity)
    app.router.add_post('/api/dreams/{id}/progress', handle_dream_progress)
    app.router.add_post('/api/dreams/{id}/set_main', handle_set_main_dream)
    app.router.add_get('/api/user_data/{user_id}', handle_user_data)
    app.router.add_get('/api/profile/{user_id}', handle_profile_stats)
    app.router.add_post('/api/settings/lang/{user_id}', handle_update_lang)
    app.router.add_post('/api/settings/base_currency/{user_id}', handle_update_base_currency)
    app.router.add_post('/api/help/{user_id}', handle_help_request)
    # Admin API routes
    app.router.add_get('/api/mng-x89b2k1q/dashboard', handle_admin_dashboard)
    app.router.add_post('/api/mng-x89b2k1q/users/search', handle_admin_user_search)
    app.router.add_post('/api/mng-x89b2k1q/users/toggle_freeze', handle_admin_user_toggle_freeze)
    app.router.add_get('/api/mng-x89b2k1q/settings', handle_admin_settings_get)
    app.router.add_post('/api/mng-x89b2k1q/settings', handle_admin_settings_update)
    app.router.add_post('/api/mng-x89b2k1q/promos', handle_admin_promo_create)
    app.router.add_get('/api/mng-x89b2k1q/promos', handle_admin_promos_get)
    app.router.add_delete('/api/mng-x89b2k1q/promos/{id}', handle_admin_promo_delete)
    app.router.add_delete('/api/mng-x89b2k1q/users/{telegram_id}', handle_admin_user_archive)
    app.router.add_post('/api/dreams/{id}/cancel_request', handle_dream_cancel_request)
    app.router.add_post('/api/dreams/{id}/cancel_undo', handle_dream_cancel_undo)
    app.router.add_post('/api/dreams/{id}/complete', handle_dream_complete)
    app.router.add_post('/api/mng-x89b2k1q/dreams/cancel_confirm', handle_admin_dream_cancel_confirm)
    app.router.add_post('/api/mng-x89b2k1q/broadcast', handle_admin_broadcast)
    app.router.add_get('/api/mng-x89b2k1q/finance', handle_admin_finance)
    app.router.add_get('/api/mng-x89b2k1q/users/{telegram_id}/referrals', handle_admin_user_referrals)
    app.router.add_get('/api/mng-x89b2k1q/referrals/stats', handle_admin_referrals_stats)
    app.router.add_get('/api/mng-x89b2k1q/moderation/cancel_requests', handle_admin_moderation_cancel_requests)
    app.router.add_post('/api/mng-x89b2k1q/users/request_delete/{telegram_id}', handle_admin_user_request_delete)

    # ── SPA Fallback LAST — must not intercept API routes ────────────────────
    if final_static_path:
        async def spa_fallback(request):
            if request.path.startswith('/api/'):
                raise web.HTTPNotFound()

            # Serve root-level static files (images, favicon, robots.txt, etc.)
            rel_path = request.path.lstrip('/')
            if '..' in rel_path or rel_path.startswith('/'):
                raise web.HTTPForbidden()
                
            if rel_path:
                candidate = os.path.join(final_static_path, rel_path)
                if os.path.isfile(candidate):
                    return web.FileResponse(candidate)

            # Map specific paths to their pre-rendered HTML files
            path = request.path.rstrip('/')
            page_map = {
                '/mng-x89b2k1q': 'mng-x89b2k1q.html',
                '/register': 'register.html',
                '/privacy': 'privacy.html',
            }
            if path in page_map:
                page_file = os.path.join(final_static_path, page_map[path])
                if os.path.exists(page_file):
                    return web.FileResponse(page_file)

            # Default SPA fallback → index.html
            index_file = os.path.join(final_static_path, "index.html")
            if os.path.exists(index_file):
                return web.FileResponse(index_file)
            raise web.HTTPNotFound()

        app.router.add_get('/{tail:.*}', spa_fallback, name='spa_fallback')
    else:
        logging.info(f"DEBUG: STATIC PATH NOT FOUND. Checked {static_path} and {alt_static_path}")
        app.router.add_get('/', handle_index)
        app.router.add_get('/mng-x89b2k1q', handle_admin_index)

async def handle_admin_finance(request):
    try:
        from database.models import PremiumRequest, User
        from sqlalchemy import select, func
        async with session_scope() as session:
            now = get_tashkent_time()
            thirty_days_ago = now - timedelta(days=30)
            
            # PremiumRequest to'lovlari (status='paid')
            total_income_stmt = select(func.sum(PremiumRequest.amount)).where(PremiumRequest.status == 'paid')
            total_income = (await session.execute(total_income_stmt)).scalar() or 0.0
            
            # Monthly income from paid premium requests in the last 30 days
            monthly_income_stmt = select(func.sum(PremiumRequest.amount)).where(
                PremiumRequest.status == 'paid',
                PremiumRequest.created_at >= thirty_days_ago
            )
            monthly_income = float((await session.execute(monthly_income_stmt)).scalar() or 0.0)
            
            # Konversiya foizi (Premium userlar / Barcha userlar)
            premium_count = (await session.execute(select(func.count(User.id)).where(User.premium_until > now))).scalar() or 0
            total_count = (await session.execute(select(func.count(User.id)))).scalar() or 1
            conversion_rate = (premium_count / total_count) * 100
            
            return web.json_response({
                "total_income": total_income,
                "monthly_income": monthly_income,
                "conversion_rate": conversion_rate
            })
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_admin_user_referrals(request):
    try:
        telegram_id = request.match_info.get('telegram_id')
        page = int(request.query.get('page', 1))
        limit = 10
        offset = (page - 1) * limit
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == int(telegram_id)))
            user = res.scalars().first()
            if not user:
                return web.json_response({"error": "User not found"}, status=404)
            
            stmt = select(User.telegram_id).where(User.referred_by_id == user.id).limit(limit + 1).offset(offset)
            refs = (await session.execute(stmt)).scalars().all()
            
            has_more = len(refs) > limit
            refs_to_return = refs[:limit]
            
            return web.json_response({
                "referrals": refs_to_return,
                "has_more": has_more
            })
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_admin_referrals_stats(request):
    try:
        async with session_scope() as session:
            # Top 10 Referrals
            top_ref_stmt = select(User.referred_by_id, func.count(User.id).label('ref_count'))\
                .where(User.referred_by_id.isnot(None))\
                .group_by(User.referred_by_id)\
                .order_by(text('ref_count DESC'))\
                .limit(10)
            
            top_ref_rows = (await session.execute(top_ref_stmt)).all()
            top_10 = []
            for row in top_ref_rows:
                if row[0]:
                    referrer = await session.get(User, row[0])
                    top_10.append({
                        "id": row[0],
                        "telegram_id": getattr(referrer, 'telegram_id', ''),
                        "name": getattr(referrer, 'name', f"ID:{row[0]}") or f"ID:{row[0]}",
                        "count": row[1]
                    })

            # Inactive Referrals (users who were invited but have 0 balance or no usage)
            # Find users who have referred_by_id set, but last_active is old or hasn't done anything
            # SECURITY FIX: replaced datetime.now() with get_tashkent_time() for consistency
            thirty_days_ago = get_tashkent_time() - timedelta(days=30)
            inactive_stmt = select(User)\
                .where(User.referred_by_id.isnot(None))\
                .where(or_(User.last_active < thirty_days_ago, User.last_active.is_(None)))\
                .order_by(User.id.desc())\
                .limit(50)
                
            inactive_users = (await session.execute(inactive_stmt)).scalars().all()
            inactive_list = []
            for u in inactive_users:
                inactive_list.append({
                    "id": u.id,
                    "telegram_id": u.telegram_id,
                    "name": u.name or "Noma'lum",
                    "inviter_id": u.referred_by_id,
                    "last_active": get_last_active_str(u.last_active)
                })

            return web.json_response({
                "top_10": top_10,
                "inactive": inactive_list
            })
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_dream_complete(request):
    try:
        dream_id = request.match_info.get('id')
        telegram_user_id = request.get('telegram_user_id')
        if not telegram_user_id:
            return web.json_response({"error": "Unauthorized. InitData missing."}, status=401)

        async with session_scope() as session:
            dream = await session.get(Dream, int(dream_id))
            if not dream:
                return web.json_response({"error": "Dream not found"}, status=404)
            
            res = await session.execute(select(User).where(User.telegram_id == telegram_user_id))
            owner = res.scalars().first()
            if not owner or dream.user_id != owner.id:
                return web.json_response({"error": "Forbidden"}, status=403)
            
            # is_active tekshiruvisiz bu endpoint qayta-qayta chaqirilib, har safar
            # Gemini chaqiruvi va Telegram xabariga sabab bo'lardi.
            if not dream.is_active:
                return web.json_response({"error": "Bu orzu allaqachon yakunlangan"}, status=400)

            if dream.saved_amount < dream.total_amount:
                return web.json_response({"error": "Orzu uchun yetarli mablag' yig'ilmagan"}, status=400)

            dream.is_active = False
            
            # Fetch user to send message
            res = await session.execute(select(User).where(User.id == dream.user_id).limit(1))
            user = res.scalars().first()
            
            ai_message = "Tabriklaymiz! Siz orzuyingizga erishdingiz!"
            if user:
                u_name = user.name or "bot a'zosi"
                prompt = f"Foydalanuvchi '{u_name}' o'zining '{dream.dream_name}' nomli orzusi uchun yetarli mablag' yig'ib, maqsadiga erishdi. Unga juda ham iliq, ruhlantiruvchi va tabriklovchi qisqa xabar yoz. 'Mana sen uddalading, yangi orzular qilish vaqti keldi!' ma'nosida bo'lsin. QAT'IY QOIDA: O'zbek tilida yozing. Hech qanday variantlar yoki kirish/chiqish so'zlari ishlatmang (masalan, 'Mana variant' demang). Faqatgina bitta yakuniy xabarni o'zini qaytaring."
                try:
                    # SECURITY FIX: use safe_generate_content (goes through global semaphore)
                    response = await safe_generate_content(prompt)
                    ai_message = response.text if response else ai_message
                except Exception as e:
                    logging.error(f"Gemini error on dream complete: {e}")
                
                if 'bot' in request.app:
                    try:
                        await request.app['bot'].send_message(chat_id=user.telegram_id, text=ai_message)
                    except Exception as e:
                        logging.error(f"Failed to send complete message: {e}")
            
            await session.commit()
            return web.json_response({"status": "success", "message": ai_message})
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_dream_cancel_undo(request):
    try:
        dream_id = request.match_info.get('id')
        telegram_user_id = request.get('telegram_user_id')
        if not telegram_user_id:
            return web.json_response({"error": "Unauthorized. InitData missing."}, status=401)

        async with session_scope() as session:
            dream = await session.get(Dream, int(dream_id))
            if not dream:
                return web.json_response({"error": "Dream not found"}, status=404)
            
            res = await session.execute(select(User).where(User.telegram_id == telegram_user_id))
            owner = res.scalars().first()
            if not owner or dream.user_id != owner.id:
                return web.json_response({"error": "Forbidden"}, status=403)
            
            dream.cancel_requested = False
            await session.commit()
            return web.json_response({"status": "success"})
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_admin_dream_cancel_confirm(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        dream_id = data.get('dream_id')
        
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == int(telegram_id)))
            user = res.scalars().first()
            if not user:
                return web.json_response({"error": "User not found"}, status=404)
                
            dream = await session.get(Dream, int(dream_id))
            if not dream:
                return web.json_response({"error": "Dream not found"}, status=404)
                
            dream.is_active = False
            dream.cancel_requested = False
            
            # Use Gemini to generate an empathetic response message
            from services.gemini_service import GeminiService
            
            # Simple AI message generation call: (Assuming GeminiService method exists or using general chat)
            # The user requested a new prompt giving a light warning about giving up.
            username = user.name or "do'st"
            prompt = f"Foydalanuvchi '{username}' o'zining '{dream.dream_name}' nomli orzusidan voz kechishni tasdiqladi va orzu o'chirildi. Unga o'zbek tilida AI sifatida yengilroq tanbeh va motivatsiya beruvchi qisqa xabar yoz. Ma'nosi shunday bo'lsin: 'Sen bugun orzuingdan voz kechding, ertaga-chi? Agar bu og'ir vaziyatga tushib qolganing uchun bo'lsa tushunaman va qabul qilaman, ammo shunchaki nafsing yoki erinchoqlik uchun bo'lsa, kelajaging haqida yaxshilab o'ylab ko'rganing yaxshi bo'lardi. Men seni har doim qo'llab-quvvatlayman, lekin o'z maqsading yo'lida taslim bo'lma.' Matn qisqa, ta'sirli va do'stona bo'lsin."
            
            try:
                # SECURITY FIX: use safe_generate_content (goes through global semaphore)
                response = await safe_generate_content(prompt)
                ai_message = response.text if response else "Sizning orzuingiz bekor qilindi."
            except Exception as e:
                ai_message = "Sizning orzuingiz bekor qilindi."
                logging.error(f"Gemini AI error during dream cancel: {e}")
                
            # Send the message via Telegram Bot instance
            if 'bot' in request.app:
               try:
                   await request.app['bot'].send_message(chat_id=user.telegram_id, text=ai_message)
               except Exception as e:
                   logging.error(f"Failed to send dream cancel message: {e}")
                   
            await session.commit()
            return web.json_response({"success": True, "message": ai_message})
            
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_admin_moderation_cancel_requests(request):
    try:
        requests_list = []
        async with session_scope() as session:
            res = await session.execute(
                select(Dream, User)
                .join(User, Dream.user_id == User.id)
                .where(Dream.cancel_requested == True, Dream.is_active == True)
            )
            for dream, user in res.all():
                requests_list.append({
                    "user_id": user.telegram_id,
                    "first_name": user.name,
                    "dream_id": dream.id,
                    "dream_name": dream.dream_name,
                    "saved": dream.saved_amount,
                    "total": dream.total_amount
                })
        return web.json_response({"status": "success", "requests": requests_list})
    except Exception as e:
        logging.error(f"Error in moderation: {e}")
        return web.json_response({"error": "Ichki xatolik"}, status=500)

async def handle_admin_user_request_delete(request):
    try:
        telegram_id = request.match_info.get('telegram_id')
        if not telegram_id:
            return web.json_response({"error": "No ID"}, status=400)
            
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == int(telegram_id)))
            user = res.scalars().first()
            if not user:
                return web.json_response({"error": "Not found"}, status=404)
                
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Ha", callback_data=f"confirm_delete_yes_{user.telegram_id}")],
                [InlineKeyboardButton(text="Yo'q", callback_data=f"confirm_delete_no_{user.telegram_id}")]
            ])
            
            # Send the message via Telegram Bot instance
            if 'bot' in request.app:
                await request.app['bot'].send_message(
                    chat_id=user.telegram_id, 
                    text="Admin sizning ma'lumotlaringizni butunlay o'chirmoqchi. Rozimisiz? E'tibor bering, barcha ma'lumotlaringiz va maqsadlaringiz o'chib ketadi va qayta tiklanmaydi.",
                    reply_markup=markup
                )
            
        return web.json_response({"status": "success"})
    except Exception as e:
        logging.error(f"Error in request delete: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_admin_dashboard(request):
    try:
        async with session_scope() as session:
            now = get_tashkent_time()
            thirty_days_ago = now - timedelta(days=30)
            today_start = datetime(now.year, now.month, now.day)
            
            # Users
            total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
            new_users_today = (await session.execute(select(func.count(User.id)).where(User.created_at >= today_start))).scalar() or 0
            
            # Active
            today_active = (await session.execute(select(func.count(Transaction.user_id.distinct())).where(Transaction.timestamp >= today_start))).scalar() or 0
            
            # Premium
            total_premium = (await session.execute(select(func.count(User.id)).where(User.premium_until > now))).scalar() or 0
            
            # Revenue Today (from transactions where amount > 0 and type == income or premium request)
            from database.models import PremiumRequest
            today_revenue = (await session.execute(select(func.sum(PremiumRequest.amount)).where(PremiumRequest.created_at >= today_start, PremiumRequest.status == 'paid'))).scalar() or 0
            
            # Dreams created today
            dreams_today = (await session.execute(select(func.count(Dream.id)).where(Dream.created_at >= today_start))).scalar() or 0
            
            # Tasks completed today
            tasks_completed_today = (await session.execute(select(func.count(Task.id)).where(Task.is_completed == True))).scalar() or 0
            
            # Discipline Average
            total_tasks_ever = (await session.execute(select(func.count(Task.id)))).scalar() or 0
            tasks_completed_ever = (await session.execute(select(func.count(Task.id)).where(Task.is_completed == True))).scalar() or 0
            avg_discipline = int((tasks_completed_ever / total_tasks_ever) * 100) if total_tasks_ever > 0 else 0
            
            # Errors today
            errors_today = 0 # No ErrorLog model exists yet
            
            # Revenue Chart (Last 7 days)
            revenue_chart = []
            for i in range(7):
                d = today_start - timedelta(days=6-i)
                d_end = d + timedelta(days=1)
                rev = (await session.execute(select(func.sum(PremiumRequest.amount)).where(PremiumRequest.created_at >= d, PremiumRequest.created_at < d_end, PremiumRequest.status == 'paid'))).scalar() or 0
                revenue_chart.append({"date": d.strftime("%d %b"), "amount": rev})
                
            # Platform Health
            active_users_30d = (await session.execute(select(func.count(User.id)).where(User.last_active >= thirty_days_ago))).scalar() or 0
            active_ratio = int((active_users_30d / total_users) * 100) if total_users > 0 else 0
            premium_ratio = int((total_premium / total_users) * 100) if total_users > 0 else 0
            
            total_dreams = (await session.execute(select(func.count(Dream.id)))).scalar() or 0
            active_dreams = (await session.execute(select(func.count(Dream.id)).where(Dream.is_active == True))).scalar() or 0
            dream_ratio = int((active_dreams / total_dreams) * 100) if total_dreams > 0 else 0
            
            health_score = int((active_ratio + avg_discipline + dream_ratio + premium_ratio) / 4)
            health_metrics = {
                "active_users": active_ratio,
                "task_completion": avg_discipline,
                "dream_continuation": dream_ratio,
                "premium_conversion": premium_ratio,
                "error_rate": 0
            }
            
            # Popular Dreams - limit to 1000 to avoid RAM issues on large deployments
            pop_dreams_stmt = select(Dream.dream_name).limit(1000)
            all_dreams = (await session.execute(pop_dreams_stmt)).scalars().all()
            from collections import Counter
            dream_counter = Counter(all_dreams)
            top_dreams = dream_counter.most_common(5)
            colors = ["#10B981", "#3B82F6", "#F59E0B", "#EF4444", "#8B5CF6"]
            popular_dreams = [{"name": name, "value": count, "fill": colors[i % len(colors)]} for i, (name, count) in enumerate(top_dreams)]
            if not popular_dreams:
                popular_dreams = [{"name": "Ma'lumot yo'q", "value": 100, "fill": "#E2E8F0"}]
            
            # User Activity
            user_activity = []
            for i in range(7):
                d = today_start - timedelta(days=6-i)
                d_end = d + timedelta(days=1)
                count = (await session.execute(select(func.count(User.id)).where(User.last_active >= d, User.last_active < d_end))).scalar() or 0
                user_activity.append({"date": d.strftime("%d %b"), "count": count})
                
            # Recent Activity
            recent_activity_raw = []
            
            new_users = (await session.execute(select(User).order_by(User.created_at.desc()).limit(3))).scalars().all()
            for u in new_users:
                recent_activity_raw.append({
                    "time_val": u.created_at,
                    "type": "new_user", "text": "Yangi foydalanuvchi", "sub": f"ID: {u.telegram_id}"
                })
                
            recent_premium = (await session.execute(select(PremiumRequest).where(PremiumRequest.status == 'paid').order_by(PremiumRequest.created_at.desc()).limit(3))).scalars().all()
            for p in recent_premium:
                recent_activity_raw.append({
                    "time_val": p.created_at,
                    "type": "premium", "text": "Premium olindi", "sub": f"{p.amount} UZS"
                })
                
            recent_dreams = (await session.execute(select(Dream).order_by(Dream.created_at.desc()).limit(3))).scalars().all()
            for d in recent_dreams:
                recent_activity_raw.append({
                    "time_val": d.created_at,
                    "type": "dream", "text": "Yangi orzu", "sub": d.dream_name
                })
                
            recent_activity_raw.sort(key=lambda x: x["time_val"] or datetime.min, reverse=True)
            top_recent = recent_activity_raw[:3]
            
            recent_activity = []
            for i, r in enumerate(top_recent):
                if not r["time_val"]:
                    time_str = "Noma'lum"
                else:
                    diff = now - r["time_val"]
                    if diff.total_seconds() < 3600:
                        time_str = f"{int(diff.total_seconds() // 60)} daqiqa oldin"
                    elif diff.total_seconds() < 86400:
                        time_str = f"{int(diff.total_seconds() // 3600)} soat oldin"
                    else:
                        time_str = f"{int(diff.total_seconds() // 86400)} kun oldin"
                recent_activity.append({
                    "id": i + 1,
                    "type": r["type"],
                    "text": r["text"],
                    "sub": r["sub"],
                    "time": time_str
                })

            return web.json_response({
                "stats": {
                    "total_users": total_users,
                    "new_users_today": new_users_today,
                    "active_users_today": today_active,
                    "total_premium": total_premium,
                    "today_revenue": today_revenue,
                    "dreams_today": dreams_today,
                    "tasks_completed_today": tasks_completed_today,
                    "avg_discipline": avg_discipline,
                    "errors_today": errors_today
                },
                "revenue_chart": revenue_chart,
                "health": {
                    "score": health_score,
                    "metrics": health_metrics
                },
                "popular_dreams": popular_dreams,
                "user_activity": user_activity,
                "recent_activity": recent_activity
            })
    except Exception as e:
        logging.error(f"Admin Dashboard Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def _run_broadcast(bot, message_text: str):
    """Fonda ishlaydi: foydalanuvchilar soni ko'p bo'lganda bu daqiqalar davom etadi."""
    sent = failed = 0
    async with session_scope() as session:
        res = await session.execute(select(User.telegram_id))
        users = res.scalars().all()

    for uid in users:
        try:
            # parse_mode=None broadcast matnida Markdown/HTML injeksiyasini oldini oladi
            await bot.send_message(chat_id=uid, text=message_text, parse_mode=None)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # Telegram rate limit himoyasi

    logging.info(f"Broadcast tugadi: {sent} yuborildi, {failed} muvaffaqiyatsiz, jami {len(users)}")


async def handle_admin_broadcast(request):
    try:
        data = await request.json()
        message_text = data.get('message')
        if not message_text or not str(message_text).strip():
            return web.json_response({"error": "Message required"}, status=400)
        if len(message_text) > 4096:
            return web.json_response({"error": "Xabar juda uzun (maksimum 4096 belgi)"}, status=400)

        bot = request.app.get('bot')
        if not bot:
            return web.json_response({"error": "Bot instance not found"}, status=500)

        async with session_scope() as session:
            total = (await session.execute(select(func.count(User.id)))).scalar() or 0

        # So'rov ichida yuborish minglab foydalanuvchida timeout'ga olib keladi va
        # admin qayta bosganda xabar takrorlanadi.
        task = asyncio.create_task(_run_broadcast(bot, message_text))
        request.app.setdefault('background_tasks', set()).add(task)
        task.add_done_callback(request.app['background_tasks'].discard)

        return web.json_response({"success": True, "queued_for": total})

    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_admin_user_search(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        if not telegram_id or not str(telegram_id).isdigit():
            return web.json_response({"error": "Noto'g'ri yoki bo'sh telegram_id"}, status=400)
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == int(telegram_id)))
            user = res.scalars().first()
            if not user:
                return web.json_response({"error": "Foydalanuvchi topilmadi"}, status=404)
            
            # Fetch active dream
            stmt_dream = select(Dream).where(Dream.user_id == user.id, Dream.is_active == True)
            dream = (await session.execute(stmt_dream)).scalars().first()
            
            active_dream_id = None
            dream_cancel_requested = False
            if dream:
                active_dream_id = dream.id
                dream_cancel_requested = dream.cancel_requested
                
            # Calculate discipline
            stmt_tasks = select(Task).where(Task.user_id == user.id)
            tasks = (await session.execute(stmt_tasks)).scalars().all()
            total_tasks = len(tasks)
            completed_tasks = sum(1 for t in tasks if t.is_completed)
            discipline_score = int((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0
                
            return web.json_response({
                "id": user.id,
                "telegram_id": user.telegram_id,
                "name": user.name or "Noma'lum",
                "is_frozen": user.is_frozen,
                "is_premium": is_premium_active(user),
                "active_dream_id": active_dream_id,
                "dream_cancel_requested": dream_cancel_requested,
                "last_active": get_last_active_str(getattr(user, 'last_active', None)),
                "balance": user.balance or 0.0,
                "discipline_score": discipline_score
            })
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_admin_user_toggle_freeze(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == int(telegram_id)))
            user = res.scalars().first()
            if not user:
                return web.json_response({"error": "Foydalanuvchi topilmadi"}, status=404)
            
            user.is_frozen = not user.is_frozen
            if not user.is_frozen:
                user.frozen_until = None
            await session.commit()
            return web.json_response({"success": True, "is_frozen": user.is_frozen})
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_admin_user_archive(request):
    try:
        telegram_id = request.match_info.get('telegram_id')
        if not telegram_id:
             return web.json_response({"error": "Telegram ID required"}, status=400)
             
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == int(telegram_id)))
            user = res.scalars().first()
            if not user:
                return web.json_response({"error": "Foydalanuvchi topilmadi"}, status=404)
            
            bot = request.app.get('bot')
            if bot:
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Ha, barchasini o'chirishga roziman", callback_data=f"confirm_delete_yes_{telegram_id}")],
                    [InlineKeyboardButton(text="Yo'q, adashmovchilik", callback_data=f"confirm_delete_no_{telegram_id}")]
                ])
                text = (
                    "⚠️ **Diqqat! Sizning so'rovingizga binoan**\n\n"
                    "Admin sizning barcha akkaunt ma'lumotlaringizni o'chirib yuborish bo'yicha ruxsat so'ramoqda. Rozimisiz?\n\n"
                    "❗️ *Agar rozilik bildirsangiz, sizning barcha orzularingiz, xarajatlaringiz, qarzlaringiz va hisob-kitoblaringiz qayta tiklanmaydigan darajada bazadan butunlay o'chirib tashlanadi!*\n\n"
                    "O'ylab ko'rib, aniq qaroringizni belgilang:"
                )
                try:
                    await bot.send_message(chat_id=int(telegram_id), text=text, reply_markup=markup, parse_mode="Markdown")
                except Exception as e:
                    logging.error(f"Failed to send delete approval to {telegram_id}: {e}")
                    return web.json_response({"error": "Bot foydalanuvchiga xabar yubora olmadi. Balki u botni bloklagan."}, status=400)
            
            return web.json_response({"success": True, "status": "approval_sent"})
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_admin_settings_get(request):
    try:
        async with session_scope() as session:
            res = await session.execute(select(Settings))
            settings = res.scalars().all()
            result = {s.key: s.value for s in settings}
            return web.json_response(result)
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_admin_settings_update(request):
    try:
        data = await request.json()
        async with session_scope() as session:
            for k, v in data.items():
                if v is None: continue
                # find or create
                res = await session.execute(select(Settings).where(Settings.key == k))
                setting = res.scalars().first()
                if setting:
                    setting.value = str(v)
                else:
                    session.add(Settings(key=k, value=str(v)))
            await session.commit()
            return web.json_response({"success": True})
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_admin_promos_get(request):
    try:
        async with session_scope() as session:
            res = await session.execute(select(PromoCode).order_by(PromoCode.id.desc()))
            promos = res.scalars().all()
            return web.json_response([{
                "id": p.id, "code": p.code, "days": p.days, "max_uses": p.max_uses, "current_uses": p.current_uses
            } for p in promos])
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_admin_promo_create(request):
    try:
        data = await request.json()
        async with session_scope() as session:
            promo = PromoCode(
                code=data['code'],
                days=int(data['days']),
                max_uses=int(data.get('max_uses', 1))
            )
            session.add(promo)
            await session.commit()
            return web.json_response({"success": True})
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_admin_promo_delete(request):
    try:
        promo_id = int(request.match_info.get('id'))
        async with session_scope() as session:
            promo = await session.get(PromoCode, promo_id)
            if promo:
                await session.delete(promo)
                await session.commit()
            return web.json_response({"success": True})
    except Exception as e:
        logging.error(f"Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)

async def handle_user_data(request):
    try:
        user_id = request.match_info.get('user_id')
        if not user_id:
             return web.json_response({"error": "Missing user_id"}, status=400)
        
        async with session_scope() as session:
            res = await session.execute(select(User).where(User.telegram_id == int(user_id)).limit(1))
            user = res.scalars().first()
            if not user or not user.phone_number:
                 return web.json_response({"error": "User not found"}, status=404)
            
            if not is_premium_active(user):
                 return web.json_response({"error": "premium_required"}, status=403)
            
            base_currency = (getattr(user, 'base_currency', 'UZS') or 'UZS').upper()
            start_of_day, _ = finance_service.day_bounds()

            daily = await finance_service.daily_totals(session, user.id, base_currency)
            monthly = await finance_service.monthly_totals(session, user.id, base_currency)
            todays = await finance_service.transactions_since(session, user.id, start_of_day)

            daily_expense = daily.expense
            daily_income = daily.income
            monthly_expense = monthly.expense
            transactions_data = [_serialize_transaction(t) for t in todays]

            # Tasks
            stmt_tasks = select(Task).where(
                Task.user_id == user.id,
                Task.is_completed == False 
            ).order_by(Task.due_date)
            tasks = (await session.execute(stmt_tasks)).scalars().all()
            tasks_data = [{
                "id": t.id, "title": t.title,
                "date": t.due_date.strftime('%Y-%m-%d %H:%M') if t.due_date else "",
                "is_completed": t.is_completed, "is_ai": t.is_ai_generated
            } for t in tasks]

            # Dreams
            stmt_dream = select(Dream).where(Dream.user_id == user.id, Dream.is_active == True).limit(1)
            dream = (await session.execute(stmt_dream)).scalars().first()
            dream_data = None
            if dream:
                stmt_prog = select(DreamProgress).where(
                    DreamProgress.dream_id == dream.id,
                    DreamProgress.date >= start_of_day
                ).limit(1)
                progress_today = (await session.execute(stmt_prog)).scalars().first()
                dream_data = {
                    "id": dream.id, "name": dream.dream_name,
                    "total": dream.total_amount, "saved": dream.saved_amount,
                    "daily_target": dream.daily_limit_target, "paid_today": bool(progress_today),
                    "deadline": dream.deadline.strftime('%Y-%m-%d') if dream.deadline else None,
                    "cancel_requested": dream.cancel_requested
                }

            admin_id = ADMIN_IDS[0] if ADMIN_IDS else None

            return web.json_response({
                "user": {
                    "balance": user.balance,
                    "daily_limit": user.daily_limit,
                    "monthly_income": getattr(user, 'monthly_income', 0.0),
                    "fixed_expenses_total": getattr(user, 'fixed_expenses_total', 0.0),
                    "currency": "so'm",
                    "admin_id": admin_id,
                    "language": user.language or 'uz'
                },
                "finance": {
                    "daily_expense": daily_expense,
                    "monthly_expense": monthly_expense,
                    "transactions": transactions_data
                },
                "tasks": tasks_data,
                "dream": dream_data
            })
    except Exception as e:
        logging.error(f"User Data API Error: {e}")
        return web.json_response({"error": "Ichki server xatoligi"}, status=500)
