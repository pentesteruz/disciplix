import asyncio
from typing import Callable, Any
from aiogram.types import Message
from services.context import current_message
import logging

class UserQueueManager:
    def __init__(self):
        self.user_locks = {}
        self.global_semaphore = asyncio.Semaphore(15) # Max concurrent requests

    def _get_lock(self, user_id) -> asyncio.Lock:
        """
        Foydalanuvchi uchun lock beradi va band bo'lmaganlarini tozalaydi.
        Ilgari bu dict hech qachon tozalanmasdi — har ko'rilgan foydalanuvchi
        uchun Lock abadiy qolib, xotira asta o'sib borardi.
        """
        if len(self.user_locks) > 1000:
            for uid, lock in list(self.user_locks.items()):
                if uid != user_id and not lock.locked():
                    del self.user_locks[uid]

        if user_id not in self.user_locks:
            self.user_locks[user_id] = asyncio.Lock()
        return self.user_locks[user_id]

    async def process(self, event: Any, coro_func: Callable, *args, **kwargs) -> Any:
        from aiogram.types import CallbackQuery, Message
        if isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            message = event.message
        else:
            user_id = event.from_user.id
            message = event

        lock = self._get_lock(user_id)

        async with lock:
            async with self.global_semaphore:
                # Set context var for retries
                token = current_message.set(message)
                
                # 1. Typing action immediately (T0)
                try:
                    await message.bot.send_chat_action(chat_id=message.chat.id, action='typing')
                except Exception:
                    pass
                
                thinking_msg = None
                
                # 2. After 2 seconds, if not done, send "O'ylayapman..." (T2)
                async def show_thinking():
                    nonlocal thinking_msg
                    await asyncio.sleep(2)
                    try:
                        thinking_msg = await message.reply("🤔 Tahlil qilinmoqda, ozroq kuting...")
                    except Exception:
                        pass
                
                thinking_task = asyncio.create_task(show_thinking())
                
                try:
                    result = await coro_func(*args, **kwargs)
                    return result
                finally:
                    # Clean up
                    thinking_task.cancel()
                    if thinking_msg:
                        try:
                            await thinking_msg.delete()
                        except Exception:
                            pass
                    current_message.reset(token)

ai_queue = UserQueueManager()
