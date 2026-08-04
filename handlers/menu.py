from aiogram import Router, F, types
import logging
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from database.engine import session_scope
from database.models import Settings, User, Task, Finance, PromoCode, Dream, DreamProgress, PremiumRequest, WithdrawalRequest
from datetime import datetime, timedelta
import random
from os import getenv
from utils.i18n import _, get_all_translations
from config import ADMIN_IDS, WEBAPP_URL, SUPPORT_GROUP_ID as FALLBACK_SUPPORT_ID
from aiogram.filters import Command
from utils.timezone import get_tashkent_time

router = Router()

class SupportState(StatesGroup):
    waiting_for_question = State()

class DelUserState(StatesGroup):
    waiting_for_confirm = State()

class AdminLoginState(StatesGroup):
    waiting_for_password = State()

class WithdrawalState(StatesGroup):
    waiting_for_card = State()
    waiting_for_amount = State()

async def get_support_group_id() -> int:
    async with session_scope() as session:
        res = await session.execute(select(Settings).where(Settings.key == 'support_group_id'))
        setting = res.scalars().first()
        if setting and setting.value:
            try:
                return int(setting.value)
            except ValueError:
                pass
    return FALLBACK_SUPPORT_ID

async def is_support_group(message: types.Message) -> bool:
    support_id = await get_support_group_id()
    return message.chat.id == support_id

@router.message(F.text.in_(get_all_translations('support_btn')))
async def support_menu(message: types.Message, state: FSMContext):
    telegram_id = message.from_user.id
    async with session_scope() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = res.scalars().first()
        lang = (user.language or 'uz') if user else 'uz'
    
        await state.set_state(SupportState.waiting_for_question)
        
        prompt = _('support_prompt', lang, default="📝 Savol yoki taklifingizni yozib qoldiring. Adminlarimiz tez orada sizga javob berishadi!\n\nBekor qilish uchun /cancel yozing.")
        await message.answer(prompt)

@router.message(SupportState.waiting_for_question)
async def process_support_question(message: types.Message, state: FSMContext):
    if message.text == '/cancel':
        await state.clear()
        from utils.i18n import _
        lang = 'uz'
        # user lang fallback could be added but let's default to uz for simple cancel
        await message.answer(_('support_cancelled', lang))
        return

    support_id = await get_support_group_id()
    text = f"📩 #ID_{message.from_user.id}\nKimdan: {message.from_user.full_name}\n\n"
    
    try:
        if message.text:
            text += message.text
            if support_id:
                await message.bot.send_message(chat_id=support_id, text=text)
        elif message.photo:
            if support_id:
                await message.bot.send_photo(chat_id=support_id, photo=message.photo[-1].file_id, caption=text + (message.caption or ""))
        elif message.video:
            if support_id:
                await message.bot.send_video(chat_id=support_id, video=message.video.file_id, caption=text + (message.caption or ""))
        else:
            from utils.i18n import _
            await message.answer(_('support_invalid_format', 'uz'))
            return

        await state.clear()
        
        if support_id == 0:
            from utils.i18n import _
            await message.answer(_('support_no_group_set', 'uz'))
        else:
            from utils.i18n import _
            await message.answer(_('support_sent_success', 'uz'))
    except Exception as e:
        await state.clear()
        logging.error(f"Error forwarding support message to group {support_id}: {e}")
        from utils.i18n import _
        await message.answer(_('support_send_error', 'uz'))

@router.message(is_support_group)
async def admin_group_reply(message: types.Message):
    if message.reply_to_message and message.reply_to_message.from_user.id == message.bot.id:
        original_text = message.reply_to_message.text or message.reply_to_message.caption
        if original_text and "#ID_" in original_text:
            first_line = original_text.split('\n')[0]
            try:
                user_id_str = first_line.split("#ID_")[1].split()[0]
                user_id = int(user_id_str)
                
                from utils.i18n import _
                reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=_('support_reask_btn', 'uz'), callback_data="reask_support")]
                ])
                if message.text:
                    await message.bot.send_message(chat_id=user_id, text=_('support_reply_from_admin', 'uz', text=message.text), reply_markup=reply_markup)
                else:
                    support_id = await get_support_group_id()
                    await message.bot.copy_message(chat_id=user_id, from_chat_id=support_id, message_id=message.message_id, reply_markup=reply_markup)
            except Exception as e:
                logging.error(f"Error sending reply to user: {e}")

