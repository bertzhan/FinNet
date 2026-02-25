#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分块测试脚本
命令行参数：document_path, mode
用法: python run_chunk.py <document_path> <mode>
  mode: chinese | english | simple
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# 添加项目根目录
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.processing.text.chunk_by_rules import StructureGenerator, ChunkGenerator


def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    parser = argparse.ArgumentParser(
        description="文档分块测试 (chunk_mode: chinese | english | simple)"
    )
    parser.add_argument(
        "document_path",
        type=str,
        help="文档路径，如 document.md",
    )
    parser.add_argument(
        "mode",
        type=str,
        choices=["chinese", "english", "simple"],
        help="分块模式: chinese(第X节/一、), english(PART/ITEM全大写), simple(一级无pattern)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default=None,
        help="输出目录，默认与文档同目录下的 chunk_output",
    )
    args = parser.parse_args()

    doc_path = Path(args.document_path)
    if not doc_path.exists():
        print(f"错误: 文件不存在: {doc_path}")
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else doc_path.parent / "chunk_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    struct_path = output_dir / "structure.json"
    chunks_json = output_dir / "chunks.json"
    chunks_md = output_dir / "chunks.md"

    print("=" * 60)
    print(f"文档: {doc_path}")
    print(f"模式: {args.mode}")
    print(f"输出: {output_dir}")
    print("=" * 60)

    t0 = time.perf_counter()
    sg = StructureGenerator(str(doc_path), chunk_mode=args.mode)
    sg.run(output_structure=str(struct_path))
    t1 = time.perf_counter()

    cg = ChunkGenerator(str(doc_path), str(struct_path), chunk_mode=args.mode)
    chunks = cg.run(output_json=str(chunks_json), output_md=str(chunks_md))
    t2 = time.perf_counter()

    print(f"\n运行时间: 总计 {t2-t0:.2f}s (structure: {t1-t0:.2f}s, chunks: {t2-t1:.2f}s)")
    print(f"输出: {struct_path}, {chunks_json}, {chunks_md}")
    print(f"共 {len(chunks)} 个块")


if __name__ == "__main__":
    main()
