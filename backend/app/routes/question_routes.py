# -*- coding: utf-8 -*-
"""题库路由"""
from flask import Blueprint, request, jsonify, Response
from ..services.question_service import question_service
from ..utils.auth import require_auth, require_admin
from ..utils.operation_logger import record_log

question_bp = Blueprint('questions', __name__)


# ── 题目 CRUD ──

@question_bp.route('/questions', methods=['GET'])
@require_auth
def list_questions():
    user = request.current_user
    kwargs = {}
    if request.args.get('type'):
        kwargs['qtype'] = request.args.get('type')
    if request.args.get('category'):
        kwargs['category'] = request.args.get('category')
    if request.args.get('topic'):
        kwargs['topic'] = request.args.get('topic')
    if request.args.get('difficulty'):
        kwargs['difficulty'] = int(request.args.get('difficulty'))
    if request.args.get('difficulty_min'):
        kwargs['difficulty_min'] = int(request.args.get('difficulty_min'))
    if request.args.get('difficulty_max'):
        kwargs['difficulty_max'] = int(request.args.get('difficulty_max'))
    if request.args.get('keyword'):
        kwargs['keyword'] = request.args.get('keyword')
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 50, type=int)

    # 状态过滤：普通用户只能看已通过审核的题目，管理员可指定 status 参数
    if user.get('role') != 'admin':
        kwargs['status'] = 'approved'
    elif request.args.get('status'):
        kwargs['status'] = request.args.get('status')

    data = question_service.query(page=page, page_size=page_size, **kwargs)
    return jsonify({'code': 200, 'success': True, 'data': data, 'message': '操作成功'})


@question_bp.route('/questions/stats', methods=['GET'])
@require_admin
def question_stats():
    """题库统计分析（管理员）"""
    data = question_service.get_stats()
    return jsonify({'code': 200, 'success': True, 'data': data, 'message': '操作成功'})


@question_bp.route('/questions/<int:qid>', methods=['GET'])
@require_auth
def get_question(qid):
    q = question_service.get_by_id(qid)
    if not q:
        return jsonify({'code': 404, 'success': False, 'message': '题目不存在'}), 404
    # 非管理员仅可查看已审核通过的题目
    if request.current_user.get('role') != 'admin' and q.get('status') != 'approved':
        return jsonify({'code': 404, 'success': False, 'message': '题目不存在'}), 404
    return jsonify({'code': 200, 'success': True, 'data': q, 'message': '操作成功'})


