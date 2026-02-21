# -*- coding: utf-8 -*-
"""
akshare 辅助函数
用于获取港股公司详细信息
"""

from typing import Dict, Optional, Callable
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from src.common.logger import get_logger

logger = get_logger(__name__)


def get_security_profile_from_akshare(stock_code: str) -> Optional[Dict]:
    """
    使用 akshare 获取港股证券基本信息
    
    Args:
        stock_code: 股票代码（5位数字，如：00001）
        
    Returns:
        证券信息字典，如果获取失败则返回 None
    """
    try:
        import akshare as ak
        import pandas as pd
    except ImportError:
        logger.warning("akshare 未安装，跳过获取证券信息")
        return None
    
    try:
        # 调用 akshare API
        profile_df = ak.stock_hk_security_profile_em(symbol=stock_code)
        
        if profile_df is None or profile_df.empty:
            logger.debug(f"akshare security profile 返回空数据: {stock_code}")
            return None
        
        # 返回的是标准 DataFrame（1行多列），不是 key-value 格式
        result = {}
        
        # 提取各个字段
        if len(profile_df) > 0:
            row = profile_df.iloc[0]
            
            # 上市日期
            listed_date_str = row.get('上市日期')
            if listed_date_str:
                try:
                    listed_date = _parse_date(str(listed_date_str))
                    if listed_date:
                        result['listed_date'] = listed_date.date()
                except Exception as e:
                    logger.debug(f"解析上市日期失败: {e}")
            
            # 证券类型
            result['security_type'] = row.get('证券类型')
            
            # 发行价
            issue_price = row.get('发行价')
            if pd.notna(issue_price) and issue_price != '':
                try:
                    result['issue_price'] = float(issue_price)
                except (ValueError, TypeError):
                    pass
            
            # 发行量
            issue_amount = row.get('发行量(股)')
            if pd.notna(issue_amount) and issue_amount != '':
                try:
                    result['issue_amount'] = int(issue_amount)
                except (ValueError, TypeError):
                    pass
            
            # 每手股数
            lot_size = row.get('每手股数')
            if pd.notna(lot_size) and lot_size != '':
                try:
                    result['lot_size'] = int(lot_size)
                except (ValueError, TypeError):
                    pass
            
            # 每股面值
            par_value = row.get('每股面值')
            if pd.notna(par_value) and par_value != '':
                result['par_value'] = str(par_value).strip()
            
            # 交易所
            # exchange = row.get('交易所')  # 通常都是"香港交易所"，不需要存储
            
            # 板块
            # board = row.get('板块')  # 之前删除了 board 字段
            
            # 年结日
            fiscal_year_end = row.get('年结日')
            if pd.notna(fiscal_year_end) and fiscal_year_end != '':
                result['fiscal_year_end'] = str(fiscal_year_end).strip()
            
            # ISIN
            isin = row.get('ISIN（国际证券识别编码）')
            if pd.notna(isin) and isin != '':
                result['isin'] = str(isin).strip()
            
            # 是否沪港通标的
            sh_hk_connect = row.get('是否沪港通标的')
            if pd.notna(sh_hk_connect):
                result['is_sh_hk_connect'] = str(sh_hk_connect).strip() == '是'
            
            # 是否深港通标的
            sz_hk_connect = row.get('是否深港通标的')
            if pd.notna(sz_hk_connect):
                result['is_sz_hk_connect'] = str(sz_hk_connect).strip() == '是'
        
        # 过滤掉 None 值
        result = {k: v for k, v in result.items() if v is not None}
        
        logger.debug(f"成功获取证券信息: {stock_code}, 字段数: {len(result)}")
        return result
        
    except Exception as e:
        logger.warning(f"获取证券信息失败 ({stock_code}): {e}")
        return None


