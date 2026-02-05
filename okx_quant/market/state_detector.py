"""
市场状态识别模块
根据各种技术指标和市场数据，识别市场状态
"""
from typing import Dict, Any, Optional
from enum import Enum


class MarketState(Enum):
    """市场状态枚举"""
    OVERHEATED = "OVERHEATED"  # 过热
    TRENDING = "TRENDING"      # 趋势
    NEUTRAL = "NEUTRAL"        # 中性
    UNKNOWN = "UNKNOWN"        # 未知


class StateDetector:
    """市场状态检测器"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化状态检测器

        Args:
            config: 配置字典
        """
        self.config = config
        self.overheat_params = config.get("strategy_overheat_short", {})
        self.trend_params = config.get("strategy_trend_long", {})
        self.market_params = config.get("market", {})

    def detect_overheat_state(
        self,
        daily_change: float,
        current_price: float,
        vwap: Optional[float],
        volumes_5m: list,
        funding_rate: Optional[float]
    ) -> Dict[str, Any]:
        """
        检测过热状态

        Args:
            daily_change: 24小时涨跌幅
            current_price: 当前价格
            vwap: VWAP 值
            volumes_5m: 5分钟成交量列表
            funding_rate: 资金费率

        Returns:
            检测结果字典
        """
        result = {
            "state": MarketState.NEUTRAL,
            "reasons": [],
            "details": {}
        }

        # 条件1：当日涨幅 ≥ 4%
        min_daily_gain = self.overheat_params.get("min_daily_gain", 0.04)
        if daily_change >= min_daily_gain:
            result["reasons"].append(f"当日涨幅 {daily_change:.2%} ≥ {min_daily_gain:.0%}")
            result["details"]["daily_change"] = daily_change
        else:
            return result

        # 条件2：当前价格 > VWAP + 2.0%
        if vwap:
            distance_above_vwap = ((current_price - vwap) / vwap) * 100
            if distance_above_vwap > 2.0:
                result["reasons"].append(f"价格高于 VWAP {distance_above_vwap:.2f}%")
                result["details"]["vwap_distance"] = distance_above_vwap
            else:
                return result
        else:
            return result

        # 条件3：5min 成交量出现峰值 → 连续下降
        if len(volumes_5m) >= 5:
            # 检查是否先有峰值
            peak_detected = volumes_5m[-1] > sum(volumes_5m[-5:-1]) / 4 * 1.5
            # 检查后续是否连续下降
            drop_detected = all(volumes_5m[i] < volumes_5m[i-1] for i in range(-3, 0))

            if peak_detected and drop_detected:
                result["reasons"].append("成交量峰值后连续下降")
                result["details"]["volume_pattern"] = "peak_then_drop"
            else:
                return result
        else:
            return result

        # 条件4：资金费率 ≥ +0.02%
        min_funding_rate = self.overheat_params.get("min_funding_rate", 0.0002)
        if funding_rate and funding_rate >= min_funding_rate:
            result["reasons"].append(f"资金费率 {funding_rate:.4f} ≥ {min_funding_rate:.4f}")
            result["details"]["funding_rate"] = funding_rate
        else:
            return result

        # 所有条件满足，判定为过热
        if len(result["reasons"]) >= 4:
            result["state"] = MarketState.OVERHEATED

        return result

    def detect_trending_state(
        self,
        ma_5: Optional[float],
        ma_15: Optional[float],
        ma_60: Optional[float],
        volumes_15m: list,
        atr_current: Optional[float],
        atr_avg: Optional[float],
        funding_rate: Optional[float]
    ) -> Dict[str, Any]:
        """
        检测趋势状态

        Args:
            ma_5: MA5
            ma_15: MA15
            ma_60: MA60
            volumes_15m: 15分钟成交量列表
            atr_current: 当前ATR
            atr_avg: 平均ATR
            funding_rate: 资金费率

        Returns:
            检测结果字典
        """
        result = {
            "state": MarketState.NEUTRAL,
            "reasons": [],
            "details": {}
        }

        # 条件1：MA(5) > MA(15) > MA(60)
        if ma_5 and ma_15 and ma_60:
            if ma_5 > ma_15 > ma_60:
                result["reasons"].append(f"MA排列：{ma_5:.2f} > {ma_15:.2f} > {ma_60:.2f}")
                result["details"]["ma_alignment"] = "bullish"
            else:
                return result
        else:
            return result

        # 条件2：15min 成交量连续 3 根温和放大
        if len(volumes_15m) >= 3:
            volume_growing = all(volumes_15m[i] > volumes_15m[i-1] for i in range(-2, 0))
            volume_not_explosive = volumes_15m[-1] < sum(volumes_15m[-10:-1]) / 9 * 2

            if volume_growing and volume_not_explosive:
                result["reasons"].append("成交量温和放大")
                result["details"]["volume_pattern"] = "gentle_growth"
            else:
                return result
        else:
            return result

        # 条件3：5min ATR < 过去 24h ATR 均值
        if atr_current and atr_avg:
            if atr_current < atr_avg:
                result["reasons"].append(f"当前 ATR {atr_current:.2f} < 平均 ATR {atr_avg:.2f}")
                result["details"]["atr_status"] = "below_avg"
            else:
                return result
        else:
            return result

        # 条件4：资金费率 ∈ [-0.01%, +0.02%]
        min_funding_rate = self.trend_params.get("min_funding_rate", -0.0001)
        max_funding_rate = self.trend_params.get("max_funding_rate", 0.0002)

        if funding_rate and min_funding_rate <= funding_rate <= max_funding_rate:
            result["reasons"].append(f"资金费率 {funding_rate:.4f} 在合理范围")
            result["details"]["funding_rate"] = funding_rate
        else:
            return result

        # 所有条件满足，判定为趋势
        if len(result["reasons"]) >= 4:
            result["state"] = MarketState.TRENDING

        return result

    def detect_market_state(
        self,
        daily_change: float,
        current_price: float,
        vwap: Optional[float],
        ma_5: Optional[float],
        ma_15: Optional[float],
        ma_60: Optional[float],
        volumes_5m: list,
        volumes_15m: list,
        atr_current: Optional[float],
        atr_avg: Optional[float],
        funding_rate: Optional[float]
    ) -> MarketState:
        """
        综合检测市场状态

        Args:
            daily_change: 24小时涨跌幅
            current_price: 当前价格
            vwap: VWAP 值
            ma_5: MA5
            ma_15: MA15
            ma_60: MA60
            volumes_5m: 5分钟成交量列表
            volumes_15m: 15分钟成交量列表
            atr_current: 当前ATR
            atr_avg: 平均ATR
            funding_rate: 资金费率

        Returns:
            市场状态
        """
        # 优先检测过热状态
        overheat_result = self.detect_overheat_state(
            daily_change, current_price, vwap, volumes_5m, funding_rate
        )
        if overheat_result["state"] == MarketState.OVERHEATED:
            return MarketState.OVERHEATED

        # 其次检测趋势状态
        trending_result = self.detect_trending_state(
            ma_5, ma_15, ma_60, volumes_15m, atr_current, atr_avg, funding_rate
        )
        if trending_result["state"] == MarketState.TRENDING:
            return MarketState.TRENDING

        # 否则返回中性
        return MarketState.NEUTRAL

    def get_funding_rate_signal(self, funding_rate: Optional[float]) -> Optional[str]:
        """
        根据资金费率判断方向限制

        Args:
            funding_rate: 资金费率

        Returns:
            'no_long', 'no_short', None (无限制)
        """
        if funding_rate is None:
            return None

        threshold = self.market_params.get("funding_rate_threshold", 0.0003)

        if funding_rate > threshold:
            return "no_long"  # 资金费率过高，不做多
        elif funding_rate < -threshold:
            return "no_short"  # 资金费率过低，不做空

        return None
