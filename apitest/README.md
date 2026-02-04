# FinNet API 测试套件

## 概述

这是 FinNet API 的全面测试套件，用于测试所有 API 接口。测试覆盖三家公司（平安银行、万科A、神州高铁）2024年四个季度的数据。

## 测试范围

### 测试公司
- 平安银行（000001）
- 万科A（000002）
- 神州高铁（000008）

### 测试周期
2024年完整四个报告周期：
- **Q1（一季报）** - quarterly_reports
- **Q2（半年报）** - interim_reports
- **Q3（三季报）** - quarterly_reports
- **年报** - annual_reports

### 测试接口（共11个）

#### 1. 基础接口（2个）
- `GET /` - 根路径
- `GET /health` - 全局健康检查

#### 2. Document API（4个）
- `POST /api/v1/document/query` - 查询document_id
- `GET /api/v1/document/{document_id}/chunks` - 获取文档chunks
- `POST /api/v1/document/company-code-search` - 公司名称搜索
- `POST /api/v1/document/chunk-by-id` - 根据chunk_id查询

#### 3. Retrieval API（5个）
- `POST /api/v1/retrieval/vector` - 向量检索
- `POST /api/v1/retrieval/fulltext` - 全文检索
- `POST /api/v1/retrieval/graph/children` - 图检索子节点
- `POST /api/v1/retrieval/hybrid` - 混合检索
- `GET /api/v1/retrieval/health` - 检索服务健康检查

## 文件结构

```
apitest/
├── README.md                       # 本文件
├── run_tests.sh                    # Bash运行脚本（推荐）
├── run_all_tests.py               # Python主测试脚本
│
├── test_basic_endpoints.py         # 基础接口测试
│
├── test_document_query.py          # 文档查询接口测试
├── test_document_chunks.py         # 文档chunks接口测试
├── test_company_code_search.py     # 公司名称搜索接口测试
├── test_chunk_by_id.py            # chunk详情接口测试
│
├── test_vector_retrieval.py       # 向量检索接口测试
├── test_fulltext_retrieval.py     # 全文检索接口测试
├── test_graph_children.py         # 图检索子节点接口测试
├── test_hybrid_retrieval.py       # 混合检索接口测试
├── test_retrieval_health.py       # 检索服务健康检查测试
│
└── test_results.csv               # 测试结果报告（运行后生成）
```

## 使用方法

### 前提条件

1. 确保 FinNet API 服务正在运行：
   ```bash
   cd /Users/han/PycharmProjects/FinNet
   python -m src.api.main
   ```

2. API 服务应该在 `http://localhost:8000` 上运行

### 方法一：使用 Bash 脚本运行（推荐）

```bash
cd /Users/han/PycharmProjects/FinNet/apitest
./run_tests.sh
```

这个脚本会：
- 检查 Python 环境
- 检查 API 服务是否运行
- 运行所有测试
- 显示彩色输出结果

### 方法二：使用 Python 脚本运行

```bash
cd /Users/han/PycharmProjects/FinNet/apitest
python run_all_tests.py
```

### 方法三：运行单个测试

```bash
cd /Users/han/PycharmProjects/FinNet/apitest

# 测试基础接口
python test_basic_endpoints.py

# 测试文档查询接口
python test_document_query.py

# 测试向量检索接口
python test_vector_retrieval.py

# ... 其他测试脚本
```

## 测试结果

### 控制台输出

测试运行时会在控制台显示详细的进度和结果：

```
============================================================
测试文档查询接口: POST /api/v1/document/query
============================================================
测试公司: 平安银行, 万科A, 神州高铁
测试年份: 2024
测试周期: Q1(季报), Q2(半年报), Q3(季报), 年报
总测试数: 12

[1/12] 测试 平安银行 2024Q1 (quarterly_reports)
  状态: PASS | 耗时: 0.118s
  文档ID: 14e2cb05-3ffb-4276-8474-e0140c7fc155...
[2/12] 测试 平安银行 2024Q2 (interim_reports)
  状态: PASS | 耗时: 0.004s
  文档ID: 9d019d09-13ab-4a43-850a-552a4215a7d0...
...

总计: 12/12 通过, 0 未找到, 0 失败
```

### CSV 报告

测试完成后会生成 `test_results.csv` 文件，包含：
- 测试时间
- 测试类别
- 测试名称
- 测试脚本
- 状态（PASS/FAIL/SKIP）
- 总测试数
- 通过数
- 失败数
- 其他（跳过/未找到/无结果）

可以使用 Excel 或其他工具打开查看。

## 测试状态说明

- **PASS** - 测试通过
- **FAIL** - 测试失败（HTTP错误等）
- **ERROR** - 测试异常（连接失败等）
- **NOT_FOUND** - 数据未找到（例如文档不存在）
- **NO_RESULTS** - 检索无结果
- **SKIP** - 测试跳过（例如依赖的数据不存在）
- **MULTIPLE_CANDIDATES** - 公司名称搜索找到多个候选

## 注意事项

1. **数据依赖**：某些测试依赖数据库中的数据，如果数据不存在会显示 `NOT_FOUND` 或 `SKIP`
2. **测试顺序**：测试按照依赖关系排序，建议按顺序运行
3. **超时设置**：每个测试有超时限制（通常10-30秒），长时间无响应会报错
4. **并发测试**：当前脚本是串行执行的，可以根据需要修改为并发执行
5. **报告类型说明**：
   - **Q1（一季报）** ✅ 测试 quarterly_reports
   - **Q2（半年报）** ✅ 测试 interim_reports
   - **Q3（三季报）** ✅ 测试 quarterly_reports
   - **年报** ✅ 测试 annual_reports（不指定quarter字段）

   注：所有四种报告类型均已覆盖测试

## 故障排查

### API 服务未运行
```
✗ API服务未运行或无法访问

请先启动API服务:
  cd /Users/han/PycharmProjects/FinNet
  python -m src.api.main
```

**解决方法**：启动 API 服务

### 测试超时
```
测试超时（超过5分钟）
```

**解决方法**：
- 检查 API 服务性能
- 检查数据库连接
- 检查网络状况

### 数据不存在
```
状态: NOT_FOUND | 原因: 未找到document_id
```

**解决方法**：
- 确认数据已导入数据库
- 检查测试参数（公司代码、年份、季度）是否正确

## 自定义测试

如果需要测试其他公司或时间段，可以修改各测试脚本中的配置：

```python
# 修改测试公司
TEST_COMPANIES = [
    {"name": "公司名称", "code": "股票代码"},
]

# 在 test_config.py 中修改测试配置
TEST_YEAR = 2024
TEST_CASES = [
    {"period": "Q1", "quarter": 1, "doc_type": "quarterly_reports"},
    {"period": "Q2", "quarter": 2, "doc_type": "interim_reports"},
    {"period": "Q3", "quarter": 3, "doc_type": "quarterly_reports"},
    {"period": "Year", "quarter": None, "doc_type": "annual_reports"},
]
```

## 联系方式

如有问题，请联系开发团队或提交 Issue。