@router.callback_query(F.data == "reask_support")
async def reask_support_callback(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(SupportState.waiting_for_question)
    from utils.i18n import _
    await call.message.answer(_('support_reask_prompt', 'uz'))
    await call.answer()

@router.message(Command("info"))
@router.message(F.text.in_(get_all_translations('info_btn')))
async def info_menu(message: types.Message):
    telegram_id = message.from_user.id
    async with session_scope() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = res.scalars().first()
        lang = (user.language or 'uz') if user else 'uz'
        
        # Get dynamic info text and video link from Settings
        info_res = await session.execute(select(Settings).where(Settings.key == 'info_text'))
        info_setting = info_res.scalars().first()
        
        video_res = await session.execute(select(Settings).where(Settings.key == 'info_video_id'))
        video_setting = video_res.scalars().first()
        
        # Determine the text to show
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
        
        # Prepare keyboard (No onboarding buttons here)
        buttons = [[InlineKeyboardButton(text=_( 'support_btn', lang), callback_data="reask_support")]]
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        if video_id:
            try:
                await message.answer_video(video=video_id, caption=text, reply_markup=markup, parse_mode="HTML")
            except Exception:
                fallback_text = text if text else _("info_welcome", lang)
                await message.answer(fallback_text, reply_markup=markup, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=markup, parse_mode="HTML")

@router.message(F.text.in_(get_all_translations('referal_btn')))
async def referal_menu(message: types.Message):
    telegram_id = message.from_user.id
    async with session_scope() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = res.scalars().first()
        if user:
            if not user.referral_code:
                import random, string
                user.referral_code = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                await session.commit()
            bot_info = await message.bot.get_me()
            ref_link = f"https://t.me/{bot_info.username}?start={user.referral_code}"
            
            count_res = await session.execute(select(User).where(User.referred_by_id == user.id))
            referred_users = count_res.scalars().all()
            
            # Fetch settings
            ref_count_res = await session.execute(select(Settings).where(Settings.key == 'ref_count'))
            ref_count_setting = ref_count_res.scalars().first()
            ref_req = int(ref_count_setting.value) if ref_count_setting and ref_count_setting.value else 4
            
            ref_days_res = await session.execute(select(Settings).where(Settings.key == 'ref_days'))
            ref_days_setting = ref_days_res.scalars().first()
            ref_days = int(ref_days_setting.value) if ref_days_setting and ref_days_setting.value else 3
            
            lang = user.language or 'uz'
            
            text = f"🤝 <b>Referal tizimi</b>\n\n" if lang == 'uz' else (f"🤝 <b>Реферальная система</b>\n\n" if lang == 'ru' else f"🤝 <b>Referral system</b>\n\n")
            text += f"Sizning taklif havolangiz:\n{ref_link}\n\n" if lang == 'uz' else (f"Ваша пригласительная ссылка:\n{ref_link}\n\n" if lang == 'ru' else f"Your invite link:\n{ref_link}\n\n")
            
            bonus_text = _('referal_promo', lang, req=ref_req, days=ref_days, default=f"Boshqalarni taklif qiling. Agar ular premium sotib olishsa, siz 10% bonus olasiz! Undan tashqari siz {ref_req} ta odam taklif qilsangiz {ref_days} kun premium bonusiga ega bo'lasiz.\n\n")
            text += bonus_text
            
            friends_text = f"Taklif qilingan do'stlar soni: {len(referred_users)}\n" if lang == 'uz' else (f"Количество приглашенных друзей: {len(referred_users)}\n" if lang == 'ru' else f"Invited friends: {len(referred_users)}\n")
            text += friends_text
            
            bal_text = f"Sizning bonus balansingiz: {user.bonus_balance:,.0f} so'm" if lang == 'uz' else (f"Ваш бонусный баланс: {user.bonus_balance:,.0f} сум" if lang == 'ru' else f"Your bonus balance: {user.bonus_balance:,.0f} UZS")
            text += bal_text
            
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="💳 Pul yechish" if lang == 'uz' else ("💳 Вывод средств" if lang == 'ru' else "💳 Withdraw"), callback_data="referral_withdraw"),
                    InlineKeyboardButton(text="🎁 Promokod" if lang == 'uz' else ("🎁 Промокод" if lang == 'ru' else "🎁 Promo code"), callback_data="referral_promo")
                ]
            ])
            
            await message.answer(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)

@router.message(F.text.in_(get_all_translations('premium_btn')))
async def premium_menu(message: types.Message):
    telegram_id = message.from_user.id
    async with session_scope() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = res.scalars().first()
        if user:
            from utils.i18n import _
            lang = user.language or 'uz'
            text = _('premium_menu_title', lang)
            text += _('premium_menu_desc', lang)
            
            now = get_tashkent_time()
            if user.premium_until and user.premium_until > now:
                days_left = (user.premium_until - now).days
                text += _('premium_days_left', lang, days=days_left)
            else:
                text += _('premium_not_active', lang)
            
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=_('premium_buy_btn', lang), callback_data="buy_premium")]
            ])
            await message.answer(text, parse_mode="HTML", reply_markup=markup)

