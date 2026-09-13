import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, text, update
from config import ADMIN_IDS
from database.engine import session_scope
from database.models import Settings, User, Task, Dream, DreamProgress, Debt, Transaction, LifeSchedule, DetailedExpenses, PremiumRequest, WithdrawalRequest

admin_panel = Router()

class AdminPanelState(StatesGroup):
    waiting_for_sms_token = State()
    waiting_for_withdraw_id = State()
    waiting_for_premium_id = State()
    waiting_for_support_id = State()
    waiting_for_error_id = State()
    waiting_for_ref_percent = State()
    waiting_for_ref_days = State()
    waiting_for_ref_count = State()
    waiting_for_info_text = State()
    waiting_for_video_link = State()
    waiting_for_card_number = State()
    waiting_for_broadcast = State()
    waiting_for_broadcast_confirm = State()

async def delete_user_data(telegram_id: int) -> bool:
    async with session_scope() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = res.scalars().first()
        if not user:
            return False
        
        user_id = user.id
        await session.execute(update(User).where(User.referred_by_id == user_id).values(referred_by_id=None))
        await session.execute(text("DELETE FROM finances WHERE user_id = :uid").bindparams(uid=user_id))
        await session.execute(text("DELETE FROM currency_conversion_log WHERE user_id = :uid").bindparams(uid=user_id))
        await session.execute(text("DELETE FROM tasks WHERE user_id = :uid").bindparams(uid=user_id))
        await session.execute(text("DELETE FROM dream_progress WHERE user_id = :uid").bindparams(uid=user_id))
        await session.execute(text("DELETE FROM dreams WHERE user_id = :uid").bindparams(uid=user_id))
        await session.execute(text("DELETE FROM premium_requests WHERE user_id = :uid").bindparams(uid=user_id))
        await session.execute(text("DELETE FROM withdrawal_requests WHERE user_id = :uid").bindparams(uid=user_id))
        await session.execute(text("DELETE FROM transactions WHERE user_id = :uid").bindparams(uid=user_id))
        await session.execute(text("DELETE FROM life_schedule WHERE user_id = :uid").bindparams(uid=user_id))
        await session.execute(text("DELETE FROM detailed_expenses WHERE user_id = :uid").bindparams(uid=user_id))
        await session.execute(text("DELETE FROM debts WHERE user_id = :uid").bindparams(uid=user_id))
        
        await session.delete(user)
        await session.commit()
        return True

@admin_panel.callback_query(F.data.startswith("user_del_confirm:"))
async def user_delete_confirm(call: types.CallbackQuery):
    try:
        _, payload = call.data.split(":", 1)
        target_id_str, admin_id_str = payload.split(":")
        target_id = int(target_id_str)
        admin_id = int(admin_id_str)
    except Exception:
        await call.answer("Xatolik: noto'g'ri so'rov", show_alert=True)
        return
    
    if call.from_user.id != target_id:
        await call.answer("Bu so'rov sizga tegishli emas.", show_alert=True)
        return
    
    ok = await delete_user_data(target_id)
    if ok:
        await call.message.edit_text("Ma'lumotlaringiz o'chirildi.")
        try:
            await call.bot.send_message(chat_id=admin_id, text=f"✅ Foydalanuvchi ({target_id}) ma'lumotlari o'chirildi.")
        except:
            pass
    else:
        await call.message.edit_text("Foydalanuvchi topilmadi yoki o'chirishda xatolik.")
    await call.answer()

@admin_panel.callback_query(F.data.startswith("user_del_cancel:"))
async def user_delete_cancel(call: types.CallbackQuery):
    try:
        _, payload = call.data.split(":", 1)
        target_id_str, admin_id_str = payload.split(":")
        target_id = int(target_id_str)
        admin_id = int(admin_id_str)
    except Exception:
        await call.answer("Xatolik: noto'g'ri so'rov", show_alert=True)
        return
    
    if call.from_user.id != target_id:
        await call.answer("Bu so'rov sizga tegishli emas.", show_alert=True)
        return
    
    await call.message.edit_text("So'rov bekor qilindi.")
    try:
        await call.bot.send_message(chat_id=admin_id, text=f"❌ Foydalanuvchi ({target_id}) ma'lumotlarni o'chirishni rad etdi.")
    except:
        pass
    await call.answer()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def get_setting(key: str, default: str = "") -> str:
    async with session_scope() as session:
        res = await session.execute(select(Settings).where(Settings.key == key))
        setting = res.scalars().first()
        return setting.value if setting else default

