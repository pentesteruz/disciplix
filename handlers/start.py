import logging
from aiogram import Router, types, F, Bot
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from sqlalchemy import select, update, func
from database.engine import session_scope
from config import WEBAPP_URL
from database.models import User, DetailedExpenses, PromoCode, Settings
import json
import string
import random
from datetime import datetime, timedelta
from utils.i18n import _, get_all_translations
from utils.timezone import get_tashkent_time

def get_main_keyboard(telegram_id, lang='uz'):
    dashboard_btn_text = _( 'dashboard_btn', lang)
    dashboard_btn = KeyboardButton(text=dashboard_btn_text)

    return ReplyKeyboardMarkup(
        keyboard=[
            [dashboard_btn],
            [KeyboardButton(text=_( 'referal_btn', lang)), KeyboardButton(text=_( 'premium_btn', lang))],
            [KeyboardButton(text=_( 'support_btn', lang)), KeyboardButton(text=_( 'info_btn', lang))]
        ],
        resize_keyboard=True
    )

router = Router()

# Diqqat: bu middleware bot.py'da dispatcher darajasida ro'yxatdan o'tkaziladi
# (message va callback_query uchun). Bu yerda router'ga ham ulash uni start.router
# orqali o'tadigan har bir xabar uchun ikki marta ishga tushirardi.
async def check_frozen_middleware(handler, event, data):
    is_message = isinstance(event, types.Message)
    is_callback = isinstance(event, types.CallbackQuery)
    if not is_message and not is_callback:
        return await handler(event, data)
        
    telegram_id = event.from_user.id
    async with session_scope() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = res.scalars().first()
        if user:
            user.last_active = get_tashkent_time()
            
            # Check freeze
            now = get_tashkent_time()
            is_currently_frozen = False
            if user.frozen_until:
                if user.frozen_until > now:
                    is_currently_frozen = True
                else:
                    # Freeze duration has expired
                    user.is_frozen = False
                    user.frozen_until = None
            elif user.is_frozen:
                is_currently_frozen = True
                
            if is_currently_frozen:
                res_set = await session.execute(select(Settings).where(Settings.key == 'admin_usernames'))
                setting = res_set.scalars().first()
                admin_usernames = setting.value if setting and setting.value else "@admin"
                
                lang = user.language or 'uz'
                freeze_msg = (
                    f"Sizning hisobingiz muzlatilgan. Iltimos adminga murojaat qiling: {admin_usernames}" if lang == 'uz' else 
                    (f"Ваш аккаунт заморожен. Пожалуйста, свяжитесь с администратором: {admin_usernames}" if lang == 'ru' else 
                     f"Your account is frozen. Please contact the admin: {admin_usernames}")
                )
                
                if is_message:
                    await event.answer(freeze_msg)
                elif is_callback:
                    await event.answer(freeze_msg, show_alert=True)
                await session.commit()
                return # Block
            
            # Test oqimida policy bloklamaslik
            if user.user_state in ('test_expense', 'test_plan', 'testing_done'):
                await session.commit()
                return await handler(event, data)

            # Check policy
            if not user.accepted_policy:
                # If they are trying to accept the policy via callback, allow it
                if is_callback and event.data == "accept_privacy_policy":
                    await session.commit()
                    return await handler(event, data)
                
                lang = user.language or 'uz'
                
                texts = {
                    'uz': "Davom etishingiz uchun Maxfiylik siyosatimizga (Privacy Policy) rozilik bildirishingiz kerak.",
                    'ru': "Для продолжения вы должны согласиться с нашей Политикой конфиденциальности.",
                    'en': "To continue, you must agree to our Privacy Policy."
                }
                policy_msg = texts.get(lang, texts['uz'])
                
                btn_uz = "✅ Roziman"
                btn_ru = "✅ Согласен(на)"
                btn_en = "✅ I Agree"
                btns = {'uz': btn_uz, 'ru': btn_ru, 'en': btn_en}
                btn_msg = btns.get(lang, btn_uz)
                
                from config import WEBAPP_URL
                from aiogram.types import WebAppInfo
                
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📄 Privacy Policy", web_app=WebAppInfo(url=f"{WEBAPP_URL}/privacy?lang={lang}"))],
                    [InlineKeyboardButton(text=btn_msg, callback_data="accept_privacy_policy")]
                ])
                
                if is_message:
                    await event.answer(policy_msg, reply_markup=markup, parse_mode="HTML")
                elif is_callback:
                    if hasattr(event.message, 'answer'):
                        await event.message.answer(policy_msg, reply_markup=markup, parse_mode="HTML")
                    await event.answer("Iltimos, avval maxfiylik siyosatiga rozi bo'ling.", show_alert=True)
                
                await session.commit()
                return # Block
            
            await session.commit()
            
    return await handler(event, data)

