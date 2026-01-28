# Neo4j 图结构迁移指南

**日期**: 2026-01-28  
**变更**: 从两层结构迁移到三层结构

---

## 📋 变更说明

### 旧图结构（V1）

```
Document (文档节点)
  └── Chunk (分块节点)
      └── Chunk (子分块节点)
```

**关系**:
- `Chunk -[:BELONGS_TO]-> Document`
- `Chunk -[:HAS_CHILD]-> Chunk`

### 新图结构（V2）

```
Company (根节点，股票代码)
  └── Document (文档节点)
      └── Chunk (分块节点)
          └── Chunk (子分块节点)
```

**关系**:
- `Company -[:HAS_DOCUMENT]-> Document` 🆕
- `Chunk -[:BELONGS_TO]-> Document`
- `Chunk -[:HAS_CHILD]-> Chunk`

---

## 🔍 检查是否需要迁移

运行统计命令检查当前图结构：

```bash
python scripts/migrate_neo4j_graph.py --stats
```

**判断标准**:
- 如果 `Company 节点: 0` 且 `Document 节点 > 0` → **需要迁移**
- 如果 `Company 节点 > 0` → **已是最新版本，无需迁移**
- 如果所有节点都是 0 → **数据库为空，无需迁移**

---

## 🚀 迁移方案

### 方案1：清空重建（推荐）⭐

**优点**:
- ✅ 简单快速
- ✅ 确保数据一致性
- ✅ 自动创建所有约束和索引

**缺点**:
- ❌ 会删除所有现有数据
- ❌ 需要重新构建图

**适用场景**:
- 开发/测试环境
- 数据可以重新生成
- 需要确保数据完全一致

**步骤**:

```bash
# 1. 查看当前数据统计
python scripts/migrate_neo4j_graph.py --stats

# 2. 试运行（查看将执行的操作）
python scripts/migrate_neo4j_graph.py --clear-rebuild --dry-run

# 3. 执行迁移
python scripts/migrate_neo4j_graph.py --clear-rebuild
```

**迁移过程**:
1. 清空 Neo4j 数据库（删除所有节点和关系）
2. 从 PostgreSQL 查询所有文档
3. 重新构建图结构（自动创建 Company 节点和关系）

---

### 方案2：数据迁移（保留现有数据）

**优点**:
- ✅ 保留现有数据
- ✅ 不需要重新构建所有分块

**缺点**:
- ⚠️ 需要确保 Document 节点有 `stock_code` 属性
- ⚠️ 可能遗漏某些数据

**适用场景**:
- 生产环境，需要保留数据
- Document 节点已有完整的 `stock_code` 和 `company_name` 属性

**步骤**:

```bash
# 1. 查看当前数据统计
python scripts/migrate_neo4j_graph.py --stats

# 2. 试运行（查看将执行的操作）
python scripts/migrate_neo4j_graph.py --migrate-data --dry-run

# 3. 执行迁移
python scripts/migrate_neo4j_graph.py --migrate-data
```

**迁移过程**:
1. 查询所有 Document 节点，提取唯一的 `stock_code`
2. 为每个 `stock_code` 创建 Company 节点
3. 创建 `Company -[:HAS_DOCUMENT]-> Document` 关系

---

## 📝 手动迁移步骤（高级）

如果自动迁移脚本不适用，可以手动执行：

### 1. 创建 Company 节点

```cypher
// 查询所有唯一的股票代码
MATCH (d:Document)
WITH DISTINCT d.stock_code as code, d.company_name as name
MERGE (c:Company {code: code})
ON CREATE SET c.name = name
ON MATCH SET c.name = name
RETURN c
```

### 2. 创建 Company -> Document 关系

```cypher
MATCH (c:Company), (d:Document {stock_code: c.code})
MERGE (c)-[r:HAS_DOCUMENT]->(d)
RETURN count(r) as created
```

### 3. 创建约束和索引

```cypher
// Company 节点约束
CREATE CONSTRAINT company_code IF NOT EXISTS 
FOR (c:Company) REQUIRE c.code IS UNIQUE;

// Company 节点索引
CREATE INDEX company_name IF NOT EXISTS 
FOR (c:Company) ON (c.name);
```

---

## ✅ 验证迁移结果

迁移完成后，验证图结构：

```bash
# 查看统计信息
python scripts/migrate_neo4j_graph.py --stats

# 或使用清理脚本查看
python scripts/clear_neo4j.py --stats
```

**预期结果**:
- ✅ `Company 节点 > 0`
- ✅ `HAS_DOCUMENT 关系 > 0`
- ✅ 每个 Document 节点都有对应的 Company 节点

**验证查询**:

```cypher
// 检查是否有孤立的 Document 节点（没有 Company 父节点）
MATCH (d:Document)
WHERE NOT (d)<-[:HAS_DOCUMENT]-()
RETURN count(d) as orphan_documents
// 应该返回 0

// 检查每个 Company 的文档数量
MATCH (c:Company)-[:HAS_DOCUMENT]->(d:Document)
RETURN c.code, c.name, count(d) as document_count
ORDER BY document_count DESC
LIMIT 10
```

---

## 🔄 回滚方案

如果需要回滚到旧结构（不推荐）：

```bash
# 删除所有 Company 节点和 HAS_DOCUMENT 关系
python scripts/clear_neo4j.py --clear --label Company --confirm
```

**注意**: 回滚后图结构会回到两层，但不会影响 Document 和 Chunk 节点。

---

## 📚 相关文件

- `scripts/migrate_neo4j_graph.py` - 迁移脚本
- `scripts/clear_neo4j.py` - 数据清理脚本
- `src/storage/graph/neo4j_client.py` - Neo4j 客户端
- `src/processing/graph/graph_builder.py` - 图构建服务
- `docs/NEO4J_GRAPH_STRUCTURE.md` - 图结构说明文档

---

## ⚠️ 注意事项

1. **备份数据**: 迁移前建议备份 Neo4j 数据（如果使用 Neo4j 企业版）
2. **测试环境**: 建议先在测试环境验证迁移脚本
3. **数据一致性**: 确保 PostgreSQL 中的 Document 表有完整的 `stock_code` 和 `company_name` 字段
4. **性能影响**: 大量数据迁移可能需要较长时间，建议在低峰期执行

---

## 🆘 故障排查

### 问题1：迁移后 Company 节点数量为 0

**原因**: Document 节点缺少 `stock_code` 属性

**解决**:
```cypher
// 检查 Document 节点是否有 stock_code
MATCH (d:Document)
WHERE d.stock_code IS NULL
RETURN count(d) as missing_stock_code
```

### 问题2：迁移后部分 Document 没有 Company 父节点

**原因**: Document 的 `stock_code` 与 Company 的 `code` 不匹配

**解决**:
```cypher
// 查找孤立的 Document
MATCH (d:Document)
WHERE NOT (d)<-[:HAS_DOCUMENT]-()
RETURN d.stock_code, d.company_name, d.id
LIMIT 10
```

### 问题3：迁移脚本执行失败

**解决**:
1. 检查 Neo4j 连接是否正常
2. 检查是否有足够的权限
3. 查看日志文件获取详细错误信息
