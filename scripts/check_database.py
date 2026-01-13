#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查数据库记录"""

import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud

pg = get_postgres_client()
with pg.get_session() as session:
    docs = crud.get_documents_by_status(session, 'crawled', limit=5)
    print(f'✅ 数据库中有 {len(docs)} 条文档记录')
    for d in docs[:5]:
        print(f'  - {d.stock_code} {d.company_name} {d.year} Q{d.quarter} (ID: {d.id})')
        print(f'    MinIO: {d.minio_object_name}')
        print(f'    大小: {d.file_size:,} bytes')
