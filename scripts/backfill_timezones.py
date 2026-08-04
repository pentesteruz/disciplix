"""
Eski sanalarni UTC dan Toshkent vaqtiga o'tkazadi.

MUAMMO
------
Ilgari sana ustunlarining bir qismi `func.now()` bilan to'ldirilardi — bu
PostgreSQL serverining UTC vaqti. Ilova kodi esa `get_tashkent_time()` (UTC+5)
yozardi. Natijada bitta ustunda 5 soat farq bilan yozilgan sanalar aralashib
ketgan, va "bugungi xarajat" kabi hisob-kitoblar kechqurun noto'g'ri ishlagan.

Modellardagi default qiymatlar endi tuzatilgan, lekin ESKI qatorlar hali ham
UTC da. Bu skript ularni +5 soatga suradi.

CUTOFF NIMA UCHUN KERAK
-----------------------
Tuzatish deploy qilingandan KEYIN yozilgan qatorlar allaqachon Toshkent vaqtida.
Ularni ham surish 5 soat oldinga siljitib, ma'lumotni yana buzadi. Shuning uchun
faqat cutoff'dan OLDINGI qatorlar suriladi.

Cutoff sifatida tuzatish deploy qilingan paytni bering (UTC bo'yicha).

QAYSI USTUNLAR
--------------
Faqat `func.now()` bilan to'ldirilgan ustunlar. Kod har doim aniq qiymat bergan
ustunlar (masalan DreamProgress.date) TEGILMAYDI — ular allaqachon to'g'ri.

ISHLATISH
---------
    python -m scripts.backfill_timezones --cutoff "2026-08-03 12:00"
    python -m scripts.backfill_timezones --cutoff "2026-08-03 12:00" --apply

DIQQAT: --apply dan oldin bazadan zaxira nusxa oling. Skriptni IKKI MARTA
ishlatmang — har ishga tushishda yana 5 soat qo'shiladi.
"""

import argparse
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import func, select

from database.engine import dispose_db, session_scope
from database.models import Dream, PremiumRequest, Task, Transaction, User

SHIFT = timedelta(hours=5)

# (model, ustun, izoh) — faqat ilgari func.now() default'i bilan to'lgan ustunlar.
#
# Ro'yxat zaxira nusxadagi haqiqiy ma'lumot bilan tekshirilgan: ma'lum UTC ustuni
# (transactions.timestamp) va ma'lum Toshkent ustuni (finances.entry_time) bilan
# solishtirib, har bir ustunning qaysi vaqt zonasida ekani aniqlangan.
TARGETS = [
    (User, "created_at", "ro'yxatdan o'tgan vaqt (kod hech qachon o'zi yozmagan)"),
    (Transaction, "timestamp", "pul harakati vaqti (eski yozuvda berilmagan)"),
    (PremiumRequest, "created_at", "premium so'rovi vaqti"),
]

# TEGILMAYDIGAN ustunlar va sababi:
#
#   tasks.created_at    — kod har doim get_tashkent_time() bergan (finance.py,
#                         tasks.py, routes.py). Allaqachon to'g'ri.
#   users.last_active   — check_frozen_middleware har muloqotda Toshkent vaqtini
#                         yozadi. Allaqachon to'g'ri.
#   dream_progress.date — routes.py aniq Toshkent vaqtini beradi.
#
# ARALASH (qo'lda ko'rib chiqish kerak):
#
#   dreams.created_at   — yaratilishda UTC default, lekin handle_set_main_dream
#                         uni get_tashkent_time() ga o'zgartiradi. Zaxira nusxada
#                         ikkala tur ham uchradi, shuning uchun avtomatik
#                         surilmaydi — aks holda "asosiy qilingan" orzular
#                         5 soat oldinga siljib ketadi.
AMBIGUOUS = [
    (Dream, "created_at", "yaratilishda UTC, set_main dan keyin Toshkent — aralash"),
]


async def backfill(cutoff: datetime, apply: bool):
    print(f"Cutoff: {cutoff:%Y-%m-%d %H:%M} (bundan oldingi qatorlar suriladi)")
    print(f"Surish: +{SHIFT}")
    print()

    jami = 0
    async with session_scope() as session:
        for model, column_name, izoh in TARGETS:
            column = getattr(model, column_name)
            table = model.__tablename__

            soni = (await session.execute(
                select(func.count()).select_from(model).where(
                    column.is_not(None), column < cutoff
                )
            )).scalar() or 0

            eng_eski = (await session.execute(
                select(func.min(column)).where(column.is_not(None), column < cutoff)
            )).scalar()
            eng_yangi = (await session.execute(
                select(func.max(column)).where(column.is_not(None), column < cutoff)
            )).scalar()

            keyingi = (await session.execute(
                select(func.count()).select_from(model).where(column >= cutoff)
            )).scalar() or 0

            print(f"{table}.{column_name}  — {izoh}")
            print(f"   suriladi:    {soni} qator", end="")
            if soni:
                print(f"  ({eng_eski:%Y-%m-%d} … {eng_yangi:%Y-%m-%d})")
            else:
                print()
            print(f"   tegilmaydi:  {keyingi} qator (cutoff'dan keyin)")

            if apply and soni:
                # Surish Python tomonida bajariladi. SQL darajasida `column + SHIFT`
                # PostgreSQL'da ishlaydi, lekin SQLite'da qiymatni songa aylantirib
                # yuboradi — ya'ni skriptni sinovdan o'tkazib bo'lmasdi.
                qatorlar = (await session.execute(
                    select(model).where(column.is_not(None), column < cutoff)
                )).scalars().all()
                for qator in qatorlar:
                    setattr(qator, column_name, getattr(qator, column_name) + SHIFT)

            jami += soni
            print()

        # Aralash ustunlar — avtomatik tegilmaydi, faqat xabar beriladi.
        print("-" * 60)
        print("QO'LDA KO'RIB CHIQISH KERAK (bu skript tegmaydi):")
        for model, column_name, izoh in AMBIGUOUS:
            column = getattr(model, column_name)
            soni = (await session.execute(
                select(func.count()).select_from(model).where(
                    column.is_not(None), column < cutoff
                )
            )).scalar() or 0
            print(f"   {model.__tablename__}.{column_name}: {soni} qator — {izoh}")
        print()

        if apply:
            await session.commit()
            print(f"YOZILDI: jami {jami} qator +5 soatga surildi.")
        else:
            print(f"QURUQ ISHLASH: {jami} qator surilardi. Yozish uchun --apply qo'shing.")
            print()
            print("Tekshiring: 'suriladi' oralig'i haqiqatan eski ma'lumotmi?")
            print("Agar cutoff noto'g'ri bo'lsa, yangi qatorlar ham surilib ketadi.")


def parse_cutoff(raw: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"Sanani tushunmadim: {raw!r} (kutilgan: 'YYYY-MM-DD HH:MM')")


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cutoff", required=True, type=parse_cutoff,
                        help="Tuzatish deploy qilingan payt; bundan oldingi qatorlar suriladi")
    parser.add_argument("--apply", action="store_true", help="O'zgarishlarni bazaga yozadi")
    args = parser.parse_args()
    try:
        await backfill(args.cutoff, args.apply)
    finally:
        await dispose_db()


if __name__ == "__main__":
    asyncio.run(main())
