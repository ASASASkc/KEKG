# -*- coding: utf-8 -*-
"""
数据导入导出服务
支持 JSON / CSV 格式批量导入导出知识图谱数据
"""
import json
import csv
import io
from ..repositories.graph_repo import graph_repo


class ImportService:

    @staticmethod
    def import_json(data, label='KnowledgePoint', source='用户导入'):
        """
        JSON 格式导入
        data: { "nodes": [...], "relationships": [...] }
        label: 节点标签，默认 KnowledgePoint
        
        关系解析逻辑：
        1. 若 source/target 是旧版数字 ID → 用 id_mapping 查找
        2. 若 source/target 是节点名称 → 用 node_map 查找
        3. 回退到图数据库属性查询
        """
        if isinstance(data, list):
            nodes_data = data
            rels_data = []
        elif isinstance(data, dict):
            nodes_data = data.get('nodes', [])
            rels_data = data.get('relationships', [])
        else:
            raise ValueError('JSON 格式错误')

        node_map = {}       # name → Neo4j elementId
        id_mapping = {}     # old_id (如 "1", "2") → Neo4j elementId
        created_nodes = skipped_nodes = 0
        created_rels = skipped_rels = 0

        for item in nodes_data:
            name = item.get('name', '').strip()
            if not name:
                skipped_nodes += 1
                continue
            existing = graph_repo.get_node_by_property(label, 'name', name)
            if existing:
                nid = existing['id']
                node_map[name] = nid
                if 'id' in item:
                    id_mapping[str(item['id'])] = nid
                skipped_nodes += 1
                continue

            node = graph_repo.create_node(label, {
                'name': name,
                'category': item.get('category', '未分类'),
                'knowledge_level': item.get('knowledge_level', item.get('category', '未分类')),
                'difficulty_level': int(item.get('difficulty_level', item.get('difficulty', 1))),
                'description': item.get('description', ''),
                'source': item.get('source', source),
                'textbook_level': item.get('textbook_level'),
                'textbook_path': item.get('textbook_path'),
                'is_leaf': item.get('is_leaf'),
                'children_count': item.get('children_count'),
            })
            if node:
                nid = node['id']
                node_map[name] = nid
                if 'id' in item:
                    id_mapping[str(item['id'])] = nid
                created_nodes += 1

        for item in rels_data:
            src = item.get('source', '')
            tgt = item.get('target', '')
            rtype = item.get('type', 'RELATED_TO')
            # 按优先级解析: old_id → name → DB 查询
            src_id = (id_mapping.get(str(src)) or
                      node_map.get(src) or
                      ImportService._resolve_node(src, node_map, label))
            tgt_id = (id_mapping.get(str(tgt)) or
                      node_map.get(tgt) or
                      ImportService._resolve_node(tgt, node_map, label))
            if not src_id or not tgt_id:
                skipped_rels += 1
                continue
            rel = graph_repo.create_relationship(src_id, tgt_id, rtype, {
                'description': item.get('description', '')
            })
            if rel:
                created_rels += 1
            else:
                skipped_rels += 1

        return {
            'nodes_created': created_nodes,
            'nodes_skipped': skipped_nodes,
            'relationships_created': created_rels,
            'relationships_skipped': skipped_rels,
            'total_nodes': len(graph_repo.get_all_nodes()),
            'total_relationships': len(graph_repo.get_all_relationships())
        }

    @staticmethod
    def import_csv(content):
        reader = csv.DictReader(io.StringIO(content))
        nodes_data, rels_data = [], []
        for row in reader:
            rt = (row.get('type') or '').strip().lower()
            if rt in ('node', '节点', ''):
                nodes_data.append({
                    'name': row.get('name', ''),
                    'category': row.get('category', '未分类'),
                    'difficulty': row.get('difficulty', 1),
                    'description': row.get('description', ''),
                })
            elif rt in ('rel', 'relation', '关系'):
                rels_data.append({
                    'source': row.get('source') or row.get('source_id', ''),
                    'target': row.get('target') or row.get('target_id', ''),
                    'type': row.get('relationship_type', 'RELATED_TO'),
                    'description': row.get('description', ''),
                })
        return ImportService.import_json({'nodes': nodes_data, 'relationships': rels_data})

    @staticmethod
    def _resolve_node(name, node_map, label):
        if name in node_map:
            return node_map[name]
        node = graph_repo.get_node_by_property(label, 'name', name)
        if node:
            node_map[name] = node['id']
            return node['id']
        for n in graph_repo.get_all_nodes(label):
            if n['id'] == str(name):
                node_map[name] = n['id']
                return n['id']
        return None


class ExportService:

    @staticmethod
    def export_json():
        nodes = graph_repo.get_all_nodes()
        relationships = graph_repo.get_all_relationships()
        result = {
            'meta': {'total_nodes': len(nodes), 'total_relationships': len(relationships), 'version': '1.0'},
            'nodes': [],
            'relationships': []
        }
        ni = {}
        for i, n in enumerate(nodes):
            ni[n['id']] = i
            result['nodes'].append({
                'id': n['id'],
                'name': n['properties'].get('name', ''),
                'category': n['properties'].get('category', ''),
                'difficulty': n['properties'].get('difficulty_level', 1),
                'description': n['properties'].get('description', ''),
                'source': n['properties'].get('source', ''),
            })
        for r in relationships:
            re = {
                'id': r['id'], 'type': r['type'],
                'source': r['start_node'], 'target': r['end_node'],
                'description': r.get('properties', {}).get('description', ''),
            }
            si = ni.get(r['start_node'])
            ti = ni.get(r['end_node'])
            if si is not None: re['source_name'] = result['nodes'][si]['name']
            if ti is not None: re['target_name'] = result['nodes'][ti]['name']
            result['relationships'].append(re)
        return result

    @staticmethod
    def export_csv():
        nodes = graph_repo.get_all_nodes()
        relationships = graph_repo.get_all_relationships()
        out = io.StringIO()
        w = csv.writer(out, lineterminator='\n')
        w.writerow(['type', 'id', 'name', 'category', 'difficulty', 'description', 'source'])
        for n in nodes:
            w.writerow(['node', n['id'], n['properties'].get('name', ''), n['properties'].get('category', ''),
                        n['properties'].get('difficulty_level', 1), n['properties'].get('description', ''),
                        n['properties'].get('source', '')])
        w.writerow(['type', 'source', 'target', 'relationship_type', 'description'])
        for r in relationships:
            w.writerow(['rel', r['start_node'], r['end_node'], r['type'],
                        r.get('properties', {}).get('description', '')])
        return out.getvalue()


import_service = ImportService()
export_service = ExportService()
