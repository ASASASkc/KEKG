# -*- coding: utf-8 -*-
"""
认证服务 — 注册、登录、获取用户信息
"""
import secrets
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash
from ..utils.auth import generate_token
from ..repositories.sql_repo import sql_repo


class AuthService:
    """用户认证"""

    @staticmethod
    def register(username, password, email=None, role='user'):
        """
        注册新用户
        返回 (success, data, message)
        """
        username = username.strip()
        password = password.strip()

        if len(username) < 2 or len(username) > 50:
            return False, None, '用户名长度 2-50 个字符'
        if len(password) < 8:
            return False, None, '密码至少 8 个字符'
        # 复杂度检查：需同时包含字母和数字
        has_letter = any(c.isalpha() for c in password)
        has_digit = any(c.isdigit() for c in password)
        if not has_letter or not has_digit:
            return False, None, '密码需同时包含字母和数字'

        # 检查用户名是否已存在
        existing = sql_repo.execute_query(
            "SELECT id FROM users WHERE username = ?", (username,)
        )
        if existing:
            return False, None, '用户名已被注册'

        # 创建用户（默认开发者账号 admin/admin 自动标记 is_dev）
        password_hash = generate_password_hash(password)
        email = email or f'{username}@kekg.local'
        is_dev = 1 if (role == 'admin' and username == 'admin') else 0
        user_id = sql_repo.execute_insert(
            "INSERT INTO users (username, password_hash, email, role, is_dev, status) VALUES (?, ?, ?, ?, ?, 'active')",
            (username, password_hash, email, role, is_dev)
        )

        return True, {
            'id': user_id,
            'username': username,
            'email': email,
            'role': role,
            'is_dev': is_dev
        }, '注册成功'

    @staticmethod
    def login(username, password):
        """
        登录
        返回 (success, data, message)
        """
        users = sql_repo.execute_query(
            "SELECT * FROM users WHERE username = ?", (username,)
        )
        if not users:
            return False, None, '用户名或密码错误'

        user = users[0]
        if not check_password_hash(user['password_hash'], password):
            return False, None, '用户名或密码错误'

        if user.get('status') != 'active':
            return False, None, '账号已被禁用'

        token = generate_token(user['id'], user['username'], user['role'], user.get('is_dev', 0))
        return True, {
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role'],
                'is_dev': user.get('is_dev', 0)
            }
        }, '登录成功'

    @staticmethod
    def get_user_by_id(user_id):
        """根据 ID 获取用户"""
        users = sql_repo.execute_query(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        )
        if not users:
            return None
        u = users[0]
        return {
            'id': u['id'],
            'username': u['username'],
            'email': u['email'],
            'role': u['role'],
            'is_dev': u.get('is_dev', 0),
            'created_at': str(u['created_at']) if u.get('created_at') else None
        }

    @staticmethod
    def change_password(user_id, old_password, new_password):
        """修改密码"""
        users = sql_repo.execute_query(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        )
        if not users:
            return False, '用户不存在'

        if not check_password_hash(users[0]['password_hash'], old_password):
            return False, '原密码错误'

        new_hash = generate_password_hash(new_password)
        sql_repo.execute_update(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, user_id)
        )
        return True, '密码修改成功'

    # ── 用户管理 ──────────────────────────────

    @staticmethod
    def get_all_users():
        """获取所有用户列表"""
        rows = sql_repo.execute_query(
            "SELECT id, username, email, role, is_dev, status, created_at FROM users ORDER BY id"
        )
        return [dict(r) for r in rows]

    @staticmethod
    def update_user_role(user_id, role):
        """修改用户角色（仅 admin/admin 账号可持有开发者标识，其余一律清除）"""
        if role not in ('user', 'admin'):
            return False, '无效的角色'
        users = sql_repo.execute_query(
            "SELECT id, username FROM users WHERE id = ?", (user_id,)
        )
        if not users:
            return False, '用户不存在'
        username = users[0]['username']
        is_dev = 1 if (role == 'admin' and username == 'admin') else 0
        sql_repo.execute_update(
            "UPDATE users SET role = ?, is_dev = ? WHERE id = ?", (role, is_dev, user_id)
        )
        return True, '角色更新成功'

    @staticmethod
    def delete_user(user_id):
        """删除用户"""
        users = sql_repo.execute_query(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        )
        if not users:
            return False, '用户不存在'
        sql_repo.execute_update(
            "DELETE FROM users WHERE id = ?", (user_id,)
        )
        return True, '用户已删除'

    # ── 邀请码 ────────────────────────────────

    @staticmethod
    def get_invite_code():
        """获取当前邀请码"""
        rows = sql_repo.execute_query(
            "SELECT value FROM system_config WHERE `key` = 'invite_code'"
        )
        if rows and rows[0]['value']:
            return rows[0]['value']
        # 未配置邀请码时生成随机码，禁止使用硬编码弱默认值（防止任何人注册管理员）
        default_code = current_app.config.get('DEFAULT_INVITE_CODE')
        if not default_code:
            default_code = secrets.token_hex(6).upper()
            current_app.logger.warning('未配置 DEFAULT_INVITE_CODE，已生成随机管理员邀请码: %s', default_code)
        sql_repo.execute_insert(
            "INSERT OR IGNORE INTO system_config (`key`, value, description) VALUES (?, ?, ?)",
            ('invite_code', default_code, '管理员注册邀请码')
        )
        return default_code

    @staticmethod
    def set_invite_code(code):
        """修改邀请码"""
        code = code.strip()
        if len(code) < 4:
            return False, '邀请码至少4个字符'
        sql_repo.execute_update(
            "INSERT OR REPLACE INTO system_config (`key`, value, description) VALUES (?, ?, ?)",
            ('invite_code', code, '管理员注册邀请码')
        )
        return True, '邀请码已更新'

    @staticmethod
    def verify_invite_code(code):
        """验证邀请码是否正确"""
        current = AuthService.get_invite_code()
        return code and code.strip() == current


auth_service = AuthService()
