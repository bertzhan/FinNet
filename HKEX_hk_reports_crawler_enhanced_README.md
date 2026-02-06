# HKEX 港股报告爬虫（增强版）使用说明

## 一、程序简介

**HKEX_hk_reports_crawler_enhanced.py** 是一款面向**香港交易所披露易（HKEXnews）**的港股上市公司报告爬虫程序。程序可批量下载港股公司的**年报、中期报告、季度报告**等 PDF 文件，并支持股票列表获取、上市日期更新、下载日志记录等功能。

### 1.1 核心功能

| 功能 | 说明 |
|------|------|
| **报告下载** | 按股票列表、年份范围批量下载年报、中期报告、季度报告 PDF |
| **股票列表** | 从港交所/披露易获取证券列表，解析并筛选股本證券（主板/创业板） |
| **stockId 补全** | 列表缺失 stockId 时，通过披露易 partial.do 接口自动补全 |
| **上市日期更新** | 下载完成后可选通过 AKShare 更新公司上市日期到 CSV |
| **下载日志** | 支持 Excel/CSV 格式的详细下载日志，便于追溯与去重 |
| **多线程** | 可配置并发线程数（1–32），提高下载效率 |
| **限流与重试** | 自适应限流、HTTP 重试，降低被服务器拒绝的概率 |

### 1.2 增强特性

- **报告类型筛选**：仅下载真实财务报表（年报/中期/季度），排除通告、函件等非报表文件  
- **股票列表集成**：自动从香港交易所下载证券列表并解析，无需手动准备  
- **详细日志系统**：下载结果记录为 CSV 或 Excel，含文件名、URL、状态、原因等  
- **自动依赖检测**：启动时检测 `requests`、`pandas`、`openpyxl`、`akshare`、`beautifulsoup4`，缺失则提示安装  
- **stockId 补全与异动监测**：列表无 stockId 时自动补全；股票列表 JSON 变更超过阈值时生成告警快照  

---

## 二、环境要求

### 2.1 Python 版本

- 建议 **Python 3.8+**

### 2.2 依赖包

程序启动时会自动检测以下依赖，缺失会提示安装命令：

| 包名 | 用途 |
|------|------|
| `requests` | HTTP 请求 |
| `pandas` | 数据处理与 CSV/Excel |
| `openpyxl` | Excel 读写 |
| `akshare` | 上市日期等数据（东方财富接口） |
| `beautifulsoup4` | HTML 解析 |

安装示例（与项目内 `requirements.txt` 一致）：

```bash
pip install requests pandas openpyxl akshare beautifulsoup4
```

或：

```bash
pip install -r requirements.txt
```

---

## 三、运行方式概览

程序支持两种运行模式：

1. **交互模式**（默认）：不传 `--auto`/`--non-interactive` 时，按提示输入股票范围、年份范围、线程数等，适合单次手动运行。  
2. **非交互/定时模式**：使用 `--auto` 或 `--non-interactive`，并结合 `--config` 或命令行参数指定全部配置，适合脚本/定时任务。

---

## 四、命令行参数说明

在脚本所在目录执行：

```bash
python HKEX_hk_reports_crawler_enhanced.py [选项]
```

### 4.1 通用与配置文件

| 参数 | 说明 |
|------|------|
| `--config <路径>` | JSON 配置文件路径（相对/绝对），用于定时或非交互运行 |
| `--auto` | 非交互模式，使用配置文件或默认参数，不提示输入 |
| `--non-interactive` | 与 `--auto` 等价，兼容旧用法 |

### 4.2 公司与年份范围

| 参数 | 说明 |
|------|------|
| `--company-range <起始-结束>` | 公司范围，1-based 闭区间，如 `1-100` |
| `--start-idx <数字>` | 起始公司序号（1-based） |
| `--end-idx <数字>` | 结束公司序号（1-based，包含） |
| `--year-range <起始-结束>` | 财年范围，如 `2022-2025` |
| `--start-year <年>` | 起始年份 |
| `--end-year <年>` | 结束年份 |

### 4.3 路径与输出

