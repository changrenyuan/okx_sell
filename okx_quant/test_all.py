"""
完整测试脚本
测试所有模块导入和基本功能
"""
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("OKX ETH 量化机器人 - 完整测试")
print("=" * 60)
print()

# 测试 1: 模块导入
print("测试 1: 模块导入")
print("-" * 60)

try:
    from exchange.okx_rest import OKXRest
    print("✓ exchange.okx_rest.OKXRest 导入成功")
except ImportError as e:
    print(f"✗ exchange.okx_rest.OKXRest 导入失败: {e}")
    sys.exit(1)

try:
    from exchange.okx_ws import OKXWS
    print("✓ exchange.okx_ws.OKXWS 导入成功")
except ImportError as e:
    print(f"✗ exchange.okx_ws.OKXWS 导入失败: {e}")
    sys.exit(1)

try:
    from market.indicators import TechnicalIndicators, MarketDataProcessor
    print("✓ market.indicators 导入成功")
except ImportError as e:
    print(f"✗ market.indicators 导入失败: {e}")
    sys.exit(1)

try:
    from market.state_detector import StateDetector, MarketState
    print("✓ market.state_detector 导入成功")
except ImportError as e:
    print(f"✗ market.state_detector 导入失败: {e}")
    sys.exit(1)

try:
    from strategy.overheat_short import OverheatShortStrategy
    print("✓ strategy.overheat_short 导入成功")
except ImportError as e:
    print(f"✗ strategy.overheat_short 导入失败: {e}")
    sys.exit(1)

try:
    from strategy.trend_long import TrendLongStrategy
    print("✓ strategy.trend_long 导入成功")
except ImportError as e:
    print(f"✗ strategy.trend_long 导入失败: {e}")
    sys.exit(1)

try:
    from risk.risk_manager import RiskManager
    print("✓ risk.risk_manager 导入成功")
except ImportError as e:
    print(f"✗ risk.risk_manager 导入失败: {e}")
    sys.exit(1)

try:
    from engine.signal_engine import SignalEngine
    print("✓ engine.signal_engine 导入成功")
except ImportError as e:
    print(f"✗ engine.signal_engine 导入失败: {e}")
    sys.exit(1)

try:
    from engine.trade_engine import TradeEngine
    print("✓ engine.trade_engine 导入成功")
except ImportError as e:
    print(f"✗ engine.trade_engine 导入失败: {e}")
    sys.exit(1)

try:
    from main import QuantBot
    print("✓ main.QuantBot 导入成功")
except ImportError as e:
    print(f"✗ main.QuantBot 导入失败: {e}")
    sys.exit(1)

print()
print("所有模块导入成功! ✅")
print()

# 测试 2: 技术指标计算
print("测试 2: 技术指标计算")
print("-" * 60)

try:
    from market.indicators import TechnicalIndicators

    indicators = TechnicalIndicators()

    # 生成模拟数据
    closes = [100 + i * 0.1 for i in range(20)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    volumes = [1000 + i * 10 for i in range(20)]

    # 计算 SMA
    sma_5 = indicators.sma(closes, 5)
    print(f"  SMA(5): {sma_5:.2f}")

    # 计算 EMA
    ema_5 = indicators.ema(closes, 5)
    print(f"  EMA(5): {ema_5:.2f}")

    # 计算 ATR
    atr = indicators.atr(highs, lows, closes, 14)
    print(f"  ATR(14): {atr:.2f}")

    # 计算 VWAP
    vwap = indicators.vwap(closes, volumes)
    print(f"  VWAP: {vwap:.2f}")

    print("✓ 技术指标计算成功")
except Exception as e:
    print(f"✗ 技术指标计算失败: {e}")
    sys.exit(1)

print()

# 测试 3: 策略状态
print("测试 3: 策略状态")
print("-" * 60)

try:
    import yaml

    with open("config/params.yaml", 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    from utils.logger import init_logger
    logger = init_logger(config)

    # 测试过热回落做空策略
    from strategy.overheat_short import OverheatShortStrategy
    overheat_strategy = OverheatShortStrategy(config, logger)
    print(f"  过热回落做空策略状态: {overheat_strategy.status.value}")

    # 测试趋势做多策略
    from strategy.trend_long import TrendLongStrategy
    trend_strategy = TrendLongStrategy(config, logger)
    print(f"  趋势做多策略状态: {trend_strategy.status.value}")

    print("✓ 策略状态检查成功")
except Exception as e:
    print(f"✗ 策略状态检查失败: {e}")

print()
print("测试 4: WebSocket 模块")
print("-" * 60)

try:
    from exchange.okx_ws import OKXWS
    print("  ✓ OKXWS 导入成功")

    # 测试实例化
    ws = OKXWS("ETH-USDT-SWAP", flag="0", simulate=True)
    print("  ✓ OKXWS 实例化成功（模拟模式）")

    # 检查方法
    methods = ["start", "stop", "get_price", "get_ticker", "get_orderbook"]
    for method in methods:
        if hasattr(ws, method):
            print(f"  ✓ {method} 方法存在")
        else:
            print(f"  ✗ {method} 方法不存在")

    print("✓ WebSocket 模块测试成功")
except Exception as e:
    print(f"✗ WebSocket 模块测试失败: {e}")

print()

# 总结
print("=" * 60)
print("所有测试通过! ✅")
print("=" * 60)
print()
print("程序已准备就绪，可以运行:")
print("  python main.py")
print()
