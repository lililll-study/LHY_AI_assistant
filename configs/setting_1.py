import os
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from typing import Optional
import dotenv

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 手动加载 .env 文件到系统环境变量
env_file_path = BASE_DIR / ".env"
if env_file_path.exists():
    print(f"🔧 正在加载 .env 文件：{env_file_path}")
    dotenv.load_dotenv(env_file_path, override=True)
    print(f"✅ .env 文件加载完成")
    # 验证加载结果
    test_key = os.environ.get('SILICONFLOW_API_KEY', '')
    print(f"   SILICONFLOW_API_KEY: '{test_key[:10] if test_key else '(空)'}...' (长度：{len(test_key)})")
else:
    print(f"⚠️ 警告：.env 文件不存在：{env_file_path}")

class Settings(BaseSettings):
    """
    应用配置管理类
    所有敏感信息从环境变量读取，提供默认值和验证
    """
    
    # ========== LLM 配置 ==========
    api_key: str = Field(
        default=str(os.environ['SILICONFLOW_API_KEY']),
        env="SILICONFLOW_API_KEY",
        description="硅基流动 API 密钥"
    )
    base_url: str = Field(
        default="https://api.siliconflow.cn/v1",
        env="LLM_BASE_URL",
        description="LLM API 基础 URL"
    )
    chat_model_name: str = Field(
        default="Qwen/Qwen2.5-72B-Instruct",
        env="LLM_MODEL_NAME",
        description="聊天模型名称"
    )
    
    # ========== 工具 API 配置 ==========
    weather_api_key: str = Field(
        default=str(os.environ['WEATHER_API_KEY']),
        env="WEATHER_API_KEY",
        description="心知天气API 密钥"
    )
    web_search_api_key: str = Field(
        default=str(os.environ['WEB_SEARCH_API_KEY']),
        env="WEB_SEARCH_API_KEY",
        description="SerpAPI 搜索密钥"
    )
    
    # ========== 数据库配置 ==========
    database_url: str = Field(
        default=f"sqlite:///{BASE_DIR}/database_server/data/info.db",
        env="DATABASE_URL",
        description="数据库连接 URL"
    )
    
    # ========== 路径配置 ==========
    temp_file_storage_dir: str = Field(
        default=str(BASE_DIR / "temp" / "data"),
        env="TEMP_FILE_STORAGE_DIR",
        description="临时文件存储目录"
    )
    media_dir: str = Field(
        default=str(BASE_DIR / "temp" / "medias"),
        env="MEDIA_DIR",
        description="媒体文件存储目录"
    )
    kb_dir: str = Field(
        default=str(BASE_DIR / "knowledgebases"),
        env="KB_DIR",
        description="知识库存储目录"
    )
    file_storage_dir: str = Field(
        default=str(BASE_DIR / "data"),
        env="FILE_STORAGE_DIR",
        description="文件存储目录"
    )
    embedding_model_path: str = Field(
        default=str(BASE_DIR / "models" / "AI-ModelScope" / "bge-large-zh-v1___5"),
        env="EMBEDDING_MODEL_PATH",
        description="Embedding 模型路径"
    )
    
    # ========== 运行时配置 ==========
    time_out: int = Field(
        default=60,
        env="REQUEST_TIMEOUT",
        ge=10,
        le=300,
        description="请求超时时间 (秒)"
    )
    media_url: str = Field(
        default="http://localhost:6605/media",
        env="MEDIA_URL",
        description="媒体文件访问 URL"
    )
    max_file_size_mb: int = Field(
        default=10,
        env="MAX_FILE_SIZE_MB",
        ge=1,
        le=100,
        description="上传文件最大大小 (MB)"
    )
    environment: str = Field(
        default="development",
        env="ENVIRONMENT",
        description="运行环境：development/production"
    )
    
    # # ========== 验证器 ==========
    # @field_validator('api_key')
    # def validate_api_key(cls, v):
    #     if not v or len(v) < 10:
    #         raise ValueError("API Key 无效，请检查环境变量 SILICONFLOW_API_KEY")
    #     return v
    
    # @field_validator('environment')
    # def validate_environment(cls, v):
    #     if v not in ['development', 'production']:
    #         raise ValueError("ENVIRONMENT 必须是 development 或 production")
    #     return v
    
    model_config = {
        "env_file": str(BASE_DIR / ".env"),  # 转为字符串路径
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": 'ignore'
    }


# 创建全局配置实例
try:
    print(f"\n{'=' * 60}")
    print("开始加载配置...")
    print(f"{'=' * 60}\n")
    
    settings = Settings()
    
    print(f"\n✅ 配置加载成功！")
    print(f"   API Key: '{settings.api_key}' (长度：{len(settings.api_key)})")
    print(f"   Base URL: {settings.base_url}")
    print(f"   模型名称：{settings.chat_model_name}")
    print(f"   环境：{settings.environment}")
    
    # 验证导出的变量
    print(f"\n📋 导出变量检查:")
    test_api_key = settings.api_key
    print(f"   settings.api_key: '{test_api_key[:10] if test_api_key else '(空)'}...' (长度：{len(test_api_key) if test_api_key else 0})")
    
except Exception as e:
    import traceback
    print(f"\n❌ 配置加载失败：{str(e)}")
    print(f"\n详细错误:")
    traceback.print_exc()
    exit(1)

# 为了向后兼容，导出旧变量名
chat_model_name = settings.chat_model_name
api_key = settings.api_key
base_url = settings.base_url
TIME_OUT = settings.time_out
TEMP_FILE_STORAGE_DIR = settings.temp_file_storage_dir
MEDIA_DIR = settings.media_dir
KB_DIR = settings.kb_dir
FILE_STORAGE_DIR = settings.file_storage_dir
embedding_model_path = settings.embedding_model_path
SQLALCHEMY_DATABASE = str(BASE_DIR / "database_server" / "data")
SQLALCHEMY_DATABASE_URI = settings.database_url

# 新增配置项
MEDIA_URL = settings.media_url
MAX_FILE_SIZE = settings.max_file_size_mb * 1024 * 1024  # 转换为字节
ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.docx', '.md', '.csv', '.json', '.py'}