@router.callback_query(F.data == "accept_privacy_policy")
async def handle_accept_policy(callback: CallbackQuery):
    telegram_id = callback.from_user.id
    async with session_scope() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = res.scalars().first()
        if user:
            user.accepted_policy = True
            await session.commit()
            
            lang = user.language or 'uz'
            
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except:
                pass
            await callback.answer()
            
            # Agar telefon raqami yo'q bo'lsa (va web orqali ham ro'yxatdan o'tmagan) — web app ga yo'naltirish
            is_web_registered = user.phone_number and user.phone_number.startswith('tg_')
            if not user.phone_number or is_web_registered:
                # If already registered via web, just show main menu
                if is_web_registered:
                    success_msg = (
                        "✅ Maxfiylik siyosati qabul qilindi! Endi botdan to'liq foydalanishingiz mumkin." if lang == 'uz' else
                        ("✅ Политика конфиденциальности принята! Теперь вы можете полноценно использовать бота." if lang == 'ru' else
                         "✅ Privacy policy accepted! You can now fully use the bot.")
                    )
                    await callback.message.answer(success_msg, reply_markup=get_main_keyboard(telegram_id, lang))
                else:
                    from config import WEBAPP_URL
                    register_text_uz = (
                        "✅ Maxfiylik siyosati qabul qilindi!\n\n"
                        "Endi ro'yxatdan o'tishingiz kerak. Quyidagi tugmani bosib, "
                        "ma'lumotlaringizni kiriting. Ro'yxatdan o'tganingiz uchun sizga "
                        "3 kunlik Premium sovg'a beramiz! 🎁"
                    )
                    register_text_ru = (
                        "✅ Политика конфиденциальности принята!\n\n"
                        "Теперь вам нужно зарегистрироваться. Нажмите кнопку ниже и "
                        "введите свои данные. За регистрацию вы получите 3 дня Premium в подарок! 🎁"
                    )
                    register_text_en = (
                        "✅ Privacy policy accepted!\n\n"
                        "Now you need to register. Press the button below and enter your details. "
                        "You will receive 3 days of Premium as a gift for registering! 🎁"
                    )
                    texts = {'uz': register_text_uz, 'ru': register_text_ru, 'en': register_text_en}
                    reg_msg = texts.get(lang, register_text_uz)
                    
                    from aiogram.types import WebAppInfo
                    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text=_('register_btn', lang),
                            web_app=WebAppInfo(url=f"{WEBAPP_URL}/register?user_id={telegram_id}&lang={lang}")
                        )
                    ]])
                    await callback.message.answer(reg_msg, reply_markup=inline_kb)
            else:
                # Allaqachon ro'yxatdan o'tgan (real phone number)
                success_msg = (
                    "✅ Maxfiylik siyosati qabul qilindi! Endi botdan to'liq foydalanishingiz mumkin." if lang == 'uz' else
                    ("✅ Политика конфиденциальности принята! Теперь вы можете полноценно использовать бота." if lang == 'ru' else
                     "✅ Privacy policy accepted! You can now fully use the bot.")
                )
                await callback.message.answer(success_msg, reply_markup=get_main_keyboard(telegram_id, lang))

