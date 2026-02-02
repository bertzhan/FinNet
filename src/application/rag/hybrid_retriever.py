# -*- coding: utf-8 -*-
"""
混合检索器
结合向量检索和全文检索，使用 RRF 算法融合结果
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict

from src.application.rag.retriever import RetrievalResult
from src.common.logger import get_logger, LoggerMixin


class HybridRetriever(LoggerMixin):
    """
    混合检索器
    使用 RRF (Reciprocal Rank Fusion) 算法融合多个检索结果
    """

    def fuse_results(
        self,
        results_dict: Dict[str, List[RetrievalResult]],
        weights: Dict[str, float],
        top_k: int = 10,
        rrf_k: int = 60
    ) -> List[RetrievalResult]:
        """
        使用 RRF 算法融合多个检索结果

        Args:
            results_dict: 检索结果字典，键为检索类型（"vector", "fulltext"），值为结果列表
            weights: 权重字典，键为检索类型，值为权重（0-1）
            top_k: 返回数量
            rrf_k: RRF 参数（默认 60）

        Returns:
            融合后的检索结果列表

        Example:
            >>> retriever = HybridRetriever()
            >>> results = retriever.fuse_results(
            ...     results_dict={
            ...         "vector": vector_results,
            ...         "fulltext": fulltext_results
            ...     },
            ...     weights={"vector": 0.5, "fulltext": 0.5},
            ...     top_k=10
            ... )
        """
        if not results_dict:
            self.logger.warning("没有检索结果需要融合")
            return []

        # 归一化权重
        total_weight = sum(weights.values())
        if total_weight == 0:
            self.logger.warning("所有权重为 0，使用均匀权重")
            weights = {k: 1.0 / len(weights) for k in weights.keys()}
        else:
            weights = {k: v / total_weight for k, v in weights.items()}

        # 计算每个结果的 RRF 分数
        chunk_scores = defaultdict(float)
        chunk_results = {}

        for retrieval_type, results in results_dict.items():
            if not results:
                continue

            weight = weights.get(retrieval_type, 0.0)
            if weight == 0:
                continue

            # 计算 RRF 分数
            for rank, result in enumerate(results, start=1):
                chunk_id = result.chunk_id

                # RRF 分数：1 / (k + rank)
                rrf_score = 1.0 / (rrf_k + rank)

                # 加权 RRF 分数
                weighted_score = rrf_score * weight

                # 累加分数
                chunk_scores[chunk_id] += weighted_score

                # 保存结果（如果还没有保存，或者当前结果的原始分数更高）
                if chunk_id not in chunk_results:
                    chunk_results[chunk_id] = result
                else:
                    # 如果当前结果的原始分数更高，更新结果
                    if result.score > chunk_results[chunk_id].score:
                        chunk_results[chunk_id] = result

        # 按 RRF 分数排序
        sorted_chunks = sorted(
            chunk_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        # 构建最终结果
        fused_results = []
        for chunk_id, rrf_score in sorted_chunks:
            result = chunk_results[chunk_id]

            # 创建新的结果，使用融合后的分数
            fused_result = RetrievalResult(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                chunk_text=result.chunk_text,
                title=result.title,
                title_level=result.title_level,
                score=min(rrf_score, 1.0),  # 限制在 [0, 1] 范围内
                metadata={
                    **result.metadata,
                    "rrf_score": rrf_score,
                    "fusion_method": "rrf"
                }
            )
            fused_results.append(fused_result)

        self.logger.info(
            f"融合完成: 输入检索类型={list(results_dict.keys())}, "
            f"融合后结果数={len(fused_results)}"
        )

        return fused_results
