okx API系统
实现方式：python，python-okx库
架构：
okx_quant/
├── config/
│   └── params.yaml
├── exchange/
│   ├── okx_rest.py
│   └── okx_ws.py
├── market/
│   ├── state_detector.py
│   └── indicators.py
├── strategy/
│   ├── overheat_short.py
│   └── trend_long.py
├── risk/
│   └── risk_manager.py
├── engine/
│   ├── signal_engine.py
│   └── trade_engine.py
└── utils/
    └── logger.py
└── main.py
WS 行情更新
 → 状态识别
   → 策略判断
     → 风控检查
       → 下单

资金费率 > +0.03% ：不做多
资金费率 < -0.03% ：不做空

约束：
不允许策略里直接写 API

风控模块优先级 > 策略

任何异常必须 fail-safe（不交易）

日志必须可复盘
策略 A（ETH 专用）：过热回落做空
🎯 ETH 的“过热”定义（比 BTC 更严格）
市场状态判定（全部满足）
1. 当日涨幅 ≥ 3.5%
2. 当前价格 > VWAP + 2.0%
3. 5min 成交量出现“峰值 → 连续下降”
4. 资金费率 ≥ +0.02%


👉 满足 → MarketState = OVERHEATED

⏱ 入场触发（等市场先示弱）
- 5min K 线收盘价跌破 VWAP
- 或 5min / 15min MA 死叉
- 同时买盘深度（前5档）减少 ≥ 20%


满足其中 2 条 → SHORT

🛑 风控（必须写死）
止损：
  最近高点 + 0.25%

止盈：
  1R 先平 50%
  1.5R 全平

最长持仓：
  20 ~ 30 分钟


📌 只吃第一段回落
📌 不隔夜

四、策略 B（ETH 专用）：温和趋势做多
🎯 ETH 趋势启动的真实特征
市场状态判定
1. MA(5) > MA(15) > MA(60)
2. 15min 成交量连续 3 根温和放大
3. 5min ATR < 过去 24h ATR 均值
4. 资金费率 ∈ [-0.01%, +0.02%]


👉 满足 → MarketState = TRENDING

⏱ 入场触发（不是追涨）
- 回踩 VWAP 或 MA(15)
- 回踩期间成交量萎缩
- 再次出现放量阳线


→ LONG

🛑 风控
止损：
  回踩低点 - 0.2%

止盈：
  0.8R 平 30%
  1.5R 平 50%
  剩余移动止损

最长持仓：
  ≤ 2 小时

建议的基础参数
合约	BTC / ETH 永续
杠杆	2x – 7x（最多）
仓位模式	逐仓
下单类型	限价为主
单笔风险	≤ 0.5% 账户

symbol: ETH-USDT-SWAP
leverage: 2       # 实盘第一阶段只用 2x
margin_mode: isolated
order_mode: net
timeframe_main: 5m
timeframe_confirm: 15m
max_position_risk: 0.5%   # 单笔最大亏损
max_daily_drawdown: 2%
max_trades_per_day: 6 # 防止系统过度交易

risk_amount = equity * 0.003  # 0.3%
stop_distance = abs(entry_price - stop_price)
position_size = risk_amount / stop_distance

过热回落（只保留“最稳条件”）

只允许在 以下全部成立 才交易：

- 当日涨幅 ≥ 4%
- 价格跌破 VWAP（5min 收盘）
- 资金费率 ≥ +0.02%
趋势做多（极简版）
- MA(5) > MA(15)
- 回踩不破 MA(15)
- 成交量回踩时下降

下单流程（防止“下了就死”）
正确顺序（必须）

计算仓位

下限价单入场

确认成交

立刻挂止损

再挂止盈
日志 & 复盘
每一笔都要记录：
{
  "time": "2026-02-05 14:35",
  "strategy": "overheat_short",
  "entry": 2345.6,
  "stop": 2351.4,
  "size": 0.12,
  "exit": 2338.2,
  "pnl": +0.42,
  "reason": "VWAP break + volume drop"
}
