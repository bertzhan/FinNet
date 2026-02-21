# MinerU PDF 解析器实现总结

**完成时间**: 2025-01-13  
**状态**: ✅ 已完成

---

## 📋 已完成的工作

### 1. MinerU 解析器实现 ✅

**文件**: `src/processing/ai/pdf_parser/mineru_parser.py`

**核心功能**：
- ✅ `parse_document()` - 解析单个文档
  - 从数据库获取文档信息
  - 从 MinIO 下载 PDF
  - 调用 MinerU 解析（支持 API 和 Python 包两种方式）
  - 保存解析结果到 Silver 层
  - 记录 ParseTask 到数据库
  - 更新文档状态为 `parsed`

- ✅ `_download_pdf_to_temp()` - 下载 PDF 到临时文件
- ✅ `_parse_with_mineru()` - 调用 MinerU 解析
  - `_parse_with_api()` - API 方式
  - `_parse_with_package()` - Python 包方式
- ✅ `_save_to_silver()` - 保存到 Silver 层
- ✅ `_update_parse_task_success()` - 更新解析任务状态
- ✅ `_update_parse_task_failed()` - 记录解析失败
- ✅ `_update_document_parsed()` - 更新文档状态

### 2. 模块导出 ✅

**文件**: `src/processing/ai/pdf_parser/__init__.py`

- ✅ 导出 `MinerUParser` 类
- ✅ 导出 `get_mineru_parser()` 便捷函数

### 3. 使用示例 ✅

**文件**: `examples/mineru_parse_demo.py`

包含 3 个示例：
- ✅ `demo_parse_single_document()` - 解析单个文档
- ✅ `demo_parse_batch()` - 批量解析
- ✅ `demo_check_parse_status()` - 检查解析状态

### 4. 文档 ✅

**文件**: `src/processing/ai/pdf_parser/README.md`

- ✅ 使用说明
- ✅ 配置选项
- ✅ 解析结果格式
- ✅ 错误处理

---

## 🔄 数据流程

```
┌─────────────────┐
│  Bronze 层 PDF  │
│  (MinIO)        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  下载 PDF       │
│  (临时文件)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  MinerU 解析    │
│  (API/包)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  解析结果       │
│  (JSON)         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Silver 层      │
│  (text_cleaned) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  数据库记录     │
│  (ParseTask)    │
└─────────────────┘
```

---

## 📊 解析结果格式

### Silver 层 JSON 结构

```json
{
  "document_id": 123,
  "stock_code": "000001",
  "company_name": "平安银行",
  "market": "hs",
  "doc_type": "quarterly_report",
  "year": 2023,
  "quarter": 3,
  "parsed_at": "2025-01-13T10:00:00",
  "parser": "mineru",
  "text": "解析后的纯文本...",
  "markdown": "解析后的 Markdown...",
  "tables": [
    {
      "table_index": 0,
      "markdown": "| 列1 | 列2 |\n|-----|-----|"
    }
  ],
  "images": [
    {
      "image_index": 0,
      "description": "图片描述"
    }
  ],
  "text_length": 50000,
  "tables_count": 10,
  "images_count": 5,
  "metadata": {}
}
```

### Silver 层路径

**常规文档**：
```
silver/text_cleaned/hs/quarterly_reports/2023/Q3/000001/000001_2023_Q3_parsed.json
```

**IPO 文档**：
```
silver/text_cleaned/hs/ipo_prospectus/000001/000001_IPO_parsed.json
```

---

## 🎯 使用示例

### 基本使用

```python
from src.processing.ai.pdf_parser import get_mineru_parser

# 创建解析器
parser = get_mineru_parser()

# 解析文档
result = parser.parse_document(document_id=123)

if result["success"]:
    print(f"✅ 解析成功！")
    print(f"Silver 层路径: {result['output_path']}")
    print(f"文本长度: {result['extracted_text_length']} 字符")
```

### 批量解析

```python
from src.storage.metadata import get_postgres_client, crud
from src.common.constants import DocumentStatus

pg_client = get_postgres_client()
parser = get_mineru_parser()

with pg_client.get_session() as session:
    docs = crud.get_documents_by_status(
        session=session,
        status=DocumentStatus.CRAWLED.value,
        limit=10
    )
    
    for doc in docs:
        result = parser.parse_document(doc.id)
        print(f"文档 {doc.id}: {'✅' if result['success'] else '❌'}")
```

---

## ⚙️ 配置

### 环境变量

```bash
# PDF 解析器配置
PDF_PARSER=mineru                    # 默认解析器
MINERU_API_BASE=http://localhost:8000  # MinerU API 地址（可选）
MINERU_BATCH_SIZE=5                   # 批量处理大小
```

### 使用方式

**方式1：MinerU API（推荐）**
- 配置 `MINERU_API_BASE` 环境变量
- 解析器会自动使用 API 方式

**方式2：MinerU Python 包**
- 安装：`pip install mineru`
- 不配置 `MINERU_API_BASE`，解析器会自动使用包方式

---

## ✅ 测试验证

### 运行示例

```bash
# 解析单个文档
python examples/mineru_parse_demo.py single

# 批量解析
python examples/mineru_parse_demo.py batch

# 检查解析状态
python examples/mineru_parse_demo.py status
```

### 验证点

- [ ] 解析器可以初始化
- [ ] 可以从 MinIO 下载 PDF
- [ ] 可以调用 MinerU 解析
- [ ] 解析结果保存到 Silver 层
- [ ] ParseTask 记录创建成功
- [ ] 文档状态更新为 `parsed`

---

## 📝 数据库记录

### ParseTask 表

每次解析都会创建一条记录：

| 字段 | 值示例 |
|-----|--------|
| `document_id` | 123 |
| `parser_type` | mineru |
| `status` | completed |
| `output_path` | silver/text_cleaned/.../parsed.json |
| `extracted_text_length` | 50000 |
| `extracted_tables_count` | 10 |
| `extracted_images_count` | 5 |

### Document 状态

- 解析前：`crawled`
- 解析后：`parsed`

---

## 🔍 错误处理

### 常见错误

| 错误 | 原因 | 处理 |
|-----|------|------|
| `文档不存在` | document_id 无效 | 检查文档ID |
| `PDF 下载失败` | MinIO 连接问题 | 检查 MinIO 服务 |
| `MinerU 包未安装` | 未安装 mineru | `pip install mineru` |
| `API 调用失败` | MinerU API 不可用 | 检查 API 服务 |

### 重试机制

解析失败后：
- 文档状态保持为 `crawled`
- ParseTask 记录错误信息
- 可以重新调用 `parse_document()` 重试

---

## 🚀 下一步

解析完成后，可以继续：

1. **文本清洗和分块**
   - `processing/text/cleaner.py` - 文本清洗
   - `processing/text/chunker.py` - 文本分块

2. **向量化**
   - `processing/ai/embedding/bge_embedder.py` - BGE Embedding
   - 写入 Milvus

3. **Dagster 作业**
   - 创建 `parsing_jobs.py` - 自动解析作业
   - 扫描待解析文档并批量处理

---

## 📚 相关文档

- [plan.md](../plan.md) - 完整架构设计
- [README.md](README.md) - MinerU 解析器使用指南
- [QUARANTINE_MANAGEMENT.md](../QUARANTINE_MANAGEMENT.md) - 隔离管理

---

*最后更新: 2025-01-13*