@router.callback_query(F.data == "buy_premium")
async def buy_premium_callback(call: types.CallbackQuery):
    async with session_scope() as session:
        res_1 = await session.execute(select(Settings).where(Settings.key == 'premium_price_1'))
        s_1 = res_1.scalars().first()
        price_1 = int(s_1.value) if s_1 and s_1.value.isdigit() else 20000

        res_3 = await session.execute(select(Settings).where(Settings.key == 'premium_price_3'))
        s_3 = res_3.scalars().first()
        price_3 = int(s_3.value) if s_3 and s_3.value.isdigit() else 50000

        res_6 = await session.execute(select(Settings).where(Settings.key == 'premium_price_6'))
        s_6 = res_6.scalars().first()
        price_6 = int(s_6.value) if s_6 and s_6.value.isdigit() else 90000

        res_12 = await session.execute(select(Settings).where(Settings.key == 'premium_price_12'))
        s_12 = res_12.scalars().first()
        price_12 = int(s_12.value) if s_12 and s_12.value.isdigit() else 150000

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"1 oy - {price_1:,} UZS", callback_data="buy_premium_1")],
        [InlineKeyboardButton(text=f"3 oy - {price_3:,} UZS", callback_data="buy_premium_3")],
        [InlineKeyboardButton(text=f"6 oy - {price_6:,} UZS", callback_data="buy_premium_6")],
        [InlineKeyboardButton(text=f"12 oy - {price_12:,} UZS", callback_data="buy_premium_12")]
    ])
    from utils.i18n import _
    await call.message.edit_text(_('premium_buy_prompt', 'uz'), reply_markup=markup)
    await call.answer()

@router.callback_query(F.data.startswith("buy_premium_"))
async def process_premium_payment(call: types.CallbackQuery):
    months_str = call.data.split("_")[-1]
    try:
        months = int(months_str)
    except:
        await call.answer("Xatolik bo'ldi.", show_alert=True)
        return
        
    async with session_scope() as session:
        res_price = await session.execute(select(Settings).where(Settings.key == f'premium_price_{months}'))
        s_price = res_price.scalars().first()
        defaults = {1: 20000, 3: 50000, 6: 90000, 12: 150000}
        base_price = int(s_price.value) if s_price and s_price.value.isdigit() else defaults.get(months)
        
        if not base_price:
            await call.answer("Xatolik bo'ldi.", show_alert=True)
            return
        now = get_tashkent_time()
        stmt = select(PremiumRequest.amount).where(PremiumRequest.status == 'pending', PremiumRequest.expires_at > now)
        res = await session.execute(stmt)
        used_amounts = set(res.scalars().all())
        
        amount_to_pay = None
        amounts_range = list(range(base_price - 50, base_price + 51))
        random.shuffle(amounts_range)
        for amt in amounts_range:
            if amt not in used_amounts:
                amount_to_pay = float(amt)
                break
                
        if not amount_to_pay:
            await call.answer("Hozirda barcha to'lov yo'laklari band. Iltimos 15 daqiqadan so'ng qayta urinib ko'ring.", show_alert=True)
            return
            
        res_set = await session.execute(select(Settings).where(Settings.key == 'premium_channel_id'))
        setting = res_set.scalars().first()
        channel_id = setting.value if setting and setting.value else getenv("premium_channel_id")
        
        if not channel_id:
            await call.answer("To'lov tizimlari yoki kanal hali ulanmagan!", show_alert=True)
            return
            
        expires = now + timedelta(minutes=15)
        
        user_res = await session.execute(select(User).where(User.telegram_id == call.from_user.id))
        db_user = user_res.scalars().first()
        if not db_user:
            await call.answer("Foydalanuvchi tizimda topilmadi.", show_alert=True)
            return
            
        new_request = PremiumRequest(
            user_id=db_user.id,
            amount=amount_to_pay,
            months=months,
            status="pending",
            expires_at=expires
        )
        session.add(new_request)
        await session.flush()
        
        log_text = (
            f"🔔 <b>Yangi Premium To'lov So'rovi</b>\n\n"
            f"👤 Foydalanuvchi: <a href='tg://user?id={call.from_user.id}'>{call.from_user.full_name}</a>\n"
            f"🆔 ID: <code>{call.from_user.id}</code>\n"
            f"📅 Muddat: {months} oy\n"
            f"💰 Asosiy narx: {base_price:,.0f} UZS\n"
            f"⚠️ Kutilayotgan summa: <b>{amount_to_pay:,.0f} UZS</b>\n"
            f"⏳ Tugash vaqti: {expires.strftime('%H:%M')}"
        )
        
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Qabul qilish (Tasdiqlash)", callback_data=f"confirm_premium_{new_request.id}")],
            [InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_premium_{new_request.id}")]
        ])
        
        try:
            msg = await call.message.bot.send_message(chat_id=channel_id, text=log_text, reply_markup=markup, parse_mode="HTML")
            new_request.message_id = msg.message_id
            await session.commit()
            
            res_card = await session.execute(select(Settings).where(Settings.key == 'card_number'))
            setting_card = res_card.scalars().first()
            card_number_full = setting_card.value if setting_card and setting_card.value else "8600 0000 0000 0000 (Eshmatov Toshmat)"
            
            parts = card_number_full.split('(', 1)
            card_num_only = parts[0].strip()
            card_name_only = f"({parts[1]}" if len(parts) > 1 else ""

            user_text = (
                f"💳 <b>To'lov qilish</b>\n\n"
                f"💳 <b>Karta raqami:</b> <code>{card_num_only}</code> {card_name_only}\n\n"
                f"⚠️ <b>DIQQAT:</b> Premium olish uchun aynan <b>{amount_to_pay:,.0f} UZS</b> o'tkazishingiz shart. "
                f"Agar boshqa summa tashlasangiz, to'lov qabul qilinmaydi!\n\n"
                f"Sizda to'lovni tasdiqlash uchun <b>15 daqiqa</b> vaqt bor."
            )
            await call.message.edit_text(user_text, parse_mode="HTML")
            
        except Exception as e:
            await session.rollback()
            logging.error(f"Error sending log message: {e}")
            await call.answer("Xatolik yuz berdi. Ehtimol to'lov kanali noto'g'ri sozlangan.", show_alert=True)
            return

