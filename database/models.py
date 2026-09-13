from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, DateTime, BigInteger, Numeric, func
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs
from datetime import datetime
from database.encryption import SmartEncryptedString, SmartEncryptedText
from utils.timezone import get_tashkent_time

class Base(AsyncAttrs, DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    name = Column(SmartEncryptedString)
    daily_limit = Column(Numeric(16, 2, asdecimal=False), default=0.0)
    balance = Column(Numeric(16, 2, asdecimal=False), default=0.0)
    is_premium = Column(Boolean, default=False)
    
    # Keeping these for logic continuity
    registration_mode = Column(String, default="quick") 
    fixed_expenses_total = Column(Numeric(16, 2, asdecimal=False), default=0.0)
    daily_income = Column(Numeric(16, 2, asdecimal=False), default=0.0) 
    monthly_income = Column(Numeric(16, 2, asdecimal=False), default=0.0) 
    language = Column(String, default="uz")    
    user_state = Column(String, default="onboarding")
    base_currency = Column(String, default="UZS")
    active_currencies = Column(String, default="UZS")
    phone_number = Column(SmartEncryptedString, nullable=True)
    warning_level = Column(Integer, default=0)
    is_frozen = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    frozen_until = Column(DateTime, nullable=True) # Expiration date for temp freezes
    fraud_strikes = Column(Integer, default=0) # Counts fake premium requests
    accepted_policy = Column(Boolean, default=False) # Must accept before using bot
    surname = Column(SmartEncryptedString, nullable=True) # Logic uses it
    premium_until = Column(DateTime, nullable=True)
    referral_code = Column(String, unique=True, nullable=True)
    referred_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    bonus_balance = Column(Numeric(16, 2, asdecimal=False), default=0.0)
    last_active = Column(DateTime, default=get_tashkent_time)
    created_at = Column(DateTime, default=get_tashkent_time)

    # --- Oylik oqimi ---
    # Oylik tushadigan kun (1-31). Oyda bunday kun bo'lmasa (masalan 31-fevral),
    # oyning oxirgi kuniga tushiriladi.
    salary_day = Column(Integer, nullable=True)
    # Oxirgi tasdiqlangan oylik qaysi oy uchun edi: "YYYY-MM".
    # Bir oy uchun ikki marta kirim yozilmasligini ta'minlaydi.
    salary_confirmed_for = Column(String, nullable=True)

    # Kunlik limitdan ortib qolgan va foydalanuvchi "tejadim" deb belgilagan summa.
    # DIQQAT: bu haqiqiy pul emas — ko'rsatkich. Pul foydalanuvchining o'zida.
    saved_surplus = Column(Numeric(16, 2, asdecimal=False), default=0.0)
    # Ortiqcha pul so'ralgan oxirgi kun (kuniga bir marta so'rash uchun).
    surplus_asked_on = Column(DateTime, nullable=True)

    dreams = relationship("Dream", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    life_schedule = relationship("LifeSchedule", back_populates="user", cascade="all, delete-orphan")
    detailed_expenses = relationship("DetailedExpenses", back_populates="user", cascade="all, delete-orphan")
    dream_progress = relationship("DreamProgress", back_populates="user", cascade="all, delete-orphan")
    debts = relationship("Debt", back_populates="user", cascade="all, delete-orphan")
    premium_requests = relationship("PremiumRequest", back_populates="user", cascade="all, delete-orphan")
    currency_conversion_logs = relationship("CurrencyConversionLog", cascade="all, delete-orphan", foreign_keys="[CurrencyConversionLog.user_id]")

    # finances relationship added dynamically below if needed or just replace usage

class Dream(Base):
    __tablename__ = "dreams"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    dream_name = Column(SmartEncryptedString, nullable=False)
    total_amount = Column(Numeric(16, 2, asdecimal=False), nullable=False)
    saved_amount = Column(Numeric(16, 2, asdecimal=False), default=0.0) # Renamed from current_amount
    daily_limit_target = Column(Numeric(16, 2, asdecimal=False), default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=get_tashkent_time)
    extra_savings = Column(Numeric(16, 2, asdecimal=False), default=0.0) # Logic needs it
    deadline = Column(DateTime, nullable=True) # Logic needs it
    icon = Column(String, nullable=True)
    icon_bg = Column(String, nullable=True)
    icon_color = Column(String, nullable=True)
    cancel_requested = Column(Boolean, default=False)

    user = relationship("User", back_populates="dreams")
    progress_history = relationship("DreamProgress", back_populates="dream", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(SmartEncryptedString, nullable=False)
    due_date = Column(DateTime, nullable=True)
    is_completed = Column(Boolean, default=False)
    is_notified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=get_tashkent_time)
    is_ai_generated = Column(Boolean, default=False)
    description = Column(SmartEncryptedText, nullable=True)

    user = relationship("User", back_populates="tasks")

class Transaction(Base):
    """
    Pul harakatining yagona jadvali.

    Ilgari har bir xarajat `finances` va `transactions` ga ikki marta yozilardi:
    `finances` boy (description, ai_advice) edi, `transactions` esa kambag'al,
    va turli endpointlar turlichasini o'qirdi. Endi manba shu jadval.
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Numeric(16, 2, asdecimal=False), nullable=False)
    currency = Column(String, default="UZS")
    category = Column(String)
    timestamp = Column(DateTime, default=get_tashkent_time)
    type = Column(String, default="expense")
    description = Column(SmartEncryptedString, nullable=True)
    ai_advice = Column(SmartEncryptedText, nullable=True)
    due_date = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="transactions")

class LifeSchedule(Base):
    __tablename__ = "life_schedule"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    activity = Column(SmartEncryptedString, nullable=False)
    time = Column(String, nullable=False)
    frequency = Column(String, default="daily") 
    day_of_week = Column(Integer, nullable=True) 
    day_of_month = Column(Integer, nullable=True) 

    user = relationship("User", back_populates="life_schedule")

class DetailedExpenses(Base):
    __tablename__ = "detailed_expenses"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(SmartEncryptedString, nullable=False)
    amount = Column(Numeric(16, 2, asdecimal=False), nullable=False)
    due_date = Column(String, nullable=True) 

    user = relationship("User", back_populates="detailed_expenses")

class DreamProgress(Base):
    __tablename__ = "dream_progress"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    dream_id = Column(Integer, ForeignKey("dreams.id"))
    date = Column(DateTime, default=get_tashkent_time)
    amount = Column(Numeric(16, 2, asdecimal=False), nullable=False)
    is_paid = Column(Boolean, default=True) # True = Tashladim, False = skipped? Or just tracking payments.

    user = relationship("User", back_populates="dream_progress")
    dream = relationship("Dream", back_populates="progress_history")

# ESKIRGAN: `Transaction` bilan almashtirilgan. Yangi kod bu modelga yozmasligi
# va undan o'qimasligi kerak — u faqat migratsiya tekshirilgunicha turibdi.
# Backfill: scripts/consolidate_transactions.py
class Finance(Base):
    __tablename__ = "finances"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Numeric(16, 2, asdecimal=False), nullable=False)
    currency = Column(String, default="UZS")
    category = Column(String)
    item_type = Column(String) 
    description = Column(String)
    entry_time = Column(DateTime)
    ai_advice = Column(String)
    due_date = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="finances")

class Debt(Base):
    __tablename__ = "debts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    # Qarzdorning ismi — shaxsiy ma'lumot, card_number kabi shifrlanadi.
    person = Column(SmartEncryptedString, nullable=False)
    amount = Column(Numeric(16, 2, asdecimal=False), nullable=False)
    type = Column(String, default="loaned") # loaned (berdim) yoki borrowed (oldim)
    due_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=get_tashkent_time)

    user = relationship("User", back_populates="debts")

# Add relationship to User model
def _update_user_model():
    User.finances = relationship("Finance", back_populates="user")
_update_user_model()

class Settings(Base):
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, nullable=True)
    description = Column(String, nullable=True)

class PromoCode(Base):
    __tablename__ = "promo_codes"
    
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    days = Column(Integer, nullable=False, default=1)
    max_uses = Column(Integer, nullable=False, default=1)
    current_uses = Column(Integer, default=0)
    created_at = Column(DateTime, default=get_tashkent_time)

class PremiumRequest(Base):
    __tablename__ = "premium_requests"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(16, 2, asdecimal=False), nullable=False)
    months = Column(Integer, nullable=False)
    status = Column(String, default="pending") # pending, paid, rejected, expired
    message_id = Column(Integer, nullable=True) # ID of the message in the logging channel
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=get_tashkent_time)

    user = relationship("User", back_populates="premium_requests")

class CurrencyConversionLog(Base):
    """
    Bazaviy valyuta almashtirilganda summalar joyida qayta yoziladi. Kurs keyin
    o'zgargani uchun teskari konversiya asl qiymatni qaytarmaydi — shuning uchun
    eski qiymatlar va ishlatilgan kurs shu yerda saqlanadi.
    """
    __tablename__ = "currency_conversion_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    from_currency = Column(String, nullable=False)
    to_currency = Column(String, nullable=False)
    rate = Column(Numeric(20, 8, asdecimal=False), nullable=False)
    snapshot = Column(SmartEncryptedText, nullable=False)  # JSON: o'zgarishdan oldingi summalar
    created_at = Column(DateTime, default=get_tashkent_time)

    user = relationship("User", foreign_keys=[user_id], overlaps="currency_conversion_logs")


class WithdrawalRequest(Base):
    __tablename__ = "withdrawal_requests"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(16, 2, asdecimal=False), nullable=False)
    card_number = Column(SmartEncryptedString, nullable=False)
    status = Column(String, default="pending") # pending, paid, rejected
    message_id = Column(Integer, nullable=True) # ID of the message in the logging channel
    created_at = Column(DateTime, default=get_tashkent_time)

    user = relationship("User", foreign_keys=[user_id])
