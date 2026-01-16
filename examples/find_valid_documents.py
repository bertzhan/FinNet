# -*- coding: utf-8 -*-
"""查找有效的待解析文档"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.common.constants import DocumentStatus
from src.storage.object_store.minio_client import MinIOClient

pg = get_postgres_client()
minio = MinIOClient()

with pg.get_session() as session:
    docs = crud.get_documents_by_status(session, DocumentStatus.CRAWLED.value, limit=20)
    print(f'找到 {len(docs)} 个已爬取的文档')
    
    valid_docs = []
    for d in docs:
        if minio.file_exists(d.minio_object_name):
            valid_docs.append(d)
    
    print(f'其中 {len(valid_docs)} 个文件在 MinIO 中存在')
    print('\n有效文档列表:')
    for d in valid_docs[:10]:
        print(f'  document_id={d.id}: {d.stock_code} - {d.minio_object_name}')
