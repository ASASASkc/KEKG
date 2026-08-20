# -*- coding: utf-8 -*-
"""代码练习会话路由 — 步骤记录持久化"""
from flask import Blueprint, request, jsonify
from ..utils.auth import require_auth
from ..repositories.sql_repo import sql_repo

code_session_bp = Blueprint('code_session', __name__)

VALID_STEP_TYPES = ('init', 'edit', 'run', 'error')
VALID_STATUS = ('saved', 'deleted')


def _get_owned_session(sid, user_id):
    """查询归属当前用户的会话，不存在返回 None"""
    rows = sql_repo.execute_query(
        "SELECT id, user_id, exercise_id, title, status, created_at, updated_at "
        "FROM code_sessions WHERE id = ? AND user_id = ?",
        (sid, user_id))
    return rows[0] if rows else None


# 注意：/code-sessions/mine 必须定义在 <int:sid> 路由之前（Flask 按定义顺序匹配）
@code_session_bp.route('/code-sessions/mine', methods=['GET'])
@require_auth
def list_my_sessions():
    """当前用户已保存的会话列表（含步骤数），按更新时间倒序"""
    user_id = request.current_user['user_id']
    rows = sql_repo.execute_query(
        "SELECT cs.id, cs.exercise_id, cs.title, cs.status, cs.created_at, cs.updated_at, "
        "(SELECT COUNT(*) FROM code_session_steps st WHERE st.session_id = cs.id) AS step_count "
        "FROM code_sessions cs "
        "WHERE cs.user_id = ? AND cs.status = 'saved' "
        "ORDER BY cs.updated_at DESC",
        (user_id,))
    return jsonify({'code': 200, 'success': True, 'data': rows, 'message': 'OK'})


@code_session_bp.route('/code-sessions', methods=['POST'])
@require_auth
def create_session():
    """创建代码练习会话"""
    data = request.get_json(force=True) or {}
    user_id = request.current_user['user_id']
    exercise_id = data.get('exercise_id')
    title = (data.get('title') or '').strip() or '未命名练习'
    sid = sql_repo.execute_insert(
        "INSERT INTO code_sessions (user_id, exercise_id, title) VALUES (?, ?, ?)",
        (user_id, exercise_id, title))
    return jsonify({'code': 200, 'success': True, 'data': {'id': sid}, 'message': '创建成功'})


@code_session_bp.route('/code-sessions/<int:sid>/steps', methods=['POST'])
@require_auth
def add_step(sid):
    """记录一个练习步骤（init/edit/run/error）"""
    user_id = request.current_user['user_id']
    if not _get_owned_session(sid, user_id):
        return jsonify({'code': 404, 'success': False, 'data': None, 'message': '会话不存在'}), 404
    data = request.get_json(force=True) or {}
    step_type = (data.get('step_type') or '').strip()
    if step_type not in VALID_STEP_TYPES:
        return jsonify({'code': 400, 'success': False, 'data': None,
                        'message': f'无效的 step_type，可选值: {"/".join(VALID_STEP_TYPES)}'}), 400
    code = data.get('code', '')
    note = data.get('note')
    step_id = sql_repo.execute_insert(
        "INSERT INTO code_session_steps (session_id, step_type, code, note) VALUES (?, ?, ?, ?)",
        (sid, step_type, code, note))
    sql_repo.execute_update(
        "UPDATE code_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (sid,))
    return jsonify({'code': 200, 'success': True, 'data': {'id': step_id}, 'message': '步骤已记录'})


@code_session_bp.route('/code-sessions/<int:sid>/steps', methods=['GET'])
@require_auth
def list_steps(sid):
    """按 id 升序返回会话的步骤列表"""
    user_id = request.current_user['user_id']
    if not _get_owned_session(sid, user_id):
        return jsonify({'code': 404, 'success': False, 'data': None, 'message': '会话不存在'}), 404
    rows = sql_repo.execute_query(
        "SELECT id, session_id, step_type, code, note, created_at "
        "FROM code_session_steps WHERE session_id = ? ORDER BY id ASC",
        (sid,))
    return jsonify({'code': 200, 'success': True, 'data': rows, 'message': 'OK'})


@code_session_bp.route('/code-sessions/<int:sid>/status', methods=['PUT'])
@require_auth
def update_status(sid):
    """更新会话状态（saved/deleted）"""
    user_id = request.current_user['user_id']
    if not _get_owned_session(sid, user_id):
        return jsonify({'code': 404, 'success': False, 'data': None, 'message': '会话不存在'}), 404
    data = request.get_json(force=True) or {}
    status = (data.get('status') or '').strip()
    if status not in VALID_STATUS:
        return jsonify({'code': 400, 'success': False, 'data': None,
                        'message': f'无效的 status，可选值: {"/".join(VALID_STATUS)}'}), 400
    sql_repo.execute_update(
        "UPDATE code_sessions SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, sid))
    return jsonify({'code': 200, 'success': True, 'data': None, 'message': '操作成功'})
