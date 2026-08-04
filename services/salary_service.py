"""
Oylik oqimi.

QOIDA
-----
`monthly_income` — bu faqat mo'ljal, balansga kirmaydi. Oylik kelganda
foydalanuvchi tasdiqlaydi va o'shanda HAQIQIY kirim tranzaksiyasi yoziladi.
Shundan keyin balans faqat tranzaksiyalardan yig'iladi.

NIMA UCHUN AVTOMATIK EMAS
-------------------------
Oylik kechikishi, kam yoki ko'p tushishi mumkin. Avtomatik yozilsa, balansda
haqiqatda yo'q pul paydo bo'ladi va foydalanuvchi limitdan oshib ketadi.
Shuning uchun tizim so'raydi, foydalanuvchi tasdiqlaydi.
"""

import calendar
from datetime import datetime, timedelta

from services.finance_service import record_transaction
from utils.timezone import get_tashkent_time

SALARY_CATEGORY = "Oylik"


def resolve_salary_date(year: int, month: int, salary_day: int) -> datetime:
    """
    Berilgan oydagi oylik sanasini qaytaradi.

    Oyda bunday kun bo'lmasa (masalan 31-fevral) oyning oxirgi kuniga
    tushiriladi — aks holda fevralda oylik hech qachon kelmasdi.
    """
    oxirgi_kun = calendar.monthrange(year, month)[1]
    return datetime(year, month, min(salary_day, oxirgi_kun))


def period_key(moment: datetime) -> str:
    """Oy kaliti: 'YYYY-MM'. Bir oy uchun ikki marta yozilmasligini ta'minlaydi."""
    return f"{moment.year:04d}-{moment.month:02d}"


def is_salary_due(user, now: datetime = None) -> bool:
    """Bugun (yoki undan keyin) shu oyning oyligi so'ralishi kerakmi."""
    if not getattr(user, "salary_day", None):
        return False
    now = now or get_tashkent_time()
    if getattr(user, "salary_confirmed_for", None) == period_key(now):
        return False
    return now.date() >= resolve_salary_date(now.year, now.month, user.salary_day).date()


def is_report_due(user, now: datetime = None) -> bool:
    """
    Oylik hisobot kuni — oylik tushishidan bir kun oldin.

    Foydalanuvchi o'tgan oyni ko'rib chiqib, keyingi oyga tayyorlanadi.
    """
    if not getattr(user, "salary_day", None):
        return False
    now = now or get_tashkent_time()
    salary_date = resolve_salary_date(now.year, now.month, user.salary_day)
    return now.date() == (salary_date - timedelta(days=1)).date()


def confirm_salary(session, user, amount: float = None, now: datetime = None):
    """
    Oylikni tasdiqlaydi: kirim tranzaksiyasini yozadi va oyni belgilaydi.

    Qaytaradi: yaratilgan Transaction, yoki allaqachon tasdiqlangan bo'lsa None.
    """
    now = now or get_tashkent_time()
    kalit = period_key(now)
    if getattr(user, "salary_confirmed_for", None) == kalit:
        return None   # shu oy uchun allaqachon yozilgan

    if amount is None:
        amount = float(getattr(user, "monthly_income", 0) or 0)
    if amount <= 0:
        return None

    tx = record_transaction(
        session,
        user_id=user.id,
        amount=amount,
        category=SALARY_CATEGORY,
        tx_type="income",
        currency=(getattr(user, "base_currency", "UZS") or "UZS").upper(),
        description=f"{kalit} oyligi",
    )
    user.salary_confirmed_for = kalit

    # Oylik miqdori o'zgargan bo'lsa, mo'ljalni ham yangilaymiz —
    # kunlik limit shundan hisoblanadi.
    if amount != float(getattr(user, "monthly_income", 0) or 0):
        user.monthly_income = amount

    return tx


def spending_verdict(income: float, expense: float, daily_limit: float, days: int = 30) -> str:
    """
    O'tgan oy sarfini bir so'z bilan baholaydi: hisobot matni uchun.

    AI kerak emas — bu sof arifmetika.
    """
    kutilgan = daily_limit * days
    if kutilgan <= 0:
        return "nomalum"
    nisbat = expense / kutilgan
    if nisbat > 1.15:
        return "ko'p"
    if nisbat < 0.85:
        return "kam"
    return "barqaror"
