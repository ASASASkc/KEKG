import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    JWT_EXPIRE_DAYS = int(os.getenv('JWT_EXPIRE_DAYS', 7))

    # 管理员初始密码（仅首次创建时使用）
    ADMIN_DEFAULT_PASSWORD = os.getenv('ADMIN_DEFAULT_PASSWORD')

    # 邀请码
    DEFAULT_INVITE_CODE = os.getenv('DEFAULT_INVITE_CODE')

    # LLM 配置
    LLM_API_KEY = os.getenv('LLM_API_KEY')
    LLM_BASE_URL = os.getenv('LLM_BASE_URL')
    LLM_MODEL = os.getenv('LLM_MODEL')
    LLM_ENCODE_KEY = os.getenv('LLM_ENCODE_KEY')

    # CORS 白名单（逗号分隔）
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '')

    # MySQL 配置
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
    MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'kekg_db')

    # Neo4j 配置
    NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')

    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig
}

# 启动强校验：SECRET_KEY 缺失或过短时拒绝启动，防止弱密钥被离线伪造任意用户/管理员 token
if not Config.SECRET_KEY or len(Config.SECRET_KEY) < 16:
    raise RuntimeError(
        'SECRET_KEY 未配置或长度过短（<16 字符）。请在 .env 中设置强随机 SECRET_KEY（如 python -c "import secrets; print(secrets.token_hex(32))"）。'
    )
