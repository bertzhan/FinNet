# -*- coding: utf-8 -*-
"""
MinerU 解析器简单测试脚本
用于快速测试基本功能
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.storage.object_store.minio_client import MinIOClient
from src.storage.metadata import get_postgres_client, crud
from src.common.constants import DocumentStatus


def check_minio_files():
    """检查 MinIO 中的文件"""
    print("=" * 60)
    print("检查 MinIO 文件")
    print("=" * 60)
    
    try:
        minio_client = MinIOClient()
        
        # 检查测试文档的路径
        test_paths = [
            "bronze/a_share/quarterly_reports/2023/Q3/000001/000001_2023_Q3.pdf",
            "bronze/a_share/ipo_prospectus/000001/000001_1989_10-03-1989.html",
            "bronze/a_share/ipo_prospectus/688111/688111_2019_13-11-2019.pdf",
        ]
        
        print("\n检查测试文档:")
        for path in test_paths:
            exists = minio_client.file_exists(path)
            status = "✅ 存在" if exists else "❌ 不存在"
            print(f"  {status}: {path}")
        
        # 列出所有 bronze 层的文件
        print("\n列出所有 bronze 层文件（前10个）:")
        objects = list(minio_client.client.list_objects(
            minio_client.bucket,
            prefix="bronze/a_share/",
            recursive=True
        ))
        
        print(f"  总共找到 {len(objects)} 个文件")
        for i, obj in enumerate(objects[:10], 1):
            print(f"  {i}. {obj.object_name} ({obj.size} bytes)")
        
        if len(objects) > 10:
            print(f"  ... 还有 {len(objects) - 10} 个文件")
        
        return True
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_mineru_installation():
    """检查 MinerU 安装"""
    print("\n" + "=" * 60)
    print("检查 MinerU 安装")
    print("=" * 60)
    
    try:
        import mineru
        print("✅ MinerU 已安装")
        print(f"   版本: {getattr(mineru, '__version__', '未知')}")
        return True
    except ImportError:
        print("❌ MinerU 未安装")
        print("   安装命令: pip install mineru")
        print("   或者配置 MINERU_API_BASE 使用 API 方式")
        return False
    except Exception as e:
        print(f"❌ 检查异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_with_local_pdf():
    """使用本地 PDF 测试（如果有）"""
    print("\n" + "=" * 60)
    print("测试本地 PDF 解析")
    print("=" * 60)
    
    # 检查是否有本地 PDF 文件
    local_pdfs = [
        "downloads/bronze/a_share/ipo_prospectus/*.pdf",
        "downloads/bronze/a_share/ipo_prospectus/*.json",
    ]
    
    import glob
    pdf_files = []
    for pattern in local_pdfs:
        pdf_files.extend(glob.glob(pattern))
    
    if not pdf_files:
        print("⚠️  没有找到本地 PDF 文件")
        print("   提示: 可以下载一个 PDF 到 downloads/ 目录进行测试")
        return True
    
    print(f"找到 {len(pdf_files)} 个本地文件")
    for f in pdf_files[:5]:
        print(f"  - {f}")
    
    # 如果有 PDF，可以测试解析
    try:
        from mineru.cli.common import do_parse
        from pathlib import Path
        import tempfile
        
        # 找一个 PDF 文件
        pdf_file = None
        for f in pdf_files:
            if f.endswith('.pdf'):
                pdf_file = f
                break
        
        if not pdf_file:
            print("⚠️  没有找到 PDF 文件")
            return True
        
        print(f"\n测试解析: {pdf_file}")
        
        # 读取 PDF
        with open(pdf_file, 'rb') as f:
            pdf_bytes = f.read()
        
        print(f"  PDF 大小: {len(pdf_bytes)} bytes")
        
        # 创建临时输出目录
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_name = Path(pdf_file).stem
            
            print(f"  输出目录: {temp_dir}")
            print("  开始解析...")
            
            do_parse(
                output_dir=temp_dir,
                pdf_file_names=[pdf_name],
                pdf_bytes_list=[pdf_bytes],
                p_lang_list=["ch"],
                backend="hybrid-auto-engine",
                parse_method="auto",
                formula_enable=True,
                table_enable=True,
                f_dump_md=True,
                f_dump_middle_json=True,
                f_dump_content_list=True,
            )
            
            # 检查输出文件
            output_files = list(Path(temp_dir).rglob("*"))
            print(f"\n  ✅ 解析完成！生成 {len(output_files)} 个文件")
            for f in output_files[:5]:
                print(f"    - {f.name}")
        
        return True
    except ImportError:
        print("⚠️  MinerU 未安装，跳过解析测试")
        return True
    except Exception as e:
        print(f"❌ 解析测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行简单测试"""
    print("\n" + "=" * 60)
    print("MinerU 解析器简单测试")
    print("=" * 60)
    print()
    
    results = []
    
    # 检查 MinerU 安装
    results.append(("MinerU 安装", check_mineru_installation()))
    
    # 检查 MinIO 文件
    results.append(("MinIO 文件", check_minio_files()))
    
    # 测试本地 PDF（如果 MinerU 已安装）
    if any(r[1] for r in results if r[0] == "MinerU 安装"):
        results.append(("本地 PDF 解析", test_with_local_pdf()))
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    total = len(results)
    passed = sum(1 for _, r in results if r)
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败")
    
    # 下一步建议
    print("\n" + "=" * 60)
    print("下一步建议")
    print("=" * 60)
    
    if not any(r[1] for r in results if r[0] == "MinerU 安装"):
        print("1. 安装 MinerU:")
        print("   pip install mineru")
        print("   或者配置 MINERU_API_BASE 使用 API 方式")
    
    if not any(r[1] for r in results if r[0] == "MinIO 文件"):
        print("2. 确保 MinIO 中有待解析的 PDF 文件")
        print("   可以运行爬虫任务先爬取一些文档")
    
    print("3. 运行完整测试:")
    print("   python tests/test_mineru_parser.py")


if __name__ == '__main__':
    main()
