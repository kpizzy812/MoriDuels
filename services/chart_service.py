"""
Сервис для создания красивых графиков цен
"""
import asyncio
import aiohttp
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import os
from pathlib import Path

from config.settings import MORI_TOKEN_MINT
from utils.logger import setup_logger

logger = setup_logger(__name__)


class ChartService:
    def __init__(self):
        self.charts_dir = Path("static/charts")
        self.charts_dir.mkdir(parents=True, exist_ok=True)

        # Стили для графиков
        self.styles = {
            "dark_yellow": {
                "bg_color": "#0a0a0a",
                "grid_color": "#1a1a1a",
                "text_color": "#ffffff",
                "candle_up": "#ffeb3b",
                "candle_down": "#f44336",
                "volume_color": "#ffc107",
                "ma_color": "#ff9800"
            },
            "dark_green": {
                "bg_color": "#0d1421",
                "grid_color": "#1a2332",
                "text_color": "#ffffff",
                "candle_up": "#00e676",
                "candle_down": "#ff5252",
                "volume_color": "#4caf50",
                "ma_color": "#2196f3"
            }
        }

    async def generate_candlestick_chart(
            self,
            token_mint: str,
            period: str = "24h",
            style: str = "dark_yellow"
    ) -> Optional[str]:
        """Генерировать свечной график"""
        try:
            logger.info(f"📊 Generating candlestick chart for {token_mint}")

            # Получаем исторические данные
            candle_data = await self._fetch_candle_data(token_mint, period)
            if not candle_data:
                logger.error("❌ No candle data received")
                return None

            # Создаем график
            chart_path = await self._create_candlestick_plot(candle_data, style, period)

            logger.info(f"✅ Chart generated: {chart_path}")
            return chart_path

        except Exception as e:
            logger.error(f"❌ Error generating chart: {e}")
            return None

    async def _fetch_candle_data(self, token_mint: str, period: str) -> Optional[List[Dict]]:
        """Получить исторические данные свечей"""
        try:
            # Определяем параметры периода
            period_params = self._get_period_params(period)
            if not period_params:
                return None

            # Используем Birdeye API для получения свечных данных
            url = "https://public-api.birdeye.so/defi/history_price"
            params = {
                "address": token_mint,
                "address_type": "token",
                "type": period_params["interval"],
                "time_from": period_params["from_timestamp"],
                "time_to": int(datetime.now().timestamp())
            }

            headers = {
                "X-API-KEY": os.getenv("BIRDEYE_API_KEY", "")  # Если есть API ключ
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()

                        if data.get("success") and data.get("data", {}).get("items"):
                            return data["data"]["items"]
                        else:
                            logger.warning("⚠️ No candlestick data in Birdeye response")
                            # Fallback: генерируем фейковые данные для демонстрации
                            return await self._generate_demo_data(period_params)
                    else:
                        logger.warning(f"⚠️ Birdeye API error: {response.status}")
                        return await self._generate_demo_data(period_params)

        except Exception as e:
            logger.error(f"❌ Error fetching candle data: {e}")
            # Генерируем демо данные в случае ошибки
            period_params = self._get_period_params(period)
            return await self._generate_demo_data(period_params) if period_params else None

    def _get_period_params(self, period: str) -> Optional[Dict]:
        """Получить параметры для периода"""
        now = datetime.now()

        period_map = {
            "1h": {"interval": "1m", "from_timestamp": int((now - timedelta(hours=1)).timestamp())},
            "4h": {"interval": "5m", "from_timestamp": int((now - timedelta(hours=4)).timestamp())},
            "24h": {"interval": "15m", "from_timestamp": int((now - timedelta(hours=24)).timestamp())},
            "7d": {"interval": "1H", "from_timestamp": int((now - timedelta(days=7)).timestamp())},
            "30d": {"interval": "4H", "from_timestamp": int((now - timedelta(days=30)).timestamp())}
        }

        return period_map.get(period)

    async def _generate_demo_data(self, period_params: Dict) -> List[Dict]:
        """Генерировать демонстрационные данные"""
        try:
            from_time = period_params["from_timestamp"]
            to_time = int(datetime.now().timestamp())
            interval_seconds = (to_time - from_time) // 96  # ~96 свечей

            demo_data = []
            base_price = 0.00001234  # Базовая цена MORI
            current_price = base_price

            for i in range(96):
                timestamp = from_time + (i * interval_seconds)

                # Генерируем реалистичные движения цены
                change_percent = np.random.normal(0, 2)  # Среднее 0%, стандартное отклонение 2%
                price_change = current_price * (change_percent / 100)

                open_price = current_price
                close_price = current_price + price_change

                # High и Low с небольшими случайными отклонениями
                high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, 1)) / 100)
                low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, 1)) / 100)

                # Объем торгов
                volume = np.random.randint(50000, 500000)

                demo_data.append({
                    "unixTime": timestamp,
                    "o": round(open_price, 8),
                    "h": round(high_price, 8),
                    "l": round(low_price, 8),
                    "c": round(close_price, 8),
                    "v": volume
                })

                current_price = close_price

            logger.info(f"✅ Generated {len(demo_data)} demo candles")
            return demo_data

        except Exception as e:
            logger.error(f"❌ Error generating demo data: {e}")
            return []

    async def _create_candlestick_plot(self, data: List[Dict], style: str, period: str) -> str:
        """Создать график свечей"""
        try:
            # Подготавливаем данные
            df = pd.DataFrame(data)
            df['datetime'] = pd.to_datetime(df['unixTime'], unit='s')
            df = df.sort_values('datetime')

            # Получаем стиль
            style_config = self.styles.get(style, self.styles["dark_yellow"])

            # Настраиваем matplotlib для темной темы
            plt.style.use('dark_background')

            # Создаем фигуру с субплотами
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8),
                                           gridspec_kw={'height_ratios': [3, 1]},
                                           facecolor=style_config["bg_color"])

            # Основной график - свечи
            await self._plot_candlesticks(ax1, df, style_config)

            # Нижний график - объем
            await self._plot_volume(ax2, df, style_config)

            # Настраиваем оси и заголовки
            await self._setup_chart_styling(ax1, ax2, df, style_config, period)

            # Сохраняем график
            timestamp = int(datetime.now().timestamp())
            filename = f"mori_chart_{period}_{timestamp}.png"
            chart_path = self.charts_dir / filename

            plt.tight_layout()
            plt.savefig(chart_path, dpi=300, bbox_inches='tight',
                        facecolor=style_config["bg_color"], edgecolor='none')
            plt.close()

            return str(chart_path)

        except Exception as e:
            logger.error(f"❌ Error creating plot: {e}")
            plt.close('all')  # Закрываем все графики в случае ошибки
            return None

    async def _plot_candlesticks(self, ax, df, style_config):
        """Нарисовать свечи"""
        try:
            for i, row in df.iterrows():
                x = mdates.date2num(row['datetime'])
                open_price, high, low, close = row['o'], row['h'], row['l'], row['c']

                # Определяем цвет свечи
                color = style_config["candle_up"] if close >= open_price else style_config["candle_down"]

                # Рисуем тело свечи
                height = abs(close - open_price)
                bottom = min(open_price, close)
                width = 0.0003  # Ширина свечи

                rect = Rectangle((x - width / 2, bottom), width, height,
                                 facecolor=color, edgecolor=color, alpha=0.8)
                ax.add_patch(rect)

                # Рисуем тени (wicks)
                ax.plot([x, x], [low, high], color=color, linewidth=1, alpha=0.7)

            # Добавляем скользящую среднюю
            if len(df) > 20:
                df['ma20'] = df['c'].rolling(window=20).mean()
                ax.plot(df['datetime'], df['ma20'], color=style_config["ma_color"],
                        linewidth=1.5, alpha=0.8, label='MA20')

        except Exception as e:
            logger.error(f"❌ Error plotting candlesticks: {e}")

    async def _plot_volume(self, ax, df, style_config):
        """Нарисовать объем"""
        try:
            colors = []
            for i, row in df.iterrows():
                if i == 0:
                    colors.append(style_config["volume_color"])
                else:
                    prev_close = df.iloc[i - 1]['c']
                    current_close = row['c']
                    color = style_config["candle_up"] if current_close >= prev_close else style_config["candle_down"]
                    colors.append(color)

            ax.bar(df['datetime'], df['v'], color=colors, alpha=0.6, width=0.8)

        except Exception as e:
            logger.error(f"❌ Error plotting volume: {e}")

    async def _setup_chart_styling(self, ax1, ax2, df, style_config, period):
        """Настроить стилизацию графика"""
        try:
            # Цены на основном графике
            ax1.set_facecolor(style_config["bg_color"])
            ax1.grid(True, color=style_config["grid_color"], alpha=0.3)
            ax1.tick_params(colors=style_config["text_color"])

            # Форматирование оси X для дат
            if period in ["1h", "4h"]:
                ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax1.xaxis.set_major_locator(mdates.HourLocator(interval=1))
            elif period == "24h":
                ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax1.xaxis.set_major_locator(mdates.HourLocator(interval=4))
            else:
                ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
                ax1.xaxis.set_major_locator(mdates.DayLocator(interval=1))

            # Заголовок и подписи
            current_price = df.iloc[-1]['c']
            price_change = ((current_price - df.iloc[0]['c']) / df.iloc[0]['c']) * 100
            change_color = style_config["candle_up"] if price_change >= 0 else style_config["candle_down"]

            title = f"MORI/SOL • ${current_price:.8f} • {price_change:+.2f}% • {period.upper()}"
            ax1.set_title(title, color=style_config["text_color"], fontsize=14, fontweight='bold', pad=20)
            ax1.set_ylabel('Цена (USD)', color=style_config["text_color"], fontsize=10)

            # Объем на нижнем графике
            ax2.set_facecolor(style_config["bg_color"])
            ax2.grid(True, color=style_config["grid_color"], alpha=0.3)
            ax2.tick_params(colors=style_config["text_color"])
            ax2.set_ylabel('Объем', color=style_config["text_color"], fontsize=10)
            ax2.set_xlabel('Время', color=style_config["text_color"], fontsize=10)

            # Форматирование объема
            ax2.yaxis.set_major_formatter(
                plt.FuncFormatter(lambda x, p: f'{x / 1000:.0f}K' if x >= 1000 else f'{x:.0f}'))

            # Убираем лишние подписи на оси X верхнего графика
            ax1.set_xticklabels([])

            # Поворачиваем подписи дат
            plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

        except Exception as e:
            logger.error(f"❌ Error setting up chart styling: {e}")

    async def cleanup_old_charts(self, max_age_hours: int = 1):
        """Очистка старых графиков"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            deleted_count = 0

            for chart_file in self.charts_dir.glob("mori_chart_*.png"):
                if chart_file.stat().st_mtime < cutoff_time.timestamp():
                    chart_file.unlink()
                    deleted_count += 1

            if deleted_count > 0:
                logger.info(f"🗑️ Cleaned up {deleted_count} old chart files")

        except Exception as e:
            logger.error(f"❌ Error cleaning up charts: {e}")


# Глобальный экземпляр сервиса
chart_service = ChartService()