"""
Valyuta konversiyasi — ilgari noma'lum valyuta uchun kurs 1.0 ga tushar edi,
ya'ni 1 USD = 1 UZS. Bu barcha balanslarni jimgina ~12 000 barobar buzardi.
"""

import asyncio

import pytest

from utils import currency
from utils.currency import CurrencyConverter, CurrencyRateUnavailable


@pytest.fixture(autouse=True)
def sobit_kurslar(monkeypatch):
    """Testlar tarmoqqa chiqmasligi uchun kurslarni qotiramiz."""
    async def fake_rates():
        return {"USD": 1.0, "UZS": 12600.0, "EUR": 0.92}

    monkeypatch.setattr(CurrencyConverter, "get_rates", staticmethod(fake_rates))
    yield


def convert(*args):
    return asyncio.run(CurrencyConverter.convert(*args))


def test_bir_xil_valyuta_ozgarmaydi():
    assert convert(1000.0, "UZS", "UZS") == 1000.0


def test_usd_dan_uzs_ga():
    assert convert(1.0, "USD", "UZS") == pytest.approx(12600.0)


def test_uzs_dan_usd_ga():
    assert convert(12600.0, "UZS", "USD") == pytest.approx(1.0)


def test_notogri_valyuta_jim_qolmaydi():
    """Asosiy regressiya: noma'lum valyuta 1:1 ga tushmasligi kerak."""
    with pytest.raises(CurrencyRateUnavailable):
        convert(1000.0, "UZS", "XYZ")

    with pytest.raises(CurrencyRateUnavailable):
        convert(1000.0, "XYZ", "UZS")


def test_borib_kelish_qiymatni_saqlaydi():
    oraliq = convert(50000.0, "UZS", "USD")
    assert convert(oraliq, "USD", "UZS") == pytest.approx(50000.0)


def test_cold_start_kurslari_toliq():
    """Zaxira jadval qo'llab-quvvatlanadigan valyutalarni qamrab olishi kerak."""
    for kod in ("USD", "UZS", "EUR", "RUB"):
        assert kod in currency._COLD_START_RATES