@router.callback_query(F.data.startswith("confirm_premium_"))
async def handle_confirm_premium(call: types.CallbackQuery):
    # Only admins can confirm payments
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    req_id = int(call.data.split("_")[-1])
    async with session_scope() as session:
        request = await session.get(PremiumRequest, req_id)
        if not request:
            await call.answer("So'rov topilmadi.", show_alert=True)
            return
            
        if request.status == "paid":
            await call.answer("Bu so'rov allaqachon tasdiqlangan.", show_alert=True)
            return
            
        # Optional check if we want admin only, but channel is admin-only anyway
        
        request.status = "paid"
        
        # Grant premium
        result = await session.execute(select(User).where(User.id == request.user_id))
        user = result.scalars().first()
        if user:
            now = get_tashkent_time()
            days_to_add = 31 * request.months
            if user.premium_until and user.premium_until > now:
                user.premium_until = user.premium_until + timedelta(days=days_to_add)
            else:
                user.premium_until = now + timedelta(days=days_to_add)
            user.is_premium = True
            
            try:
                await call.message.bot.send_message(
                    chat_id=user.telegram_id, 
                    text=f"🎉 Tabriklaymiz! {request.amount:,.0f} UZS to'lovingiz tasdiqlandi. Sizga {request.months} oylik ({days_to_add} kun) Premium obuna taqdim etildi.\n\nMuddat: {user.premium_until.strftime('%d.%m.%Y gacha')}"
                )
            except:
                pass
                
        # Grant premium 10% bonus to referrer if exists
        if user and user.referred_by_id:
            ref_res = await session.execute(select(User).where(User.id == user.referred_by_id))
            referrer = ref_res.scalars().first()
            if referrer:
                bonus_amount = request.amount * 0.10
                referrer.bonus_balance = (referrer.bonus_balance or 0.0) + bonus_amount
                
                referrer_lang = referrer.language or 'uz'
                bonus_msg = f"🎉 Siz taklif qilgan do'stingiz Premium obuna sotib oldi!\nSizning hisobingizga <b>{bonus_amount:,.0f} so'm</b> bonus qo'shildi!\n\nHozirgi balansingiz: {referrer.bonus_balance:,.0f} so'm." if referrer_lang == 'uz' else (f"🎉 Приглашенный вами друг купил Premium подписку!\nНа ваш счет добавлен бонус в размере <b>{bonus_amount:,.0f} сум</b>!\n\nВаш текущий баланс: {referrer.bonus_balance:,.0f} сум." if referrer_lang == 'ru' else f"🎉 Your invited friend bought a Premium subscription!\nA bonus of <b>{bonus_amount:,.0f} UZS</b> has been added to your account!\n\nYour current balance: {referrer.bonus_balance:,.0f} UZS.")
                
                try:
                    await call.message.bot.send_message(chat_id=referrer.telegram_id, text=bonus_msg, parse_mode="HTML")
                except:
                    pass

        await session.commit()
        
        # update message
        try:
            await call.message.edit_text(call.message.html_text + "\n\n✅ <b>Qo'lda Tasdiqlandi</b>", parse_mode="HTML")
        except:
            pass
            
        await call.answer("Tasdiqlandi!")

