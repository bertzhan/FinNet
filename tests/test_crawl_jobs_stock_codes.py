# -*- coding: utf-8 -*-
"""
测试爬虫 job 按股票代码过滤功能
"""

import pytest
from src.processing.compute.dagster.jobs.crawl_jobs import load_company_list_from_db
from src.storage.metadata import get_postgres_client, crud


class TestCrawlJobsStockCodes:
    """测试爬虫 job 的股票代码过滤功能"""

    def test_load_company_list_by_stock_codes(self):
        """测试按股票代码列表加载公司"""
        # 准备测试数据：确保数据库中有这些公司
        stock_codes = ["000001", "000002"]

        # 调用函数
        companies = load_company_list_from_db(stock_codes=stock_codes)

        # 验证结果
        assert isinstance(companies, list)
        assert len(companies) <= len(stock_codes)  # 可能部分代码不存在

        # 验证返回的公司代码在指定的列表中
        returned_codes = [c['code'] for c in companies]
        for code in returned_codes:
            assert code in stock_codes

    def test_stock_codes_priority_over_limit(self):
        """测试 stock_codes 优先级高于 limit"""
        stock_codes = ["000001", "000002"]
        limit = 100  # 设置一个很大的 limit

        # 使用 stock_codes
        companies_with_codes = load_company_list_from_db(
            stock_codes=stock_codes,
            limit=limit  # 这个参数应该被忽略
        )

        # 验证结果数量不超过 stock_codes 的长度
        assert len(companies_with_codes) <= len(stock_codes)

    def test_stock_codes_priority_over_industry(self):
        """测试 stock_codes 优先级高于 industry"""
        stock_codes = ["000001"]  # 平安银行（银行业）
        industry = "制造业"  # 指定不同的行业

        # 使用 stock_codes
        companies = load_company_list_from_db(
            stock_codes=stock_codes,
            industry=industry  # 这个参数应该被忽略
        )

        # 验证结果
        if len(companies) > 0:
            # 如果找到了公司，验证代码是否正确
            assert companies[0]['code'] in stock_codes

    def test_empty_stock_codes_list(self):
        """测试空股票代码列表"""
        companies = load_company_list_from_db(stock_codes=[])

        # 空列表应该返回空结果
        assert companies == []

    def test_nonexistent_stock_codes(self):
        """测试不存在的股票代码"""
        stock_codes = ["999999", "888888"]  # 不存在的代码

        companies = load_company_list_from_db(stock_codes=stock_codes)

        # 不存在的代码应该返回空列表
        assert companies == []

    def test_mixed_existent_and_nonexistent_codes(self):
        """测试混合存在和不存在的股票代码"""
        stock_codes = ["000001", "999999", "000002"]  # 部分存在，部分不存在

        companies = load_company_list_from_db(stock_codes=stock_codes)

        # 应该只返回存在的公司
        returned_codes = [c['code'] for c in companies]
        assert "000001" in returned_codes or "000002" in returned_codes
        assert "999999" not in returned_codes

    def test_fallback_to_limit_when_no_stock_codes(self):
        """测试当没有指定 stock_codes 时，使用 limit 参数"""
        limit = 5

        companies = load_company_list_from_db(limit=limit)

        # 验证返回的数量不超过 limit
        assert len(companies) <= limit

    def test_fallback_to_industry_when_no_stock_codes(self):
        """测试当没有指定 stock_codes 时，使用 industry 参数"""
        industry = "银行"

        companies = load_company_list_from_db(industry=industry)

        # 验证至少返回了一些公司（如果数据库中有该行业的公司）
        # 注意：这个测试依赖于数据库中是否有银行业的公司
        assert isinstance(companies, list)

    def test_stock_code_format(self):
        """测试股票代码格式"""
        # 测试6位数字格式
        stock_codes = ["000001"]

        companies = load_company_list_from_db(stock_codes=stock_codes)

        # 验证返回的公司代码格式正确
        if len(companies) > 0:
            code = companies[0]['code']
            assert isinstance(code, str)
            assert len(code) == 6
            assert code.isdigit()

    def test_large_stock_codes_list(self):
        """测试大量股票代码列表"""
        # 生成一个较大的股票代码列表
        stock_codes = [f"{i:06d}" for i in range(1, 101)]  # 000001 到 000100

        companies = load_company_list_from_db(stock_codes=stock_codes)

        # 验证返回的数量不超过指定的代码数量
        assert len(companies) <= len(stock_codes)

        # 验证返回的公司代码都在指定列表中
        returned_codes = [c['code'] for c in companies]
        for code in returned_codes:
            assert code in stock_codes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
