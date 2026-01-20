#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安装 Embedding 模型依赖（Python 版本）
"""

import subprocess
import sys


def run_command(cmd, description):
    """运行命令"""
    print(f"\n{description}...")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"✅ {description}成功")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description}失败: {e}")
        if e.stderr:
            print(e.stderr)
        return False


def check_package(package_name, import_name=None):
    """检查包是否已安装"""
    if import_name is None:
        import_name = package_name
    
    try:
        module = __import__(import_name)
        version = getattr(module, '__version__', 'unknown')
        print(f"✅ {package_name}: {version}")
        return True
    except ImportError:
        print(f"❌ {package_name}: 未安装")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("安装 Embedding 模型依赖")
    print("=" * 60)
    print()
    
    # 检查 Python 版本
    print("1. 检查 Python 环境...")
    print(f"   Python: {sys.version}")
    print()
    
    # 检查已安装的包
    print("2. 检查已安装的包...")
    packages = [
        ("torch", "torch"),
        ("transformers", "transformers"),
        ("sentence-transformers", "sentence_transformers"),
    ]
    
    installed = []
    missing = []
    for pkg_name, import_name in packages:
        if check_package(pkg_name, import_name):
            installed.append(pkg_name)
        else:
            missing.append(pkg_name)
    
    print()
    
    # 如果都已安装，直接返回
    if not missing:
        print("✅ 所有依赖已安装！")
        print()
        print("下一步：")
        print("1. 运行测试: python examples/test_vectorize_simple.py")
        print("2. 首次运行会自动下载模型")
        return
    
    # 安装缺失的包
    print(f"3. 安装缺失的包: {', '.join(missing)}...")
    print()
    
    # 优先安装 sentence-transformers（会自动安装依赖）
    if "sentence-transformers" in missing:
        success = run_command(
            "pip install sentence-transformers --no-cache-dir",
            "安装 sentence-transformers"
        )
        if success:
            missing.remove("sentence-transformers")
    
    # 安装其他缺失的包
    for pkg in missing:
        run_command(
            f"pip install {pkg} --no-cache-dir",
            f"安装 {pkg}"
        )
    
    # 再次验证
    print("\n4. 验证安装...")
    all_installed = True
    for pkg_name, import_name in packages:
        if not check_package(pkg_name, import_name):
            all_installed = False
    
    print()
    if all_installed:
        print("=" * 60)
        print("✅ 安装完成！")
        print("=" * 60)
        print()
        print("下一步：")
        print("1. 运行测试: python examples/test_vectorize_simple.py")
        print("2. 首次运行会自动下载模型（需要网络）")
        print("3. 模型会下载到: ~/.cache/huggingface/hub/")
        print()
    else:
        print("=" * 60)
        print("⚠️  部分包安装失败，请手动安装")
        print("=" * 60)
        print()
        print("手动安装命令：")
        print("  pip install sentence-transformers")
        print()


if __name__ == "__main__":
    main()
