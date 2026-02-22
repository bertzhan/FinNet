# -*- coding: utf-8 -*-
"""
Base crawler module
Provides base classes and common components for all crawlers
"""

from .base_crawler import BaseCrawler, CrawlTask, CrawlResult
from .crawl_validation import validate_crawl_results_op

__all__ = ['BaseCrawler', 'CrawlTask', 'CrawlResult', 'validate_crawl_results_op']
