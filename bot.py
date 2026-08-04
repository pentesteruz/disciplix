import asyncio
import logging
import sys
import time
from collections import defaultdict, deque
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from database.engine import init_db
from handlers import start, finance, tasks, ai_chat, dreams, menu, admin_panel, user_deletion, salary

async def main():
    # Logging Configuration
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Initialize Bot and Dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # --- RATE LIMITER ---
    # Tracks per-user message timestamps to prevent spam/abuse
    _user_timestamps: dict = defaultdict(lambda: deque())
    RATE_LIMIT_MAX = 20     # max messages
    RATE_LIMIT_WINDOW = 10  # seconds
    RATE_LIMIT_COOLDOWN = 30  # seconds cooldown after being rate-limited
    _last_sweep = 0.0

    def _sweep_stale_users(now: float):
        """Faol bo'lmagan foydalanuvchilarni chiqarib tashlaydi — aks holda dict
        har bir ko'rilgan foydalanuvchi uchun abadiy o'sib boradi."""
        stale = [uid for uid, ts in _user_timestamps.items()
                 if not ts or now - ts[-1] > RATE_LIMIT_WINDOW]
        for uid in stale:
            del _user_timestamps[uid]

    async def rate_limit_middleware(handler, event, data):
        nonlocal _last_sweep
        from aiogram import types as tg_types
        is_msg = isinstance(event, tg_types.Message)
        is_cb  = isinstance(event, tg_types.CallbackQuery)
        if not is_msg and not is_cb:
            return await handler(event, data)

        user_id = event.from_user.id if event.from_user else None
        if not user_id:
            return await handler(event, data)

        now = time.monotonic()
        if now - _last_sweep > 300:
            _sweep_stale_users(now)
            _last_sweep = now

        timestamps = _user_timestamps[user_id]
        # Evict old timestamps outside the window
        while timestamps and now - timestamps[0] > RATE_LIMIT_WINDOW:
            timestamps.popleft()

        if len(timestamps) >= RATE_LIMIT_MAX:
            logging.warning(f"Rate limit triggered for user {user_id}")
            if is_msg:
                try:
                    await event.answer(
                        f"⏳ Juda ko'p xabar yuboryapsiz. Iltimos {RATE_LIMIT_COOLDOWN} soniya kuting."
                    )
                except Exception:
                    pass
            elif is_cb:
                try:
                    await event.answer(
                        f"⏳ Juda tez bosdingiz. {RATE_LIMIT_COOLDOWN} soniya kuting.",
                        show_alert=True
                    )
                except Exception:
                    pass
            return  # Block the update

        timestamps.append(now)
        return await handler(event, data)

    # Tartib muhim: rate limiter birinchi bo'lishi kerak, aks holda spam qilingan
    # har bir xabar bloklanishidan oldin baza so'roviga sabab bo'ladi.
    from handlers.start import check_frozen_middleware
    dp.message.outer_middleware(rate_limit_middleware)
    dp.callback_query.outer_middleware(rate_limit_middleware)
    dp.message.outer_middleware(check_frozen_middleware)
    dp.callback_query.outer_middleware(check_frozen_middleware)

    # Register Routers (Order matters: finance.router has catch-all F.text)
    dp.include_router(start.router)
    dp.include_router(dreams.router)
    dp.include_router(tasks.router)
    dp.include_router(ai_chat.router)
    dp.include_router(menu.router)
    dp.include_router(admin_panel.admin_panel)
    dp.include_router(user_deletion.router)
    dp.include_router(salary.router)
    dp.include_router(finance.router)

    # Initialize Database
    await init_db()

    # --- USERBOT ---
    from services.userbot_service import create_userbot, set_aiogram_bot
    set_aiogram_bot(bot)
    userbot = None
    userbot = create_userbot()
    if userbot:
        try:
            await userbot.start()
            logging.info("Pyrogram Userbot started successfully.")
        except Exception as e:
            logging.error(f"Failed to start Userbot: {e}")
            userbot = None

    # --- SCHEDULER ---
    from services.scheduler import start_scheduler
    start_scheduler(bot)

    # --- WEB SERVER QISMI ---
    from aiohttp import web
    import os
    from web.routes import setup_routes
    
    app = web.Application()
    app['bot'] = bot
    
    # Setup Routes
    setup_routes(app)
    
    # CORS setup (REQUIRED for Web App)
    # CORS faqat WEBAPP_URL o'rnatilganda sozlanadi. Bo'sh satrni origin sifatida
    # berish aiohttp_cors uchun yaroqsiz kalit yaratadi.
    import aiohttp_cors
    from config import WEBAPP_URL
    if WEBAPP_URL:
        cors = aiohttp_cors.setup(app, defaults={
            WEBAPP_URL: aiohttp_cors.ResourceOptions(
                allow_credentials=False,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*",
            )
        })
        for route in list(app.router.routes()):
            try:
                cors.add(route)
            except (ValueError, RuntimeError) as e:
                logging.debug(f"CORS skipped for {route}: {e}")
    else:
        logging.warning("WEBAPP_URL yo'q — CORS sozlanmadi (bir originli rejim).")

    runner = web.AppRunner(app)
    await runner.setup()
    
    # Force port 8081 to avoid conflicts
    port = int(os.environ.get("PORT", 8081))
    site = web.TCPSite(runner, "0.0.0.0", port)

    
    # --- PARALLEL ISHGA TUSHIRISH ---
    logging.info(f"Web server running on port {port}")
    logging.info("SYSTEM READY: DATABASE SYNCED")
    # --- STARTUP LOGIC: WEBHOOK vs POLLING ---
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

    if WEBHOOK_URL:
        # --- WEBHOOK MODE ---
        logging.info(f"SWITCHING TO WEBHOOK MODE: {WEBHOOK_URL}")
        
        # 1. Set Webhook
        webhook_path = "/webhook"
        full_webhook_url = f"{WEBHOOK_URL}{webhook_path}"
        
        WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "").strip()
        if not WEBHOOK_SECRET:
            raise RuntimeError(
                "WEBHOOK_URL o'rnatilgan, lekin WEBHOOK_SECRET yo'q. "
                "Sirsiz webhook rejimi har kimga soxta Telegram update yuborish imkonini beradi. "
                "Railway Variables'ga tasodifiy WEBHOOK_SECRET qo'shing (masalan: python -c \"import secrets; print(secrets.token_urlsafe(32))\")."
            )

        try:
            current_webhook = await bot.get_webhook_info()
            if current_webhook.url != full_webhook_url:
                logging.info(f"Setting webhook to: {full_webhook_url}")
                await bot.set_webhook(full_webhook_url, drop_pending_updates=True, secret_token=WEBHOOK_SECRET)
            else:
                # Ensure the secret token is set even if URL matches
                await bot.set_webhook(full_webhook_url, drop_pending_updates=True, secret_token=WEBHOOK_SECRET)
                logging.info("Webhook set/updated correctly.")
        except Exception as e:
            logging.error(f"Failed to set webhook: {e}")

        # 2. Add Webhook Handler to existing aiohttp app
        from aiogram.types import Update
        
        import hmac

        async def handle_webhook(request):
            provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if not hmac.compare_digest(provided, WEBHOOK_SECRET):
                return web.Response(text="Unauthorized", status=401)
            try:
                data = await request.json()
                update = Update.model_validate(data, context={"bot": bot})
                await dp.feed_update(bot, update)
                return web.Response(text="OK")
            except Exception as e:
                logging.error(f"Webhook update error: {e}")
                return web.Response(text="Error", status=500)

        app.router.add_post(webhook_path, handle_webhook)
        logging.info(f"Webhook handler registered at {webhook_path}")

        # 3. Start Web Server Only (No Polling)
        # Note: We already start 'site' below, so we just don't add dp.start_polling()
        
        try:
            # Only start the web server
            await site.start()
            
            # Keep the app running indefinitely
            # standard asyncio.Event wait or similar
            shutdown_event = asyncio.Event()
            await shutdown_event.wait()
            
        finally:
            if 'userbot' in locals() and userbot:
                await userbot.stop()
            await bot.session.close()
            await dp.storage.close()
            from database.engine import dispose_db
            await dispose_db()
            logging.info("Bot shutdown cleanly.")

    else:
        # --- POLLING MODE (Fallback/Local) ---
        logging.info("STARTING IN POLLING MODE")
        
        # Webhook removal with retry logic
        retry_count = 0
        max_retries = 3
        while retry_count < max_retries:
            try:
                webhook_info = await bot.get_webhook_info()
                if webhook_info.url:
                    logging.info(f"WEBHOOK DETECTED: {webhook_info.url}")
                    await bot.delete_webhook(drop_pending_updates=True)
                    logging.info("Webhook deleted.")
                    await asyncio.sleep(1) # Give Telegram time to propagate
                else:
                    logging.info("No active webhook found.")
                    break
            except Exception as e:
                logging.error(f"Error checking/deleting webhook: {e}")
                await asyncio.sleep(1)
                retry_count += 1
        
        if retry_count == max_retries:
            logging.info("WARNING: Could not clear webhook after retries. Polling might fail.")
        
        # Message Logging Middleware
        @dp.message.outer_middleware
        async def log_messages(handler, event, data):
            if event.text:
                logging.info(f"XABAR KELDI: {event.text}")
            return await handler(event, data)

        try:
            await asyncio.gather(
                site.start(),
                dp.start_polling(bot)
            )
        finally:
            if ('userbot' in globals() or 'userbot' in locals()) and userbot:
                 try: await userbot.stop()
                 except: pass # Ignore if not running
            await bot.session.close()
            await dp.storage.close()
            from database.engine import dispose_db
            await dispose_db()
            logging.info("Bot shutdown cleanly.")

if __name__ == "__main__":
    try:
        # Windows selector event loop policy fix might be needed if asyncio.run fails
        if sys.platform == 'win32':
             asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass