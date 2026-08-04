"""
`users.balance` ustunini tranzaksiyalardan qayta hisoblaydi.

NIMA UCHUN KERAK
----------------
Ilgari balans ikki manbadan kelardi:
  1. ro'yxatdan o'tishda `balance = monthly_income` deb urug'lantirilardi,
  2. keyin har tranzaksiyada `balance += / -=` qilinardi,
  3. dashboard esa buni umuman o'qimay, o'zi qayta hisoblardi (va ustiga
     yana `monthly_income` ni qo'shardi).

Natijada bazadagi `balance` haqiqatdan uzoqlashgan va oylik ikki marta
hisoblangan. Endi yagona qoida: balans = barcha tranzaksiyalar yig'indisi.

Bu skript eski `balance` qiymatlarini shu qoidaga keltiradi.

ISHLATISH
---------
    python -m scripts.recalculate_balances            # quruq ishlash
    python -m scripts.recalculate_balances --apply    # yozish

DIQQAT: --apply dan oldin bazadan zaxira nusxa oling.
"""

import argparse
import asyncio

from sqlalchemy import select

from database.engine import dispose_db, session_scope
from database.models import User
from services.finance_service import compute_balance


async def recalculate(apply: bool):
    ozgarganlar = []

    async with session_scope() as session:
        users = (await session.execute(select(User))).scalars().all()

        for user in users:
            eski = float(user.balance or 0)
            base = (user.base_currency or "UZS").upper()
            yangi = round(await compute_balance(session, user.id, base), 2)

            if abs(eski - yangi) < 0.01:
                continue

            ozgarganlar.append((user.telegram_id, eski, yangi, float(user.monthly_income or 0)))
            if apply:
                user.balance = yangi

        if apply:
            await session.commit()

    print(f"Jami foydalanuvchi: {len(users)}")
    print(f"Balansi mos kelmaydi: {len(ozgarganlar)}")
    print()

    if ozgarganlar:
        print(f"{'telegram_id':>13} {'eski balans':>16} {'yangi balans':>16} {'oylik':>14}")
        print("-" * 64)
        for tid, eski, yangi, oylik in ozgarganlar[:30]:
            print(f"{tid:>13} {eski:>16,.0f} {yangi:>16,.0f} {oylik:>14,.0f}")
        if len(ozgarganlar) > 30:
            print(f"  ... yana {len(ozgarganlar) - 30} ta")
        print()
        print("Eslatma: eski balans ko'pincha oylik miqdoricha katta bo'ladi —")
        print("aynan shu ikki marta hisoblash tuzatilmoqda.")
        print()

    if apply:
        print(f"YOZILDI: {len(ozgarganlar)} foydalanuvchining balansi qayta hisoblandi.")
    else:
        print("QURUQ ISHLASH: hech narsa o'zgartirilmadi. Yozish uchun --apply qo'shing.")


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="O'zgarishlarni bazaga yozadi")
    args = parser.parse_args()
    try:
        await recalculate(apply=args.apply)
    finally:
        await dispose_db()


if __name__ == "__main__":
    asyncio.run(main())
