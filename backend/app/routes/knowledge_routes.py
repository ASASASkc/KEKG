# -*- coding: utf-8 -*-
from flask import Blueprint, request
from ..services.knowledge_service import knowledge_service
from ..utils.response import ok, created, not_found, fail
from ..utils.auth import require_admin, require_auth
from ..utils.operation_logger import record_log

knowledge_bp = Blueprint('knowledge', __name__)


@knowledge_bp.route('/graph-groups', methods=['GET'])
@require_auth
def get_graph_groups():
    try:
        groups = knowledge_service.get_graph_groups()
        return ok(groups)
    except Exception as e:
        return fail(str(e), 500)


@knowledge_bp.route('/knowledge-points', methods=['GET'])
@require_auth
def get_all():
    try:
        label = request.args.get('label', '')
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 30))
        result = knowledge_service.get_all(
            label=label if label else None,
            page=page,
            page_size=page_size
        )
        return ok(result)
    except Exception as e:
        return fail(str(e), 500)


@knowledge_bp.route('/knowledge-points/<node_id>', methods=['GET'])
@require_auth
def get_one(node_id):
    try:
        node = knowledge_service.get_by_id(node_id)
        if node:
            return ok(node)
        return not_found('知识点不存在')
    except Exception as e:
        return fail(str(e), 500)


@knowledge_bp.route('/knowledge-points', methods=['POST'])
@require_admin
def create():
    try:
        data = request.get_json(force=True)
        node = knowledge_service.create(
            name=data.get('name'),
            category=data.get('category'),
            level=data.get('level') or data.get('knowledge_level'),
            difficulty=data.get('difficulty', 1),
            description=data.get('description'),
            source=data.get('source'),
            course_id=data.get('course_id')
        )
        record_log('创建知识点', '知识点管理', f'创建知识点 "{data.get("name", "")}"')
        return created(node, '知识点创建成功')
    except ValueError as e:
        return fail(str(e), 400)
    except Exception as e:
        return fail(str(e), 500)


@knowledge_bp.route('/knowledge-points/<node_id>', methods=['PUT'])
@require_admin
def update(node_id):
    try:
        data = request.get_json(force=True)
        old_name = data.get('name', '')
        node = knowledge_service.update(
            node_id=node_id,
            name=data.get('name'),
            category=data.get('category'),
            knowledge_level=data.get('knowledge_level') or data.get('category'),
            difficulty_level=data.get('difficulty_level') or data.get('difficulty'),
            description=data.get('description'),
            source=data.get('source'),
            course_id=data.get('course_id'),
            code_example=data.get('code_example'),
            syntax=data.get('syntax')
        )
        if node:
            record_log('更新知识点', '知识点管理', f'更新知识点 "{old_name}"')
            return ok(node, '更新成功')
        return not_found('知识点不存在')
    except ValueError as e:
        return fail(str(e), 400)
    except Exception as e:
        return fail(str(e), 500)


@knowledge_bp.route('/knowledge-points/<node_id>', methods=['DELETE'])
@require_admin
def delete(node_id):
    try:
        ok_flag = knowledge_service.delete(node_id)
        if ok_flag:
            record_log('删除知识点', '知识点管理', f'删除知识点 ID={node_id}')
            return ok(message='删除成功')
        return not_found('知识点不存在')
    except Exception as e:
        return fail(str(e), 500)


@knowledge_bp.route('/knowledge-points/search', methods=['GET'])
@require_auth
def search():
    try:
        keyword = request.args.get('keyword', '')
        if not keyword:
            return fail('搜索关键词不能为空', 400)
        label = request.args.get('label', '')
        nodes = knowledge_service.search(keyword, label=label if label else None)
        return ok(nodes)
    except Exception as e:
        return fail(str(e), 500)


@knowledge_bp.route('/knowledge-points/<node_id>/neighbors', methods=['GET'])
@require_auth
def neighbors(node_id):
    try:
        direction = request.args.get('direction', 'both')
        depth = int(request.args.get('depth', 1))
        data = knowledge_service.get_neighbors(node_id, direction, depth)
        return ok(data)
    except Exception as e:
        return fail(str(e), 500)
