# -*- coding: utf-8 -*-
from flask import Blueprint, request
from ..repositories.graph_repo import graph_repo
from ..utils.response import ok, created, not_found, fail
from ..utils.auth import require_auth, require_admin
from ..utils.operation_logger import record_log
from ..utils.pagination import get_pagination_params, paginate_list, paginate_response

entity_bp = Blueprint('entity', __name__)


@entity_bp.route('/entities', methods=['GET'])
@require_auth
def get_all():
    try:
        page, page_size = get_pagination_params(request.args)
        label = request.args.get('label')
        nodes = graph_repo.get_all_nodes(label)
        items, total = paginate_list(nodes, page, page_size)
        return ok(paginate_response(items, page, page_size, total))
    except Exception as e:
        return fail(str(e), 500)


@entity_bp.route('/entities', methods=['POST'])
@require_admin
def create():
    try:
        data = request.get_json(force=True)
        label = data.get('label', 'Entity')
        name = data.get('name')
        if not name:
            return fail('实体名称不能为空', 400)
        node = graph_repo.create_node(label, {
            'name': name,
            'description': data.get('description', ''),
            **{k: v for k, v in data.items() if k not in ('label', 'name', 'description')}
        })
        record_log('创建实体', '实体管理', f'创建实体 "{name}" (label={label})')
        return created(node, '实体创建成功')
    except Exception as e:
        return fail(str(e), 500)


@entity_bp.route('/entities/<node_id>', methods=['GET'])
@require_auth
def get_one(node_id):
    try:
        node = graph_repo.get_node_by_id(node_id)
        if node.get('id'):
            return ok(node)
        return not_found('实体不存在')
    except Exception as e:
        return fail(str(e), 500)


@entity_bp.route('/entities/<node_id>', methods=['PUT'])
@require_admin
def update(node_id):
    try:
        data = request.get_json(force=True)
        node = graph_repo.update_node(node_id, data)
        if node:
            record_log('更新实体', '实体管理', f'更新实体 "{data.get("name", node_id)}"')
            return ok(node, '更新成功')
        return not_found('实体不存在')
    except Exception as e:
        return fail(str(e), 500)


@entity_bp.route('/entities/<node_id>', methods=['DELETE'])
@require_admin
def delete(node_id):
    try:
        ok_flag = graph_repo.delete_node(node_id)
        if ok_flag:
            record_log('删除实体', '实体管理', f'删除实体 ID={node_id}')
            return ok(message='删除成功')
        return not_found('实体不存在')
    except Exception as e:
        return fail(str(e), 500)


# ── 分类管理 ──────────────────────────────

@entity_bp.route('/categories', methods=['GET'])
@require_auth
def get_categories():
    try:
        page, page_size = get_pagination_params(request.args)
        nodes = graph_repo.get_all_nodes('Category')
        items, total = paginate_list(nodes, page, page_size)
        return ok(paginate_response(items, page, page_size, total))
    except Exception as e:
        return fail(str(e), 500)


@entity_bp.route('/categories', methods=['POST'])
@require_admin
def create_category():
    try:
        data = request.get_json(force=True)
        name = data.get('name')
        if not name:
            return fail('分类名称不能为空', 400)
        node = graph_repo.create_node('Category', {
            'name': name,
            'description': data.get('description', ''),
            'parent_id': data.get('parent_id')
        })
        record_log('创建分类', '实体管理', f'创建分类 "{name}"')
        return created(node, '分类创建成功')
    except Exception as e:
        return fail(str(e), 500)
