# -*- coding: utf-8 -*-
"""后台任务路由"""
from flask import Blueprint, jsonify
from ..services.task_manager import get_status, cleanup_expired
from ..utils.auth import require_auth, require_admin

task_bp = Blueprint('tasks', __name__)


@task_bp.route('/tasks/<task_id>/status', methods=['GET'])
@require_auth
def task_status(task_id):
    """轮询后台任务状态"""
    task = get_status(task_id)
    if not task:
        return jsonify({'code': 404, 'success': False, 'data': None, 'message': '任务不存在或已过期'}), 404
    return jsonify({'code': 200, 'success': True, 'data': task, 'message': 'OK'})


@task_bp.route('/tasks/cleanup', methods=['POST'])
@require_admin
def task_cleanup():
    """清理过期任务（管理员调用）"""
    cleanup_expired()
    return jsonify({'code': 200, 'success': True, 'data': None, 'message': '清理完成'})
