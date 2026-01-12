# CNINFO 定期报告批量下载工具

一个功能强大的 Python 爬虫脚本，用于从巨潮资讯网（CNINFO）批量下载上市公司定期报告（年报、季报、半年报）。

## 主要特性

### 核心功能
- **批量下载**：支持从CSV文件批量导入任务，一次性下载多家公司的多个报告
- **智能分类**：自动识别交易所（深交所/上交所/北交所），按目录结构分类存储
- **断点续传**：支持中断后继续下载，避免重复抓取
- **多进程加速**：支持多进程并行下载，显著提升下载效率

### 智能机制
- **多重 orgId 获取策略**：
  1. 本地缓存优先
  2. 规则构造（快速）
  3. 搜索API查询
  4. searchkey查询（兜底）
  5. HTML页面解析（最终兜底）

- **股票代码变更处理**：自动检测和处理公司代码变更（如重组、借壳上市等）
- **公司名称变更记录**：当API返回的公司名与输入不一致时，自动记录到 `name_changes.csv`
- **重复下载避免**：可指定旧PDF目录，自动跳过已下载的文件

### 可靠性保障
- **智能重试**：HTTP 403/502/503/504 自动重试，带指数退避
- **404 链接刷新**：遇到 404 时自动重新获取最新下载链接
- **错误日志**：滚动记录所有错误到 `error.log`，可实时监控
- **失败记录**：将下载失败的任务记录到CSV文件，便于重试

## 系统要求

### Python 版本
- Python 3.7+

### 依赖库
```bash
pip install requests beautifulsoup4 tqdm
```

### 可选依赖
```bash
pip install sqlite3  # 推荐：高性能状态管理（Python 3.x通常自带）
```

## 安装

1. 克隆或下载本项目
2. 安装依赖：
```bash
pip install -r requirements.txt
```

如果没有 `requirements.txt`，手动安装：
```bash
pip install requests beautifulsoup4 tqdm
```

## 使用方法

### 基本用法

#### 1. 准备输入CSV文件

创建一个CSV文件（如 `tasks.csv`），包含以下列：

```csv
code,name,year,quarter
000001,平安银行,2023,Q1
000001,平安银行,2023,Q2
000002,万科A,2023,Q1
600519,贵州茅台,2023,Q4
```

**字段说明**：
- `code`: 股票代码（6位数字，如 000001）
- `name`: 公司简称（用于辅助查询和日志记录）
- `year`: 报告年份（如 2023）
- `quarter`: 报告季度（Q1/Q2/Q3/Q4）

**编码要求**：
- Windows系统：推荐使用 GBK 或 UTF-8-sig 编码
- Linux/Mac系统：推荐使用 UTF-8 编码
- 脚本会自动尝试多种编码

#### 2. 运行脚本

**顺序下载模式**（适合小批量任务）：
```bash
python cninfo_dual_fetch_Final（latest_new）.py \
    --input tasks.csv \
    --out ./reports \
    --fail failed.csv
```

**多进程并行模式**（推荐，适合大批量任务）：
```bash
python cninfo_dual_fetch_Final（latest_new）.py \
    --input tasks.csv \
    --out ./reports \
    --fail failed.csv \
    --workers 4
```

**避免重复下载**（指定旧PDF目录）：
```bash
python cninfo_dual_fetch_Final（latest_new）.py \
    --input tasks.csv \
    --out ./reports_new \
    --fail failed.csv \
    --workers 4 \
    --old-pdf-dir ./reports_old
```

**调试模式**（输出详细日志）：
```bash
python cninfo_dual_fetch_Final（latest_new）.py \
    --input tasks.csv \
    --out ./reports \
    --fail failed.csv \
    --debug
```

**实时监控日志**（仅顺序模式）：
```bash
python cninfo_dual_fetch_Final（latest_new）.py \
    --input tasks.csv \
    --out ./reports \
    --fail failed.csv \
    --watch-log
```

### 参数说明

