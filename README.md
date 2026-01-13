# FinNet MVP - 全球上市公司数据湖平台

## 项目简介

FinNet MVP 是一个面向大模型训练和知识库应用的数据湖平台，整合A股、港股、美股上市公司公开数据，提供高质量的结构化与非结构化数据支持。

**MVP目标**：验证端到端数据流程（采集 → 存储 → 处理 → RAG应用）

## 技术栈

- **对象存储**: MinIO
- **元数据数据库**: PostgreSQL 15
- **向量数据库**: Milvus Standalone
- **部署方式**: Docker Compose

## 快速开始

### 前置要求

- Docker >= 20.10
- Docker Compose >= 2.0
- 至少 8GB 可用内存
- 至少 20GB 可用磁盘空间

### 1. 克隆项目

```bash
git clone <repository-url>
cd FinNet
```

### 2. 配置环境变量

```bash
cp env.example .env
# 编辑 .env 文件，修改密码等配置（可选）
```

### 3. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 4. 验证服务

```bash
# 运行健康检查脚本
chmod +x scripts/check_services.sh
./scripts/check_services.sh
```

### 5. 访问服务

| 服务 | 地址 | 默认账号/密码 |
|-----|------|-------------|
| MinIO Console | http://localhost:9001 | admin / admin123456 |
| PostgreSQL | localhost:5432 | finnet / finnet123456 |
| Milvus | localhost:19530 | - |

## 服务说明

### MinIO (对象存储)

- **API端口**: 9000
- **Console端口**: 9001
- **用途**: 存储原始PDF、解析后的文本等文件
- **访问**: http://localhost:9001

### PostgreSQL (元数据数据库)

- **端口**: 5432
- **数据库名**: finnet
- **用途**: 存储公告元数据、文本元数据、向量元数据
- **连接**: `psql -h localhost -U finnet -d finnet`

### Milvus (向量数据库)

- **gRPC端口**: 19530
- **指标端口**: 9091
- **用途**: 存储文档向量，支持相似度检索
- **依赖**: etcd (元数据存储) + MinIO (对象存储)

## 目录结构

```
FinNet/
├── docker-compose.yml      # Docker Compose配置
├── env.example             # 环境变量模板
├── scripts/
│   ├── init_db.sql        # 数据库初始化脚本
│   └── check_services.sh   # 服务健康检查脚本
├── plan.md                # 完整架构设计文档
└── README.md              # 本文件
```

## 数据流程（MVP）

```
A股公告采集 → MinIO存储 → PDF解析 → 文本清洗 → 向量化 → Milvus存储 → RAG检索
```

## 开发计划

- [x] Day 1-2: 基础设施部署
- [ ] Day 3-4: 数据采集开发
- [ ] Day 5-7: PDF解析 + 文本处理
- [ ] Day 8-9: 向量化服务
- [ ] Day 10-11: RAG检索服务
- [ ] Day 12-13: LLM问答集成
- [ ] Day 14: 集成测试 + 文档

## 常见问题

### Q: 服务启动失败怎么办？

A: 检查端口占用和磁盘空间：
```bash
# 检查端口占用
lsof -i :9000
lsof -i :5432
lsof -i :19530

# 检查磁盘空间
df -h
```

### Q: 如何重置所有数据？

A: 停止服务并删除卷：
```bash
docker-compose down -v
docker-compose up -d
```

### Q: 如何查看服务日志？

A: 使用docker-compose logs：
```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f minio
docker-compose logs -f postgres
docker-compose logs -f milvus
```

## 许可证

Apache 2.0

## 联系方式

如有问题，请提交 Issue。
