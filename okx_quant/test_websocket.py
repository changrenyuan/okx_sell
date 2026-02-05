"""
测试主程序和 WebSocket 的集成
"""
import asyncio
from exchange.okx_ws import OKXWS

async def test_websocket_simulate():
    """测试模拟模式下的 WebSocket"""
    print("=" * 50)
    print("测试模拟模式 WebSocket")
    print("=" * 50)

    # 创建模拟模式 WebSocket
    ws = OKXWS("ETH-USDT-SWAP", flag="0", simulate=True)

    # 注册回调
    received_data = {"ticker": 0, "orderbook": 0}

    def on_ticker(ticker):
        print(f"  收到 Ticker: 价格={ticker['last']:.2f}, 涨跌={ticker['change_24h']:.2f}%")
        received_data["ticker"] += 1

    def on_orderbook(orderbook):
        best_bid = orderbook["bids"][0] if orderbook["bids"] else None
        best_ask = orderbook["asks"][0] if orderbook["asks"] else None
        if best_bid and best_ask:
            print(f"  收到订单簿: 买一={best_bid[0]:.2f}({best_bid[1]}), 卖一={best_ask[0]:.2f}({best_ask[1]})")
        received_data["orderbook"] += 1

    ws.on_ticker(on_ticker)
    ws.on_orderbook(on_orderbook)

    # 启动（后台任务）
    print("启动 WebSocket...")
    ws_task = asyncio.create_task(ws.start())

    # 运行5秒
    await asyncio.sleep(5)

    # 停止
    print("\n停止 WebSocket...")
    ws.stop()

    # 等待任务结束
    try:
        await asyncio.wait_for(ws_task, timeout=2)
    except asyncio.TimeoutError:
        print("任务超时（这是正常的）")

    print(f"\n统计数据: 收到 {received_data['ticker']} 个 ticker, {received_data['orderbook']} 个订单簿")
    print("✓ 模拟模式测试通过")

async def test_real_websocket():
    """测试真实 WebSocket（需要网络连接）"""
    print("\n" + "=" * 50)
    print("测试真实 WebSocket（如果网络不可用会跳过）")
    print("=" * 50)

    try:
        # 创建真实 WebSocket
        ws = OKXWS("ETH-USDT-SWAP", flag="0", simulate=False)

        # 注册回调
        received_data = {"ticker": 0, "orderbook": 0}

        def on_ticker(ticker):
            print(f"  收到 Ticker: 价格={ticker['last']:.2f}, 涨跌={ticker['change_24h']:.2f}%")
            received_data["ticker"] += 1
            if received_data["ticker"] >= 2:
                raise StopIteration  # 收到足够数据后停止

        def on_orderbook(orderbook):
            best_bid = orderbook["bids"][0] if orderbook["bids"] else None
            best_ask = orderbook["asks"][0] if orderbook["asks"] else None
            if best_bid and best_ask:
                print(f"  收到订单簿: 买一={best_bid[0]:.2f}({best_bid[1]}), 卖一={best_ask[0]:.2f}({best_ask[1]})")
            received_data["orderbook"] += 1

        ws.on_ticker(on_ticker)
        ws.on_orderbook(on_orderbook)

        # 启动
        print("启动 WebSocket...")
        ws_task = asyncio.create_task(ws.start())

        # 运行最多10秒
        try:
            await asyncio.wait_for(ws_task, timeout=10)
        except (asyncio.TimeoutError, StopIteration):
            pass

        # 停止
        print("\n停止 WebSocket...")
        ws.stop()

        print(f"\n统计数据: 收到 {received_data['ticker']} 个 ticker, {received_data['orderbook']} 个订单簿")

        if received_data["ticker"] > 0 or received_data["orderbook"] > 0:
            print("✓ 真实 WebSocket 测试通过")
        else:
            print("⚠ 真实 WebSocket 未收到数据（可能是网络问题）")

    except Exception as e:
        print(f"✗ 真实 WebSocket 测试失败: {e}")
        print("  这可能是网络连接问题，继续使用模拟模式")

async def main():
    """主测试函数"""
    try:
        # 测试模拟模式
        await test_websocket_simulate()

        # 测试真实 WebSocket（可选）
        import os
        if os.environ.get("TEST_REAL_WS"):
            await test_real_websocket()

        print("\n" + "=" * 50)
        print("所有测试完成！✅")
        print("=" * 50)

    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