| 参数 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `--input` | ✓ | 输入CSV文件路径 | `tasks.csv` |
| `--out` | ✓ | PDF输出根目录 | `./reports` |
| `--fail` | ✓ | 失败记录CSV文件路径 | `failed.csv` |
| `--workers` | × | 并行进程数（0=顺序模式，推荐4-8） | `4` |
| `--old-pdf-dir` | × | 旧PDF目录路径（避免重复下载） | `./old_reports` |
| `--watch-log` | × | 实时显示error.log（仅顺序模式） | - |
| `--debug` | × | 调试模式（输出详细日志） | - |

### 输出结构

```
reports/                      # 输出根目录
├── SZ/                       # 深圳交易所
│   ├── 000001/              # 股票代码
│   │   ├── 2023/            # 年份
│   │   │   ├── 000001_2023_Q1_25-04-2023.pdf
│   │   │   ├── 000001_2023_Q2_28-08-2023.pdf
│   │   │   └── ...
│   ├── 000002/
│   └── ...
├── SH/                       # 上海交易所
│   ├── 600519/
│   └── ...
├── BJ/                       # 北京交易所
│   ├── 430001/
│   └── ...
└── checkpoint.json           # 断点续传记录
```

**文件命名规则**：
- 格式：`{股票代码}_{年份}_{季度}_{发布日期}.pdf`
- 示例：`000001_2023_Q1_25-04-2023.pdf`

## 核心功能详解

### 1. 多重 orgId 获取策略

CNINFO API 需要公司的 `orgId`（组织ID）才能准确查询。脚本采用多重策略确保成功：

```
优先级 1: 本地缓存（orgid_cache.json）
    ↓ 失败
优先级 2: 规则构造（如：gssz0000001）
    ↓ 失败
优先级 3: 搜索API查询（/topSearch/query）
    ↓ 失败
优先级 4: searchkey查询（用公司名搜索）
    ↓ 失败
优先级 5: HTML页面解析（最终兜底）
```

### 2. 股票代码变更处理

自动检测并处理以下场景：
- 公司重组导致的代码变更
- 借壳上市
- 退市重新上市

**检测机制**：
- 分析公告中出现的股票代码统计
- 比较公司名称相似度（避免合并重组误判）
- 自动缓存代码变更关系到 `code_change_cache.json`

**示例**：
```
[代码变更检测] orgId=gssz0000001: 请求代码 000001 -> 实际代码 001979
```

### 3. 公告筛选机制

**按类别过滤**（优先）：
- Q1: `category_yjdbg_szsh` (一季度报告)
- Q2: `category_bndbg_szsh` (半年度报告)
- Q3: `category_sjdbg_szsh` (三季度报告)
- Q4: `category_ndbg_szsh` (年度报告)

**标题正则匹配**（兜底）：
- 自动识别 "2023年一季度报告"、"2023年半年度报告" 等各种格式
- 排除摘要、英文版等

**时间窗口**：
- Q1-Q3: 当年全年（如 2023-01-01~2023-12-31）
- Q4: 跨年双窗口（如 2023-10-01~2023-12-31 + 2024-01-01~2024-06-30）

### 4. 多进程并行下载

**性能提升**：
- 4进程：约 3-4倍速度提升
- 8进程：约 5-7倍速度提升

**状态管理**：
- **SQLite模式**（推荐）：高性能、无文件锁冲突
- **JSON模式**（兜底）：跨进程锁保护，性能较低

**进程安全**：
- 共享锁保护所有文件操作
- 原子性更新checkpoint
- 防止重复下载

### 5. 错误处理与重试

**HTTP状态码重试**：
- 403/502/503/504 自动重试（最多3次）
- 指数退避（1秒 → 2秒 → 4秒）

**404 智能刷新**：
```python
# 遇到404时自动重新查询最新链接
def refresh_fn():
    anns = fetch_anns_by_category(...)
    best = pick_latest(anns, ...)
    return new_pdf_url
```

**请求速率控制**：
- 组合间睡眠：2-3秒随机
- 同股票间隔：1秒
- 避免触发反爬虫机制

## 配置说明

### 代理设置

如需使用代理，修改脚本中的 `PROXIES` 变量：

```python
# 默认无代理
PROXIES = None

# 启用代理
PROXIES = {
    "http": "http://ip:port",
    "https": "http://ip:port"
}
```

### 自定义Headers

脚本已内置浏览器级别的Headers，通常无需修改。如需自定义：

