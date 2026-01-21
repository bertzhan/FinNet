#!/bin/bash
# 手动测试 API 的脚本

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-test-key}"

echo "=========================================="
echo "FinNet OpenAI API 测试"
echo "=========================================="
echo "API URL: $API_BASE_URL"
echo ""

# 测试1: 健康检查
echo "1. 测试健康检查端点..."
curl -s "$API_BASE_URL/health" | jq '.' || echo "健康检查失败"
echo ""

# 测试2: 非流式响应
echo "2. 测试非流式 Chat Completion..."
curl -X POST "$API_BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "model": "finnet-rag",
    "messages": [
      {"role": "user", "content": "平安银行2023年第三季度的营业收入是多少？"}
    ],
    "temperature": 0.7,
    "max_tokens": 500,
    "stream": false
  }' | jq '.' || echo "非流式请求失败"
echo ""

# 测试3: 流式响应
echo "3. 测试流式 Chat Completion..."
curl -X POST "$API_BASE_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "model": "finnet-rag",
    "messages": [
      {"role": "user", "content": "什么是人工智能？"}
    ],
    "temperature": 0.7,
    "max_tokens": 300,
    "stream": true
  }' || echo "流式请求失败"
echo ""

echo "=========================================="
echo "测试完成"
echo "=========================================="
