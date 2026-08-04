import logging
import aiohttp
import time
import asyncio

CACHE_DURATION = 3600  # Cache for 1 hour
_exchange_rates = {}
_last_fetch = 0

# Cold-start uchun taxminiy kurslar: API hali bir marta ham javob bermagan holat.
# Muvaffaqiyatli fetch'dan keyin bular ishlatilmaydi va eski kurslar kesh'da qoladi.
_COLD_START_RATES = {
    "USD": 1.0,
    "UZS": 12600.0,
    "RUB": 92.0,
    "EUR": 0.92,
    "CNY": 7.23,
}


class CurrencyRateUnavailable(RuntimeError):
    """Kurs ma'lum bo'lmaganda ko'tariladi — noto'g'ri konversiyadan ko'ra xato afzal."""


class CurrencyConverter:
    @staticmethod
    async def get_rates():
        global _exchange_rates, _last_fetch
        current_time = time.time()
        
        if _exchange_rates and (current_time - _last_fetch < CACHE_DURATION):
            return _exchange_rates
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://open.er-api.com/v6/latest/USD") as response:
                    if response.status == 200:
                        data = await response.json()
                        _exchange_rates = data.get("rates", {})
                        _last_fetch = current_time
        except Exception as e:
            logging.error(f"Error fetching exchange rates: {e}")
            if not _exchange_rates:
                logging.warning("Kurs API javob bermadi, taxminiy cold-start kurslari ishlatilmoqda.")
                return dict(_COLD_START_RATES)

        return _exchange_rates

    @staticmethod
    async def convert(amount: float, from_currency: str, to_currency: str) -> float:
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if from_currency == to_currency:
            return amount

        rates = await CurrencyConverter.get_rates()

        # Base is USD in this API. Kurs topilmasa 1.0 ga tushib qolish mumkin emas:
        # 1 USD = 1 UZS deb hisoblash summalarni ~12 000 barobar buzadi.
        rate_from = rates.get(from_currency)
        rate_to = rates.get(to_currency)
        if not rate_from or not rate_to:
            missing = from_currency if not rate_from else to_currency
            raise CurrencyRateUnavailable(f"'{missing}' uchun valyuta kursi topilmadi")

        # Convert to USD first, then to target currency
        amount_usd = amount / rate_from
        converted = amount_usd * rate_to

        return converted
