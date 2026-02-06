# -*- coding: utf-8 -*-
"""
单独测试 get_company_profile_from_akshare 接口
查看实际返回的数据和字段映射
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ingestion.hk_stock.utils.akshare_helper import get_company_profile_from_akshare
import logging

# 设置日志级别为 DEBUG
logging.basicConfig(level=logging.DEBUG)

def test_get_company_profile():
    """测试获取公司详细信息"""
    test_codes = ["00001", "00700", "09988"]  # 长和、腾讯、阿里
    
    print("=" * 80)
    print("测试 get_company_profile_from_akshare 接口")
    print("=" * 80)
    
    for code in test_codes:
        print(f"\n{'='*80}")
        print(f"测试股票代码: {code}")
        print(f"{'='*80}")
        
        try:
            result = get_company_profile_from_akshare(code)
            
            if result is None:
                print(f"❌ 返回 None")
                continue
            
            if len(result) == 0:
                print(f"⚠️  返回空字典（无数据）")
                continue
            
            print(f"\n✅ 成功获取数据，共 {len(result)} 个字段:")
            print(f"\n字段详情:")
            for key, value in result.items():
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:100] + "..."
                print(f"  {key:25s} = {value_str}")
            
            # 检查关键字段
            print(f"\n关键字段检查:")
            key_fields = [
                'org_name_cn', 'org_name_en', 'reg_location', 'reg_address',
                'telephone', 'email', 'chairman', 'secretary', 
                'established_date', 'staff_num', 'industry'
            ]
            for field in key_fields:
                if field in result:
                    print(f"  ✅ {field}: {result[field]}")
                else:
                    print(f"  ❌ {field}: 缺失")
                    
        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_get_company_profile()
