# SEC Filings ETL - 快速开始指南

## 📋 项目简介

这是一个自动化的 SEC 财报数据采集系统，可以：
- 自动下载美国上市公司的 10-K（年报）和 10-Q（季报）
- 支持 NASDAQ、NYSE、NYSE American、NYSE Arca 等交易所
- 下载包含完整的 HTML 财报和相关图片
- 存储到本地文件系统，并在数据库中记录元数据

**当前数据规模：**
- 📊 **107,694** 个文件（152 GB）
- 🏢 **4,192** 家公司
- 📈 **44,188** 份财报
- 📅 时间范围：**2023-2025** 年

---

## 🚀 快速开始

### 1️⃣ 环境检查

```bash
cd /Users/hao/Desktop/FINAI/files/filings-etl

# 检查数据库状态
docker ps | grep postgres

# 如果数据库未运行，启动它
docker-compose up -d postgres
```

### 2️⃣ 激活虚拟环境

```bash
source venv/bin/activate
```

### 3️⃣ 验证配置

```bash
# 查看当前配置
python -c "from config.settings import settings; print('存储路径:', settings.storage_root); print('数据库:', settings.database_url)"

# 应该看到：
# 存储路径: /Users/hao/Desktop/FINAI/sec_filings_data
# 数据库: postgresql+psycopg://postgres:***@localhost:5432/filings_db
```

---

## 📊 核心功能

### 功能 1：查看数据状态

```bash
# 快速查看数据库状态
python check_db_status.py

# 生成详细的完整性报告
python export_integrity_report.py -o integrity_report.md
```

### 功能 2：导出公司列表

```bash
# 导出 NASDAQ 公司列表
python export_companies.py --exchange NASDAQ

# 导出 NYSE 公司列表
python export_companies.py --exchange NYSE

# 导出所有交易所
python export_companies.py --all

# 导出时包含 IPO 日期（耗时较长）
python export_companies.py --exchange NASDAQ --with-ipo
```

**输出位置：** `data/companies/{交易所名称}/company.csv`

### 功能 3：下载财报数据

```bash
# NASDAQ 全量回填
make nasdaq-backfill

# NYSE 全量回填
make nyse-backfill

# 所有交易所回填
make all-exchanges-backfill

# 快速并发下载（推荐，10倍速度提升）
make backfill-fast

# 极速并发下载（20倍速度提升）
make backfill-turbo
```

### 功能 4：HTML 图片链接修复

```bash
# 预览将要修复的文件（安全，不修改）
make fix-html-preview

# 测试修复 50 个文件
make fix-html-test

# 修复所有 HTML 文件
make fix-html-all

# 按交易所修复
make fix-nasdaq        # NASDAQ
make fix-nyse          # NYSE
```

---

## 🎯 典型使用场景

### 场景 1：我想查看已有哪些公司的数据

```bash
# 方法 1：导出 CSV 查看
python export_companies.py --exchange NASDAQ
open data/companies/NASDAQ/company.csv

# 方法 2：直接浏览文件
open /Users/hao/Desktop/FINAI/sec_filings_data/NASDAQ
```

### 场景 2：我想下载某个交易所的最新数据

```bash
# 1. 确保数据库运行
docker-compose up -d postgres

# 2. 激活环境
source venv/bin/activate

# 3. 运行回填（仅下载缺失的数据）
make nasdaq-backfill

# 4. 监控进度（另开一个终端）
watch -n 5 python check_db_status.py
```

### 场景 3：我想查看某家公司的财报

```bash
# 示例：查看 Apple (AAPL) 的财报
open /Users/hao/Desktop/FINAI/sec_filings_data/NASDAQ/AAPL

# 文件命名规则：
# AAPL_2024_FY_01-11-2024.html     → 2024财年年报
# AAPL_2024_Q1_02-02-2024.html     → 2024年Q1季报
# AAPL_2024_Q1_02-02-2024_image-001.jpg → 相关图片
```

### 场景 4：我想获取公司的 IPO 日期

```bash
# 导出 NASDAQ 公司并包含 IPO 日期
python export_companies.py --exchange NASDAQ --with-ipo

# 等待完成（可能需要10-30分钟，取决于公司数量）
# 输出：data/companies/NASDAQ/company_with_ipo.csv

# 查看结果
cat data/companies/NASDAQ/company_with_ipo.csv | head -20
```

### 场景 5：我想生成数据质量报告

```bash
# 生成完整性报告
python export_integrity_report.py -o my_report.md

# 在 VS Code 或其他编辑器中查看
code my_report.md

# 报告包含：
# - 文件完整性统计
# - 按交易所分类的覆盖率
# - 按文件类型（HTML/图片）的匹配率
# - 公司覆盖率分析
```

---

## 🔧 常用命令速查

### 数据库管理

```bash
docker-compose up -d postgres      # 启动数据库
docker-compose down                # 停止数据库
python check_db_status.py          # 检查数据库状态
```

