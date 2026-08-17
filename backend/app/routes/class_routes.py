# -*- coding: utf-8 -*-
"""班级路由"""
from flask import Blueprint, request, jsonify
from ..services.class_service import class_service
from ..utils.operation_logger import record_log
from ..utils.auth import require_auth, require_admin
from ..utils.pagination import get_pagination_params, paginate_list, paginate_response
from ..repositories.sql_repo import sql_repo

class_bp = Blueprint('class', __name__)


def _is_class_member(cid):
    """校验当前用户是否该班学生，防止查看他人班级学生名单"""
    user_id = request.current_user.get('user_id')
    rows = sql_repo.execute_query(
        "SELECT id FROM class_students WHERE class_id = ? AND student_id = ?",
        (cid, user_id))
    return bool(rows)


def _is_teacher(cid):
    """校验当前管理员是否该班教师，防止跨班越权管理"""
    user_id = request.current_user.get('user_id')
    rows = sql_repo.execute_query(
        "SELECT id FROM classes WHERE id = ? AND teacher_id = ?",
        (cid, user_id))
    return bool(rows)


def _check_teacher(cid):
    """管理类操作越权校验：仅本班教师可操作，否则返回 403 响应"""
    if not _is_teacher(cid):
        return jsonify({'code': 403, 'success': False, 'message': '无权管理该班级'}), 403
    return None


