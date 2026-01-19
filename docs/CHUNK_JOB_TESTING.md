# 文本分块作业测试指南

## 测试方式

### 方式1：通过 Dagster UI 测试（推荐）

1. **启动 Dagster UI**：
   ```bash
   bash scripts/start_dagster.sh
   ```

2. **访问 UI**：
   打开浏览器访问：http://localhost:3000

3. **查找分块作业**：
   - 在 Jobs 列表中查找 `chunk_documents_job` 或 `chunk_documents_batch_job`
   - 点击作业名称进入详情页

4. **手动触发**：
   - 点击右上角 "Launch Run" 按钮
   - 配置参数（可选）：
     ```yaml
     ops:
       scan_parsed_documents_op:
         config:
           batch_size: 2
           limit: 5
           # market: "a_share"  # 可选：过滤市场
           # doc_type: "quarterly_report"  # 可选：过滤文档类型
       chunk_documents_op:
         config:
           force_rechunk: false  # 是否强制重新分块
     ```
   - 点击 "Launch" 执行

5. **查看结果**：
   - 在 "Runs" 标签页查看运行历史
   - 点击运行记录查看详细日志
   - 查看每个步骤的输出结果

### 方式2：通过命令行测试

```bash
cd /Users/han/PycharmProjects/FinNet
export PYTHONPATH=".:$PYTHONPATH"

# 执行分块作业
dagster job execute \
  -j chunk_documents_job \
  -m src.processing.compute.dagster \
  --config '{
    "ops": {
      "scan_parsed_documents_op": {
        "config": {
          "batch_size": 2,
          "limit": 5
        }
      },
      "chunk_documents_op": {
        "config": {
          "force_rechunk": false
        }
      }
    }
  }'
```

### 方式3：通过 Python 脚本测试

```bash
# 直接测试分块服务（不依赖 Dagster）
python3 examples/test_chunk_job_simple.py

# 测试 Dagster 作业（需要 Dagster 环境）
python3 examples/test_chunk_job.py
```

### 方式4：在 Python 中直接调用

```python
from src.processing.text import get_text_chunker
import uuid

# 创建分块服务
chunker = get_text_chunker()

# 执行分块（替换为实际的 document_id）
document_id = uuid.UUID("your-document-id-here")
result = chunker.chunk_document(document_id)

if result["success"]:
    print(f"✅ 分块成功！")
    print(f"  分块数量: {result['chunks_count']}")
    print(f"  Structure 路径: {result['structure_path']}")
    print(f"  Chunks 路径: {result['chunks_path']}")
else:
    print(f"❌ 分块失败: {result['error_message']}")
```

## 测试前准备

### 1. 确保有已解析的文档

分块作业需要已解析的文档（有 markdown_path）。如果没有，先运行解析作业：

```bash
# 通过 Dagster UI 运行 parse_pdf_job
# 或通过命令行：
dagster job execute -j parse_pdf_job -m src.processing.compute.dagster
```

### 2. 检查数据库连接

确保 PostgreSQL 数据库正在运行：

```bash
# 检查数据库连接
python3 scripts/check_database.py
```

### 3. 检查 MinIO 连接

确保 MinIO 服务正在运行：

```bash
# 检查 MinIO 连接
python3 scripts/check_minio_config.py
```

## 验证结果

### 1. 检查数据库记录

```python
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud

pg_client = get_postgres_client()
with pg_client.get_session() as session:
    # 查询分块记录
    chunks = crud.get_document_chunks(session, document_id)
    print(f"文档分块数量: {len(chunks)}")
    
    # 查询 ParsedDocument 记录
    parsed_doc = crud.get_latest_parsed_document(session, document_id)
    if parsed_doc:
        print(f"Structure 路径: {parsed_doc.structure_json_path}")
        print(f"Chunks 路径: {parsed_doc.chunks_json_path}")
        print(f"分块数量: {parsed_doc.chunks_count}")
```

### 2. 检查 Silver 层文件

```python
from src.storage.object_store.minio_client import MinIOClient

minio_client = MinIOClient()

# 检查 structure.json
if parsed_doc.structure_json_path:
    exists = minio_client.file_exists(parsed_doc.structure_json_path)
    print(f"Structure JSON 存在: {exists}")

# 检查 chunks.json
if parsed_doc.chunks_json_path:
    exists = minio_client.file_exists(parsed_doc.chunks_json_path)
    print(f"Chunks JSON 存在: {exists}")
```

## 常见问题

### 1. 没有找到待分块的文档

**原因**：没有已解析的文档，或所有文档都已分块

**解决**：
- 先运行解析作业生成 Markdown 文件
- 或设置 `force_rechunk: true` 强制重新分块

### 2. Markdown 文件不存在

**原因**：ParsedDocument 记录中的 markdown_path 指向的文件不存在

**解决**：
- 检查 MinIO 中是否存在该文件
- 重新运行解析作业

### 3. 分块失败

**原因**：可能是 Markdown 格式问题、文件编码问题等

**解决**：
- 查看详细错误日志
- 检查 Markdown 文件内容
- 确保文件编码为 UTF-8

## 下一步

分块完成后，可以：
1. 查看分块结果（数据库和 Silver 层）
2. 实现向量化服务（Embedding）
3. 实现 RAG 检索服务
