# -*- coding: utf-8 -*-
"""
MinerU 解析器直接测试
使用 MinIO 中实际存在的 PDF 文件进行测试
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.processing.ai.pdf_parser import get_mineru_parser
from src.storage.object_store.minio_client import MinIOClient
import tempfile


def test_parse_minio_pdf():
    """测试解析 MinIO 中的 PDF 文件"""
    print("=" * 60)
    print("MinerU 解析器直接测试")
    print("=" * 60)
    print()
    
    # 1. 查找 MinIO 中的 PDF 文件
    print("步骤1: 查找 MinIO 中的 PDF 文件")
    print("-" * 60)
    
    minio_client = MinIOClient()
    objects = list(minio_client.client.list_objects(
        minio_client.bucket,
        prefix="bronze/a_share/ipo_prospectus/",
        recursive=True
    ))
    
    # 找一个较小的 PDF 文件（便于快速测试）
    pdf_object = None
    for obj in objects:
        if obj.object_name.endswith('.pdf') and obj.size < 10 * 1024 * 1024:  # 小于 10MB
            pdf_object = obj
            break
    
    if not pdf_object:
        print("⚠️  没有找到合适的 PDF 文件")
        return False
    
    print(f"✅ 找到 PDF 文件:")
    print(f"   路径: {pdf_object.object_name}")
    print(f"   大小: {pdf_object.size / 1024 / 1024:.2f} MB")
    print()
    
    # 2. 下载 PDF 到临时文件
    print("步骤2: 下载 PDF 到临时文件")
    print("-" * 60)
    
    temp_dir = tempfile.mkdtemp(prefix="mineru_test_")
    temp_pdf_path = os.path.join(temp_dir, Path(pdf_object.object_name).name)
    
    try:
        minio_client.download_file(
            object_name=pdf_object.object_name,
            file_path=temp_pdf_path
        )
        print(f"✅ PDF 已下载到: {temp_pdf_path}")
        print(f"   文件大小: {os.path.getsize(temp_pdf_path)} bytes")
        print()
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 3. 测试 MinerU 解析
    print("步骤3: 使用 MinerU 解析 PDF")
    print("-" * 60)
    
    try:
        from mineru.cli.common import do_parse
        
        pdf_file_name = Path(temp_pdf_path).stem
        
        # 读取 PDF 字节
        with open(temp_pdf_path, "rb") as f:
            pdf_bytes = f.read()
        
        print(f"   开始解析... (文件: {pdf_file_name})")
        print(f"   这可能需要一些时间，请耐心等待...")
        
        # 创建输出目录
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        
        # 调用 MinerU
        # 先尝试使用 pipeline backend（不需要 VLM 依赖）
        # 如果失败，再尝试 hybrid-auto-engine
        try:
            backend = "pipeline"
            print(f"   使用 backend: {backend}")
            do_parse(
                output_dir=output_dir,
                pdf_file_names=[pdf_file_name],
                pdf_bytes_list=[pdf_bytes],
                p_lang_list=["ch"],
                backend=backend,
                parse_method="auto",
                formula_enable=True,
                table_enable=True,
                f_dump_md=True,
                f_dump_middle_json=True,
                f_dump_content_list=True,
                f_dump_model_output=False,
                f_dump_orig_pdf=False,
                f_draw_layout_bbox=False,
                f_draw_span_bbox=False,
            )
        except Exception as e:
            print(f"   pipeline backend 失败: {e}")
            print(f"   尝试使用 hybrid-auto-engine backend...")
            backend = "hybrid-auto-engine"
            do_parse(
                output_dir=output_dir,
                pdf_file_names=[pdf_file_name],
                pdf_bytes_list=[pdf_bytes],
                p_lang_list=["ch"],
                backend=backend,
                parse_method="auto",
                formula_enable=True,
                table_enable=True,
                f_dump_md=True,
                f_dump_middle_json=True,
                f_dump_content_list=True,
                f_dump_model_output=False,
                f_dump_orig_pdf=False,
                f_draw_layout_bbox=False,
                f_draw_span_bbox=False,
            )
        
        print("✅ MinerU 解析完成！")
        print()
        
        # 4. 检查输出文件
        print("步骤4: 检查解析结果")
        print("-" * 60)
        
        output_path = Path(output_dir)
        
        # 查找实际输出目录
        pdf_output_dir = output_path / pdf_file_name
        if pdf_output_dir.exists():
            subdirs = [d for d in pdf_output_dir.iterdir() if d.is_dir()]
            if subdirs:
                result_dir = subdirs[0]
                print(f"   输出目录: {result_dir}")
                
                # 检查文件
                md_file = result_dir / f"{pdf_file_name}.md"
                json_file = result_dir / f"{pdf_file_name}_middle.json"
                content_list_file = result_dir / f"{pdf_file_name}_content_list.json"
                
                files_found = []
                if md_file.exists():
                    md_size = md_file.stat().st_size
                    files_found.append(f"Markdown ({md_size} bytes)")
                if json_file.exists():
                    json_size = json_file.stat().st_size
                    files_found.append(f"Middle JSON ({json_size} bytes)")
                if content_list_file.exists():
                    content_size = content_list_file.stat().st_size
                    files_found.append(f"Content List ({content_size} bytes)")
                
                if files_found:
                    print(f"   ✅ 找到 {len(files_found)} 个输出文件:")
                    for f in files_found:
                        print(f"      - {f}")
                    
                    # 读取并显示部分内容
                    if md_file.exists():
                        with open(md_file, "r", encoding="utf-8") as f:
                            md_content = f.read()
                        print(f"\n   Markdown 预览 (前500字符):")
                        print("   " + "-" * 56)
                        preview = md_content[:500].replace("\n", "\n   ")
                        print(f"   {preview}")
                        if len(md_content) > 500:
                            print("   ...")
                    
                    return True
                else:
                    print("   ⚠️  没有找到预期的输出文件")
                    return False
            else:
                print(f"   ⚠️  输出目录中没有子目录: {pdf_output_dir}")
                return False
        else:
            print(f"   ⚠️  PDF 输出目录不存在: {pdf_output_dir}")
            return False
            
    except ImportError as e:
        print(f"❌ MinerU 导入失败: {e}")
        print("   请确保已安装: pip install mineru")
        return False
    except Exception as e:
        print(f"❌ 解析失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理临时文件
        try:
            import shutil
            shutil.rmtree(temp_dir)
            print(f"\n✅ 已清理临时文件: {temp_dir}")
        except Exception as e:
            print(f"\n⚠️  清理临时文件失败: {e}")


if __name__ == '__main__':
    success = test_parse_minio_pdf()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 测试通过！MinerU 解析器工作正常")
    else:
        print("❌ 测试失败，请检查错误信息")
    print("=" * 60)
