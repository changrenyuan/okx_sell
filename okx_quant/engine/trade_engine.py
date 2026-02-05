"""
交易引擎
负责执行交易、订单管理、止损止盈等
"""
from typing import Dict, Any, Optional
from datetime import datetime
import time


class TradeEngine:
    """交易引擎"""

    def __init__(self, config: Dict[str, Any], okx_rest, risk_manager, signal_engine, logger):
        """
        初始化交易引擎

        Args:
            config: 配置字典
            okx_rest: OKX REST 客户端
            risk_manager: 风控管理器
            signal_engine: 信号引擎
            logger: 日志记录器
        """
        self.config = config
        self.okx_rest = okx_rest
        self.risk_manager = risk_manager
        self.signal_engine = signal_engine
        self.logger = logger

        self.trade_config = config.get("trade", {})
        self.symbol = self.trade_config.get("symbol", "ETH-USDT-SWAP")
        self.leverage = self.trade_config.get("leverage", 2)

        # 当前持仓状态
        self.current_position: Optional[Dict[str, Any]] = None
        self.current_strategy: Optional[str] = None

    def initialize(self):
        """初始化交易引擎"""
        # 设置杠杆
        self.logger.info(f"设置杠杆: {self.leverage}x")
        try:
            self.okx_rest.set_leverage(self.symbol, self.leverage, "isolated")
        except Exception as e:
            self.logger.error(f"设置杠杆失败: {str(e)}")
            raise

        # 获取账户权益
        equity = self.okx_rest.get_equity()
        self.risk_manager.update_equity(equity)
        self.logger.info(f"账户权益: {equity:.2f} USDT")

    def process_entry_signal(self, signal: Dict[str, Any]) -> bool:
        """
        处理入场信号

        Args:
            signal: 交易信号

        Returns:
            是否成功处理
        """
        strategy_name = signal["strategy"]
        direction = signal["direction"]
        price = signal["price"]

        self.logger.info(f"处理入场信号: {strategy_name} {direction} @ {price}")

        # 检查风控
        equity = self.okx_rest.get_equity()
        self.risk_manager.update_equity(equity)

        # 准备交易信息
        trade_info = self.signal_engine.prepare_trade(signal, equity)

        if not trade_info:
            self.logger.error("准备交易信息失败")
            return False

        # 检查风控
        risk_check = self.risk_manager.check_all_risks(
            equity=equity,
            entry_price=trade_info["entry_price"],
            stop_price=trade_info["stop_price"],
            size=trade_info["position_size"],
            funding_rate=self.signal_engine.funding_rate,
            direction=direction
        )

        if not risk_check["passed"]:
            self.logger.warning(f"风控检查未通过: {risk_check['message']}")
            return False

        # 执行下单
        try:
            # 下限价单（略低于/高于当前价）
            slippage = 0.001  # 0.1% 滑点
            if direction == "long":
                limit_price = price * (1 - slippage)
            else:
                limit_price = price * (1 + slippage)

            order = self.okx_rest.place_order(
                symbol=self.symbol,
                side="buy" if direction == "long" else "sell",
                size=trade_info["position_size"],
                order_type="limit",
                price=limit_price
            )

            self.logger.order(order)
            self.logger.info(f"限价单已提交: {trade_info['position_size']} @ {limit_price:.2f}")

            # 等待成交（简化处理，实际应该查询订单状态）
            time.sleep(2)

            # 确认成交（简化处理，使用实际成交价格）
            actual_price = price  # 实际应该从订单获取
            size = trade_info["position_size"]

            # 立刻挂止损单
            self._place_stop_loss(strategy_name, direction, trade_info["stop_price"], size)

            # 挂止盈单
            self._place_take_profit(strategy_name, direction, trade_info, size)

            # 更新策略状态
            if strategy_name == "overheat_short":
                self.signal_engine.overheat_strategy.on_entry(actual_price, size)
            elif strategy_name == "trend_long":
                self.signal_engine.trend_strategy.on_entry(actual_price, size)

            # 更新当前持仓状态
            self.current_position = {
                "strategy": strategy_name,
                "direction": direction,
                "entry_price": actual_price,
                "size": size,
                "stop_price": trade_info["stop_price"],
                "take_profit_1r": trade_info.get("take_profit_1r"),
                "take_profit_2r": trade_info.get("take_profit_2r"),
                "entry_time": datetime.now()
            }
            self.current_strategy = strategy_name

            self.logger.info(f"入场成功: {strategy_name} {direction} {size} @ {actual_price:.2f}")
            return True

        except Exception as e:
            self.logger.exception(e, f"下单失败: {strategy_name} {direction}")
            return False

    def _place_stop_loss(self, strategy_name: str, direction: str, stop_price: float, size: float):
        """
        下止损单

        Args:
            strategy_name: 策略名称
            direction: 方向
            stop_price: 止损价格
            size: 数量
        """
        try:
            # 做多的止损是 sell，做空的止损是 buy
            stop_side = "sell" if direction == "long" else "buy"

            # 使用市价止损单（简化处理）
            self.logger.info(f"准备止损单: {stop_side} {size} @ {stop_price:.2f}")
            # 实际应该使用条件单或止损单
        except Exception as e:
            self.logger.error(f"下止损单失败: {str(e)}")

    def _place_take_profit(self, strategy_name: str, direction: str, trade_info: Dict[str, Any], size: float):
        """
        下止盈单

        Args:
            strategy_name: 策略名称
            direction: 方向
            trade_info: 交易信息
            size: 数量
        """
        try:
            tp1r = trade_info.get("take_profit_1r")
            tp2r = trade_info.get("take_profit_2r")

            if tp1r:
                self.logger.info(f"准备止盈单1R: {direction} {size} @ {tp1r:.2f}")

            if tp2r:
                self.logger.info(f"准备止盈单1.5R: {direction} {size} @ {tp2r:.2f}")

        except Exception as e:
            self.logger.error(f"下止盈单失败: {str(e)}")

    def check_exit(self) -> Optional[Dict[str, Any]]:
        """
        检查是否需要出场

        Returns:
            出场信号字典，None 表示不需要出场
        """
        if not self.current_position or not self.current_strategy:
            return None

        # 检查策略出场信号
        exit_reason = self.signal_engine.check_exit_signal(self.current_strategy)

        if exit_reason:
            return {
                "strategy": self.current_strategy,
                "direction": self.current_position["direction"],
                "exit_reason": exit_reason,
                "size": self.current_position["size"]
            }

        return None

    def execute_exit(self, exit_signal: Dict[str, Any]) -> bool:
        """
        执行出场

        Args:
            exit_signal: 出场信号

        Returns:
            是否成功
        """
        strategy_name = exit_signal["strategy"]
        direction = exit_signal["direction"]
        exit_reason = exit_signal["exit_reason"]
        size = exit_signal["size"]

        self.logger.info(f"执行出场: {strategy_name} {direction}, 原因: {exit_reason}")

        try:
            # 计算平仓方向
            close_side = "sell" if direction == "long" else "buy"

            # 判断是部分平仓还是全部平仓
            if exit_reason == "take_profit_1r":
                # 1R 平50%（过热）或30%（趋势）
                if strategy_name == "overheat_short":
                    close_size = size * 0.5
                else:
                    close_size = size * 0.3

                # 部分平仓
                order = self.okx_rest.place_order(
                    symbol=self.symbol,
                    side=close_side,
                    size=close_size,
                    reduce_only=True
                )

                # 获取当前价格
                current_price = self.signal_engine.current_price or self.current_position["entry_price"]

                if strategy_name == "overheat_short":
                    self.signal_engine.overheat_strategy.on_partial_exit(close_size, current_price)
                else:
                    self.signal_engine.trend_strategy.on_partial_exit(close_size, current_price, "1r")

                return True

            elif exit_reason == "take_profit_2r":
                # 1.5R 平50%（趋势）
                if strategy_name == "trend_long":
                    close_size = self.current_position["size"] * 0.5

                    # 部分平仓
                    order = self.okx_rest.place_order(
                        symbol=self.symbol,
                        side=close_side,
                        size=close_size,
                        reduce_only=True
                    )

                    current_price = self.signal_engine.current_price or self.current_position["entry_price"]
                    self.signal_engine.trend_strategy.on_partial_exit(close_size, current_price, "2r")

                    return True

            else:
                # 全部平仓（止损、超时、移动止损等）
                order = self.okx_rest.close_position(
                    symbol=self.symbol,
                    side=close_side,
                    size=size
                )

                # 获取当前价格
                current_price = self.signal_engine.current_price or self.current_position["entry_price"]

                # 计算盈亏
                if direction == "long":
                    pnl = (current_price - self.current_position["entry_price"]) * size
                else:
                    pnl = (self.current_position["entry_price"] - current_price) * size

                # 记录交易
                self.risk_manager.record_trade(pnl)

                if strategy_name == "overheat_short":
                    self.signal_engine.overheat_strategy.on_full_exit(current_price)
                else:
                    self.signal_engine.trend_long.on_full_exit(current_price, exit_reason)

                # 清空持仓状态
                self.current_position = None
                self.current_strategy = None

                return True

        except Exception as e:
            self.logger.exception(e, f"平仓失败: {strategy_name} {exit_reason}")
            return False

    def get_position(self) -> Optional[Dict[str, Any]]:
        """
        获取当前持仓

        Returns:
            持仓信息
        """
        if not self.current_position:
            return None

        return {
            **self.current_position,
            "strategy_status": self.signal_engine.get_strategy_status(self.current_strategy)
        }
