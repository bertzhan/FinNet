# -*- coding: utf-8 -*-
"""
文本分块服务集成测试
验证从 Silver 层读取、分块生成、数据库保存、Silver 层保存的完整流程
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.processing.text import get_text_chunker
from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.storage.metadata.models import Document, ParsedDocument
from src.common.constants import Market, DocType, DocumentStatus


class TestTextChunker:
    """文本分块服务测试类"""

    @pytest.fixture
    def chunker(self):
        """创建分块服务实例"""
        return get_text_chunker()

    @pytest.fixture
    def sample_document(self):
        """创建示例文档"""
        return {
            "id": uuid.uuid4(),
            "stock_code": "000001",
            "company_name": "测试公司",
            "market": Market.A_SHARE.value,
            "doc_type": DocType.QUARTERLY_REPORT.value,
            "year": 2023,
            "quarter": 3,
            "status": DocumentStatus.CRAWLED.value
        }

    @pytest.fixture
    def sample_parsed_document(self, sample_document):
        """创建示例解析文档"""
        return {
            "id": uuid.uuid4(),
            "document_id": sample_document["id"],
            "markdown_path": "silver/text_cleaned/a_share/quarterly_reports/2023/Q3/000001/document.md",
            "chunks_count": 0
        }

    @pytest.fixture
    def sample_markdown(self):
        """示例 Markdown 内容"""
        return """# 测试文档

## 第一节 重要提示

### 一、公司信息

这是公司信息的内容。

### 二、财务数据

这是财务数据的内容。

## 第二节 公司基本情况

### 一、公司简介

这是公司简介的内容。
"""

    def test_load_markdown_from_silver(self, chunker, sample_parsed_document, sample_markdown):
        """测试从 Silver 层加载 Markdown"""
        with patch.object(chunker.minio_client, 'download_file') as mock_download:
            with patch('builtins.open', create=True) as mock_open:
                mock_download.return_value = True
                mock_open.return_value.__enter__.return_value.read.return_value = sample_markdown
                
                content = chunker._load_markdown_from_silver(sample_parsed_document["markdown_path"])
                
                assert content == sample_markdown
                mock_download.assert_called_once()

    def test_generate_structure(self, chunker, sample_markdown):
        """测试生成文档结构"""
        structure = chunker._generate_structure(sample_markdown)
        
        assert structure is not None
        assert isinstance(structure, list)
        assert len(structure) > 0

    def test_generate_chunks(self, chunker, sample_markdown):
        """测试生成分块"""
        # 先生成结构
        structure = chunker._generate_structure(sample_markdown)
        assert structure is not None
        
        # 再生成分块
        chunks = chunker._generate_chunks(sample_markdown, structure)
        
        assert chunks is not None
        assert isinstance(chunks, list)
        assert len(chunks) > 0

    def test_save_structure_to_silver(self, chunker, sample_document):
        """测试保存 structure.json 到 Silver 层"""
        structure = [
            {
                "title": "第一节 重要提示",
                "level": 1,
                "heading_index": 0,
                "line_number": 3,
                "children": []
            }
        ]
        
        with patch.object(chunker.minio_client, 'upload_file') as mock_upload:
            mock_upload.return_value = True
            
            path, hash_value = chunker._save_structure_to_silver(
                structure=structure,
                document_id=sample_document["id"],
                market=Market(sample_document["market"]),
                doc_type=DocType(sample_document["doc_type"]),
                stock_code=sample_document["stock_code"],
                year=sample_document["year"],
                quarter=sample_document["quarter"]
            )
            
            assert path is not None
            assert hash_value is not None
            assert "_structure.json" in path
            mock_upload.assert_called_once()

    def test_save_chunks_to_silver(self, chunker, sample_document):
        """测试保存 chunks.json 到 Silver 层"""
        chunks = [
            {
                "chunk_id": 1,
                "chunk_index": 0,
                "title": "第一节 重要提示",
                "title_level": 1,
                "content": "这是内容",
                "start_line": 3,
                "end_line": 10,
                "parent_id": None
            }
        ]
        
        with patch.object(chunker.minio_client, 'upload_file') as mock_upload:
            mock_upload.return_value = True
            
            path, hash_value = chunker._save_chunks_to_silver(
                chunks=chunks,
                document_id=sample_document["id"],
                market=Market(sample_document["market"]),
                doc_type=DocType(sample_document["doc_type"]),
                stock_code=sample_document["stock_code"],
                year=sample_document["year"],
                quarter=sample_document["quarter"]
            )
            
            assert path is not None
            assert hash_value is not None
            assert "_chunks.json" in path
            mock_upload.assert_called_once()

    def test_chunk_document_integration(self, chunker, sample_document, sample_parsed_document, sample_markdown):
        """测试完整的分块流程（集成测试）"""
        # Mock 数据库查询
        with patch.object(crud, 'get_document_by_id') as mock_get_doc:
            with patch.object(crud, 'delete_document_chunks') as mock_delete:
                with patch.object(crud, 'create_document_chunks_batch') as mock_create:
                    with patch.object(crud, 'update_parsed_document_chunk_info') as mock_update:
                        # Mock MinIO 操作
                        with patch.object(chunker.minio_client, 'download_file') as mock_download:
                            with patch.object(chunker.minio_client, 'upload_file') as mock_upload:
                                # 设置 Mock 返回值
                                mock_doc = Mock()
                                mock_doc.id = sample_document["id"]
                                mock_doc.market = sample_document["market"]
                                mock_doc.doc_type = sample_document["doc_type"]
                                mock_doc.stock_code = sample_document["stock_code"]
                                mock_doc.year = sample_document["year"]
                                mock_doc.quarter = sample_document["quarter"]
                                mock_get_doc.return_value = mock_doc
                                
                                mock_parsed_doc = Mock()
                                mock_parsed_doc.id = sample_parsed_document["id"]
                                mock_parsed_doc.document_id = sample_document["id"]
                                mock_parsed_doc.markdown_path = sample_parsed_document["markdown_path"]
                                mock_parsed_doc.chunks_count = 0
                                
                                mock_download.return_value = True
                                mock_upload.return_value = True
                                
                                # Mock 文件读取
                                with patch('builtins.open', create=True) as mock_open:
                                    mock_open.return_value.__enter__.return_value.read.return_value = sample_markdown
                                    
                                    # Mock 数据库会话
                                    with patch.object(chunker.pg_client, 'get_session') as mock_session:
                                        mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_parsed_doc
                                        
                                        mock_create.return_value = [Mock(id=uuid.uuid4())]
                                        
                                        # 执行分块
                                        result = chunker.chunk_document(sample_document["id"])
                                        
                                        # 验证结果
                                        assert result["success"] is True
                                        assert "chunks_count" in result
                                        assert "structure_path" in result
                                        assert "chunks_path" in result

    def test_count_headings(self, chunker):
        """测试计算标题数量"""
        structure = [
            {
                "title": "第一节",
                "level": 1,
                "children": [
                    {
                        "title": "一、",
                        "level": 2,
                        "children": []
                    }
                ]
            }
        ]
        
        count = chunker._count_headings(structure)
        assert count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
