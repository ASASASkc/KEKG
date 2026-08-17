# -*- coding: utf-8 -*-
"""代码编辑器路由"""
import json
from flask import Blueprint, request, jsonify, current_app
from ..utils.auth import require_auth, require_admin
from ..services.code_editor_service import code_editor_service
from ..services.activity_service import activity_service
from ..utils.operation_logger import record_log
from ..utils.rate_limit import rate_limit

editor_bp = Blueprint('code_editor', __name__)

@editor_bp.route('/code-exercises', methods=['GET'])
@require_auth
def list_exercises():
    page = request.args.get('page', 1, type=int)
    my_only = request.args.get('my', '0') == '1'
    user_id = request.current_user['user_id'] if my_only else None
    result = code_editor_service.get_exercises(page, created_by=user_id)
    return jsonify({'code': 200, 'success': True, 'data': result})

@editor_bp.route('/code-exercises/<int:eid>', methods=['GET'])
@require_auth
def get_exercise(eid):
    ex = code_editor_service.get_exercise(eid)
    if not ex:
        return jsonify({'code': 404, 'success': False, 'message': '题目不存在'}), 404
    return jsonify({'code': 200, 'success': True, 'data': ex})

@editor_bp.route('/code-exercises', methods=['POST'])
@require_admin
def create_exercise():
    data = request.get_json(force=True) or {}
    user_id = request.current_user['user_id']
    ex = code_editor_service.create_exercise(
        title=data.get('title', ''),
        description=data.get('description', ''),
        language=data.get('language', 'python'),
        template_code=data.get('template_code', ''),
        test_cases=data.get('test_cases', []),
        knowledge_point_id=data.get('knowledge_point_id', ''),
        knowledge_point_name=data.get('knowledge_point_name', ''),
        difficulty=data.get('difficulty', 1),
        created_by=user_id
    )
    record_log('创建代码题', '代码编辑器', f'创建代码题 "{ex["title"]}"')
    return jsonify({'code': 200, 'success': True, 'data': ex, 'message': '创建成功'})

@editor_bp.route('/code-exercises/<int:eid>', methods=['PUT'])
@require_admin
def update_exercise(eid):
    data = request.get_json(force=True) or {}
    sets = []
    params = []
    for k in ['title', 'description', 'template_code', 'test_cases', 'difficulty']:
        if k in data:
            sets.append(f"{k} = ?")
            val = json.dumps(data[k]) if k == 'test_cases' and isinstance(data[k], list) else data[k]
            params.append(val)
    if sets:
        params.append(eid)
        from ..repositories.sql_repo import sql_repo
        sql_repo.execute_update(f"UPDATE code_exercises SET {', '.join(sets)} WHERE id = ?", params)
    return jsonify({'code': 200, 'success': True, 'message': '更新成功'})

@editor_bp.route('/code-exercises/<int:eid>', methods=['DELETE'])
@require_admin
def delete_exercise(eid):
    from ..repositories.sql_repo import sql_repo
    sql_repo.execute_update("UPDATE code_exercises SET status = 'deleted' WHERE id = ?", (eid,))
    return jsonify({'code': 200, 'success': True, 'message': '已删除'})

@editor_bp.route('/code-run', methods=['POST'])
@require_auth
@rate_limit(max_requests=10, window_seconds=60)
def run_code():
    data = request.get_json(force=True) or {}
    result = code_editor_service.run_code(
        code=data.get('code', ''),
        language=data.get('language', 'python')
    )
    return jsonify({'code': 200, 'success': True, 'data': result})

@editor_bp.route('/code-submit', methods=['POST'])
@require_auth
def submit_code():
    user_id = request.current_user['user_id']
    data = request.get_json(force=True) or {}
    result = code_editor_service.submit_code(
        exercise_id=data.get('exercise_id', 0),
        user_id=user_id,
        code=data.get('code', '')
    )
    # 记录活动
    try:
        activity_service.log(
            user_id=user_id,
            activity_type='code',
            activity_subtype='submit',
            score=result.get('score', 0),
            related_id=data.get('exercise_id', 0),
            detail=f'代码练习提交'
        )
    except Exception as e:
        current_app.logger.warning('[CodeEditorRoute] activity log failed: %s', str(e))
    return jsonify({'code': 200, 'success': True, 'data': result})

