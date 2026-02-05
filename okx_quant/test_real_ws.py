"""
测试真实的 WebSocket 连接
基于成功的 OKX WebSocket 连接代码
"""
import asyncio
from exchange.okx_ws import OKXWS


async def test_real_connection():
    """测试真实的 WebSocket 连接"""
    print("=" * 60)
    print("测试真实的 OKX WebSocket 连接")
    print("=" * 60)

    received_data = {"ticker": 0, "orderbook": 0}

    def on_ticker(ticker):
        print(f"  ✓ 收到 Ticker: 价格={ticker['last']}, 涨跌={ticker['change_24h']:.2f}%")
        received_data["ticker"] += 1

        # 收到 3 个 ticker 后退出
        if received_data["ticker"] >= 3:
            print("\n✅ 连接成功！已收到足够数据")
            return False  # 停止
        return True

    def on_orderbook(orderbook):
        best_bid = orderbook["bids"][0] if orderbook["bids"] else None
        best_ask = orderbook["asks"][0] if orderbook["asks"] else None
        if best_bid and best_ask:
            print(f"  ✓ 收到订单簿: 买一={best_bid[0]:.2f}({best_bid[1]}), 卖一={best_ask[0]:.2f}({best_ask[1]})")
        received_data["orderbook"] += 1

    # 创建实例（实盘连接，但只订阅公共频道）
    ws = OKXWS("ETH-USDT-SWAP", flag="0", simulate=False)

    # 注册回调
    ws.on_ticker(on_ticker)
    ws.on_orderbook(on_orderbook)

    try:
        print("启动 WebSocket 连接...")
        print("（这需要网络连接，如果失败请检查网络或使用代理）")
        print()

        # 启动 WebSocket
        await ws.start()

    except Exception as e:
        print(f"\n❌ 连接失败: {e}")
        import traceback
        traceback.print_exc()

        print("\n提示：")
        print("1. 检查网络连接")
        print("2. 如果在国内，可能需要配置代理")
        print("3. 可以使用模拟模式测试: python test_websocket.py")
        return False

    finally:
        print("\n停止 WebSocket...")
        await ws.stop()

    print(f"\n统计数据: Ticker={received_data['ticker']}, 订单簿={received_data['orderbook']}")

    if received_data["ticker"] > 0:
        print("✅ 真实 WebSocket 测试成功")
        return True
    else:
        print("❌ 未收到数据")
        return False


async def test_simulate_mode():
    """测试模拟模式"""
    print("\n" + "=" * 60)
    print("测试模拟模式（推荐用于测试）")
    print("=" * 60)

    received_data = {"ticker": 0}

    def on_ticker(ticker):
        print(f"  ✓ 模拟 Ticker: 价格={ticker['last']:.2f}")
        received_data["ticker"] += 1

    ws = OKXWS("ETH-USDT-SWAP", simulate=True)
    ws.on_ticker(on_ticker)

    task = asyncio.create_task(ws.start())

    # 运行 3 秒
    await asyncio.sleep(3)

    await ws.stop()

    if received_data["ticker"] > 0:
        print(f"\n✅ 模拟模式测试成功，收到 {received_data['ticker']} 个 ticker")
        return True
    return False


async def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("OKX WebSocket 连接测试")
    print("=" * 60)
    print()

    # 先测试模拟模式
    simulate_ok = await test_simulate_mode()

    # 询问是否测试真实连接
    print("\n" + "=" * 60)
    response = input("是否测试真实的 WebSocket 连接？(y/n): ").strip().lower()

    if response == 'y':
        real_ok = await test_real_connection()

        if real_ok:
            print("\n" + "=" * 60)
            print("✅ 所有测试通过！")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("⚠️ 真实连接失败，但模拟模式正常")
            print("   建议使用模拟模式进行开发测试")
            print("=" * 60)
    else:
        if simulate_ok:
            print("\n" + "=" * 60)
            print("✅ 模拟模式测试通过！")
            print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
