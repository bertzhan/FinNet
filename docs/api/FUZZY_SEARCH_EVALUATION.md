# 公司名称模糊搜索逻辑评估

## 当前实现分析

### 当前查询逻辑（第498-502行）

```python
should_clauses = [
    # 精确匹配
    {"term": {"company_name": company_name_query}},
    # 前缀匹配（如 "平安" 匹配 "平安银行"）
    {"prefix": {"company_name": company_name_query}},
    # 通配符匹配（支持中间匹配，如 "*平安*"）
    {"wildcard": {"company_name": f"*{company_name_query}*"}},
]

# 如果公司名称包含多个字符，也尝试部分匹配
if len(company_name_query) > 2:
    # 尝试前两个字符的前缀匹配
    should_clauses.append({"prefix": {"company_name": company_name_query[:2]}})
```

## 评估结果

### ✅ 优点

1. **覆盖多种场景**
   - 精确匹配：`term` 查询
   - 前缀匹配：`prefix` 查询
   - 中间匹配：`wildcard` 查询

2. **灵活性好**
   - 支持完整公司名称搜索
   - 支持部分名称搜索（如"平安"匹配"平安银行"）
   - 支持中间关键词搜索

3. **使用 should 子句**
   - 满足任一条件即可，不会因为一个条件失败而整体失败

### ⚠️ 潜在问题

#### 1. **查询重复和冗余**

**问题**：
- `prefix` 查询和 `wildcard` 查询有重叠
- 例如：查询"平安银行"时，`prefix` 和 `wildcard` 都会匹配相同的文档
- 第506-508行的逻辑与前面的 `prefix` 查询有重叠

**示例**：
```python
# 查询: "平安银行"
# prefix: "平安银行"  → 匹配 "平安银行股份有限公司"
# wildcard: "*平安银行*" → 也匹配 "平安银行股份有限公司"
# 两者匹配结果相同，造成冗余
```

#### 2. **性能问题**

**问题**：
- `wildcard` 查询以 `*` 开头时性能较差
- 需要扫描所有文档，无法使用索引优化
- 对于 keyword 类型字段，wildcard 查询效率较低

**影响**：
- 数据量大时查询可能变慢
- 特别是 `*{query}*` 这种模式

#### 3. **评分不合理**

**问题**：
- 所有查询条件没有设置 boost（权重）
- 精确匹配和模糊匹配的评分相同
- 精确匹配应该获得更高的评分

**示例**：
```python
# 查询: "平安银行"
# term 匹配 "平安银行" → 评分: 1.0
# wildcard 匹配 "中国平安银行" → 评分: 1.0
# 两者评分相同，但精确匹配应该更高
```

#### 4. **逻辑冗余**

**问题**：
- 第506-508行的逻辑与前面的 `prefix` 查询有重叠
- 如果查询是"平安银行"，前面的 `prefix` 已经会匹配，不需要再添加前两个字符的前缀

## 改进建议

### 方案1: 优化查询逻辑（推荐）

```python
# 构建多个查询条件（使用 should，满足任一即可）
should_clauses = []

# 1. 精确匹配（最高优先级，boost=3.0）
should_clauses.append({
    "term": {
        "company_name": {
            "value": company_name_query,
            "boost": 3.0  # 精确匹配权重最高
        }
    }
})

# 2. 前缀匹配（中等优先级，boost=2.0）
# 只有当查询长度 >= 2 时才使用前缀匹配
if len(company_name_query) >= 2:
    should_clauses.append({
        "prefix": {
            "company_name": {
                "value": company_name_query,
                "boost": 2.0  # 前缀匹配权重中等
            }
        }
    })

# 3. 通配符匹配（最低优先级，boost=1.0）
# 只有当查询长度 >= 2 时才使用通配符匹配
# 注意：避免以 * 开头，改为后缀通配符以提高性能
if len(company_name_query) >= 2:
    # 使用后缀通配符（性能更好）
    should_clauses.append({
        "wildcard": {
            "company_name": {
                "value": f"{company_name_query}*",  # 改为后缀通配符
                "boost": 1.0  # 通配符匹配权重最低
            }
        }
    })
    
    # 如果需要支持中间匹配，使用单独的查询（性能较差，但更灵活）
    # 注意：这个查询性能较差，建议只在必要时使用
    if len(company_name_query) >= 3:  # 只对较长的查询使用
        should_clauses.append({
            "wildcard": {
                "company_name": {
                    "value": f"*{company_name_query}*",
                    "boost": 0.5  # 中间匹配权重最低
                }
            }
        })

es_query = {
    "bool": {
        "should": should_clauses,
        "minimum_should_match": 1
    }
}
```

