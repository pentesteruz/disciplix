"""
Moliyaviy so'rovlarning yagona joyi.

Ilgari "foydalanuvchining kunlik xarajati qancha" degan savol kodda uch marta,
uch xil yozilgan edi — `handle_dashboard_stats` `Transaction` dan, `handle_finance_stats`
va `handle_user_data` esa `Finance` dan o'qirdi. Uchalasi turli natija berardi.

Bu modul HTTP va aiogram'ga bog'liq emas, shuning uchun uni testdan o'tkazsa bo'ladi.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func, select

from database.models import Transaction
from utils.currency import CurrencyConverter
from utils.timezone import get_tashkent_time

INCOME_TYPES = ("income", "kirim", "daromad")
EXPENSE_TYPES = ("expense", "chiqim")

# Kunlik limitga kirmaydigan kategoriya: ijara, soliq kabi majburiy to'lovlar
# foydalanuvchi ixtiyoridagi xarajat emas.
MANDATORY_CATEGORY = "Majburiy xarajat"


def is_income(tx_type: str) -> bool:
    return (tx_type or "").lower() in INCOME_TYPES


def is_expense(tx_type: str) -> bool:
    return (tx_type or "").lower() in EXPENSE_TYPES


def day_bounds(moment: datetime = None):
    """Berilgan paytdagi kunning boshi va oxiri (Toshkent vaqti)."""
    moment = moment or get_tashkent_time()
    start = datetime(moment.year, moment.month, moment.day)
    return start, start + timedelta(days=1)


def month_start(moment: datetime = None) -> datetime:
    moment = moment or get_tashkent_time()
    return datetime(moment.year, moment.month, 1)


@dataclass
class PeriodTotals:
    """Bir davr uchun kirim/chiqim yig'indisi, bazaviy valyutada."""
    income: float = 0.0
    expense: float = 0.0
    discretionary_expense: float = 0.0  # 'Majburiy xarajat' hisobga olinmagan
    by_currency: dict = field(default_factory=dict)

    @property
    def net(self) -> float:
        return self.income - self.expense


async def _to_base(amount, currency, base_currency) -> float:
    return await CurrencyConverter.convert(float(amount or 0), (currency or "UZS").upper(), base_currency)


async def totals_for_period(
    session, user_id: int, start: datetime, end: datetime, base_currency: str = "UZS"
) -> PeriodTotals:
    """Berilgan davr uchun kirim/chiqim, bazaviy valyutaga o'tkazilgan holda."""
    stmt = select(
        Transaction.amount, Transaction.type, Transaction.currency, Transaction.category
    ).where(
        Transaction.user_id == user_id,
        Transaction.timestamp >= start,
        Transaction.timestamp < end,
    )
    rows = (await session.execute(stmt)).all()

    totals = PeriodTotals()
    for amount, tx_type, currency, category in rows:
        currency = (currency or "UZS").upper()
        in_base = await _to_base(amount, currency, base_currency)

        bucket = totals.by_currency.setdefault(currency, {"income": 0.0, "expense": 0.0})
        if is_income(tx_type):
            totals.income += in_base
            bucket["income"] += float(amount or 0)
        elif is_expense(tx_type):
            totals.expense += in_base
            bucket["expense"] += float(amount or 0)
            if category != MANDATORY_CATEGORY:
                totals.discretionary_expense += in_base

    return totals


async def daily_totals(session, user_id: int, base_currency: str = "UZS") -> PeriodTotals:
    start, end = day_bounds()
    return await totals_for_period(session, user_id, start, end, base_currency)


async def monthly_totals(session, user_id: int, base_currency: str = "UZS") -> PeriodTotals:
    start = month_start()
    _, end = day_bounds()
    return await totals_for_period(session, user_id, start, end, base_currency)


