from datetime import datetime, timedelta, timezone

TASHKENT_OFFSET = timedelta(hours=5)
TASHKENT_TZ = timezone(TASHKENT_OFFSET, name="UTC+5")


def get_tashkent_time() -> datetime:
    """
    Toshkent vaqtidagi hozirgi payt, naive datetime ko'rinishida.

    Naive qaytariladi, chunki bazadagi barcha DateTime ustunlari timezone'siz.
    Aware qiymat qaytarilsa, ular bilan taqqoslash TypeError beradi.

    Muhim: modellardagi default qiymatlar ham shu funksiyaga bog'langan. Ilgari
    bir qismi `func.now()` (server UTC vaqti) edi va shu sababli bitta jadvalda
    5 soat farq bilan yozilgan sanalar aralashib ketardi.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None) + TASHKENT_OFFSET


def to_tashkent(dt: datetime) -> datetime:
    """UTC (yoki aware) datetime'ni Toshkent naive vaqtiga o'tkazadi."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(TASHKENT_TZ).replace(tzinfo=None)
    return dt + TASHKENT_OFFSET