### 数据下载

```bash
make nasdaq-backfill               # NASDAQ 回填
make nyse-backfill                 # NYSE 回填
make backfill-fast                 # 快速并发下载
make monitor                       # 监控下载进度
```

### 数据导出

```bash
# 导出公司列表
python export_companies.py --exchange NASDAQ
python export_companies.py --all

# 导出 IPO 数据
python export_companies.py --exchange NASDAQ --with-ipo

# 生成完整性报告
python export_integrity_report.py
```

### HTML 修复

```bash
make fix-html-preview              # 预览修复
make fix-html-test                 # 测试修复（50文件）
make fix-nasdaq                    # 修复 NASDAQ
make fix-nyse                      # 修复 NYSE
make test-html-links               # 测试链接状态
```

### 诊断工具

```bash
python check_db_status.py          # 数据库状态
python check_file_integrity.py     # 文件完整性
make diagnose                      # 覆盖率诊断
make compliance                    # 合规性检查
```

---

## 📁 重要路径

### 数据存储

```
/Users/hao/Desktop/FINAI/sec_filings_data/
├── NASDAQ/              # NASDAQ 公司数据
│   ├── AAPL/           # Apple
│   ├── MSFT/           # Microsoft
│   ├── GOOGL/          # Alphabet
│   └── ...
├── NYSE/                # NYSE 公司数据
│   ├── JPM/            # JPMorgan
│   ├── BAC/            # Bank of America
│   └── ...
├── NYSE American/       # NYSE American 数据
└── NYSE Arca/          # NYSE Arca 数据
```

### 导出数据

```
filings-etl/data/companies/
├── NASDAQ/
│   ├── company.csv                # 基础公司列表
│   └── company_with_ipo.csv       # 含 IPO 日期
├── NYSE/
│   ├── company.csv
│   └── company_with_ipo.csv
└── ...
```

### 配置文件

```
filings-etl/
├── .env                           # 环境变量配置
├── docker-compose.yml             # Docker 配置
├── Makefile                       # 常用命令集合
└── requirements.txt               # Python 依赖
```

---

## ⚙️ 配置说明

### .env 配置文件

```bash
# 数据库配置
DB_HOST=localhost
DB_PORT=5432
DB_NAME=filings_db
DB_USER=postgres
DB_PASSWORD=postgres

# SEC API 配置（必须修改为你的信息）
SEC_USER_AGENT=hao marandahao@gmail.com

# 下载配置
DOWNLOAD_WORKERS=8                 # 并发下载数（1-10）

# 存储配置
STORAGE_ROOT=/Users/hao/Desktop/FINAI/sec_filings_data
```

**重要提示：**
- `SEC_USER_AGENT` 必须包含你的姓名和有效邮箱
- SEC 要求所有 API 请求必须标识身份
- 违反此规定可能导致 IP 被封禁

---

## 📈 性能与限制

### 下载速度

- **顺序下载：** ~116 文件/分钟
- **并发下载（8 workers）：** ~512 文件/分钟（**4.4x 提升**）
- **并发下载（20 workers）：** ~1000 文件/分钟（**8-10x 提升**）

### SEC API 限制

- **速率限制：** 10 请求/秒
- **用户代理：** 必须包含姓名和邮箱
- **合规性：** 脚本自动遵守速率限制

### 存储需求

- **当前规模：** 152 GB（107,694 文件）
- **预计完整规模：** 180-200 GB
- **年增长：** ~30 GB/年

---

## 🆘 常见问题

### Q1: 数据库连接失败

```bash
# 检查 Docker 是否运行
docker ps | grep postgres

# 如果未运行，启动数据库
docker-compose up -d postgres

# 等待 3 秒后重试
sleep 3
python check_db_status.py
```

### Q2: 下载速度太慢

```bash
# 使用快速并发下载
make backfill-fast

# 或使用极速模式（注意 SEC 限速）
make backfill-turbo

# 调整并发数（编辑 .env）
DOWNLOAD_WORKERS=8  # 推荐值：8
```

### Q3: 磁盘空间不足

```bash
# 查看存储使用情况
du -sh /Users/hao/Desktop/FINAI/sec_filings_data

# 如果需要移动到其他位置
# 1. 编辑 .env，修改 STORAGE_ROOT
# 2. 移动文件
mv /Users/hao/Desktop/FINAI/sec_filings_data /新路径/
# 3. 重启服务
```

### Q4: HTML 图片无法显示

```bash
# 运行图片链接修复
make fix-html-preview     # 先预览
make fix-html-test        # 测试 50 个文件
make fix-html-all         # 全部修复

# 验证修复效果
make test-html-links
```

### Q5: 如何只下载特定公司的数据

