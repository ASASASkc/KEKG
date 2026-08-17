# -*- coding: utf-8 -*-
"""
认证路由 — 登录 / 注册 / 用户管理
"""
from flask import Blueprint, request, jsonify
from ..services.auth_service import auth_service
from ..utils.auth import require_auth, require_admin, require_dev
from ..utils.operation_logger import record_log
from ..utils.pagination import get_pagination_params, paginate_list, paginate_response
from ..utils.rate_limit import rate_limit

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/auth/register', methods=['POST'])
def register():
    """注册新用户 —— 支持邀请码升级管理员"""
    data = request.get_json(force=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    email = data.get('email', '').strip() or None
    invite_code = data.get('invite_code', '').strip()

    if not username or not password:
        return jsonify({
            'code': 400,
            'success': False,
            'data': None,
            'message': '用户名和密码不能为空'
        }), 400

    role = 'admin' if invite_code and auth_service.verify_invite_code(invite_code) else 'user'
    success, data, msg = auth_service.register(username, password, email, role)

    if success:
        record_log('注册', '用户管理', f'用户 "{username}" 注册（角色: {role}）')

    msg_detail = msg
    if success and role == 'admin':
        msg_detail = '管理员注册成功'
    elif success and invite_code:
        msg_detail = '注册成功（邀请码错误，已注册为普通用户）'

    return jsonify({
        'code': 200 if success else 400,
        'success': success,
        'data': data,
        'message': msg_detail
    }), 200 if success else 400


@auth_bp.route('/auth/login', methods=['POST'])
@rate_limit(max_requests=10, window_seconds=60)
def login():
    """登录"""
    data = request.get_json(force=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({
            'code': 400,
            'success': False,
            'data': None,
            'message': '用户名和密码不能为空'
        }), 400

    success, data, msg = auth_service.login(username, password)

    resp = jsonify({
        'code': 200 if success else 401,
        'success': success,
        'data': data,
        'message': msg
    })

    if success:
        record_log('登录', '用户管理', f'用户 "{username}" 登录成功')
        # 设置 httpOnly Cookie
        resp.status_code = 200
        resp.set_cookie(
            'kekg_token',
            value=data['token'],
            max_age=7 * 24 * 3600,  # 7 天
            httponly=True,
            samesite='Lax',
            path='/',
            secure=False  # 开发环境 HTTP，生产应为 True
        )
    else:
        record_log('登录', '用户管理', f'用户 "{username}" 登录失败: {msg}', result='fail')

    return resp


@auth_bp.route('/auth/logout', methods=['POST'])
def logout():
    """登出 — 清除 httpOnly Cookie"""
    resp = jsonify({
        'code': 200,
        'success': True,
        'data': None,
        'message': '已登出'
    })
    resp.set_cookie('kekg_token', value='', max_age=0, httponly=True, path='/')
    return resp


@auth_bp.route('/auth/me', methods=['GET'])
@require_auth
def me():
    """获取当前登录用户信息"""
    user = auth_service.get_user_by_id(request.current_user['user_id'])
    if not user:
        return jsonify({
            'code': 404,
            'success': False,
            'data': None,
            'message': '用户不存在'
        }), 404

    return jsonify({
        'code': 200,
        'success': True,
        'data': user,
        'message': 'OK'
    })


# ── 用户管理路由（仅开发者）────────────────────

@auth_bp.route('/auth/users', methods=['GET'])
@require_dev
def list_users():
    """获取所有用户列表"""
    page, page_size = get_pagination_params(request.args)
    users = auth_service.get_all_users()
    items, total = paginate_list(users, page, page_size)
    return jsonify({
        'code': 200,
        'success': True,
        'data': paginate_response(items, page, page_size, total),
        'message': 'OK'
    })


@auth_bp.route('/auth/users/<int:user_id>/role', methods=['PUT'])
@require_dev
def update_user_role(user_id):
    """修改用户角色"""
    current_user_id = request.current_user['user_id']
    if int(user_id) == int(current_user_id):
        return jsonify({
            'code': 400,
            'success': False,
            'data': None,
            'message': '不能修改自己的角色'
        }), 400

    data = request.get_json(force=True) or {}
    role = data.get('role', '').strip()
    success, msg = auth_service.update_user_role(user_id, role)

    if success:
        record_log('修改角色', '用户管理', f'用户ID={user_id} 角色改为 "{role}"')

    return jsonify({
        'code': 200 if success else 400,
        'success': success,
        'data': None,
        'message': msg
    }), 200 if success else 400


@auth_bp.route('/auth/users/<int:user_id>', methods=['DELETE'])
@require_dev
def delete_user(user_id):
    """删除用户"""
    current_user_id = request.current_user['user_id']
    if int(user_id) == int(current_user_id):
        return jsonify({
            'code': 400,
            'success': False,
            'data': None,
            'message': '不能删除自己'
        }), 400

    success, msg = auth_service.delete_user(user_id)

    if success:
        record_log('删除用户', '用户管理', f'用户ID={user_id} 已被删除')
    return jsonify({
        'code': 200 if success else 400,
        'success': success,
        'data': None,
        'message': msg
    }), 200 if success else 400


# ── 邀请码管理（仅管理员）────────────────────

@auth_bp.route('/auth/invite-code', methods=['GET'])
@require_admin
def get_invite_code():
    """获取当前邀请码"""
    code = auth_service.get_invite_code()
    return jsonify({
        'code': 200,
        'success': True,
        'data': {'invite_code': code},
        'message': 'OK'
    })


@auth_bp.route('/auth/invite-code', methods=['PUT'])
@require_admin
def set_invite_code():
    """修改邀请码"""
    data = request.get_json(force=True) or {}
    code = data.get('invite_code', '')
    success, msg = auth_service.set_invite_code(code)
    return jsonify({
        'code': 200 if success else 400,
        'success': success,
        'data': None,
        'message': msg
    }), 200 if success else 400
