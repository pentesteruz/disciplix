"""
Premium huquqini aniqlashning yagona manbai.

Ilgari kodda ikki xil tekshiruv bor edi:

    getattr(user, 'is_premium', False) or (user.premium_until and user.premium_until > now)
    # va
    user.premium_until > now if user.premium_until else user.is_premium

Birinchisi `is_premium` bayrog'i hech qachon False ga qaytarilmagani uchun bir marta
to'lov qilgan foydalanuvchini umrbod premium qilib qo'yardi; ikkinchisi esa muddat
tugagach False qaytarardi. Natijada dashboard ochiq, lekin limitlar yopiq bo'lardi.

Endi yagona qoida: premium `premium_until` bilan belgilanadi. `is_premium` — faqat
denormalizatsiya qilingan kesh, u `sync_premium_flag()` orqali yangilanadi.
"""

from utils.timezone import get_tashkent_time


def is_premium_active(user) -> bool:
    """Foydalanuvchida hozir amal qiluvchi premium bor-yo'qligi."""
    premium_until = getattr(user, "premium_until", None)
    if not premium_until:
        return False
    return premium_until > get_tashkent_time()


def sync_premium_flag(user) -> bool:
    """`is_premium` keshini `premium_until` ga moslaydi va joriy holatni qaytaradi."""
    active = is_premium_active(user)
    if getattr(user, "is_premium", None) != active:
        user.is_premium = active
    return active
