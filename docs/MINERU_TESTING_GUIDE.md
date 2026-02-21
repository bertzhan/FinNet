# MinerU 解析器测试指南

**更新时间**: 2025-01-13

---

## 📋 测试前准备

### 1. 安装 MinerU

**方式1: Python 包安装（推荐）**

```bash
pip install mineru
```

**方式2: 使用 API 方式**

如果不想安装 MinerU 包，可以配置 API 地址：

```bash
export MINERU_API_BASE=http://localhost:8000
```

### 2. 确保服务运行

- ✅ **MinIO**: 确保 MinIO 服务运行，并且有 PDF 文件
- ✅ **PostgreSQL**: 确保数据库服务运行（可选，用于完整流程测试）

---

## 🧪 测试方式

### 方式1: 完整流程测试（推荐）

使用数据库中的文档记录进行完整测试：

```bash
python examples/test_mineru_local.py
```

**要求**:
- MinerU 已安装
- 数据库中有状态为 `crawled` 的文档记录
- MinIO 中存在对应的 PDF 文件

### 方式2: 简单功能测试

测试基本功能，不依赖数据库：

```bash
python tests/test_mineru_simple.py
```

**测试内容**:
- MinerU 安装检查
- MinIO 文件检查
- 本地 PDF 解析（如果有）

### 方式3: 完整单元测试

运行所有测试用例：

```bash
python tests/test_mineru_parser.py
```

**测试内容**:
- 模块导入
- MinerU 包导入
- 解析器初始化
- 查找待解析文档
- 解析单个文档
- Markdown 文本提取
- Silver 层路径生成

---

## 🔍 当前测试状态

### ✅ 已通过

1. **模块导入** - 解析器模块可以正常导入
2. **解析器初始化** - MinIO、PostgreSQL 客户端初始化成功
3. **查找待解析文档** - 可以从数据库查找文档
4. **Markdown 文本提取** - 文本提取功能正常
5. **Silver 层路径生成** - 路径生成符合规范
6. **MinIO 文件检查** - MinIO 中有 PDF 文件

### ⚠️ 待解决

1. **MinerU 包未安装**
   - 需要运行: `pip install mineru`
   - 或者配置 `MINERU_API_BASE` 使用 API 方式

2. **数据库文档路径不匹配**
   - 数据库中的文档路径与 MinIO 实际路径不一致
   - 建议: 重新运行爬虫任务，确保路径一致

---

## 📝 测试示例

### 示例1: 解析单个文档

```python
from src.processing.ai.pdf_parser import get_mineru_parser

# 创建解析器
parser = get_mineru_parser()

# 解析文档（需要文档 ID）
result = parser.parse_document(document_id=123)

if result["success"]:
    print(f"✅ 解析成功！")
    print(f"Silver 层路径: {result['output_path']}")
    print(f"文本长度: {result['extracted_text_length']} 字符")
    print(f"表格数量: {result['extracted_tables_count']}")
    print(f"图片数量: {result['extracted_images_count']}")
```

### 示例2: 批量解析

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

## 🐛 常见问题

### Q1: MinerU 导入失败

**错误**: `ModuleNotFoundError: No module named 'mineru'`

**解决**:
```bash
pip install mineru
```

### Q2: MinIO 文件不存在

**错误**: `MinIO 文件不存在: bronze/hs/...`

**原因**: 数据库中的文档路径与 MinIO 实际路径不一致

**解决**:
1. 检查 MinIO 中的实际文件路径
2. 更新数据库中的 `minio_object_path` 字段
3. 或者重新运行爬虫任务

### Q3: 解析失败

**可能原因**:
- PDF 文件损坏
- MinerU 解析引擎未正确初始化
- 临时目录权限问题

**调试**:
1. 检查日志输出
2. 手动下载 PDF 文件测试
3. 检查 MinerU 输出目录

---

## 📊 测试结果示例

### 成功输出

```
✅ 解析成功！
   解析任务ID: 1
   Silver 层路径: silver/text_cleaned/hs/ipo_prospectus/300542/300542_parsed.json
   文本长度: 50000 字符
   表格数量: 10
   图片数量: 5
```

### 失败输出

```
❌ 解析失败: MinerU 解析异常: ...
```

---

## 🚀 下一步

测试通过后，可以：

1. **创建 Dagster 解析作业**
   - 自动扫描待解析文档
   - 批量处理解析任务

2. **实现文本清洗和分块**
   - 处理 Silver 层的文本
   - 按语义分块（512 tokens）

3. **实现向量化**
   - 使用 BGE Embedding
   - 写入 Milvus

---

*最后更新: 2025-01-13*
