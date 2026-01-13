# CNINFO IPO招股说明书抓取工具

## 功能说明

本脚本用于从巨潮资讯网（CNINFO）自动抓取A股IPO招股说明书文件，支持PDF和HTML格式。

## 主要特点

1. **广泛的历史覆盖**
   - 支持40年时间跨度（1985-2025）
   - 涵盖早期HTML格式招股说明书（1990s）
   - 自动识别并处理PDF和HTML两种格式

2. **多格式支持**
   - **PDF格式**：现代IPO招股说明书（2000年后）
   - **HTML格式**：历史IPO招股说明书（1990s）
   - **自动转换**：HTML文件自动转换为纯文本格式
   - **编码修复**：自动修复中文编码（GB2312/GBK → UTF-8）

3. **多策略orgId获取**
   - 优先使用搜索API获取真实orgId（无需公司名）
   - 兜底使用HTML页面解析
   - 自动缓存orgId，避免重复查询

4. **智能过滤**
   - 使用关键词"招股说明书"精准搜索
   - 排除摘要、英文版、更正、补充等文件
   - 自动选择最新版本

5. **防反爬机制**
   - 保留原脚本所有防反爬功能
   - 自动重试（403/502/503/504状态码）
   - 随机延迟（2-3秒组合间睡眠）
   - Session管理（自动获取JSESSIONID）

6. **断点续传**
   - 支持断点续抓（checkpoint机制）
   - 缓存orgId，避免重复查询
   - 失败记录自动导出

7. **多进程支持**
   - 支持多进程并行下载（推荐4-8个进程）
   - 显著提升抓取效率

## 安装依赖

```bash
pip install requests beautifulsoup4 tqdm
```

## CSV文件格式

创建一个CSV文件（如`ipo_list.csv`），包含以下列：

```csv
code,name
688805,健信超导
688123,聚和材料
688XXX,公司名称
```

**注意**：
- 只需要两列：`code`（股票代码）和`name`（公司名称）
- 不需要year和quarter列（与定期报告抓取不同）

## 使用方法

### 顺序模式（单进程）

```bash
python3 cninfo_ipo_prospectus_fetcher.py \
  --input ipo_list.csv \
  --out ./ipo_downloads \
  --fail ./failed_ipo.csv
```

### 多进程模式（推荐）

```bash
python3 cninfo_ipo_prospectus_fetcher.py \
  --input ipo_list.csv \
  --out ./ipo_downloads \
  --fail ./failed_ipo.csv \
  --workers 4
```

### 调试模式

```bash
python3 cninfo_ipo_prospectus_fetcher.py \
  --input ipo_list.csv \
  --out ./ipo_downloads \
  --fail ./failed_ipo.csv \
  --debug
```

## 参数说明

- `--input`：输入CSV文件路径（必需）
- `--out`：输出根目录（必需）
- `--fail`：失败记录CSV文件路径（必需）
- `--workers`：并行进程数（0=顺序模式，推荐4-8）
- `--watch-log`：实时显示错误日志（仅顺序模式）
- `--debug`：调试模式，输出详细日志

## 输出结构

```
ipo_downloads/
├── SH/              # 上海证券交易所
│   └── 688805/
│       ├── 688805_2025_19-12-2025.pdf
│       └── 688805_2020_15-07-2020.pdf
├── SZ/              # 深圳证券交易所
│   └── 000012/
│       ├── 000012_1991_28-10-1991.html  # HTML格式（早期文档）
│       └── 000012_1991_28-10-1991.txt   # 自动生成的文本版本
└── BJ/              # 北京证券交易所
    └── 430XXX/
        └── 430XXX_2025_DD-MM-YYYY.pdf
```

## 文件格式

### PDF文件
- 现代IPO招股说明书（一般2000年后）
- 直接从CNINFO下载

### HTML文件
- 历史IPO招股说明书（1990s）
- 自动修复中文编码为UTF-8
- 自动生成同名.txt纯文本版本

## 文件命名规则

`{股票代码}_{年份}_{发布日期}.{扩展名}`

示例：
- PDF格式：`688805_2025_19-12-2025.pdf`
- HTML格式：`000012_1991_28-10-1991.html`
- 文本格式：`000012_1991_28-10-1991.txt`

**目录结构**：`交易所/代码/文件名`

## 缓存文件

脚本会在当前目录生成以下缓存文件：

- `checkpoint_ipo.json`：断点续传记录
- `orgid_cache_ipo.json`：orgId缓存
- `error_ipo.log`：错误日志

## 测试示例

### 现代IPO（PDF格式）

测试文件`test_recent_ipo.csv`：
```csv
code,name
688981,中芯集成
688599,天合光能
```

