# -*- coding: utf-8 -*-
"""
赛道服务 — 赛道 JSON 导入 + 赛道子图查询
"""
import json
import os
from ..repositories.graph_repo import graph_repo
from ..repositories.sql_repo import sql_repo

TRACK_NAMES = {
    'python公共部分': '公共基础',
    'graph_data_analysis': '数据分析及可视化',
    'graph_ml': '机器学习',
    'graph_dl': '深度学习',
    'graph_llm': '大模型',
    'graph_nlp': '自然语言处理',
    'graph_crawler': '网络爬虫',
    'graph_devops': '自动化运维',
}


class TrackService:

    # ── 导入 ─────────────────────────────────────────

    @staticmethod
    def import_track_json(filepath: str) -> dict:
        """导入单个赛道 JSON（双事务保护）"""
        # SKIP_SQL_META=1：只写 Neo4j，不写 MySQL 镜像表，避免双写导致统计翻倍
        skip_sql_meta = os.getenv('SKIP_SQL_META', '0') == '1'
        if not os.path.exists(filepath):
            raise FileNotFoundError(f'文件不存在: {filepath}')

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        filename = os.path.basename(filepath).replace('.json', '')
        track_name = TRACK_NAMES.get(filename, filename)

        nodes_data = data.get('nodes', []) if isinstance(data, dict) else data
        rels_data = data.get('relationships', []) if isinstance(data, dict) else []

        sql_repo.begin_transaction()
        graph_repo.begin_transaction()
        try:
            node_map = {}      # name → Neo4j id
            id_map = {}        # original id → Neo4j id
            nodes_created = 0
            rels_created = 0

            # 1. 创建 Track 节点
            if track_name:
                track_nodes = graph_repo.get_all_nodes('Track')
                existing = [n for n in track_nodes if n['properties'].get('name') == track_name]
                if not existing:
                    graph_repo.create_node('Track', {
                        'name': track_name,
                        'track_id': filename,
                    })

            # 2. 创建知识点节点
            for item in nodes_data:
                # 检查是否已存在（按 name）
                existing = graph_repo.get_node_by_property('KnowledgePoint', 'name', item['name'])
                if existing:
                    node_map[item['name']] = existing['id']
                    if item.get('id'):
                        id_map[item['id']] = existing['id']
                    continue

                props = {
                    'name': item['name'],
                    'category': item.get('category', ''),
                    'difficulty_level': item.get('tier', item.get('difficulty', 1)),
                    'description': item.get('description', ''),
                    'syntax': item.get('syntax', ''),
                    'examples': json.dumps(item.get('examples', []), ensure_ascii=False),
                    'mooc_links': json.dumps(item.get('mooc_links', []), ensure_ascii=False),
                    'tracks': json.dumps(item.get('tracks', []) or [track_name], ensure_ascii=False),
                }

                node = graph_repo.create_node('KnowledgePoint', props)
                node_map[item['name']] = node['id']
                if item.get('id'):
                    id_map[item['id']] = node['id']
                nodes_created += 1

                if not skip_sql_meta:
                    sql_repo.execute_insert(
                        """INSERT INTO knowledge_points_meta
                           (graph_node_id, name, category, knowledge_level,
                            difficulty_level, description, source, course_id, code_example)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (node['id'], item['name'], item.get('category', ''),
                         item.get('category', ''), item.get('tier', item.get('difficulty', 1)),
                         item.get('description', ''), track_name, '', '')
                    )

            # 3. 创建 BELONGS_TO_TRACK 关系（缓存 Track 节点避免重复查询）
            cached_track_nodes = graph_repo.get_all_nodes('Track')
            for item in nodes_data:
                nid = node_map.get(item['name'])
                if not nid:
                    continue
                effective_tracks = item.get('tracks', []) or [track_name]
                for tname in effective_tracks:
                    t_node = next((n for n in cached_track_nodes if n['properties'].get('name') == tname), None)
                    if t_node:
                        graph_repo.create_relationship(
                            nid, t_node['id'], 'BELONGS_TO_TRACK',
                            {'description': f'属于{tname}赛道'}
                        )

            # 4. 创建关系
            for rel in rels_data:
                # 支持 source/target (ID 或 name) + source_name/target_name 回退
                sid = (id_map.get(str(rel.get('source') or '')) or
                       id_map.get(str(rel.get('from') or '')) or
                       node_map.get(rel.get('source_name') or '') or
                       node_map.get(rel.get('from') or '') or
                       node_map.get(rel.get('source') or ''))
                tid = (id_map.get(str(rel.get('target') or '')) or
                       id_map.get(str(rel.get('to') or '')) or
                       node_map.get(rel.get('target_name') or '') or
                       node_map.get(rel.get('to') or '') or
                       node_map.get(rel.get('target') or ''))
                rtype = rel.get('type', 'PRECEDES')
                if sid and tid:
                    r = graph_repo.create_relationship(sid, tid, rtype,
                                                       {'description': rel.get('description', '')})
                    if r:
                        rels_created += 1
                        if not skip_sql_meta:
                            sql_repo.execute_insert(
                                "INSERT INTO relationship_meta (graph_rel_id, source_node_id, target_node_id, type, description) VALUES (?, ?, ?, ?, ?)",
                                (r['id'], sid, tid, rtype, rel.get('description', ''))
                            )

            # 5. 根据 prerequisites 自动创建 PRECEDES 关系
            for item in nodes_data:
                prereqs = item.get('prerequisites', [])
                nid = node_map.get(item['name'])
                if not nid or not prereqs:
                    continue
                for pre_name in prereqs:
                    pre_id = node_map.get(pre_name)
                    if pre_id and pre_id != nid:
                        graph_repo.create_relationship(
                            pre_id, nid, 'PRECEDES',
                            {'description': f'{pre_name} 是 {item["name"]} 的前置知识'}
                        )
                        rels_created += 1

            graph_repo.commit_transaction()
            sql_repo.commit_transaction()

        except Exception:
            try:
                graph_repo.rollback_transaction()
            except Exception:
                pass
            try:
                sql_repo.rollback_transaction()
            except Exception:
                pass
            raise

        return {
            'track': track_name,
            'nodes_created': nodes_created,
            'relationships_created': rels_created,
        }

    @staticmethod
    def import_all_tracks(data_dir: str) -> dict:
        """从目录批量导入所有赛道 JSON 文件"""
        results = {}
        for fname in sorted(os.listdir(data_dir)):
            if (fname.startswith('graph_') or fname == 'python公共部分.json') and fname.endswith('.json'):
                filepath = os.path.join(data_dir, fname)
                try:
                    r = TrackService.import_track_json(filepath)
                    results[fname] = r
                except Exception as e:
                    results[fname] = {'error': str(e)}
        return results

    # ── 查询 ─────────────────────────────────────────

    @staticmethod
    def list_tracks() -> list:
        """列出所有赛道（从 Neo4j Track 节点 + BELONGS_TO_TRACK 关系统计）"""
        with graph_repo._session() as session:
            result = session.run(
                "MATCH (t:Track) "
                "OPTIONAL MATCH (kp:KnowledgePoint)-[:BELONGS_TO_TRACK]->(t) "
                "RETURN t.name as name, t.track_id as track_id, count(kp) as node_count "
                "ORDER BY node_count DESC"
            )
            tracks = []
            for record in result:
                tracks.append({
                    'name': record['name'] or '',
                    'id': record['track_id'] or '',
                    'node_count': record['node_count'],
                })
            return tracks

    @staticmethod
    def get_track_graph(track_name: str) -> dict:
        """获取赛道子图：使用 Neo4j 直接查询，按 tracks 属性过滤"""
        with graph_repo._session() as session:
            # tracks 存储为 JSON 字符串如 '["公共基础", "网络爬虫"]'，
            # 使用 CONTAINS 精确匹配（带引号避免子串误匹配）
            result = session.run(
                "MATCH (kp:KnowledgePoint) "
                "WHERE kp.tracks CONTAINS $track_pattern "
                "RETURN kp, elementId(kp) as nid",
                track_pattern='"' + track_name + '"'
            )

            nodes = []
            for record in result:
                kp = record['kp']
                nodes.append({
                    'id': record['nid'],
                    'labels': list(kp.labels),
                    'properties': dict(kp.items()),
                })

            if not nodes:
                return {'nodes': [], 'relationships': []}

            selected_ids = [n['id'] for n in nodes]

            # 查询选中节点之间的关系
            rel_result = session.run(
                "MATCH (a)-[r]->(b) "
                "WHERE elementId(a) IN $nids AND elementId(b) IN $nids "
                "RETURN r, elementId(startNode(r)) as sid, elementId(endNode(r)) as eid",
                nids=selected_ids
            )

            rels = []
            seen = set()
            for record in rel_result:
                rid = record['r'].element_id
                if rid not in seen:
                    seen.add(rid)
                    rels.append({
                        'id': rid,
                        'type': record['r'].type,
                        'start_node': record['sid'],
                        'end_node': record['eid'],
                        'properties': dict(record['r'].items()),
                    })

            return {'nodes': nodes, 'relationships': rels}


track_service = TrackService()
