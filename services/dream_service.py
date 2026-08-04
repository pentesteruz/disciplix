"""
Orzu sig'imi — foydalanuvchi kuniga qancha ajrata oladi.

MUAMMO
------
Ilgari orzu qo'shishda 50% / 100% / 150% variantlari foydalanuvchining TO'LIQ
kunlik ortiqcha pulidan hisoblanardi. Ikkinchi orzu qo'shilganda ham xuddi
o'sha raqamlar chiqardi, holbuki birinchi orzu allaqachon sig'imning bir
qismini band qilgan.

Misol: kunlik 100 000 ortiqcha. Birinchi orzuga 50% → 50 000.
Qolgani 50 000. Lekin ikkinchi orzu uchun ham 50 000 / 100 000 / 150 000
taklif qilinardi — ya'ni bajarib bo'lmaydigan majburiyat.

Endi foizlar QOLGAN sig'imdan hisoblanadi: 25 000 / 50 000 / 75 000.
"""

from dataclasses import dataclass

from sqlalchemy import func, select

from database.models import Dream

# Foydalanuvchiga taklif qilinadigan standart ulushlar.
# 150% ataylab sig'imdan oshadi — bu "o'zini qiynash" varianti.
STANDARD_SHARES = (0.5, 1.0, 1.5)


@dataclass
class DreamCapacity:
    daily_limit: float          # foydalanuvchining kunlik limiti
    committed: float            # faol orzular allaqachon band qilgan kunlik summa
    available: float            # qolgan sig'im
    options: list               # taklif qilinadigan variantlar

    @property
    def is_full(self) -> bool:
        return self.available <= 0


async def get_capacity(session, user) -> DreamCapacity:
    """Foydalanuvchining qolgan kunlik orzu sig'imini hisoblaydi."""
    daily_limit = float(getattr(user, "daily_limit", 0) or 0)

    committed = (await session.execute(
        select(func.sum(Dream.daily_limit_target)).where(
            Dream.user_id == user.id,
            Dream.is_active == True,  # noqa: E712 — SQLAlchemy solishtiruvi
        )
    )).scalar() or 0.0
    committed = float(committed)

    available = max(0.0, daily_limit - committed)

    options = [
        {
            "share": share,
            "label": f"{int(share * 100)}%",
            "amount": round(available * share, 2),
            # 100% dan ortig'i qolgan sig'imdan oshadi
            "exceeds_capacity": share > 1.0,
        }
        for share in STANDARD_SHARES
    ]

    return DreamCapacity(
        daily_limit=daily_limit,
        committed=committed,
        available=available,
        options=options,
    )


def validate_daily_target(capacity: DreamCapacity, requested: float):
    """
    So'ralgan kunlik summani baholaydi.

    Taqiqlamaydi — bu foydalanuvchining o'z puli va u ataylab qiyin maqsad
    qo'yishi mumkin. Lekin sig'imdan oshsa ochiq ogohlantiradi.

    Qaytaradi: (ruxsat_berilsinmi, ogohlantirish_matni_yoki_None)
    """
    if requested <= 0:
        return False, "Kunlik summa noldan katta bo'lishi kerak."

    if capacity.daily_limit <= 0:
        # Limit hali belgilanmagan — tekshiradigan narsa yo'q
        return True, None

    if capacity.is_full:
        return False, (
            "Kunlik limitingiz allaqachon to'liq band. "
            f"Faol orzularingiz kuniga {capacity.committed:,.0f} talab qiladi. "
            "Yangi orzu qo'shishdan oldin birortasini yakunlang yoki bekor qiling."
        )

    if requested > capacity.available:
        oshgan = requested - capacity.available
        return True, (
            f"Diqqat: bu summa qolgan kunlik sig'imingizdan {oshgan:,.0f} oshadi. "
            f"Sizda kuniga {capacity.available:,.0f} bo'sh edi."
        )

    return True, None
