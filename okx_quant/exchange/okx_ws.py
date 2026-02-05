"""
OKX WebSocket 行情模块
基于 websockets 库实现，不依赖 python-okx 官方 WebSocket
"""
import asyncio
import json
import hmac
import hashlib
import base64
import time
import os
from typing import Dict, Any, Optional, Callable, List

import websockets


class OKXWS:
    """OKX WebSocket 行情客户端（自定义实现）"""

    # OKX WebSocket 端点
    WS_URL_PUBLIC = "wss://ws.okx.com:8443/ws/v5/public"
    WS_URL_PRIVATE = "wss://ws.okx.com:8443/ws/v5/private"
    WS_URL_PUBLIC_DEMO = "wss://wspap.okx.com:8443/ws/v5/public?brokerId=9999"
    WS_URL_PRIVATE_DEMO = "wss://wspap.okx.com:8443/ws/v5/private?brokerId=9999"

    def __init__(self, symbol: str, flag: str = "0", api_key: Optional[str] = None,
                 api_secret: Optional[str] = None, passphrase: Optional[str] = None,
                 simulate: bool = False, proxy: Optional[str] = None):
        """
        初始化 WebSocket 客户端

        Args:
            symbol: 交易对
            flag: 0=实盘，1=模拟盘
            api_key: API Key（私有频道需要）
            api_secret: API Secret（私有频道需要）
            passphrase: API Passphrase（私有频道需要）
            simulate: 是否使用模拟模式（不连接真实 WebSocket）
            proxy: 代理地址，格式如 "http://127.0.0.1:7890"
        """
        self.symbol = symbol
        self.flag = flag
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.simulate = simulate

        # 代理配置
        self.proxy = proxy or os.environ.get("OKX_PROXY", "")

        # WebSocket 连接
        self._ws_public: Optional[websockets.WebSocketClientProtocol] = None
        self._ws_private: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._tasks: List[asyncio.Task] = []

        # 市场数据缓存
        self.last_price: Optional[float] = None
        self.last_ticker: Optional[Dict[str, Any]] = None
        self.last_candles: Dict[str, List[Dict]] = {}
        self.last_orderbook: Optional[Dict[str, Any]] = None

        # 回调函数列表
        self.callbacks: Dict[str, List[Callable]] = {
            "ticker": [],
            "candle": [],
            "orderbook": [],
            "order": [],
            "position": [],
            "balance": []
        }

        if self.proxy:
            print(f"[OKXWS] 使用代理: {self.proxy}")

    def on_ticker(self, callback: Callable):
        """注册 ticker 回调"""
        self.callbacks["ticker"].append(callback)

    def on_candle(self, callback: Callable):
        """注册 K线回调"""
        self.callbacks["candle"].append(callback)

    def on_orderbook(self, callback: Callable):
        """注册订单簿回调"""
        self.callbacks["orderbook"].append(callback)

    def on_order(self, callback: Callable):
        """注册订单更新回调"""
        self.callbacks["order"].append(callback)

    def on_position(self, callback: Callable):
        """注册持仓更新回调"""
        self.callbacks["position"].append(callback)

    def on_balance(self, callback: Callable):
        """注册余额更新回调"""
        self.callbacks["balance"].append(callback)

    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        """
        生成 API 签名

        Args:
            timestamp: 时间戳
            method: 请求方法 (GET/POST)
            request_path: 请求路径
            body: 请求体

        Returns:
            签名字符串
        """
        if not self.api_secret:
            raise ValueError("API Secret is required for signing")

        message = timestamp + method + request_path + body
        mac = hmac.new(
            bytes(self.api_secret, encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        d = mac.digest()
        return base64.b64encode(d).decode()

    def _build_login_params(self) -> Dict:
        """构建登录参数"""
        timestamp = str(time.time())
        sign = self._generate_signature(timestamp, "GET", "/users/self/verify")

        return {
            "op": "login",
            "args": [{
                "apiKey": self.api_key,
                "passphrase": self.passphrase,
                "timestamp": timestamp,
                "sign": sign
            }]
        }

    def _handle_ticker(self, data: List[Dict]):
        """处理 ticker 数据"""
        if not data:
            return

        ticker_data = data[0]
        self.last_price = float(ticker_data.get("last", 0))
        self.last_ticker = {
            "last": self.last_price,
            "bid": float(ticker_data.get("bidPx", 0)),
            "ask": float(ticker_data.get("askPx", 0)),
            "volume_24h": float(ticker_data.get("volCcy24h", 0)),
            "change_24h": float(ticker_data.get("chg", 0)),
            "timestamp": ticker_data.get("ts", "")
        }

        # 触发回调
        for callback in self.callbacks.get("ticker", []):
            try:
                callback(self.last_ticker.copy())
            except Exception as e:
                print(f"[OKXWS] Ticker callback error: {e}")

    def _handle_candle(self, data: List[Dict], timeframe: str):
        """处理 K线数据"""
        if not data:
            return

        candles = []
        for candle in data:
            candles.append({
                "timestamp": candle[0],
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "volume": float(candle[5]),
                "volume_ccy": float(candle[6])
            })

        self.last_candles[timeframe] = candles

        # 触发回调
        for callback in self.callbacks.get("candle", []):
            try:
                callback(timeframe, candles.copy())
            except Exception as e:
                print(f"[OKXWS] Candle callback error: {e}")

    def _handle_orderbook(self, data: List[Dict]):
        """处理订单簿数据"""
        if not data:
            return

        book_data = data[0]
        asks = [[float(bid[0]), float(bid[1])] for bid in book_data.get("asks", [])]
        bids = [[float(ask[0]), float(ask[1])] for ask in book_data.get("bids", [])]

        self.last_orderbook = {
            "asks": asks,
            "bids": bids,
            "timestamp": book_data.get("ts", "")
        }

        # 触发回调
        for callback in self.callbacks.get("orderbook", []):
            try:
                callback(self.last_orderbook.copy())
            except Exception as e:
                print(f"[OKXWS] Orderbook callback error: {e}")

    def _handle_message(self, message: str):
        """处理 WebSocket 消息"""
        try:
            data = json.loads(message)
            arg = data.get("arg", {})
            channel = arg.get("channel", "")
            msg_data = data.get("data", [])

            # 登录响应
            if data.get("event") == "login":
                if data.get("code") == "0":
                    print(f"[OKXWS] 登录成功")
                else:
                    print(f"[OKXWS] 登录失败: {data.get('msg')}")
                return

            # 订阅响应
            if data.get("event") == "subscribe":
                print(f"[OKXWS] 订阅成功: {arg}")
                return

            # 数据消息
            if channel == "tickers":
                self._handle_ticker(msg_data)
            elif channel.startswith("candle"):
                timeframe = channel.replace("candle", "")
                self._handle_candle(msg_data, timeframe)
            elif channel == "books":
                self._handle_orderbook(msg_data)
            elif channel == "orders":
                # 订单更新
                for callback in self.callbacks.get("order", []):
                    try:
                        callback(msg_data)
                    except Exception as e:
                        print(f"[OKXWS] Order callback error: {e}")
            elif channel == "positions":
                # 持仓更新
                for callback in self.callbacks.get("position", []):
                    try:
                        callback(msg_data)
                    except Exception as e:
                        print(f"[OKXWS] Position callback error: {e}")
            elif channel == "account" or channel == "balance_and_position":
                # 余额更新
                for callback in self.callbacks.get("balance", []):
                    try:
                        callback(msg_data)
                    except Exception as e:
                        print(f"[OKXWS] Balance callback error: {e}")

        except json.JSONDecodeError as e:
            print(f"[OKXWS] JSON 解析错误: {e}")
        except Exception as e:
            print(f"[OKXWS] 消息处理错误: {e}")

    async def _connect_ws(self, url: str, name: str) -> websockets.WebSocketClientProtocol:
        """
        连接 WebSocket

        Args:
            url: WebSocket URL
            name: 连接名称

        Returns:
            WebSocket 连接对象
        """
        # 代理支持提示
        if self.proxy:
            print(f"[OKXWS] 注意: websockets 库对代理支持有限")
            print(f"[OKXWS] 如需代理，建议使用系统代理或通过环境变量设置")

        print(f"[OKXWS] 正在连接 {name}: {url}")

        ws = await asyncio.wait_for(
            websockets.connect(url),
            timeout=10
        )

        print(f"[OKXWS] {name} 连接成功")
        return ws

    async def _subscribe_channel(self, ws: websockets.WebSocketClientProtocol, channels: List[Dict]):
        """
        订阅频道

        Args:
            ws: WebSocket 连接
            channels: 频道列表
        """
        msg = {
            "op": "subscribe",
            "args": channels
        }

        await ws.send(json.dumps(msg))
        print(f"[OKXWS] 已发送订阅请求: {[c['channel'] for c in channels]}")

    async def _login(self, ws: websockets.WebSocketClientProtocol):
        """
        登录私有频道

        Args:
            ws: WebSocket 连接
        """
        if not self.api_key or not self.api_secret or not self.passphrase:
            raise ValueError("API Key, Secret and Passphrase are required for login")

        login_params = self._build_login_params()
        await ws.send(json.dumps(login_params))
        print(f"[OKXWS] 已发送登录请求")

    async def _consume_messages(self, ws: websockets.WebSocketClientProtocol, name: str):
        """
        消费消息

        Args:
            ws: WebSocket 连接
            name: 连接名称
        """
        try:
            async for message in ws:
                if not self._running:
                    break
                self._handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            print(f"[OKXWS] {name} 连接已关闭")
        except Exception as e:
            print(f"[OKXWS] {name} 消息消费错误: {e}")

    async def start(self, public_channels: Optional[List[Dict]] = None, private_channels: Optional[List[Dict]] = None):
        """
        启动 WebSocket 连接

        Args:
            public_channels: 公共频道订阅列表
            private_channels: 私有频道订阅列表
        """
        if self._running:
            print("[OKXWS] WebSocket 已经在运行")
            return

        self._running = True

        # 模拟模式
        if self.simulate:
            print("[OKXWS] 模拟模式已启用，生成模拟数据")
            await self._simulate_data()
            return

        # 确定 WebSocket URL
        public_url = self.WS_URL_PUBLIC_DEMO if self.flag == "1" else self.WS_URL_PUBLIC
        private_url = self.WS_URL_PRIVATE_DEMO if self.flag == "1" else self.WS_URL_PRIVATE

        try:
            # 默认公共频道
            if public_channels is None:
                public_channels = [
                    {"channel": "tickers", "instId": self.symbol},
                    {"channel": "candle5m", "instId": self.symbol},
                    {"channel": "candle15m", "instId": self.symbol},
                    {"channel": "books", "instId": self.symbol}
                ]

            # 启动公共频道
            if public_channels:
                print(f"[OKXWS] 启动公共频道 WebSocket")
                self._ws_public = await self._connect_ws(public_url, "公共频道")

                # 订阅
                await self._subscribe_channel(self._ws_public, public_channels)

                # 启动消费任务
                self._tasks.append(asyncio.create_task(self._consume_messages(self._ws_public, "公共频道")))

            # 启动私有频道（如果有 API Key）
            if private_channels and self.api_key and self.api_secret and self.passphrase:
                print(f"[OKXWS] 启动私有频道 WebSocket")
                self._ws_private = await self._connect_ws(private_url, "私有频道")

                # 登录
                await self._login(self._ws_private)

                # 等待登录响应
                await asyncio.sleep(1)

                # 订阅
                await self._subscribe_channel(self._ws_private, private_channels)

                # 启动消费任务
                self._tasks.append(asyncio.create_task(self._consume_messages(self._ws_private, "私有频道")))

            print("[OKXWS] WebSocket 启动完成")

            # 保持协程活跃
            while self._running:
                await asyncio.sleep(1)

        except Exception as e:
            print(f"[OKXWS] WebSocket 启动失败: {e}")
            import traceback
            traceback.print_exc()
            self._running = False

    async def stop(self):
        """停止 WebSocket 连接"""
        if not self._running:
            return

        print("[OKXWS] 正在停止 WebSocket...")
        self._running = False

        # 取消所有任务
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._tasks.clear()

        # 关闭连接
        if self._ws_public:
            try:
                await self._ws_public.close()
                print("[OKXWS] 公共频道已停止")
            except Exception as e:
                print(f"[OKXWS] 停止公共频道错误: {e}")
            self._ws_public = None

        if self._ws_private:
            try:
                await self._ws_private.close()
                print("[OKXWS] 私有频道已停止")
            except Exception as e:
                print(f"[OKXWS] 停止私有频道错误: {e}")
            self._ws_private = None

    def get_price(self) -> Optional[float]:
        """获取最新价格"""
        return self.last_price

    def get_ticker(self) -> Optional[Dict[str, Any]]:
        """获取最新 ticker"""
        return self.last_ticker.copy() if self.last_ticker else None

    def get_candles(self, timeframe: str = "5m") -> List[Dict]:
        """获取 K线数据"""
        return self.last_candles.get(timeframe, []).copy()

    def get_orderbook(self) -> Optional[Dict[str, Any]]:
        """获取订单簿"""
        return self.last_orderbook.copy() if self.last_orderbook else None

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running

    async def _simulate_data(self):
        """生成模拟数据（用于测试）"""
        import random

        print("[OKXWS] 开始生成模拟数据...")

        # 初始化价格
        price = 3200.0

        while self._running:
            # 模拟价格波动
            price += (random.random() * 20 - 10)
            self.last_price = price

            # 模拟 ticker
            self.last_ticker = {
                "last": price,
                "bid": price - 1,
                "ask": price + 1,
                "volume_24h": 1000000 + random.random() * 100000,
                "change_24h": (random.random() * 4 - 2),
                "timestamp": str(int(time.time() * 1000))
            }

            # 触发 ticker 回调
            for callback in self.callbacks.get("ticker", []):
                try:
                    callback(self.last_ticker.copy())
                except Exception as e:
                    print(f"Ticker callback error: {e}")

            # 模拟订单簿
            self.last_orderbook = {
                "asks": [[price + (i + 1) * 0.5, random.randint(1, 100)] for i in range(5)],
                "bids": [[price - (i + 1) * 0.5, random.randint(1, 100)] for i in range(5)],
                "timestamp": str(int(time.time() * 1000))
            }

            # 触发订单簿回调
            for callback in self.callbacks.get("orderbook", []):
                try:
                    callback(self.last_orderbook.copy())
                except Exception as e:
                    print(f"Orderbook callback error: {e}")

            # 模拟 K线（每秒生成一个点）
            if not self.last_candles.get("5m"):
                self.last_candles["5m"] = []

            candle = {
                "timestamp": str(int(time.time() * 1000)),
                "open": price - random.random() * 5,
                "high": price + random.random() * 5,
                "low": price - random.random() * 5,
                "close": price,
                "volume": random.randint(100, 1000),
                "volume_ccy": random.randint(100, 1000) * price
            }

            self.last_candles["5m"].append(candle)

            # 限制 K线数量
            if len(self.last_candles["5m"]) > 100:
                self.last_candles["5m"].pop(0)

            # 触发 K线回调
            for callback in self.callbacks.get("candle", []):
                try:
                    callback("5m", [candle])
                except Exception as e:
                    print(f"Candle callback error: {e}")

            # 等待
            await asyncio.sleep(1)


class PriceCache:
    """价格缓存，用于存储历史价格"""

    def __init__(self, max_size: int = 1000):
        """
        初始化价格缓存

        Args:
            max_size: 最大缓存数量
        """
        self.max_size = max_size
        self.prices: List[float] = []
        self.timestamps: List[float] = []

    def add_price(self, price: float, timestamp: Optional[float] = None):
        """
        添加价格

        Args:
            price: 价格
            timestamp: 时间戳
        """
        if timestamp is None:
            timestamp = time.time()

        self.prices.append(price)
        self.timestamps.append(timestamp)

        # 限制缓存大小
        if len(self.prices) > self.max_size:
            self.prices.pop(0)
            self.timestamps.pop(0)

    def get_prices(self, count: int = 100) -> List[float]:
        """
        获取最近 N 个价格

        Args:
            count: 数量

        Returns:
            价格列表
        """
        return self.prices[-count:]

    def get_timestamps(self, count: int = 100) -> List[float]:
        """
        获取最近 N 个时间戳

        Args:
            count: 数量

        Returns:
            时间戳列表
        """
        return self.timestamps[-count:]

    def clear(self):
        """清空缓存"""
        self.prices = []
        self.timestamps = []

    def size(self) -> int:
        """获取缓存大小"""
        return len(self.prices)