async def set_setting(key: str, value: str):
    async with session_scope() as session:
        res = await session.execute(select(Settings).where(Settings.key == key))
        setting = res.scalars().first()
        if setting:
            setting.value = value
        else:
            session.add(Settings(key=key, value=value))
        await session.commit()

def admin_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Channel Setting & Elon", callback_data="admin_menu_channel")],
        [InlineKeyboardButton(text="👥 Referral System", callback_data="admin_menu_referral")],
        [InlineKeyboardButton(text="ℹ️ Info & Content", callback_data="admin_menu_content")],
        [InlineKeyboardButton(text="👤 Admin Profile", callback_data="admin_menu_profile")],
        [InlineKeyboardButton(text="❌ Yopish", callback_data="admin_menu_close")]
    ])

@admin_panel.message(F.text == "/adminpanelkubu")
@admin_panel.message(F.text == "/adminkubu")
async def cmd_admin_panel(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⚠️ Kechirasiz, ushbu buyruqdan foydalanish uchun sizda yetarli ruxsatlar yo'q.")
        return
    await state.clear()
    await message.answer("🛠 <b>Admin Panelga xush kelibsiz!</b>\n\nQuyidagi bo'limlardan birini tanlang:", 
                         reply_markup=admin_main_menu(), parse_mode="HTML")

@admin_panel.message(Command("addelon"))
async def cmd_add_elon(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_menu_channel")]])
    await message.answer("📢 Barcha foydalanuvchilarga yuboriladigan xabarni kiriting (yoki forward qiling):", reply_markup=kb)
    await state.set_state(AdminPanelState.waiting_for_broadcast)

@admin_panel.callback_query(F.data == "admin_menu_close")
async def admin_close_cb(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.clear()
    await call.message.delete()
    await call.answer()

@admin_panel.callback_query(F.data == "admin_menu_main")
async def admin_main_cb(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return
    await state.clear()
    await call.message.edit_text("🛠 <b>Admin Panelga xush kelibsiz!</b>\n\nQuyidagi bo'limlardan birini tanlang:", 
                                reply_markup=admin_main_menu(), parse_mode="HTML")
    await call.answer()

# --- CHANNEL SETTINGS & ELON ---
def channel_settings_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="SMS Bot Username", callback_data="admin_set_smstoken")],
        [InlineKeyboardButton(text="Withdraw Channel ID", callback_data="admin_set_withdrawid")],
        [InlineKeyboardButton(text="Premium Channel ID", callback_data="admin_set_premiumid")],
        [InlineKeyboardButton(text="Support Group ID", callback_data="admin_set_supportid")],
        [InlineKeyboardButton(text="📢 Ommaviy Elon Berish", callback_data="admin_set_broadcast")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_menu_main")]
    ])

@admin_panel.callback_query(F.data == "admin_menu_channel")
async def ds_channel(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("📢 <b>Channel Setting & Elon</b>\n\nKerakli bo'limni tanlang:", 
                                 reply_markup=channel_settings_menu(), parse_mode="HTML")
    await call.answer()

# Config handlers (generic editor pattern)
async def prompt_for_setting(call: types.CallbackQuery, state: FSMContext, setting_key: str, next_state: State, prompt: str):
    if not is_admin(call.from_user.id): return
    current_val = await get_setting(setting_key, "O'rnatilmagan")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_menu_channel")]])
    await call.message.edit_text(f"{prompt}\n\nMavjud qiymat: <code>{current_val}</code>\n\nYangi qiymatni yuboring:", 
                                 reply_markup=kb, parse_mode="HTML")
    await state.set_state(next_state)
    await call.answer()

@admin_panel.callback_query(F.data == "admin_set_smstoken")
async def prompt_smstoken(call: types.CallbackQuery, state: FSMContext):
    await prompt_for_setting(call, state, "sms_bot_username", AdminPanelState.waiting_for_sms_token, "SMS Bot usernamesini kiriting (masalan: pyromsu_11_bot):")

@admin_panel.callback_query(F.data == "admin_set_withdrawid")
async def prompt_withdrawid(call: types.CallbackQuery, state: FSMContext):
    await prompt_for_setting(call, state, "withdrawal_channel_id", AdminPanelState.waiting_for_withdraw_id, "Pul yechish so'rovlari tushadigan kanal/guruh ID'sini kiriting:")

@admin_panel.callback_query(F.data == "admin_set_premiumid")
async def prompt_premiumid(call: types.CallbackQuery, state: FSMContext):
    await prompt_for_setting(call, state, "premium_channel_id", AdminPanelState.waiting_for_premium_id, "Premium xarid loglari tushadigan kanal/guruh ID'sini kiriting:")

@admin_panel.callback_query(F.data == "admin_set_supportid")
async def prompt_supportid(call: types.CallbackQuery, state: FSMContext):
    await prompt_for_setting(call, state, "support_group_id", AdminPanelState.waiting_for_support_id, "Support (Help desk) manzilini kiriting:")

@admin_panel.callback_query(F.data == "admin_set_errorid")
async def prompt_errorid(call: types.CallbackQuery, state: FSMContext):
    await prompt_for_setting(call, state, "error_channel_id", AdminPanelState.waiting_for_error_id, "Tizimdagi xatoliklar (Crash loglar) tushadigan yopiq kanal yoki guruh ID'sini kiriting:")

@admin_panel.callback_query(F.data == "admin_set_broadcast")
async def prompt_broadcast(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_menu_channel")]])
    await call.message.edit_text("📢 Barcha foydalanuvchilarga yuboriladigan xabarni kiriting (yoki forward qiling):", reply_markup=kb)
    await state.set_state(AdminPanelState.waiting_for_broadcast)
    await call.answer()

# --- REFERRAL SYSTEM ---
def referral_settings_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Taklif uchun Premium (kun)", callback_data="admin_set_refdays")],
        [InlineKeyboardButton(text="Xarid bonus (%)", callback_data="admin_set_refpercent")],
        [InlineKeyboardButton(text="Taklif uchun talab (soni)", callback_data="admin_set_refcount")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_menu_main")]
    ])

@admin_panel.callback_query(F.data == "admin_menu_referral")
async def ds_referral(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("👥 <b>Referral System Sozlamalari</b>", reply_markup=referral_settings_menu(), parse_mode="HTML")
    await call.answer()

@admin_panel.callback_query(F.data == "admin_set_refdays")
async def prompt_refdays(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⚠️ Kechirasiz, ushbu buyruqdan foydalanish uchun sizda yetarli ruxsatlar yo'q.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_menu_referral")]])
    current = await get_setting("ref_days", "O'rnatilmagan")
    await call.message.edit_text(f"Taklif uchun beriladigan ustama kun (har N odamga).\nHozirgi qiymat: {current}\n\nYangi qiymatni yuboring (faqat son):", reply_markup=kb)
    await state.set_state(AdminPanelState.waiting_for_ref_days)
    await call.answer()

@admin_panel.callback_query(F.data == "admin_set_refpercent")
async def prompt_refpercent(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⚠️ Kechirasiz, ushbu buyruqdan foydalanish uchun sizda yetarli ruxsatlar yo'q.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_menu_referral")]])
    current = await get_setting("ref_conversion_percent", "10")
    await call.message.edit_text(f"Taklif qilingan do'st premium olsa beriladigan bonus foizi (%).\nHozirgi qiymat: {current}%\n\nYangi qiymatni yuboring (faqat son, 0 dan 100 gacha):", reply_markup=kb)
    await state.set_state(AdminPanelState.waiting_for_ref_percent)
    await call.answer()

# --- INFO & CONTENT ---
def content_type_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 /start uchun", callback_data="admin_content_start")],
        [InlineKeyboardButton(text="ℹ️ /info uchun", callback_data="admin_content_info")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_menu_main")]
    ])

def content_settings_menu(ctype: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Matn (Tasnif)", callback_data=f"admin_set_text_{ctype}"),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin_del_text_{ctype}")
        ],
        [
            InlineKeyboardButton(text="🎥 Video yuklash", callback_data=f"admin_set_video_{ctype}"),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin_del_video_{ctype}")
        ],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_menu_content")]
    ])

@admin_panel.callback_query(F.data == "admin_menu_content")
async def ds_content(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("ℹ️ <b>Qaysi biri uchun sozlamalarni o'zgartiramiz?</b>", reply_markup=content_type_menu(), parse_mode="HTML")
    await call.answer()

@admin_panel.callback_query(F.data.startswith("admin_content_"))
async def open_content_menu(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    ctype = call.data.split("_")[-1]
    name = "START" if ctype == "start" else "INFO"
    await call.message.edit_text(f"ℹ️ <b>{name} Sozlamalari</b>", reply_markup=content_settings_menu(ctype), parse_mode="HTML")
    await call.answer()

@admin_panel.callback_query(F.data.startswith("admin_set_text_"))
async def prompt_infotext(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⚠️ Kechirasiz, ushbu buyruqdan foydalanish uchun sizda yetarli ruxsatlar yo'q.", show_alert=True)
        return
    ctype = call.data.split("_")[-1]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data=f"admin_content_{ctype}")]])
    await state.update_data(current_ctype=ctype)
    await call.message.edit_text(f"Yangi matnni yuboring (Formatlangan HTML ishlaydi):\n\n<i>Bu matn /{ctype} komandasi bosilganda chiqadi.</i>", reply_markup=kb, parse_mode="HTML")
    await state.set_state(AdminPanelState.waiting_for_info_text)
    await call.answer()

