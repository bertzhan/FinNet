# MinerU PDF 解析器实现总结

**完成时间**: 2025-01-13  
**状态**: ✅ 已完成

---

## ✅ 已完成的工作

### 1. MinerU 解析器实现

**文件**: `src/processing/ai/pdf_parser/mineru_parser.py`

**核心功能**：
- ✅ `parse_document()` - 解析文档的完整流程
- ✅ `_download_pdf_to_temp()` - 从 MinIO 下载 PDF
- ✅ `_parse_with_mineru()` - 调用 MinerU 解析
  - `_parse_with_api()` - API 方式（如果配置了 MINERU_API_BASE）
  - `_parse_with_package()` - Python 包方式（使用 `do_parse` 函数）
- ✅ `_save_to_silver()` - 保存解析结果到 Silver 层
- ✅ `_extract_text_from_markdown()` - 从 Markdown 提取纯文本

### 2. MinerU 集成方式

根据你提供的 MinerU 实际使用方式，解析器使用：

```python
from mineru.cli.parse import do_parse

do_parse(
    output_dir=temp_output_dir,
    pdf_file_names=[pdf_file_name],
    pdf_bytes_list=[pdf_bytes],
    p_lang_list=["ch"],  # 中文
    backend="hybrid-auto-engine",  # 混合引擎，高精度
    parse_method="auto",  # 自动选择解析方法
    formula_enable=True,  # 启用公式解析
    table_enable=True,  # 启用表格解析
    f_dump_md=True,  # 输出 Markdown
    f_dump_middle_json=True,  # 输出中间 JSON
    f_dump_content_list=True,  # 输出内容列表
)
```

### 3. 解析结果提取

从 MinerU 输出目录读取：
- ✅ `{pdf_file_name}.md` - Markdown 文件
- ✅ `{pdf_file_name}_middle.json` - 中间 JSON（包含表格、图片信息）
- ✅ `{pdf_file_name}_content_list.json` - 内容列表

### 4. 表格和图片提取

从 `middle_json` 中提取：
- **表格**：从 `pdf_info.pages[].tables[]` 提取
- **图片**：从 `pdf_info.pages[].images[]` 提取

---

## 📊 解析结果格式

保存到 Silver 层的 JSON 结构：

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
  "parser_version": "package",
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
  "content_list": [...],
  "text_length": 50000,
  "tables_count": 10,
  "images_count": 5,
  "metadata": {
    "pdf_info": {...},
    "parse_method": "hybrid_auto",
    "backend": "hybrid-auto-engine"
  }
}
```

---

## 🔧 配置选项

### 环境变量

```bash
# PDF 解析器配置
PDF_PARSER=mineru                    # 默认解析器
MINERU_API_BASE=http://localhost:8000  # MinerU API 地址（可选，如果使用 API 方式）
MINERU_BATCH_SIZE=5                   # 批量处理大小
```

### 使用方式

**方式1：MinerU Python 包（当前实现）**
- 安装：`pip install mineru`
- 使用 `do_parse` 函数
- Backend: `hybrid-auto-engine`（推荐，高精度）

**方式2：MinerU API（可选）**
- 配置 `MINERU_API_BASE` 环境变量
- 解析器会自动使用 API 方式

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
    print(f"表格数量: {result['extracted_tables_count']}")
    print(f"图片数量: {result['extracted_images_count']}")
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

## 📁 文件输出

### MinerU 输出目录结构

```
{temp_output_dir}/
└── {pdf_file_name}/
    └── hybrid_auto/  # 或实际使用的 parse_method
        ├── {pdf_file_name}.md              # Markdown 文件
        ├── {pdf_file_name}_middle.json     # 中间 JSON
        └── {pdf_file_name}_content_list.json  # 内容列表
```

### Silver 层路径

**常规文档**：
```
silver/text_cleaned/a_share/quarterly_reports/2023/Q3/000001/000001_2023_Q3_parsed.json
```

**IPO 文档**：
```
silver/text_cleaned/a_share/ipo_prospectus/000001/000001_IPO_parsed.json
```

---

## ✅ 功能特性

1. **自动路径查找**：如果输出目录不存在，会自动查找实际目录
2. **纯文本提取**：从 Markdown 中提取纯文本（去除格式标记）
3. **结构化信息**：提取表格、图片的结构化信息
4. **错误处理**：完整的异常处理和日志记录
5. **临时文件清理**：自动清理临时输出目录

---

## 🚀 下一步

解析完成后，可以继续：

1. **文本清洗和分块**
   - 清洗解析后的文本
   - 按语义分块（512 tokens，重叠 50 tokens）

2. **向量化**
   - 使用 BGE Embedding
   - 写入 Milvus

3. **Dagster 作业**
   - 创建自动解析作业
   - 扫描待解析文档并批量处理

---

*最后更新: 2025-01-13*
