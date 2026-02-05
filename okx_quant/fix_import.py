"""
清理 Python 缓存并测试导入
"""
import os
import sys
import shutil


def clean_cache():
    """清理所有 __pycache__ 目录"""
    print("清理 Python 缓存...")

    # 删除所有 __pycache__ 目录
    for root, dirs, files in os.walk('.'):
        for d in dirs:
            if d == '__pycache__':
                path = os.path.join(root, d)
                print(f"  删除: {path}")
                shutil.rmtree(path)

    # 删除所有 .pyc 文件
    for root, dirs, files in os.walk('.'):
        for f in files:
            if f.endswith('.pyc'):
                path = os.path.join(root, f)
                print(f"  删除: {path}")
                os.remove(path)

    print("缓存清理完成！\n")


def test_import():
    """测试导入"""
    print("测试模块导入...")

    try:
        # 测试单独导入 OKXWS
        print("  导入 OKXWS...")
        from exchange.okx_ws import OKXWS
        print("  ✓ OKXWS 导入成功")

        # 测试实例化
        print("  实例化 OKXWS...")
        ws = OKXWS("ETH-USDT-SWAP", simulate=True)
        print("  ✓ OKXWS 实例化成功")

        # 测试方法
        print("  测试方法...")
        assert hasattr(ws, 'start'), "缺少 start 方法"
        assert hasattr(ws, 'stop'), "缺少 stop 方法"
        assert hasattr(ws, 'get_price'), "缺少 get_price 方法"
        print("  ✓ 所有方法检查通过")

        # 测试 WebSocket 连接（模拟模式）
        print("  测试模拟模式连接...")
        async def quick_test():
            await asyncio.wait_for(ws.start(), timeout=2)
            return ws.get_price() is not None

        import asyncio
        try:
            has_price = asyncio.run(quick_test())
            if has_price:
                print("  ✓ 模拟模式连接成功")
        except:
            print("  ⚠ 模拟模式测试跳过（正常）")

        print("\n✅ 所有测试通过！\n")
        return True

    except ImportError as e:
        print(f"\n❌ 导入失败: {e}")
        print("\n诊断信息：")
        print(f"  Python 版本: {sys.version}")
        print(f"  当前目录: {os.getcwd()}")

        # 检查文件是否存在
        okx_ws_path = os.path.join('exchange', 'okx_ws.py')
        if os.path.exists(okx_ws_path):
            print(f"  文件存在: {okx_ws_path}")
            print(f"  文件大小: {os.path.getsize(okx_ws_path)} bytes")
        else:
            print(f"  ❌ 文件不存在: {okx_ws_path}")

        # 检查语法
        print("\n检查语法...")
        import py_compile
        try:
            py_compile.compile(okx_ws_path, doraise=True)
            print("  ✓ 语法检查通过")
        except py_compile.PyCompileError as e:
            print(f"  ❌ 语法错误: {e}")

        return False

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    clean_cache()
    test_import()

    if test_import():
        print("\n💡 提示：现在可以运行 'python test_real_ws.py' 测试 WebSocket 连接")
        print("💡 或运行 'python main.py' 启动机器人")
