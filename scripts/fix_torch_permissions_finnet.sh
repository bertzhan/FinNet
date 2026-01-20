#!/bin/bash
# -*- coding: utf-8 -*-
"""
修复 finnet 环境中 torch 权限问题
"""

set -e

TORCH_PATH="/Users/han/Anaconda3/anaconda3/envs/finnet/lib/python3.10/site-packages/torch"

echo "=========================================="
echo "修复 finnet 环境中 torch 权限问题"
echo "=========================================="
echo ""

# 检查文件是否存在
if [ ! -d "$TORCH_PATH" ]; then
    echo "⚠️  torch 目录不存在: $TORCH_PATH"
    echo "   请检查路径是否正确"
    exit 1
fi

echo "1. 检查当前权限..."
ls -la "$TORCH_PATH/_environment.py" 2>/dev/null || echo "   文件不存在或无法访问"
echo ""

echo "2. 修复权限..."
chmod -R u+r "$TORCH_PATH"/* 2>/dev/null && echo "✅ 权限修复成功" || {
    echo "⚠️  权限修复失败，尝试使用 sudo..."
    sudo chmod -R u+r "$TORCH_PATH"/* 2>/dev/null && echo "✅ 权限修复成功（使用 sudo）" || echo "❌ 权限修复失败"
}
echo ""

echo "3. 验证修复..."
if [ -r "$TORCH_PATH/_environment.py" ]; then
    echo "✅ 文件可读"
    echo ""
    echo "可以运行测试："
    echo "  conda activate finnet"
    echo "  python examples/test_embedder_quick.py"
else
    echo "❌ 文件仍不可读"
    echo ""
    echo "请手动修复权限："
    echo "  chmod -R u+r $TORCH_PATH"
    echo "  或"
    echo "  sudo chmod -R u+r $TORCH_PATH"
fi

echo ""
echo "=========================================="
echo "完成"
echo "=========================================="
