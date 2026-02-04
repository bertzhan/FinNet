# Dagster 文档索引

## 概述

本目录包含了 FinNet 项目中 Dagster 相关的所有文档和故障排查指南。

---

## 📚 文档目录

### 快速开始

- **[Dagster 快速参考指南](DAGSTER_QUICK_REFERENCE.md)** ⭐️ 推荐
  - 常用命令速查
  - 故障排查快速指南
  - 监控脚本使用说明
  - 最佳实践

### 故障排查

- **[Dagster UI 故障排查指南](DAGSTER_UI_TROUBLESHOOTING.md)**
  - UI 显示问题的完整解决方案
  - 多实例冲突处理
  - 浏览器缓存问题
  - 网络连接问题

### 功能文档

- **[爬虫 Job 股票代码过滤功能](CRAWL_STOCK_CODES_FEATURE.md)**
  - 功能实现总结
  - 测试结果
  - 使用示例

- **[爬虫 Job 快速参考](CRAWL_JOB_QUICK_REFERENCE.md)**
  - 配置参数说明
  - 常见使用场景
  - 错误处理

- **[爬虫 Job 进度显示功能](CRAWL_JOB_PROGRESS_FEATURE.md)**
  - 进度显示实现
  - 单进程 vs 多进程模式
  - 性能影响分析

- **[爬虫 Job 股票代码使用说明](crawl_job_stock_codes_usage.md)**
  - 详细使用说明
  - 参数优先级
  - 完整配置示例

---

## 🛠️ 实用脚本

### 诊断和监控

| 脚本 | 功能 | 使用场景 |
|------|------|----------|
| `scripts/diagnose_dagster_ui.sh` | 诊断 Dagster UI 显示问题 | UI 无法显示或显示异常 |
| `scripts/fix_dagster_instances.sh` | 检查并修复多实例问题 | 有多个 Dagster 进程运行 |
| `scripts/monitor_parse_job.sh` | 监控 Parse Job 运行状态 | 查看 job 实时进度 |
| `scripts/restart_dagster_clean.sh` | 一键重启 Dagster | 清理所有旧实例并重启 |

### 测试脚本

| 脚本 | 功能 |
|------|------|
| `scripts/test_stock_codes_filter.py` | 测试股票代码过滤功能（完整版） |
| `scripts/test_stock_codes_filter_simple.py` | 测试股票代码过滤功能（简化版） |

---

## 🚀 快速开始

### 1. 启动 Dagster

```bash
# 进入项目目录
cd /Users/han/PycharmProjects/FinNet

# 启动 Dagster
dagster dev

# 或使用一键启动脚本（推荐）
./scripts/restart_dagster_clean.sh
```

### 2. 访问 UI

打开浏览器访问: http://127.0.0.1:3000

### 3. 运行 Job

1. 在 UI 中找到你的 job
2. 点击 "Launchpad"
3. 配置参数
4. 点击 "Launch Run"

### 4. 监控进度

- 方法 1: 在 UI 的 "Runs" 标签页查看
- 方法 2: 运行监控脚本 `./scripts/monitor_parse_job.sh`

---

## ❓ 常见问题

### Q1: Dagster UI 显示不出内容？

**快速解决**:
```bash
# 1. 刷新浏览器 (Cmd+R)
# 2. 运行诊断
./scripts/diagnose_dagster_ui.sh
# 3. 重启 Dagster
./scripts/restart_dagster_clean.sh
```

**详细说明**: 参见 [DAGSTER_UI_TROUBLESHOOTING.md](DAGSTER_UI_TROUBLESHOOTING.md)

### Q2: 有多个 Dagster 实例在运行？

**快速解决**:
```bash
./scripts/fix_dagster_instances.sh
```

