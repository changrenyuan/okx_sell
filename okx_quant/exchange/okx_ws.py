"""
OKX WebSocket 行情模块
提供实时行情数据订阅功能
"""
import asyncio
from okx import MarketData
from typing import Dict, Any, Optional, Callable, List
import json


class OKXWS:
    """OKX WebSocket 行情客户端"""

    def __init__(self, symbol: str, flag: str = "0"):
        """
        初始化 WebSocket 客户端

        Args:
            symbol: 交易对
            flag: 0=实盘，1=模拟盘
        """
        self.symbol = symbol
        self.flag = flag
        self.last_price: Optional[float] = None
        self.last_ticker: Optional[Dict[str, Any]] = None
        self.last_candles: Dict[str, List[Dict]] = {}
        self.last_orderbook: Optional[Dict[str, Any]] = None
        self.callbacks: Dict[str, List[Callable]] = {}
        self._ws: Optional[MarketData.MarketDataAPI] = None
        self._running = False

    def on_ticker(self, callback: Callable):
        """注册 ticker 回调"""
        if "ticker" not in self.callbacks:
            self.callbacks["ticker"] = []
        self.callbacks["ticker"].append(callback)

    def on_candle(self, callback: Callable):
        """注册 K线回调"""
        if "candle" not in self.callbacks:
            self.callbacks["candle"] = []
        self.callbacks["candle"].append(callback)

    def on_orderbook(self, callback: Callable):
        """注册订单簿回调"""
        if "orderbook" not in self.callbacks:
            self.callbacks["orderbook"] = []
        self.callbacks["orderbook"].append(callback)

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
                callback(self.last_ticker)
            except Exception as e:
                print(f"Ticker callback error: {e}")

    def _handle_candle(self, data: List[Dict], timeframe: str):
        """处理 K线数据"""
        if not data:
            return

        # 解析 K线数据
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
                callback(timeframe, candles)
            except Exception as e:
                print(f"Candle callback error: {e}")

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
                callback(self.last_orderbook)
            except Exception as e:
                print(f"Orderbook callback error: {e}")

    async def start(self, subscriptions: Optional[List[Dict]] = None):
        """
        启动 WebSocket 连接

        Args:
            subscriptions: 订阅列表，None 则使用默认订阅
        """
        if self._running:
            return

        # 默认订阅
        if subscriptions is None:
            subscriptions = [
                {"channel": "tickers", "instId": self.symbol},
                {"channel": "candle5m", "instId": self.symbol},
                {"channel": "candle15m", "instId": self.symbol},
                {"channel": "books", "instId": self.symbol}
            ]

        self._ws = MarketData.MarketDataAPI(flag=self.flag)
        self._running = True

        try:
            async for msg in self._ws.subscribe(subscriptions):
                if not self._running:
                    break

                if "data" in msg and msg["data"]:
                    channel = msg.get("arg", {}).get("channel", "")

                    if channel == "tickers":
                        self._handle_ticker(msg["data"])
                    elif channel.startswith("candle"):
                        timeframe = channel.replace("candle", "")
                        self._handle_candle(msg["data"], timeframe)
                    elif channel == "books":
                        self._handle_orderbook(msg["data"])

        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            self._running = False

    def stop(self):
        """停止 WebSocket 连接"""
        self._running = False
        if self._ws:
            try:
                # 关闭连接
                pass
            except Exception as e:
                print(f"Stop WebSocket error: {e}")

    def get_price(self) -> Optional[float]:
        """获取最新价格"""
        return self.last_price

    def get_ticker(self) -> Optional[Dict[str, Any]]:
        """获取最新 ticker"""
        return self.last_ticker

    def get_candles(self, timeframe: str = "5m") -> List[Dict]:
        """获取 K线数据"""
        return self.last_candles.get(timeframe, [])

    def get_orderbook(self) -> Optional[Dict[str, Any]]:
        """获取订单簿"""
        return self.last_orderbook

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running


class PriceCache:
    """价格缓存，用于存储历史价格"""

    def __init__(self, max_size: int = 1000):
        """
        初始化价格缓存

        Args:
            max_size: 最大缓存数量
        """
        self.prices: List[float] = []
        self.max_size = max_size
        self.timestamps: List[str] = []

    def add(self, price: float, timestamp: Optional[str] = None):
        """
        添加价格

        Args:
            price: 价格
            timestamp: 时间戳
        """
        self.prices.append(price)
        if timestamp:
            self.timestamps.append(timestamp)
        else:
            from datetime import datetime
            self.timestamps.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # 保持最大缓存数量
        if len(self.prices) > self.max_size:
            self.prices.pop(0)
            self.timestamps.pop(0)

    def get_last_n(self, n: int) -> List[float]:
        """获取最近 n 个价格"""
        return self.prices[-n:] if n <= len(self.prices) else self.prices

    def get_all(self) -> List[float]:
        """获取所有价格"""
        return self.prices

    def size(self) -> int:
        """获取缓存大小"""
        return len(self.prices)

    def clear(self):
        """清空缓存"""
        self.prices = []
        self.timestamps = []
