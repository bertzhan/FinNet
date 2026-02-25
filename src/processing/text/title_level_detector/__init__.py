#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标题级别检测器
基于规则的标题层级识别
"""

from .detector import TitleLevelDetector
from .modes import ChunkMode, ChineseChunkMode, EnglishChunkMode, SimpleChunkMode, MODES

__all__ = [
    'TitleLevelDetector',
    'ChunkMode',
    'ChineseChunkMode',
    'EnglishChunkMode',
    'SimpleChunkMode',
    'MODES',
]
