"""
风控模块
提供各种风控检查功能，确保交易安全
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum


class RiskLevel(Enum):
    """风险级别"""
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"
    BLOCKED = "blocked"


class RiskManager:
    """风控管理器"""

    def __init__(self, config: Dict[str, Any], logger):
        """
        初始化风控管理器

        Args:
            config: 配置字典
            logger: 日志记录器
        """
        self.config = config
        self.logger = logger
        self.risk_params = config.get("risk", {})
        self.market_params = config.get("market", {})

        # 每日统计
        self.start_equity: float = 0.0
        self.current_equity: float = 0.0
        self.daily_trades_count: int = 0
        self.daily_pnl: float = 0.0
        self.max_daily_equity: float = 0.0
        self.trade_history: list = []

        # 每日重置时间
        self.last_reset_date: Optional[str] = None

    def reset_daily(self):
        """重置每日统计数据"""
        today = datetime.now().strftime("%Y-%m-%d")

        if self.last_reset_date != today:
            self.last_reset_date = today
            self.daily_trades_count = 0
            self.daily_pnl = 0.0
            self.trade_history = []

            if self.current_equity > 0:
                self.max_daily_equity = self.current_equity

            self.logger.info("每日风控统计已重置")

    def update_equity(self, equity: float):
        """
        更新账户权益

        Args:
            equity: 当前权益
        """
        if self.start_equity == 0.0:
            self.start_equity = equity

        self.current_equity = equity

        # 更新最高权益
        if equity > self.max_daily_equity:
            self.max_daily_equity = equity

        # 重置每日统计
        self.reset_daily()

    def check_position_risk(
        self,
        equity: float,
        entry_price: float,
        stop_price: float,
        size: float
    ) -> Dict[str, Any]:
        """
        检查仓位风险

        Args:
            equity: 账户权益
            entry_price: 入场价格
            stop_price: 止损价格
            size: 仓位大小

        Returns:
            检查结果字典
        """
        result = {
            "passed": True,
            "risk_amount": 0.0,
            "risk_pct": 0.0,
            "level": RiskLevel.SAFE,
            "message": ""
        }

        # 计算风险金额
        stop_distance = abs(entry_price - stop_price)
        risk_amount = stop_distance * size
        risk_pct = risk_amount / equity if equity > 0 else 0

        result["risk_amount"] = risk_amount
        result["risk_pct"] = risk_pct

        # 检查单笔最大风险
        max_position_risk = self.risk_params.get("max_position_risk", 0.005)

        if risk_pct > max_position_risk:
            result["passed"] = False
            result["level"] = RiskLevel.BLOCKED
            result["message"] = f"单笔风险 {risk_pct:.2%} 超过最大限制 {max_position_risk:.0%}"
            self.logger.risk_check("position_risk", False, result["message"])
        else:
            self.logger.risk_check("position_risk", True, f"单笔风险 {risk_pct:.2%}")

        return result

    def check_daily_drawdown(self) -> Dict[str, Any]:
        """
        检查日回撤

        Returns:
            检查结果字典
        """
        result = {
            "passed": True,
            "drawdown": 0.0,
            "level": RiskLevel.SAFE,
            "message": ""
        }

        if self.max_daily_equity == 0:
            return result

        # 计算回撤
        drawdown = (self.max_daily_equity - self.current_equity) / self.max_daily_equity
        result["drawdown"] = drawdown

        # 检查最大日回撤
        max_daily_drawdown = self.risk_params.get("max_daily_drawdown", 0.02)

        if drawdown >= max_daily_drawdown:
            result["passed"] = False
            result["level"] = RiskLevel.BLOCKED
            result["message"] = f"日回撤 {drawdown:.2%} 超过最大限制 {max_daily_drawdown:.0%}"
            self.logger.risk_check("daily_drawdown", False, result["message"])
        elif drawdown >= max_daily_drawdown * 0.7:
            result["level"] = RiskLevel.WARNING
            result["message"] = f"日回撤 {drawdown:.2%} 接近最大限制"
            self.logger.risk_check("daily_drawdown", True, result["message"])
        else:
            self.logger.risk_check("daily_drawdown", True, f"日回撤 {drawdown:.2%}")

        return result

    def check_trades_limit(self) -> Dict[str, Any]:
        """
        检查每日交易次数限制

        Returns:
            检查结果字典
        """
        result = {
            "passed": True,
            "trades_count": self.daily_trades_count,
            "limit": 0,
            "level": RiskLevel.SAFE,
            "message": ""
        }

        max_trades = self.risk_params.get("max_trades_per_day", 6)
        result["limit"] = max_trades

        if self.daily_trades_count >= max_trades:
            result["passed"] = False
            result["level"] = RiskLevel.BLOCKED
            result["message"] = f"今日交易次数 {self.daily_trades_count} 已达上限 {max_trades}"
            self.logger.risk_check("trades_limit", False, result["message"])
        elif self.daily_trades_count >= max_trades * 0.8:
            result["level"] = RiskLevel.WARNING
            result["message"] = f"今日交易次数 {self.daily_trades_count} 接近上限 {max_trades}"
            self.logger.risk_check("trades_limit", True, result["message"])
        else:
            self.logger.risk_check("trades_limit", True, f"今日交易次数 {self.daily_trades_count}/{max_trades}")

        return result

    def check_funding_rate(self, funding_rate: Optional[float], direction: str) -> Dict[str, Any]:
        """
        检查资金费率限制

        Args:
            funding_rate: 资金费率
            direction: 交易方向 (long/short)

        Returns:
            检查结果字典
        """
        result = {
            "passed": True,
            "funding_rate": funding_rate,
            "level": RiskLevel.SAFE,
            "message": ""
        }

        if funding_rate is None:
            result["message"] = "资金费率数据不可用"
            self.logger.risk_check("funding_rate", True, result["message"])
            return result

        threshold = self.market_params.get("funding_rate_threshold", 0.0003)

        # 资金费率 > +0.03%：不做多
        if direction == "long" and funding_rate > threshold:
            result["passed"] = False
            result["level"] = RiskLevel.BLOCKED
            result["message"] = f"资金费率 {funding_rate:.4f} 过高，禁止做多"
            self.logger.risk_check("funding_rate", False, result["message"])
            return result

        # 资金费率 < -0.03%：不做空
        if direction == "short" and funding_rate < -threshold:
            result["passed"] = False
            result["level"] = RiskLevel.BLOCKED
            result["message"] = f"资金费率 {funding_rate:.4f} 过低，禁止做空"
            self.logger.risk_check("funding_rate", False, result["message"])
            return result

        self.logger.risk_check("funding_rate", True, f"资金费率 {funding_rate:.4f} 正常")
        return result

    def check_all_risks(
        self,
        equity: float,
        entry_price: float,
        stop_price: float,
        size: float,
        funding_rate: Optional[float],
        direction: str
    ) -> Dict[str, Any]:
        """
        综合检查所有风控

        Args:
            equity: 账户权益
            entry_price: 入场价格
            stop_price: 止损价格
            size: 仓位大小
            funding_rate: 资金费率
            direction: 交易方向

        Returns:
            综合检查结果
        """
        results = {
            "position_risk": self.check_position_risk(equity, entry_price, stop_price, size),
            "daily_drawdown": self.check_daily_drawdown(),
            "trades_limit": self.check_trades_limit(),
            "funding_rate": self.check_funding_rate(funding_rate, direction)
        }

        # 判断是否全部通过
        all_passed = all(r["passed"] for r in results.values())

        # 判断最高风险级别
        levels = [r["level"] for r in results.values()]
        if RiskLevel.BLOCKED in levels:
            max_level = RiskLevel.BLOCKED
        elif RiskLevel.DANGER in levels:
            max_level = RiskLevel.DANGER
        elif RiskLevel.WARNING in levels:
            max_level = RiskLevel.WARNING
        else:
            max_level = RiskLevel.SAFE

        return {
            "passed": all_passed,
            "level": max_level,
            "checks": results,
            "message": "所有风控检查通过" if all_passed else "风控检查未通过"
        }

    def record_trade(self, pnl: float):
        """
        记录交易

        Args:
            pnl: 盈亏
        """
        self.daily_trades_count += 1
        self.daily_pnl += pnl

        self.trade_history.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pnl": pnl
        })

        self.logger.info(f"记录交易：今日第 {self.daily_trades_count} 笔，盈亏 {pnl:.2f}")

    def get_daily_summary(self) -> Dict[str, Any]:
        """
        获取每日统计摘要

        Returns:
            统计摘要
        """
        return {
            "date": self.last_reset_date,
            "start_equity": self.start_equity,
            "current_equity": self.current_equity,
            "max_equity": self.max_daily_equity,
            "daily_pnl": self.daily_pnl,
            "daily_pnl_pct": (self.daily_pnl / self.start_equity * 100) if self.start_equity > 0 else 0,
            "daily_drawdown": ((self.max_daily_equity - self.current_equity) / self.max_daily_equity * 100) if self.max_daily_equity > 0 else 0,
            "trades_count": self.daily_trades_count,
            "trade_history": self.trade_history
        }

    def is_trading_allowed(self) -> bool:
        """
        检查是否允许交易

        Returns:
            是否允许
        """
        daily_drawdown_check = self.check_daily_drawdown()
        trades_limit_check = self.check_trades_limit()

        return daily_drawdown_check["passed"] and trades_limit_check["passed"]
