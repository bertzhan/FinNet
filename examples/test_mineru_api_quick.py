# -*- coding: utf-8 -*-
"""
MinerU API 快速测试脚本
只解析 PDF 的前几页，用于快速验证 API 功能
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.processing.ai.pdf_parser import get_mineru_parser
from src.storage.object_store.minio_client import MinIOClient
import tempfile


def test_api_parse_first_pages():
    """测试 API 解析 PDF 前几页"""
    print("=" * 60)
    print("MinerU API 快速测试（只解析前3页）")
    print("=" * 60)
    print()
    
    # 1. 初始化解析器
    print("步骤1: 初始化解析器")
    print("-" * 60)
    try:
        parser = get_mineru_parser()
        print(f"✅ 解析器初始化成功")
        print(f"   API 地址: {parser.api_base}")
        print()
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 2. 查找 PDF 文件
    print("步骤2: 查找 MinIO 中的 PDF 文件")
    print("-" * 60)
    try:
        minio_client = MinIOClient()
        objects = list(minio_client.client.list_objects(
            minio_client.bucket,
            prefix="bronze/a_share/ipo_prospectus/",
            recursive=True
        ))
        
        # 找一个较小的 PDF 文件
        pdf_object = None
        for obj in objects:
            if obj.object_name.endswith('.pdf') and obj.size < 5 * 1024 * 1024:  # 小于 5MB
                pdf_object = obj
                break
        
        if not pdf_object:
            # 尝试找一个稍大的文件
            for obj in objects:
                if obj.object_name.endswith('.pdf'):
                    pdf_object = obj
                    break
        
        if not pdf_object:
            print("❌ MinIO 中没有找到 PDF 文件")
            return False
        
        print(f"✅ 找到 PDF 文件:")
        print(f"   路径: {pdf_object.object_name}")
        print(f"   大小: {pdf_object.size / 1024 / 1024:.2f} MB")
        print()
    except Exception as e:
        print(f"❌ 查找失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 3. 下载 PDF
    print("步骤3: 下载 PDF 到临时文件")
    print("-" * 60)
    temp_dir = tempfile.mkdtemp(prefix="mineru_api_test_")
    temp_pdf_path = os.path.join(temp_dir, Path(pdf_object.object_name).name)
    
    try:
        minio_client.download_file(
            object_name=pdf_object.object_name,
            file_path=temp_pdf_path
        )
        print(f"✅ PDF 已下载: {temp_pdf_path}")
        print(f"   文件大小: {os.path.getsize(temp_pdf_path)} bytes")
        print()
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 4. 调用 API 解析（只解析前3页）
    print("步骤4: 调用 MinerU API 解析（前3页）")
    print("-" * 60)
    print(f"   API 地址: {parser.api_base}/file_parse")
    print(f"   页面范围: 0-2 (前3页)")
    print(f"   这可能需要一些时间，请耐心等待...")
    print()
    
    try:
        # 只解析前3页（页码从0开始：0, 1, 2）
        parse_result = parser._parse_with_api(
            pdf_path=temp_pdf_path,
            start_page_id=0,
            end_page_id=2  # 包含第2页，所以是前3页
        )
        
        # 清理临时文件
        try:
            os.remove(temp_pdf_path)
            os.rmdir(temp_dir)
        except:
            pass
        
        if parse_result.get("success"):
            print(f"✅ API 解析成功！")
            print()
            print(f"解析结果:")
            print(f"   文本长度: {parse_result.get('text_length', 0)} 字符")
            print(f"   表格数量: {parse_result.get('tables_count', 0)}")
            print(f"   图片数量: {parse_result.get('images_count', 0)}")
            
            # 保存完整结果到本地文件
            output_dir = Path(project_root) / "downloads" / "mineru_test_results"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pdf_name = Path(pdf_object.object_name).stem
            
            # 保存完整 JSON 结果
            json_file = output_dir / f"{pdf_name}_parsed_{timestamp}.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(parse_result, f, ensure_ascii=False, indent=2)
            print(f"   ✅ 完整结果已保存到: {json_file}")
            
            # 保存 Markdown 文本
            markdown_file = output_dir / f"{pdf_name}_markdown_{timestamp}.md"
            markdown_content = parse_result.get('markdown', '')
            if markdown_content:
                with open(markdown_file, "w", encoding="utf-8") as f:
                    f.write(markdown_content)
                print(f"   ✅ Markdown 已保存到: {markdown_file}")
            
            # 保存纯文本
            text_file = output_dir / f"{pdf_name}_text_{timestamp}.txt"
            text_content = parse_result.get('text', '')
            if text_content:
                with open(text_file, "w", encoding="utf-8") as f:
                    f.write(text_content)
                print(f"   ✅ 纯文本已保存到: {text_file}")
            
            print()
            print(f"📁 结果文件位置:")
            print(f"   目录: {output_dir}")
            print(f"   JSON: {json_file.name}")
            if markdown_content:
                print(f"   Markdown: {markdown_file.name}")
            if text_content:
                print(f"   文本: {text_file.name}")
            
            # 显示文本预览
            text_preview = text_content[:500] if text_content else ""
            if text_preview:
                print()
                print(f"文本预览（前500字符）:")
                print("-" * 60)
                print(text_preview)
                if len(text_content) > 500:
                    print("...")
            
            # 显示表格信息
            tables = parse_result.get('tables', [])
            if tables:
                print()
                print(f"表格信息（前3个）:")
                for i, table in enumerate(tables[:3], 1):
                    print(f"   表格 {i}: 第 {table.get('page', 0)} 页")
                    table_md = table.get('markdown', '')[:100]
                    if table_md:
                        print(f"      {table_md}...")
            
            return True
        else:
            error_msg = parse_result.get('error_message', '未知错误')
            print(f"❌ API 解析失败: {error_msg}")
            return False
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_api_parse_first_pages()
    
    print()
    print("=" * 60)
    if success:
        print("✅ 测试通过！MinerU API 解析功能正常")
    else:
        print("❌ 测试失败，请检查错误信息")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
