"""
`users.is_premium` keshini `premium_until` ga moslaydi.

NIMA UCHUN KERAK
----------------
Ilgari `is_premium` premium berilganda True qilinardi, lekin muddat tugaganda hech
qachon False ga qaytarilmasdi. Kirish tekshiruvi esa `is_premium OR premium_until >
now` shaklida edi — ya'ni bir marta to'lov qilgan foydalanuvchi umrbod premium
bo'lib qolardi.

Endi huquq faqat `premium_until` bo'yicha aniqlanadi (utils/premium.py), shuning
uchun `is_premium` ustuni faqat kesh. Bu skript uni haqiqatga moslaydi.

ISHLATISH
---------
Avval nima o'zgarishini ko'rish (hech narsa yozmaydi):
    python -m scripts.sync_premium_flags

Haqiqatan yozish:
    python -m scripts.sync_premium_flags --apply

DIQQAT: --apply dan oldin bazadan zaxira nusxa oling.
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from database.engine import dispose_db, session_scope
from database.models import User
from utils.premium import is_premium_active
from utils.timezone import get_tashkent_time


async def sync(apply: bool) -> int:
    now = get_tashkent_time()
    huquq_yoqotadi = []
    huquq_oladi = []

    async with session_scope() as session:
        users = (await session.execute(select(User))).scalars().all()

        for user in users:
            haqiqiy = is_premium_active(user)
            if bool(user.is_premium) == haqiqiy:
                continue
            qator = (user.telegram_id, user.premium_until)
            if user.is_premium and not haqiqiy:
                huquq_yoqotadi.append(qator)
            else:
                huquq_oladi.append(qator)
            if apply:
                user.is_premium = haqiqiy

        if apply:
            await session.commit()

    print(f"Hozirgi vaqt (Toshkent): {now:%Y-%m-%d %H:%M}")
    print(f"Jami foydalanuvchi: {len(users)}")
    print()
    print(f"is_premium=True, lekin obuna amal qilmaydi: {len(huquq_yoqotadi)}")
    for tid, until in huquq_yoqotadi:
        holat = f"muddati {until:%Y-%m-%d} da tugagan" if until else "premium_until YO'Q (legacy)"
        print(f"  - {tid}: {holat}")

    print()
    print(f"is_premium=False, lekin obuna amal qiladi: {len(huquq_oladi)}")
    for tid, until in huquq_oladi:
        print(f"  - {tid}: {until:%Y-%m-%d} gacha")

    print()
    if apply:
        print("YOZILDI: is_premium ustuni yangilandi.")
    else:
        print("QURUQ ISHLASH: hech narsa o'zgartirilmadi. Yozish uchun --apply qo'shing.")

    return len(huquq_yoqotadi) + len(huquq_oladi)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="O'zgarishlarni bazaga yozadi")
    args = parser.parse_args()

    try:
        await sync(apply=args.apply)
    finally:
        await dispose_db()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
