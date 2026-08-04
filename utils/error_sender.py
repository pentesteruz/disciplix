import logging
import traceback
import html
from sqlalchemy import select
from database.engine import session_scope
from database.models import Settings

async def send_error_to_channel(bot, error, context_name="Noma'lum", user_info="Noma'lum"):
    """
    Xatolikni ushlab, Admin panelda sozlangan Error Channelga yuboradi.
    """
    try:
        async with session_scope() as session:
            res = await session.execute(select(Settings).where(Settings.key == 'error_channel_id'))
            setting = res.scalars().first()
            channel_id = setting.value if setting and setting.value else None
        
        if not channel_id or channel_id == "O'rnatilmagan":
            return # Kanal ulanmagan
            
        tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        # Telegram xabar uzunligi limiti (4096). Juda uzun xatolarni qisqartiramiz.
        if len(tb_str) > 3000:
            tb_str = tb_str[-3000:]
            
        text = (
            f"🚨 <b>XATOLIK YUZ BERDI!</b>\n\n"
            f"📍 <b>Joylashuv:</b> {html.escape(context_name)}\n"
            f"👤 <b>Foydalanuvchi/Ma'lumot:</b> <code>{html.escape(str(user_info))}</code>\n"
            f"❌ <b>Xato turi:</b> {html.escape(str(error))}\n\n"
            f"🔍 <b>Batafsil (Traceback):</b>\n<pre><code class='language-python'>{html.escape(tb_str)}</code></pre>"
        )
        
        await bot.send_message(chat_id=channel_id, text=text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Error jo'natish tizimida xatolik: {e}")
