"""
趋势做多策略
专门针对 ETH 的温和趋势做多策略
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum


class TradeStatus(Enum):
    """交易状态"""
    IDLE = "idle"              # 空闲
    WAITING_ENTRY = "waiting"  # 等待入场
    IN_POSITION = "position"   # 持仓中
    EXITING = "exiting"        # 平仓中


class TrendLongStrategy:
    """趋势做多策略"""

    def __init__(self, config: Dict[str, Any], logger):
        """
        初始化策略

        Args:
            config: 配置字典
            logger: 日志记录器
        """
        self.config = config
        self.logger = logger
        self.params = config.get("strategy_trend_long", {})

        # 策略状态
        self.status = TradeStatus.IDLE
        self.entry_price: Optional[float] = None
        self.stop_price: Optional[float] = None
        self.take_profit_1r: Optional[float] = None
        self.take_profit_2r: Optional[float] = None
        self.position_size: float = 0.0
        self.entry_time: Optional[datetime] = None
        self.risk_amount: float = 0.0
        self.lowest_price_since_entry: Optional[float] = None  # 移动止损最低价
        self.trailing_stop_active: bool = False  # 移动止损是否激活
        self.partial_closed_1r: bool = False  # 是否已经平仓过1R
        self.partial_closed_2r: bool = False  # 是否已经平仓过2R

        # 记录策略触发原因
        self.trigger_reasons: List[str] = []

    def check_entry_conditions(
        self,
        current_price: float,
        vwap: Optional[float],
        ma_15: Optional[float],
        volumes_5m: List[float],
        recent_high: Optional[float] = None
    ) -> bool:
        """
        检查入场条件

        Args:
            current_price: 当前价格
            vwap: VWAP 值
            ma_15: MA15
            volumes_5m: 5分钟成交量列表
            recent_high: 最近高点

        Returns:
            是否满足入场条件
        """
        if self.status != TradeStatus.WAITING_ENTRY:
            return False

        conditions_met = 0
        self.trigger_reasons = []

        # 条件1：回踩 VWAP 或 MA(15)
        touch_support = False
        if vwap and abs((current_price - vwap) / vwap) < 0.005:  # 价格接近 VWAP 0.5%
            touch_support = True
            conditions_met += 1
            self.trigger_reasons.append(f"回踩 VWAP: {current_price:.2f} ≈ {vwap:.2f}")
        elif ma_15 and current_price < ma_15 * 1.005 and current_price > ma_15 * 0.995:
            touch_support = True
            conditions_met += 1
            self.trigger_reasons.append(f"回踩 MA15: {current_price:.2f} ≈ {ma_15:.2f}")

        # 条件2：回踩期间成交量萎缩
        volume_shrinking = False
        if len(volumes_5m) >= 3:
            avg_volume_before = sum(volumes_5m[-10:-3]) / 7 if len(volumes_5m) >= 10 else sum(volumes_5m[:-3]) / len(volumes_5m[:-3])
            avg_volume_recent = sum(volumes_5m[-3:]) / 3

            if avg_volume_recent < avg_volume_before * 0.8:  # 成交量萎缩 20%
                volume_shrinking = True
                conditions_met += 1
                self.trigger_reasons.append(f"成交量萎缩: {avg_volume_recent:.0f} < {avg_volume_before:.0f}")

        # 条件3：再次出现放量阳线
        if len(volumes_5m) >= 2 and recent_high:
            current_volume = volumes_5m[-1]
            prev_volume = volumes_5m[-2]
            avg_volume = sum(volumes_5m[-5:]) / 5

            # 当前价格高于前一根（阳线）
            # 成交量放大
            bullish_candle = current_price > recent_high and current_volume > avg_volume * 1.2

            if bullish_candle:
                conditions_met += 1
                self.trigger_reasons.append("放量阳线突破")

        # 满足至少 2 条条件即可入场
        if conditions_met >= 2:
            self.logger.signal(
                "trend_long",
                "entry",
                current_price,
                f"入场条件满足: {', '.join(self.trigger_reasons)}",
                conditions_met=conditions_met
            )
            return True

        return False

    def check_exit_conditions(
        self,
        current_price: float,
        lowest_price_since_entry: Optional[float]
    ) -> Optional[str]:
        """
        检查出场条件

        Args:
            current_price: 当前价格
            lowest_price_since_entry: 入场后的最低价

        Returns:
            出场原因 (stop_loss/take_profit_1r/take_profit_2r/trailing_stop/time_out/None)
        """
        if self.status != TradeStatus.IN_POSITION:
            return None

        # 检查止损
        if self.stop_price and current_price <= self.stop_price:
            return "stop_loss"

        # 检查止盈 0.8R（平30%）
        if not self.partial_closed_1r and self.take_profit_1r and current_price >= self.take_profit_1r:
            return "take_profit_1r"

        # 检查止盈 1.5R（平50%）
        if not self.partial_closed_2r and self.take_profit_2r and current_price >= self.take_profit_2r:
            return "take_profit_2r"

        # 检查移动止损（在1.5R后激活）
        trailing_stop_enabled = self.params.get("trailing_stop", True)
        if trailing_stop_enabled and self.partial_closed_2r:
            # 使用入场后的最低价作为移动止损基准
            if lowest_price_since_entry:
                # 设置新的止损：最低价 - 0.2%
                new_stop = lowest_price_since_entry * (1 - 0.002)

                if not self.trailing_stop_active or new_stop > self.stop_price:
                    self.stop_price = new_stop
                    self.trailing_stop_active = True
                    self.logger.info(f"移动止损更新: {self.stop_price:.2f}")

                if current_price <= self.stop_price:
                    return "trailing_stop"

        # 检查持仓时间
        if self.entry_time:
            elapsed = (datetime.now() - self.entry_time).total_seconds()
            max_hold_time = self.params.get("max_hold_time", 7200)
            min_hold_time = self.params.get("min_hold_time", 300)

            # 最短持仓时间后检查最长持仓时间
            if elapsed > max_hold_time:
                return "time_out"

        return None

    def calculate_position_size(
        self,
        equity: float,
        entry_price: float,
        stop_price: float
    ) -> float:
        """
        计算仓位大小

        Args:
            equity: 账户权益
            entry_price: 入场价格
            stop_price: 止损价格

        Returns:
            仓位大小
        """
        risk_pct = self.params.get("risk_per_trade", 0.003)
        self.risk_amount = equity * risk_pct

        stop_distance = abs(entry_price - stop_price)
        if stop_distance <= 0:
            return 0.0

        position_size = self.risk_amount / stop_distance
        return round(position_size, 3)

    def prepare_entry(
        self,
        equity: float,
        current_price: float,
        lowest_price: Optional[float]
    ) -> Dict[str, Any]:
        """
        准备入场（计算各种价格）

        Args:
            equity: 账户权益
            current_price: 当前价格
            lowest_price: 回踩低点

        Returns:
            入场信息字典
        """
        # 计算止损价格：回踩低点 - 0.2%
        stop_offset = self.params.get("stop_loss_offset", 0.002)
        if lowest_price:
            self.stop_price = lowest_price * (1 - stop_offset)
        else:
            self.stop_price = current_price * (1 - stop_offset)

        # 计算仓位大小
        self.position_size = self.calculate_position_size(equity, current_price, self.stop_price)

        # 计算止盈价格
        take_profit_1r_ratio = self.params.get("take_profit_1r", 0.8)
        take_profit_2r_ratio = self.params.get("take_profit_2r", 1.5)

        risk_per_unit = abs(current_price - self.stop_price)
        self.take_profit_1r = current_price + risk_per_unit * take_profit_1r_ratio
        self.take_profit_2r = current_price + risk_per_unit * take_profit_2r_ratio

        entry_info = {
            "entry_price": current_price,
            "stop_price": self.stop_price,
            "take_profit_1r": self.take_profit_1r,
            "take_profit_2r": self.take_profit_2r,
            "position_size": self.position_size,
            "risk_amount": self.risk_amount,
            "risk_per_unit": risk_per_unit,
            "potential_r": risk_per_unit / current_price * 100
        }

        return entry_info

    def on_entry(self, entry_price: float, size: float):
        """
        入场后更新状态

        Args:
            entry_price: 实际入场价格
            size: 实际仓位大小
        """
        self.status = TradeStatus.IN_POSITION
        self.entry_price = entry_price
        self.position_size = size
        self.entry_time = datetime.now()
        self.lowest_price_since_entry = entry_price
        self.partial_closed_1r = False
        self.partial_closed_2r = False
        self.trailing_stop_active = False

        # 重新计算止损和止盈
        if self.stop_price:
            risk_per_unit = abs(entry_price - self.stop_price)
            self.take_profit_1r = entry_price + risk_per_unit * self.params.get("take_profit_1r", 0.8)
            self.take_profit_2r = entry_price + risk_per_unit * self.params.get("take_profit_2r", 1.5)

        self.logger.signal(
            "trend_long",
            "entry_filled",
            entry_price,
            f"入场成功: {size} @ {entry_price}",
            stop_price=self.stop_price,
            take_profit_1r=self.take_profit_1r,
            take_profit_2r=self.take_profit_2r
        )

    def update_lowest_price(self, price: float):
        """
        更新入场后的最低价

        Args:
            price: 当前价格
        """
        if self.status == TradeStatus.IN_POSITION:
            if self.lowest_price_since_entry is None or price < self.lowest_price_since_entry:
                self.lowest_price_since_entry = price

    def on_partial_exit(self, size: float, exit_price: float, stage: str):
        """
        部分平仓

        Args:
            size: 平仓数量
            exit_price: 平仓价格
            stage: 阶段 (1r/2r)
        """
        self.position_size -= size

        if stage == "1r":
            self.partial_closed_1r = True
        elif stage == "2r":
            self.partial_closed_2r = True

        pnl = (exit_price - self.entry_price) * size
        self.logger.trade({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "strategy": "trend_long",
            "entry": self.entry_price,
            "stop": self.stop_price,
            "size": size,
            "exit": exit_price,
            "pnl": pnl,
            "reason": f"take_profit_{stage}",
            "partial": True
        })

        self.logger.info(f"部分平仓 {stage}: {size} @ {exit_price}, PnL: {pnl:.2f}")

    def on_full_exit(self, exit_price: float, reason: str):
        """
        全部平仓

        Args:
            exit_price: 平仓价格
            reason: 平仓原因
        """
        pnl = (exit_price - self.entry_price) * self.position_size
        hold_time = (datetime.now() - self.entry_time).total_seconds() if self.entry_time else 0

        self.logger.trade({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "strategy": "trend_long",
            "entry": self.entry_price,
            "stop": self.stop_price,
            "size": self.position_size,
            "exit": exit_price,
            "pnl": pnl,
            "reason": reason,
            "hold_time_seconds": hold_time,
            "trigger_reasons": self.trigger_reasons
        })

        self.logger.info(f"全部平仓 ({reason}): {self.position_size} @ {exit_price}, PnL: {pnl:.2f}, 持仓时间: {hold_time:.0f}秒")

        # 重置状态
        self.reset()

    def reset(self):
        """重置策略状态"""
        self.status = TradeStatus.IDLE
        self.entry_price = None
        self.stop_price = None
        self.take_profit_1r = None
        self.take_profit_2r = None
        self.position_size = 0.0
        self.entry_time = None
        self.risk_amount = 0.0
        self.lowest_price_since_entry = None
        self.trailing_stop_active = False
        self.partial_closed_1r = False
        self.partial_closed_2r = False
        self.trigger_reasons = []

    def set_waiting_entry(self):
        """设置为等待入场状态"""
        self.status = TradeStatus.WAITING_ENTRY

    def get_status(self) -> Dict[str, Any]:
        """
        获取当前状态

        Returns:
            状态字典
        """
        return {
            "status": self.status.value,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "take_profit_1r": self.take_profit_1r,
            "take_profit_2r": self.take_profit_2r,
            "position_size": self.position_size,
            "entry_time": self.entry_time.strftime("%Y-%m-%d %H:%M:%S") if self.entry_time else None,
            "partial_closed_1r": self.partial_closed_1r,
            "partial_closed_2r": self.partial_closed_2r,
            "trailing_stop_active": self.trailing_stop_active,
            "lowest_price_since_entry": self.lowest_price_since_entry
        }
