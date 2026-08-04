# Orzular Sari Yo'l Telegram Bot

Bu loyiha foydalanuvchilarning moliyaviy maqsadlariga erishishda yordam beruvchi Telegram bot skeletidir.

## Xususiyatlari
- **Foydalanuvchilarni ro'yxatga olish**: Ism va ID saqlanadi.
- **Moliya**: Ovozli xabarlar orqali daromad va xarajatlarni kuzatish (Gemini AI yordamida).
- **Maqsadlar**: Moliyaviy maqsadlarni belgilash.
- **AI Chat**: Google Gemini bilan erkin suhbat.

## O'rnatish

1. Talab qilinadigan kutubxonalarni o'rnating:
   ```bash
   pip install -r requirements.txt
   ```

2. `.env` fayl yarating va quyidagilarni kiriting (yoki `config.py` ni o'zgartiring):
   ```env
   BOT_TOKEN=sizning_bot_tokeningiz
   GEMINI_API_KEY=sizning_gemini_api_keyingiz
   ADMIN_IDS=admin_id1,admin_id2
   DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
   ```

3. Botni ishga tushiring:
   ```bash
   python bot.py
   ```

## Texnologiyalar
- Python 3.10+
- Aiogram 3.x
- SQLAlchemy (PostgreSQL/SQLite)
- Google Gemini API
- Next.js (WebApp va Admin Panel)
