#!/bin/bash
# -*- coding: utf-8 -*-
"""
安装 Embedding 模型依赖脚本
"""

set -e

echo "=========================================="
echo "安装 Embedding 模型依赖"
echo "=========================================="
echo ""

# 检查 Python
echo "1. 检查 Python 环境..."
python --version
echo ""

# 检查 pip
echo "2. 检查 pip..."
pip --version
echo ""

# 安装依赖
echo "3. 安装依赖包..."
echo "   安装 sentence-transformers（包含 torch 等依赖）..."
pip install sentence-transformers --no-cache-dir

echo ""
echo "4. 验证安装..."
python -c "import torch; print(f'✅ PyTorch: {torch.__version__}')" || echo "❌ PyTorch 未安装"
python -c "import transformers; print(f'✅ Transformers: {transformers.__version__}')" || echo "❌ Transformers 未安装"
python -c "import sentence_transformers; print(f'✅ Sentence-Transformers: {sentence_transformers.__version__}')" || echo "❌ Sentence-Transformers 未安装"

echo ""
echo "=========================================="
echo "安装完成！"
echo "=========================================="
echo ""
echo "下一步："
echo "1. 运行测试: python examples/test_vectorize_simple.py"
echo "2. 首次运行会自动下载模型（需要网络）"
echo "3. 模型会下载到: ~/.cache/huggingface/hub/"
echo ""
