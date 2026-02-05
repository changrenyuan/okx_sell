"""
过热回落做空策略
专门针对 ETH 的过热回落做空策略
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


class OverheatShortStrategy:
    """过热回落做空策略"""

    def __init__(self, config: Dict[str, Any], logger):
        """
        初始化策略

        Args:
            config: 配置字典
            logger: 日志记录器
        """
        self.config = config
        self.logger = logger
        self.params = config.get("strategy_overheat_short", {})
        self.market_params = config.get("market", {})

        # 策略状态
        self.status = TradeStatus.IDLE
        self.entry_price: Optional[float] = None
        self.stop_price: Optional[float] = None
        self.take_profit_1r: Optional[float] = None
        self.take_profit_2r: Optional[float] = None
        self.position_size: float = 0.0
        self.entry_time: Optional[datetime] = None
        self.risk_amount: float = 0.0
        self.partial_closed_1r: bool = False  # 是否已经平仓过1R

        # 历史数据缓存（用于判断MA死叉）
        self.ma_5_history: List[float] = []
        self.ma_15_history: List[float] = []

        # 记录策略触发原因
        self.trigger_reasons: List[str] = []

    def check_entry_conditions(
        self,
        current_price: float,
        vwap: Optional[float],
        ma_5: Optional[float],
        ma_15: Optional[float],
        ma_5_prev: Optional[float],
        ma_15_prev: Optional[float],
        volumes_5m: List[float],
        orderbook_bids: List[List[float]],
        prev_orderbook_bids: List[List[float]]
    ) -> bool:
        """
        检查入场条件

        Args:
            current_price: 当前价格
            vwap: VWAP 值
            ma_5: MA5
            ma_15: MA15
            ma_5_prev: 前一期 MA5
            ma_15_prev: 前一期 MA15
            volumes_5m: 5分钟成交量列表
            orderbook_bids: 买盘深度
            prev_orderbook_bids: 前一次买盘深度

        Returns:
            是否满足入场条件
        """
        if self.status != TradeStatus.WAITING_ENTRY:
            return False

        conditions_met = 0
        self.trigger_reasons = []

        # 条件1：5min K 线收盘价跌破 VWAP
        if vwap and current_price < vwap:
            conditions_met += 1
            self.trigger_reasons.append(f"价格 {current_price:.2f} 跌破 VWAP {vwap:.2f}")

        # 条件2：5min / 15min MA 死叉
        death_cross = False
        if ma_5 and ma_15 and ma_5_prev and ma_15_prev:
            if ma_5_prev >= ma_15_prev and ma_5 < ma_15:
                death_cross = True
                conditions_met += 1
                self.trigger_reasons.append(f"MA 死叉：{ma_5_prev:.2f} > {ma_15_prev:.2f} → {ma_5:.2f} < {ma_15:.2f}")

        # 条件3：买盘深度（前5档）减少 ≥ 20%
        depth_dropped = False
        if orderbook_bids and prev_orderbook_bids and len(orderbook_bids) >= 5 and len(prev_orderbook_bids) >= 5:
            current_bid_volume = sum(size for _, size in orderbook_bids[:5])
            prev_bid_volume = sum(size for _, size in prev_orderbook_bids[:5])

            if prev_bid_volume > 0:
                drop_ratio = (prev_bid_volume - current_bid_volume) / prev_bid_volume
                threshold = self.market_params.get("volume_drop_threshold", 0.2)

                if drop_ratio >= threshold:
                    depth_dropped = True
                    conditions_met += 1
                    self.trigger_reasons.append(f"买盘深度减少 {drop_ratio:.1%}")

        # 满足其中 2 条即可入场
        if conditions_met >= 2:
            self.logger.signal(
                "overheat_short",
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
        highest_price: Optional[float] = None
    ) -> Optional[str]:
        """
        检查出场条件

        Args:
            current_price: 当前价格
            highest_price: 持仓期间的最高价

        Returns:
            出场原因 (stop_loss/take_profit_1r/take_profit_2r/time_out/None)
        """
        if self.status != TradeStatus.IN_POSITION:
            return None

        # 检查止损
        if self.stop_price and current_price >= self.stop_price:
            return "stop_loss"

        # 检查止盈 1R（平50%）
        if not self.partial_closed_1r and self.take_profit_1r and current_price <= self.take_profit_1r:
            return "take_profit_1r"

        # 检查止盈 1.5R（全平）
        if self.take_profit_2r and current_price <= self.take_profit_2r:
            return "take_profit_2r"

        # 检查持仓时间
        if self.entry_time:
            elapsed = (datetime.now() - self.entry_time).total_seconds()
            max_hold_time = self.params.get("max_hold_time", 1800)
            min_hold_time = self.params.get("min_hold_time", 600)

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
        highest_price: Optional[float]
    ) -> Dict[str, Any]:
        """
        准备入场（计算各种价格）

        Args:
            equity: 账户权益
            current_price: 当前价格
            highest_price: 最近高点

        Returns:
            入场信息字典
        """
        # 计算止损价格：最近高点 + 0.25%
        stop_offset = self.params.get("stop_loss_offset", 0.0025)
        if highest_price:
            self.stop_price = highest_price * (1 + stop_offset)
        else:
            self.stop_price = current_price * (1 + stop_offset)

        # 计算仓位大小
        self.position_size = self.calculate_position_size(equity, current_price, self.stop_price)

        # 计算止盈价格
        take_profit_1r_ratio = self.params.get("take_profit_1r", 1.0)
        take_profit_2r_ratio = self.params.get("take_profit_2r", 1.5)

        risk_per_unit = abs(self.stop_price - current_price)
        self.take_profit_1r = current_price - risk_per_unit * take_profit_1r_ratio
        self.take_profit_2r = current_price - risk_per_unit * take_profit_2r_ratio

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
        self.partial_closed_1r = False

        # 重新计算止损和止盈
        if self.stop_price:
            risk_per_unit = abs(self.stop_price - entry_price)
            self.take_profit_1r = entry_price - risk_per_unit * self.params.get("take_profit_1r", 1.0)
            self.take_profit_2r = entry_price - risk_per_unit * self.params.get("take_profit_2r", 1.5)

        self.logger.signal(
            "overheat_short",
            "entry_filled",
            entry_price,
            f"入场成功: {size} @ {entry_price}",
            stop_price=self.stop_price,
            take_profit_1r=self.take_profit_1r,
            take_profit_2r=self.take_profit_2r
        )

    def on_partial_exit(self, size: float, exit_price: float):
        """
        部分平仓

        Args:
            size: 平仓数量
            exit_price: 平仓价格
        """
        self.position_size -= size
        self.partial_closed_1r = True

        pnl = (self.entry_price - exit_price) * size
        self.logger.trade({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "strategy": "overheat_short",
            "entry": self.entry_price,
            "stop": self.stop_price,
            "size": size,
            "exit": exit_price,
            "pnl": pnl,
            "reason": "take_profit_1r",
            "partial": True
        })

        self.logger.info(f"部分平仓 1R: {size} @ {exit_price}, PnL: {pnl:.2f}")

    def on_full_exit(self, exit_price: float):
        """
        全部平仓

        Args:
            exit_price: 平仓价格
        """
        pnl = (self.entry_price - exit_price) * self.position_size
        hold_time = (datetime.now() - self.entry_time).total_seconds() if self.entry_time else 0

        self.logger.trade({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "strategy": "overheat_short",
            "entry": self.entry_price,
            "stop": self.stop_price,
            "size": self.position_size,
            "exit": exit_price,
            "pnl": pnl,
            "reason": "full_exit",
            "hold_time_seconds": hold_time,
            "trigger_reasons": self.trigger_reasons
        })

        self.logger.info(f"全部平仓: {self.position_size} @ {exit_price}, PnL: {pnl:.2f}, 持仓时间: {hold_time:.0f}秒")

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
        self.partial_closed_1r = False
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
            "partial_closed_1r": self.partial_closed_1r
        }
