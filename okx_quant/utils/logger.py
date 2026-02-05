"""
日志模块
提供统一的日志记录接口，支持文件输出和控制台输出
"""
import json
from loguru import logger
from datetime import datetime
from typing import Dict, Any, Optional


class TradeLogger:
    """交易日志记录器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._setup_logger()

    def _setup_logger(self):
        """配置日志输出"""
        log_config = self.config.get("logging", {})

        # 移除默认处理器
        logger.remove()

        # 控制台输出
        logger.add(
            sink=lambda msg: print(msg, end=""),
            level=log_config.get("level", "INFO"),
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )

        # 文件输出
        logger.add(
            sink=log_config.get("file", "trade.log"),
            level=log_config.get("level", "INFO"),
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation=log_config.get("rotation", "10 MB"),
            retention=log_config.get("retention", "30 days"),
            encoding="utf-8"
        )

    def info(self, message: str):
        """记录信息"""
        logger.info(message)

    def warning(self, message: str):
        """记录警告"""
        logger.warning(message)

    def error(self, message: str):
        """记录错误"""
        logger.error(message)

    def debug(self, message: str):
        """记录调试信息"""
        logger.debug(message)

    def trade(self, trade_data: Dict[str, Any]):
        """
        记录交易日志（结构化，便于复盘）

        Args:
            trade_data: 交易数据字典，包含以下字段：
                - time: 交易时间
                - strategy: 策略名称
                - entry: 入场价格
                - stop: 止损价格
                - size: 仓位大小
                - exit: 出场价格
                - pnl: 盈亏
                - reason: 交易原因
        """
        log_message = f"[TRADE] {json.dumps(trade_data, ensure_ascii=False)}"
        logger.info(log_message)

    def signal(self, strategy: str, action: str, price: float, reason: str, **kwargs):
        """
        记录信号日志

        Args:
            strategy: 策略名称
            action: 动作 (long/short/close)
            price: 当前价格
            reason: 信号原因
            **kwargs: 其他附加信息
        """
        signal_data = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "strategy": strategy,
            "action": action,
            "price": price,
            "reason": reason,
            **kwargs
        }
        logger.info(f"[SIGNAL] {json.dumps(signal_data, ensure_ascii=False)}")

    def risk_check(self, check_type: str, passed: bool, details: str):
        """
        记录风控检查日志

        Args:
            check_type: 检查类型
            passed: 是否通过
            details: 详细信息
        """
        status = "PASS" if passed else "FAIL"
        logger.info(f"[RISK] {check_type} - {status} - {details}")

    def market_state(self, state: str, price: float, details: str):
        """
        记录市场状态

        Args:
            state: 市场状态 (OVERHEATED/TRENDING/NEUTRAL)
            price: 当前价格
            details: 详细信息
        """
        state_data = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "state": state,
            "price": price,
            "details": details
        }
        logger.info(f"[MARKET_STATE] {json.dumps(state_data, ensure_ascii=False)}")

    def order(self, order_data: Dict[str, Any]):
        """
        记录订单日志

        Args:
            order_data: 订单数据
        """
        logger.info(f"[ORDER] {json.dumps(order_data, ensure_ascii=False)}")

    def exception(self, exc: Exception, context: str = ""):
        """
        记录异常日志

        Args:
            exc: 异常对象
            context: 上下文信息
        """
        logger.exception(f"[EXCEPTION] {context}: {str(exc)}")


# 全局日志实例
_logger_instance: Optional[TradeLogger] = None


def init_logger(config: Dict[str, Any]) -> TradeLogger:
    """
    初始化日志记录器

    Args:
        config: 配置字典

    Returns:
        TradeLogger 实例
    """
    global _logger_instance
    _logger_instance = TradeLogger(config)
    return _logger_instance


def get_logger() -> Optional[TradeLogger]:
    """
    获取全局日志实例

    Returns:
        TradeLogger 实例
    """
    return _logger_instance


def log_trade(msg: str):
    """便捷函数：记录交易日志"""
    if _logger_instance:
        _logger_instance.info(msg)


def log_info(msg: str):
    """便捷函数：记录信息"""
    if _logger_instance:
        _logger_instance.info(msg)


def log_error(msg: str):
    """便捷函数：记录错误"""
    if _logger_instance:
        _logger_instance.error(msg)


def log_warning(msg: str):
    """便捷函数：记录警告"""
    if _logger_instance:
        _logger_instance.warning(msg)