@router.callback_query(F.data.startswith("reject_premium_"))
async def handle_reject_premium(call: types.CallbackQuery):
    # Only admins can reject payments
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    req_id = int(call.data.split("_")[-1])
    async with session_scope() as session:
        request = await session.get(PremiumRequest, req_id)
        if not request:
            await call.answer("So'rov topilmadi.", show_alert=True)
            return
            
        if request.status == "paid":
            await call.answer("Bu so'rov tasdiqlangan, rad etib bo'lmaydi.", show_alert=True)
            return
            
        request.status = "rejected"
        await session.commit()
        
        result = await session.execute(select(User).where(User.id == request.user_id))
        user = result.scalars().first()
        if user:
            try:
                await call.message.bot.send_message(
                    chat_id=user.telegram_id, 
                    text=f"❌ {request.amount:,.0f} UZS to'lovingiz rad etildi. Agar e'tirozingiz bo'lsa adminga murojaat qiling."
                )
            except:
                pass
                
        # Update message with "Rad etildi" but retain "Tasdiqlash" button
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Qabul qilish (Tasdiqlash)", callback_data=f"confirm_premium_{req_id}")]
        ])
        try:
            await call.message.edit_text(call.message.html_text + "\n\n❌ <b>Rad etildi</b>", parse_mode="HTML", reply_markup=markup)
        except:
            pass
            
        await call.answer("Rad etildi!")

import os

ADMIN_SECRET_PASSWORD = os.getenv("ADMIN_PASSWORD", "salomdedimadmingaammosalomolmadi") # Tavsiya: .env da o'zgartiring!

@router.message(Command("salomadmin"))
async def hidden_admin_command(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        await message.delete()
    except:
        pass
    await state.set_state(AdminLoginState.waiting_for_password)
    await message.answer("\U0001f510 Parolni kiriting:")

@router.message(AdminLoginState.waiting_for_password)
async def process_admin_password(message: types.Message, state: FSMContext):
    entered = (message.text or "").strip()
    await state.clear()  # Only 1 attempt allowed - clear immediately
    if entered == ADMIN_SECRET_PASSWORD:
        admin_url = (WEBAPP_URL or "").rstrip("/") + "/mng-x89b2k1q?v=2"  # ADMIN PANEL URL
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="\U0001f6e0 Admin Panel", web_app=WebAppInfo(url=admin_url))]
        ])
        await message.answer("\u2705 Xush kelibsiz, Admin!", reply_markup=markup)
    else:
        await message.answer(
            "Kechirasiz, men bu so\u2019rovingizni tushunmadim. "
            "Iltimos, boshqa savol bering yoki mendan yordam so\u2019rang \U0001f60a"
        )

from datetime import timedelta

@router.message(Command("addprem"))
async def add_premium_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    args = message.text.split()
    if len(args) != 3:
        await message.answer("Xato format. Foydalanish: /addprem [telegram_id] [oylar_soni]\nMasalan: /addprem 123456789 1")
        return
        
    try:
        target_id = int(args[1])
        months = int(args[2])
    except ValueError:
        await message.answer("ID yoki oylar soni raqam bo'lishi kerak.")
        return
        
    async with session_scope() as session:
        res = await session.execute(select(User).where(User.telegram_id == target_id))
        user = res.scalars().first()
        
        if not user:
            await message.answer("Bunday foydalanuvchi topilmadi.")
            return
            
        now = get_tashkent_time()
        days_to_add = 31 * months
        if user.premium_until and user.premium_until > now:
            user.premium_until = user.premium_until + timedelta(days=days_to_add)
        else:
            user.premium_until = now + timedelta(days=days_to_add)
            
        user.is_premium = True
        
        # Admin Added Premium Referrer 10% Bonus
        if user.referred_by_id:
            res_referrer = await session.execute(select(User).where(User.id == user.referred_by_id))
            referrer = res_referrer.scalars().first()
            if referrer:
                prices = {1: 20000, 3: 50000, 6: 90000, 12: 150000}
                base_price = prices.get(months, 20000 * months)
                bonus_amount = base_price * 0.10
                referrer.bonus_balance = (referrer.bonus_balance or 0.0) + bonus_amount
                
                referrer_lang = referrer.language or 'uz'
                bonus_msg = f"🎉 Siz taklif qilgan do'stingizga Premium obuna (Admin tomondan) taqdim etildi!\nSizning hisobingizga <b>{bonus_amount:,.0f} so'm</b> bonus qo'shildi!\n\nHozirgi balansingiz: {referrer.bonus_balance:,.0f} so'm." if referrer_lang == 'uz' else (f"🎉 Приглашенный вами друг получил Premium подписку!\nНа ваш счет добавлен бонус в размере <b>{bonus_amount:,.0f} сум</b>!\n\nВаш текущий баланс: {referrer.bonus_balance:,.0f} сум." if referrer_lang == 'ru' else f"🎉 Your invited friend received a Premium subscription!\nA bonus of <b>{bonus_amount:,.0f} UZS</b> has been added to your account!\n\nYour current balance: {referrer.bonus_balance:,.0f} UZS.")
                
                try:
                    await message.bot.send_message(chat_id=referrer.telegram_id, text=bonus_msg, parse_mode="HTML")
                except:
                    pass
                    
        await session.commit()
        
        await message.answer(f"✅ Foydalanuvchi ({target_id}) premium obunasi {months} oyga ({days_to_add} kunga) uzaytirildi.\nYangi muddat: {user.premium_until.strftime('%Y-%m-%d %H:%M')}")
        
        try:
            await message.bot.send_message(
                chat_id=target_id, 
                text=f"🎉 Tabriklaymiz! Sizga admin tomonidan {months} oylik ({days_to_add} kun) Premium obuna taqdim etildi.\n\nMuddat: {user.premium_until.strftime('%d.%m.%Y gacha')}"
            )
        except Exception as e:
            await message.answer(f"Foydalanuvchiga xabar yuborishda xatolik: qulflangan bo'lishi mumkin.")



