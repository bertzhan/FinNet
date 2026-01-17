# ParsedDocument 表设计文档

**版本**: 1.0  
**更新时间**: 2026-01-16

---

## 📋 表结构设计

### ParsedDocument 表（Silver 层解析文档表）

```python
class ParsedDocument(Base):
    """
    Silver 层解析文档表
    存储解析后的文档信息和路径
    """
    __tablename__ = 'parsed_documents'

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # ==================== 关联字段 ====================
    document_id = Column(Integer, nullable=False, index=True)
    parse_task_id = Column(Integer, nullable=False, index=True)
    
    # ==================== 路径信息 ====================
    content_json_path = Column(String(500), nullable=False)    # 内容 JSON 文件路径（主文件）
    markdown_path = Column(String(500), nullable=True)         # Markdown 文件路径（可选）
    image_folder_path = Column(String(500), nullable=True)     # 图片文件夹路径（可选）
    
    # ==================== 哈希值字段 ====================
    content_json_hash = Column(String(64), nullable=False, index=True)      # JSON 文件哈希
    markdown_hash = Column(String(64), nullable=True)                      # Markdown 文件哈希
    source_document_hash = Column(String(64), nullable=False, index=True)  # 源 PDF 哈希
    
    # ==================== 解析结果统计 ====================
    text_length = Column(Integer, default=0)                   # 文本长度（字符数）
    tables_count = Column(Integer, default=0)                  # 表格数量
    images_count = Column(Integer, default=0)                   # 图片数量
    pages_count = Column(Integer, default=0)                    # 页数
    
    # ==================== 解析器信息 ====================
    parser_type = Column(String(50), nullable=False)            # mineru/docling
    parser_version = Column(String(100))                        # 解析器版本
    
    # ==================== 解析质量指标 ====================
    parsing_quality_score = Column(Float)                      # 解析质量评分（0-1）
    has_tables = Column(Boolean, default=False)                 # 是否包含表格
    has_images = Column(Boolean, default=False)                # 是否包含图片
    
    # ==================== 时间戳 ====================
    parsed_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # ==================== 状态 ====================
    status = Column(String(50), default='active')              # active/archived
    
    # ==================== 索引和约束 ====================
    __table_args__ = (
        # 索引
        Index('idx_document_parsed', 'document_id', 'parsed_at'),
        Index('idx_parse_task', 'parse_task_id'),
        Index('idx_source_hash', 'source_document_hash'),
        Index('idx_json_hash', 'content_json_hash'),
        Index('idx_text_length', 'text_length'),
        
        # 外键约束
        ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['parse_task_id'], ['parse_tasks.id'], ondelete='CASCADE'),
    )
```

---

## 📁 路径字段说明

### 1. `content_json_path`（必需）

**用途**: 存储主 JSON 文件路径，包含解析后的所有结构化数据

**路径格式示例**:
```
silver/text_cleaned/a_share/quarterly_reports/2023/Q3/000001/document_content_list.json
```

**文件内容结构**:
```json
{
    "document_id": 123,
    "stock_code": "000001",
    "text": "提取的纯文本内容...",
    "markdown": "Markdown 格式内容...",
    "tables": [
        {
            "table_index": 0,
            "page": 5,
            "markdown": "| 列1 | 列2 |\n|-----|-----|",
            "bbox": [x1, y1, x2, y2]
        }
    ],
    "images": [
        {
            "image_index": 0,
            "page": 3,
            "filename": "img_001.jpg",
            "description": "财务数据图表",
            "bbox": [x1, y1, x2, y2]
        }
    ],
    "metadata": {
        "parser": "mineru",
        "parser_version": "api-xxx",
        "parsed_at": "2026-01-16T10:00:00"
    }
}
```

---

### 2. `markdown_path`（可选）

**用途**: 存储 Markdown 格式文件路径（如果解析器生成了独立的 Markdown 文件）

**路径格式示例**:
```
silver/text_cleaned/a_share/quarterly_reports/2023/Q3/000001/document.md
```

**何时为 NULL**:
- 解析器没有生成独立的 Markdown 文件
- Markdown 内容已包含在 JSON 文件中
- 用户不需要 Markdown 格式

**文件内容**: 纯 Markdown 格式文本

---

### 3. `image_folder_path`（可选）

**用途**: 存储图片文件夹路径，该文件夹包含从 PDF 中提取的所有图片

**路径格式示例**:
```
silver/text_cleaned/a_share/quarterly_reports/2023/Q3/000001/images/
```

**文件夹结构示例**:
```
images/
├── img_001.jpg      # 第1页的图片
├── img_002.jpg      # 第3页的图片
├── img_003.jpg      # 第5页的图片
└── ...
```

**何时为 NULL**:
- PDF 中没有图片
- 图片已嵌入到 JSON 中（Base64）
- 不需要单独存储图片文件

**图片元数据**: 图片的详细信息（文件名、页码、描述等）存储在 `content_json_path` 的 JSON 文件中

---

## 🔄 路径生成逻辑

### 路径生成示例

