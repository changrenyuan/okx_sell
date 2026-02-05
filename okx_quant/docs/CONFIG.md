# 配置文件管理说明

## 配置文件说明

项目中有两个配置文件：

- **config/params.yaml** - 实际配置文件（本地使用，包含 API 密钥等敏感信息）
- **config/params.yaml.example** - 配置文件模板（Git 追踪，供参考）

## 重要说明

### ✅ 已解决的问题

`config/params.yaml` 已从 Git 追踪中移除，**不会再被后续更新覆盖**。

### 📝 如何使用

#### 初次使用（没有配置文件）

```bash
# 复制模板文件
cp config/params.yaml.example config/params.yaml

# 编辑配置文件
nano config/params.yaml
```

#### 更新代码后

```bash
# 拉取最新代码
git pull origin main

# 你的 config/params.yaml 不会被覆盖 ✅
```

#### 添加新的配置项

如果 `config/params.yaml.example` 中添加了新配置项：

```bash
# 备份你的配置
cp config/params.yaml config/params.yaml.backup

# 合并新配置（手动）
diff config/params.yaml config/params.yaml.example

# 或者直接从模板重新创建（需要重新填入 API 密钥）
cp config/params.yaml.example config/params.yaml
# 然后重新填入你的 API 密钥
```

## .gitignore 规则

`.gitignore` 中已配置忽略以下文件：

```gitignore
# Sensitive data
config.yaml
config/params.yaml
*.pem
*.key
```

## Git 追踪状态

```bash
# 查看被追踪的文件
git ls-files | grep params

# 输出应该是：
# config/params.yaml.example  ✅ （模板文件）
```

## 常见问题

### Q: 为什么 params.yaml 不在 Git 中？

A: 因为它包含 API 密钥等敏感信息，不应该提交到公开仓库。

### Q: 如何同步配置文件的更新？

A: 手动对比 `config/params.yaml.example` 和你的 `config/params.yaml`，添加缺失的配置项。

### Q: 团队协作时如何共享配置？

A: 推荐做法：
1. 每个成员有自己的 `config/params.yaml`
2. 使用环境变量传递 API 密钥
3. 或者在私有配置管理工具中管理密钥

## 安全建议

1. **不要将 `config/params.yaml` 提交到 Git**
2. **定期更换 API 密钥**
3. **使用最小权限原则（只授权必要的权限）**
4. **建议使用模拟盘测试（flag: "1"）**