```bash
# 目前系统按交易所批量下载
# 如需单个公司，可以手动查询数据库：

source venv/bin/activate
python -c "
from config.db import get_db_session
from models import Company, Filing
session = get_db_session()
company = session.query(Company).filter_by(ticker='AAPL').first()
print(f'Company: {company.company_name}')
print(f'CIK: {company.cik}')
filings = session.query(Filing).filter_by(company_id=company.id).all()
print(f'Filings: {len(filings)}')
"
```

---

## 📚 更多文档

- **完整用户指南：** `USER_GUIDE.md` (1273 行详细说明)
- **完整性报告使用：** `INTEGRITY_REPORT_USAGE.md`
- **HTML 修复指南：** `QUICK_START_FIX_HTML.md`
- **批量修复指南：** `BATCH_FIX_GUIDE.md`
- **IPO 提取指南：** `IPO_DATE_EXTRACTION_GUIDE.md`
- **优化总结：** `OPTIMIZATION_SUMMARY.md`

---

## 🎓 学习路径

### 第 1 天：熟悉基础操作

1. 启动数据库：`docker-compose up -d postgres`
2. 检查状态：`python check_db_status.py`
3. 导出公司列表：`python export_companies.py --exchange NASDAQ`
4. 浏览数据文件：`open /Users/hao/Desktop/FINAI/sec_filings_data/NASDAQ/AAPL`

### 第 2 天：了解数据下载

1. 运行小规模测试：`python test_download_first_artifact.py`
2. 下载单个交易所：`make nasdaq-backfill`
3. 监控进度：`python check_db_status.py`
4. 生成报告：`python export_integrity_report.py`

### 第 3 天：数据质量优化

1. 检查 HTML 图片：`make test-html-links`
2. 修复图片链接：`make fix-html-test`
3. 验证修复效果：浏览修复后的 HTML 文件
4. 全量修复：`make fix-html-all`

### 第 4 天：高级功能

1. 获取 IPO 数据：`python export_companies.py --all --with-ipo`
2. 并发下载优化：`make backfill-fast`
3. 自定义导出：修改 `export_companies.py` 添加字段
4. 数据分析：使用 SQL 查询数据库

---

## 💡 最佳实践

### 1. 定期备份

```bash
# 备份数据库
docker exec filings_postgres pg_dump -U postgres filings_db > backup.sql

# 备份文件（增量）
rsync -av --progress /Users/hao/Desktop/FINAI/sec_filings_data /备份路径/
```

### 2. 增量更新

```bash
# 定期运行回填，只下载新数据
make nasdaq-backfill  # 会自动跳过已下载的文件
```

### 3. 监控与日志

```bash
# 实时监控下载
watch -n 5 python check_db_status.py

# 查看日志
tail -f logs/download.log

# 查看错误
python -c "
from config.db import get_db_session
from models import Artifact
session = get_db_session()
failed = session.query(Artifact).filter_by(status='failed').all()
for a in failed:
    print(f'{a.filing.company.ticker}: {a.url}')
"
```

### 4. 性能调优

```bash
# 根据网络状况调整并发数
# 编辑 .env
DOWNLOAD_WORKERS=8    # 网络好：8-10
                      # 网络差：4-6
                      # 不稳定：2-4
```

---

## 🔗 相关资源

- **SEC EDGAR：** https://www.sec.gov/edgar
- **SEC API 文档：** https://www.sec.gov/os/accessing-edgar-data
- **项目 GitHub：** https://github.com/offshore4190/finai

---

## 📞 获取帮助

### 查看所有可用命令

```bash
make help
```

### 查看脚本帮助

```bash
python export_companies.py --help
python export_integrity_report.py --help
```

### 常用诊断命令

```bash
# 数据库状态
python check_db_status.py

# 文件完整性
python check_file_integrity.py

# 详细分析
python query_db_summary.py

# 覆盖率诊断
make diagnose

# 合规性检查
make compliance
```

---

**最后更新：** 2025-11-02  
**版本：** 1.0  
**维护者：** Hao (marandahao@gmail.com)

---

## ⚡ 快速命令参考卡

```bash
# === 基础操作 ===
docker-compose up -d postgres           # 启动数据库
source venv/bin/activate               # 激活环境
python check_db_status.py              # 检查状态

# === 数据导出 ===
python export_companies.py --exchange NASDAQ          # 导出公司
python export_companies.py --exchange NASDAQ --with-ipo  # 含IPO
python export_integrity_report.py                     # 完整性报告

# === 数据下载 ===
make nasdaq-backfill                   # NASDAQ 回填
make nyse-backfill                     # NYSE 回填
make backfill-fast                     # 快速并发
make monitor                           # 监控进度

# === HTML 修复 ===
make fix-html-preview                  # 预览修复
make fix-nasdaq                        # 修复 NASDAQ
make test-html-links                   # 测试状态

# === 帮助 ===
make help                              # 所有命令
python 脚本名.py --help                # 脚本帮助
```

---

🎉 **开始使用：** `make help` 或继续阅读 `USER_GUIDE.md`








