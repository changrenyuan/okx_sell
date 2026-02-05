"""
OKX ETH 量化交易机器人主程序
"""
import asyncio
import yaml
import sys
import signal

from exchange.okx_rest import OKXRest
from exchange.okx_ws import OKXWS
from utils.logger import init_logger, get_logger
from risk.risk_manager import RiskManager
from engine.signal_engine import SignalEngine
from engine.trade_engine import TradeEngine


class QuantBot:
    """量化交易机器人"""

    def __init__(self, config_path: str = "config/params.yaml"):
        """
        初始化交易机器人

        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        self.config = self._load_config(config_path)

        # 初始化日志
        self.logger = init_logger(self.config)

        # 获取配置
        api_config = self.config.get("api", {})
        trade_config = self.config.get("trade", {})

        # 初始化 OKX REST
        self.okx_rest = OKXRest(
            api_key=api_config.get("key"),
            api_secret=api_config.get("secret"),
            passphrase=api_config.get("passphrase"),
            flag=api_config.get("flag", "0")
        )

        # 初始化风控管理器
        self.risk_manager = RiskManager(self.config, self.logger)

        # 初始化信号引擎
        self.signal_engine = SignalEngine(self.config, self.logger)

        # 初始化交易引擎
        self.trade_engine = TradeEngine(
            self.config,
            self.okx_rest,
            self.risk_manager,
            self.signal_engine,
            self.logger
        )

        # 初始化 WebSocket
        self.ws = OKXWS(
            symbol=trade_config.get("symbol", "ETH-USDT-SWAP"),
            flag=api_config.get("flag", "0")
        )

        # 运行状态
        self.running = False

    def _load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"加载配置文件失败: {str(e)}")
            sys.exit(1)

    async def start(self):
        """启动机器人"""
        self.logger.info("=" * 50)
        self.logger.info("OKX ETH 量化交易机器人启动")
        self.logger.info("=" * 50)

        self.running = True

        try:
            # 初始化交易引擎
            self.trade_engine.initialize()

            # 启动 WebSocket
            self.logger.info("启动 WebSocket 行情订阅...")
            ws_task = asyncio.create_task(self._run_ws())

            # 主循环
            self.logger.info("进入主循环...")
            await self._main_loop()

        except KeyboardInterrupt:
            self.logger.info("收到中断信号，正在停止...")
        except Exception as e:
            self.logger.error(f"运行异常: {str(e)}")
        finally:
            await self.stop()

    async def _run_ws(self):
        """运行 WebSocket"""
        try:
            await self.ws.start()
        except Exception as e:
            self.logger.error(f"WebSocket 异常: {str(e)}")

    async def _main_loop(self):
        """主循环"""
        check_interval = 5  # 检查间隔（秒）

        while self.running:
            try:
                # 获取当前价格
                price = self.ws.get_price()
                if not price:
                    await asyncio.sleep(1)
                    continue

                # 获取市场数据
                ticker = self.ws.get_ticker()
                candles_5m = self.ws.get_candles("5m")
                candles_15m = self.ws.get_candles("15m")
                orderbook = self.ws.get_orderbook()

                # 获取资金费率（每5分钟更新一次）
                funding_rate = None
                if int(asyncio.get_event_loop().time()) % 300 == 0:
                    try:
                        funding_rate = self.okx_rest.get_funding_rate(self.config["trade"]["symbol"])
                    except:
                        pass

                # 更新市场数据
                daily_change = ticker.get("change_24h", 0.0) if ticker else 0.0

                self.signal_engine.update_market_data(
                    price=price,
                    daily_change=daily_change,
                    candles_5m=candles_5m,
                    candles_15m=candles_15m,
                    funding_rate=funding_rate,
                    orderbook=orderbook
                )

                # 更新策略状态
                self.signal_engine.update_strategy_status(price)

                # 检查是否允许交易
                if not self.risk_manager.is_trading_allowed():
                    self.logger.warning("当前不允许交易（风控限制）")
                    await asyncio.sleep(check_interval)
                    continue

                # 检查持仓状态
                position = self.trade_engine.get_position()

                if position:
                    # 有持仓，检查是否需要出场
                    exit_signal = self.trade_engine.check_exit()
                    if exit_signal:
                        self.logger.info(f"检测到出场信号: {exit_signal['exit_reason']}")
                        self.trade_engine.execute_exit(exit_signal)
                else:
                    # 无持仓，检查是否有入场信号
                    signal = self.signal_engine.generate_signal()
                    if signal:
                        self.logger.info(f"检测到入场信号: {signal['strategy']} {signal['direction']}")
                        self.trade_engine.process_entry_signal(signal)

                # 等待下一次检查
                await asyncio.sleep(check_interval)

            except Exception as e:
                self.logger.error(f"主循环异常: {str(e)}")
                await asyncio.sleep(check_interval)

    async def stop(self):
        """停止机器人"""
        self.logger.info("正在停止机器人...")
        self.running = False

        # 停止 WebSocket
        self.ws.stop()

        # 获取每日统计
        summary = self.risk_manager.get_daily_summary()
        self.logger.info("=" * 50)
        self.logger.info("每日统计摘要")
        self.logger.info("=" * 50)
        self.logger.info(f"日期: {summary.get('date')}")
        self.logger.info(f"起始权益: {summary.get('start_equity', 0):.2f} USDT")
        self.logger.info(f"当前权益: {summary.get('current_equity', 0):.2f} USDT")
        self.logger.info(f"最高权益: {summary.get('max_equity', 0):.2f} USDT")
        self.logger.info(f"日盈亏: {summary.get('daily_pnl', 0):.2f} USDT ({summary.get('daily_pnl_pct', 0):.2f}%)")
        self.logger.info(f"日回撤: {summary.get('daily_drawdown', 0):.2f}%")
        self.logger.info(f"交易次数: {summary.get('trades_count', 0)}")
        self.logger.info("=" * 50)

        self.logger.info("机器人已停止")


def main():
    """主函数"""
    # 创建机器人实例
    bot = QuantBot()

    # 注册信号处理
    def signal_handler(sig, frame):
        print("\n收到停止信号...")
        asyncio.create_task(bot.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 启动机器人
    asyncio.run(bot.start())


if __name__ == "__main__":
    main()
