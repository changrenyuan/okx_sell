"""
OKX REST API 封装
提供账户、交易、市场数据等功能的统一接口
"""
from okx import Trade, Account, Market
from typing import Dict, Any, Optional
from datetime import datetime


class OKXRest:
    """OKX REST API 客户端"""

    def __init__(self, api_key: str, api_secret: str, passphrase: str, flag: str):
        """
        初始化 OKX REST 客户端

        Args:
            api_key: API Key
            api_secret: API Secret
            passphrase: API Passphrase
            flag: 0=实盘，1=模拟盘
        """
        self.flag = flag
        self.trade = Trade.TradeAPI(api_key, api_secret, passphrase, flag=flag)
        self.account = Account.AccountAPI(api_key, api_secret, passphrase, flag=flag)
        self.market = Market.MarketAPI(api_key, api_secret, passphrase, flag=flag)

    def get_equity(self, ccy: str = "USDT") -> float:
        """
        获取账户余额

        Args:
            ccy: 币种，默认 USDT

        Returns:
            账户余额
        """
        try:
            res = self.account.get_account_balance()
            if res.get("code") == "0" and res.get("data"):
                details = res["data"][0].get("details", [])
                for d in details:
                    if d.get("ccy") == ccy:
                        return float(d.get("eq", 0.0))
            return 0.0
        except Exception as e:
            raise Exception(f"获取账户余额失败: {str(e)}")

    def get_position(self, symbol: str) -> Dict[str, Any]:
        """
        获取当前持仓

        Args:
            symbol: 交易对

        Returns:
            持仓信息字典
        """
        try:
            res = self.account.get_position(instId=symbol)
            if res.get("code") == "0" and res.get("data"):
                positions = res["data"]
                if positions:
                    pos = positions[0]
                    return {
                        "size": float(pos.get("pos", 0)),
                        "avg_price": float(pos.get("avgPx", 0)),
                        "unrealized_pnl": float(pos.get("upl", 0)),
                        "side": pos.get("posSide", "net")
                    }
            return {"size": 0, "avg_price": 0, "unrealized_pnl": 0, "side": "net"}
        except Exception as e:
            raise Exception(f"获取持仓失败: {str(e)}")

    def set_leverage(self, symbol: str, leverage: int, margin_mode: str = "isolated"):
        """
        设置杠杆

        Args:
            symbol: 交易对
            leverage: 杠杆倍数
            margin_mode: 保证金模式
        """
        try:
            res = self.account.set_leverage(
                instId=symbol,
                lever=str(leverage),
                mgnMode=margin_mode
            )
            if res.get("code") != "0":
                raise Exception(f"设置杠杆失败: {res.get('msg', 'Unknown error')}")
        except Exception as e:
            raise Exception(f"设置杠杆异常: {str(e)}")

    def place_order(
        self,
        symbol: str,
        side: str,
        size: float,
        order_type: str = "market",
        price: Optional[float] = None,
        reduce_only: bool = False
    ) -> Dict[str, Any]:
        """
        下单

        Args:
            symbol: 交易对
            side: 方向 (buy/sell)
            size: 数量
            order_type: 订单类型 (market/limit)
            price: 限价单价格（限价单必填）
            reduce_only: 是否只减仓

        Returns:
            订单信息
        """
        try:
            # 构建下单参数
            params = {
                "instId": symbol,
                "tdMode": "isolated",
                "side": side,
                "ordType": order_type,
                "sz": str(size),
                "reduceOnly": reduce_only
            }

            # 限价单需要价格
            if order_type == "limit" and price is not None:
                params["px"] = str(price)

            # 下单
            res = self.trade.place_order(**params)

            if res.get("code") != "0":
                raise Exception(f"下单失败: {res.get('msg', 'Unknown error')}")

            order_data = res.get("data", [{}])[0]
            return {
                "order_id": order_data.get("ordId"),
                "symbol": symbol,
                "side": side,
                "size": size,
                "type": order_type,
                "price": price,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            raise Exception(f"下单异常: {str(e)}")

    def cancel_order(self, symbol: str, order_id: str):
        """
        撤单

        Args:
            symbol: 交易对
            order_id: 订单ID
        """
        try:
            res = self.trade.cancel_order(instId=symbol, ordId=order_id)
            if res.get("code") != "0":
                raise Exception(f"撤单失败: {res.get('msg', 'Unknown error')}")
        except Exception as e:
            raise Exception(f"撤单异常: {str(e)}")

    def get_funding_rate(self, symbol: str) -> Optional[float]:
        """
        获取资金费率

        Args:
            symbol: 交易对

        Returns:
            资金费率，失败返回 None
        """
        try:
            res = self.account.get_funding_rate(instId=symbol)
            if res.get("code") == "0" and res.get("data"):
                funding_rate = res["data"][0].get("fundingRate")
                if funding_rate:
                    return float(funding_rate)
            return None
        except Exception as e:
            raise Exception(f"获取资金费率失败: {str(e)}")

    def get_order_book(self, symbol: str, depth: int = 5) -> Dict[str, Any]:
        """
        获取订单簿深度

        Args:
            symbol: 交易对
            depth: 深度

        Returns:
            订单簿数据
        """
        try:
            res = self.market.books(instId=symbol, sz=str(depth))
            if res.get("code") == "0" and res.get("data"):
                book_data = res["data"][0]
                asks = [[float(bid[0]), float(bid[1])] for bid in book_data.get("asks", [])]
                bids = [[float(ask[0]), float(ask[1])] for ask in book_data.get("bids", [])]
                return {"asks": asks, "bids": bids}
            return {"asks": [], "bids": []}
        except Exception as e:
            raise Exception(f"获取订单簿失败: {str(e)}")

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        获取ticker信息

        Args:
            symbol: 交易对

        Returns:
            ticker数据
        """
        try:
            res = self.market.ticker(instId=symbol)
            if res.get("code") == "0" and res.get("data"):
                ticker_data = res["data"][0]
                return {
                    "last_price": float(ticker_data.get("last", 0)),
                    "volume_24h": float(ticker_data.get("volCcy24h", 0)),
                    "change_24h": float(ticker_data.get("chg", 0)),
                    "high_24h": float(ticker_data.get("high24h", 0)),
                    "low_24h": float(ticker_data.get("low24h", 0))
                }
            return {}
        except Exception as e:
            raise Exception(f"获取ticker失败: {str(e)}")

    def get_daily_change(self, symbol: str) -> float:
        """
        获取24小时涨跌幅

        Args:
            symbol: 交易对

        Returns:
            24小时涨跌幅
        """
        try:
            ticker = self.get_ticker(symbol)
            return ticker.get("change_24h", 0.0)
        except Exception as e:
            raise Exception(f"获取24小时涨跌幅失败: {str(e)}")

    def close_position(self, symbol: str, side: str, size: Optional[float] = None) -> Dict[str, Any]:
        """
        平仓

        Args:
            symbol: 交易对
            side: 平仓方向 (buy=平空, sell=平多)
            size: 平仓数量，None表示全部平仓

        Returns:
            订单信息
        """
        if size is None:
            # 获取当前持仓
            position = self.get_position(symbol)
            size = position.get("size", 0)
            if size <= 0:
                raise Exception("当前无持仓，无法平仓")

        return self.place_order(
            symbol=symbol,
            side=side,
            size=size,
            reduce_only=True
        )
