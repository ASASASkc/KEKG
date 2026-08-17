# -*- coding: utf-8 -*-
"""用户主页路由"""
from flask import Blueprint, request, jsonify
from ..utils.auth import require_auth
from ..services.auth_service import auth_service
from ..services.activity_service import activity_service
from ..services.exam_service import exam_service

user_bp = Blueprint('user', __name__)


@user_bp.route('/users/<int:uid>/profile', methods=['GET'])
@require_auth
def user_profile(uid):
    """获取用户主页数据（按角色返回不同内容）
    - 学生/普通用户：个人学习数据
    - 教师（管理员）：教学概览（班级、学生、考试），不含个人学习数据
    - 开发者：系统运维概览
    """
    # 权限校验：非管理员只能查看自己的主页
    current_user = request.current_user
    if current_user.get('role') != 'admin' and current_user['user_id'] != uid:
        return jsonify({'code': 403, 'success': False, 'message': '无权查看他人主页'}), 403

    user = auth_service.get_user_by_id(uid)
    if not user:
        return jsonify({'code': 404, 'success': False, 'message': '用户不存在'}), 404

    if user.get('is_dev'):
        # 开发者：系统运维概览
        data = {'user': user, 'system': _system_summary()}
    elif user.get('role') == 'admin':
        # 教师：教学概览
        data = {'user': user, 'teaching': _teaching_summary(uid)}
    else:
        # 学生：个人学习数据
        heatmap_end = request.args.get('heatmap_end', '')
        stats = activity_service.get_user_stats(uid, heatmap_end=heatmap_end if heatmap_end else None)
        data = {'user': user, 'stats': stats}

    return jsonify({
        'code': 200,
        'success': True,
        'data': data
    })


def _teaching_summary(teacher_id):
    """教师教学概览：班级、学生、考试等教学数据（替换个人学习数据）"""
    from ..repositories.sql_repo import sql_repo

    classes = sql_repo.execute_query(
        """SELECT c.id, c.name, c.class_code, c.created_at,
                  (SELECT COUNT(*) FROM class_students cs WHERE cs.class_id = c.id) AS student_count
           FROM classes c
           WHERE c.teacher_id = ?
           ORDER BY c.id DESC""",
        (teacher_id,))
    class_ids = [c['id'] for c in classes]

    student_total = 0
    if class_ids:
        placeholders = ','.join('?' * len(class_ids))
        row = sql_repo.execute_query(
            f"SELECT COUNT(DISTINCT student_id) AS cnt FROM class_students WHERE class_id IN ({placeholders})",
            class_ids)
        student_total = row[0]['cnt'] if row else 0

    exam_rows = sql_repo.execute_query(
        "SELECT COUNT(*) AS cnt FROM exam_papers WHERE created_by = ?", (teacher_id,))
    exam_count = exam_rows[0]['cnt'] if exam_rows else 0

    # 待批改：教师考试的已提交待评分答卷
    pending_rows = sql_repo.execute_query(
        """SELECT COUNT(*) AS cnt FROM exam_submissions es
           JOIN exam_papers ep ON es.exam_id = ep.id
           WHERE ep.created_by = ? AND es.status = 'submitted'""",
        (teacher_id,))
    pending_review_count = pending_rows[0]['cnt'] if pending_rows else 0

    # 草稿试卷：已生成未发布
    draft_rows = sql_repo.execute_query(
        "SELECT COUNT(*) AS cnt FROM exam_papers WHERE created_by = ? AND status = 'draft'",
        (teacher_id,))
    draft_exam_count = draft_rows[0]['cnt'] if draft_rows else 0

    # 最近布置的考试（不含已删除）
    recent = sql_repo.execute_query(
        """SELECT ep.id, ep.title, ep.status, ep.created_at, c.name AS class_name
           FROM exam_papers ep
           LEFT JOIN classes c ON ep.class_id = c.id
           WHERE ep.created_by = ? AND ep.status != 'deleted'
           ORDER BY ep.id DESC LIMIT 5""",
        (teacher_id,))

    return {
        'class_count': len(classes),
        'student_total': student_total,
        'exam_count': exam_count,
        'pending_review_count': pending_review_count,
        'draft_exam_count': draft_exam_count,
        'recent_exams': [dict(r) for r in recent],
        'classes': [dict(c) for c in classes],
    }


