# WebSocket 连接修复说明

## 问题描述

之前 `okx_ws.py` 无法连接到 OKX WebSocket，原因是：

1. **错误的端口号**：使用了 `8443` 而不是 `443`
2. **缺少 SSL 上下文**：没有正确配置 SSL 证书
3. **连接方式不正确**：没有使用 `async with` 上下文管理器

## 解决方案

参考成功的 OKX WebSocket 连接代码，重写了 `okx_ws.py`。

### 关键修改

#### 1. SSL 上下文配置

```python
import ssl
import certifi

# 创建 SSL 上下文，使用 Mozilla CA 证书
self._ssl_context = ssl.create_default_context(cafile=certifi.where())
```

**为什么需要 certifi？**
- OKX 使用 WSS（WebSocket Secure）协议
- 需要 SSL/TLS 证书验证
- certifi 提供 Mozilla 的 CA 证书包

#### 2. 正确的 WebSocket URL

```python
# ❌ 错误（之前）
WS_URL_PUBLIC = "wss://ws.okx.com:8443/ws/v5/public"

# ✅ 正确（现在）
WS_URL_PUBLIC = "wss://ws.okx.com:443/ws/v5/public"
```

**关键变化**：端口号从 `8443` 改为 `443`

#### 3. 使用 async with 上下文管理器

```python
# ✅ 正确的连接方式
async with websockets.connect(public_url, ssl=self._ssl_context) as ws:
    # 订阅
    sub_msg = {"op": "subscribe", "args": public_channels}
    await ws.send(json.dumps(sub_msg))

    # 消费消息
    async for message in ws:
        self._handle_message(message)
```

**优势**：
- 自动管理连接生命周期
- 自动处理连接关闭
- 代码更简洁

#### 4. 订阅方式

```python
sub_msg = {"op": "subscribe", "args": public_channels}
await ws.send(json.dumps(sub_msg))
```

**参数格式**：
```python
{
    "op": "subscribe",
    "args": [
        {"channel": "tickers", "instId": "ETH-USDT-SWAP"},
        {"channel": "candle5m", "instId": "ETH-USDT-SWAP"}
    ]
}
```

## 依赖更新

添加了 `certifi` 依赖：

```txt
certifi>=2023.0.0
```

## 测试方法

### 方法 1：测试模拟模式（推荐）

```bash
python test_real_ws.py
# 输入: n (跳过真实连接测试)
```

### 方法 2：测试真实连接

```bash
python test_real_ws.py
# 输入: y (测试真实连接)
```

### 方法 3：代码测试

```python
import asyncio
from exchange.okx_ws import OKXWS

async def test():
    ws = OKXWS("ETH-USDT-SWAP", simulate=True)
    ws.on_ticker(lambda t: print(f"价格: {t['last']}"))
    await asyncio.wait_for(ws.start(), timeout=5)

asyncio.run(test())
```

## 连接端点

### 实盘
```python
公共频道: wss://ws.okx.com:443/ws/v5/public
私有频道: wss://ws.okx.com:443/ws/v5/private
```

### 模拟盘
```python
公共频道: wss://wspap.okx.com:443/ws/v5/public?brokerId=9999
私有频道: wss://wspap.okx.com:443/ws/v5/private?brokerId=9999
```

## 常见问题

### Q1: 还是连不上怎么办？

A: 检查：
1. 网络连接是否正常
2. 是否需要代理（国内用户）
3. 防火墙是否阻止连接

### Q2: SSL 证书错误怎么办？

A: 确保安装了 certifi：
```bash
pip install certifi
```

### Q3: 如何使用代理？

A: websockets 库对代理支持有限，建议：
1. 使用系统代理
2. 设置环境变量：
   ```bash
   export HTTP_PROXY=http://127.0.0.1:7890
   export HTTPS_PROXY=http://127.0.0.1:7890
   ```

## 成功案例对比

| 特性 | 之前的实现 | 现在的实现（基于成功案例） |
|------|----------|----------------------|
| 端口 | 8443 ❌ | 443 ✅ |
| SSL 上下文 | 无 ❌ | certifi ✅ |
| 连接方式 | 普通连接 ❌ | async with ✅ |
| 订阅方式 | 复杂 ❌ | 简洁 ✅ |
| 稳定性 | 低 ❌ | 高 ✅ |

## 验证连接

运行测试脚本：
```bash
python test_real_ws.py
```

预期输出：
```
✅ 模拟模式测试成功
✅ 收到 Ticker 数据
✅ 收到订单簿数据
```

## 参考资料

- [OKX WebSocket API 文档](https://www.okx.com/docs-v5/en/#websocket-api)
- [websockets 库文档](https://websockets.readthedocs.io/)
- [certifi 文档](https://certifi.io/)

## 更新日志

- 2025-02-05: 基于成功案例重写 WebSocket 连接
- 修复端口号问题（8443 → 443）
- 添加 SSL 上下文和 certifi
- 使用 async with 上下文管理器