@router.message(Command("deluser"))
async def deluser_command(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Xato format. Foydalanish: /deluser [telegram_id yoki user_id]")
        return
        
    target_id_str = args[1]
    
    async with session_scope() as session:
        try:
            tid = int(target_id_str)
        except ValueError:
            await message.answer("ID raqam bo'lishi kerak.")
            return

        if tid > 2147483647:
            res = await session.execute(select(User).where(User.telegram_id == tid))
        else:
            res = await session.execute(select(User).where((User.telegram_id == tid) | (User.id == tid)))
        user = res.scalars().first()
        
        if not user:
            await message.answer("Bunday foydalanuvchi topilmadi.")
            return

        await state.update_data(target_user_id=user.id)
        await state.set_state(DelUserState.waiting_for_confirm)
        
        caption = f"Haqiqatan ham ushbu foydalanuvchini va uning BARCHA ma'lumotlarini o'chirishni xohlaysizmi? (y/n)\n\nID: {user.id}\nTelegram ID: {user.telegram_id}\nIsm: {user.name}"
        await message.answer(caption)

@router.message(DelUserState.waiting_for_confirm)
async def process_deluser_confirm(message: types.Message, state: FSMContext):
    if message.text.lower() != 'y':
        await state.clear()
        await message.answer("Bekor qilindi.")
        return
        
    data = await state.get_data()
    user_id = data.get("target_user_id")
    if not user_id:
        await state.clear()
        await message.answer("Xatolik reytingda.")
        return

    from database.models import User, Task, Dream, Transaction, LifeSchedule, DetailedExpenses, DreamProgress, Finance, Debt, PremiumRequest
    from sqlalchemy import delete, update

    async with session_scope() as session:
        # First unlink referrals to avoid FK violation
        await session.execute(
            update(User).where(User.referred_by_id == user_id).values(referred_by_id=None)
        )
        
        # Delete dependent tables
        await session.execute(delete(Task).where(Task.user_id == user_id))
        await session.execute(delete(DreamProgress).where(DreamProgress.user_id == user_id))
        await session.execute(delete(Dream).where(Dream.user_id == user_id))
        await session.execute(delete(Transaction).where(Transaction.user_id == user_id))
        await session.execute(delete(LifeSchedule).where(LifeSchedule.user_id == user_id))
        await session.execute(delete(DetailedExpenses).where(DetailedExpenses.user_id == user_id))
        await session.execute(delete(Finance).where(Finance.user_id == user_id))
        await session.execute(delete(Debt).where(Debt.user_id == user_id))
        await session.execute(delete(PremiumRequest).where(PremiumRequest.user_id == user_id))
        
        # Finally delete user
        await session.execute(delete(User).where(User.id == user_id))
        
        await session.commit()
        await state.clear()
        await message.answer(f"✅ Foydalanuvchi ({user_id}) va uning barcha ma'lumotlari muvaffaqiyatli o'chirildi.")

@router.callback_query(F.data == "referral_withdraw")
async def process_referral_withdraw(call: types.CallbackQuery, state: FSMContext):
    async with session_scope() as session:
        res = await session.execute(select(User).where(User.telegram_id == call.from_user.id))
        user = res.scalars().first()
        
        if not user or user.bonus_balance < 20000:
            msg = "Minimal yechish summasi 20,000 UZS. Balansingiz yetarli emas." if (not user or not user.language or user.language == 'uz') else ("Минимальная сумма вывода 20,000 UZS. Недостаточно средств." if user.language == 'ru' else "Minimum withdrawal amount is 20,000 UZS. Insufficient balance.")
            await call.answer(msg, show_alert=True)
            return

        lang = user.language or 'uz'
        text = "💳 Iltimos, pulni yechib olish uchun \n<b>16 xonali karta raqamini</b> yuboring:" if lang == 'uz' else ("💳 Пожалуйста, отправьте <b>16-значный номер карты</b> для вывода:" if lang == 'ru' else "💳 Please send your <b>16-digit card number</b> for withdrawal:")
        
        await state.set_state(WithdrawalState.waiting_for_card)
        await call.message.answer(text, parse_mode="HTML")
        await call.answer()

@router.message(WithdrawalState.waiting_for_card)
async def process_withdrawal_card(message: types.Message, state: FSMContext):
    card = message.text.replace(" ", "")
    if not card.isdigit() or len(card) != 16:
        from utils.i18n import _
        await message.answer(_('withdraw_invalid_card', 'uz'))
        return

    await state.update_data(card_number=message.text)
    
    async with session_scope() as session:
        res = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = res.scalars().first()
        
        lang = user.language or 'uz'
        text = f"Sizning balansingiz: <b>{user.bonus_balance:,.0f} UZS</b>\n\nQancha yechmoqchisiz? (Minimal: 20000)" if lang == 'uz' else f"Ваш баланс: <b>{user.bonus_balance:,.0f} UZS</b>\n\nСколько хотите вывести? (Минимум: 20000)"
        
        await state.set_state(WithdrawalState.waiting_for_amount)
        await message.answer(text, parse_mode="HTML")

@router.message(WithdrawalState.waiting_for_amount)
async def process_withdrawal_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(" ", "").replace(",", ""))
    except ValueError:
        from utils.i18n import _
        await message.answer(_('withdraw_invalid_amount', 'uz'))
        return

    if amount < 20000:
        from utils.i18n import _
        await message.answer(_('withdraw_min_amount_err', 'uz'))
        return

    async with session_scope() as session:
        res = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = res.scalars().first()

        if not user or amount > user.bonus_balance:
            from utils.i18n import _
            lang = user.language if user else 'uz'
            await message.answer(_('withdraw_insufficient_funds', lang))
            return

        data = await state.get_data()
        card_number = data.get("card_number")

        res_set = await session.execute(select(Settings).where(Settings.key == 'premium_channel_id'))
        setting = res_set.scalars().first()
        channel_id = setting.value if setting and setting.value else getenv("premium_channel_id")

        if not channel_id:
            from utils.i18n import _
            lang = user.language if user else 'uz'
            await message.answer(_('withdraw_channel_error', lang))
            await state.clear()
            return

        # Deduct balance
        user.bonus_balance -= amount

        # Create Withdrawal Request
        withdrawal = WithdrawalRequest(
            user_id=user.id,
            amount=amount,
            card_number=card_number,
            status="pending"
        )
        session.add(withdrawal)
        await session.flush()

        log_text = (
            f"💸 <b>Pul yechish so'rovi</b>\n\n"
            f"👤 Foydalanuvchi: <a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a>\n"
            f"🆔 ID: <code>{message.from_user.id}</code>\n"
            f"💳 Karta raqami: <code>{card_number}</code>\n"
            f"💰 Summa: <b>{amount:,.0f} UZS</b>\n"
        )

        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ To'landi", callback_data=f"withdraw_paid_{withdrawal.id}")],
            [InlineKeyboardButton(text="❌ Rad etish", callback_data=f"withdraw_reject_{withdrawal.id}")]
        ])

        try:
            msg = await message.bot.send_message(chat_id=channel_id, text=log_text, reply_markup=markup, parse_mode="HTML")
            withdrawal.message_id = msg.message_id
            await session.commit()
            
            from utils.i18n import _
            lang = user.language if user else 'uz'
            await message.answer(_('withdraw_request_sent', lang))
        except Exception as e:
            await session.rollback()
            logging.error(f"Error sending withdrawal log: {e}")
            from utils.i18n import _
            lang = user.language if 'user' in locals() and user else 'uz'
            await message.answer(_('withdraw_error', lang))
        finally:
            await state.clear()

