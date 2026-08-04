"""
Vaqt zonasi izchilligi.

Ilgari kod `get_tashkent_time()` (UTC+5) yozardi, modellardagi default qiymatlar
esa `func.now()` — ya'ni server UTC vaqti. Natijada bitta jadvalda 5 soat farq
bilan yozilgan sanalar aralashib, "bugungi" hisob-kitoblar buzilardi.
"""

from datetime import datetime, timedelta, timezone

from database.models import Dream, DreamProgress, Task, Transaction, User
from utils.timezone import get_tashkent_time, to_tashkent


def test_toshkent_vaqti_utc_dan_5_soat_oldinda():
    utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
    farq = get_tashkent_time() - utc_now
    assert timedelta(hours=4, minutes=59) < farq < timedelta(hours=5, minutes=1)


def test_naive_qaytaradi():
    """Baza ustunlari timezone'siz — aware qiymat taqqoslashda TypeError berardi."""
    assert get_tashkent_time().tzinfo is None


def test_bazadagi_sana_bilan_taqqoslash_ishlaydi():
    saqlangan = get_tashkent_time() - timedelta(days=1)
    assert saqlangan < get_tashkent_time()


def test_to_tashkent_aware_qiymatni_ogiradi():
    aware = datetime(2026, 8, 3, 8, 0, tzinfo=timezone.utc)
    assert to_tashkent(aware) == datetime(2026, 8, 3, 13, 0)


def test_to_tashkent_none_ni_qaytaradi():
    assert to_tashkent(None) is None


def test_barcha_sana_defaultlari_bitta_manbadan():
    """Regressiya: hech bir ustun DB server vaqtiga qaytmasligi kerak."""
    ustunlar = [
        User.__table__.c.created_at,
        User.__table__.c.last_active,
        Dream.__table__.c.created_at,
        Task.__table__.c.created_at,
        Transaction.__table__.c.timestamp,
        DreamProgress.__table__.c.date,
    ]
    utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
    for ustun in ustunlar:
        default = ustun.default
        assert default is not None, f"{ustun} uchun default yo'q"
        # func.now() SQL ifodasi bo'lardi va server UTC vaqtini bergan bo'lardi.
        assert not default.is_clause_element, f"{ustun} hali ham SQL server vaqtida"
        assert default.is_callable, f"{ustun} Python default emas"

        # SQLAlchemy callable'ni context qabul qiladigan qilib o'raydi.
        qiymat = default.arg(None)
        assert qiymat.tzinfo is None
        assert timedelta(hours=4, minutes=59) < qiymat - utc_now < timedelta(hours=5, minutes=1), (
            f"{ustun} Toshkent vaqtini qaytarmadi"
        )
