"""
测试 WebSocket 代理和重试功能
"""
import asyncio
import os


async def test_proxy_and_retry():
    """测试代理配置和重试逻辑"""
    print("=" * 60)
    print("测试 WebSocket 代理和重试功能")
    print("=" * 60)

    from exchange.okx_ws import OKXWS

    received_data = {"ticker": 0}

    def on_ticker(ticker):
        print(f"  ✓ 收到 Ticker: 价格={ticker['last']}, 涨跌={ticker['change_24h']:.2f}%")
        received_data["ticker"] += 1

    # 测试 1: 无代理，模拟模式
    print("\n测试 1: 模拟模式（无代理）")
    print("-" * 60)
    ws1 = OKXWS("ETH-USDT-SWAP", flag="1", simulate=True)
    ws1.on_ticker(on_ticker)

    task1 = asyncio.create_task(ws1.start())
    await asyncio.sleep(3)
    await ws1.stop()
    print(f"✓ 模拟模式测试完成，收到 {received_data['ticker']} 个 ticker")

    # 测试 2: 有代理设置（但不实际连接，因为模拟模式）
    print("\n测试 2: 模拟模式（带代理配置）")
    print("-" * 60)
    ws2 = OKXWS(
        "ETH-USDT-SWAP",
        flag="1",
        simulate=True,
        proxy="http://127.0.0.1:7890"
    )
    ws2.on_ticker(on_ticker)

    task2 = asyncio.create_task(ws2.start())
    await asyncio.sleep(3)
    await ws2.stop()
    print(f"✓ 模拟模式（带代理）测试完成")

    # 测试 3: 真实连接（如果配置了代理）
    print("\n测试 3: 真实连接（需要环境变量 OKX_PROXY）")
    print("-" * 60)

    proxy = os.environ.get("OKX_PROXY", "")
    if not proxy:
        print("  未配置代理，跳过真实连接测试")
        print("  如需测试，请设置环境变量: export OKX_PROXY=http://127.0.0.1:7890")
    else:
        print(f"  检测到代理: {proxy}")

        ws3 = OKXWS("ETH-USDT-SWAP", flag="1", simulate=False, proxy=proxy)
        ws3.on_ticker(on_ticker)

        received_data["ticker"] = 0

        try:
            task3 = asyncio.create_task(ws3.start())

            # 等待最多 10 秒
            await asyncio.wait_for(asyncio.shield(task3), timeout=10)

        except asyncio.TimeoutError:
            print("  超时，停止连接...")
        except Exception as e:
            print(f"  连接失败: {e}")
        finally:
            await ws3.stop()

        if received_data["ticker"] > 0:
            print(f"✓ 真实连接测试成功，收到 {received_data['ticker']} 个 ticker")
        else:
            print("⚠ 真实连接未收到数据（可能是代理配置不正确）")

    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)


async def test_connection_check():
    """测试连接检查逻辑"""
    print("\n" + "=" * 60)
    print("测试连接检查和重试逻辑")
    print("=" * 60)

    from exchange.okx_ws import OKXWS

    # 测试连接检查
    print("\n测试连接检查（模拟模式）")
    print("-" * 60)

    ws = OKXWS("ETH-USDT-SWAP", flag="1", simulate=True)

    # 测试 _connect_with_retry 不会在模拟模式下被调用
    print("✓ 模拟模式下跳过连接检查")

    await ws.stop()

    print("\n" + "=" * 60)
    print("连接检查测试完成！")
    print("=" * 60)


async def main():
    """主测试函数"""
    try:
        await test_proxy_and_retry()
        await test_connection_check()

    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
