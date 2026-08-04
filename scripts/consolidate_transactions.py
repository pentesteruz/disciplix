"""
`finances` jadvalidagi boy maydonlarni `transactions` ga ko'chiradi.

NIMA UCHUN KERAK
----------------
Har bir pul harakati ikkita jadvalga yozilardi:

  finances      -> amount, category, item_type, description, ai_advice, entry_time (Toshkent vaqti)
  transactions  -> amount, category, type,                                timestamp (server UTC vaqti)

Ya'ni bir xil hodisa, lekin `transactions` da `description` va `ai_advice` bo'sh
qolardi, va vaqtlar 5 soat farq qilardi. Zaxira nusxada 16/16 qator mos keldi.

Endi manba — `transactions`. Bu skript yo'qolgan matnli maydonlarni `finances`
dan topib ko'chiradi. `finances` o'chirilmaydi — u tekshiruv tugagunicha turadi.

MOSLASHTIRISH
-------------
Jufti `user_id` + `amount` + vaqt oynasi bo'yicha topiladi. Vaqt farqi 5 soat
bo'lishi kutiladi (vaqt zonasi xatosi), shuning uchun oyna keng olingan.

ISHLATISH
---------
    python -m scripts.consolidate_transactions            # quruq ishlash
    python -m scripts.consolidate_transactions --apply    # yozish

DIQQAT: --apply dan oldin bazadan zaxira nusxa oling.
"""

import argparse
import asyncio
from datetime import timedelta

from sqlalchemy import select

from database.engine import dispose_db, session_scope
from database.models import Finance, Transaction

# Vaqt zonasi xatosi tufayli juftlar orasidagi kutilgan farq 5 soat.
# Oynani kengroq olamiz, chunki yozuvlar ketma-ket bo'lgan.
MATCH_WINDOW = timedelta(hours=6)


def _matches(finance, tx) -> bool:
    if finance.user_id != tx.user_id:
        return False
    if abs(float(finance.amount or 0) - float(tx.amount or 0)) > 0.01:
        return False
    if not finance.entry_time or not tx.timestamp:
        return False
    return abs(finance.entry_time - tx.timestamp) <= MATCH_WINDOW


async def consolidate(apply: bool):
    async with session_scope() as session:
        finances = (await session.execute(select(Finance).order_by(Finance.id))).scalars().all()
        transactions = (await session.execute(select(Transaction).order_by(Transaction.id))).scalars().all()

        print(f"finances:     {len(finances)} qator")
        print(f"transactions: {len(transactions)} qator")
        print()

        ishlatilgan = set()
        toldirildi = 0
        juftsiz_finance = []

        for finance in finances:
            juft = None
            for tx in transactions:
                if tx.id in ishlatilgan:
                    continue
                if _matches(finance, tx):
                    juft = tx
                    break

            if not juft:
                juftsiz_finance.append(finance)
                continue

            ishlatilgan.add(juft.id)

            ozgardi = False
            if not juft.description and finance.description:
                if apply:
                    juft.description = finance.description
                ozgardi = True
            if not juft.ai_advice and finance.ai_advice:
                if apply:
                    juft.ai_advice = finance.ai_advice
                ozgardi = True
            if ozgardi:
                toldirildi += 1

        juftsiz_tx = [t for t in transactions if t.id not in ishlatilgan]

        print(f"juftlashtirildi:      {len(ishlatilgan)}")
        print(f"maydonlari to'ldirildi: {toldirildi}")
        print()

        if juftsiz_finance:
            print(f"DIQQAT: {len(juftsiz_finance)} ta finances qatoriga juft topilmadi.")
            print("Bular transactions'da umuman yo'q — ya'ni yo'qoladigan ma'lumot:")
            for f in juftsiz_finance[:20]:
                print(f"  finances.id={f.id} user={f.user_id} {float(f.amount or 0):,.0f} "
                      f"{f.category} {f.entry_time}")
            if len(juftsiz_finance) > 20:
                print(f"  ... yana {len(juftsiz_finance) - 20} ta")
            print()

        if juftsiz_tx:
            print(f"Eslatma: {len(juftsiz_tx)} ta transactions qatoriga finances'da juft yo'q.")
            print("Bu normal — bu qatorlar allaqachon faqat transactions'ga yozilgan.")
            print()

        if apply:
            await session.commit()
            print("YOZILDI: transactions yangilandi. finances jadvali TEGILMADI.")
        else:
            print("QURUQ ISHLASH: hech narsa o'zgartirilmadi. Yozish uchun --apply qo'shing.")

        if juftsiz_finance:
            print()
            print("TAVSIYA: juftsiz qatorlarni ko'rib chiqing va kerak bo'lsa qo'lda")
            print("transactions'ga ko'chiring. finances'ni faqat shundan keyin o'chiring.")


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="O'zgarishlarni bazaga yozadi")
    args = parser.parse_args()
    try:
        await consolidate(apply=args.apply)
    finally:
        await dispose_db()


if __name__ == "__main__":
    asyncio.run(main())
