"""
CORS配置模块

提供灵活的CORS配置选项，支持开发环境和生产环境的不同需求。
"""

from typing import List
import os

# CORS配置常量
class CORSConfig:
    """CORS配置类"""
    
    # 开发环境配置 - 允许所有来源
    DEVELOPMENT_ORIGINS = ["*"]
    
    # 生产环境默认配置 - 只允许特定域名
    PRODUCTION_ORIGINS = [
        "https://your-domain.com",
        "https://app.your-domain.com",
        "https://admin.your-domain.com"
    ]
    
    # 本地开发常用端口
    LOCAL_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:8080", 
        "http://localhost:5173",  # Vite默认端口
        "http://localhost:3001",  # React默认端口
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3001"
    ]
    
    @staticmethod
    def get_cors_origins() -> List[str]:
        """
        根据环境变量获取CORS允许的来源列表
        
        支持的配置方式：
        1. CORS_MODE=development - 允许所有来源（*）
        2. CORS_MODE=production - 使用生产环境配置
        3. CORS_MODE=local - 允许本地开发端口
        4. CORS_ORIGINS=http://example.com,http://app.example.com - 自定义来源
        
        Returns:
            List[str]: 允许的CORS来源列表
        """
        # 优先检查自定义CORS_ORIGINS环境变量
        custom_origins = os.getenv("CORS_ORIGINS")
        if custom_origins:
            # 支持逗号分隔的多个来源
            return [origin.strip() for origin in custom_origins.split(",")]
        
        # 检查CORS模式
        cors_mode = os.getenv("CORS_MODE", "development").lower()
        
        if cors_mode == "development":
            return CORSConfig.DEVELOPMENT_ORIGINS
        elif cors_mode == "production":
            return CORSConfig.PRODUCTION_ORIGINS
        elif cors_mode == "local":
            return CORSConfig.LOCAL_ORIGINS
        else:
            # 默认使用开发环境配置
            return CORSConfig.DEVELOPMENT_ORIGINS
    
    @staticmethod
    def get_cors_config() -> dict:
        """
        获取完整的CORS配置
        
        Returns:
            dict: CORS中间件配置参数
        """
        return {
            "allow_origins": CORSConfig.get_cors_origins(),
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"],
            "expose_headers": ["*"]
        }


# 预定义的CORS配置模板
CORS_TEMPLATES = {
    "permissive": {
        "allow_origins": ["*"],
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
        "expose_headers": ["*"]
    },
    "restrictive": {
        "allow_origins": ["https://your-domain.com"],
        "allow_credentials": False,
        "allow_methods": ["GET", "POST"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["X-Request-ID"]
    },
    "frontend_dev": {
        "allow_origins": [
            "http://localhost:3000",
            "http://localhost:8080",
            "http://localhost:5173"
        ],
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["*"],
        "expose_headers": ["*"]
    }
}