@admin_panel.callback_query(F.data.startswith("admin_set_video_"))
async def prompt_videolink(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⚠️ Kechirasiz, ushbu buyruqdan foydalanish uchun sizda yetarli ruxsatlar yo'q.", show_alert=True)
        return
    ctype = call.data.split("_")[-1]
    key = f"{ctype}_video_id"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data=f"admin_content_{ctype}")]])
    current = await get_setting(key, "O'rnatilmagan")
    status = "✅ Video o'rnatilgan" if current not in ("O'rnatilmagan", "O'chirilgan") else "❌ O'rnatilmagan / O'chirilgan"
    await state.update_data(current_ctype=ctype)
    await call.message.edit_text(f"Video darslikni botga <b>yuboring yoki uzating (forward)</b>.\n\nHozirgi holat: {status}\n\n<i>Faqat video fayl qabul qilinadi.</i>", reply_markup=kb, parse_mode="HTML")
    await state.set_state(AdminPanelState.waiting_for_video_link)
    await call.answer()

@admin_panel.callback_query(F.data.startswith("admin_del_text_"))
async def del_infotext(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    ctype = call.data.split("_")[-1]
    key = f"{ctype}_text"
    await set_setting(key, "O'chirilgan")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"admin_content_{ctype}")]])
    await call.message.edit_text(f"✅ /{ctype} matni muvaffaqiyatli o'chirildi!", reply_markup=kb)
    await call.answer()

