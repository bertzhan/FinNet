# MinerU API 集成文档

**更新时间**: 2025-01-15

---

## 📋 概述

MinerU 解析器已重写为使用 API 接口方式，通过 OpenBayes API 服务进行 PDF 解析。

**API 地址**: `https://hanco9-bb.gear-c1.openbayes.net`  
**API 文档**: https://hanco9-bb.gear-c1.openbayes.net/docs#/default/parse_pdf_file_parse_post

---

## 🔧 配置

### 环境变量

```bash
# MinerU API 地址（可选，默认使用 OpenBayes API）
MINERU_API_BASE=https://hanco9-bb.gear-c1.openbayes.net
```

### 代码配置

解析器会自动使用 API 模式，默认 API 地址为：
- `https://hanco9-bb.gear-c1.openbayes.net`

如果设置了 `MINERU_API_BASE` 环境变量，将使用该地址。

---

## 📡 API 调用

### 请求格式

**端点**: `POST /parse`

**请求类型**: `multipart/form-data`

**参数**:
- `file`: PDF 文件（二进制数据）

**示例**:
```python
import requests

url = "https://hanco9-bb.gear-c1.openbayes.net/parse"
files = {"file": ("document.pdf", pdf_data, "application/pdf")}

response = requests.post(url, files=files, timeout=600)
result = response.json()
```

### 响应格式

API 可能返回以下格式之一：

**格式1: 直接返回解析结果**
```json
{
  "markdown": "...",
  "tables": [...],
  "images": [...]
}
```

**格式2: 嵌套在 data 字段中**
```json
{
  "data": {
    "markdown": "...",
    "tables": [...],
    "images": [...],
    "middle_json": {...}
  }
}
```

**格式3: 嵌套在 result 字段中**
```json
{
  "result": {
    "markdown": "...",
    "tables": [...],
    "images": [...]
  }
}
```

解析器会自动处理这些不同的响应格式。

---

## 🚀 使用示例

### 基本使用

```python
from src.processing.ai.pdf_parser import get_mineru_parser

# 创建解析器（自动使用 API 模式）
parser = get_mineru_parser()

# 解析文档
result = parser.parse_document(document_id=123)

if result["success"]:
    print(f"✅ 解析成功！")
    print(f"Silver 层路径: {result['output_path']}")
    print(f"文本长度: {result['extracted_text_length']} 字符")
    print(f"表格数量: {result['extracted_tables_count']}")
    print(f"图片数量: {result['extracted_images_count']}")
else:
    print(f"❌ 解析失败: {result['error_message']}")
```

### 批量解析

```python
from src.storage.metadata import get_postgres_client, crud
from src.common.constants import DocumentStatus
from src.processing.ai.pdf_parser import get_mineru_parser

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

## ⚙️ 功能特性

### 1. 自动响应格式识别

解析器会自动识别并处理多种 API 响应格式：
- 直接返回解析结果
- 嵌套在 `data` 字段中
- 嵌套在 `result` 字段中

### 2. 错误处理

- **超时处理**: 10 分钟超时，适合大型 PDF 文件
- **HTTP 错误**: 详细的错误信息记录
- **网络错误**: 完整的异常处理和日志记录

### 3. 数据提取

- **Markdown 内容**: 提取完整的 Markdown 格式文本
- **纯文本**: 自动从 Markdown 中提取纯文本（去除格式标记）
- **表格**: 提取表格的 Markdown 格式和边界框信息
- **图片**: 提取图片的描述和边界框信息
- **结构化数据**: 提取 `middle_json` 和 `content_list`

---

## 📊 解析结果格式

保存到 Silver 层的 JSON 结构：

```json
{
  "document_id": 123,
  "stock_code": "000001",
  "company_name": "平安银行",
  "market": "a_share",
  "doc_type": "ipo_prospectus",
  "year": 2023,
  "quarter": null,
  "parsed_at": "2025-01-15T10:00:00",
  "parser": "mineru",
  "text": "提取的纯文本（去除 Markdown 格式）",
  "markdown": "完整的 Markdown 内容",
  "tables": [
    {
      "table_index": 0,
      "page": 0,
      "markdown": "| 列1 | 列2 |\n|-----|-----|",
      "bbox": [x1, y1, x2, y2]
    }
  ],
  "images": [
    {
      "image_index": 0,
      "page": 0,
      "description": "图片描述",
      "bbox": [x1, y1, x2, y2]
    }
  ],
  "text_length": 50000,
  "tables_count": 10,
  "images_count": 5,
  "metadata": {
    "api_base": "https://hanco9-bb.gear-c1.openbayes.net",
    "response_keys": ["markdown", "tables", "images"]
  }
}
```

---

## 🔍 调试

### 日志级别

解析器会记录详细的日志信息：

- **INFO**: API 调用、解析成功/失败
- **DEBUG**: API 响应状态、响应键、文件大小

### 常见问题

**1. API 请求超时**
- 原因: PDF 文件过大或网络问题
- 解决: 增加超时时间或检查网络连接

**2. API HTTP 错误**
- 原因: API 服务不可用或请求格式错误
- 解决: 检查 API 地址和请求格式

**3. 响应格式不匹配**
- 原因: API 响应格式与预期不符
- 解决: 检查日志中的 `response_keys`，更新解析逻辑

---

## 📝 注意事项

1. **API 超时**: 默认超时时间为 10 分钟，适合大多数 PDF 文件
2. **文件大小**: 确保 PDF 文件大小在 API 限制范围内
3. **网络连接**: 需要稳定的网络连接访问 API 服务
4. **API 配额**: 注意 API 调用频率限制（如果有）

---

## 🔄 从本地包模式迁移

如果之前使用本地 MinerU 包模式，现在已自动切换到 API 模式：

1. **无需安装依赖**: 不再需要安装 `mineru`、`ultralytics` 等本地依赖
2. **配置简单**: 只需设置 `MINERU_API_BASE` 环境变量（可选）
3. **性能稳定**: API 服务提供稳定的解析性能

---

*最后更新: 2025-01-15*
