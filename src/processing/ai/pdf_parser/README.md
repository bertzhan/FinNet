# MinerU PDF 解析器

## 概述

MinerU PDF 解析器用于将 Bronze 层的 PDF 文档解析为结构化文本，并直接上传到 Silver 层。

按照 plan.md 4.3.1 设计，MinerU 专门优化了中文文档和复杂表格的解析。

## 功能特性

- ✅ 支持 API 和 Python 包两种调用方式
- ✅ 自动从 MinIO 下载 PDF
- ✅ 解析结果自动上传到 Silver 层
- ✅ 记录解析任务到数据库
- ✅ 更新文档状态
- ✅ 支持批量解析

## 安装

### 方式1：使用 MinerU API（推荐）

如果 MinerU 已部署为服务，配置 API 地址：

```bash
# 在 .env 文件中配置
MINERU_API_BASE=http://localhost:8000
```

### 方式2：使用 MinerU Python 包

```bash
pip install mineru
```

## 快速开始

### 基本使用

```python
from src.processing.ai.pdf_parser import get_mineru_parser

# 创建解析器
parser = get_mineru_parser()

# 解析文档（document_id 从数据库获取）
result = parser.parse_document(document_id=123)

if result["success"]:
    print(f"✅ 解析成功！")
    print(f"Silver 层路径: {result['output_path']}")
    print(f"文本长度: {result['extracted_text_length']} 字符")
else:
    print(f"❌ 解析失败: {result['error_message']}")
```

### 批量解析

```python
from src.storage.metadata import get_postgres_client, crud
from src.common.constants import DocumentStatus

pg_client = get_postgres_client()
parser = get_mineru_parser()

with pg_client.get_session() as session:
    # 查找待解析的文档
    docs = crud.get_documents_by_status(
        session=session,
        status=DocumentStatus.CRAWLED.value,
        limit=10
    )
    
    for doc in docs:
        result = parser.parse_document(doc.id)
        print(f"文档 {doc.id}: {'✅' if result['success'] else '❌'}")
```

## 解析结果格式

解析结果保存在 Silver 层，JSON 格式：

```json
{
  "document_id": 123,
  "stock_code": "000001",
  "company_name": "平安银行",
  "market": "a_share",
  "doc_type": "quarterly_report",
  "year": 2023,
  "quarter": 3,
  "parsed_at": "2025-01-13T10:00:00",
  "parser": "mineru",
  "text": "解析后的纯文本内容...",
  "markdown": "解析后的 Markdown 内容...",
  "tables": [
    {
      "table_index": 0,
      "markdown": "| 列1 | 列2 |\n|-----|-----|\n| 值1 | 值2 |"
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

## Silver 层路径

解析结果保存在 Silver 层的 `text_cleaned` 子目录：

```
silver/text_cleaned/{market}/{doc_type}/{year}/{quarter}/{stock_code}/{filename}
```

示例：
```
silver/text_cleaned/a_share/quarterly_reports/2023/Q3/000001/000001_2023_Q3_parsed.json
```

## 数据库记录

### ParseTask 表

每次解析都会创建一条 `ParseTask` 记录：

| 字段 | 说明 |
|-----|------|
| `document_id` | 关联的文档ID |
| `parser_type` | 解析器类型（mineru） |
| `status` | 状态（pending/processing/completed/failed） |
| `output_path` | Silver 层路径 |
| `extracted_text_length` | 提取的文本长度 |
| `extracted_tables_count` | 提取的表格数量 |
| `extracted_images_count` | 提取的图片数量 |

### Document 状态更新

解析成功后，文档状态从 `crawled` 更新为 `parsed`。

## 配置选项

### 环境变量

```bash
# PDF 解析器配置
PDF_PARSER=mineru                    # 默认解析器
MINERU_API_BASE=http://localhost:8000  # MinerU API 地址（可选）
MINERU_BATCH_SIZE=5                   # 批量处理大小
```

### 代码配置

```python
from src.common.config import pdf_parser_config

print(f"默认解析器: {pdf_parser_config.DEFAULT_PARSER}")
print(f"MinerU API: {pdf_parser_config.MINERU_API_BASE}")
```

## 错误处理

解析失败时：
- 记录错误信息到 `ParseTask.error_message`
- 文档状态保持为 `crawled`（不更新为 `parsed`）
- 可以重试解析

常见错误：
- `文档不存在`: document_id 无效
- `PDF 下载失败`: MinIO 连接问题或文件不存在
- `MinerU 包未安装`: 需要安装 `pip install mineru`
- `API 调用失败`: MinerU API 服务不可用

## 运行示例

```bash
# 解析单个文档
python examples/mineru_parse_demo.py single

# 批量解析
python examples/mineru_parse_demo.py batch

# 检查解析状态
python examples/mineru_parse_demo.py status

# 运行所有示例
python examples/mineru_parse_demo.py
```

## 下一步

解析完成后，可以：
1. 文本清洗和分块（`processing/text/`）
2. 向量化（`processing/ai/embedding/`）
3. 构建知识图谱（`processing/nlp/`）

---

*最后更新: 2025-01-13*
