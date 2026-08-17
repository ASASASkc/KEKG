# -*- coding: utf-8 -*-
"""学习路径路由"""
from flask import Blueprint, request, jsonify
from ..services.learning_path_service import LearningPathService, learning_path_service
from ..utils.auth import require_auth

learning_bp = Blueprint('learning', __name__)


@learning_bp.route('/learning/assessment', methods=['GET'])
@require_auth
def get_assessment():
    user_id = request.current_user['user_id']
    result = LearningPathService.get_assessment(user_id)
    return jsonify({'code': 200, 'success': True, 'data': result, 'message': '操作成功'})


@learning_bp.route('/learning/path', methods=['GET'])
@require_auth
def get_path():
    user_id = request.current_user['user_id']
    result = LearningPathService.get_learning_path(user_id)
    return jsonify({'code': 200, 'success': True, 'data': result, 'message': '操作成功'})


@learning_bp.route('/learning/track-recommendations', methods=['GET'])
@require_auth
def get_track_recommendations():
    user_id = request.current_user['user_id']
    result = learning_path_service.get_track_recommendations(user_id)
    return jsonify({'code': 200, 'success': True, 'data': result, 'message': '操作成功'})


# ── 自定义学习计划 CRUD ──

@learning_bp.route('/learning/plans', methods=['GET'])
@require_auth
def list_plans():
    from ..services.study_plan_service import StudyPlanService
    user_id = request.current_user['user_id']
    plans = StudyPlanService.get_user_plans(user_id)
    return jsonify({'code': 200, 'success': True, 'data': plans})


@learning_bp.route('/learning/plans', methods=['POST'])
@require_auth
def create_plan():
    from ..services.study_plan_service import StudyPlanService
    user_id = request.current_user['user_id']
    data = request.get_json() or {}
    try:
        plan = StudyPlanService.create(
            user_id=user_id,
            title=data.get('title', ''),
            description=data.get('description', ''),
            knowledge_point_ids=data.get('knowledge_point_ids'),
            target_date=data.get('target_date'),
            question_ids=data.get('question_ids')
        )
        return jsonify({'code': 200, 'success': True, 'data': plan, 'message': '创建成功'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400


@learning_bp.route('/learning/plans/<int:plan_id>', methods=['PUT'])
@require_auth
def update_plan(plan_id):
    from ..services.study_plan_service import StudyPlanService
    user_id = request.current_user['user_id']
    data = request.get_json() or {}
    try:
        plan = StudyPlanService.update(plan_id, user_id, **data)
        return jsonify({'code': 200, 'success': True, 'data': plan, 'message': '更新成功'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400


@learning_bp.route('/learning/plans/<int:plan_id>', methods=['DELETE'])
@require_auth
def delete_plan(plan_id):
    from ..services.study_plan_service import StudyPlanService
    user_id = request.current_user['user_id']
    try:
        result = StudyPlanService.delete(plan_id, user_id)
        return jsonify({'code': 200, 'success': True, 'data': result, 'message': '删除成功'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400


@learning_bp.route('/learning/plans/<int:plan_id>/questions', methods=['GET'])
@require_auth
def get_plan_questions(plan_id):
    from ..services.study_plan_service import StudyPlanService
    user_id = request.current_user['user_id']
    try:
        data = StudyPlanService.get_plan_questions(plan_id, user_id)
        return jsonify({'code': 200, 'success': True, 'data': data})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400


# ── 打卡功能 ──

@learning_bp.route('/learning/plans/<int:plan_id>/checkin', methods=['POST'])
@require_auth
def plan_checkin(plan_id):
    from ..services.study_plan_service import StudyPlanService
    user_id = request.current_user['user_id']
    data = request.get_json() or {}
    try:
        result = StudyPlanService.checkin(
            plan_id, user_id,
            study_minutes=data.get('study_minutes', 0),
            question_count=data.get('question_count', 0),
            notes=data.get('notes', '')
        )
        return jsonify({'code': 200, 'success': True, 'data': result, 'message': '打卡成功'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400


@learning_bp.route('/learning/plans/<int:plan_id>/checkins', methods=['GET'])
@require_auth
def get_plan_checkins(plan_id):
    from ..services.study_plan_service import StudyPlanService
    user_id = request.current_user['user_id']
    year_month = request.args.get('month', '')
    try:
        rows = StudyPlanService.get_checkins(plan_id, user_id, year_month or None)
        streak = StudyPlanService.get_checkin_streak(plan_id, user_id)
        return jsonify({'code': 200, 'success': True, 'data': {'checkins': rows, 'streak': streak}})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400