@router.callback_query(F.data.startswith("withdraw_paid_"))
async def handle_withdraw_paid(call: types.CallbackQuery):
    # Only admins can mark withdrawals as paid
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    req_id = int(call.data.split("_")[-1])
    async with session_scope() as session:
        withdrawal = await session.get(WithdrawalRequest, req_id)
        if not withdrawal:
            from utils.i18n import _
            await call.answer(_('withdraw_req_not_found', 'uz'), show_alert=True)
            return
            
        if withdrawal.status != "pending":
            from utils.i18n import _
            await call.answer(_('withdraw_already_reviewed', 'uz'), show_alert=True)
            return
            
        withdrawal.status = "paid"
        await session.commit()
        
        # Fetch user to send notification
        user = await session.get(User, withdrawal.user_id)
        if user:
            try:
                from utils.i18n import _
                lang = user.language or 'uz'
                await call.message.bot.send_message(
                    chat_id=user.telegram_id, 
                    text=_('withdraw_paid_msg', lang, amount=withdrawal.amount)
                )
            except:
                pass
                
        try:
            await call.message.edit_text(call.message.html_text + "\n\n✅ <b>To'landi</b>", parse_mode="HTML")
        except:
            pass
            
        await call.answer("Tasdiqlandi!")

@router.callback_query(F.data.startswith("withdraw_reject_"))
async def handle_withdraw_reject(call: types.CallbackQuery):
    # Only admins can reject withdrawals
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("Ruxsat yo'q.", show_alert=True)
        return
    req_id = int(call.data.split("_")[-1])
    async with session_scope() as session:
        withdrawal = await session.get(WithdrawalRequest, req_id)
        if not withdrawal:
            await call.answer("So'rov topilmadi.", show_alert=True)
            return
            
        if withdrawal.status != "pending":
            await call.answer("Bu so'rov allaqachon ko'rib chiqilgan.", show_alert=True)
            return
            
        withdrawal.status = "rejected"
        
        # Refund balance
        user = await session.get(User, withdrawal.user_id)
        if user:
            user.bonus_balance += withdrawal.amount
            try:
                from utils.i18n import _
                lang = user.language or 'uz'
                await call.message.bot.send_message(
                    chat_id=user.telegram_id, 
                    text=_('withdraw_rejected_msg', lang, amount=withdrawal.amount)
                )
            except:
                pass
                
        await session.commit()
        
        try:
            await call.message.edit_text(call.message.html_text + "\n\n❌ <b>Rad etildi</b>", parse_mode="HTML")
        except:
            pass
            
        await call.answer("Rad etildi va pul qaytarildi!")