@router.message(Command("promo"))
async def cmd_promo(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("Iltimos, promokodni kiriting: masalan /promo soz")
        return
        
    code = command.args.strip()
    telegram_id = message.from_user.id
    
    async with session_scope() as session:
        res_user = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = res_user.scalars().first()
        
        if not user:
            lang = message.from_user.language_code or 'uz'
            reg_msg = "Siz ro'yxatdan o'tmagansiz. Ro'yxatdan o'tish uchun tugmani bosing."
            from aiogram.types import WebAppInfo
            inline_kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text=_( 'register_btn', lang),
                    web_app=WebAppInfo(url=f"{WEBAPP_URL}/register?user_id={telegram_id}&lang={lang}")
                )
            ]])
            await message.answer(reg_msg, reply_markup=inline_kb)
            return

        res_promo = await session.execute(select(PromoCode).where(PromoCode.code == code))
        promo = res_promo.scalars().first()
        
        if not promo:
            await message.answer("❌ Promokod noto'g'ri yoki mavjud emas.")
            return
            
        if promo.current_uses >= promo.max_uses:
            await message.answer("❌ Bu promokod limitga yetgan yoki tugagan.")
            return
        
        # apply promo
        tashkent_now = get_tashkent_time()
        if user.premium_until and user.premium_until > tashkent_now:
            user.premium_until = user.premium_until + timedelta(days=promo.days)
        else:
            user.premium_until = tashkent_now + timedelta(days=promo.days)
            
        promo.current_uses += 1
        
        await session.commit()
        await message.answer(f"🎉 Tabriklayman! Sizga {promo.days} kun premium qo'shildi.")

@router.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject):
    telegram_id = message.from_user.id
    name = message.from_user.full_name
    
    ref_code = command.args if command and command.args else None

    async with session_scope() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalars().first()
        
        referred_by_id = None
        if not user and ref_code:
            # Look up referrer
            ref_res = await session.execute(select(User).where(User.referral_code == ref_code))
            referrer = ref_res.scalars().first()
            if referrer:
                referred_by_id = referrer.id

        if not user or user.user_state == "onboarding":
            # Show onboarding message with dynamic text and video from Admin Settings
            info_res = await session.execute(select(Settings).where(Settings.key == 'start_text'))
            info_setting = info_res.scalars().first()
            
            video_res = await session.execute(select(Settings).where(Settings.key == 'start_video_id'))
            video_setting = video_res.scalars().first()
            
            welcome_text_raw = info_setting.value if info_setting else "O'rnatilmagan"
            if welcome_text_raw == "O'chirilgan":
                welcome_text = ""
            elif welcome_text_raw and welcome_text_raw != "O'rnatilmagan":
                welcome_text = welcome_text_raw
            else:
                welcome_text = "Assalomu alaykum! Men Disciplix — sizning moliyaviy va shaxsiy intizomingiz uchun aqlli yordamchiman."
            
            video_id_raw = video_setting.value if video_setting else "O'rnatilmagan"
            video_id = None if video_id_raw in ("O'rnatilmagan", "O'chirilgan", None, "") else video_id_raw
            
            # Guard against zero content
            if not video_id and not welcome_text:
                welcome_text = "Assalomu alaykum! Men Disciplix — sizning moliyaviy va shaxsiy intizomingiz uchun aqlli yordamchiman."
            
            onboard_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Ha, boshlaymiz", callback_data=f"onboard_skip_{ref_code or 'none'}")],
                [InlineKeyboardButton(text="🔍 Test qilib ko'rish", callback_data=f"onboard_test_{ref_code or 'none'}")]
            ])
            
            if video_id:
                try:
                    await message.answer_video(video=video_id, caption=welcome_text, reply_markup=onboard_kb, parse_mode="HTML")
                except Exception:
                    # Fallback to text if video fails to send
                    fallback_text = welcome_text if welcome_text else "Assalomu alaykum! Men Disciplix — sizning moliyaviy va shaxsiy intizomingiz uchun aqlli yordamchiman."
                    await message.answer(fallback_text, reply_markup=onboard_kb, parse_mode="HTML")
            else:
                await message.answer(welcome_text, reply_markup=onboard_kb, parse_mode="HTML")
        elif user.user_state == "test_expense":
            lang = user.language or 'uz'
            msg = "Test jarayonidasiz. Keling, sinab ko'ramiz. Menga: 'Bugun tushlikka 35 ming sarfladim' deb yozing yoki ovoz yuboring." if lang == 'uz' else ("Вы в процессе тестирования. Попробуем. Напишите или отправьте голос: 'Я потратил 35 тысяч на обед сегодня'." if lang == 'ru' else "You are in testing mode. Let's try. Write or send voice: 'I spent 35 thousand on lunch today'.")
            await message.answer(msg)
        elif user.user_state == "test_plan":
            lang = user.language or 'uz'
            msg = "Test jarayonidasiz. Endi reja tuzib ko'ramiz. Menga: 'Men bugun 6:30 da yugurib kelaman' deb yozib ko'ring yoki ovozli xabar yuboring." if lang == 'uz' else ("Вы в процессе тестирования. Теперь давайте создадим план. Попробуйте написать или отправить голосовое: 'Я пойду на пробежку в 6:30 сегодня'." if lang == 'ru' else "You are in testing mode. Now let's create a plan. Try writing or sending voice: 'I will go for a run at 6:30 today'.")
            await message.answer(msg)
        else:
            lang = user.language or 'uz'
            # phone_number=None => not registered, phone_number starts with tg_ => registered via web app
            is_web_registered = user.phone_number and user.phone_number.startswith('tg_')
            is_phone_registered = user.phone_number and not user.phone_number.startswith('tg_')
            if is_phone_registered or is_web_registered:
                await message.answer(_( 'welcome_main', lang, name=user.name or name), reply_markup=get_main_keyboard(telegram_id, lang))
            else:
                from aiogram.types import WebAppInfo
                inline_kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text=_( 'register_btn', lang),
                        web_app=WebAppInfo(url=f"{WEBAPP_URL}/register?user_id={telegram_id}&lang={lang}")
                    )
                ]])
                msg = "Orzularingiz uchun to'liq imkoniyatlardan foydalanish uchun ro'yxatdan o'ting!" if lang == 'uz' else ("Зарегистрируйтесь, чтобы использовать все возможности для ваших мечт!" if lang == 'ru' else "Register to use all opportunities for your dreams!")
                await message.answer(msg, reply_markup=inline_kb)

