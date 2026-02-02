# -*- coding: utf-8 -*-
"""
测试title_level字段
"""

import requests
import json

document_id = "5099ba9b-73f2-46a2-bb9c-ae1e2587aba9"
url = f"http://localhost:8000/api/v1/document/{document_id}/chunks"

response = requests.get(url)
data = response.json()

chunks = data['chunks']

# 统计title_level
levels = {}
for chunk in chunks:
    level = chunk.get('title_level')
    level_str = str(level) if level is not None else 'None'
    if level_str not in levels:
        levels[level_str] = []
    levels[level_str].append(chunk)

print("title_level统计:")
for level in sorted(levels.keys(), key=lambda x: (x == 'None', int(x) if x != 'None' else 0)):
    print(f"  Level {level}: {len(levels[level])} chunks")

print("\n不同title_level的示例:")
for level in sorted([k for k in levels.keys() if k != 'None'], key=int, reverse=True)[:5]:
    chunk = levels[level][0]
    title = chunk['title'][:60] if chunk['title'] else 'None'
    print(f"  Level {level}: {title}...")

print("\n前3个chunks的完整信息:")
for i, chunk in enumerate(chunks[:3], 1):
    print(f"\n{i}. chunk_id: {chunk['chunk_id']}")
    print(f"   title: {chunk['title'][:60] if chunk['title'] else 'None'}...")
    print(f"   title_level: {chunk.get('title_level')}")
    print(f"   parent_chunk_id: {chunk['parent_chunk_id'] or 'None'}")
