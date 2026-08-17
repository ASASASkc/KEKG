# -*- coding: utf-8 -*-
"""图谱管理路由 — 图谱标签管理 + 数据导入导出"""
from flask import Blueprint, request, jsonify, Response, current_app
from ..services.import_export_service import import_service, export_service
from ..repositories.graph_repo import graph_repo
from ..repositories.sql_repo import sql_repo
from ..utils.operation_logger import record_log
from ..utils.auth import require_auth, require_admin
from ..utils.pagination import get_pagination_params, paginate_list, paginate_response

gm_bp = Blueprint('graph_management', __name__)

# ════════════════════════════════════════════════
#  图谱标签管理
# ════════════════════════════════════════════════

@gm_bp.route('/graph-management/labels', methods=['GET'])
@require_auth
def list_labels():
    """获取所有图谱标签及其统计"""
    try:
        # 从图存储获取各 label 的节点数
        all_nodes = graph_repo.get_all_nodes()
        label_counts = {}
        for n in all_nodes:
            for lb in n.get('labels', []):
                label_counts[lb] = label_counts.get(lb, 0) + 1

        # 从 MySQL 获取标签元数据（display_name, description）
        meta_rows = sql_repo.execute_query(
            "SELECT label, display_name, description, created_by, created_at FROM graph_labels"
        )
        meta_map = {r['label']: r for r in meta_rows}

        result = []
        for lb, count in label_counts.items():
            if lb == 'Category':
                continue
            meta = meta_map.get(lb, {})
            result.append({
                'label': lb,
                'display_name': meta.get('display_name', lb),
                'description': meta.get('description', ''),
                'node_count': count,
                'created_at': str(meta.get('created_at', '')) if meta.get('created_at') else ''
            })

        # 补充 MySQL 中有但图中无节点的图谱（新建的空图谱）
        for lb, meta in meta_map.items():
            if lb not in label_counts and lb != 'Category':
                result.append({
                    'label': lb,
                    'display_name': meta.get('display_name', lb),
                    'description': meta.get('description', ''),
                    'node_count': 0,
                    'created_at': str(meta.get('created_at', '')) if meta.get('created_at') else ''
                })

        # 排序：按 node_count 降序
        result.sort(key=lambda x: x['node_count'], reverse=True)
        page, page_size = get_pagination_params(request.args)
        items, total = paginate_list(result, page, page_size)
        return jsonify({
            'code': 200, 'success': True,
            'data': paginate_response(items, page, page_size, total),
            'message': 'OK'
        })
    except Exception as e:
        return jsonify({'code': 500, 'success': False, 'message': str(e)}), 500


@gm_bp.route('/graph-management/labels', methods=['POST'])
@require_admin
def create_label():
    """创建新图谱标签"""
    data = request.get_json(force=True) or {}
    label = data.get('label', '').strip()
    display_name = data.get('display_name', '').strip()

    if not label:
        return jsonify({'code': 400, 'success': False, 'message': '图谱标识（label）不能为空'}), 400
    if not display_name:
        display_name = label

    # 检查是否已存在
    existing = sql_repo.execute_query(
        "SELECT label FROM graph_labels WHERE label = ?", (label,)
    )
    if existing:
        return jsonify({'code': 400, 'success': False, 'message': f'图谱 "{label}" 已存在'}), 400

    # 检查图存储中是否已有该 label 的节点（防止与已有数据冲突）
    existing_nodes = graph_repo.get_all_nodes(label)
    if existing_nodes:
        return jsonify({
            'code': 400, 'success': False,
            'message': f'已存在 {len(existing_nodes)} 个标签为 "{label}" 的节点，不能重复创建'
        }), 400

    user_id = request.current_user.get('user_id')
    sql_repo.execute_insert(
        """INSERT INTO graph_labels (label, display_name, description, created_by)
           VALUES (?, ?, ?, ?)""",
        (label, display_name, data.get('description', ''), user_id)
    )
    record_log('创建图谱', '图谱管理', f'创建图谱 "{display_name}" (label={label})')
    return jsonify({
        'code': 200, 'success': True,
        'data': {'label': label, 'display_name': display_name, 'node_count': 0},
        'message': f'图谱 "{display_name}" 创建成功'
    })


