# OKX ETH 量化交易机器人

基于 Python 的 OKX ETH-USDT-SWAP 量化交易机器人，采用双策略系统（过热回落做空 + 趋势做多），配合完善的风控体系。

## 项目特点

- **双策略系统**：过热回落做空策略 + 趋势做多策略
- **完善风控**：单笔风险控制、日回撤限制、交易次数限制、资金费率限制
- **实时行情**：基于 WebSocket 的实时行情订阅
- **结构化日志**：完整的交易记录，便于复盘
- ** fail-safe 设计**：任何异常都能安全处理

## 系统要求

- Python ≥ 3.10
- pip install python-okx pyyaml loguru numpy

## 项目结构

```
okx_quant/
├── config/
│   └── params.yaml          # 配置文件
├── exchange/
│   ├── okx_rest.py          # OKX REST API 封装
│   └── okx_ws.py            # WebSocket 行情模块
├── market/
│   ├── state_detector.py    # 市场状态识别
│   └── indicators.py        # 技术指标计算
├── strategy/
│   ├── overheat_short.py    # 过热回落做空策略
│   └── trend_long.py        # 趋势做多策略
├── risk/
│   └── risk_manager.py      # 风控管理器
├── engine/
│   ├── signal_engine.py     # 信号引擎
│   └── trade_engine.py      # 交易引擎
├── utils/
│   └── logger.py            # 日志模块
├── main.py                  # 主程序
└── README.md                # 本文件
```

## 快速开始

### 1. 安装依赖

```bash
pip install python-okx pyyaml loguru numpy
```

### 2. 配置 API

编辑 `config/params.yaml`，填入你的 OKX API 信息：

```yaml
api:
  key: "YOUR_API_KEY"
  secret: "YOUR_API_SECRET"
  passphrase: "YOUR_API_PASSPHRASE"
  flag: "0"  # 0=实盘，1=模拟盘
```

**⚠️ 重要提示**：
- API 只需要开启交易权限，**不要开启提现权限**
- 建议先使用模拟盘测试（flag: "1"）

### 3. 运行程序

```bash
cd okx_quant
python main.py
```

### 4. 停止程序

按 `Ctrl + C` 安全停止程序

## 策略说明

### 策略 A：过热回落做空

#### 市场状态判定（需全部满足）
1. 当日涨幅 ≥ 4%
2. 当前价格 > VWAP + 2.0%
3. 5分钟成交量出现峰值后连续下降
4. 资金费率 ≥ +0.02%

#### 入场触发（满足 2 条即可）
- 5分钟 K 线收盘价跌破 VWAP
- 5分钟/15分钟 MA 死叉
- 买盘深度（前5档）减少 ≥ 20%

#### 风控参数
- **止损**：最近高点 + 0.25%
- **止盈**：1R 平 50%，1.5R 全平
- **最长持仓**：20~30 分钟
- **资金费率限制**：< -0.03% 时不做空

### 策略 B：趋势做多

#### 市场状态判定（需全部满足）
1. MA(5) > MA(15) > MA(60)
2. 15分钟成交量连续 3 根温和放大
3. 5分钟 ATR < 过去 24h ATR 均值
4. 资金费率 ∈ [-0.01%, +0.02%]

#### 入场触发
- 回踩 VWAP 或 MA(15)
- 回踩期间成交量萎缩
- 再次出现放量阳线

#### 风控参数
- **止损**：回踩低点 - 0.2%
- **止盈**：0.8R 平 30%，1.5R 平 50%，剩余移动止损
- **最长持仓**：≤ 2 小时
- **资金费率限制**：> +0.03% 时不做多

## 风控体系

### 单笔风险控制
- 最大单笔风险：0.5% 账户权益
- 每次交易风险：0.3% 账户权益

### 日回撤控制
- 最大日回撤：2%

### 交易次数限制
- 每日最大交易次数：6 次

### 资金费率限制
- 资金费率 > +0.03%：禁止做多
- 资金费率 < -0.03%：禁止做空

## 配置参数说明

### 交易参数
```yaml
trade:
  symbol: "ETH-USDT-SWAP"   # 交易对
  leverage: 2                # 杠杆倍数
  margin_mode: "isolated"    # 保证金模式
  order_mode: "net"          # 订单模式
```

### 风控参数
```yaml
risk:
  max_position_risk: 0.005   # 单笔最大亏损 0.5%
  max_daily_drawdown: 0.02   # 最大日回撤 2%
  max_trades_per_day: 6      # 每日最大交易次数
```

### 策略参数
```yaml
strategy_overheat_short:
  enabled: true              # 是否启用
  min_daily_gain: 0.04       # 最小当日涨幅 4%
  min_funding_rate: 0.0002   # 最小资金费率 +0.02%
```

## 日志说明

### 日志文件
- `trade.log`：主日志文件
- 日志文件大小超过 10MB 自动轮转
- 保留 30 天

### 日志格式
- `[TRADE]`：交易记录（结构化 JSON）
- `[SIGNAL]`：信号记录
- `[RISK]`：风控检查记录
- `[MARKET_STATE]`：市场状态记录
- `[ORDER]`：订单记录
- `[EXCEPTION]`：异常记录

### 复盘
每笔交易都会记录为结构化 JSON，便于复盘：

```json
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
```

## 注意事项

1. **API 权限**：只开启交易权限，不要开启提现权限
2. **模拟盘测试**：建议先在模拟盘充分测试
3. **资金管理**：严格控制仓位，不要投入全部资金
4. **风险控制**：严格遵守风控参数，不要随意修改
5. **监控运行**：建议定期检查日志，确保程序正常运行
6. **止损保护**：程序有止损保护，但网络异常时可能失效

## 故障排查

### WebSocket 连接失败
- 检查网络连接
- 检查 API 配置是否正确

### 下单失败
- 检查账户余额是否充足
- 检查杠杆设置是否正确
- 检查风控是否限制

### 策略未触发
- 检查市场状态是否满足条件
- 检查策略是否启用
- 检查日志中的详细信息

## 免责声明

本项目仅供学习和研究使用，不构成任何投资建议。量化交易存在风险，可能导致资金损失。使用者需自行承担所有风险和后果。作者不对任何损失负责。

## 许可证

MIT License
