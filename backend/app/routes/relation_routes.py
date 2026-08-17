# -*- coding: utf-8 -*-
from flask import Blueprint, request
from ..services.knowledge_service import relation_service
from ..utils.response import ok, created, fail
from ..utils.operation_logger import record_log
from ..utils.auth import require_auth, require_admin
from ..utils.pagination import get_pagination_params, paginate_list, paginate_response

relation_bp = Blueprint('relation', __name__)


@relation_bp.route('/relationships', methods=['GET'])
@require_auth
def get_all():
    try:
        page, page_size = get_pagination_params(request.args)
        rels = relation_service.get_all()
        items, total = paginate_list(rels, page, page_size)
        return ok(paginate_response(items, page, page_size, total))
    except Exception as e:
        return fail(str(e), 500)


@relation_bp.route('/relationships', methods=['POST'])
@require_admin
def create():
    try:
        data = request.get_json(force=True)
        rel = relation_service.create(
            source_id=data.get('source_id'),
            target_id=data.get('target_id'),
            rel_type=data.get('type') or data.get('relationship_type'),
            description=data.get('description')
        )
        record_log('创建关系', '关系管理', f'{data.get("type")}: {data.get("source_id")} → {data.get("target_id")}')
        return created(rel, '关系创建成功')
    except ValueError as e:
        return fail(str(e), 400)
    except Exception as e:
        return fail(str(e), 500)


@relation_bp.route('/relationships/<rel_id>', methods=['DELETE'])
@require_admin
def delete(rel_id):
    try:
        relation_service.delete(rel_id)
        record_log('删除关系', '关系管理', f'删除关系 ID={rel_id}')
        return ok(message='关系已删除')
    except Exception as e:
        return fail(str(e), 500)


@relation_bp.route('/relationships/types', methods=['GET'])
@require_auth
def get_types():
    return ok(relation_service.RELATION_TYPES)


@relation_bp.route('/relationships/by-type/<rel_type>', methods=['GET'])
@require_auth
def get_by_type(rel_type):
    try:
        rels = relation_service.get_by_type(rel_type)
        return ok(rels)
    except Exception as e:
        return fail(str(e), 500)


@relation_bp.route('/relationships/find-path', methods=['POST'])
@require_auth
def find_path():
    try:
        data = request.get_json(force=True)
        paths = relation_service.find_path(
            start_id=data.get('start_id'),
            end_id=data.get('end_id'),
            max_depth=data.get('max_depth', 5)
        )
        return ok(paths)
    except Exception as e:
        return fail(str(e), 500)
