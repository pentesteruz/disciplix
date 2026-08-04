"""
Premium huquqi — ilgari ikki xil tekshiruv ikki xil natija berardi va
`is_premium` bayrog'i hech qachon False ga qaytmagani uchun bir marta to'lov
qilgan foydalanuvchi umrbod premium bo'lib qolardi.
"""

from datetime import timedelta

from utils.premium import is_premium_active, sync_premium_flag
from utils.timezone import get_tashkent_time


class FakeUser:
    def __init__(self, premium_until=None, is_premium=False):
        self.premium_until = premium_until
        self.is_premium = is_premium


def test_amaldagi_obuna_faol():
    user = FakeUser(premium_until=get_tashkent_time() + timedelta(days=5))
    assert is_premium_active(user) is True


def test_muddati_tugagan_obuna_faol_emas():
    user = FakeUser(premium_until=get_tashkent_time() - timedelta(days=1))
    assert is_premium_active(user) is False


def test_eski_bayroq_umrbod_premium_bermaydi():
    """Asosiy regressiya: is_premium=True muddati tugaganini bekor qila olmaydi."""
    user = FakeUser(premium_until=get_tashkent_time() - timedelta(days=30), is_premium=True)
    assert is_premium_active(user) is False


def test_sanasiz_bayroq_huquq_bermaydi():
    user = FakeUser(premium_until=None, is_premium=True)
    assert is_premium_active(user) is False


def test_hech_qachon_premium_bolmagan():
    assert is_premium_active(FakeUser()) is False


def test_sync_bayroqni_haqiqiy_holatga_keltiradi():
    user = FakeUser(premium_until=get_tashkent_time() - timedelta(days=1), is_premium=True)
    assert sync_premium_flag(user) is False
    assert user.is_premium is False

    user2 = FakeUser(premium_until=get_tashkent_time() + timedelta(days=1), is_premium=False)
    assert sync_premium_flag(user2) is True
    assert user2.is_premium is True
