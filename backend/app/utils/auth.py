# -*- coding: utf-8 -*-
"""
JWT 认证工具
- generate_token: 生成 JWT
- verify_token: 验证 JWT
- require_auth: 装饰器，保护接口
"""
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app
from ..config import Config


def generate_token(user_id, username, role='user', is_dev=0):
    """生成 JWT token"""
    payload = {
        'user_id': user_id,
        'username': username,
        'role': role,
        'is_dev': 1 if is_dev else 0,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(days=Config.JWT_EXPIRE_DAYS)
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')


def verify_token(token):
    """
    验证 JWT token
    返回 (payload, error)
    """
    try:
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, 'token 已过期'
    except jwt.InvalidTokenError:
        return None, 'token 无效'


def require_auth(f):
    """装饰器：要求请求头携带 Authorization: Bearer <token>"""

    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({
                'code': 401,
                'success': False,
                'data': None,
                'message': '请先登录'
            }), 401

        payload, error = verify_token(token)
        if error:
            return jsonify({
                'code': 401,
                'success': False,
                'data': None,
                'message': error
            }), 401

        # 从数据库校验用户最新状态与角色：防止用户被禁用/降权/删除后
        # 已签发的 JWT（最长 7 天）仍携带旧权限访问接口
        from ..repositories.sql_repo import sql_repo
        rows = sql_repo.execute_query(
            "SELECT id, username, role, is_dev, status FROM users WHERE id = ?",
            (payload.get('user_id'),))
        if not rows or rows[0].get('status') != 'active':
            return jsonify({
                'code': 401,
                'success': False,
                'data': None,
                'message': '账号不存在或已被禁用'
            }), 401
        db_user = rows[0]

        # 将用户信息注入请求上下文（以数据库最新数据为准）
        request.current_user = {
            'user_id': db_user['id'],
            'username': db_user['username'],
            'role': db_user['role'],
            'is_dev': 1 if db_user.get('is_dev') else 0
        }
        return f(*args, **kwargs)

    return decorated


def require_admin(f):
    """装饰器：要求管理员角色"""

    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        if request.current_user.get('role') != 'admin':
            return jsonify({
                'code': 403,
                'success': False,
                'data': None,
                'message': '需要管理员权限'
            }), 403
        return f(*args, **kwargs)

    return decorated


def require_dev(f):
    """装饰器：仅限开发者账号（is_dev=1）"""

    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        if not request.current_user.get('is_dev'):
            return jsonify({
                'code': 403,
                'success': False,
                'data': None,
                'message': '仅限开发者账号访问'
            }), 403
        return f(*args, **kwargs)

    return decorated


def _extract_token():
    """从 Cookie 或 Authorization 头提取 JWT token"""
    # 优先从 Cookie 读取（httpOnly，防 XSS）
    token = request.cookies.get('kekg_token')
    if token:
        return token
    # 兼容旧版 Authorization header
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:]
    return None
