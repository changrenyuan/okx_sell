"""
信号引擎
负责整合市场数据、状态检测、策略判断，生成交易信号
"""
from typing import Dict, Any, Optional
from ..market.state_detector import StateDetector, MarketState
from ..market.indicators import MarketDataProcessor
from ..strategy.overheat_short import OverheatShortStrategy
from ..strategy.trend_long import TrendLongStrategy


class SignalEngine:
    """信号引擎"""

    def __init__(self, config: Dict[str, Any], logger):
        """
        初始化信号引擎

        Args:
            config: 配置字典
            logger: 日志记录器
        """
        self.config = config
        self.logger = logger

        # 初始化各模块
        self.state_detector = StateDetector(config)
        self.market_processor = MarketDataProcessor()
        self.overheat_strategy = OverheatShortStrategy(config, logger)
        self.trend_strategy = TrendLongStrategy(config, logger)

        # 市场数据缓存
        self.current_price: Optional[float] = None
        self.daily_change: float = 0.0
        self.funding_rate: Optional[float] = None
        self.prev_orderbook_bids: list = []

        # 当前市场状态
        self.market_state: MarketState = MarketState.NEUTRAL

        # 记录最近高点（用于策略）
        self.recent_high: Optional[float] = None
        self.recent_low: Optional[float] = None

    def update_market_data(
        self,
        price: float,
        daily_change: float,
        candles_5m: list,
        candles_15m: list,
        funding_rate: Optional[float],
        orderbook: Optional[Dict[str, Any]] = None
    ):
        """
        更新市场数据

        Args:
            price: 当前价格
            daily_change: 24小时涨跌幅
            candles_5m: 5分钟K线数据
            candles_15m: 15分钟K线数据
            funding_rate: 资金费率
            orderbook: 订单簿数据
        """
        self.current_price = price
        self.daily_change = daily_change
        self.funding_rate = funding_rate

        # 更新K线数据
        self.market_processor.update_5m_candles(candles_5m)
        self.market_processor.update_15m_candles(candles_15m)

        # 更新订单簿
        if orderbook and "bids" in orderbook:
            self.prev_orderbook_bids = orderbook["bids"][:5]  # 保存前5档买盘

        # 更新最近高点和最低点
        if candles_5m:
            highs = [c["high"] for c in candles_5m[-10:]]
            lows = [c["low"] for c in candles_5m[-10:]]
            self.recent_high = max(highs)
            self.recent_low = min(lows)

    def detect_market_state(self) -> MarketState:
        """
        检测市场状态

        Returns:
            市场状态
        """
        if self.current_price is None:
            return MarketState.UNKNOWN

        # 获取技术指标
        vwap = self.market_processor.get_vwap("5m")
        ma_5 = self.market_processor.get_ma(5, "5m")
        ma_15 = self.market_processor.get_ma(15, "5m")
        ma_60 = self.market_processor.get_ma(60, "5m")

        ma_5_15m = self.market_processor.get_ma(5, "15m")
        ma_15_15m = self.market_processor.get_ma(15, "15m")

        atr_current = self.market_processor.get_atr(14, "5m")
        atr_avg = self.market_processor.get_avg_atr(14, 24, "5m")

        volumes_5m = self.market_processor.get_volumes("5m")
        volumes_15m = self.market_processor.get_volumes("15m")

        # 检测市场状态
        self.market_state = self.state_detector.detect_market_state(
            daily_change=self.daily_change,
            current_price=self.current_price,
            vwap=vwap,
            ma_5=ma_5,
            ma_15=ma_15,
            ma_60=ma_60,
            volumes_5m=volumes_5m,
            volumes_15m=volumes_15m,
            atr_current=atr_current,
            atr_avg=atr_avg,
            funding_rate=self.funding_rate
        )

        # 记录市场状态
        self.logger.market_state(
            self.market_state.value,
            self.current_price,
            f"VWAP: {vwap:.2f}, MA5: {ma_5:.2f}, MA15: {ma_15:.2f}, MA60: {ma_60:.2f}"
        )

        return self.market_state

    def generate_signal(self) -> Optional[Dict[str, Any]]:
        """
        生成交易信号

        Returns:
            信号字典，None 表示无信号
        """
        if self.current_price is None:
            return None

        # 获取技术指标
        vwap = self.market_processor.get_vwap("5m")
        ma_5 = self.market_processor.get_ma(5, "5m")
        ma_15 = self.market_processor.get_ma(15, "5m")
        ma_60 = self.market_processor.get_ma(60, "5m")

        # 获取前一期MA（用于判断交叉）
        closes_5m = self.market_processor.get_close_prices("5m")
        ma_5_prev = self.market_processor.get_ma(5, "5m")
        ma_15_prev = self.market_processor.get_ma(15, "5m")

        if len(closes_5m) > 1:
            # 简化的前一期MA计算
            prev_closes = closes_5m[:-1]
            ma_5_prev = sum(prev_closes[-5:]) / 5 if len(prev_closes) >= 5 else None
            ma_15_prev = sum(prev_closes[-15:]) / 15 if len(prev_closes) >= 15 else None

        volumes_5m = self.market_processor.get_volumes("5m")

        # 检测市场状态
        market_state = self.detect_market_state()

        # 根据市场状态选择策略
        if market_state == MarketState.OVERHEATED:
            # 过热回落做空策略
            if self.overheat_strategy.params.get("enabled", True):
                # 检查资金费率限制
                funding_signal = self.state_detector.get_funding_rate_signal(self.funding_rate)
                if funding_signal == "no_short":
                    self.logger.info("资金费率过低，禁止做空")
                    return None

                # 检查入场条件
                if self.overheat_strategy.status.value == "idle":
                    self.overheat_strategy.set_waiting_entry()

                entry_triggered = self.overheat_strategy.check_entry_conditions(
                    current_price=self.current_price,
                    vwap=vwap,
                    ma_5=ma_5,
                    ma_15=ma_15,
                    ma_5_prev=ma_5_prev,
                    ma_15_prev=ma_15_prev,
                    volumes_5m=volumes_5m,
                    orderbook_bids=self.prev_orderbook_bids,
                    prev_orderbook_bids=self.prev_orderbook_bids
                )

                if entry_triggered:
                    return {
                        "strategy": "overheat_short",
                        "direction": "short",
                        "price": self.current_price,
                        "state": market_state.value
                    }

        elif market_state == MarketState.TRENDING:
            # 趋势做多策略
            if self.trend_strategy.params.get("enabled", True):
                # 检查资金费率限制
                funding_signal = self.state_detector.get_funding_rate_signal(self.funding_rate)
                if funding_signal == "no_long":
                    self.logger.info("资金费率过高，禁止做多")
                    return None

                # 检查入场条件
                if self.trend_strategy.status.value == "idle":
                    self.trend_strategy.set_waiting_entry()

                entry_triggered = self.trend_strategy.check_entry_conditions(
                    current_price=self.current_price,
                    vwap=vwap,
                    ma_15=ma_15,
                    volumes_5m=volumes_5m,
                    recent_high=self.recent_high
                )

                if entry_triggered:
                    return {
                        "strategy": "trend_long",
                        "direction": "long",
                        "price": self.current_price,
                        "state": market_state.value
                    }

        return None

    def check_exit_signal(self, strategy_name: str) -> Optional[str]:
        """
        检查出场信号

        Args:
            strategy_name: 策略名称

        Returns:
            出场原因，None 表示不需要出场
        """
        if self.current_price is None:
            return None

        if strategy_name == "overheat_short":
            return self.overheat_strategy.check_exit_conditions(
                current_price=self.current_price,
                highest_price=self.recent_high
            )
        elif strategy_name == "trend_long":
            return self.trend_strategy.check_exit_conditions(
                current_price=self.current_price,
                lowest_price_since_entry=self.trend_strategy.lowest_price_since_entry
            )

        return None

    def prepare_trade(self, signal: Dict[str, Any], equity: float) -> Dict[str, Any]:
        """
        准备交易信息

        Args:
            signal: 交易信号
            equity: 账户权益

        Returns:
            交易信息字典
        """
        strategy_name = signal["strategy"]
        direction = signal["direction"]
        price = signal["price"]

        if strategy_name == "overheat_short":
            entry_info = self.overheat_strategy.prepare_entry(
                equity=equity,
                current_price=price,
                highest_price=self.recent_high
            )
        elif strategy_name == "trend_long":
            entry_info = self.trend_strategy.prepare_entry(
                equity=equity,
                current_price=price,
                lowest_price=self.recent_low
            )
        else:
            return {}

        return {
            "strategy": strategy_name,
            "direction": direction,
            "entry_price": price,
            **entry_info
        }

    def update_strategy_status(self, current_price: float):
        """
        更新策略状态（用于趋势策略的最低价更新）

        Args:
            current_price: 当前价格
        """
        if self.trend_strategy.status.value == "position":
            self.trend_strategy.update_lowest_price(current_price)

    def get_strategy_status(self, strategy_name: str) -> Dict[str, Any]:
        """
        获取策略状态

        Args:
            strategy_name: 策略名称

        Returns:
            策略状态
        """
        if strategy_name == "overheat_short":
            return self.overheat_strategy.get_status()
        elif strategy_name == "trend_long":
            return self.trend_strategy.get_status()
        return {}

    def reset_strategy(self, strategy_name: str):
        """
        重置策略

        Args:
            strategy_name: 策略名称
        """
        if strategy_name == "overheat_short":
            self.overheat_strategy.reset()
        elif strategy_name == "trend_long":
            self.trend_strategy.reset()
