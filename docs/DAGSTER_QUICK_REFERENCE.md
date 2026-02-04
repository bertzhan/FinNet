# Dagster 快速参考指南

## 目录
- [常用命令](#常用命令)
- [故障排查](#故障排查)
- [监控脚本](#监控脚本)
- [最佳实践](#最佳实践)

---

## 常用命令

### 启动 Dagster

```bash
# 方法 1: 标准启动（推荐）
cd /Users/han/PycharmProjects/FinNet
dagster dev

# 方法 2: 使用固定的 Dagster Home
export DAGSTER_HOME=/Users/han/PycharmProjects/FinNet/.dagster_home
mkdir -p $DAGSTER_HOME
dagster dev

# 方法 3: 使用一键启动脚本（清理旧实例）
./scripts/restart_dagster_clean.sh
```

**默认 UI 地址**: http://127.0.0.1:3000

### 停止 Dagster

```bash
# 方法 1: 在运行 dagster dev 的终端按 Ctrl+C

# 方法 2: 停止所有 Dagster 进程
pkill -f dagster

# 方法 3: 强制停止
pkill -9 -f dagster
```

### 检查状态

```bash
# 检查所有 Dagster 进程
ps aux | grep dagster | grep -v grep

# 检查 Web Server
ps aux | grep dagster_webserver | grep -v grep

# 检查端口占用
lsof -i :3000

# 检查特定端口
lsof -i :61879
```

---

## 故障排查

### 问题 1: UI 显示不出内容

**症状**: 打开 Dagster UI，Runs 页面空白或不显示运行记录

**诊断**:
```bash
# 运行诊断脚本
./scripts/diagnose_dagster_ui.sh

# 或手动检查
ps aux | grep dagster_webserver | grep -v grep
```

**解决方法**:

1. **刷新浏览器**
   ```
   - 硬刷新: Cmd+Shift+R (Mac) 或 Ctrl+Shift+R (Windows)
   - 清除缓存后重新打开
   - 尝试隐身模式
   ```

2. **重启 Dagster**
   ```bash
   ./scripts/restart_dagster_clean.sh
   ```

3. **检查是否有多个实例**
   ```bash
   ./scripts/fix_dagster_instances.sh
   ```

### 问题 2: 多个 Dagster 实例运行

**症状**: `ps aux | grep dagster` 显示多个 webserver 进程

**解决方法**:
```bash
# 停止所有实例
pkill -f dagster
sleep 3

# 重新启动
dagster dev
```

### 问题 3: Parse Job 不显示进度

**症状**: Job 在运行，但 UI 中看不到进度或日志

**可能原因**:
1. MinerU API 解析大文件需要时间（5-30分钟）
2. 日志缓冲还未写入
3. 浏览器未自动刷新

**解决方法**:

1. **等待并刷新**
   - 等待 1-2 分钟
   - 刷新浏览器页面

2. **实时查看日志**
   ```bash
   # 运行监控脚本
   ./scripts/monitor_parse_job.sh

   # 或手动查看日志
   ls -lth $DAGSTER_HOME/storage/
   LATEST_RUN=$(ls -t $DAGSTER_HOME/storage/ | head -1)
   tail -f $DAGSTER_HOME/storage/$LATEST_RUN/compute_logs/*.err
   ```

3. **检查进程状态**
   ```bash
   ps aux | grep parse | grep -v grep
   ```

### 问题 4: 无法访问 UI

**症状**: 浏览器无法打开 Dagster UI 或显示连接错误

**诊断**:
```bash
# 检查 Dagster 是否在运行
ps aux | grep dagster_webserver | grep -v grep

# 检查端口是否被占用
lsof -i :3000
```

**解决方法**:

1. **确认 Dagster 正在运行**
   ```bash
   dagster dev
   ```

2. **检查端口冲突**
   ```bash
   # 如果 3000 端口被占用，使用其他端口
   dagster dev -p 3001
   ```

3. **检查防火墙设置**
   - macOS: 系统偏好设置 > 安全性与隐私 > 防火墙
   - 允许 Python 访问网络

---

## 监控脚本

### 诊断 Dagster UI 问题

```bash
./scripts/diagnose_dagster_ui.sh
```

**功能**:
- 检查所有 Dagster 进程
- 找到活动的 Dagster home 目录
- 显示最近的运行记录
- 查看最新的日志

### 修复多实例问题

```bash
./scripts/fix_dagster_instances.sh
```

**功能**:
- 列出所有 Dagster webserver 实例
- 识别有活动任务的实例
- 显示每个实例的 UI 地址
- 提供清理建议

### 监控 Parse Job

```bash
./scripts/monitor_parse_job.sh
```

**功能**:
- 查找运行中的 parse job 进程
- 定位日志文件位置
- 显示最新的日志内容
- 提供实时监控命令

### 一键重启

```bash
./scripts/restart_dagster_clean.sh
```

**功能**:
- 停止所有 Dagster 进程
- 验证进程已完全停止
- 启动新的 Dagster 实例
- 显示 UI 访问地址

---

## 最佳实践

### 1. 使用固定的 Dagster Home

**好处**: 避免临时目录被清理，方便查看历史运行记录

**方法**:
```bash
# 在 ~/.bashrc 或 ~/.zshrc 中添加
export DAGSTER_HOME=/Users/han/PycharmProjects/FinNet/.dagster_home

# 或创建启动脚本
cat > start_dagster.sh << 'EOF'
#!/bin/bash
export DAGSTER_HOME=/Users/han/PycharmProjects/FinNet/.dagster_home
mkdir -p $DAGSTER_HOME
cd /Users/han/PycharmProjects/FinNet
dagster dev
EOF

chmod +x start_dagster.sh
```

### 2. 定期清理旧的运行记录

```bash
# 删除 30 天前的运行记录
find $DAGSTER_HOME/storage -type d -mtime +30 -exec rm -rf {} +

# 只保留最近 100 个运行
cd $DAGSTER_HOME/storage
ls -t | tail -n +101 | xargs rm -rf
```

### 3. 监控日志文件大小

```bash
# 检查日志目录大小
du -sh $DAGSTER_HOME/storage

# 查找大文件
find $DAGSTER_HOME/storage -type f -size +100M
```

### 4. 使用 Git 忽略 Dagster 临时文件

```bash
# .gitignore
.tmp_dagster_home_*/
.dagster_home/
```

### 5. 配置日志级别

```bash
# 减少日志输出
dagster dev --dagster-log-level warning

# 详细日志（调试用）
dagster dev --dagster-log-level debug
```

---

## 常见 Job 配置

### Parse PDF Job

```yaml
ops:
  parse_documents_op:
    config:
      enable_silver_upload: true
      start_page_id: 0
      # end_page_id: 100  # 可选：只解析前100个文档
      # force_reparse: false  # 可选：强制重新解析
```

### Crawl Job

```yaml
ops:
  crawl_a_share_reports_op:
    config:
      workers: 4
      year: 2024
      stock_codes: ["000001", "000002"]
      # 或使用其他过滤方式
      # limit: 10
      # industry: "银行"
```

### Chunk Job

```yaml
ops:
  chunk_documents_op:
    config:
      max_chunk_size: 800
      overlap_size: 100
      # start_page_id: 0
      # end_page_id: 100
```

### Vectorize Job

```yaml
ops:
  vectorize_chunks_op:
    config:
      batch_size: 32
      # force_revectorize: false
      # start_chunk_id: 0
```

---

## 快速命令速查表

| 操作 | 命令 |
|------|------|
| 启动 Dagster | `dagster dev` |
| 停止 Dagster | `Ctrl+C` 或 `pkill -f dagster` |
| 检查进程 | `ps aux \| grep dagster` |
| 查看运行记录 | `ls -lth $DAGSTER_HOME/storage/` |
| 实时查看日志 | `tail -f $DAGSTER_HOME/storage/<run_id>/compute_logs/*.err` |
| 清理所有进程 | `pkill -9 -f dagster` |
| 诊断 UI 问题 | `./scripts/diagnose_dagster_ui.sh` |
| 一键重启 | `./scripts/restart_dagster_clean.sh` |
| 监控 Parse Job | `./scripts/monitor_parse_job.sh` |
| 检查端口占用 | `lsof -i :3000` |

---

## 获取帮助

### 查看 Dagster 文档

```bash
# 打开官方文档
open https://docs.dagster.io

# 查看命令帮助
dagster --help
dagster dev --help
```

### 查看本地文档

- [Dagster UI 故障排查](DAGSTER_UI_TROUBLESHOOTING.md)
- [Crawl Job 快速参考](CRAWL_JOB_QUICK_REFERENCE.md)
- [爬虫 Job 进度功能](CRAWL_JOB_PROGRESS_FEATURE.md)

### 调试技巧

1. **查看详细日志**
   ```bash
   dagster dev --dagster-log-level debug
   ```

2. **检查配置**
   ```bash
   dagster instance info
   ```

3. **验证 Job 定义**
   ```bash
   dagster job list
   ```

4. **测试单个 Op**
   ```bash
   dagster job execute -j parse_pdf_job --config-yaml config.yaml
   ```

---

## 总结

**最常用的工作流程**:

1. 启动 Dagster: `dagster dev`
2. 访问 UI: http://127.0.0.1:3000
3. 运行 Job: 在 UI 中选择 Job → Launchpad → Launch Run
4. 监控进度: Runs 标签页 → 点击运行 → 查看日志
5. 停止 Dagster: `Ctrl+C`

**遇到问题时**:

1. 刷新浏览器 (`Cmd+R`)
2. 运行诊断: `./scripts/diagnose_dagster_ui.sh`
3. 重启 Dagster: `./scripts/restart_dagster_clean.sh`
4. 查看文档: [DAGSTER_UI_TROUBLESHOOTING.md](DAGSTER_UI_TROUBLESHOOTING.md)