```python
HEADERS_API = {
    "User-Agent": "...",
    "Accept": "...",
    # ...
}
```

### 排除关键词

默认排除包含以下关键词的公告：

```python
EXCLUDE_IN_TITLE = ("摘要", "英文", "英文版")
```

可根据需要添加其他排除词。

## 状态文件说明

脚本运行期间会生成以下状态文件：

| 文件 | 位置 | 说明 |
|------|------|------|
| `checkpoint.json` | 输出目录 | 记录已成功下载的任务，用于断点续传 |
| `orgid_cache.json` | 脚本目录 | 缓存股票代码→orgId的映射，加速查询 |
| `code_change_cache.json` | 脚本目录 | 记录股票代码变更关系 |
| `name_changes.csv` | 脚本目录 | 记录公司名称不一致的情况 |
| `error.log` | 脚本目录 | 详细错误日志 |
| `failed.csv` | 用户指定 | 下载失败的任务列表（可重试） |

### 断点续传

如需重新开始，删除对应的 `checkpoint.json` 文件：

```bash
rm reports/checkpoint.json
```

如需重试失败任务，使用 `failed.csv` 作为新的输入：

```bash
python cninfo_dual_fetch_Final（latest_new）.py \
    --input failed.csv \
    --out ./reports \
    --fail failed_retry.csv
```

## 常见问题

### 1. CSV读取失败（编码问题）

**错误信息**：
```
❌ 无法读取 CSV 文件，尝试了编码: ['utf-8-sig', 'utf-8', 'gbk', ...]
```

**解决方案**：
- Windows：用记事本打开CSV，另存为时选择 "UTF-8" 或 "GBK" 编码
- Mac/Linux：确保CSV文件是UTF-8编码
- Excel：保存时选择 "CSV UTF-8 (逗号分隔)"

### 2. 未找到公告

**可能原因**：
- 该季度报告未发布（如未到披露时间）
- 公司代码或名称错误
- 公司已退市或重组