| 参数 | 说明 |
|------|------|
| `--stock-list <路径>` | 股票列表 CSV 文件路径（含 stockId 的 company_stockid.csv） |
| `--output-dir <路径>` | 报告 PDF 保存目录 |
| `--log-dir <路径>` | 运行日志与下载日志目录 |
| `--log-format <excel\|csv>` | 下载日志格式，默认 `excel` |

### 4.4 股票列表与上市日期

| 参数 | 说明 |
|------|------|
| `--skip-listing-update` | 下载完成后不更新上市日期 |
| `--force-download-list` | 强制重新下载并解析港交所证券列表 |
| `--listing-mode <1\|2\|3>` | 上市日期更新范围：1=前10家，2=前100家，3=全部 |

### 4.5 并发

| 参数 | 说明 |
|------|------|
| `--threads <数字>` | 下载线程数 |
| `--max-workers <数字>` | 与 `--threads` 等价，下载线程数（程序内部限制在 1–32） |

---

## 五、配置文件格式（JSON）

当使用 `--config` 或非交互模式时，可通过 JSON 文件预设参数。路径可为相对（相对脚本所在目录）或绝对。

示例 `config.json`：

```json
{
  "stock_list_file": "HKEX/company_stockid.csv",
  "output_dir": "HKEX",
  "log_dir": "日志文件",
  "log_format": "excel",
  "company_range": "1-50",
  "year_range": "2022-2025",
  "threads": 8,
  "update_listing": true,
  "force_download_list": false,
  "non_interactive": true,
  "listing_mode": "3"
}
```

字段说明：

- **stock_list_file**：股票列表 CSV 路径  
- **output_dir**：报告输出目录  
- **log_dir**：日志目录  
- **log_format**：`excel` 或 `csv`  
- **company_range**：公司范围，如 `"1-100"`  
- **year_range**：年份范围，如 `"2022-2025"`  
- **threads** / **max_workers**：线程数  
- **update_listing**：是否在下载后更新上市日期  
- **force_download_list**：是否强制重新下载股票列表  
- **non_interactive**：是否非交互  
- **listing_mode**：`"1"` / `"2"` / `"3"`（同上）  

命令行参数会覆盖配置文件中同名字段。

---

## 六、使用示例

### 6.1 交互模式（默认）

直接运行，按提示输入范围与线程数：

```bash
python HKEX_hk_reports_crawler_enhanced.py
```

程序将依次询问：

- 是否更新/下载股票列表  
- 是否在下载完成后更新上市日期  
- 股票范围（如 `1-50` 或留空表示全部）  
- 年份范围（如 `2022-2025`）  
- 线程数（如 `8`）  
- 最后确认是否开始下载  

### 6.2 非交互模式 + 配置文件

使用配置文件一次性指定所有参数：

```bash
python HKEX_hk_reports_crawler_enhanced.py --auto --config config.json
```

或：

```bash
python HKEX_hk_reports_crawler_enhanced.py --non-interactive --config config.json
```

### 6.3 仅命令行参数（无配置文件）

```bash
python HKEX_hk_reports_crawler_enhanced.py --auto --company-range 1-100 --year-range 2022-2025 --threads 8 --output-dir HKEX --log-dir 日志文件
```

### 6.4 强制刷新股票列表

```bash
python HKEX_hk_reports_crawler_enhanced.py --auto --force-download-list --company-range 1-50 --year-range 2024-2025
```

### 6.5 跳过上市日期更新

```bash
python HKEX_hk_reports_crawler_enhanced.py --auto --skip-listing-update --company-range 1-200 --year-range 2023-2025
```

### 6.6 指定日志格式为 CSV

```bash
python HKEX_hk_reports_crawler_enhanced.py --auto --log-format csv --company-range 1-30
```

---

## 七、目录与文件结构

### 7.1 程序运行后常见目录

