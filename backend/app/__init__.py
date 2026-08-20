# -*- coding: utf-8 -*-
"""Flask 应用工厂"""
from flask import Flask, request, g, current_app
from flask_cors import CORS
from .config import Config, config_map
from .repositories.sql_repo import sql_repo
from .repositories.graph_repo import graph_repo
from .utils.auth import require_admin
import os
import uuid
import logging


def create_app(env='default'):
    app = Flask(__name__)
    app.config.from_object(config_map.get(env, config_map['default']))
    # 请求体大小限制 5MB
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

    # ── 请求 ID 追踪 ──────────────────────────
    class _RequestIDFilter(logging.Filter):
        def filter(self, record):
            from flask import has_request_context, request as req
            try:
                if has_request_context():
                    record.request_id = req.environ.get('x_request_id', '-')
                else:
                    record.request_id = '-'
            except Exception:
                record.request_id = '-'
            return True

    # 为 app logger 和 root logger 注入 request_id
    _rid_filter = _RequestIDFilter()
    app.logger.addFilter(_rid_filter)
    # 修改日志格式，在每行前面加上 [request_id]
    for handler in app.logger.handlers:
        handler.addFilter(_rid_filter)
    logging.root.addFilter(_rid_filter)
    for handler in logging.root.handlers:
        handler.addFilter(_rid_filter)

    @app.before_request
    def _inject_request_id():
        req_id = request.headers.get('X-Request-ID') or uuid.uuid4().hex[:12]
        g.request_id = req_id
        request.environ['x_request_id'] = req_id

    @app.after_request
    def _add_request_id_header(response):
        try:
            req_id = getattr(g, 'request_id', None)
            if req_id:
                response.headers['X-Request-ID'] = req_id
        except Exception:
            pass
        return response

    # CORS 配置 — 从 .env 白名单读取，为空则仅允许本地开发
    cors_origins_raw = app.config.get('CORS_ORIGINS', '')
    if cors_origins_raw:
        origins = [o.strip() for o in cors_origins_raw.split(',') if o.strip()]
    else:
        origins = ['http://localhost:3000', 'http://127.0.0.1:3000']
    CORS(app, resources={r"/api/v1/*": {"origins": origins}})

    # 确保 data 目录存在
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(data_dir, exist_ok=True)

    # 初始化存储层 — MySQL 唯一后端
    _init_storage(app)

    # ── 注册蓝图 ──────────────────────────────
    from .routes.knowledge_routes import knowledge_bp

    @app.route('/api/v1/health')
    def health():
        """健康检查"""
        from .repositories.sql_repo import sql_repo
        db_ok = False
        try:
            sql_repo.execute_query("SELECT 1")
            db_ok = True
        except Exception:
            pass
        return {
            'code': 200, 'success': True,
            'data': {
                'status': 'ok',
                'database': 'ok' if db_ok else 'error',
                'version': '1.0.0'
            }
        }
    from .routes.relation_routes import relation_bp
    from .routes.graph_routes import graph_bp
    from .routes.entity_routes import entity_bp
    from .routes.auth_routes import auth_bp
    from .routes.graph_management_routes import gm_bp
    from .routes.log_routes import log_bp
    from .routes.question_routes import question_bp
    from .routes.class_routes import class_bp
    from .routes.exam_routes import exam_bp
    from .routes.statistics_routes import statistics_bp
    from .routes.learning_path_routes import learning_bp
    from .routes.resource_routes import resource_bp
    from .routes.llm_routes import llm_bp
    from .routes.ai_practice_routes import ai_practice_bp
    from .routes.code_editor_routes import editor_bp
    from .routes.code_session_routes import code_session_bp
    from .routes.user_routes import user_bp
    from .routes.task_routes import task_bp
    from .routes.practice_routes import practice_bp
    from .routes.notification_routes import notification_bp

    app.register_blueprint(knowledge_bp, url_prefix='/api/v1')
    app.register_blueprint(relation_bp, url_prefix='/api/v1')
    app.register_blueprint(graph_bp, url_prefix='/api/v1')
    app.register_blueprint(entity_bp, url_prefix='/api/v1')
    app.register_blueprint(auth_bp, url_prefix='/api/v1')
    app.register_blueprint(gm_bp, url_prefix='/api/v1')
    app.register_blueprint(log_bp, url_prefix='/api/v1')
    app.register_blueprint(question_bp, url_prefix='/api/v1')
    app.register_blueprint(class_bp, url_prefix='/api/v1')
    app.register_blueprint(exam_bp, url_prefix='/api/v1')
    app.register_blueprint(statistics_bp, url_prefix='/api/v1')
    app.register_blueprint(learning_bp, url_prefix='/api/v1')
    app.register_blueprint(resource_bp, url_prefix='/api/v1')
    app.register_blueprint(llm_bp, url_prefix='/api/v1')
    app.register_blueprint(ai_practice_bp, url_prefix='/api/v1')
    app.register_blueprint(editor_bp, url_prefix='/api/v1')
    app.register_blueprint(code_session_bp, url_prefix='/api/v1')
    app.register_blueprint(user_bp, url_prefix='/api/v1')
    app.register_blueprint(task_bp, url_prefix='/api/v1')
    app.register_blueprint(practice_bp, url_prefix='/api/v1')
    app.register_blueprint(notification_bp, url_prefix='/api/v1')

    # ── 全局限流 ──────────────────────────────
    from .utils.rate_limit import check_limit

    @app.before_request
    def global_rate_limit():
        if request.path == '/api/v1/health':
            return
        if request.method == 'OPTIONS' or (request.path or '').startswith('/api/v1/static'):
            return
        # 排除日志上报和静态资源
        if '/logs/' in request.path:
            return
        try:
            key = f'global:{request.remote_addr}'
            limited, _, _ = check_limit(key, 300)
            if limited:
                return jsonify({
                    'code': 429, 'success': False,
                    'message': '请求过于频繁，请稍后重试'
                }), 429
        except Exception:
            pass  # 限流异常不影响正常请求

    # ── 全局错误捕获 ──────────────────────────
    import traceback
    @app.errorhandler(500)
    def handle_500(e):
        from .services.log_service import LogService
        tb = traceback.format_exc()
        LogService.log_error(
            source='backend',
            action='server_error',
            module='system',
            detail=str(e),
            error_type=type(e).__name__,
            traceback=tb,
            endpoint=request.path if request else ''
        )
        return {
            'code': 500,
            'success': False,
            'message': '服务器内部错误，已记录日志'
        }, 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        from werkzeug.exceptions import HTTPException
        # HTTPException（404/405 等）按原状态码返回 JSON，避免被统一转成 500
        if isinstance(e, HTTPException):
            return {
                'code': e.code,
                'success': False,
                'message': getattr(e, 'description', None) or '请求失败'
            }, e.code
        try:
            from .services.log_service import LogService
            tb = traceback.format_exc()
            LogService.log_error(
                source='backend',
                action='unhandled_error',
                module='system',
                detail=str(e),
                error_type=type(e).__name__,
                traceback=tb,
                endpoint=request.path if request else ''
            )
        except Exception:
            import sys
            print(str(e), file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        return {
            'code': 500,
            'success': False,
            'message': '服务器异常，已记录日志'
        }, 500

    # ── 健康检查 ──────────────────────────────
    @app.route('/api/v1/health', methods=['GET'])
    def health_check():
        db_ok = False
        graph_ok = False
        try:
            sql_repo.execute_query("SELECT 1")
            db_ok = True
        except Exception:
            pass
        try:
            graph_repo.test_connection()
            graph_ok = True
        except Exception:
            pass
        return {
            'code': 200,
            'success': True,
            'data': {
                'status': 'running',
                'db_backend': 'mysql',
                'graph_backend': 'neo4j',
                'mysql_ok': db_ok,
                'neo4j_ok': graph_ok,
            },
            'message': '服务正常'
        }

    # ── 数据初始化 ─────────────────────────────
    @app.route('/api/v1/init-data', methods=['POST'])
    @require_admin
    def init_data():
        from data.seed_data import init_all
        try:
            result = init_all()
            return {
                'code': 200,
                'success': True,
                'data': result,
                'message': '数据初始化完成'
            }
        except Exception as e:
            current_app.logger.exception('数据初始化失败')
            return {
                'code': 500,
                'success': False,
                'data': None,
                'message': '数据初始化失败，请查看服务器日志'
            }, 500

    return app


def _init_storage(app):
    """初始化存储层 — MySQL 建表 + Neo4j 图数据库（无需手动持久化）"""
    sql_repo.create_tables()

    # Neo4j 自身持久化，无需 load_from_disk / auto_save

    # 确保默认管理员账号存在且角色正确
    try:
        admin_pwd = app.config.get('ADMIN_DEFAULT_PASSWORD')
        if not admin_pwd:
            app.logger.warning('[Init] ADMIN_DEFAULT_PASSWORD 未配置，跳过默认管理员创建')
        else:
            from .services.auth_service import auth_service
            existing = sql_repo.execute_query("SELECT id, role FROM users WHERE username = 'admin'")
            if existing:
                if existing[0]['role'] != 'admin':
                    sql_repo.execute_update("UPDATE users SET role = 'admin', is_dev = 1 WHERE username = 'admin'")
            else:
                auth_service.register('admin', admin_pwd, role='admin')
    except Exception as e:
        app.logger.error('[Init] 默认管理员创建失败: %s', str(e))
