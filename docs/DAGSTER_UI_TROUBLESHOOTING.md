# Dagster UI 显示问题排查指南

## 问题描述

访问 Dagster UI (http://127.0.0.1:61879/runs) 时，运行 parse job 一直显示不出内容。

## 常见原因

### 1. 多个 Dagster 实例同时运行

**症状**：
- 有多个 `dagster_webserver` 进程在运行
- 访问的 UI 可能不是正在执行任务的那个实例
- 日志显示任务正在运行，但 UI 中看不到

**诊断方法**：
```bash
# 检查所有 Dagster webserver 进程
ps aux | grep dagster_webserver | grep -v grep

# 检查端口占用
lsof -i :61879

# 使用诊断脚本
./scripts/fix_dagster_instances.sh
```

**解决方法**：
```bash
# 方法 1: 停止所有 Dagster 进程并重启
pkill -f dagster
sleep 3
dagster dev

# 方法 2: 只停止多余的实例
kill <不需要的PID>
```

### 2. 浏览器缓存问题

**症状**：
- UI 加载缓慢或不完整
- 页面显示空白
- 控制台有 JS 错误

**解决方法**：
```
1. 硬刷新浏览器：Cmd+Shift+R (Mac) 或 Ctrl+Shift+R (Windows)
2. 清除浏览器缓存
3. 使用隐身模式打开
4. 尝试不同的浏览器
```

### 3. Dagster 实例存储目录问题

**症状**：
- 日志正常但 UI 中看不到运行记录
- 运行 ID 不匹配

**诊断方法**：
```bash
# 检查 Dagster home 目录
echo $DAGSTER_HOME

# 查看运行记录
ls -lth $DAGSTER_HOME/storage/

# 查看最新运行的日志
ls -lh $DAGSTER_HOME/storage/<run_id>/compute_logs/
```

**解决方法**：
```bash
# 使用固定的 DAGSTER_HOME
export DAGSTER_HOME=/Users/han/PycharmProjects/FinNet/.dagster_home
mkdir -p $DAGSTER_HOME
dagster dev
```

### 4. 任务正在运行但进度不显示

**症状**：
- 日志显示任务在执行
- UI 中看不到实时进度

**可能原因**：
1. **长时间运行的任务**：MinerU API 解析大文件可能需要 5-30 分钟
2. **UI 轮询频率**：Dagster UI 默认每 2 秒轮询一次日志
3. **日志缓冲**：日志可能被缓冲，还没有写入文件

**解决方法**：
```bash
# 实时查看日志文件
tail -f $DAGSTER_HOME/storage/<run_id>/compute_logs/*.err
tail -f $DAGSTER_HOME/storage/<run_id>/compute_logs/*.out

# 或使用脚本
./scripts/diagnose_dagster_ui.sh
```

### 5. 网络/CORS 问题

**症状**：
- 浏览器控制台显示网络错误
- CORS 错误
- WebSocket 连接失败

**诊断方法**：
```
打开浏览器开发者工具 (F12)
- Console 标签：查看 JavaScript 错误
- Network 标签：查看网络请求状态
```

**解决方法**：
```bash
# 重启 Dagster
pkill -f dagster
dagster dev

# 或使用特定端口
dagster dev -p 3000
```

## 快速诊断脚本

### 检查 Dagster UI 状态

```bash
#!/bin/bash
# 运行诊断脚本
./scripts/diagnose_dagster_ui.sh
```

### 检查并修复多实例问题

```bash
#!/bin/bash
# 运行修复脚本
./scripts/fix_dagster_instances.sh
```

## 常用命令

### 查看所有运行记录

```bash
# 列出所有运行
ls -lth $DAGSTER_HOME/storage/

# 查看特定运行的日志
cat $DAGSTER_HOME/storage/<run_id>/compute_logs/*.err
cat $DAGSTER_HOME/storage/<run_id>/compute_logs/*.out
```

### 实时监控日志

```bash
# 监控错误日志
tail -f $DAGSTER_HOME/storage/<run_id>/compute_logs/*.err

# 监控输出日志
tail -f $DAGSTER_HOME/storage/<run_id>/compute_logs/*.out

# 同时监控两个日志
tail -f $DAGSTER_HOME/storage/<run_id>/compute_logs/*.{err,out}
```

### 清理和重启

```bash
# 清理所有 Dagster 进程
pkill -f dagster

# 清理旧的运行记录（可选）
rm -rf $DAGSTER_HOME/storage/*

# 重新启动
dagster dev
```

## 推荐的工作流程

### 1. 启动 Dagster

```bash
# 方法 1: 使用默认配置
cd /Users/han/PycharmProjects/FinNet
dagster dev

# 方法 2: 使用固定的 DAGSTER_HOME
export DAGSTER_HOME=/Users/han/PycharmProjects/FinNet/.dagster_home
mkdir -p $DAGSTER_HOME
dagster dev
```

### 2. 访问 UI

```
http://127.0.0.1:3000
```

### 3. 运行 Job

1. 在 UI 中找到你的 job (例如 `parse_pdf_job`)
2. 点击 "Launchpad"
3. 配置参数
4. 点击 "Launch Run"

### 4. 监控进度

**方法 1: 在 UI 中查看**
- 点击 "Runs" 标签
- 找到你的运行
- 点击查看详情和日志

**方法 2: 在命令行查看**
```bash
# 查看最新运行的日志
LATEST_RUN=$(ls -t $DAGSTER_HOME/storage/ | head -1)
tail -f $DAGSTER_HOME/storage/$LATEST_RUN/compute_logs/*.err
```

### 5. 检查结果

```bash
# 查看运行是否完成
ls $DAGSTER_HOME/storage/$LATEST_RUN/compute_logs/*.complete

# 查看最终日志
tail -100 $DAGSTER_HOME/storage/$LATEST_RUN/compute_logs/*.err
```

## 当前问题的解决方案

根据你的情况，问题可能是：

**你有多个 Dagster 实例在运行，访问的 UI 不是正在执行任务的那个实例。**

**立即解决方法**：

```bash
# 1. 停止所有 Dagster 进程
pkill -f dagster

# 2. 等待几秒
sleep 3

# 3. 重新启动
cd /Users/han/PycharmProjects/FinNet
dagster dev

# 4. 访问 UI
# 打开浏览器访问: http://127.0.0.1:3000
```

**长期解决方案**：

创建一个启动脚本，避免多实例问题：

```bash
#!/bin/bash
# start_dagster.sh

# 停止所有旧的 Dagster 进程
pkill -f dagster
sleep 2

# 设置固定的 DAGSTER_HOME
export DAGSTER_HOME=/Users/han/PycharmProjects/FinNet/.dagster_home
mkdir -p $DAGSTER_HOME

# 启动 Dagster
cd /Users/han/PycharmProjects/FinNet
dagster dev

# UI 地址: http://127.0.0.1:3000
```

## 验证修复

运行以下命令验证修复成功：

```bash
# 1. 只应该有一个 dagster_webserver 进程
ps aux | grep dagster_webserver | grep -v grep | wc -l
# 期望输出: 1

# 2. 检查端口
lsof -i :3000
# 应该看到 dagster_webserver 在监听

# 3. 访问 UI
# http://127.0.0.1:3000/runs
# 应该能看到所有运行记录
```

## 需要帮助？

如果问题仍然存在，收集以下信息：

1. Dagster 版本
   ```bash
   dagster --version
   ```

2. 进程信息
   ```bash
   ps aux | grep dagster | grep -v grep
   ```

3. 日志文件
   ```bash
   ls -lth $DAGSTER_HOME/storage/
   tail -100 $DAGSTER_HOME/storage/<run_id>/compute_logs/*.err
   ```

4. 浏览器控制台错误截图
