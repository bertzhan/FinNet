# Embedding 模型测试指南

## 当前状态

✅ **sentence-transformers 已安装**

⚠️ **torch 权限问题**：Anaconda 环境中的 torch 库有权限限制

## 解决方案

### 方案1：修复 torch 权限（推荐）

```bash
# 检查文件权限
ls -la /Users/han/Anaconda3/anaconda3/lib/python3.12/site-packages/torch/_environment.py

# 修复权限
chmod 644 /Users/han/Anaconda3/anaconda3/lib/python3.12/site-packages/torch/_environment.py

# 或者修复整个 torch 目录
chmod -R u+r /Users/han/Anaconda3/anaconda3/lib/python3.12/site-packages/torch/
```

### 方案2：重新安装 torch

```bash
# 卸载并重新安装
pip uninstall torch
pip install torch

# 或使用 conda
conda uninstall pytorch
conda install pytorch cpuonly -c pytorch
```

### 方案3：使用虚拟环境（推荐用于生产）

```bash
# 创建新的虚拟环境
python -m venv venv_embedding

# 激活虚拟环境
source venv_embedding/bin/activate  # Mac/Linux
# 或
venv_embedding\Scripts\activate  # Windows

# 安装依赖
pip install sentence-transformers
```

## 测试步骤

### 1. 验证安装

在修复权限后，运行：

```bash
# 测试导入
python -c "import torch; print('✅ PyTorch OK')"
python -c "import sentence_transformers; print('✅ Sentence-Transformers OK')"
```

### 2. 快速测试 Embedder

```bash
python examples/test_embedder_quick.py
```

**预期输出**：
```
============================================================
Embedder 快速测试
============================================================

============================================================
1. 测试依赖导入
============================================================

✅ PyTorch: 2.x.x
✅ Transformers: 4.x.x
✅ Sentence-Transformers: 2.x.x

============================================================
2. 测试 Embedder 初始化
============================================================

正在初始化 Embedder（首次会下载模型，可能需要几分钟）...
✅ Embedder 初始化成功
   模型名称: bge-large-zh-v1.5
   向量维度: 1024
   设备: cpu

============================================================
3. 测试单个文本向量化
============================================================

✅ 向量化成功
   文本长度: 50 字符
   向量维度: 1024

============================================================
4. 测试批量向量化
============================================================

✅ 批量向量化成功
   输入文本数: 3
   输出向量数: 3
   每个向量维度: 1024
```

### 3. 完整测试

```bash
# 测试完整的向量化流程
python examples/test_vectorize_simple.py
```

## 首次运行说明

### 模型下载

首次运行 Embedder 时，会自动从 HuggingFace 下载模型：

- **模型**: BAAI/bge-large-zh-v1.5
- **大小**: 约 1.3GB
- **下载位置**: `~/.cache/huggingface/hub/`
- **时间**: 根据网络速度，可能需要几分钟到十几分钟

### 下载进度

模型下载时会显示进度条，例如：
```
Downloading (100%): 1.3GB/1.3GB [00:30<00:00, 45MB/s]
```

### 网络问题

如果下载失败，可以：

1. **使用镜像**（如果在中国）：
   ```python
   import os
   os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
   ```

2. **手动下载**：
   ```bash
   pip install huggingface_hub
   huggingface-cli download BAAI/bge-large-zh-v1.5
   ```

## 验证清单

- [ ] sentence-transformers 已安装
- [ ] torch 可以正常导入（无权限错误）
- [ ] Embedder 可以初始化
- [ ] 单个文本向量化成功
- [ ] 批量向量化成功
- [ ] 模型已下载（首次运行后）

## 常见问题

### Q1: 权限错误如何解决？

**A**: 使用方案1修复权限，或使用方案3创建新的虚拟环境。

### Q2: 模型下载很慢怎么办？

**A**: 
- 使用 HuggingFace 镜像
- 或手动下载后指定本地路径

### Q3: CPU 模式下速度很慢？

**A**: 这是正常的。CPU 模式比 GPU 慢很多，但功能完整。可以：
- 减小批量大小
- 使用更小的模型（BCE）
- 考虑使用 GPU（如果有）

### Q4: 内存不足？

**A**: 
- 使用更小的模型（BCE，768维）
- 减小批量大小：`EMBEDDING_BATCH_SIZE=16`
- 关闭其他程序释放内存

## 下一步

测试通过后：

1. **运行向量化作业**：
   ```bash
   # 在 Dagster UI 中运行
   dagster dev
   # 然后运行 vectorize_documents_job
   ```

2. **查看文档**：
   - [向量化测试指南](VECTORIZE_TESTING_GUIDE.md)
   - [安装指南](INSTALL_EMBEDDING_MODEL.md)

## 测试脚本

已创建的测试脚本：

- `examples/test_embedder_quick.py` - 快速测试 Embedder
- `examples/test_vectorize_simple.py` - 完整向量化测试
- `tests/test_vectorize_quick.py` - 快速测试（不依赖模型）
- `tests/test_vectorize_job.py` - 完整测试