**详细说明**: 参见 [DAGSTER_UI_TROUBLESHOOTING.md#1-多个-dagster-实例同时运行](DAGSTER_UI_TROUBLESHOOTING.md#1-多个-dagster-实例同时运行)

### Q3: Parse Job 不显示进度？

**可能原因**:
1. MinerU API 解析大文件需要时间（5-30分钟）
2. 日志缓冲还未写入
3. 浏览器未自动刷新

**快速解决**:
```bash
# 实时查看日志
./scripts/monitor_parse_job.sh
```

**详细说明**: 参见 [DAGSTER_QUICK_REFERENCE.md#问题-3-parse-job-不显示进度](DAGSTER_QUICK_REFERENCE.md#问题-3-parse-job-不显示进度)

### Q4: 如何按股票代码爬取数据？

**快速配置**:
```yaml
ops:
  crawl_a_share_reports_op:
    config:
      stock_codes: ["000001", "000002", "600000"]
      year: 2024
```

**详细说明**: 参见 [CRAWL_JOB_QUICK_REFERENCE.md](CRAWL_JOB_QUICK_REFERENCE.md)

---

## 📖 推荐阅读顺序

### 初次使用

1. [Dagster 快速参考指南](DAGSTER_QUICK_REFERENCE.md) - 了解基本操作
2. [爬虫 Job 快速参考](CRAWL_JOB_QUICK_REFERENCE.md) - 学习如何配置和运行 job
3. [Dagster UI 故障排查指南](DAGSTER_UI_TROUBLESHOOTING.md) - 遇到问题时查阅

### 深入学习

4. [爬虫 Job 股票代码过滤功能](CRAWL_STOCK_CODES_FEATURE.md) - 了解高级功能
5. [爬虫 Job 进度显示功能](CRAWL_JOB_PROGRESS_FEATURE.md) - 了解进度监控实现

---

## 🔧 开发和调试

### 查看日志

```bash
# 方法 1: 使用脚本
./scripts/monitor_parse_job.sh

# 方法 2: 手动查看
export DAGSTER_HOME=/Users/han/PycharmProjects/FinNet/.dagster_home
ls -lth $DAGSTER_HOME/storage/
LATEST_RUN=$(ls -t $DAGSTER_HOME/storage/ | head -1)
tail -f $DAGSTER_HOME/storage/$LATEST_RUN/compute_logs/*.err
```

### 调试技巧

```bash
# 1. 启用详细日志
dagster dev --dagster-log-level debug

# 2. 查看实例信息
dagster instance info

# 3. 列出所有 job
dagster job list

# 4. 测试单个 job（命令行）
dagster job execute -j parse_pdf_job
```

### 性能分析

```bash
# 查看日志文件大小
du -sh $DAGSTER_HOME/storage

# 查看运行记录数量
ls $DAGSTER_HOME/storage | wc -l

# 查找大文件
find $DAGSTER_HOME/storage -type f -size +100M
```

---

## 📝 更新日志

### 2026-02-04

- ✅ 添加爬虫 job 进度显示功能
  - BaseCrawler 单进程模式进度
  - ReportCrawler 多进程模式进度
  - IPOCrawler 多进程模式进度

- ✅ 添加爬虫 job 股票代码过滤功能
  - 支持按股票代码列表精确爬取
  - 参数优先级: stock_codes > industry > limit
  - 完整的测试覆盖

- ✅ 创建完整的故障排查文档
  - Dagster UI 问题诊断和解决
  - 多实例问题处理
  - 实用脚本工具集

---

## 🤝 贡献

如果你发现文档有误或有改进建议，欢迎：

1. 直接修改文档
2. 提交 issue
3. 补充新的使用案例

---

## 📞 获取帮助

### 相关资源

- **Dagster 官方文档**: https://docs.dagster.io
- **项目 README**: `/Users/han/PycharmProjects/FinNet/README.md`
- **爬虫模块文档**: `/Users/han/PycharmProjects/FinNet/src/ingestion/README.md`

### 快速命令

```bash
# 查看所有可用脚本
ls -lh scripts/

# 查看所有文档
ls -lh docs/

# 搜索特定问题
grep -r "关键词" docs/
```

---

## 总结

本文档集合提供了：

✅ **快速参考** - 常用命令和配置
✅ **故障排查** - 常见问题的解决方案
✅ **实用脚本** - 自动化诊断和修复工具
✅ **最佳实践** - 推荐的工作流程
✅ **功能文档** - 新功能的详细说明

**开始使用**: 从 [Dagster 快速参考指南](DAGSTER_QUICK_REFERENCE.md) 开始！