async def balances_by_currency(session, user_id: int) -> dict:
    """Har bir valyuta bo'yicha umumiy kirim/chiqim (konversiyasiz, xom holda)."""
    stmt = (
        select(Transaction.currency, Transaction.type, func.sum(Transaction.amount))
        .where(Transaction.user_id == user_id)
        .group_by(Transaction.currency, Transaction.type)
    )
    rows = (await session.execute(stmt)).all()

    balances = {}
    for currency, tx_type, total in rows:
        currency = (currency or "UZS").upper()
        bucket = balances.setdefault(currency, {"income": 0.0, "expense": 0.0})
        if is_income(tx_type):
            bucket["income"] += float(total or 0)
        else:
            bucket["expense"] += float(total or 0)
    return balances


async def compute_balance(session, user_id: int, base_currency: str = "UZS") -> float:
    """
    Balansning YAGONA manbai: barcha tranzaksiyalar yig'indisi.

    Ilgari ikkita raqobatlashuvchi balans bor edi — `users.balance` ustuni
    (finance.py har tranzaksiyada o'zgartirardi) va dashboard'ning o'z hisobi.
    Ular vaqt o'tishi bilan bir-biridan uzoqlashardi.

    Bundan tashqari dashboard `monthly_income` ni ham qo'shardi, ya'ni
    ro'yxatdan o'tishda aytilgan oylik doimiy soxta daromad bo'lib qolardi va
    foydalanuvchi "oylik oldim" desa summa ikki marta hisoblanardi.
    """
    balances = await balances_by_currency(session, user_id)
    jami = 0.0
    for currency, totals in balances.items():
        kirim = await _to_base(totals["income"], currency, base_currency)
        chiqim = await _to_base(totals["expense"], currency, base_currency)
        jami += kirim - chiqim
    return jami


async def sync_balance_cache(session, user) -> float:
    """`users.balance` keshini haqiqiy yig'indiga moslaydi va uni qaytaradi."""
    haqiqiy = await compute_balance(session, user.id,
                                    (getattr(user, "base_currency", "UZS") or "UZS").upper())
    user.balance = round(haqiqiy, 2)
    return haqiqiy


async def daily_surplus(session, user, base_currency: str = None) -> float:
    """
    Bugun kunlik limitdan ortib qolgan summa.

    Majburiy xarajatlar (ijara, soliq) limitga kirmaydi, shuning uchun
    ixtiyoriy sarf asos qilib olinadi. Manfiy bo'lsa 0 qaytadi — limitdan
    oshgan holatda "ortiqcha pul" yo'q.
    """
    base_currency = base_currency or (getattr(user, "base_currency", "UZS") or "UZS").upper()
    limit = float(getattr(user, "daily_limit", 0) or 0)
    if limit <= 0:
        return 0.0
    totals = await daily_totals(session, user.id, base_currency)
    return max(0.0, limit - totals.discretionary_expense)


async def recent_transactions(session, user_id: int, limit: int = 20):
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.timestamp.desc())
        .limit(limit)
    )
    return (await session.execute(stmt)).scalars().all()


async def transactions_since(session, user_id: int, since: datetime):
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id, Transaction.timestamp >= since)
        .order_by(Transaction.timestamp.desc())
    )
    return (await session.execute(stmt)).scalars().all()


def record_transaction(
    session,
    user_id: int,
    amount: float,
    category: str,
    tx_type: str,
    currency: str = "UZS",
    description: str = None,
    ai_advice: str = None,
    due_date: datetime = None,
) -> Transaction:
    """
    Pul harakatini yozadi. Yagona yozuv nuqtasi — ilgari bu ikkita jadvalga
    qo'lda ikki marta yozilardi va ikkitasi turli maydonlar olardi.

    Chaqiruvchi commit qilishi kerak.
    """
    normalized = "income" if is_income(tx_type) else "expense"
    tx = Transaction(
        user_id=user_id,
        amount=amount,
        currency=(currency or "UZS").upper(),
        category=category,
        type=normalized,
        description=description,
        ai_advice=ai_advice,
        due_date=due_date,
        timestamp=get_tashkent_time(),
    )
    session.add(tx)
    return tx
