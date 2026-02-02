# -*- coding: utf-8 -*-
"""
FastAPI 主应用
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import retrieval, document
from src.common.config import api_config
from src.common.logger import get_logger

logger = get_logger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="FinNet API",
    description="FinNet 数据湖平台 API",
    version="1.0.0"
)


def custom_openapi():
    """自定义 OpenAPI schema，保留 schemas 但通过 Swagger UI 配置隐藏"""
    if app.openapi_schema:
        return app.openapi_schema
    
    from fastapi.openapi.utils import get_openapi
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # 保留 schemas，但添加 Swagger UI 配置来隐藏 Schemas 标签页
    # 注意：schemas 必须保留，因为 FastAPI 路由需要引用它们
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# 覆盖默认的 openapi 方法
app.openapi = custom_openapi


# 自定义 Swagger UI 配置，隐藏 Schemas 标签页
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """自定义 Swagger UI HTML，隐藏 Schemas 标签页"""
    from fastapi.openapi.docs import get_swagger_ui_html
    from fastapi.responses import HTMLResponse
    
    html_response = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
    )
    
    # 获取原始 HTML 内容
    html_content = html_response.body.decode("utf-8")
    
    # 注入 JavaScript 和 CSS 来隐藏 Schemas 标签页
    hide_schemas_code = """
    <style>
    /* 隐藏 Schemas 标签页 */
    .opblock-tag-section[data-tag="schemas"],
    .opblock-tag-section:has(.opblock-tag:contains("Schemas")),
    .opblock-tag-section:has([data-tag="schemas"]) {
        display: none !important;
    }
    </style>
    <script>
    (function() {
        // 方法1: 在 Swagger UI 初始化时配置
        if (window.ui) {
            // 监听 Swagger UI 初始化完成
            window.ui.onComplete(function() {
                hideSchemas();
            });
        }
        
        // 方法2: DOM 加载完成后隐藏
        function hideSchemas() {
            // 通过多种选择器查找并隐藏
            var selectors = [
                '.opblock-tag-section[data-tag="schemas"]',
                '.opblock-tag-section:has(.opblock-tag)',
                '[data-tag="schemas"]'
            ];
            
            selectors.forEach(function(selector) {
                var elements = document.querySelectorAll(selector);
                elements.forEach(function(el) {
                    var tagElement = el.querySelector('.opblock-tag');
                    if (tagElement && tagElement.textContent.trim() === 'Schemas') {
                        el.style.display = 'none';
                        el.remove(); // 直接移除元素
                    }
                });
            });
            
            // 查找所有标签页，移除 Schemas
            var allSections = document.querySelectorAll('.opblock-tag-section');
            allSections.forEach(function(section) {
                var tagElement = section.querySelector('.opblock-tag');
                if (tagElement && tagElement.textContent.trim() === 'Schemas') {
                    section.style.display = 'none';
                    section.remove();
                }
            });
        }
        
        // 页面加载时执行
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                setTimeout(hideSchemas, 500);
                setTimeout(hideSchemas, 1500);
                setTimeout(hideSchemas, 3000);
            });
        } else {
            setTimeout(hideSchemas, 500);
            setTimeout(hideSchemas, 1500);
            setTimeout(hideSchemas, 3000);
        }
        
        // 监听 DOM 变化，确保动态加载的内容也被隐藏
        var observer = new MutationObserver(function(mutations) {
            hideSchemas();
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
        
        // 定期检查并隐藏（防止动态加载）
        setInterval(hideSchemas, 2000);
    })();
    </script>
    """
    
    # 在 </head> 标签后插入样式和脚本
    html_content = html_content.replace('</head>', hide_schemas_code + '</head>')
    
    return HTMLResponse(content=html_content, status_code=200)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=api_config.CORS_ORIGINS.split(",") if api_config.CORS_ORIGINS != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(retrieval.router)  # 检索接口（向量检索、全文检索、图检索）
app.include_router(document.router)  # 文档查询接口


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
