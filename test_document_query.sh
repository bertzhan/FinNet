#!/bin/bash
# 文档查询接口测试脚本

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"

echo "=========================================="
echo "FinNet 文档查询 API 测试"
echo "=========================================="
echo "API URL: $API_BASE_URL"
echo ""

# 测试1: 健康检查
echo "1. 测试健康检查端点..."
curl -s "$API_BASE_URL/health" | jq '.' || echo "健康检查失败"
echo ""

# 测试2: 查询文档ID（季度报告）
echo "2. 测试查询文档ID（季度报告）..."
curl -X POST "$API_BASE_URL/api/v1/document/query" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "000001",
    "year": 2024,
    "quarter": 3,
    "doc_type": "quarterly_reports"
  }' | jq '.' || echo "查询失败"
echo ""

# 测试3: 查询文档ID（年度报告）
echo "3. 测试查询文档ID（年度报告）..."
curl -X POST "$API_BASE_URL/api/v1/document/query" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "000001",
    "year": 2024,
    "doc_type": "annual_reports"
  }' | jq '.' || echo "查询失败"
echo ""

# 测试4: 查询文档ID（不存在的文档）
echo "4. 测试查询不存在的文档..."
curl -X POST "$API_BASE_URL/api/v1/document/query" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "999999",
    "year": 2020,
    "quarter": 1,
    "doc_type": "quarterly_reports"
  }' | jq '.' || echo "查询失败"
echo ""

echo "=========================================="
echo "测试完成"
echo "=========================================="