@router.callback_query(F.data.startswith("onboard_"))
async def process_onboarding_selection(callback: CallbackQuery):
    data_parts = callback.data.split('_')
    action = data_parts[1]
    ref_code = data_parts[2] if len(data_parts) > 2 and data_parts[2] != 'none' else ''
    telegram_id = callback.from_user.id
    
    async with session_scope() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalars().first()

        referred_by_id = None
        if ref_code:
            ref_res = await session.execute(select(User).where(User.referral_code == ref_code))
            referrer = ref_res.scalars().first()
            if referrer:
                referred_by_id = referrer.id

        if not user:
            user = User(
                telegram_id=telegram_id,
                referral_code=''.join(random.choices(string.ascii_letters + string.digits, k=8)),
                referred_by_id=referred_by_id,
                language='uz',
                user_state='onboarding'
            )
            session.add(user)
    
        if action == "test":
            user.user_state = "test_expense"
            await session.commit()
            lang = user.language or 'uz'
            test_text = "Keling, sinab ko'ramiz. Menga: 'Bugun tushlikka 35 ming sarfladim' deb yozing yoki ovoz yuboring." if lang == 'uz' else ("Попробуем. Напишите или отправьте голос: 'Я потратил 35 тысяч на обед сегодня'." if lang == 'ru' else "Let's try. Write or send voice: 'I spent 35 thousand on lunch today'.")
            await callback.message.edit_text(test_text)
            await callback.answer()
        elif action == "skip":
            user.user_state = "testing_done" # mark as done
            await session.commit()
            
            lang_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data=f"lang_uz_{ref_code or 'none'}")],
                [InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"lang_ru_{ref_code or 'none'}")],
                [InlineKeyboardButton(text="🇬🇧 English", callback_data=f"lang_en_{ref_code or 'none'}")]
            ])
            await callback.message.edit_text("🇺🇿 Tilni tanlang:\n🇷🇺 Выберите язык:\n🇬🇧 Choose language:", reply_markup=lang_kb)
            await callback.answer()

