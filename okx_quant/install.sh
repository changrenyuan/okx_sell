#!/bin/bash

echo "========================================="
echo "OKX ETH 量化交易机器人 - 安装脚本"
echo "========================================="
echo ""

# 检查 Python 版本
echo "检查 Python 版本..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python 版本: $python_version"

# 安装依赖
echo ""
echo "安装依赖包..."
pip3 install -r requirements.txt

# 检查配置文件
echo ""
echo "检查配置文件..."
if [ ! -f "config/params.yaml" ]; then
    echo "错误: 配置文件 config/params.yaml 不存在"
    exit 1
fi

# 提示用户配置 API
echo ""
echo "========================================="
echo "安装完成！"
echo "========================================="
echo ""
echo "下一步："
echo "1. 编辑 config/params.yaml，填入你的 OKX API 信息"
echo "2. 运行程序: python3 main.py"
echo ""
echo "⚠️ 重要提示："
echo "- API 只需要开启交易权限，不要开启提现权限"
echo "- 建议先使用模拟盘测试（flag: \"1\"）"
echo ""
