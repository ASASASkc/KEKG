# -*- coding: utf-8 -*-
from flask import Blueprint, request
from ..services.graph_service import graph_service
from ..services.track_service import track_service
from ..repositories.graph_repo import graph_repo
from ..utils.response import ok, fail
from ..utils.auth import require_auth, require_admin
from ..utils.pagination import get_pagination_params, paginate_list, paginate_response
import os

graph_bp = Blueprint('graph', __name__)


@graph_bp.route('/graph/tracks', methods=['GET'])
@require_auth
def get_tracks():
    """列出所有赛道"""
    try:
        page, page_size = get_pagination_params(request.args)
        tracks = track_service.list_tracks()
        items, total = paginate_list(tracks, page, page_size)
        return ok(paginate_response(items, page, page_size, total))
    except Exception as e:
        return fail(str(e), 500)


@graph_bp.route('/graph/track/<track_name>', methods=['GET'])
@require_auth
def get_track_graph(track_name):
    """获取赛道子图"""
    try:
        data = track_service.get_track_graph(track_name)
        return ok(data)
    except Exception as e:
        return fail(str(e), 500)


@graph_bp.route('/graph/import-track', methods=['POST'])
@require_admin
def import_track():
    """导入单个赛道 JSON 文件（管理员）"""
    try:
        body = request.get_json(force=True)
        filepath = body.get('filepath', '')
        if not filepath:
            return fail('请提供文件路径', 400)
        result = track_service.import_track_json(filepath)
        return ok(result)
    except FileNotFoundError as e:
        return fail(str(e), 404)
    except Exception as e:
        return fail(str(e), 500)


@graph_bp.route('/graph/full', methods=['GET'])
@require_auth
def get_full_graph():
    try:
        page, page_size = get_pagination_params(request.args)
        label = request.args.get('label', '')
        data = graph_service.get_full_graph(label=label if label else None)
        nodes = data.get('nodes', [])
        relationships = data.get('relationships', [])
        items, total = paginate_list(nodes, page, page_size)
        # 过滤关系：只保留当前页节点之间的关联
        page_node_ids = {n.get('id') for n in items if isinstance(n, dict)}
        filtered_rels = [r for r in relationships
                         if r.get('start_node') in page_node_ids
                         and r.get('end_node') in page_node_ids]
        return ok(paginate_response(
            {'nodes': items, 'relationships': filtered_rels},
            page, page_size, total))
    except Exception as e:
        return fail(str(e), 500)


@graph_bp.route('/graph/statistics', methods=['GET'])
@require_auth
def get_statistics():
    try:
        stats = graph_service.get_statistics()
        return ok(stats)
    except Exception as e:
        return fail(str(e), 500)


@graph_bp.route('/graph/subgraph', methods=['POST'])
@require_auth
def get_subgraph():
    try:
        data = request.get_json(force=True)
        center_id = data.get('center_id')
        depth = min(int(data.get('depth', 1)), 10)
        if not center_id:
            return fail('请指定中心节点 center_id', 400)
        result = graph_service.get_subgraph(center_id, depth)
        return ok(result)
    except Exception as e:
        return fail(str(e), 500)


@graph_bp.route('/graph/path', methods=['POST'])
@require_auth
def find_graph_path():
    try:
        data = request.get_json(force=True)
        start_id = data.get('start_id')
        end_id = data.get('end_id')
        max_depth = min(int(data.get('max_depth', 5)), 15)
        if not start_id or not end_id:
            return fail('请指定 start_id 和 end_id', 400)
        paths = graph_service.find_paths(start_id, end_id, max_depth)
        return ok(paths)
    except Exception as e:
        return fail(str(e), 500)


@graph_bp.route('/graph/node/<node_id>/neighbors', methods=['GET'])
@require_auth
def get_node_neighbors(node_id):
    try:
        depth = min(int(request.args.get('depth', 1)), 10)
        direction = request.args.get('direction', 'both')
        rel_type = request.args.get('rel_type')
        result = graph_service.get_neighbors(node_id, depth, direction, rel_type)
        return ok(result)
    except Exception as e:
        return fail(str(e), 500)


@graph_bp.route('/graph/node/<node_id>/children', methods=['GET'])
@require_auth
def get_node_children(node_id):
    try:
        result = graph_service.get_children(node_id)
        return ok(result)
    except Exception as e:
        return fail(str(e), 500)


@graph_bp.route('/graph/tree', methods=['GET'])
@require_auth
def get_tree():
    try:
        label = request.args.get('label', '')
        tree = graph_service.get_tree(label=label if label else None)
        return ok(tree)
    except Exception as e:
        return fail(str(e), 500)


@graph_bp.route('/graph/nodes', methods=['GET'])
@require_auth
def get_nodes():
    """获取所有知识点节点（供资源管理等模块使用）"""
    try:
        page, page_size = get_pagination_params(request.args)
        nodes = graph_repo.get_all_nodes(label='KnowledgePoint')
        result = [{'name': n.get('name', ''), 'elementId': n.get('elementId', '')} for n in nodes]
        items, total = paginate_list(result, page, page_size)
        return ok(paginate_response(items, page, page_size, total))
    except Exception as e:
        return fail(str(e), 500)


@graph_bp.route('/graph/full-tree', methods=['GET'])
@require_auth
def get_full_tree():
    """获取 5 级完整知识树（Python > 赛道 > 章 > 节 > 知识点）"""
    try:
        tree = graph_service.build_full_tree()
        return ok(tree)
    except Exception as e:
        return fail(str(e), 500)
