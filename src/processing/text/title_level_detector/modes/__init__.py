#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分块模式实现
"""

from .base import ChunkMode
from .chinese import ChineseChunkMode
from .english import EnglishChunkMode
from .simple import SimpleChunkMode

MODES = {
    "chinese": ChineseChunkMode(),
    "english": EnglishChunkMode(),
    "simple": SimpleChunkMode(),
}

__all__ = [
    "ChunkMode",
    "ChineseChunkMode",
    "EnglishChunkMode",
    "SimpleChunkMode",
    "MODES",
]
