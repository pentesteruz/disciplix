from pyrogram import Client
import asyncio
from config import API_ID, API_HASH

async def generate():
    if not API_ID or not API_HASH:
        print("API_ID yoki API_HASH .env faylida topilmadi!")
        return

    print("Pyrogram Client ishga tushyapti. Agar so'rasa telefon raqam va kodni kiriting...")
    
    # Using the existing local session if available to avoid re-login, 
    # but export it to a string format.
    app = Client("my_account", api_id=int(API_ID), api_hash=API_HASH, workdir=".")
    
    await app.start()
    session_string = await app.export_session_string()
    await app.stop()
    
    print("\n\n" + "="*60)
    print("YANGI 'SESSION_STRING' YARATILDI:")
    print("="*60)
    print(session_string)
    print("="*60)
    print("\n☝️ Tepadagi uzun matnni nusxalab oling va Railway'dagi 'Variables' qismiga qo'shing!")
    print("Nomi: SESSION_STRING")
    print("Qiymati: (tepadagi matn)")

if __name__ == "__main__":
    asyncio.run(generate())
