# -*- coding: utf-8 -*-
"""
CNINFO 抓取调度器
功能：
- auto 模式：自动计算上一季度并调度抓取
- history 模式：批量抓取历史数据
"""

import os
import sys
import csv
import argparse
import subprocess
from datetime import datetime
from typing import List, Tuple


def get_previous_quarter(year: int, quarter: int) -> Tuple[int, int]:
    """
    计算上一季度
    
    Args:
        year: 当前年份
        quarter: 当前季度 (1-4)
    
    Returns:
        (prev_year, prev_quarter)
    """
    if quarter == 1:
        return year - 1, 4
    else:
        return year, quarter - 1


def calculate_current_quarter() -> Tuple[int, int]:
    """
    根据今日日期计算当前季度
    
    Returns:
        (year, quarter)
    """
    today = datetime.now()
    year = today.year
    month = today.month
    
    if month <= 3:
        quarter = 1
    elif month <= 6:
        quarter = 2
    elif month <= 9:
        quarter = 3
    else:
        quarter = 4
    
    return year, quarter


def generate_task_csv(company_list_path: str, year: int, quarter: int, output_path: str) -> int:
    """
    生成任务CSV文件
    
    Args:
        company_list_path: 公司列表CSV路径
        year: 目标年份
        quarter: 目标季度
        output_path: 输出CSV路径
    
    Returns:
        生成的任务数量
    """
    # 读取公司列表
    companies = []
    try:
        with open(company_list_path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = (row.get('code') or '').strip()
                name = (row.get('name') or '').strip()
                if code and name:
                    companies.append((code, name))
    except UnicodeDecodeError:
        # 尝试GBK编码
        with open(company_list_path, 'r', encoding='gbk', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = (row.get('code') or '').strip()
                name = (row.get('name') or '').strip()
                if code and name:
                    companies.append((code, name))
    
    if not companies:
        print(f"❌ 错误：未从 {company_list_path} 中读取到公司信息")
        return 0
    
    # 写入任务CSV
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['code', 'name', 'year', 'quarter'])
        for code, name in companies:
            writer.writerow([code, name, year, f'Q{quarter}'])
    
    print(f"✅ 生成任务文件：{output_path}（{len(companies)} 家公司）")
    return len(companies)


def run_fetcher(task_csv: str, output_root: str, fail_csv: str, workers: int = 6, old_pdf_dir: str = None):
    """
    调用抓取脚本

    Args:
        task_csv: 任务CSV路径
        output_root: 输出根目录
        fail_csv: 失败记录CSV路径
        workers: 并行进程数
        old_pdf_dir: 旧PDF目录路径
    """
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    fetcher_script = os.path.join(script_dir, 'main.py')
    
    if not os.path.exists(fetcher_script):
        print(f"❌ 错误：未找到抓取脚本 {fetcher_script}")
        sys.exit(1)
    
    # 构建命令
    cmd = [
        sys.executable,  # 使用当前Python解释器
        fetcher_script,
        '--input', task_csv,
        '--out', output_root,
        '--fail', fail_csv,
        '--workers', str(workers)
    ]

    # 如果指定了旧PDF目录，添加参数
    if old_pdf_dir:
        cmd.extend(['--old-pdf-dir', old_pdf_dir])
    
    print(f"\n🚀 开始抓取...")
    print(f"命令：{' '.join(cmd)}\n")
    
    # 执行命令
    try:
        result = subprocess.run(cmd, check=True)
        print(f"\n✅ 抓取完成（返回码：{result.returncode}）")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 抓取失败（返回码：{e.returncode}）")
        sys.exit(e.returncode)


def mode_auto(company_list: str, output_root: str, workers: int, old_pdf_dir: str = None):
    """
    自动模式：抓取上一季度和当前季度数据
    """
    print("=" * 60)
    print("模式：自动抓取上一季度 + 当前季度")
    print("=" * 60)

    # 计算当前季度
    curr_year, curr_quarter = calculate_current_quarter()
    print(f"当前季度：{curr_year} Q{curr_quarter}")

    # 计算目标季度（上一季）
    prev_year, prev_quarter = get_previous_quarter(curr_year, curr_quarter)
    print(f"上一季度：{prev_year} Q{prev_quarter}")

    # 需要抓取的两个季度
    quarters_to_fetch = [
        (prev_year, prev_quarter, "上一季度"),
        (curr_year, curr_quarter, "当前季度")
    ]

    print(f"\n总共需要抓取 {len(quarters_to_fetch)} 个季度\n")

    # 获取脚本所在目录
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # 逐个季度抓取
    for idx, (year, quarter, desc) in enumerate(quarters_to_fetch, 1):
        print("\n" + "=" * 60)
        print(f"进度：{idx}/{len(quarters_to_fetch)} - {year} Q{quarter} ({desc})")
        print("=" * 60)

        # 生成任务CSV（保存在脚本所在目录）
        task_csv = os.path.join(base_dir, f"tasks_{year}_Q{quarter}.csv")
        fail_csv = os.path.join(base_dir, f"fail_{year}_Q{quarter}.csv")

        count = generate_task_csv(company_list, year, quarter, task_csv)
        if count == 0:
            continue

        # 调用抓取脚本
        run_fetcher(task_csv, output_root, fail_csv, workers, old_pdf_dir)

        # 清理临时文件（可选）
        # if os.path.exists(task_csv):
        #     os.remove(task_csv)
        #     print(f"\n🗑️  已删除临时文件：{task_csv}")

    print("\n" + "=" * 60)
    print("✅ 所有季度抓取完成")
    print("=" * 60)


def mode_history(company_list: str, output_root: str, start_year: int, end_year: int,
                 workers: int, start_quarter: int = 1, end_quarter: int = 4, old_pdf_dir: str = None):
    """
    历史模式：批量抓取历史数据

    Args:
        start_quarter: 起始季度 (1-4)，默认从Q1开始
        end_quarter: 结束季度 (1-4)，默认到Q4结束
        old_pdf_dir: 旧PDF目录路径
    """
    print("=" * 60)
    print(f"模式：历史数据抓取 ({start_year} Q{start_quarter} - {end_year} Q{end_quarter})")
    print("=" * 60)
    
    # 获取脚本所在目录
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 生成所有需要抓取的季度
    quarters_to_fetch = []

    # 判断是否为"单季度跨年"模式（例如：只抓Q4，跨多年）
    single_quarter_mode = (start_quarter == end_quarter)

    for year in range(start_year, end_year + 1):
        if single_quarter_mode:
            # 单季度模式：所有年份都使用同一个季度
            quarters_to_fetch.append((year, start_quarter))
        else:
            # 多季度模式：确定当前年份的季度范围
            q_start = start_quarter if year == start_year else 1
            q_end = end_quarter if year == end_year else 4

            for quarter in range(q_start, q_end + 1):
                quarters_to_fetch.append((year, quarter))
    
    print(f"\n总共需要抓取 {len(quarters_to_fetch)} 个季度\n")
    
    # 逐个季度抓取
    for idx, (year, quarter) in enumerate(quarters_to_fetch, 1):
        print("\n" + "=" * 60)
        print(f"进度：{idx}/{len(quarters_to_fetch)} - {year} Q{quarter}")
        print("=" * 60)
        
        # 生成任务CSV（保存在脚本所在目录）
        task_csv = os.path.join(base_dir, f"tasks_{year}_Q{quarter}.csv")
        fail_csv = os.path.join(base_dir, f"fail_{year}_Q{quarter}.csv")
        
        count = generate_task_csv(company_list, year, quarter, task_csv)
        if count == 0:
            continue

        # 调用抓取脚本
        run_fetcher(task_csv, output_root, fail_csv, workers, old_pdf_dir)
        
        # 清理临时文件（可选）
        # if os.path.exists(task_csv):
        #     os.remove(task_csv)
        #     print(f"\n🗑️  已删除临时文件：{task_csv}")
    
    print("\n" + "=" * 60)
    print("✅ 所有季度抓取完成")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='CNINFO 抓取调度器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：
  # 自动模式（抓取上一季度 + 当前季度）
  python scheduler.py --company-list company_list.csv --out ./reports
  
  # 历史模式（抓取2018-2021年所有季度）
  python scheduler.py --mode history --start-year 2018 --end-year 2021 \\
                      --company-list company_list.csv --out ./reports
  
  # 只抓取2020年第一季度
  python scheduler.py --mode history --start-year 2020 --end-year 2020 \\
                      --start-quarter 1 --end-quarter 1 \\
                      --company-list company_list.csv --out ./reports
  
  # 抓取2020 Q3 到 2021 Q2
  python scheduler.py --mode history --start-year 2020 --end-year 2021 \\
                      --start-quarter 3 --end-quarter 2 \\
                      --company-list company_list.csv --out ./reports
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['auto', 'history'],
        default='auto',
        help='运行模式：auto=自动抓取上一季度+当前季度（默认），history=批量抓取历史数据'
    )
    
    parser.add_argument(
        '--company-list',
        required=True,
        help='公司列表CSV文件路径（至少包含 code, name 字段）'
    )
    
    parser.add_argument(
        '--out',
        required=True,
        help='输出根目录'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=6,
        help='并行进程数（默认：6）'
    )

    parser.add_argument(
        '--old-pdf-dir',
        type=str,
        default=None,
        help='旧PDF目录路径（如：D:\\Koplos_D\\cninfo_spider\\财报），用于跳过已下载的文件'
    )

    # history 模式专用参数
    parser.add_argument(
        '--start-year',
        type=int,
        help='起始年份（仅 history 模式）'
    )
    
    parser.add_argument(
        '--end-year',
        type=int,
        help='结束年份（仅 history 模式）'
    )
    
    parser.add_argument(
        '--start-quarter',
        type=int,
        choices=[1, 2, 3, 4],
        default=1,
        help='起始季度 1-4（仅 history 模式，默认：1）'
    )
    
    parser.add_argument(
        '--end-quarter',
        type=int,
        choices=[1, 2, 3, 4],
        default=4,
        help='结束季度 1-4（仅 history 模式，默认：4）'
    )
    
    args = parser.parse_args()
    
    # 检查文件是否存在
    if not os.path.exists(args.company_list):
        print(f"❌ 错误：公司列表文件不存在：{args.company_list}")
        sys.exit(1)
    
    # 创建输出目录
    os.makedirs(args.out, exist_ok=True)
    
    # 根据模式执行
    if args.mode == 'auto':
        mode_auto(args.company_list, args.out, args.workers, args.old_pdf_dir)
    elif args.mode == 'history':
        if not args.start_year or not args.end_year:
            print("❌ 错误：history 模式需要指定 --start-year 和 --end-year")
            sys.exit(1)
        if args.start_year > args.end_year:
            print("❌ 错误：起始年份不能大于结束年份")
            sys.exit(1)
        # 同一年份时，检查季度顺序
        if args.start_year == args.end_year and args.start_quarter > args.end_quarter:
            print("❌ 错误：同一年份内，起始季度不能大于结束季度")
            sys.exit(1)
        mode_history(args.company_list, args.out, args.start_year, args.end_year,
                    args.workers, args.start_quarter, args.end_quarter, args.old_pdf_dir)


if __name__ == '__main__':
    main()