**排查方法**：
1. 检查 `error.log` 查看详细错误
2. 手动访问 [CNINFO网站](https://www.cninfo.com.cn/) 确认报告是否存在
3. 使用 `--debug` 参数运行，查看详细查询过程

### 3. 下载速度慢

**优化建议**：
- 使用多进程模式：`--workers 4`（或更高，如8）
- 检查网络连接
- 考虑使用代理（如有）

### 4. 多进程模式下文件锁冲突

**现象**：
```
⚠️  保存JSON文件失败（checkpoint.json）: [WinError 32] 另一个程序正在使用...
```

**解决方案**：
- 安装 SQLite（Python 3.x通常自带）
- 脚本会自动检测并使用SQLite模式（高性能、无锁冲突）
- 如看到 "✅ 使用 SQLite 状态管理" 则说明已启用

### 5. orgId 获取失败

**现象**：
```
[orgId] 所有方法均失败
未获得公告列表
```

**解决方案**：
- 检查公司名称是否正确（与CNINFO网站一致）
- 检查股票代码是否正确
- 尝试手动访问CNINFO网站，确认公司是否存在
- 使用 `--debug` 查看详细查询过程

### 6. SSL证书验证错误

**错误信息**：
```
SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**解决方案**：
```bash
# Mac系统
cd "/Applications/Python 3.x/Install Certificates.command"

# 或在脚本中临时禁用SSL验证（不推荐）
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
```

## 交易所识别规则

| 股票代码前缀 | 交易所 | 目录 | API参数 | stock后缀 |
|------------|--------|------|---------|----------|
| 688xxx | 科创板（上海） | SH | sse | .SH |
| 6xxxxx | 上海主板 | SH | sse | .SH |
| 300xxx, 301xxx | 创业板（深圳） | SZ | szse | .SZ |
| 000xxx, 001xxx, 002xxx, 003xxx | 深圳主板/中小板 | SZ | szse | .SZ |
| 8xxxxx, 43xxx, 83xxx | 北京交易所 | BJ | szse | .BJ |

## 技术细节

### 关键API接口

1. **历史公告查询API**：
   - URL: `https://www.cninfo.com.cn/new/hisAnnouncement/query`
   - 方法: POST
   - 参数: stock, column, category, seDate, pageNum, pageSize

2. **搜索API**：
   - URL: `https://www.cninfo.com.cn/new/information/topSearch/query`
   - 方法: POST
   - 参数: keyWord

3. **PDF下载**：
   - URL: `https://static.cninfo.com.cn/{adjunctUrl}`
   - 方法: GET
   - 验证: 检查响应头5字节是否为 `%PDF-`

### 会话管理

```python
# 建立会话，获取 JSESSIONID Cookie
session.get("https://www.cninfo.com.cn/")

# 后续请求自动携带Cookie
session.post(CNINFO_API, data=payload)
```

### 文件命名与路径

```python
# 规范化代码（补零）
code = "1" -> "000001"

# 检测交易所
detect_exchange("000001") -> ("SZ", "szse", "SZ")

# 构建路径
path = f"{out_root}/{exch_dir}/{code}/{year}/{code}_{year}_{quarter}_{date}.pdf"
# 示例: reports/SZ/000001/2023/000001_2023_Q1_25-04-2023.pdf
```

## 性能优化建议

1. **使用多进程**：
   - 小批量（<100个任务）：顺序模式即可
   - 中批量（100-500）：4-6进程
   - 大批量（>500）：6-8进程

2. **指定旧PDF目录**：
   - 避免重复下载已有文件
   - 显著减少API请求次数

3. **分批下载**：
   - 将大任务拆分为多个小批次
   - 每批次300-500个任务
   - 便于管理和错误恢复

4. **定期清理缓存**：
   - `orgid_cache.json` 可以长期保留（加速查询）
   - `checkpoint.json` 任务完成后可删除
   - `error.log` 定期归档

## 注意事项

1. **合法使用**：
   - 仅用于学习和研究目的
   - 遵守CNINFO网站的使用条款
   - 不要过度频繁请求（已内置速率限制）

2. **数据准确性**：
   - 脚本优先选择最新发布的公告
   - 如有多个版本（如修订版），下载最新时间戳的版本
   - 建议定期对比CNINFO网站确认数据完整性

3. **网络环境**：
   - 需要稳定的网络连接
   - 大批量下载建议在网络空闲时段进行
   - 考虑使用企业网络或高速网络

4. **磁盘空间**：
   - 每份年报约 2-10 MB
   - 每份季报约 1-5 MB
   - 预留足够磁盘空间（估算：任务数 × 5 MB）

## 开发与扩展

### 添加新的公告类型

修改 `CATEGORY_MAP` 字典：

```python
CATEGORY_MAP = {
    "Q1": "category_yjdbg_szsh;",
    "Q2": "category_bndbg_szsh;",
    "Q3": "category_sjdbg_szsh;",
    "Q4": "category_ndbg_szsh;",
    "XX": "category_xxxxx_szsh;",  # 新类型
}
```

### 自定义下载逻辑

主要函数入口：

```python
# 单任务处理（可扩展）
def process_single_task(task_data) -> Tuple[bool, Optional[Tuple]]:
    # 自定义逻辑
    pass

# 多进程入口
def run_multiprocessing(...):
    pass

# 顺序模式入口
def run(...):
    pass
```

### 日志级别

```python
# 设置为DEBUG级别查看详细日志
logger.setLevel(logging.DEBUG)

# 或使用 --debug 参数
```

## 更新日志

### 最新版本特性
- ✅ 支持多进程并行下载
- ✅ SQLite状态管理（高性能、无锁冲突）
- ✅ 股票代码变更自动检测
- ✅ 旧PDF目录检查（避免重复下载）
- ✅ 多重orgId获取策略
- ✅ 类别过滤 + 标题正则双重筛选
- ✅ Q4跨年时间窗口支持
- ✅ 404智能链接刷新
- ✅ Windows/Mac/Linux多平台兼容

## 许可证

本项目仅供学习和研究使用。请遵守相关法律法规和网站使用条款。

## 贡献

欢迎提交Issue和Pull Request。

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 GitHub Issue
- 邮件联系（如有）

---

**免责声明**：本工具仅供学习和研究使用。使用者应当遵守《中华人民共和国网络安全法》等相关法律法规，不得用于任何商业目的或非法用途。因使用本工具产生的任何法律责任由使用者自行承担。