运行测试：
```bash
python3 cninfo_ipo_prospectus_fetcher.py \
  --input test_recent_ipo.csv \
  --out ./test_output \
  --fail ./test_fail.csv \
  --debug
```

### 历史IPO（HTML格式）

测试文件`test_000012.csv`：
```csv
code,name
000012,南方玻璃
```

运行测试：
```bash
python3 cninfo_ipo_prospectus_fetcher.py \
  --input test_000012.csv \
  --out ./test_output \
  --fail ./test_fail.csv \
  --debug
```

输出示例：
```
test_output/SZ/000012/
├── 000012_1991_28-10-1991.html  # HTML格式原文
└── 000012_1991_28-10-1991.txt   # 自动生成的文本版本
```

## 常见问题

### 1. 找不到招股说明书

可能原因：
- 公司尚未上市或未发布招股说明书
- 股票代码错误
- orgId获取失败

解决方法：
- 使用`--debug`模式查看详细日志
- 检查股票代码是否正确
- 手动访问巨潮网验证是否有招股说明书

### 2. 下载速度慢

解决方法：
- 使用多进程模式（`--workers 4-8`）
- 检查网络连接
- 避免高峰期使用

### 3. HTTP 403/503错误

原因：服务器反爬限制

解决方法：
- 脚本已内置自动重试机制
- 适当增加延迟时间（修改`INTER_COMBO_SLEEP_RANGE`）
- 使用代理（修改`PROXIES`配置）

### 4. HTML文件中文显示乱码

原因：浏览器未识别UTF-8编码

解决方法：
- 脚本已自动修复HTML charset声明
- 如仍有问题，手动在浏览器中选择UTF-8编码
- 使用自动生成的.txt文本文件

### 5. 早期公司找不到招股说明书

可能原因：
- 部分1980s后期IPO的HTML文件已从服务器移除（如万科000002）
- 1990年代早期的公司大部分可以找到（如南方玻璃000012）

解决方法：
- 使用`--debug`模式查看详细日志
- 检查error_ipo.log中的错误信息
- 1991年后的IPO成功率较高

## 与原版脚本的主要区别

1. **CSV格式**：只需`code`和`name`，不需要`year`和`quarter`
2. **搜索方法**：使用`searchkey="招股说明书"`精准搜索，而非category限制
3. **标题匹配**：匹配"招股说明书"而非季度报告，排除"提示性公告"、"意向书"等
4. **时间窗口**：查询40年（1985-2025），覆盖所有历史IPO
5. **目录结构**：`交易所/代码/`（移除年份目录层级）
6. **文件命名**：`{code}_{year}_{date}.{扩展名}`
7. **多格式支持**：
   - PDF格式：现代招股说明书
   - HTML格式：1990s历史招股说明书
   - 自动生成TXT文本版本
8. **编码处理**：自动修复GB2312/GBK编码为UTF-8，确保浏览器正确显示中文

## 技术细节

### orgId获取策略

1. **优先**：搜索API（`/new/information/topSearch/query`）
   - 直接用股票代码查询
   - 不需要公司名
   - 准确率高

2. **兜底**：HTML页面解析
   - 访问检索页
   - 解析详情链接中的orgId
   - 支持多种搜索关键词

### 防反爬机制

- Session管理（获取JSESSIONID Cookie）
- 自动重试（指数退避）
- 随机延迟
- User-Agent伪装
- Referer设置

### HTML格式处理

**下载流程**：
1. 检测文件格式（.html/.htm扩展名）
2. 下载HTML内容
3. 智能检测原始编码（GB2312/GBK/GB18030/UTF-8）
4. 修复HTML meta标签的charset声明为UTF-8
5. 保存UTF-8编码的HTML文件
6. 使用BeautifulSoup解析HTML
7. 清理和格式化文本内容
8. 生成同名.txt纯文本文件

**中文编码修复**：
```python
# 自动将GB2312/GBK编码声明替换为UTF-8
<meta charset="gb2312"> → <meta charset="UTF-8">
<meta http-equiv="Content-Type" content="text/html; charset=gb2312">
→ <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
```

**文本转换特性**：
- 移除HTML标签和样式
- 保留段落结构
- 去除重复行
- 添加文档头部信息
- UTF-8编码确保中文正确显示

## 版本信息

- 基于：cninfo_dual_fetch_Final（原版）
- 修改：IPO招股说明书专用版
- 更新日期：2025-12-24
- 主要更新：
  - v2.0 (2025-12-24): 添加HTML格式支持、中文编码修复、文本转换
  - v1.0 (2025-12-22): 初始版本

## 许可证

本工具仅供学习和研究使用，请遵守巨潮资讯网的使用条款。