def _system_summary():
    """系统运维概览（开发者专属）"""
    from ..repositories.sql_repo import sql_repo

    def cnt(sql):
        rows = sql_repo.execute_query(sql)
        return rows[0]['cnt'] if rows else 0

    return {
        'user_count': cnt("SELECT COUNT(*) AS cnt FROM users"),
        'teacher_count': cnt("SELECT COUNT(*) AS cnt FROM users WHERE role = 'admin'"),
        'question_count': cnt("SELECT COUNT(*) AS cnt FROM question_bank"),
        'class_count': cnt("SELECT COUNT(*) AS cnt FROM classes"),
        'exam_count': cnt("SELECT COUNT(*) AS cnt FROM exam_papers"),
        'kp_count': cnt("SELECT COUNT(*) AS cnt FROM knowledge_points_meta"),
        'log_count': cnt("SELECT COUNT(*) AS cnt FROM operation_logs"),
    }


@user_bp.route('/users/<int:uid>/achievements', methods=['GET'])
@require_auth
def user_achievements(uid):
    """获取用户成就徽章墙（访问时自动重算解锁）"""
    current_user = request.current_user
    if current_user.get('role') != 'admin' and current_user['user_id'] != uid:
        return jsonify({'code': 403, 'success': False, 'message': '无权查看他人徽章'}), 403
    from ..services.achievement_service import achievement_service
    data = achievement_service.get_wall(uid)
    return jsonify({'code': 200, 'success': True, 'data': data})


@user_bp.route('/users/<int:uid>/day-activities', methods=['GET'])
@require_auth
def day_activities(uid):
    """获取某天的活动详情"""
    current_user = request.current_user
    if current_user.get('role') != 'admin' and current_user['user_id'] != uid:
        return jsonify({'code': 403, 'success': False, 'message': '无权查看他人活动'}), 403
    date = request.args.get('date', '')
    if not date:
        return jsonify({'code': 400, 'success': False, 'message': '缺少日期参数'}), 400
    items = activity_service.get_day_activities(uid, date)
    return jsonify({'code': 200, 'success': True, 'data': items})


@user_bp.route('/users/<int:uid>/wrong-answers', methods=['GET'])
@require_auth
def wrong_answers(uid):
    """获取用户错题本"""
    current_user = request.current_user
    if current_user.get('role') != 'admin' and current_user['user_id'] != uid:
        return jsonify({'code': 403, 'success': False, 'message': '无权查看他人错题本'}), 403
    from ..utils.pagination import get_pagination_params
    page, page_size = get_pagination_params(request.args)
    result = exam_service.get_wrong_answers(uid, page, page_size)
    return jsonify({'code': 200, 'success': True, 'data': result})


@user_bp.route('/users/<int:uid>/wrong-answers/<int:aid>', methods=['DELETE'])
@require_auth
def delete_wrong_answer(uid, aid):
    """删除用户的错题记录"""
    current_user = request.current_user
    if current_user.get('role') != 'admin' and current_user['user_id'] != uid:
        return jsonify({'code': 403, 'success': False, 'message': '无权操作'}), 403
    try:
        exam_service.delete_wrong_answer(aid, uid)
        return jsonify({'code': 200, 'success': True, 'message': '已删除'})
    except Exception as e:
        return jsonify({'code': 500, 'success': False, 'message': str(e)}), 500


@user_bp.route('/users/<int:uid>/wrong-answers/<int:aid>/redo', methods=['POST'])
@require_auth
def redo_wrong_answer(uid, aid):
    """记录错题重做结果（重做正确则标记已掌握）"""
    current_user = request.current_user
    if current_user.get('role') != 'admin' and current_user['user_id'] != uid:
        return jsonify({'code': 403, 'success': False, 'message': '无权操作'}), 403
    data = request.get_json() or {}
    is_correct = 1 if data.get('is_correct') else 0
    try:
        ok, msg = exam_service.redo_wrong_answer(uid, aid, is_correct)
        if not ok:
            return jsonify({'code': 404, 'success': False, 'message': msg}), 404
        return jsonify({'code': 200, 'success': True, 'message': msg})
    except Exception as e:
        return jsonify({'code': 500, 'success': False, 'message': str(e)}), 500
