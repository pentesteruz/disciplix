import logging
import re
from pyrogram import Client, filters
from config import API_ID, API_HASH, SMS_BOT_USERNAME
from os import getenv
from database.engine import session_scope
from database.models import PremiumRequest, User, Settings
from sqlalchemy import select
from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.timezone import get_tashkent_time

def create_userbot():
    if not API_ID or not API_HASH:
        return None
    
    session_string = getenv("SESSION_STRING")
    
    if session_string:
        logging.info("Using Session String for Pyrogram...")
        userbot = Client(
            "my_account_memory",
            session_string=session_string,
            api_id=int(API_ID),
            api_hash=API_HASH,
            in_memory=True
        )
    else:
        logging.info("Using local session file for Pyrogram...")
        userbot = Client(
            "my_account",
            api_id=int(API_ID),
            api_hash=API_HASH,
            workdir="." 
        )

    # Arvoh Rejim (Ghost Mode) implementation
    async def enable_ghost_mode(client):
        try:
            # Hide online status
            from pyrogram.raw.functions.account import UpdateStatus
            from pyrogram.raw.types import InputStatusOffline
            await client.invoke(UpdateStatus(offline=True))
            logging.info("👻 Arvoh rejim yoqildi (Online status yashirildi)")
        except Exception as e:
            logging.error(f"Ghost mode error: {e}")

    # Patch userbot.start to enable ghost mode
    original_start = userbot.start
    async def ghost_start():
        await original_start()
        await enable_ghost_mode(userbot)
    userbot.start = ghost_start

    async def dynamic_sms_filter(_, __, message):
        if not message.from_user or not message.from_user.username:
            return False
        async with session_scope() as session:
            res_set = await session.execute(select(Settings).where(Settings.key == 'sms_bot_username'))
            setting_sms = res_set.scalars().first()
            current_sms_bot = setting_sms.value if setting_sms and setting_sms.value else SMS_BOT_USERNAME
        
        target = current_sms_bot.replace("@", "").lower() if current_sms_bot else ""
        return message.from_user.username.lower() == target

    sms_filter = filters.create(dynamic_sms_filter)

    @userbot.on_message(sms_filter & filters.text)
    async def handle_sms(client, message):
        text = message.text
        logging.info(f"📨 Yangi SMS xabar keldi:\n{text}\n")

        # Extract amount
        # Check for ➕ format first
        match = re.search(r"➕\s*([\d\s\.,]+)\s*(uzs|so'm|som|sum|сўм)", text.lower())
        if not match:
            # Fallback for old formats
            match = re.search(r"(?:balansingiz|tushdi|qabul qilindi)?.*?(\d[\d\s\.,]*)\s*(uzs|so'm|som|sum|сўм)", text.lower())

        if match:
            raw_amount = match.group(1).replace(" ", "")
            # Handle decimal points or commas before converting to avoid multiplying by 100
            if '.' in raw_amount:
                raw_amount = raw_amount.split('.')[0]
            elif ',' in raw_amount and len(raw_amount.split(',')[-1]) == 2:
                raw_amount = raw_amount.split(',')[0]
                
            amount_str = re.sub(r"[^\d]", "", raw_amount)
            try:
                amount = float(amount_str)
                logging.info(f"💰 SMS orqali summa aniqlandi: {amount}")
                await process_payment(amount)
            except ValueError:
                logging.info("❌ Summani ajratishda xatolik yuz berdi!")
        else:
            logging.info("ℹ️ Xabarda summa formati topilmadi.")

    return userbot

_aiogram_bot = None

def set_aiogram_bot(b):
    global _aiogram_bot
    _aiogram_bot = b

async def process_payment(amount: float):
    global _aiogram_bot
    async with session_scope() as session:
        now = get_tashkent_time()
        stmt = select(PremiumRequest).where(
            PremiumRequest.amount == amount,
            PremiumRequest.status == 'pending',
            PremiumRequest.expires_at > now
        ).with_for_update()
        res = await session.execute(stmt)
        request = res.scalars().first()
        
        if not request:
            logging.info(f"Kutilayotgan so'rovlar orasida {amount} summa topilmadi yoku muddati tugagan.")
            return

        request.status = "paid"
        
        # Grant Premium
        res_user = await session.execute(select(User).where(User.id == request.user_id))
        user = res_user.scalars().first()
        
        if user:
            days_to_add = 31 * request.months
            if user.premium_until and user.premium_until > now:
                user.premium_until = user.premium_until + timedelta(days=days_to_add)
            else:
                user.premium_until = now + timedelta(days=days_to_add)
            user.is_premium = True

            # Notify user
            if _aiogram_bot:
                try:
                    await _aiogram_bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"🎉 Tabriklaymiz! {amount:,.0f} UZS to'lovingiz avtomatik tasdiqlandi.\nSizga {request.months} oylik ({days_to_add} kun) Premium obuna taqdim etildi.\n\nMuddat: {user.premium_until.strftime('%d.%m.%Y gacha')}"
                    )
                except Exception as e:
                    logging.error(f"Failed to notify user: {e}")
                    
            # Auto-pay Referrer 10% Bonus
            if user.referred_by_id:
                res_referrer = await session.execute(select(User).where(User.id == user.referred_by_id))
                referrer = res_referrer.scalars().first()
                if referrer:
                    bonus_amount = request.amount * 0.10
                    referrer.bonus_balance = (referrer.bonus_balance or 0.0) + bonus_amount
                    
                    referrer_lang = referrer.language or 'uz'
                    bonus_msg = f"🎉 Siz taklif qilgan do'stingiz Premium obuna sotib oldi (Avto-tasdiqlandli)!\nSizning hisobingizga <b>{bonus_amount:,.0f} so'm</b> bonus qo'shildi!\n\nHozirgi balansingiz: {referrer.bonus_balance:,.0f} so'm." if referrer_lang == 'uz' else (f"🎉 Приглашенный вами друг купил Premium подписку!\nНа ваш счет добавлен бонус в размере <b>{bonus_amount:,.0f} сум</b>!\n\nВаш текущий баланс: {referrer.bonus_balance:,.0f} сум." if referrer_lang == 'ru' else f"🎉 Your invited friend bought a Premium subscription!\nA bonus of <b>{bonus_amount:,.0f} UZS</b> has been added to your account!\n\nYour current balance: {referrer.bonus_balance:,.0f} UZS.")
                    
                    if _aiogram_bot:
                        try:
                            await _aiogram_bot.send_message(chat_id=referrer.telegram_id, text=bonus_msg, parse_mode="HTML")
                        except:
                            pass
        
        await session.commit()
        
        # Edit channel message if possible
        if _aiogram_bot and request.message_id:
            try:
                res_set = await session.execute(select(Settings).where(Settings.key == 'premium_channel_id'))
                setting = res_set.scalars().first()
                channel_id = setting.value if setting and setting.value else getenv("premium_channel_id")
                
                if channel_id:
                    # Remove buttons and append "Avtomatik Tasdiqlandi"
                    # We can't easily fetch the original text without complex methods, but we can edit the markup to None 
                    # Actually, Pyrogram or Aiogram might need the exact text to edit it correctly. 
                    # If we don't have text, editing reply_markup=None removes buttons.
                    await _aiogram_bot.edit_message_reply_markup(
                        chat_id=channel_id,
                        message_id=request.message_id,
                        reply_markup=None
                    )
            except Exception as e:
                logging.error(f"Failed to update channel message: {e}")
                