@router.callback_query(F.data == "referral_promo")
async def process_referral_promo(call: types.CallbackQuery):
    async with session_scope() as session:
        res = await session.execute(select(User).where(User.telegram_id == call.from_user.id))
        user = res.scalars().first()
        
        if not user or user.bonus_balance < 20000:
            msg = "Promokod yaratish uchun kamida 20,000 UZS talab qilinadi." if (not user or not user.language or user.language == 'uz') else ("Для создания промокода требуется минимум 20,000 UZS." if user.language == 'ru' else "Minimum 20,000 UZS required to create a promo code.")
            await call.answer(msg, show_alert=True)
            return

        lang = user.language or 'uz'
        max_months = int(user.bonus_balance // 20000)

        if max_months > 1:
            markup = InlineKeyboardMarkup(inline_keyboard=[])
            # Generates buttons dynamically for 1 up to max_months
            for i in range(1, max_months + 1):
                btn_text = f"{i} oy ({-i * 20000:,.0f} UZS)" if lang == 'uz' else (f"{i} месяц ({-i * 20000:,.0f} UZS)" if lang == 'ru' else f"{i} months ({-i * 20000:,.0f} UZS)")
                markup.inline_keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"gen_promo_{i}")])
                
            text = f"Sizda {user.bonus_balance:,.0f} UZS bor. Necha oylik promokod yaratmoqchisiz?" if lang == 'uz' else f"У вас есть {user.bonus_balance:,.0f} UZS. На сколько месяцев создать промокод?"
            await call.message.answer(text, reply_markup=markup)
            await call.answer()
        else:
            # max_months == 1
            await process_gen_promo(call, 1, user, session)

@router.callback_query(F.data.startswith("gen_promo_"))
async def handle_gen_promo_callback(call: types.CallbackQuery):
    months = int(call.data.split("_")[-1])
    async with session_scope() as session:
        res = await session.execute(select(User).where(User.telegram_id == call.from_user.id))
        user = res.scalars().first()
        if not user:
            return
        
        required_balance = months * 20000
        if user.bonus_balance < required_balance:
            lang = user.language or 'uz'
            msg = "Balansingiz yetarli emas." if lang == 'uz' else ("Недостаточно средств." if lang == 'ru' else "Insufficient balance.")
            await call.answer(msg, show_alert=True)
            return
            
        await process_gen_promo(call, months, user, session)

async def process_gen_promo(call, months, user, session):
    cost = months * 20000
    user.bonus_balance -= cost
    
    import random, string
    code = "REF-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    days = months * 31
    
    promo = PromoCode(
        code=code,
        days=days,
        max_uses=1,
        current_uses=0
    )
    session.add(promo)
    await session.commit()
    
    lang = user.language or 'uz'
    text = (
        f"✅ <b>Promokod yaratildi!</b>\n\n"
        f"🎁 Promokod: <code>{code}</code>\n"
        f"⏳ Muddat: {days} kun ({months} oy)\n"
        f"💰 Yechilgan summa: {cost:,.0f} UZS\n\n"
        f"Ushbu promokodni botga yuborib Premium obuna olishingiz yoki boshqalarga sovg'a qilishingiz mumkin."
    ) if lang == 'uz' else (
        f"✅ <b>Промокод создан!</b>\n\n"
        f"🎁 Промокод: <code>{code}</code>\n"
        f"⏳ Срок: {days} дней ({months} месяца)\n"
        f"💰 Списанная сумма: {cost:,.0f} UZS\n\n"
        f"Вы можете отправить этот промокод боту, чтобы получить Premium подписку, или подарить его другим."
    )
    
    await call.message.answer(text, parse_mode="HTML")
    await call.answer()