@class_bp.route('/classes', methods=['POST'])
@require_admin
def create_class():
    data = request.get_json(force=True) or {}
    user_id = request.current_user.get('user_id', 1)
    try:
        cls = class_service.create(
            name=data.get('name', ''),
            description=data.get('description', ''),
            teacher_id=user_id
        )
        record_log('创建班级', '班级管理', f'创建班级 "{cls["name"]}" 码={cls["class_code"]}')
        return jsonify({'code': 200, 'success': True, 'data': cls, 'message': '创建成功'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400


@class_bp.route('/classes', methods=['GET'])
@require_auth
def list_classes():
    user_id = request.current_user.get('user_id', 1)
    role = request.current_user.get('role', 'user')
    page, page_size = get_pagination_params(request.args)
    if role == 'admin':
        classes = class_service.get_teacher_classes(user_id)
    else:
        classes = class_service.get_student_classes(user_id)
    items, total = paginate_list(classes, page, page_size)
    return jsonify({
        'code': 200, 'success': True,
        'data': paginate_response(items, page, page_size, total),
        'message': '操作成功'
    })


@class_bp.route('/classes/<int:cid>', methods=['GET'])
@require_auth
def get_class(cid):
    cls = class_service.get_by_id(cid)
    if not cls:
        return jsonify({'code': 404, 'success': False, 'message': '班级不存在'}), 404
    # 仅本班学生或本班教师可查看，防止查看他人班级学生名单
    if not (_is_teacher(cid) or _is_class_member(cid)):
        return jsonify({'code': 403, 'success': False, 'message': '无权查看该班级'}), 403
    cls['students'] = class_service.get_students(cid)
    return jsonify({'code': 200, 'success': True, 'data': cls, 'message': '操作成功'})


@class_bp.route('/classes/<int:cid>', methods=['PUT'])
@require_admin
def update_class(cid):
    denied = _check_teacher(cid)
    if denied:
        return denied
    data = request.get_json(force=True) or {}
    class_service.update(cid, name=data.get('name'), description=data.get('description'))
    record_log('编辑班级', '班级管理', f'编辑班级 ID={cid}')
    return jsonify({'code': 200, 'success': True, 'message': '更新成功'})


@class_bp.route('/classes/<int:cid>', methods=['DELETE'])
@require_admin
def delete_class(cid):
    denied = _check_teacher(cid)
    if denied:
        return denied
    class_service.delete(cid)
    record_log('删除班级', '班级管理', f'删除班级 ID={cid}')
    return jsonify({'code': 200, 'success': True, 'message': '已解散班级'})


@class_bp.route('/classes/join', methods=['POST'])
@require_auth
def join_class():
    data = request.get_json(force=True) or {}
    code = data.get('class_code', '').strip()
    user_id = request.current_user.get('user_id', 1)
    try:
        cls = class_service.join(code, user_id)
        record_log('加入班级', '班级管理', f'加入班级 "{cls["name"]}"')
        return jsonify({'code': 200, 'success': True, 'data': cls, 'message': '加入成功'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400


@class_bp.route('/classes/<int:cid>/students/<int:sid>', methods=['DELETE'])
@require_admin
def remove_student(cid, sid):
    denied = _check_teacher(cid)
    if denied:
        return denied
    class_service.remove_student(cid, sid)
    record_log('移除学生', '班级管理', f'从班级 {cid} 移除学生 {sid}')
    return jsonify({'code': 200, 'success': True, 'message': '已移除学生'})


@class_bp.route('/classes/<int:cid>/leave', methods=['POST'])
@require_auth
def leave_class(cid):
    """学生主动退出班级"""
    user_id = request.current_user.get('user_id', 1)
    try:
        class_service.leave_class(cid, user_id)
        record_log('退出班级', '班级管理', f'学生 {user_id} 退出班级 {cid}')
        return jsonify({'code': 200, 'success': True, 'message': '已退出班级'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400


# ── 公告 ──

@class_bp.route('/classes/<int:cid>/announcements', methods=['GET'])
@require_auth
def get_announcements(cid):
    if not (_is_teacher(cid) or _is_class_member(cid)):
        return jsonify({'code': 403, 'success': False, 'message': '无权查看该班级公告'}), 403
    items = class_service.get_announcements(cid)
    return jsonify({'code': 200, 'success': True, 'data': items})


@class_bp.route('/classes/<int:cid>/announcements', methods=['POST'])
@require_admin
def create_announcement(cid):
    denied = _check_teacher(cid)
    if denied:
        return denied
    data = request.get_json(force=True) or {}
    user_id = request.current_user.get('user_id', 1)
    try:
        a = class_service.create_announcement(
            cid, data.get('title', ''), data.get('content', ''),
            user_id, data.get('is_pinned', 0))
        return jsonify({'code': 200, 'success': True, 'data': a, 'message': '公告已发布'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400


@class_bp.route('/classes/<int:cid>/announcements/<int:aid>', methods=['DELETE'])
@require_admin
def delete_announcement(cid, aid):
    denied = _check_teacher(cid)
    if denied:
        return denied
    class_service.delete_announcement(aid)
    return jsonify({'code': 200, 'success': True, 'message': '公告已删除'})


# ── 分组 ──

@class_bp.route('/classes/<int:cid>/groups', methods=['GET'])
@require_admin
def get_groups(cid):
    denied = _check_teacher(cid)
    if denied:
        return denied
    items = class_service.get_groups(cid)
    return jsonify({'code': 200, 'success': True, 'data': items})


@class_bp.route('/classes/<int:cid>/groups', methods=['POST'])
@require_admin
def create_group(cid):
    denied = _check_teacher(cid)
    if denied:
        return denied
    data = request.get_json(force=True) or {}
    user_id = request.current_user.get('user_id', 1)
    try:
        g = class_service.create_group(cid, data.get('name', ''), data.get('description', ''), user_id)
        return jsonify({'code': 200, 'success': True, 'data': g, 'message': '分组已创建'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400


@class_bp.route('/classes/<int:cid>/groups/<int:gid>', methods=['DELETE'])
@require_admin
def delete_group(cid, gid):
    denied = _check_teacher(cid)
    if denied:
        return denied
    class_service.delete_group(gid)
    return jsonify({'code': 200, 'success': True, 'message': '分组已删除'})


@class_bp.route('/classes/<int:cid>/groups/<int:gid>/members', methods=['GET'])
@require_admin
def get_group_members(cid, gid):
    denied = _check_teacher(cid)
    if denied:
        return denied
    members = class_service.get_group_members(gid)
    return jsonify({'code': 200, 'success': True, 'data': members})


@class_bp.route('/classes/<int:cid>/groups/<int:gid>/members', methods=['POST'])
@require_admin
def add_group_member(cid, gid):
    denied = _check_teacher(cid)
    if denied:
        return denied
    data = request.get_json(force=True) or {}
    try:
        class_service.add_group_member(gid, data.get('student_id', 0))
        return jsonify({'code': 200, 'success': True, 'message': '已添加成员'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400


@class_bp.route('/classes/<int:cid>/groups/<int:gid>/members/<int:mid>', methods=['DELETE'])
@require_admin
def remove_group_member(cid, gid, mid):
    denied = _check_teacher(cid)
    if denied:
        return denied
    class_service.remove_group_member(gid, mid)
    return jsonify({'code': 200, 'success': True, 'message': '已移除成员'})
