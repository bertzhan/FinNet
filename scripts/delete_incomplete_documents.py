#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
删除 document 表中所有下载不完整的记录

检查标准：
1. 文件在 MinIO 中不存在
2. 文件大小异常小（< 1KB）
3. PDF 文件不完整（缺少 %%EOF 标记）
"""

import sys
import os
from pathlib import Path
from typing import Tuple

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.metadata.postgres_client import get_postgres_client
from src.storage.metadata import crud
from src.storage.metadata.models import Document, ParsedDocument, ParseTask, DocumentChunk
from src.storage.object_store.minio_client import MinIOClient
from src.common.logger import get_logger

logger = get_logger(__name__)


def verify_pdf_completeness(file_data: bytes) -> bool:
    """
    验证 PDF 文件是否完整
    
    Args:
        file_data: PDF 文件数据
        
    Returns:
        是否完整
    """
    if len(file_data) < 1024:  # 至少 1KB
        return False
    
    # 检查是否以 PDF 头开始
    if not file_data.startswith(b"%PDF-"):
        return False
    
    # 检查是否包含 %%EOF 标记（PDF 文件必须以 %%EOF 结尾）
    # 读取最后 1KB 来查找 %%EOF
    tail = file_data[-1024:] if len(file_data) >= 1024 else file_data
    if b'%%EOF' not in tail:
        return False
    
    return True


def check_document_completeness(doc: Document, minio_client: MinIOClient) -> Tuple[bool, str]:
    """
    检查文档是否完整
    
    Args:
        doc: 文档对象
        minio_client: MinIO 客户端
        
    Returns:
        (是否完整, 原因)
    """
    # 1. 检查文件是否存在
    if not doc.minio_object_path:
        return False, "MinIO 路径为空"
    
    if not minio_client.file_exists(doc.minio_object_path):
        return False, "文件在 MinIO 中不存在"
    
    # 2. 下载文件并验证
    try:
        file_data = minio_client.download_file(doc.minio_object_path)
        if not file_data:
            return False, "无法下载文件"
        
        # 3. 检查文件大小
        file_size = len(file_data)
        if file_size < 1024:  # 至少 1KB
            return False, f"文件太小（{file_size} bytes）"
        
        # 4. 如果是 PDF 文件，验证完整性
        if doc.minio_object_path.lower().endswith('.pdf'):
            if not verify_pdf_completeness(file_data):
                return False, "PDF 文件不完整（缺少 %%EOF 标记或文件头无效）"
        
        return True, "文件完整"
        
    except Exception as e:
        return False, f"验证异常: {e}"


def delete_document_and_related_data(session, doc: Document, minio_client: MinIOClient) -> bool:
    """
    删除文档及其相关数据
    
    Args:
        session: 数据库会话
        doc: 文档对象
        minio_client: MinIO 客户端
        
    Returns:
        是否删除成功
    """
    try:
        document_id = doc.id
        
        # 1. 删除 MinIO 文件
        if doc.minio_object_path:
            try:
                if minio_client.file_exists(doc.minio_object_path):
                    minio_client.delete_file(doc.minio_object_path)
                    logger.debug(f"✅ 已删除 MinIO 文件: {doc.minio_object_path}")
            except Exception as e:
                logger.warning(f"删除 MinIO 文件失败: {doc.minio_object_path}, 错误: {e}")
        
        # 2. 删除相关数据（按依赖顺序）
        # 2.1 删除 DocumentChunk（如果有）
        chunks = session.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).all()
        for chunk in chunks:
            session.delete(chunk)
        if chunks:
            logger.debug(f"✅ 已删除 {len(chunks)} 个 DocumentChunk 记录")
        
        # 2.2 删除 Image（如果有，通过 ParsedDocument 关联）
        parsed_docs = session.query(ParsedDocument).filter(
            ParsedDocument.document_id == document_id
        ).all()
        for parsed_doc in parsed_docs:
            # 删除关联的 Image 记录
            from src.storage.metadata.models import Image
            images = session.query(Image).filter(
                Image.document_id == document_id
            ).all()
            for img in images:
                session.delete(img)
            if images:
                logger.debug(f"✅ 已删除 {len(images)} 个 Image 记录")
            
            # 删除 ParsedDocument 记录
            session.delete(parsed_doc)
        if parsed_docs:
            logger.debug(f"✅ 已删除 {len(parsed_docs)} 个 ParsedDocument 记录")
        
        # 2.3 删除 ParseTask（如果有）
        parse_tasks = session.query(ParseTask).filter(
            ParseTask.document_id == document_id
        ).all()
        for task in parse_tasks:
            session.delete(task)
        if parse_tasks:
            logger.debug(f"✅ 已删除 {len(parse_tasks)} 个 ParseTask 记录")
        
        # 3. 最后删除 Document 记录
        session.delete(doc)
        
        return True
        
    except Exception as e:
        logger.error(f"删除文档及相关数据失败: document_id={doc.id}, 错误: {e}", exc_info=True)
        return False


def find_and_delete_incomplete_documents(dry_run: bool = True, limit: int = None):
    """
    查找并删除不完整的文档
    
    Args:
        dry_run: 如果为 True，只检查不删除；如果为 False，实际删除
        limit: 限制检查的文档数量（None 表示检查所有）
    """
    logger.info("=" * 80)
    logger.info("查找并删除不完整的文档")
    logger.info("=" * 80)
    logger.info(f"模式: {'[DRY RUN] 只检查，不删除' if dry_run else '[实际删除] 将删除不完整的文档'}")
    if limit:
        logger.info(f"限制: 最多检查 {limit} 个文档")
    logger.info("")
    
    pg_client = get_postgres_client()
    minio_client = MinIOClient()
    
    incomplete_docs = []
    checked_count = 0
    
    try:
        with pg_client.get_session() as session:
            # 查询所有文档
            query = session.query(Document)
            if limit:
                query = query.limit(limit)
            
            all_docs = query.all()
            total_count = len(all_docs)
            logger.info(f"找到 {total_count} 个文档记录，开始检查...\n")
            
            for i, doc in enumerate(all_docs, 1):
                checked_count = i
                
                # 检查文档完整性
                is_complete, reason = check_document_completeness(doc, minio_client)
                
                if not is_complete:
                    incomplete_docs.append((doc, reason))
                    if len(incomplete_docs) <= 20:  # 只打印前20个
                        logger.warning(
                            f"❌ 不完整文档 {len(incomplete_docs)}: "
                            f"document_id={doc.id}, "
                            f"stock_code={doc.stock_code}, "
                            f"path={doc.minio_object_path}, "
                            f"原因: {reason}"
                        )
                
                if i % 100 == 0:
                    logger.info(f"已检查 {i}/{total_count} 个文档...")
            
            logger.info(f"\n检查完成！找到 {len(incomplete_docs)} 个不完整的文档\n")
            
            if not incomplete_docs:
                logger.info("✅ 所有文档都是完整的")
                return
            
            # 显示详细信息
            logger.info("不完整的文档详情（前30个）:")
            logger.info("-" * 80)
            for i, (doc, reason) in enumerate(incomplete_docs[:30], 1):
                logger.info(f"{i}. document_id: {doc.id}")
                logger.info(f"   stock_code: {doc.stock_code}")
                logger.info(f"   company_name: {doc.company_name}")
                logger.info(f"   market: {doc.market}, doc_type: {doc.doc_type}")
                logger.info(f"   year: {doc.year}, quarter: {doc.quarter}")
                logger.info(f"   status: {doc.status}")
                logger.info(f"   minio_object_path: {doc.minio_object_path}")
                logger.info(f"   file_size: {doc.file_size}")
                logger.info(f"   原因: {reason}")
                logger.info("")
            
            if len(incomplete_docs) > 30:
                logger.info(f"   ... 还有 {len(incomplete_docs) - 30} 个文档未显示\n")
            
            # 删除（如果不是 dry_run）
            if dry_run:
                logger.info("=" * 80)
                logger.info("⚠️  DRY RUN 模式：未进行实际删除")
                logger.info("=" * 80)
                logger.info(f"如果要实际删除，请运行:")
                logger.info(f"  python {Path(__file__).name} --delete")
            else:
                logger.info("开始删除不完整的文档...")
                deleted_count = 0
                failed_count = 0
                
                for doc, reason in incomplete_docs:
                    try:
                        success = delete_document_and_related_data(session, doc, minio_client)
                        if success:
                            deleted_count += 1
                            if deleted_count <= 10:
                                logger.info(
                                    f"✅ 已删除: document_id={doc.id}, "
                                    f"{doc.stock_code}, 原因: {reason}"
                                )
                        else:
                            failed_count += 1
                            logger.error(f"❌ 删除失败: document_id={doc.id}")
                    except Exception as e:
                        failed_count += 1
                        logger.error(
                            f"❌ 删除异常: document_id={doc.id}, "
                            f"错误: {e}", exc_info=True
                        )
                
                # 提交事务
                session.commit()
                
                logger.info("")
                logger.info("=" * 80)
                logger.info("删除完成！")
                logger.info("=" * 80)
                logger.info(f"成功删除: {deleted_count} 个文档")
                logger.info(f"删除失败: {failed_count} 个文档")
                logger.info(f"总计: {len(incomplete_docs)} 个不完整文档")
                logger.info(f"检查总数: {checked_count} 个文档")
                
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        raise


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="查找并删除不完整的文档记录")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="实际删除（默认只检查不删除）"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="限制检查的文档数量（用于测试）"
    )
    
    args = parser.parse_args()
    
    try:
        find_and_delete_incomplete_documents(dry_run=not args.delete, limit=args.limit)
    except Exception as e:
        logger.error(f"\n❌ 执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
