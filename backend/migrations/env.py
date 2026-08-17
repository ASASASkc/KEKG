# -*- coding: utf-8 -*-
"""Alembic 迁移环境配置"""
from logging.config import fileConfig
from sqlalchemy import create_engine
from alembic import context
from app.config import Config

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 从配置构建 MySQL 连接 URL
_db_url = (
    f"mysql+pymysql://{Config.MYSQL_USER}:{Config.MYSQL_PASSWORD}"
    f"@{Config.MYSQL_HOST}:{Config.MYSQL_PORT}/{Config.MYSQL_DATABASE}"
    f"?charset=utf8mb4"
)
config.set_main_option('sqlalchemy.url', _db_url)

target_metadata = None  # 未使用 ORM，设为 None


def run_migrations_offline() -> None:
    """离线模式 — 生成 SQL 脚本"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式 — 直接执行 SQL"""
    connectable = create_engine(config.get_main_option("sqlalchemy.url"))

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
