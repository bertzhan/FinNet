#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于规则的文档结构识别和分块方案
向后兼容：从 chunk 包导出
"""

import logging
import sys
from pathlib import Path

from src.processing.text.chunk import StructureGenerator, ChunkGenerator

__all__ = ['StructureGenerator', 'ChunkGenerator']

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    base_dir = Path(__file__).parent
    doc_path = base_dir / 'document1.md'
    if len(sys.argv) > 1:
        doc_path = Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else 'chinese'
    output_dir = doc_path.parent / "chunk_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    struct_path = output_dir / "structure.json"
    sg = StructureGenerator(str(doc_path), chunk_mode=mode)
    sg.run(output_structure=str(struct_path))
    cg = ChunkGenerator(str(doc_path), str(struct_path), chunk_mode=mode)
    cg.run(output_json=str(output_dir / "chunks.json"), output_md=str(output_dir / "chunks.md"))