### 方案2: 使用 match_phrase_prefix（更优雅）

```python
# 使用 match_phrase_prefix，更适合中文搜索
es_query = {
    "bool": {
        "should": [
            # 精确匹配（最高优先级）
            {
                "term": {
                    "company_name": {
                        "value": company_name_query,
                        "boost": 3.0
                    }
                }
            },
            # 短语前缀匹配（适合中文）
            {
                "match_phrase_prefix": {
                    "company_name": {
                        "query": company_name_query,
                        "max_expansions": 50,  # 限制扩展数量
                        "boost": 2.0
                    }
                }
            },
            # 通配符匹配（仅后缀，性能更好）
            {
                "wildcard": {
                    "company_name": {
                        "value": f"{company_name_query}*",
                        "boost": 1.0
                    }
                }
            }
        ],
        "minimum_should_match": 1
    }
}
```

**注意**：`match_phrase_prefix` 主要用于 text 类型字段，对于 keyword 类型可能不适用。

### 方案3: 简化版本（性能优先）

```python
# 简化版本，优先性能
should_clauses = []

# 1. 精确匹配
should_clauses.append({
    "term": {
        "company_name": {
            "value": company_name_query,
            "boost": 3.0
        }
    }
})

# 2. 前缀匹配（性能好，推荐）
if len(company_name_query) >= 2:
    should_clauses.append({
        "prefix": {
            "company_name": {
                "value": company_name_query,
                "boost": 2.0
            }
        }
    })

# 3. 后缀通配符（性能较好）
if len(company_name_query) >= 2:
    should_clauses.append({
        "wildcard": {
            "company_name": {
                "value": f"{company_name_query}*",
                "boost": 1.0
            }
        }
    })

# 注意：移除了中间匹配（*query*），因为性能较差
# 如果需要中间匹配，可以考虑使用 ngram 分析器或单独处理

es_query = {
    "bool": {
        "should": should_clauses,
        "minimum_should_match": 1
    }
}
```

## 性能对比

| 查询类型 | 性能 | 适用场景 | 推荐度 |
|---------|------|---------|--------|
| `term` | ⭐⭐⭐⭐⭐ | 精确匹配 | ✅ 推荐 |
| `prefix` | ⭐⭐⭐⭐ | 前缀匹配 | ✅ 推荐 |
| `wildcard` (后缀) | ⭐⭐⭐ | 后缀匹配 | ⚠️ 可用 |
| `wildcard` (中间) | ⭐⭐ | 中间匹配 | ❌ 不推荐（性能差）|

## 推荐方案

**推荐使用方案3（简化版本）**，原因：

1. **性能优先**：避免使用性能较差的中间通配符查询
2. **逻辑清晰**：移除冗余查询条件
3. **评分合理**：使用 boost 让精确匹配优先
4. **满足需求**：覆盖大部分实际使用场景

## 实际测试建议

建议测试以下场景：

1. **精确匹配**：`"平安银行"` → 应该返回 `000001`
2. **前缀匹配**：`"平安"` → 应该返回 `000001`（平安银行）
3. **部分匹配**：`"银行"` → 可能返回多个结果（需要投票）
4. **不存在**：`"不存在的公司"` → 应该返回空结果

## 总结

当前实现**基本合理**，但有以下改进空间：

1. ✅ **添加 boost 权重**：让精确匹配优先
2. ✅ **移除冗余查询**：删除第506-508行的重复逻辑
3. ✅ **优化通配符**：避免使用 `*query*`，改用 `query*`
4. ✅ **性能优化**：对于中间匹配，考虑使用其他方案（如 ngram）
