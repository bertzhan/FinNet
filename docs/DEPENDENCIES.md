# 项目依赖说明

## 📦 核心依赖

### 配置管理
- `pydantic-settings>=2.0.0` - 配置管理（`src/common/config.py`）
- `pydantic>=2.0.0` - 数据验证

### 爬虫模块
- `requests>=2.28.0` - HTTP 请求
- `beautifulsoup4>=4.11.0` - HTML 解析
- `tqdm>=4.64.0` - 进度条

### 存储层
- `minio>=7.0.0` - MinIO 对象存储客户端
- `psycopg2-binary>=2.9.0` - PostgreSQL 驱动
- `sqlalchemy>=2.0.0` - ORM
- `pymilvus>=2.3.0` - Milvus 向量数据库客户端

### 调度系统
- `dagster>=1.5.0` - 数据编排和调度
- `dagster-webserver>=1.5.0` - Dagster Web UI

### 工具库
- `python-dotenv>=1.0.0` - 环境变量管理

## 🚀 安装方式

### 方式1：使用安装脚本（推荐）

```bash
bash scripts/install_dependencies.sh
```

### 方式2：手动安装

```bash
pip install -r requirements.txt
```

### 方式3：使用国内镜像（网络较慢时）

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## ✅ 验证安装

### 检查关键依赖

```bash
python3 -c "
import sys
packages = {
    'pydantic_settings': 'pydantic-settings',
    'dagster': 'dagster',
    'minio': 'minio',
    'psycopg2': 'psycopg2-binary',
    'sqlalchemy': 'sqlalchemy',
    'pymilvus': 'pymilvus',
}
for module, package in packages.items():
    try:
        __import__(module)
        print(f'✅ {package}')
    except ImportError:
        print(f'❌ {package} 未安装')
"
```

### 运行完整测试

```bash
bash scripts/test_dagster_integration.sh
```

## 🔍 依赖问题排查

### 问题1: `ModuleNotFoundError: No module named 'pydantic_settings'`

**解决**:
```bash
pip install pydantic-settings
```

### 问题2: `ModuleNotFoundError: No module named 'dagster'`

**解决**:
```bash
pip install dagster dagster-webserver
```

### 问题3: PostgreSQL 连接失败

**检查**:
1. PostgreSQL 服务是否运行：`docker-compose ps postgres`
2. 环境变量是否正确：检查 `.env` 文件
3. 端口是否被占用：`lsof -i :5432`

### 问题4: MinIO 连接失败

**检查**:
1. MinIO 服务是否运行：`docker-compose ps minio`
2. 环境变量是否正确：检查 `.env` 文件
3. 端口是否被占用：`lsof -i :9000`

## 📝 依赖文件位置

- **项目依赖**: `requirements.txt` (项目根目录)
- **爬虫模块依赖**: `src/crawler/requirements.txt` (旧版本，已整合)

## 🔄 更新依赖

### 添加新依赖

1. 编辑 `requirements.txt`
2. 添加依赖项（格式：`package>=version`）
3. 运行 `pip install -r requirements.txt`

### 更新依赖版本

1. 编辑 `requirements.txt`
2. 修改版本号
3. 运行 `pip install -r requirements.txt --upgrade`

## 📚 相关文档

- [README.md](../README.md) - 项目说明
- [DAGSTER_QUICKSTART.md](DAGSTER_QUICKSTART.md) - Dagster 快速开始
- [INGESTION_LAYER_GUIDE.md](INGESTION_LAYER_GUIDE.md) - 爬虫使用指南

---

*最后更新: 2025-01-13*