@admin_panel.callback_query(F.data.startswith("admin_del_video_"))
async def del_videolink(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    ctype = call.data.split("_")[-1]
    key = f"{ctype}_video_id"
    await set_setting(key, "O'chirilgan")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"admin_content_{ctype}")]])
    await call.message.edit_text(f"✅ /{ctype} video muvaffaqiyatli o'chirildi!", reply_markup=kb)
    await call.answer()

# --- ADMIN PROFILE ---
def profile_settings_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Bosh Karta Raqami", callback_data="admin_set_cardnumber")],
        [InlineKeyboardButton(text="💎 Premium Narxlari", callback_data="admin_menu_prem_prices")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_menu_main")]
    ])

@admin_panel.callback_query(F.data == "admin_menu_profile")
async def ds_profile(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return
    await call.message.edit_text("👤 <b>Admin Profile Sozlamalari</b>", reply_markup=profile_settings_menu(), parse_mode="HTML")
    await call.answer()

@admin_panel.callback_query(F.data == "admin_set_cardnumber")
async def prompt_cardnumber(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⚠️ Kechirasiz, ushbu buyruqdan foydalanish uchun sizda yetarli ruxsatlar yo'q.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_menu_profile")]])
    current = await get_setting("card_number", "O'rnatilmagan")
    await call.message.edit_text(f"To'lovlar uchun bot ko'rsatadigan karta raqami (va Ism).\nHozirgi: {current}\n\nYangi karta raqamini yuboring (Masalan: 8600 0000 0000 0000 (Eshmatov)):", reply_markup=kb)
    await state.set_state(AdminPanelState.waiting_for_card_number)
    await call.answer()

@admin_panel.callback_query(F.data == "admin_menu_prem_prices")
async def ds_prem_prices(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id if hasattr(call, 'from_user') else call.from_user.id): return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 oy narxi", callback_data="admin_set_prem_1")],
        [InlineKeyboardButton(text="3 oy narxi", callback_data="admin_set_prem_3")],
        [InlineKeyboardButton(text="6 oy narxi", callback_data="admin_set_prem_6")],
        [InlineKeyboardButton(text="12 oy narxi", callback_data="admin_set_prem_12")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_menu_profile")]
    ])
    await call.message.edit_text("💎 <b>Premium Narxlari</b>\n\nQaysi tarif narxini o'zgartirmoqchisiz?", reply_markup=kb, parse_mode="HTML")
    await call.answer()

from aiogram.fsm.state import StatesGroup, State
class PremPriceState(StatesGroup):
    waiting_for_price = State()

async def prompt_prem_price(call: types.CallbackQuery, state: FSMContext, months: int, default_price: int):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_menu_prem_prices")]])
    current = await get_setting(f"premium_price_{months}", str(default_price))
    await call.message.edit_text(f"{months} oylik premium narxini kiriting (faqat son, UZS da).\nHozirgi narx: {current} UZS\n\nYangi narxni yuboring:", reply_markup=kb)
    await state.update_data(current_prem_months=months)
    await state.set_state(PremPriceState.waiting_for_price)
    await call.answer()

@admin_panel.callback_query(F.data.startswith("admin_set_prem_"))
async def handle_set_prem_price(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⚠️ Kechirasiz, ushbu buyruqdan foydalanish uchun sizda yetarli ruxsatlar yo'q.", show_alert=True)
        return
    months = int(call.data.split("_")[-1])
    defaults = {1: 20000, 3: 50000, 6: 90000, 12: 150000}
    await prompt_prem_price(call, state, months, defaults.get(months, 0))

# --- MESSAGE HANDLERS FOR SAVING ---

async def save_and_confirm(message: types.Message, state: FSMContext, key: str, value: str, menu_callback: str):
    await set_setting(key, value)
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data=menu_callback)]])
    await message.answer(f"✅ Qabul qilindi!\n\n<code>{key}</code> = {value}", reply_markup=kb, parse_mode="HTML")