```python
from src.storage.object_store.path_manager import PathManager

pm = PathManager()
doc = get_document(document_id)

# 1. 生成基础路径
base_path = pm.get_silver_path(
    market=doc.market,
    doc_type=doc.doc_type,
    stock_code=doc.stock_code,
    year=doc.year,
    quarter=doc.quarter,
    filename="document_content_list.json",
    subdir="text_cleaned"
)

# 2. 生成三个路径
content_json_path = base_path
# 例如: silver/text_cleaned/a_share/quarterly_reports/2023/Q3/000001/document_content_list.json

markdown_path = base_path.replace('document_content_list.json', 'document.md')
# 例如: silver/text_cleaned/a_share/quarterly_reports/2023/Q3/000001/000001_2023_Q3.md

image_folder_path = base_path.rsplit('/', 1)[0] + '/images/'
# 例如: silver/text_cleaned/a_share/quarterly_reports/2023/Q3/000001/images/
```

---

## 💾 数据存储示例

### 示例 1: 完整解析结果（包含所有文件）

```python
parsed_doc = ParsedDocument(
    document_id=123,
    parse_task_id=456,
    
    # 路径信息
    content_json_path="silver/text_cleaned/a_share/quarterly_reports/2023/Q3/000001/document_content_list.json",
    markdown_path="silver/text_cleaned/a_share/quarterly_reports/2023/Q3/000001/document.md",
    image_folder_path="silver/text_cleaned/a_share/quarterly_reports/2023/Q3/000001/images/",
    
    # 哈希值
    content_json_hash="a1b2c3d4e5f6...",
    markdown_hash="b2c3d4e5f6a1...",
    source_document_hash="d4e5f6a1b2c3...",
    
    # 统计信息
    text_length=50000,
    tables_count=10,
    images_count=5,
    pages_count=50,
    
    # 解析器信息
    parser_type="mineru",
    parser_version="api-v1.0",
    
    # 质量指标
    has_tables=True,
    has_images=True
)
```

### 示例 2: 简单解析结果（无 Markdown 和图片）

```python
parsed_doc = ParsedDocument(
    document_id=124,
    parse_task_id=457,
    
    # 路径信息（只有 JSON）
    content_json_path="silver/text_cleaned/a_share/ipo_prospectus/000001/document_content_list.json",
    markdown_path=None,           # 无 Markdown 文件
    image_folder_path=None,       # 无图片文件夹
    
    # 哈希值
    content_json_hash="e5f6a1b2c3d4...",
    markdown_hash=None,           # 无 Markdown，哈希也为 None
    source_document_hash="a1b2c3d4e5f6...",
    
    # 统计信息
    text_length=30000,
    tables_count=0,
    images_count=0,
    pages_count=30,
    
    # 解析器信息
    parser_type="mineru",
    parser_version="api-v1.0",
    
    # 质量指标
    has_tables=False,
    has_images=False
)
```

---

## 🔍 查询示例

### 1. 获取解析结果的所有文件路径

```python
def get_parsed_document_files(parsed_doc_id: int) -> Dict[str, Optional[str]]:
    """获取解析文档的所有文件路径"""
    parsed_doc = session.query(ParsedDocument).filter(
        ParsedDocument.id == parsed_doc_id
    ).first()
    
    return {
        'content_json': parsed_doc.content_json_path,
        'markdown': parsed_doc.markdown_path,
        'images_folder': parsed_doc.image_folder_path
    }
```

### 2. 下载解析结果的所有文件

```python
def download_parsed_document_files(
    parsed_doc: ParsedDocument,
    minio_client: MinIOClient,
    output_dir: str
) -> Dict[str, str]:
    """下载解析文档的所有文件到本地"""
    files = {}
    
    # 1. 下载 JSON 文件
    json_path = os.path.join(output_dir, 'document_content_list.json')
    minio_client.download_file(
        parsed_doc.content_json_path,
        json_path
    )
    files['json'] = json_path
    
    # 2. 下载 Markdown 文件（如果存在）
    if parsed_doc.markdown_path:
        md_path = os.path.join(output_dir, 'parsed.md')
        minio_client.download_file(
            parsed_doc.markdown_path,
            md_path
        )
        files['markdown'] = md_path
    
    # 3. 下载图片文件夹（如果存在）
    if parsed_doc.image_folder_path:
        images_dir = os.path.join(output_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)
        
        # 列出文件夹中的所有图片
        image_objects = minio_client.list_files(
            prefix=parsed_doc.image_folder_path
        )
        
        for img_obj in image_objects:
            if img_obj['name'].endswith(('.jpg', '.png', '.jpeg')):
                local_path = os.path.join(
                    images_dir,
                    os.path.basename(img_obj['name'])
                )
                minio_client.download_file(
                    img_obj['name'],
                    local_path
                )
        
        files['images'] = images_dir
    
    return files
```

### 3. 查找包含图片的解析文档