@editor_bp.route('/code-exercises/<int:eid>/answers', methods=['GET'])
@require_auth
def get_answers(eid):
    answers = code_editor_service.get_answers(eid)
    return jsonify({'code': 200, 'success': True, 'data': answers})

@editor_bp.route('/code-exercises/<int:eid>/answers', methods=['POST'])
@require_auth
def add_answer(eid):
    user_id = request.current_user['user_id']
    data = request.get_json(force=True) or {}
    answer_type = data.get('answer_type', 'user')
    # 服务端白名单校验答案类型，防止普通用户伪造标准答案
    if answer_type not in ('user', 'standard', 'ai'):
        return jsonify({'code': 400, 'success': False, 'message': '无效的答案类型'}), 400
    if answer_type == 'standard' and request.current_user.get('role') != 'admin':
        return jsonify({'code': 403, 'success': False, 'message': '仅管理员可提交标准答案'}), 403
    result = code_editor_service.add_answer(
        exercise_id=eid,
        user_id=user_id,
        code=data.get('code', ''),
        explanation=data.get('explanation', ''),
        answer_type=answer_type
    )
    return jsonify({'code': 200, 'success': True, 'data': result})

@editor_bp.route('/code-exercises/<int:eid>/ai-answer', methods=['POST'])
@require_auth
def generate_ai_answer(eid):
    result = code_editor_service.generate_ai_answer(eid)
    if not result:
        return jsonify({'code': 404, 'success': False, 'message': '题目不存在'}), 404
    # 保存AI答案
    code_editor_service.add_answer(eid, request.current_user['user_id'], result['code'], result['explanation'], 'ai')
    return jsonify({'code': 200, 'success': True, 'data': result})


# ── 代码片段（个人代码库）──

@editor_bp.route('/code-snippets', methods=['GET'])
@require_auth
def list_snippets():
    user_id = request.current_user['user_id']
    snippet_service = code_editor_service._get_snippet_service()
    snips = snippet_service.list(user_id)
    return jsonify({'code': 200, 'success': True, 'data': snips})


@editor_bp.route('/code-snippets', methods=['POST'])
@require_auth
def create_snippet():
    user_id = request.current_user['user_id']
    data = request.get_json(force=True) or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'code': 400, 'success': False, 'message': '请输入片段名称'}), 400
    snippet_service = code_editor_service._get_snippet_service()
    snip = snippet_service.create(
        user_id=user_id,
        title=title,
        code=data.get('code', ''),
        language=data.get('language', 'python')
    )
    return jsonify({'code': 200, 'success': True, 'data': snip, 'message': '保存成功'})


@editor_bp.route('/code-snippets/<int:sid>', methods=['PUT'])
@require_auth
def update_snippet(sid):
    user_id = request.current_user['user_id']
    data = request.get_json(force=True) or {}
    snippet_service = code_editor_service._get_snippet_service()
    snip = snippet_service.update(sid, user_id, code=data.get('code', ''), title=data.get('title'), language=data.get('language'))
    if not snip:
        return jsonify({'code': 404, 'success': False, 'message': '片段不存在'}), 404
    return jsonify({'code': 200, 'success': True, 'data': snip, 'message': '保存成功'})


@editor_bp.route('/code-snippets/<int:sid>', methods=['DELETE'])
@require_auth
def delete_snippet(sid):
    user_id = request.current_user['user_id']
    snippet_service = code_editor_service._get_snippet_service()
    ok = snippet_service.delete(sid, user_id)
    if not ok:
        return jsonify({'code': 404, 'success': False, 'message': '片段不存在'}), 404
    return jsonify({'code': 200, 'success': True, 'message': '已删除'})
