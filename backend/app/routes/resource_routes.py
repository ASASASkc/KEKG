# -*- coding: utf-8 -*-
"""学习资源路由"""
from flask import Blueprint, request, jsonify
from ..services.resource_service import ResourceService
from ..utils.auth import require_auth, require_admin
from ..utils.operation_logger import record_log

resource_bp = Blueprint('resources', __name__)


@resource_bp.route('/resources', methods=['GET'])
@require_auth
def list_resources():
    kwargs = {}
    if request.args.get('type'):
        kwargs['rtype'] = request.args.get('type')
    if request.args.get('knowledge_point_id'):
        kwargs['knowledge_point_id'] = request.args.get('knowledge_point_id')
    if request.args.get('keyword'):
        kwargs['keyword'] = request.args.get('keyword')
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 50, type=int)

    data = ResourceService.query(page=page, page_size=page_size, **kwargs)
    return jsonify({'code': 200, 'success': True, 'data': data, 'message': '操作成功'})


@resource_bp.route('/resources/<int:rid>', methods=['GET'])
@require_auth
def get_resource(rid):
    r = ResourceService.get_by_id(rid)
    if not r:
        return jsonify({'code': 404, 'success': False, 'message': '资源不存在'}), 404
    return jsonify({'code': 200, 'success': True, 'data': r, 'message': '操作成功'})


@resource_bp.route('/resources', methods=['POST'])
@require_admin
def create_resource():
    data = request.get_json(force=True) or {}
    user_id = request.current_user.get('user_id', 1)
    try:
        r = ResourceService.create(
            title=data.get('title', ''),
            rtype=data.get('type', 'doc'),
            knowledge_point_id=data.get('knowledge_point_id', ''),
            url=data.get('url', ''),
            content=data.get('content', ''),
            tags=data.get('tags', ''),
            created_by=user_id
        )
        record_log('创建资源', '资源管理', f'资源: {r.get("title","")[:30]}')
        return jsonify({'code': 200, 'success': True, 'data': r, 'message': '创建成功'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400


@resource_bp.route('/resources/<int:rid>', methods=['PUT'])
@require_admin
def update_resource(rid):
    data = request.get_json(force=True) or {}
    try:
        ResourceService.update(rid, **data)
        record_log('编辑资源', '资源管理', f'资源ID: {rid}')
        return jsonify({'code': 200, 'success': True, 'message': '更新成功'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400


@resource_bp.route('/resources/<int:rid>', methods=['DELETE'])
@require_admin
def delete_resource(rid):
    ResourceService.delete(rid)
    record_log('删除资源', '资源管理', f'资源ID: {rid}')
    return jsonify({'code': 200, 'success': True, 'message': '删除成功'})


@resource_bp.route('/resources/batch-delete', methods=['POST'])
@require_admin
def batch_delete():
    data = request.get_json(force=True) or {}
    ids = data.get('ids', [])
    if not ids:
        return jsonify({'code': 400, 'success': False, 'message': '请选择资源'}), 400
    ResourceService.batch_delete(ids)
    record_log('批量删除资源', '资源管理', f'删除 {len(ids)} 个')
    return jsonify({'code': 200, 'success': True, 'message': f'成功删除 {len(ids)} 个'})


# ── 推送接口 ──

@resource_bp.route('/resources/for-path', methods=['POST'])
@require_auth
def resources_for_path():
    """学习路径推送：传入知识点 ID 列表，返回各知识点的资源"""
    data = request.get_json(force=True) or {}
    kp_ids = data.get('knowledge_point_ids', [])
    if not kp_ids:
        return jsonify({'code': 400, 'success': False, 'message': '请提供知识点列表'}), 400
    result = ResourceService.get_for_path(kp_ids)
    return jsonify({'code': 200, 'success': True, 'data': result, 'message': '操作成功'})


@resource_bp.route('/resources/types', methods=['GET'])
@require_auth
def get_types():
    return jsonify({
        'code': 200, 'success': True,
        'data': [
            {'value': t, 'label': ResourceService.TYPE_LABELS[t]}
            for t in ResourceService.TYPES
        ],
        'message': '操作成功'
    })


@resource_bp.route('/resources/import/markdown', methods=['POST'])
@require_admin
def import_markdown():
    """上传 Markdown 文件批量导入资源"""
    if 'file' not in request.files:
        return jsonify({'code': 400, 'success': False, 'message': '请选择 Markdown 文件'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'code': 400, 'success': False, 'message': '请选择文件'}), 400
    if not file.filename.lower().endswith(('.md', '.markdown', '.txt')):
        return jsonify({'code': 400, 'success': False, 'message': '仅支持 .md / .markdown / .txt 文件'}), 400

    user_id = request.current_user.get('user_id', 1)
    try:
        raw = file.read()
        if len(raw) > 5 * 1024 * 1024:
            return jsonify({'code': 400, 'success': False, 'message': '文件过大，最大支持 5MB'}), 400
        text = raw.decode('utf-8')
        result = ResourceService.import_markdown(text, created_by=user_id)
        total = result['success_count'] + result['error_count']
        record_log('Markdown导入资源', '资源管理',
                   f'成功 {result["success_count"]}, 跳过 {result.get("skipped_count", 0)}')
        return jsonify({'code': 200, 'success': True, 'data': result,
                        'message': f'导入完成: 成功 {result["success_count"]}/{total or result.get("total_rows", 0)}'})
    except UnicodeDecodeError:
        return jsonify({'code': 400, 'success': False, 'message': '文件编码错误，请使用 UTF-8 编码'}), 400
    except Exception as e:
        return jsonify({'code': 400, 'success': False, 'message': f'导入失败: {str(e)}'}), 400


@resource_bp.route('/resources/export/template-markdown', methods=['GET'])
@require_auth
def export_template_markdown():
    """下载 Markdown 导入模板"""
    from io import BytesIO
    from flask import send_file
    from ..utils.markdown_helper import generate_template_bytes
    return send_file(generate_template_bytes(),
                     mimetype='text/markdown; charset=utf-8',
                     as_attachment=True,
                     download_name='学习资源导入模板.md')