@router.callback_query(F.data.startswith("lang_"))
async def process_language_selection(callback: CallbackQuery):
    data_parts = callback.data.split('_')
    lang = data_parts[1]
    ref_code = data_parts[2] if len(data_parts) > 2 and data_parts[2] != 'none' else ''
    telegram_id = callback.from_user.id
    
    is_registered = False
    async with session_scope() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalars().first()
        if user:
            user.language = lang
            if user.phone_number:
                is_registered = True
            await session.commit()
    
    try:
        await callback.message.delete()
    except:
        pass

    if is_registered:
        from handlers.start import get_main_keyboard
        await callback.message.answer(_('lang_success', lang), reply_markup=get_main_keyboard(telegram_id, lang))
        await callback.answer()
        return

    register_text = (
        "Botning barcha imkoniyatlaridan to'liq foydalanish va ma'lumotlaringizni xavfsiz saqlash uchun ro'yxatdan o'ting.\n\n"
        "🎁 Sovg'a: Ro'yxatdan o'tganingiz uchun sizga 3 kunlik Premium obuna taqdim etiladi!"
    )
    
    from aiogram.types import WebAppInfo
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=_( 'register_btn', lang),
            web_app=WebAppInfo(url=f"{WEBAPP_URL}/register?user_id={telegram_id}&lang={lang}")
        )
    ]])
    
    await callback.message.answer(register_text, reply_markup=inline_kb)
    await callback.answer()

@router.message(Command("lang"))
@router.message(Command("language"))
async def cmd_lang(message: types.Message):
    telegram_id = message.from_user.id
    async with session_scope() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalars().first()
        lang = user.language if user else 'uz'
    
    lang_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz_none")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru_none")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en_none")]
    ])
    await message.answer(_('lang_choose', lang), reply_markup=lang_kb)

