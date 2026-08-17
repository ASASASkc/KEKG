# -*- coding: utf-8 -*-
"""操作日志记录辅助工具"""

from flask import request
from ..services.log_service import LogService


def _get_user_info():
    """从当前请求上下文中提取用户信息"""
    user = getattr(request, 'current_user', None)
    if user:
        return user['user_id'], user['username']
    return 0, '匿名'


def _get_ip():
    """获取客户端 IP"""
    return request.headers.get('X-Forwarded-For',
           request.headers.get('X-Real-IP',
           request.remote_addr or ''))


def record_log(action, module='', detail='', result='success'):
    """便捷：记录一条操作日志"""
    user_id, username = _get_user_info()
    ip = _get_ip()
    LogService.log(user_id, username, action, module, detail, ip, result)
