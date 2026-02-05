"""
测试 python-okx 官方 WebSocket 功能（Async 版本）
"""
import asyncio


async def test_public_ws_async():
    """测试公共频道 WebSocket（Async）"""
    print("=" * 50)
    print("测试官方公共频道 WebSocket (Async)")
    print("=" * 50)

    from okx.websocket.WsPublicAsync import WsPublicAsync

    received_data = {"tickers": 0, "candle": 0, "books": 0}

    def callback(message):
        """回调函数"""
        arg = message.get("arg", {})
        channel = arg.get("channel", "")
        data = message.get("data", [])

        if channel == "tickers" and data:
            ticker = data[0]
            print(f"  ✓ Ticker: 价格={ticker.get('last', 0)}, 涨跌={ticker.get('chg', 0)}%")
            received_data["tickers"] += 1
        elif channel == "candle5m" and data:
            print(f"  ✓ K线 (5m): 最新收盘价={data[0][4]}")
            received_data["candle"] += 1
        elif channel == "books" and data:
            book = data[0]
            asks = book.get("asks", [])[:2]
            bids = book.get("bids", [])[:2]
            print(f"  ✓ 订单簿: 卖单前2={asks}, 买单前2={bids}")
            received_data["books"] += 1

    # 实例化（使用模拟盘）
    ws = WsPublicAsync(url="wss://wspap.okx.com:8443/ws/v5/public?brokerId=9999")

    # 订阅参数
    args = [
        {"channel": "tickers", "instId": "ETH-USDT-SWAP"},
        {"channel": "candle5m", "instId": "ETH-USDT-SWAP"},
        {"channel": "books", "instId": "ETH-USDT-SWAP"}
    ]

    consume_task = None
    try:
        # 先连接
        print("连接 WebSocket...")
        await ws.connect()
        print("连接成功")

        # 订阅
        print("订阅频道...")
        await ws.subscribe(args, callback)
        print(f"订阅成功: {[a['channel'] for a in args]}")

        # 启动消费任务
        print("启动消费任务...")
        consume_task = asyncio.create_task(ws.consume())

        # 等待数据
        print("等待数据（10秒）...\n")
        await asyncio.sleep(10)

    except Exception as e:
        print(f"失败: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 清理
        if consume_task and not consume_task.done():
            consume_task.cancel()
            try:
                await consume_task
            except asyncio.CancelledError:
                pass

        if ws.websocket:
            await ws.websocket.close()
            print("WebSocket 已关闭")

    print(f"\n统计数据: Ticker={received_data['tickers']}, K线={received_data['candle']}, 订单簿={received_data['books']}")

    if received_data["tickers"] > 0:
        print("✅ 公共频道 WebSocket 测试成功")
        return True
    else:
        print("❌ 未收到数据（可能是网络问题）")
        return False


async def test_okxws_wrapper():
    """测试封装后的 OKXWS 类"""
    print("\n" + "=" * 50)
    print("测试封装后的 OKXWS 类")
    print("=" * 50)

    from exchange.okx_ws import OKXWS

    received_data = {"ticker": 0, "orderbook": 0}

    def on_ticker(ticker):
        print(f"  ✓ 收到 Ticker: 价格={ticker['last']}, 涨跌={ticker['change_24h']:.2f}%")
        received_data["ticker"] += 1

    def on_orderbook(orderbook):
        best_bid = orderbook["bids"][0] if orderbook["bids"] else None
        best_ask = orderbook["asks"][0] if orderbook["asks"] else None
        if best_bid and best_ask:
            print(f"  ✓ 收到订单簿: 买一={best_bid[0]:.2f}({best_bid[1]}), 卖一={best_ask[0]:.2f}({best_ask[1]})")
        received_data["orderbook"] += 1

    # 创建实例（使用模拟模式，避免网络问题）
    ws = OKXWS("ETH-USDT-SWAP", flag="1", simulate=True)

    # 注册回调
    ws.on_ticker(on_ticker)
    ws.on_orderbook(on_orderbook)

    try:
        # 启动
        print("启动 OKXWS（模拟模式）...")
        ws_task = asyncio.create_task(ws.start())

        # 等待数据
        print("等待数据（10秒）...\n")
        await asyncio.sleep(10)

    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()

    # 停止
    print("停止 OKXWS...")
    await ws.stop()

    print(f"\n统计数据: Ticker={received_data['ticker']}, 订单簿={received_data['orderbook']}")

    if received_data["ticker"] > 0:
        print("✅ OKXWS 封装测试成功")
        return True
    else:
        print("❌ 未收到数据")
        return False


async def main():
    """主测试函数"""
    try:
        # 测试 1: 原生公共 WebSocket (Async)
        success1 = await test_public_ws_async()

        # 测试 2: 封装后的 OKXWS
        success2 = await test_okxws_wrapper()

        print("\n" + "=" * 50)
        if success1 and success2:
            print("✅ 所有测试通过！")
        else:
            print("⚠️ 部分测试未通过（可能是网络问题）")
        print("=" * 50)

    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