def get_company_profile_from_akshare(stock_code: str) -> Optional[Dict]:
    """
    使用 akshare 获取港股公司详细信息
    
    Args:
        stock_code: 股票代码（5位数字，如：00001）
        
    Returns:
        公司信息字典，如果获取失败则返回 None
    """
    try:
        import akshare as ak
    except ImportError:
        logger.warning("akshare 未安装，跳过获取公司详细信息")
        return None
    
    try:
        # 调用 akshare API
        profile_df = ak.stock_hk_company_profile_em(symbol=stock_code)
        
        if profile_df is None or profile_df.empty:
            logger.debug(f"akshare 返回空数据: {stock_code}")
            return None
        
        # akshare 返回的是标准 DataFrame，列名就是字段名
        # 格式：列名如 "公司名称"、"英文名称" 等，每行是一条记录
        profile_dict = {}
        
        if len(profile_df) > 0:
            # 取第一行数据
            row = profile_df.iloc[0]
            
            # 直接按列名访问数据
            for col_name in profile_df.columns:
                value = row.get(col_name)
                
                # 处理空值
                try:
                    import pandas as pd
                    if pd.isna(value) or value == '' or str(value).strip() == '':
                        continue
                except ImportError:
                    if value == '' or value is None:
                        continue
                
                profile_dict[col_name] = value
        
        # 根据实际返回的字段进行映射
        # 实际字段：公司名称、英文名称、注册地、注册地址、公司成立日期、所属行业、
        #           董事长、公司秘书、员工人数、办公地址、公司网址、E-MAIL、年结日、
        #           联系电话、核数师、传真、公司介绍
        result = {}
        
        # 公司名称信息
        result['org_name_cn'] = profile_dict.get('公司名称')
        result['org_name_en'] = profile_dict.get('英文名称')
        
        # 业务信息
        result['org_cn_introduction'] = profile_dict.get('公司介绍')
        
        # 联系信息
        result['telephone'] = profile_dict.get('联系电话')
        result['fax'] = profile_dict.get('传真')
        result['email'] = profile_dict.get('E-MAIL')
        result['org_website'] = profile_dict.get('公司网址')
        result['reg_location'] = profile_dict.get('注册地')  # 注册地（单独字段）
        result['reg_address'] = profile_dict.get('注册地址')  # 注册地址
        result['office_address_cn'] = profile_dict.get('办公地址')
        
        # 管理信息
        result['chairman'] = profile_dict.get('董事长')
        result['secretary'] = profile_dict.get('公司秘书')
        
        # 财务信息
        # 处理公司成立日期
        established_date_str = profile_dict.get('公司成立日期')
        if established_date_str:
            try:
                established_date = _parse_date(str(established_date_str))
                if established_date:
                    result['established_date'] = established_date.date()
            except Exception as e:
                logger.debug(f"解析公司成立日期失败: {e}")
        
        # 处理员工人数
        staff_num_str = profile_dict.get('员工人数')
        if staff_num_str:
            try:
                # 移除逗号和其他字符
                staff_num_str = str(staff_num_str).replace(',', '').replace('人', '').strip()
                if staff_num_str:
                    result['staff_num'] = int(float(staff_num_str))
            except Exception as e:
                logger.debug(f"解析员工人数失败: {e}")
        
        # 其他信息
        result['industry'] = profile_dict.get('所属行业')
        
        # 年结日（可以作为额外信息，但不在模型中）
        # fiscal_year_end = profile_dict.get('年结日')
        
        # 核数师（不在模型中，但可以记录）
        # auditor = profile_dict.get('核数师')
        
        # 调试：记录原始数据
        logger.debug(f"获取公司信息原始数据 ({stock_code}): profile_dict 有 {len(profile_dict)} 个字段")
        if len(profile_dict) > 0:
            logger.debug(f"profile_dict 的键: {list(profile_dict.keys())[:10]}")
        
        # 过滤掉 None 值
        result = {k: v for k, v in result.items() if v is not None}
        
        logger.debug(f"过滤后的结果 ({stock_code}): {len(result)} 个字段")
        if len(result) > 0:
            logger.debug(f"结果字段: {list(result.keys())[:10]}")
        
        return result
        
    except Exception as e:
        logger.warning(f"获取公司详细信息失败 ({stock_code}): {e}")
        return None


def _parse_date(date_str: str) -> Optional[datetime]:
    """
    解析日期字符串
    
    Args:
        date_str: 日期字符串（可能包含时间）
        
    Returns:
        datetime 对象，如果解析失败则返回 None
    """
    if not date_str:
        return None
    
    # 移除时间部分（如果有）
    date_str = str(date_str).strip().split(' ')[0]
    
    # 尝试多种日期格式
    date_formats = [
        '%Y-%m-%d',
        '%Y/%m/%d',
        '%d/%m/%Y',
        '%Y年%m月%d日',
        '%d-%m-%Y',
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    logger.debug(f"无法解析日期格式: {date_str}")
    return None


def batch_get_company_profiles(
    stock_codes: list,
    delay: float = 0.1,
    max_retries: int = 3,
    max_workers: int = 10,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Dict[str, Optional[Dict]]:
    """
    批量获取公司详细信息（并发版本）
    同时获取公司详细信息和证券基本信息
    
    Args:
        stock_codes: 股票代码列表
        delay: 请求间隔（秒），用于限流
        max_retries: 最大重试次数
        max_workers: 最大并发线程数（默认10）
        progress_callback: 进度回调函数，接收 (current, total, code) 参数
        
    Returns:
        {stock_code: profile_dict} 字典，包含公司详细信息和证券基本信息
    """
    results = {}
    total = len(stock_codes)
    completed_count = 0
    completed_lock = Lock()
    
    def fetch_with_retry(code: str) -> tuple[str, Optional[Dict]]:
        """获取单个公司信息，带重试机制"""
        retries = 0
        company_profile = None
        
        # 先获取公司详细信息
        while retries < max_retries:
            company_profile = get_company_profile_from_akshare(code)
            if company_profile is not None:
                break
            retries += 1
            if retries < max_retries:
                time.sleep(delay * retries)  # 指数退避
        
        # 初始化 profile 字典
        profile = {}
        
        # 如果获取成功，合并公司信息
        if company_profile is not None:
            if len(company_profile) > 0:
                profile.update(company_profile)
                logger.debug(f"获取公司详细信息成功 ({code}): {len(company_profile)} 个字段")
            else:
                logger.debug(f"获取公司详细信息为空 ({code}): 接口返回空字典")
        else:
            logger.warning(f"获取公司详细信息失败（已重试 {max_retries} 次）: {code}")
        
        # 再获取证券基本信息（失败不影响整体结果）
        retries = 0
        security_profile = None
        while retries < max_retries:
            security_profile = get_security_profile_from_akshare(code)
            if security_profile is not None:
                break
            retries += 1
            if retries < max_retries:
                time.sleep(delay * retries)
        
        # 合并证券信息
        if security_profile:
            profile.update(security_profile)
            logger.debug(f"获取证券信息成功 ({code}): {len(security_profile)} 个字段")
        
        # 返回结果（即使 profile 是空字典也要返回，表示获取成功但无数据）
        return (code, profile)
    
    # 使用线程池并发处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_code = {
            executor.submit(fetch_with_retry, code): code 
            for code in stock_codes
        }
        
        # 处理完成的任务
        for future in as_completed(future_to_code):
            code, profile = future.result()
            results[code] = profile
            
            # 更新进度
            with completed_lock:
                completed_count += 1
                if progress_callback:
                    progress_callback(completed_count, total, code)
            
            # 限流：每个线程完成后等待一小段时间
            time.sleep(delay)
    
    return results
