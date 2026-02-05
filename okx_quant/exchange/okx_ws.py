"""
OKX WebSocket 行情模块
基于 websockets 库实现，参考成功的 OKX WebSocket 连接代码
"""
import asyncio
import json
import ssl
import certifi
import hmac
import hashlib
import base64
import time
import os
from typing import Dict, Any, Optional, Callable, List

import websockets


class OKXWS:
    """OKX WebSocket 行情客户端（基于成功案例实现）"""

    # OKX WebSocket 端点（使用正确的端口 443）
    WS_URL_PUBLIC = "wss://ws.okx.com:443/ws/v5/public"
    WS_URL_PRIVATE = "wss://ws.okx.com:443/ws/v5/private"
    WS_URL_PUBLIC_DEMO = "wss://wspap.okx.com:443/ws/v5/public?brokerId=9999"
    WS_URL_PRIVATE_DEMO = "wss://wspap.okx.com:443/ws/v5/private?brokerId=9999"

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
            proxy: 代理地址（暂不支持，websockets 库限制）
        """
        self.symbol = symbol
        self.flag = flag
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.simulate = simulate
        self.proxy = proxy

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

        # SSL 上下文
        self._ssl_context = ssl.create_default_context(cafile=certifi.where())

        if self.proxy:
            print(f"[OKXWS] 注意: websockets 库对代理支持有限")

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

    def _get_timestamp(self) -> str:
        """获取 ISO 格式时间戳"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()[:-6] + 'Z'

    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        """
        生成 API 签名

        Args:
            timestamp: ISO 格式时间戳
            method: 请求方法 (GET/POST)
            request_path: 请求路径
            body: 请求体

        Returns:
            签名字符串
        """
        if not self.api_secret:
            raise ValueError("API Secret is required for signing")

        message = timestamp + method.upper() + request_path + body
        mac = hmac.new(
            bytes(self.api_secret, encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode("utf-8")

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
            elif channel == "account":
                # 账户更新
                for callback in self.callbacks.get("balance", []):
                    try:
                        callback(msg_data)
                    except Exception as e:
                        print(f"[OKXWS] Balance callback error: {e}")

        except json.JSONDecodeError as e:
            print(f"[OKXWS] JSON 解析错误: {e}")
        except Exception as e:
            print(f"[OKXWS] 消息处理错误: {e}")

    async def _consume_public(self, ws: websockets.WebSocketClientProtocol):
        """
        消费公共频道消息

        Args:
            ws: WebSocket 连接
        """
        try:
            async for message in ws:
                if not self._running:
                    break
                self._handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            print(f"[OKXWS] 公共频道连接已关闭")
        except Exception as e:
            print(f"[OKXWS] 公共频道消息消费错误: {e}")

    async def _consume_private(self, ws: websockets.WebSocketClientProtocol):
        """
        消费私有频道消息

        Args:
            ws: WebSocket 连接
        """
        try:
            async for message in ws:
                if not self._running:
                    break
                self._handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            print(f"[OKXWS] 私有频道连接已关闭")
        except Exception as e:
            print(f"[OKXWS] 私有频道消息消费错误: {e}")

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
                print(f"[OKXWS] 启动公共频道 WebSocket: {public_url}")

                # 使用 SSL 上下文连接
                async with websockets.connect(public_url, ssl=self._ssl_context) as ws:
                    self._ws_public = ws

                    # 订阅
                    sub_msg = {"op": "subscribe", "args": public_channels}
                    await ws.send(json.dumps(sub_msg))
                    print(f"[OKXWS] 公共频道订阅请求已发送: {[c['channel'] for c in public_channels]}")

                    # 消费消息
                    await self._consume_public(ws)

            # 注意：私有频道需要单独的连接
            # 由于使用了 async with，私有频道的实现需要在实际使用时单独处理

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

        # async with 会自动关闭连接
        self._ws_public = None
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
                    print(f"[OKXWS] Ticker callback error: {e}")

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
                    print(f"[OKXWS] Orderbook callback error: {e}")

            # 模拟 K线
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

            if len(self.last_candles["5m"]) > 100:
                self.last_candles["5m"].pop(0)

            for callback in self.callbacks.get("candle", []):
                try:
                    callback("5m", [candle])
                except Exception as e:
                    print(f"[OKXWS] Candle callback error: {e}")

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
