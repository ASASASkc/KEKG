# -*- coding: utf-8 -*-
"""统计路由"""
from flask import Blueprint, request, jsonify
from ..services.statistics_service import statistics_service
from ..utils.auth import require_auth, require_admin

statistics_bp = Blueprint('statistics', __name__)


@statistics_bp.route('/statistics/student/overview', methods=['GET'])
@require_auth
def student_overview():
    user_id = request.current_user['user_id']
    start = request.args.get('start_date', '')
    end = request.args.get('end_date', '')
    result = statistics_service.student_overview(user_id, start, end)
    return jsonify({'code': 200, 'success': True, 'data': result, 'message': '操作成功'})


@statistics_bp.route('/statistics/student/exam/<int:eid>', methods=['GET'])
@require_auth
def student_exam(eid):
    user_id = request.current_user['user_id']
    result = statistics_service.student_exam_detail(eid, user_id)
    if not result:
        return jsonify({'code': 404, 'success': False, 'message': '暂无数据'}), 404
    return jsonify({'code': 200, 'success': True, 'data': result, 'message': '操作成功'})


@statistics_bp.route('/statistics/class/<int:cid>/exam/<int:eid>', methods=['GET'])
@require_admin
def class_exam(cid, eid):
    result = statistics_service.class_exam_detail(eid, cid)
    if not result:
        return jsonify({'code': 404, 'success': False, 'message': '暂无数据'}), 404
    return jsonify({'code': 200, 'success': True, 'data': result, 'message': '操作成功'})


@statistics_bp.route('/statistics/class/<int:cid>/summary', methods=['GET'])
@require_admin
def class_summary(cid):
    start = request.args.get('start_date', '')
    end = request.args.get('end_date', '')
    result = statistics_service.class_summary(cid, start, end)
    return jsonify({'code': 200, 'success': True, 'data': result, 'message': '操作成功'})


@statistics_bp.route('/statistics/student/summary', methods=['GET'])
@require_auth
def student_summary():
    user_id = request.current_user['user_id']
    start = request.args.get('start_date', '')
    end = request.args.get('end_date', '')
    result = statistics_service.student_summary(user_id, start, end)
    return jsonify({'code': 200, 'success': True, 'data': result, 'message': '操作成功'})


@statistics_bp.route('/statistics/student/radar', methods=['GET'])
@require_auth
def student_radar():
    user_id = request.current_user['user_id']
    result = statistics_service.student_radar(user_id)
    return jsonify({'code': 200, 'success': True, 'data': result, 'message': '操作成功'})


@statistics_bp.route('/statistics/class/<int:cid>/weak-points/<int:eid>', methods=['GET'])
@require_admin
def class_weak_points(cid, eid):
    result = statistics_service.class_weak_points(eid, cid)
    return jsonify({'code': 200, 'success': True, 'data': result, 'message': '操作成功'})
