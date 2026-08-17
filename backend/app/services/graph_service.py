# -*- coding: utf-8 -*-
"""
图谱查询服务
"""
from ..repositories.graph_repo import graph_repo


class GraphService:
    """图谱查询与统计服务"""

    @staticmethod
    def get_full_graph(label=None):
        nodes = graph_repo.get_all_nodes(label)
        if not label:
            return {'nodes': nodes, 'relationships': graph_repo.get_all_relationships()}
        # filter relationships to only those connecting nodes of this label
        node_ids = {n['id'] for n in nodes}
        all_rels = graph_repo.get_all_relationships()
        filtered_rels = [r for r in all_rels if r['start_node'] in node_ids and r['end_node'] in node_ids]
        return {'nodes': nodes, 'relationships': filtered_rels}

    @staticmethod
    def get_subgraph(center_id, depth=1):
        return graph_repo.get_subgraph(center_id, depth)

    @staticmethod
    def find_paths(start_id, end_id, max_depth=5):
        return graph_repo.find_paths(start_id, end_id, max_depth)

    @staticmethod
    def get_neighbors(node_id, depth=1, direction='both', rel_type=None, limit=100):
        result = graph_repo.get_neighbors(node_id, rel_type=rel_type,
                                        direction=direction, depth=depth)
        if limit and len(result.get('nodes', [])) > limit:
            result['nodes'] = result['nodes'][:limit]
        return result

    @staticmethod
    def get_children(node_id):
        """获取节点的直接子节点（CONTAINS 关系，outgoing 方向）"""
        neighbors = graph_repo.get_neighbors(node_id, direction='outgoing', rel_type='CONTAINS', depth=1)
        child_ids = {n['id'] for n in neighbors.get('nodes', [])}
        rels = [r for r in neighbors.get('relationships', [])
                if r['start_node'] == str(node_id) and r['end_node'] in child_ids]
        return {'nodes': neighbors.get('nodes', []), 'relationships': rels}

    @staticmethod
    def get_tree(label=None):
        """重建树形结构
        1. 优先按 CONTAINS 关系构建（支持所有有层级关系的图谱）
        2. 回退按 textbook_path 属性构建（教材知识图谱）
        """
        nodes = graph_repo.get_all_nodes(label)
        all_rels = graph_repo.get_all_relationships()
        contains_rels = [r for r in all_rels if r.get('type') == 'CONTAINS']

        # 若指定了 label 且有 textbook_path 节点 → 优先用 textbook_path
        if label:
            tree_nodes = [n for n in nodes if n.get('properties', {}).get('textbook_path')]
            if tree_nodes:
                return GraphService._build_textbook_tree(tree_nodes)

        # 回退：按 CONTAINS 关系构建树
        if contains_rels and nodes:
            result = GraphService._build_contains_tree(nodes, contains_rels)
            if result['children']:
                return result

        # 最终回退：textbook_path
        tree_nodes = [n for n in nodes if n.get('properties', {}).get('textbook_path')]
        if tree_nodes:
            return GraphService._build_textbook_tree(tree_nodes)

        return {'name': '全部', 'children': [], '_count': 0}

    @staticmethod
    def _build_textbook_tree(tree_nodes):
        """按 textbook_path 构建树"""
        tree_nodes.sort(key=lambda n: n['properties']['textbook_path'].count(' > '))
        root = {'name': '全部', 'children': [], '_count': 0}
        path_map = {}
        for n in tree_nodes:
            path = n['properties']['textbook_path']
            parts = [p.strip() for p in path.split(' > ')]
            parent = root
            for i, part in enumerate(parts):
                key = ' > '.join(parts[:i+1])
                if key not in path_map:
                    is_last = (i == len(parts) - 1)
                    new_node = {
                        'name': part,
                        'children': [],
                        '_count': 0,
                        '_id': n['id'] if is_last else None,
                        '_category': n['properties'].get('category', '') if is_last else '',
                        '_level': n['properties'].get('textbook_level') if is_last else None
                    }
                    path_map[key] = new_node
                    parent['children'].append(new_node)
                parent = path_map[key]
                parent['_count'] += 1
        return root

    @staticmethod
    def _build_contains_tree(nodes, contains_rels):
        """按 CONTAINS 关系构建树"""
        node_map = {n['id']: n for n in nodes}
        node_ids = set(node_map.keys())

        # 找出参与 CONTAINS 关系的节点
        con_nodes = set()
        for r in contains_rels:
            con_nodes.add(r['start_node'])
            con_nodes.add(r['end_node'])
        con_nodes &= node_ids  # 仅保留在当前节点中的

        # 分离：参与 CONTAINS 的节点 vs 独立节点
        tree_node_ids = {nid for nid in node_ids if nid in con_nodes}
        standalone_ids = node_ids - tree_node_ids

        # 找出根节点（不在 CONTAINS 的 target 中出现的节点）
        target_ids = {r['end_node'] for r in contains_rels if r['end_node'] in node_ids}
        root_ids = {nid for nid in tree_node_ids if nid not in target_ids}

        # 如果没有明显的根节点，把入度最小的作为根
        if not root_ids and tree_node_ids:
            indegree = {}
            for r in contains_rels:
                if r['end_node'] in node_ids:
                    indegree[r['end_node']] = indegree.get(r['end_node'], 0) + 1
            source_ids = {r['start_node'] for r in contains_rels if r['start_node'] in node_ids}
            min_indeg = float('inf')
            for sid in source_ids:
                d = indegree.get(sid, 0)
                if d < min_indeg:
                    min_indeg = d
                    root_ids = {sid}
                elif d == min_indeg:
                    root_ids.add(sid)

        # 构建父子映射
        children_map = {}
        for r in contains_rels:
            sid, eid = r['start_node'], r['end_node']
            if sid in node_ids and eid in node_ids:
                children_map.setdefault(sid, []).append(eid)

        def build_subtree(nid, visited):
            if nid in visited:
                return None  # 防止循环引用
            visited.add(nid)
            n = node_map[nid]
            props = n.get('properties', {})
            node = {
                'name': props.get('name', str(nid)[:12]),
                'children': [],
                '_count': 1,
                '_id': nid,
                '_category': props.get('category', props.get('knowledge_level', '')),
            }
            for child_id in children_map.get(nid, []):
                if child_id in node_map and child_id != nid:
                    child_node = build_subtree(child_id, visited)
                    if child_node:
                        node['children'].append(child_node)
                        node['_count'] += child_node['_count']
            return node

        root = {'name': '全部', 'children': [], '_count': 0}
        built = set()
        for rid in root_ids:
            if rid in node_map:
                subtree = build_subtree(rid, set())
                if subtree:
                    root['children'].append(subtree)
                    root['_count'] += subtree['_count']
                built.add(rid)

        # 独立节点按 label 分组
        if standalone_ids:
            grouped = {}
            for sid in standalone_ids:
                n = node_map[sid]
                props = n.get('properties', {})
                labels = n.get('labels', [])
                group_name = '未分类'
                for lb in labels:
                    if lb not in ('Category',):
                        group_name = lb
                        break
                cat = props.get('category', props.get('knowledge_level', ''))
                if group_name not in grouped:
                    grouped[group_name] = {
                        'name': group_name,
                        'children': [],
                        '_count': 0,
                        '_id': None,
                        '_category': '',
                    }
                grouped[group_name]['children'].append({
                    'name': props.get('name', str(sid)[:12]),
                    'children': [],
                    '_count': 1,
                    '_id': sid,
                    '_category': cat,
                })
                grouped[group_name]['_count'] += 1
            for g in grouped.values():
                root['children'].append(g)
                root['_count'] += g['_count']

        # 补上孤立节点
        for nid in node_ids:
            if nid not in built and nid not in target_ids:
                n = node_map[nid]
                props = n.get('properties', {})
                root['children'].append({
                    'name': props.get('name', str(nid)[:12]),
                    'children': [],
                    '_count': 1,
                    '_id': nid,
                    '_category': props.get('category', ''),
                })
                root['_count'] += 1

        return root

    @staticmethod
    def get_statistics():
        stats = graph_repo.get_statistics()
        
        # 计算中心度: 统计每个节点的出度和入度
        indegree = {}
        outdegree = {}
        all_nodes = graph_repo.get_all_nodes()
        
        # 初始化所有节点度数为0
        for n in all_nodes:
            node_id = str(n['id'])
            indegree[node_id] = 0
            outdegree[node_id] = 0
        
        # 建立 node_id -> node info 映射
        node_info = {}
        for n in all_nodes:
            node_id = str(n['id'])
            props = n.get('properties', {})
            node_info[node_id] = {
                'name': n.get('name', props.get('name', '')),
                'category': props.get('category', ''),
                'label': n.get('labels', [''])[0] if n.get('labels') else ''
            }
        
        # 统计度数
        rels = graph_repo.get_all_relationships()
        for r in rels:
            start = str(r['start_node'])
            end = str(r['end_node'])
            if start in outdegree:
                outdegree[start] += 1
            if end in indegree:
                indegree[end] += 1
        
        # 计算总度数并排序，取前20
        centrality_list = []
        for node_id in indegree:
            total = indegree[node_id] + outdegree[node_id]
            if total > 0:
                info = node_info.get(node_id, {})
                centrality_list.append({
                    'id': node_id,
                    'name': info.get('name', node_id),
                    'category': info.get('category', ''),
                    'indegree': indegree[node_id],
                    'outdegree': outdegree[node_id],
                    'total_degree': total
                })
        
        centrality_list.sort(key=lambda x: x['total_degree'], reverse=True)
        stats['centrality'] = centrality_list[:20]
        
        return stats

    @staticmethod
    def _natural_sort_key(name):
        """自然排序键：提取"第N章"中的数字，没有则按原名字排序"""
        import re
        # 匹配 "第N章" 模式
        m = re.match(r'第(\d+)章', name)
        if m:
            return (0, int(m.group(1)), name)
        # 匹配 "N." 或 "N.N" 数字开头
        m2 = re.match(r'(\d+(?:\.\d+)*)', name)
        if m2:
            parts = [int(x) for x in m2.group(1).split('.')]
            return (0, *parts, name)
        # 其他放后面
        return (1, 0, name)

    @staticmethod
    def build_full_tree():
        """
        构建 5 级完整知识树：
          L1: "Python" 固定根
          L2: "公共基础" + 各拓展名（从 KnowledgePoint.tracks 属性汇总）
          L3: 章级 — CONTAINS 关系中的根节点（source 且非 target）
          L4: 节级 — CONTAINS 中间层节点
          L5: 具体知识点叶子节点
        孤立节点（不在任何 CONTAINS 中）按 tracks 属性分组挂到对应子图的"未分类"节点。
        返回 JSON 树形结构：{name: "Python", children: [{name: "公共基础", children: [...]}]}
        """
        import json as _json
        import re as _re

        with graph_repo._session() as session:
            # ── 1. 获取所有 KnowledgePoint 节点 ──
            kp_result = session.run(
                "MATCH (kp:KnowledgePoint) "
                "RETURN elementId(kp) as nid, kp"
            )
            all_nodes = {}  # nid -> node info
            for record in kp_result:
                nid = record['nid']
                kp = record['kp']
                props = dict(kp.items())
                tracks_raw = props.get('tracks', '[]')
                try:
                    tracks = _json.loads(tracks_raw) if isinstance(tracks_raw, str) else tracks_raw
                except Exception:
                    tracks = []
                all_nodes[nid] = {
                    'id': nid,
                    'name': props.get('name', ''),
                    'category': props.get('category', ''),
                    'tracks': tracks if isinstance(tracks, list) else [tracks],
                }

            if not all_nodes:
                return {'name': 'Python', 'children': []}

            # ── 2. 获取所有 CONTAINS 关系 ──
            contains_result = session.run(
                "MATCH (a:KnowledgePoint)-[r:CONTAINS]->(b:KnowledgePoint) "
                "RETURN elementId(a) as pid, elementId(b) as cid"
            )
            contains_pairs = [(r['pid'], r['cid']) for r in contains_result]

            # ── 3. 按 tracks 汇总轨道名称 (去重，保持稳定顺序) ──
            all_track_names_set = set()
            for node in all_nodes.values():
                for t in node['tracks']:
                    t = t.strip()
                    if t:
                        all_track_names_set.add(t)

            # 确保"公共基础"排第一位
            ordered_tracks = []
            if '公共基础' in all_track_names_set:
                ordered_tracks.append('公共基础')
                all_track_names_set.remove('公共基础')
            ordered_tracks.extend(sorted(all_track_names_set))

            # ── 4. 按 track 分组节点 ID ──
            track_node_ids = {tn: set() for tn in ordered_tracks}
            trackless_node_ids = set()   # 无 tracks 属性的节点
            for nid, node in all_nodes.items():
                found = False
                for t in node['tracks']:
                    t = t.strip()
                    if t in track_node_ids:
                        track_node_ids[t].add(nid)
                        found = True
                if not found:
                    trackless_node_ids.add(nid)

            # ── 4.5. 将 trackless 节点按 CONTAINS 关系归入已有 track ──
            still_trackless = set()
            for nid in trackless_node_ids:
                assigned = False
                for p, c in contains_pairs:
                    if nid == p or nid == c:
                        other = c if nid == p else p
                        for tn, tnids in track_node_ids.items():
                            if other in tnids:
                                track_node_ids[tn].add(nid)
                                assigned = True
                                break
                    if assigned:
                        break
                if not assigned:
                    still_trackless.add(nid)
            trackless_node_ids = still_trackless

            # ── 5. 为每个 track 构建子树 ──
            root = {'name': 'Python', 'children': []}

            for track_name in ordered_tracks:
                tnode_ids = track_node_ids[track_name]
                if not tnode_ids:
                    continue

                # 过滤该 track 内的 CONTAINS 关系
                track_contains = [(p, c) for p, c in contains_pairs
                                  if p in tnode_ids and c in tnode_ids]

                # 构建父子映射
                children_map = {}   # parent -> [child_ids]
                con_parents = set()
                con_children = set()
                for p, c in track_contains:
                    children_map.setdefault(p, []).append(c)
                    con_parents.add(p)
                    con_children.add(c)

                # CONTAINS 关系中的根节点：是 source 但不是 target
                root_ids = con_parents - con_children

                # 孤立节点：在 track 中但不在任何 CONTAINS 关系中
                isolated_ids = tnode_ids - con_parents - con_children

                track_subtree = {'name': track_name, 'children': []}

                # 递归构建子树
                visited = set()

                def _build_recursive(nid):
                    if nid in visited:
                        return None
                    visited.add(nid)
                    node = all_nodes.get(nid)
                    if not node:
                        return None
                    child = {
                        'name': node['name'],
                        'children': [],
                        '_id': nid,
                        '_category': node.get('category', ''),
                    }
                    # 子节点按自然排序
                    sorted_children = sorted(children_map.get(nid, []),
                                             key=lambda cid: GraphService._natural_sort_key(
                                                 all_nodes.get(cid, {}).get('name', '')))
                    for cid in sorted_children:
                        sub = _build_recursive(cid)
                        if sub:
                            child['children'].append(sub)
                    return child

                # 根节点按自然排序
                sorted_roots = sorted(root_ids,
                                     key=lambda rid: GraphService._natural_sort_key(
                                         all_nodes.get(rid, {}).get('name', '')))
                for rid in sorted_roots:
                    subtree = _build_recursive(rid)
                    if subtree:
                        track_subtree['children'].append(subtree)

                # 孤立节点 → "未分类"（也按自然排序）
                if isolated_ids:
                    uncat = {'name': '未分类', 'children': []}
                    sorted_isolated = sorted(isolated_ids,
                                             key=lambda nid: GraphService._natural_sort_key(
                                                 all_nodes.get(nid, {}).get('name', '')))
                    for nid in sorted_isolated:
                        node = all_nodes.get(nid)
                        if node:
                            uncat['children'].append({
                                'name': node['name'],
                                'children': [],
                                '_id': nid,
                                '_category': node.get('category', ''),
                            })
                    track_subtree['children'].append(uncat)

                root['children'].append(track_subtree)

            # ── 6. 无 tracks 属性的节点 → "未归类" ──
            if trackless_node_ids:
                uncat_track = {'name': '未归类', 'children': []}
                sorted_trackless = sorted(trackless_node_ids,
                                          key=lambda nid: GraphService._natural_sort_key(
                                              all_nodes.get(nid, {}).get('name', '')))
                for nid in sorted_trackless:
                    node = all_nodes.get(nid)
                    if node:
                        uncat_track['children'].append({
                            'name': node['name'],
                            'children': [],
                            '_id': nid,
                            '_category': node.get('category', ''),
                        })
                root['children'].append(uncat_track)

            return root


graph_service = GraphService()