@router.message(F.web_app_data)
async def handle_web_app_data(message: types.Message):
    data = json.loads(message.web_app_data.data)
    
    if data.get('action') == 'register':
        telegram_id = message.from_user.id
        ref_code = data.get('ref')
        lang = data.get('lang', 'uz')
        
        async with session_scope() as session:
            result = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalars().first()
            
            if not user:
                referred_by_id = None
                if ref_code:
                    ref_res = await session.execute(select(User).where(User.referral_code == ref_code))
                    referrer = ref_res.scalars().first()
                    if referrer:
                        referred_by_id = referrer.id

                user = User(
                    telegram_id=telegram_id,
                    referral_code=''.join(random.choices(string.ascii_letters + string.digits, k=8)),
                    referred_by_id=referred_by_id,
                    language=lang
                )
                session.add(user)
            else:
                user.language = lang
            
            user.name = data.get('name')
            user.surname = data.get('surname')
            user.monthly_income = float(data.get('monthly_income', 0))
            user.registration_mode = data.get('mode', 'quick')
            user.fixed_expenses_total = float(data.get('fixed_expenses_total', 0))
            user.balance = user.monthly_income 
            user.user_state = "registered"
            
            await session.flush()
            
            if user.registration_mode == 'quick':
                user.daily_limit = float(data.get('daily_limit', 0))
            else:
                # Detailed mode logic
                expenses = data.get('expenses', [])
                for exp in expenses:
                    new_expense = DetailedExpenses(
                        user_id=user.id, 
                        name=exp['name'],
                        amount=float(exp['amount']),
                        due_date=str(exp.get('day', ''))
                    )
                    session.add(new_expense)
                
                # Calculate daily limit
                remaining_income = user.monthly_income - user.fixed_expenses_total
                calculated_daily_limit = remaining_income / 30 if remaining_income > 0 else 0
                user.daily_limit = round(calculated_daily_limit, 2)
            user.phone_number = f"998{telegram_id}"
            
            # 3 days premium for registration.
            # premium_until muddati tugagach ham tozalanmaydi, shuning uchun uning
            # bo'shligi "hech qachon premium bo'lmagan" degani.
            if not user.premium_until:
                user.premium_until = get_tashkent_time() + timedelta(days=3)
            
            try:
                await session.commit()
                
                lang = user.language or 'uz'
                
                response_text = "Ma'lumotlar qabul qilindi." if lang == 'uz' else ("Данные приняты." if lang == 'ru' else "Data received.")
                
                success_text = _('registration_complete', lang)
                if user.registration_mode == 'detailed':
                    extra = f"\n\nSizning hisoblangan kunlik limitigingiz: {user.daily_limit:,.0f} so'm." if lang == 'uz' else (
                        f"\n\nВаш расчётный дневной лимит: {user.daily_limit:,.0f} сум." if lang == 'ru' else
                        f"\n\nYour calculated daily limit: {user.daily_limit:,.0f} UZS."
                    )
                    success_text += extra
                
                await message.answer(success_text, reply_markup=get_main_keyboard(telegram_id, lang))
                
                # Reward referrer
                if user.referred_by_id:
                    res_referrer = await session.execute(select(User).where(User.id == user.referred_by_id))
                    referrer = res_referrer.scalars().first()
                    if referrer:
                        referrer_lang = referrer.language or 'uz'
                        individual_msg = f"🎉 Tabriklaymiz! Sizning taklifingiz orqali yangi do'stingiz ro'yxatdan o'tdi." if referrer_lang == 'uz' else (f"🎉 Поздравляем! По вашей ссылке зарегистрировался новый друг." if referrer_lang == 'ru' else f"🎉 Congratulations! A new friend registered via your invite link.")
                        try:
                            await message.bot.send_message(chat_id=referrer.telegram_id, text=individual_msg)
                        except:
                            pass
                            
                        count_res = await session.execute(select(func.count(User.id)).where(User.referred_by_id == referrer.id, User.phone_number != None))
                        actual_ref_count = count_res.scalar() or 0
                        
                        ref_count_res = await session.execute(select(Settings).where(Settings.key == 'ref_count'))
                        ref_count_setting = ref_count_res.scalars().first()
                        ref_req = int(ref_count_setting.value) if ref_count_setting and ref_count_setting.value else 4
                        
                        ref_days_res = await session.execute(select(Settings).where(Settings.key == 'ref_days'))
                        ref_days_setting = ref_days_res.scalars().first()
                        ref_days = int(ref_days_setting.value) if ref_days_setting and ref_days_setting.value else 3
                        
                        if actual_ref_count > 0 and actual_ref_count % ref_req == 0:
                            if not referrer.premium_until or referrer.premium_until < get_tashkent_time():
                                referrer.premium_until = get_tashkent_time() + timedelta(days=ref_days)
                            else:
                                referrer.premium_until += timedelta(days=ref_days)
                            
                            await session.commit()
                            try:
                                bonus_msg = _('referrer_bonus', referrer_lang, count=actual_ref_count, req=ref_req, days=ref_days)
                                await message.bot.send_message(
                                    chat_id=referrer.telegram_id, 
                                    text=bonus_msg
                                )
                            except Exception as e:
                                logging.error(f"Failed to send bonus message to referrer: {e}")

            except Exception as e:
                await session.rollback()
                import traceback
                traceback.print_exc()
                error_msg = "⚠️ Ma'lumotlarni saqlashda xatolik yuz berdi." if data.get('lang') == 'uz' else ("⚠️ Ошибка при сохранении данных." if data.get('lang') == 'ru' else "⚠️ Data saving error.")
                await message.answer(error_msg)


@router.message(F.text.in_(get_all_translations('dashboard_btn')))
async def dashboard_menu_start(message: types.Message):
    telegram_id = message.from_user.id
    async with session_scope() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = res.scalars().first()
        lang = (user.language or 'uz') if user else 'uz'
        text = "Shaxsiy kabinetingizga kirish uchun maxsus tugma:" if lang == 'uz' else ("Специальная кнопка для входа в личный кабинет:" if lang == 'ru' else "Special button to access your cabinet:")
        if WEBAPP_URL:
            markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=_( 'dashboard_btn', lang), web_app=WebAppInfo(url=WEBAPP_URL))]])
            await message.answer(text, reply_markup=markup, parse_mode="HTML")
        else:
            msg = "Web ilova hozirda mavjud emas." if lang == 'uz' else ("Веб-приложение в настоящее время недоступно." if lang == 'ru' else "Web app is currently not available.")
            await message.answer(msg, parse_mode="HTML")