@admin_panel.message(AdminPanelState.waiting_for_sms_token)
async def process_smstoken(message: types.Message, state: FSMContext):
    await save_and_confirm(message, state, "sms_bot_username", message.text, "admin_menu_channel")

@admin_panel.message(AdminPanelState.waiting_for_withdraw_id)
async def process_withdrawid(message: types.Message, state: FSMContext):
    await save_and_confirm(message, state, "withdrawal_channel_id", message.text, "admin_menu_channel")

@admin_panel.message(AdminPanelState.waiting_for_premium_id)
async def process_premiumid(message: types.Message, state: FSMContext):
    await save_and_confirm(message, state, "premium_channel_id", message.text, "admin_menu_channel")

@admin_panel.message(AdminPanelState.waiting_for_support_id)
async def process_supportid(message: types.Message, state: FSMContext):
    await save_and_confirm(message, state, "support_group_id", message.text, "admin_menu_channel")

@admin_panel.message(AdminPanelState.waiting_for_error_id)
async def process_errorid(message: types.Message, state: FSMContext):
    await save_and_confirm(message, state, "error_channel_id", message.text, "admin_menu_channel")

@admin_panel.message(AdminPanelState.waiting_for_ref_days)
async def process_refdays(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat raqam kiriting:")
        return
    await save_and_confirm(message, state, "ref_days", message.text, "admin_menu_referral")

@admin_panel.message(AdminPanelState.waiting_for_ref_count)
async def process_refcount(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat raqam kiriting:")
        return
    await save_and_confirm(message, state, "ref_count", message.text, "admin_menu_referral")

@admin_panel.message(AdminPanelState.waiting_for_ref_percent)
async def process_refpercent(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat raqam kiriting:")
        return
    await save_and_confirm(message, state, "ref_conversion_percent", message.text, "admin_menu_referral")

@admin_panel.message(AdminPanelState.waiting_for_info_text)
async def process_infotext(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ctype = data.get("current_ctype", "start")
    key = f"{ctype}_text"
    await save_and_confirm(message, state, key, message.text, f"admin_content_{ctype}")

@admin_panel.message(AdminPanelState.waiting_for_video_link, F.video)
async def process_videolink(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ctype = data.get("current_ctype", "start")
    key = f"{ctype}_video_id"
    video_id = message.video.file_id
    await save_and_confirm(message, state, key, video_id, f"admin_content_{ctype}")

@admin_panel.message(AdminPanelState.waiting_for_video_link)
async def process_videolink_fallback(message: types.Message, state: FSMContext):
    await message.answer("Iltimos, faqat video yuboring (yoki videoni forward qiling).")

@admin_panel.message(AdminPanelState.waiting_for_card_number)
async def process_cardnumber(message: types.Message, state: FSMContext):
    await save_and_confirm(message, state, "card_number", message.text, "admin_menu_profile")

@admin_panel.message(PremPriceState.waiting_for_price)
async def process_prem_price_fallback(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat raqam kiriting:")
        return
    data = await state.get_data()
    months = data.get("current_prem_months", 1)
    await save_and_confirm(message, state, f"premium_price_{months}", message.text, "admin_menu_prem_prices")

@admin_panel.message(AdminPanelState.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    # Preview message sent by admin
    await message.copy_to(message.chat.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha", callback_data="bc_confirm_ha"),
         InlineKeyboardButton(text="❌ Yo'q", callback_data="bc_confirm_yoq")],
        [InlineKeyboardButton(text="✏️ Tahrirlash", callback_data="bc_confirm_tahrir")]
    ])
    
    await state.update_data(broadcast_message_id=message.message_id)
    await state.set_state(AdminPanelState.waiting_for_broadcast_confirm)
    
    await message.answer("Siz rostdan ham shu xabarni e'lon qilmoqchimisiz?", reply_markup=kb)

@admin_panel.callback_query(AdminPanelState.waiting_for_broadcast_confirm, F.data.startswith("bc_confirm_"))
async def process_broadcast_confirm(call: types.CallbackQuery, state: FSMContext):
    action = call.data.split("_")[-1]
    
    if action == "yoq":
        await state.clear()
        await call.message.edit_text("❌ E'lon yuborish bekor qilindi.")
        await call.answer()
        return
        
    elif action == "tahrir":
        await state.set_state(AdminPanelState.waiting_for_broadcast)
        await call.message.edit_text("Yangi xabarni yuboring (yoki forward qiling):")
        await call.answer()
        return
        
    elif action == "ha":
        data = await state.get_data()
        msg_id = data.get("broadcast_message_id")
        
        if not msg_id:
            await call.answer("Xabarni topib bo'lmadi.", show_alert=True)
            return
            
        import asyncio
        from database.models import User
        await state.clear()
        
        await call.message.edit_text("Siklda xabar yuborilmoqda, kuting...")
        success = 0
        fail = 0
        async with session_scope() as session:
            res = await session.execute(select(User.telegram_id))
            users = res.scalars().all()
            for uid in users:
                try:
                    await call.message.bot.copy_message(chat_id=uid, from_chat_id=call.message.chat.id, message_id=msg_id)
                    success += 1
                except Exception as e:
                    logging.error(f"Broadcast failed for {uid}: {e}")
                    fail += 1
                await asyncio.sleep(0.05)  # Telegram API flood-control protection
        
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_menu_channel")]])
        await call.message.edit_text(f"✅ E'lon hammaga yetkazildi!\n\nMuvaffaqiyatli: {success}\nXato: {fail}", reply_markup=kb)
        await call.answer()