```python
def find_parsed_documents_with_images(
    session: Session,
    document_id: Optional[int] = None
) -> List[ParsedDocument]:
    """查找包含图片的解析文档"""
    query = session.query(ParsedDocument).filter(
        ParsedDocument.has_images == True,
        ParsedDocument.image_folder_path.isnot(None)
    )
    
    if document_id:
        query = query.filter(ParsedDocument.document_id == document_id)
    
    return query.all()
```

---

## 🔐 哈希值计算说明

#### `content_json_hash` - JSON 文件哈希

```python
from src.common.utils import calculate_file_hash

# 计算 JSON 文件的哈希值（文件级）
content_json_hash = calculate_file_hash(
    file_path=content_json_path,
    algorithm='sha256'
)
```

#### `markdown_hash` - Markdown 文件哈希

```python
# 如果存在 Markdown 文件
if markdown_path:
    markdown_hash = calculate_file_hash(
        file_path=markdown_path,
        algorithm='sha256'
    )
else:
    markdown_hash = None
```

#### `source_document_hash` - 源 PDF 哈希

```python
# 从 Document 表获取源 PDF 的哈希值
source_document_hash = doc.file_hash  # 已在爬虫阶段计算
```

### 完整哈希计算示例

```python
def calculate_parsed_document_hashes(
    json_data: Dict[str, Any],
    content_json_path: str,
    markdown_path: Optional[str] = None,
    source_doc_hash: str = None
) -> Dict[str, str]:
    """计算解析文档的所有哈希值"""
    
    from src.common.utils import calculate_file_hash
    
    # 1. JSON 文件哈希（文件级）
    content_json_hash = calculate_file_hash(
        content_json_path,
        algorithm='sha256'
    )
    
    # 2. Markdown 文件哈希（如果存在）
    markdown_hash = None
    if markdown_path:
        markdown_hash = calculate_file_hash(
            markdown_path,
            algorithm='sha256'
        )
    
    # 3. 源文档哈希
    source_document_hash = source_doc_hash or ""
    
    return {
        'content_json_hash': content_json_hash,
        'markdown_hash': markdown_hash,
        'source_document_hash': source_document_hash
    }
```

---

## 🔄 更新解析器代码

### 在 MinerU 解析器中更新

```python
# src/processing/ai/pdf_parser/mineru_parser.py

def _save_to_silver(
    self,
    doc: Document,
    parse_result: Dict[str, Any]
) -> str:
    """保存解析结果到 Silver 层，返回主 JSON 路径"""
    
    # 1. 生成路径
    base_dir = self.path_manager.get_silver_path(
        market=doc.market,
        doc_type=doc.doc_type,
        stock_code=doc.stock_code,
        year=doc.year,
        quarter=doc.quarter,
        filename="document_content_list.json",
        subdir="text_cleaned"
    )
    
    content_json_path = base_dir
    markdown_path = base_dir.replace('document_content_list.json', 'document.md')
    image_folder_path = base_dir.rsplit('/', 1)[0] + '/images/'
    
    # 2. 保存 JSON 文件
    json_data = {
        "document_id": doc.id,
        "stock_code": doc.stock_code,
        "text": parse_result.get("text", ""),
        "markdown": parse_result.get("markdown", ""),
        "tables": parse_result.get("tables", []),
        "images": parse_result.get("images", []),
        "metadata": parse_result.get("metadata", {})
    }
    
    self.minio_client.upload_json(
        object_name=content_json_path,
        data=json_data
    )
    
    # 3. 保存 Markdown 文件（如果存在）
    if parse_result.get("markdown"):
        self.minio_client.upload_file(
            object_name=markdown_path,
            data=parse_result["markdown"].encode('utf-8')
        )
    else:
        markdown_path = None
    
    # 4. 保存图片（如果存在）
    if parse_result.get("images"):
        for img_info in parse_result["images"]:
            img_path = f"{image_folder_path}{img_info['filename']}"
            # 上传图片文件
            # ...
    else:
        image_folder_path = None
    
    return content_json_path
```

---

## 📊 路径字段使用场景

| 字段 | 使用场景 | 查询频率 | 是否必需 |
|-----|---------|---------|---------|
| `content_json_path` | 获取解析后的结构化数据 | 高 | ✅ 必需 |
| `markdown_path` | 显示 Markdown 格式内容 | 中 | ⚪ 可选 |
| `image_folder_path` | 下载或显示图片 | 低 | ⚪ 可选 |

---

## ✅ 总结

### 路径字段设计

1. **`content_json_path`**（必需）
   - 主 JSON 文件路径
   - 包含所有解析结果的结构化数据
   - 最常用的路径

2. **`markdown_path`**（可选）
   - Markdown 文件路径
   - 如果解析器生成了独立的 Markdown 文件
   - 便于直接查看和编辑

3. **`image_folder_path`**（可选）
   - 图片文件夹路径
   - 包含从 PDF 提取的所有图片
   - 便于批量下载和展示

### 优势

- ✅ 路径清晰，职责明确
- ✅ 支持灵活的文件组织方式
- ✅ 便于后续扩展（如添加表格文件夹路径）
- ✅ 查询效率高（直接路径访问）

---

*最后更新: 2026-01-16*
