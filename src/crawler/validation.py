# -*- coding: utf-8 -*-
"""
数据验证体系
按照plan.md设计实现全链路数据验证
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import os
import hashlib

from .base_crawler import CrawlResult, Market, DocType


class ValidationStage(Enum):
    """验证阶段"""
    INGESTION = "ingestion"  # 采集阶段
    BRONZE = "bronze"  # 入湖前验证
    SILVER = "silver"  # 内容验证


class ValidationLevel(Enum):
    """验证级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """验证结果"""
    stage: ValidationStage
    level: ValidationLevel
    passed: bool
    message: str
    details: Optional[Dict] = None


class DataValidator:
    """
    数据验证器
    实现plan.md中定义的全链路验证规则
    """

    def __init__(self, market: Market):
        """
        Args:
            market: 市场类型
        """
        self.market = market

    def validate_ingestion(self, result: CrawlResult) -> List[ValidationResult]:
        """
        采集阶段验证
        
        验证点：
        - 来源可信度
        - 响应完整性
        - 格式正确性
        - 时效性
        """
        results = []

        # 1. 来源可信度检查
        if not result.success:
            results.append(ValidationResult(
                stage=ValidationStage.INGESTION,
                level=ValidationLevel.ERROR,
                passed=False,
                message="数据采集失败",
                details={"error": result.error_message}
            ))
            return results

        # 2. 响应完整性检查
        if not result.file_path or not os.path.exists(result.file_path):
            results.append(ValidationResult(
                stage=ValidationStage.INGESTION,
                level=ValidationLevel.ERROR,
                passed=False,
                message="文件不存在"
            ))
            return results

        # 3. 格式正确性检查
        if not result.file_path.lower().endswith('.pdf'):
            results.append(ValidationResult(
                stage=ValidationStage.INGESTION,
                level=ValidationLevel.ERROR,
                passed=False,
                message="文件格式不是PDF"
            ))

        # 4. 时效性检查
        if result.metadata:
            crawl_time = result.metadata.get('crawl_time')
            if crawl_time:
                try:
                    crawl_dt = datetime.fromisoformat(crawl_time)
                    now = datetime.now()
                    # 检查是否在未来（不合理）
                    if crawl_dt > now:
                        results.append(ValidationResult(
                            stage=ValidationStage.INGESTION,
                            level=ValidationLevel.WARNING,
                            passed=True,
                            message="采集时间在未来，可能存在时间同步问题"
                        ))
                except:
                    pass

        # 所有检查通过
        if not any(not r.passed for r in results):
            results.append(ValidationResult(
                stage=ValidationStage.INGESTION,
                level=ValidationLevel.INFO,
                passed=True,
                message="采集阶段验证通过"
            ))

        return results

    def validate_bronze(self, result: CrawlResult) -> List[ValidationResult]:
        """
        入湖前验证（Bronze层）
        
        验证点：
        - 文件完整性（MD5/SHA256）
        - 格式验证（PDF可解析）
        - 元数据完整
        - 去重检查
        - 时间合理性
        - 文件大小
        """
        results = []

        if not result.file_path or not os.path.exists(result.file_path):
            results.append(ValidationResult(
                stage=ValidationStage.BRONZE,
                level=ValidationLevel.ERROR,
                passed=False,
                message="文件不存在"
            ))
            return results

        # 1. 文件完整性检查
        file_size = os.path.getsize(result.file_path)
        if file_size == 0:
            results.append(ValidationResult(
                stage=ValidationStage.BRONZE,
                level=ValidationLevel.ERROR,
                passed=False,
                message="文件大小为0"
            ))
            return results

        # 计算文件哈希（用于去重）
        try:
            with open(result.file_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            results.append(ValidationResult(
                stage=ValidationStage.BRONZE,
                level=ValidationLevel.ERROR,
                passed=False,
                message=f"文件读取失败: {str(e)}"
            ))
            return results

        # 2. 格式验证（PDF头检查）
        try:
            with open(result.file_path, 'rb') as f:
                header = f.read(5)
                if not header.startswith(b'%PDF-'):
                    results.append(ValidationResult(
                        stage=ValidationStage.BRONZE,
                        level=ValidationLevel.ERROR,
                        passed=False,
                        message="文件不是有效的PDF格式"
                    ))
                    return results
        except Exception as e:
            results.append(ValidationResult(
                stage=ValidationStage.BRONZE,
                level=ValidationLevel.ERROR,
                passed=False,
                message=f"PDF格式验证失败: {str(e)}"
            ))
            return results

        # 3. 元数据完整性检查
        required_fields = ['stock_code', 'company_name', 'year', 'market', 'doc_type']
        if result.metadata:
            missing_fields = [f for f in required_fields if f not in result.metadata]
            if missing_fields:
                results.append(ValidationResult(
                    stage=ValidationStage.BRONZE,
                    level=ValidationLevel.ERROR,
                    passed=False,
                    message=f"元数据缺少必填字段: {', '.join(missing_fields)}"
                ))
        else:
            results.append(ValidationResult(
                stage=ValidationStage.BRONZE,
                level=ValidationLevel.ERROR,
                passed=False,
                message="元数据为空"
            ))

        # 4. 时间合理性检查
        if result.metadata and 'year' in result.metadata:
            year = result.metadata['year']
            current_year = datetime.now().year
            # 检查年份是否在合理范围内（2000-未来5年）
            if year < 2000 or year > current_year + 5:
                results.append(ValidationResult(
                    stage=ValidationStage.BRONZE,
                    level=ValidationLevel.WARNING,
                    passed=True,
                    message=f"年份 {year} 超出合理范围"
                ))

        # 5. 文件大小检查
        max_size = 500 * 1024 * 1024  # 500MB
        if file_size > max_size:
            results.append(ValidationResult(
                stage=ValidationStage.BRONZE,
                level=ValidationLevel.WARNING,
                passed=True,
                message=f"文件大小 {file_size / 1024 / 1024:.2f}MB 超过建议值 500MB"
            ))

        # 所有检查通过
        if not any(not r.passed for r in results):
            results.append(ValidationResult(
                stage=ValidationStage.BRONZE,
                level=ValidationLevel.INFO,
                passed=True,
                message="Bronze层验证通过",
                details={"file_hash": file_hash, "file_size": file_size}
            ))

        return results

    def validate_silver(self, result: CrawlResult) -> List[ValidationResult]:
        """
        内容验证（Silver层前）
        
        验证点：
        - 编码正确性
        - 语言匹配
        - 内容非空
        - 关键字段提取
        """
        results = []

        if not result.file_path or not os.path.exists(result.file_path):
            results.append(ValidationResult(
                stage=ValidationStage.SILVER,
                level=ValidationLevel.ERROR,
                passed=False,
                message="文件不存在"
            ))
            return results

        # 注意：实际的内容验证需要PDF解析，这里只做基础检查
        # 完整的PDF解析和内容验证应该在后续处理阶段进行

        # 1. 文件可读性检查
        try:
            file_size = os.path.getsize(result.file_path)
            if file_size < 100:  # 至少100字节
                results.append(ValidationResult(
                    stage=ValidationStage.SILVER,
                    level=ValidationLevel.ERROR,
                    passed=False,
                    message="文件内容过少，可能损坏"
                ))
                return results
        except Exception as e:
            results.append(ValidationResult(
                stage=ValidationStage.SILVER,
                level=ValidationLevel.ERROR,
                passed=False,
                message=f"文件读取失败: {str(e)}"
            ))
            return results

        # 2. 语言匹配检查（根据市场类型）
        # 这里只是占位，实际需要PDF解析后检查文本语言
        if self.market == Market.A_SHARE:
            # A股文档应该是中文
            pass  # 实际实现需要PDF解析
        elif self.market == Market.US_STOCK:
            # 美股文档应该是英文
            pass  # 实际实现需要PDF解析

        # 所有检查通过
        results.append(ValidationResult(
            stage=ValidationStage.SILVER,
            level=ValidationLevel.INFO,
            passed=True,
            message="Silver层基础验证通过（完整内容验证需PDF解析）"
        ))

        return results

    def validate_all(self, result: CrawlResult) -> Dict[ValidationStage, List[ValidationResult]]:
        """
        执行全链路验证
        
        Args:
            result: 爬取结果
            
        Returns:
            各阶段的验证结果
        """
        return {
            ValidationStage.INGESTION: self.validate_ingestion(result),
            ValidationStage.BRONZE: self.validate_bronze(result),
            ValidationStage.SILVER: self.validate_silver(result),
        }
