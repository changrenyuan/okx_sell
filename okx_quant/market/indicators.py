"""
技术指标计算模块
提供 MA、VWAP、ATR 等常用技术指标的计算功能
"""
import numpy as np
from typing import List, Dict, Optional


class TechnicalIndicators:
    """技术指标计算器"""

    @staticmethod
    def sma(data: List[float], period: int) -> Optional[float]:
        """
        计算简单移动平均线 (SMA)

        Args:
            data: 价格数据
            period: 周期

        Returns:
            SMA 值，数据不足返回 None
        """
        if len(data) < period:
            return None
        return sum(data[-period:]) / period

    @staticmethod
    def ema(data: List[float], period: int) -> Optional[float]:
        """
        计算指数移动平均线 (EMA)

        Args:
            data: 价格数据
            period: 周期

        Returns:
            EMA 值，数据不足返回 None
        """
        if len(data) < period:
            return None

        # 初始值使用 SMA
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period

        # 计算 EMA
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    @staticmethod
    def vwap(prices: List[float], volumes: List[float]) -> Optional[float]:
        """
        计算成交量加权平均价格 (VWAP)

        Args:
            prices: 价格列表
            volumes: 成交量列表

        Returns:
            VWAP 值，数据不足返回 None
        """
        if len(prices) != len(volumes) or len(prices) == 0:
            return None

        total_price_volume = sum(p * v for p, v in zip(prices, volumes))
        total_volume = sum(volumes)

        if total_volume == 0:
            return None

        return total_price_volume / total_volume

    @staticmethod
    def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
        """
        计算平均真实波幅 (ATR)

        Args:
            highs: 最高价列表
            lows: 最低价列表
            closes: 收盘价列表
            period: 周期

        Returns:
            ATR 值，数据不足返回 None
        """
        if len(highs) < period + 1 or len(lows) < period + 1 or len(closes) < period + 1:
            return None

        # 计算真实波幅 (TR)
        tr_list = []
        for i in range(1, len(closes)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            tr = max(high_low, high_close, low_close)
            tr_list.append(tr)

        # 计算 ATR (使用 RMA 方法)
        if len(tr_list) < period:
            return None

        atr = sum(tr_list[:period]) / period
        for tr in tr_list[period:]:
            atr = (atr * (period - 1) + tr) / period

        return atr

    @staticmethod
    def check_ma_cross(short_ma: float, long_ma: float, prev_short_ma: Optional[float], prev_long_ma: Optional[float]) -> Optional[str]:
        """
        检查 MA 交叉

        Args:
            short_ma: 短期 MA
            long_ma: 长期 MA
            prev_short_ma: 前一期短期 MA
            prev_long_ma: 前一期长期 MA

        Returns:
            'golden_cross' (金叉), 'death_cross' (死叉), None (无交叉)
        """
        if prev_short_ma is None or prev_long_ma is None:
            return None

        # 金叉：短期从下往上穿过长期
        if prev_short_ma <= prev_long_ma and short_ma > long_ma:
            return "golden_cross"

        # 死叉：短期从上往下穿过长期
        if prev_short_ma >= prev_long_ma and short_ma < long_ma:
            return "death_cross"

        return None

    @staticmethod
    def calculate_distance_pct(price1: float, price2: float) -> float:
        """
        计算两个价格的百分比距离

        Args:
            price1: 价格1
            price2: 价格2

        Returns:
            百分比距离
        """
        if price2 == 0:
            return 0.0
        return abs((price1 - price2) / price2) * 100

    @staticmethod
    def check_volume_spike(volumes: List[float], threshold: float = 1.5) -> bool:
        """
        检查成交量是否出现峰值

        Args:
            volumes: 成交量列表
            threshold: 峰值倍数阈值

        Returns:
            是否出现峰值
        """
        if len(volumes) < 10:
            return False

        recent_volume = volumes[-1]
        avg_volume = sum(volumes[-10:-1]) / 9

        return recent_volume > avg_volume * threshold

    @staticmethod
    def check_volume_drop(volumes: List[float], threshold: float = 0.8) -> bool:
        """
        检查成交量是否连续下降

        Args:
            volumes: 成交量列表
            threshold: 下降阈值（1 - threshold）

        Returns:
            是否连续下降
        """
        if len(volumes) < 3:
            return False

        # 检查最近3根K线是否连续下降
        drop_count = 0
        for i in range(-3, 0):
            if volumes[i] < volumes[i-1] * threshold:
                drop_count += 1

        return drop_count >= 2

    @staticmethod
    def get_depth_change_ratio(current_depth: List[List[float]], prev_depth: List[List[float]], levels: int = 5) -> Optional[float]:
        """
        计算订单簿深度变化比例

        Args:
            current_depth: 当前深度 [[price, size], ...]
            prev_depth: 前一次深度
            levels: 比较的档位数

        Returns:
            变化比例（正数表示增加，负数表示减少）
        """
        if len(current_depth) < levels or len(prev_depth) < levels:
            return None

        current_volume = sum(size for _, size in current_depth[:levels])
        prev_volume = sum(size for _, size in prev_depth[:levels])

        if prev_volume == 0:
            return None

        return (current_volume - prev_volume) / prev_volume


class MarketDataProcessor:
    """市场数据处理器"""

    def __init__(self):
        self.indicators = TechnicalIndicators()
        self.candles_5m: List[Dict] = []
        self.candles_15m: List[Dict] = []

    def update_5m_candles(self, candles: List[Dict]):
        """更新5分钟K线数据"""
        if candles:
            self.candles_5m = candles[-100:]  # 保留最近100根

    def update_15m_candles(self, candles: List[Dict]):
        """更新15分钟K线数据"""
        if candles:
            self.candles_15m = candles[-100:]  # 保留最近100根

    def get_close_prices(self, timeframe: str = "5m") -> List[float]:
        """获取收盘价列表"""
        candles = self.candles_5m if timeframe == "5m" else self.candles_15m
        return [c["close"] for c in candles]

    def get_high_prices(self, timeframe: str = "5m") -> List[float]:
        """获取最高价列表"""
        candles = self.candles_5m if timeframe == "5m" else self.candles_15m
        return [c["high"] for c in candles]

    def get_low_prices(self, timeframe: str = "5m") -> List[float]:
        """获取最低价列表"""
        candles = self.candles_5m if timeframe == "5m" else self.candles_15m
        return [c["low"] for c in candles]

    def get_volumes(self, timeframe: str = "5m") -> List[float]:
        """获取成交量列表"""
        candles = self.candles_5m if timeframe == "5m" else self.candles_15m
        return [c["volume"] for c in candles]

    def get_vwap(self, timeframe: str = "5m", period: int = 390) -> Optional[float]:
        """
        计算 VWAP

        Args:
            timeframe: K线周期
            period: VWAP周期（分钟）

        Returns:
            VWAP 值
        """
        candles = self.candles_5m if timeframe == "5m" else self.candles_15m

        # 计算需要的K线数量
        candles_needed = period // (5 if timeframe == "5m" else 15)

        if len(candles) < candles_needed:
            return None

        recent_candles = candles[-candles_needed:]
        prices = [c["close"] for c in recent_candles]
        volumes = [c["volume"] for c in recent_candles]

        return self.indicators.vwap(prices, volumes)

    def get_ma(self, period: int, timeframe: str = "5m", ma_type: str = "sma") -> Optional[float]:
        """
        计算移动平均线

        Args:
            period: 周期
            timeframe: K线周期
            ma_type: MA类型 (sma/ema)

        Returns:
            MA 值
        """
        closes = self.get_close_prices(timeframe)

        if ma_type == "ema":
            return self.indicators.ema(closes, period)
        else:
            return self.indicators.sma(closes, period)

    def get_atr(self, period: int = 14, timeframe: str = "5m") -> Optional[float]:
        """
        计算 ATR

        Args:
            period: 周期
            timeframe: K线周期

        Returns:
            ATR 值
        """
        highs = self.get_high_prices(timeframe)
        lows = self.get_low_prices(timeframe)
        closes = self.get_close_prices(timeframe)

        return self.indicators.atr(highs, lows, closes, period)

    def get_avg_atr(self, period: int = 14, bars: int = 24, timeframe: str = "5m") -> Optional[float]:
        """
        计算过去 N 根K线的平均 ATR

        Args:
            period: ATR周期
            bars: K线数量
            timeframe: K线周期

        Returns:
            平均 ATR 值
        """
        highs = self.get_high_prices(timeframe)
        lows = self.get_low_prices(timeframe)
        closes = self.get_close_prices(timeframe)

        if len(highs) < period + bars:
            return None

        atr_values = []
        for i in range(period + bars - 1, period - 1, -1):
            h = highs[:i+1]
            l = lows[:i+1]
            c = closes[:i+1]
            atr = self.indicators.atr(h, l, c, period)
            if atr:
                atr_values.append(atr)

        if not atr_values:
            return None

        return sum(atr_values) / len(atr_values)