| 路径 | 说明 |
|------|------|
| **HKEX/** | 默认报告输出目录；也常放置 `company_stockid.csv`、`company_with_listing_date.csv` |
| **日志文件/** | 运行日志 `crawler_runtime.log`、下载日志（Excel/CSV） |
| **stockid_json/** | 披露易 activestock/inactivestock 的 JSON 及快照、告警 |
| **stockid_json/snapshots/** | 股票列表 JSON 的历史快照，用于异动比对 |
| **stockid_json/alerts/** | 当股票列表变动超过阈值时生成的告警目录 |

### 7.2 关键文件

- **company_stockid.csv**：带 `stockId` 的股票列表（股份代號、股份名稱、stockId 等），爬虫主入口列表。  
- **company_with_listing_date.csv**：在“更新上市日期”后生成，在列表基础上增加“上市日期”列。  
- **ListOfSecurities_c.xlsx**：从港交所下载的证券列表原始文件，用于生成/刷新上述 CSV。  
- **下载日志_YYYYMMDD_HHMMSS.xlsx（或 .csv）**：每次运行的下载明细（股票、报告类型、年份、文件名、URL、状态等）。  
- **crawler_runtime.log**：程序运行日志（旋转日志），便于排查错误。  

---

## 八、程序流程简述

1. **解析参数**：命令行 + 可选配置文件，得到最终 `settings`。  
2. **初始化爬虫**：创建 `CninfoHKReportCrawlerEnhanced`，加载或下载股票列表（`ensure_stock_list`）。  
3. **股票列表**（若需要）：  
   - 下载 `ListOfSecurities_c.xlsx` → 解析为股本證券列表 → 通过披露易接口补全 `stockId` → 保存为 `company_stockid.csv`。  
4. **按范围与年份爬取**：  
   - 根据 `start_idx`、`end_idx`、`start_year`、`end_year` 过滤公司与年份；  
   - 对每家公司的年报、中期报告、季度报告调用披露易搜索，解析结果页，筛选目标类型；  
   - 多线程下载 PDF，跳过已存在文件，并写入下载日志。  
5. **上市日期更新**（可选）：  
   - 调用 `run_listing_date_update`，按 `listing_mode`（1/2/3）更新前 10/100/全部公司的上市日期，写入 `company_with_listing_date.csv`。  

---

## 九、注意事项

1. **网络与合规**：请合理设置线程数（建议 5–10），避免请求过于频繁；使用仅用于个人学习与研究，遵守港交所披露易使用条款。  
2. **股票列表**：首次运行或使用 `--force-download-list` 时会从港交所下载列表并解析，需要网络畅通。  
3. **stockId**：披露易搜索依赖 `stockId`，列表中的 `stockId` 由程序自动从披露易 JSON/partial 接口获取或补全；若大量缺失可考虑刷新列表。  
4. **已下载文件**：程序会根据本地已有文件与日志跳过已下载的 PDF，重复运行不会重复下载同一文件。  
5. **上市日期**：依赖 AKShare（东方财富）接口，可能受接口限频或变更影响；`listing_mode` 选 3 时处理全部公司，耗时较长。  
6. **日志与编码**：日志与 CSV 使用 UTF-8（含 BOM 的 utf-8-sig），便于在 Excel 中正确打开中文。  

---

## 十、常见问题

**Q：提示缺少某个包？**  
A：按提示执行 `pip install <包名>`，或 `pip install -r requirements.txt`。

**Q：如何只下载某几家公司的报告？**  
A：使用 `--company-range`，例如 `--company-range 1-5` 表示列表中的前 5 家。

**Q：如何只下载某几年？**  
A：使用 `--year-range` 或 `--start-year`/`--end-year`，例如 `--year-range 2023-2025`。

**Q：下载被拒绝或很慢？**  
A：降低 `--threads`/`--max-workers`，程序内部会自适应限流，但线程数过大会增加被限流概率。

**Q：上市日期更新很慢？**  
A：`listing_mode` 选 1 或 2 先测试；选 3 会更新全部公司，每家公司有约 0.5 秒间隔，总时间较长。

**Q：非交互模式如何不更新上市日期？**  
A：在配置中设 `"update_listing": false` 或命令行加 `--skip-listing-update`。

---

以上为 **HKEX_hk_reports_crawler_enhanced.py** 的使用与介绍说明。若脚本升级，请以实际代码与帮助信息为准。
