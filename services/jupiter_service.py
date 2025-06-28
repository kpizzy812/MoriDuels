"""
Сервис для получения цен токенов через Jupiter API
"""
import asyncio
import aiohttp
from decimal import Decimal
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from config.settings import JUPITER_API_KEY, MORI_TOKEN_MINT
from utils.logger import setup_logger

logger = setup_logger(__name__)


class JupiterService:
    def __init__(self):
        self.base_url = "https://price.jup.ag/v4"
        self.api_key = JUPITER_API_KEY
        self.cache = {}  # Простой кеш для цен
        self.cache_duration = timedelta(minutes=1)  # Кешируем на 1 минуту

    async def get_token_price(self, token_mint: str) -> Optional[Dict[str, Any]]:
        """Получить цену токена"""
        try:
            # Проверяем кеш
            cache_key = f"price_{token_mint}"
            if cache_key in self.cache:
                cached_data, cached_time = self.cache[cache_key]
                if datetime.utcnow() - cached_time < self.cache_duration:
                    return cached_data

            async with aiohttp.ClientSession() as session:
                headers = {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"

                # Получаем цену в USD
                url = f"{self.base_url}/price"
                params = {"ids": token_mint}

                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()

                        if "data" in data and token_mint in data["data"]:
                            price_data = data["data"][token_mint]

                            # Получаем цену в SOL
                            sol_price_usd = await self._get_sol_price_usd(session, headers)

                            result = {
                                "price_usd": Decimal(str(price_data["price"])),
                                "price_sol": Decimal(
                                    str(price_data["price"])) / sol_price_usd if sol_price_usd else None,
                                "market_cap": price_data.get("marketCap"),
                                "volume_24h": price_data.get("volume24h"),
                                "timestamp": datetime.utcnow()
                            }

                            # Кешируем результат
                            self.cache[cache_key] = (result, datetime.utcnow())

                            logger.info(f"✅ Got price for {token_mint}: ${result['price_usd']}")
                            return result
                        else:
                            logger.warning(f"⚠️ No price data for token {token_mint}")
                            return None
                    else:
                        logger.error(f"❌ Jupiter API error: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"❌ Error getting token price: {e}")
            return None

    async def _get_sol_price_usd(self, session: aiohttp.ClientSession, headers: dict) -> Optional[Decimal]:
        """Получить цену SOL в USD"""
        try:
            sol_mint = "So11111111111111111111111111111111111111112"  # Wrapped SOL

            url = f"{self.base_url}/price"
            params = {"ids": sol_mint}

            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    if "data" in data and sol_mint in data["data"]:
                        sol_price = data["data"][sol_mint]["price"]
                        return Decimal(str(sol_price))

                return None

        except Exception as e:
            logger.error(f"❌ Error getting SOL price: {e}")
            return Decimal("100")  # Fallback цена SOL

    async def get_mori_price(self) -> Optional[Dict[str, Any]]:
        """Получить цену MORI токена"""
        if not MORI_TOKEN_MINT:
            logger.error("❌ MORI token mint not configured")
            return None

        return await self.get_token_price(MORI_TOKEN_MINT)

    async def get_token_info(self, token_mint: str) -> Optional[Dict[str, Any]]:
        """Получить информацию о токене"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"

                # Используем альтернативный API для метаданных токена
                url = f"https://api.solscan.io/token/meta"
                params = {"tokenAddress": token_mint}

                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "name": data.get("name"),
                            "symbol": data.get("symbol"),
                            "decimals": data.get("decimals"),
                            "supply": data.get("supply"),
                            "description": data.get("description")
                        }

                return None

        except Exception as e:
            logger.error(f"❌ Error getting token info: {e}")
            return None

    async def generate_price_chart(self, token_mint: str, period: str = "24h") -> Optional[str]:
        """Генерировать график цены"""
        try:
            # Используем новый chart_service для создания графиков
            from services.chart_service import chart_service

            chart_path = await chart_service.generate_candlestick_chart(
                token_mint=token_mint,
                period=period,
                style="dark_yellow"
            )

            if chart_path:
                logger.info(f"✅ Generated price chart: {chart_path}")
                return chart_path
            else:
                logger.warning("⚠️ Failed to generate price chart")
                return None

        except Exception as e:
            logger.error(f"❌ Error generating price chart: {e}")
            return None

    async def get_market_data(self, token_mint: str) -> Optional[Dict[str, Any]]:
        """Получить расширенные рыночные данные"""
        try:
            price_data = await self.get_token_price(token_mint)
            token_info = await self.get_token_info(token_mint)

            if price_data and token_info:
                # Рассчитываем рыночную капитализацию
                supply = token_info.get("supply", 0)
                price_usd = price_data["price_usd"]
                market_cap = float(supply) * float(price_usd) if supply else None

                return {
                    **price_data,
                    **token_info,
                    "calculated_market_cap": market_cap,
                    "trading_pair": f"{token_info.get('symbol', 'TOKEN')}/SOL"
                }

            return price_data

        except Exception as e:
            logger.error(f"❌ Error getting market data: {e}")
            return None

    def clear_cache(self):
        """Очистить кеш цен"""
        self.cache.clear()
        logger.info("🗑️ Price cache cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        """Получить статистику кеша"""
        total_entries = len(self.cache)
        valid_entries = 0

        current_time = datetime.utcnow()
        for _, (_, cached_time) in self.cache.items():
            if current_time - cached_time < self.cache_duration:
                valid_entries += 1

        return {
            "total_entries": total_entries,
            "valid_entries": valid_entries,
            "expired_entries": total_entries - valid_entries
        }


# Глобальный экземпляр сервиса
jupiter_service = JupiterService()


# Вспомогательные функции
async def get_mori_market_data() -> Optional[Dict[str, Any]]:
    """Быстрый доступ к данным MORI"""
    return await jupiter_service.get_mori_price()


async def format_price_message(price_data: Dict[str, Any], token_symbol: str = "MORI") -> str:
    """Форматировать сообщение с ценой токена"""
    if not price_data:
        return f"❌ Не удалось получить данные о цене {token_symbol}"

    price_usd = price_data["price_usd"]
    price_sol = price_data.get("price_sol")
    market_cap = price_data.get("market_cap") or price_data.get("calculated_market_cap")
    volume_24h = price_data.get("volume_24h")

    message = f"""🪙 {token_symbol}/SOL

💰 Цена: ${price_usd:.6f}"""

    if price_sol:
        message += f" ({price_sol:.6f} SOL)"

    if market_cap:
        if market_cap >= 1_000_000:
            message += f"\n📊 MCAP: ${market_cap / 1_000_000:.1f}M"
        else:
            message += f"\n📊 MCAP: ${market_cap:,.0f}"

    if volume_24h:
        if volume_24h >= 1_000_000:
            message += f"\n📈 Volume 24h: ${volume_24h / 1_000_000:.1f}M"
        else:
            message += f"\n📈 Volume 24h: ${volume_24h:,.0f}"

    message += f"\n🔗 Raydium: [Trade](https://raydium.io/swap/?inputCurrency=sol&outputCurrency={MORI_TOKEN_MINT})"

    return message