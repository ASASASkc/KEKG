# -*- coding: utf-8 -*-
"""站内通知路由"""
from flask import Blueprint, request, jsonify
from ..utils.auth import require_auth
from ..services.notification_service import notification_service

notification_bp = Blueprint('notification', __name__)


@notification_bp.route('/notifications', methods=['GET'])
@require_auth
def list_notifications():
    """分页查询当前用户通知"""
    user_id = request.current_user['user_id']
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    result = notification_service.list(user_id, page, page_size)
    return jsonify({'code': 200, 'success': True, 'data': result})


@notification_bp.route('/notifications/unread-count', methods=['GET'])
@require_auth
def unread_count():
    """未读通知数（顶部红点）"""
    user_id = request.current_user['user_id']
    return jsonify({
        'code': 200, 'success': True,
        'data': {'count': notification_service.unread_count(user_id)}
    })


@notification_bp.route('/notifications/<int:nid>/read', methods=['PUT'])
@require_auth
def mark_read(nid):
    """标记单条通知已读"""
    user_id = request.current_user['user_id']
    notification_service.mark_read(user_id, nid)
    return jsonify({'code': 200, 'success': True, 'message': '已标记已读'})


@notification_bp.route('/notifications/read-all', methods=['PUT'])
@require_auth
def mark_all_read():
    """全部标记已读"""
    user_id = request.current_user['user_id']
    notification_service.mark_all_read(user_id)
    return jsonify({'code': 200, 'success': True, 'message': '已全部标记已读'})
