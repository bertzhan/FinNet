# 安装本地 Embedding 模型指南

## 概述

本文档说明如何安装和配置本地 Embedding 模型（BGE/BCE），用于向量化功能。

## 安装步骤

### 1. 安装依赖包

#### 方式1：使用 pip 安装（推荐）

```bash
# 安装 sentence-transformers（会自动安装 torch 等依赖）
pip install sentence-transformers

# 或者安装所有项目依赖
pip install -r requirements.txt
```

#### 方式2：使用 conda 安装（如果使用 Anaconda）

```bash
# 安装 PyTorch（CPU 版本）
conda install pytorch cpuonly -c pytorch

# 安装 sentence-transformers
pip install sentence-transformers
```

#### 方式3：分步安装（如果遇到问题）

```bash
# 1. 先安装 PyTorch（CPU 版本）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# 2. 安装 transformers
pip install transformers

# 3. 安装 sentence-transformers
pip install sentence-transformers

# 4. 安装其他依赖
pip install numpy scikit-learn
```

### 2. 验证安装

运行以下命令验证安装是否成功：

```bash
# 验证 Python 包
python -c "import torch; print(f'✅ PyTorch: {torch.__version__}')"
python -c "import transformers; print(f'✅ Transformers: {transformers.__version__}')"
python -c "import sentence_transformers; print(f'✅ Sentence-Transformers: {sentence_transformers.__version__}')"
```

### 3. 下载模型（首次使用）

模型会在首次使用时自动从 HuggingFace 下载。也可以手动下载：

#### 方式1：自动下载（推荐）

首次运行代码时，模型会自动下载：

```python
from src.processing.ai.embedding.bge_embedder import get_embedder

# 首次运行会自动下载模型到 ~/.cache/huggingface/
embedder = get_embedder()
```

#### 方式2：手动下载

```bash
# 使用 huggingface-cli 下载
pip install huggingface_hub
huggingface-cli download BAAI/bge-large-zh-v1.5
```

#### 方式3：使用 Python 代码下载

```python
from huggingface_hub import snapshot_download

# 下载 BGE 模型
snapshot_download(
    repo_id="BAAI/bge-large-zh-v1.5",
    local_dir="./models/bge-large-zh-v1.5"
)

# 下载 BCE 模型
snapshot_download(
    repo_id="maidalun1020/bce-embedding-base_v1",
    local_dir="./models/bce-embedding-base_v1"
)
```

### 4. 配置模型路径（可选）

如果需要使用本地已下载的模型，可以在 `.env` 文件中配置：

```bash
# .env 文件
EMBEDDING_MODEL=bge-large-zh-v1.5
EMBEDDING_DEVICE=cpu
EMBEDDING_BATCH_SIZE=32
EMBEDDING_DIM=1024

# 如果模型已下载到本地目录
BGE_MODEL_PATH=/path/to/local/models/bge-large-zh-v1.5
# 或使用 HuggingFace 模型ID（会自动下载）
BGE_MODEL_PATH=BAAI/bge-large-zh-v1.5
```

## 模型选择

### BGE-large-zh-v1.5（推荐）

- **维度**: 1024
- **特点**: 中文 SOTA，效果最好
- **模型大小**: ~1.3GB
- **适用场景**: 生产环境，对质量要求高

```bash
# 使用 BGE
EMBEDDING_MODEL=bge-large-zh-v1.5
BGE_MODEL_PATH=BAAI/bge-large-zh-v1.5
EMBEDDING_DIM=1024
```

### BCE-embedding-base（轻量）

- **维度**: 768
- **特点**: 轻量高效，速度快
- **模型大小**: ~400MB
- **适用场景**: 快速测试，资源受限环境

```bash
# 使用 BCE
EMBEDDING_MODEL=bce-embedding-base
BCE_MODEL_PATH=maidalun1020/bce-embedding-base_v1
EMBEDDING_DIM=768
```

## 测试安装

### 1. 简单测试

```python
from src.processing.ai.embedding.bge_embedder import get_embedder

# 初始化（首次会下载模型）
embedder = get_embedder(device="cpu")

# 测试单个文本
text = "这是一个测试文本"
vector = embedder.embed_text(text)
print(f"向量维度: {len(vector)}")
print(f"前5个值: {vector[:5]}")
```

### 2. 批量测试

```python
from src.processing.ai.embedding.bge_embedder import get_embedder

embedder = get_embedder(device="cpu")

texts = ["文本1", "文本2", "文本3"]
vectors = embedder.embed_batch(texts)
print(f"批量向量化成功，共 {len(vectors)} 个向量")
```

### 3. 运行完整测试

```bash
python examples/test_vectorize_simple.py
```

## 常见问题

### 1. 下载模型失败

**问题**: 网络连接问题，无法从 HuggingFace 下载

**解决**:
- 检查网络连接
- 使用镜像站点（如果在中国）
- 手动下载模型到本地

**使用镜像**:
```python
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'  # 使用镜像
```

### 2. 内存不足

**问题**: 模型太大，内存不足

**解决**:
- 使用更小的模型（BCE）
- 减小批量大小：`EMBEDDING_BATCH_SIZE=16`
- 使用 GPU（如果有）

### 3. 权限问题

**问题**: 无法写入缓存目录

**解决**:
```bash
# 设置缓存目录到有权限的位置
export HF_HOME=/path/to/cache
export TRANSFORMERS_CACHE=/path/to/cache
```

### 4. CPU 速度慢

**问题**: CPU 模式下向量化速度慢

**解决**:
- 这是正常的，CPU 模式比 GPU 慢很多
- 可以减小批量大小
- 考虑使用 GPU（如果有）

### 5. 模型路径问题

**问题**: 找不到模型文件

**解决**:
- 检查模型路径配置
- 确认模型已下载
- 使用 HuggingFace 模型 ID 而不是本地路径

## 性能优化

### CPU 模式优化

```python
# 减小批量大小
EMBEDDING_BATCH_SIZE=16

# 使用多进程（如果支持）
# 注意：sentence-transformers 默认使用多线程
```

### GPU 模式（如果有 GPU）

```bash
# 安装 GPU 版本的 PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# 配置使用 GPU
EMBEDDING_DEVICE=cuda
```

## 模型存储位置

默认情况下，模型会下载到：

- **Linux/Mac**: `~/.cache/huggingface/hub/`
- **Windows**: `C:\Users\<username>\.cache\huggingface\hub\`

可以通过环境变量修改：

```bash
export HF_HOME=/custom/path
```

## 下一步

安装完成后：

1. **运行测试**: `python examples/test_vectorize_simple.py`
2. **运行向量化作业**: 在 Dagster UI 中运行 `vectorize_documents_job`
3. **查看文档**: [向量化测试指南](VECTORIZE_TESTING_GUIDE.md)

## 参考

- [Sentence-Transformers 文档](https://www.sbert.net/)
- [BGE 模型页面](https://huggingface.co/BAAI/bge-large-zh-v1.5)
- [BCE 模型页面](https://huggingface.co/maidalun1020/bce-embedding-base_v1)
