"""
WebApp initData tekshiruvi va kirish ma'lumotlarini validatsiya qilish.

Telegram imzosi muddatsiz amal qiladi, shuning uchun auth_date'ni o'zimiz
tekshirmasak, bir marta oqib ketgan initData cheksiz qayta ishlatiladi.
"""

import time

import pytest

from web.routes import (
    INIT_DATA_MAX_AGE_SECONDS,
    MAX_MONEY_VALUE,
    _parse_money,
    check_init_data_freshness,
)


def init_data(auth_date):
    return f"query_id=AAA&user=%7B%22id%22%3A1%7D&auth_date={auth_date}&hash=deadbeef"


def test_yangi_initdata_qabul_qilinadi():
    assert check_init_data_freshness(init_data(int(time.time()))) is True


def test_eski_initdata_rad_etiladi():
    eski = int(time.time()) - INIT_DATA_MAX_AGE_SECONDS - 60
    assert check_init_data_freshness(init_data(eski)) is False


def test_chegaradagi_initdata():
    deyarli = int(time.time()) - INIT_DATA_MAX_AGE_SECONDS + 60
    assert check_init_data_freshness(init_data(deyarli)) is True


def test_kelajakdagi_initdata_rad_etiladi():
    """Soat farqi uchun kichik zaxira bor, lekin uzoq kelajak qabul qilinmaydi."""
    assert check_init_data_freshness(init_data(int(time.time()) + 60)) is True
    assert check_init_data_freshness(init_data(int(time.time()) + 4000)) is False


def test_auth_date_yoq_yoki_buzuq():
    assert check_init_data_freshness("hash=abc") is False
    assert check_init_data_freshness("auth_date=notanumber&hash=abc") is False
    assert check_init_data_freshness("") is False


@pytest.mark.parametrize("qiymat", [0, 1, 1000.5, MAX_MONEY_VALUE])
def test_pul_qiymatlari_qabul_qilinadi(qiymat):
    assert _parse_money(qiymat, "maydon") == float(qiymat)


def test_manfiy_summa_rad_etiladi():
    """Manfiy fixed_expenses_total kunlik limitni cheksiz kattalashtirardi."""
    with pytest.raises(ValueError, match="manfiy"):
        _parse_money(-1, "fixed_expenses_total")


def test_juda_katta_summa_rad_etiladi():
    with pytest.raises(ValueError, match="katta"):
        _parse_money(MAX_MONEY_VALUE + 1, "monthly_income")


@pytest.mark.parametrize("qiymat", ["abc", None, float("nan"), float("inf"), {}])
def test_son_bolmagan_qiymat_rad_etiladi(qiymat):
    with pytest.raises(ValueError):
        _parse_money(qiymat, "monthly_income")
