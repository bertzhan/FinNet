# -*- coding: utf-8 -*-
"""
FastAPI 主应用
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import qa, openai
from src.common.config import api_config
from src.common.logger import get_logger

logger = get_logger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="FinNet API",
    description="FinNet 数据湖平台 API",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=api_config.CORS_ORIGINS.split(",") if api_config.CORS_ORIGINS != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(qa.router)
app.include_router(openai.router)  # OpenAI 兼容接口（用于 LibreChat）


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "FinNet API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """全局健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=api_config.API_HOST,
        port=api_config.API_PORT,
        reload=api_config.API_RELOAD
    )