@question_bp.route('/questions', methods=['POST'])
@require_admin
def create_question():
    data = request.get_json(force=True) or {}
    user_id = request.current_user.get('user_id', 1)
    try:
        q = question_service.create(
            title=data.get('title', ''),
            qtype=data.get('type', ''),
            answer=data.get('answer', ''),
            options=data.get('options'),
            is_multi=data.get('is_multi', False),
            category=data.get('category', ''),
            explanation=data.get('explanation', ''),
            knowledge_point_id=data.get('knowledge_point_id', ''),
            knowledge_point_name=data.get('knowledge_point_name', ''),
            knowledge_point_ids=data.get('knowledge_point_ids'),
            topic=data.get('topic', ''),
            created_by=user_id
        )
        record_log('创建题目', '题库管理', f'题目标题: {q.get("title", "")[:30]}')
        return jsonify({'code': 200, 'success': True, 'data': q, 'message': '创建成功'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400


@question_bp.route('/questions/<int:qid>', methods=['PUT'])
@require_admin
def update_question(qid):
    data = request.get_json(force=True) or {}
    try:
        q = question_service.update(qid, **data)
        if not q:
            return jsonify({'code': 404, 'success': False, 'message': '题目不存在'}), 404
        record_log('编辑题目', '题库管理', f'题目ID: {qid}')
        return jsonify({'code': 200, 'success': True, 'data': q, 'message': '更新成功'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400


@question_bp.route('/questions/<int:qid>', methods=['DELETE'])
@require_admin
def delete_question(qid):
    question_service.delete(qid)
    record_log('删除题目', '题库管理', f'题目ID: {qid}')
    return jsonify({'code': 200, 'success': True, 'message': '删除成功'})


@question_bp.route('/questions/batch-delete', methods=['POST'])
@require_admin
def batch_delete():
    data = request.get_json(force=True) or {}
    ids = data.get('ids', [])
    if not ids:
        return jsonify({'code': 400, 'success': False, 'message': '请选择题目'}), 400
    question_service.batch_delete(ids)
    record_log('批量删除题目', '题库管理', f'删除 {len(ids)} 题')
    return jsonify({'code': 200, 'success': True, 'message': f'成功删除 {len(ids)} 题'})


# ── 题目收藏 ──

@question_bp.route('/questions/favorites', methods=['GET'])
@require_auth
def list_favorites():
    """个人收藏夹"""
    user_id = request.current_user['user_id']
    page = request.args.get('page', 1, type=int)
    page_size = min(request.args.get('page_size', 20, type=int), 100)
    data = question_service.query_favorites(user_id, page=page, page_size=page_size)
    return jsonify({'code': 200, 'success': True, 'data': data, 'message': '操作成功'})


@question_bp.route('/questions/<int:qid>/favorite', methods=['PUT', 'DELETE'])
@require_auth
def toggle_favorite(qid):
    """收藏(PUT) / 取消收藏(DELETE)"""
    q = question_service.get_by_id(qid)
    if not q:
        return jsonify({'code': 404, 'success': False, 'message': '题目不存在'}), 404
    user_id = request.current_user['user_id']
    if request.method == 'PUT':
        question_service.add_favorite(user_id, qid)
        return jsonify({'code': 200, 'success': True, 'data': {'favorited': True}, 'message': '已收藏'})
    question_service.remove_favorite(user_id, qid)
    return jsonify({'code': 200, 'success': True, 'data': {'favorited': False}, 'message': '已取消收藏'})


# ── AI 题目审核 ──

@question_bp.route('/questions/<int:qid>/approve', methods=['POST'])
@require_admin
def approve_question(qid):
    """审核通过 AI 生成的题目"""
    success = question_service.set_status(qid, 'approved')
    if not success:
        return jsonify({'code': 404, 'success': False, 'message': '题目不存在'}), 404
    record_log('审核题目', '题库管理', f'题目ID={qid} 审核通过')
    return jsonify({'code': 200, 'success': True, 'message': '审核通过'})


@question_bp.route('/questions/<int:qid>/reject', methods=['POST'])
@require_admin
def reject_question(qid):
    """驳回/删除 AI 生成的题目"""
    success = question_service.set_status(qid, 'rejected')
    if not success:
        return jsonify({'code': 404, 'success': False, 'message': '题目不存在'}), 404
    record_log('驳回题目', '题库管理', f'题目ID={qid} 被驳回')
    return jsonify({'code': 200, 'success': True, 'message': '已驳回'})


# ── 分类管理 ──

@question_bp.route('/question-categories', methods=['GET'])
@require_auth
def get_categories():
    cats = question_service.get_categories()
    return jsonify({'code': 200, 'success': True, 'data': cats, 'message': '操作成功'})


@question_bp.route('/question-categories', methods=['POST'])
@require_admin
def add_category():
    data = request.get_json(force=True) or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'code': 400, 'success': False, 'message': '分类名不能为空'}), 400
    result = question_service.add_category(name)
    record_log('添加分类', '题库管理', f'分类: {name}')
    return jsonify({'code': 200, 'success': True, 'data': result, 'message': '添加成功'})


@question_bp.route('/question-categories/<name>', methods=['DELETE'])
@require_admin
def delete_category(name):
    try:
        question_service.delete_category(name)
        record_log('删除分类', '题库管理', f'分类: {name}')
        return jsonify({'code': 200, 'success': True, 'message': '删除成功'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400


@question_bp.route('/question-topics', methods=['GET'])
@require_auth
def get_topics():
    topics = question_service.get_topics()
    return jsonify({'code': 200, 'success': True, 'data': topics, 'message': '操作成功'})


# ── 导入导出 ──

@question_bp.route('/questions/import/excel', methods=['POST'])
@require_admin
def import_excel():
    """上传 Excel 文件导入"""
    if 'file' not in request.files:
        return jsonify({'code': 400, 'success': False, 'message': '请选择 Excel 文件'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'code': 400, 'success': False, 'message': '请选择文件'}), 400

    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        return jsonify({'code': 400, 'success': False, 'message': '仅支持 .xlsx / .xls 文件'}), 400

    if request.content_length and request.content_length > 50 * 1024 * 1024:
        return jsonify({'code': 400, 'success': False, 'message': '文件大小不能超过 50MB'}), 400

    user_id = request.current_user.get('user_id', 1)
    try:
        result = question_service.import_excel(file.stream, created_by=user_id)
        total = result['success_count'] + result['error_count']
        record_log('Excel导入题目', '题库管理',
                   f'成功 {result["success_count"]} 题, 失败 {result["error_count"]} 题')
        return jsonify({'code': 200, 'success': True, 'data': result,
                        'message': f'导入完成: 成功 {result["success_count"]}/{total} 题'})
    except Exception as e:
        return jsonify({'code': 400, 'success': False, 'message': f'导入失败: {str(e)}'}), 400


@question_bp.route('/questions/import/word', methods=['POST'])
@require_admin
def import_word():
    """上传 Word 文件导入"""
    if 'file' not in request.files:
        return jsonify({'code': 400, 'success': False, 'message': '请选择 Word 文件'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'code': 400, 'success': False, 'message': '请选择文件'}), 400
    if not file.filename.lower().endswith('.docx'):
        return jsonify({'code': 400, 'success': False, 'message': '仅支持 .docx 文件'}), 400

    user_id = request.current_user.get('user_id', 1)
    try:
        result = question_service.import_word(file, created_by=user_id)
        total = result['success_count'] + result['error_count']
        record_log('Word导入题目', '题库管理', f'成功 {result["success_count"]} 题, 失败 {result["error_count"]} 题')
        return jsonify({'code': 200, 'success': True, 'data': result,
                        'message': f'导入完成: 成功 {result["success_count"]}/{total} 题'})
    except Exception as e:
        return jsonify({'code': 400, 'success': False, 'message': f'导入失败: {str(e)}'}), 400


@question_bp.route('/questions/export/<fmt>', methods=['GET'])
@require_admin
def export_questions(fmt):
    """导出题目: excel / word"""
    ids_raw = request.args.get('ids', '')
    ids = [int(x) for x in ids_raw.split(',') if x.strip().isdigit()] if ids_raw else None

    questions = question_service.get_all_for_export(ids)
    record_log('导出题目', '题库管理', f'导出 {len(questions)} 题, 格式={fmt}')

    if fmt == 'word':
        word_data = question_service.export_word(ids)
        return Response(word_data,
                        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        headers={'Content-Disposition': 'attachment; filename=questions.docx'})
    else:  # excel (default)
        excel_data = question_service.export_excel(ids)
        return Response(excel_data,
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        headers={'Content-Disposition': 'attachment; filename=questions.xlsx'})