@gm_bp.route('/graph-management/labels/<label>', methods=['DELETE'])
@require_admin
def delete_label(label):
    """删除图谱标签及其所有节点和关系（级联删除 — 双事务保护）"""
    try:
        nodes = graph_repo.get_all_nodes(label)
        if not nodes and not sql_repo.execute_query(
            "SELECT label FROM graph_labels WHERE label = ?", (label,)
        ):
            return jsonify({'code': 404, 'success': False, 'message': '图谱不存在'}), 404

        node_count = len(nodes)

        # 双事务：先删 Neo4j，再删 MySQL，任一失败全部回滚
        graph_repo.begin_transaction()
        sql_repo.begin_transaction()
        try:
            for n in nodes:
                graph_repo.delete_node(n['id'])
            sql_repo.execute_update("DELETE FROM graph_labels WHERE label = ?", (label,))
            graph_repo.commit_transaction()
            sql_repo.commit_transaction()
        except Exception:
            try:
                graph_repo.rollback_transaction()
            except Exception as e:
                current_app.logger.warning('[GraphMgmt] rollback failed: %s', str(e))
            try:
                sql_repo.rollback_transaction()
            except Exception as e:
                current_app.logger.warning('[GraphMgmt] rollback failed: %s', str(e))
            raise

        record_log('删除图谱', '图谱管理',
                   f'删除图谱 "{label}"，共 {node_count} 个节点')
        return jsonify({
            'code': 200, 'success': True,
            'data': {'deleted_nodes': node_count},
            'message': f'图谱 "{label}" 已删除，共移除 {node_count} 个节点'
        })
    except Exception as e:
        return jsonify({'code': 500, 'success': False, 'message': str(e)}), 500


# ════════════════════════════════════════════════
#  数据导入（保留原有端点）
# ════════════════════════════════════════════════

@gm_bp.route('/import/json', methods=['POST'])
@require_admin
def import_json():
    body = request.get_json(force=True) or {}
    label = body.pop('label', 'KnowledgePoint')
    source = body.pop('source', '用户导入')
    result = import_service.import_json(body, label=label, source=source)
    record_log('导入JSON', '图谱管理',
               f'导入 {result["nodes_created"]} 节点, {result["relationships_created"]} 关系, label={label}')
    return jsonify({'code': 200, 'success': True, 'data': result,
                    'message': f'导入: {result["nodes_created"]}节点, {result["relationships_created"]}关系'})


@gm_bp.route('/import/csv', methods=['POST'])
@require_admin
def import_csv():
    data = request.get_json(force=True) or {}
    content = data.get('content', '')
    result = import_service.import_csv(content)
    record_log('导入CSV', '图谱管理',
               f'导入 {result["nodes_created"]} 节点, {result["relationships_created"]} 关系')
    return jsonify({'code': 200, 'success': True, 'data': result,
                    'message': f'导入: {result["nodes_created"]}节点, {result["relationships_created"]}关系'})


@gm_bp.route('/import/file', methods=['POST'])
@require_admin
def import_file():
    if 'file' not in request.files:
        return jsonify({'code': 400, 'success': False, 'message': '请选择文件'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'code': 400, 'success': False, 'message': '请选择文件'}), 400

    filename = file.filename.lower()
    label = request.form.get('label', 'KnowledgePoint')
    source = request.form.get('source', '用户导入')

    try:
        content = file.read().decode('utf-8-sig')
        if filename.endswith('.json'):
            import json as _json
            data = _json.loads(content)
            if isinstance(data, list):
                data = {'nodes': data, 'relationships': []}
            result = import_service.import_json(data, label=label, source=source)
        elif filename.endswith('.csv'):
            result = import_service.import_csv(content)
        else:
            return jsonify({'code': 400, 'success': False, 'message': '不支持的文件格式，请上传 JSON 或 CSV 文件'}), 400

        record_log('文件导入', '图谱管理',
                   f'导入 {result["nodes_created"]} 节点, {result["relationships_created"]} 关系, 文件: {filename}')
        return jsonify({'code': 200, 'success': True, 'data': result,
                        'message': f'导入: {result["nodes_created"]}节点, {result["relationships_created"]}关系'})
    except Exception as e:
        return jsonify({'code': 400, 'success': False, 'message': f'导入失败: {str(e)}'}), 400


# ════════════════════════════════════════════════
#  数据导出（保留原有端点）
# ════════════════════════════════════════════════

@gm_bp.route('/export/json', methods=['GET'])
@require_auth
def export_json():
    data = export_service.export_json()
    record_log('导出JSON', '图谱管理', f'导出 {len(data.get("nodes", []))} 节点')
    return jsonify({'code': 200, 'success': True, 'data': data, 'message': '导出成功'})


@gm_bp.route('/export/csv', methods=['GET'])
@require_auth
def export_csv():
    csv_data = export_service.export_csv()
    record_log('导出CSV', '图谱管理', '导出 CSV 文件')
    return Response(csv_data, mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=kekg_export.csv'})
