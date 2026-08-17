# -*- coding: utf-8 -*-
"""个性化学习路径规划服务"""
from decimal import Decimal
from ..repositories.sql_repo import sql_repo
from ..repositories.graph_repo import graph_repo


_total = lambda rows: [dict(r) for r in (rows or [])]
_first = lambda rows: dict(rows[0]) if rows else None


class LearningPathService:

    @staticmethod
    def get_assessment(student_id):
        """评估学生水平：均分 60% + 末考成绩 40%，分析薄弱知识点"""

        # ── 所有已提交考试 ──
        exams = _total(sql_repo.execute_query(
            """SELECT es.exam_id, es.total_score as score, ep.total_score as max_score, ep.title
               FROM exam_submissions es
               JOIN exam_papers ep ON es.exam_id = ep.id
               WHERE es.student_id = ? AND es.status IN ('submitted', 'reviewed')
               ORDER BY ep.start_time ASC""",
            (student_id,)))

        if not exams:
            return {
                'composite_score': 0, 'avg_score': 0, 'last_exam': None,
                'level': '暂无数据', 'level_index': 0,
                'weak_points': [], 'exam_count': 0
            }

        # 按试卷满分归一化到百分制
        scores = []
        for e in exams:
            ratio = 100.0 / e['max_score'] if e['max_score'] else 1
            scores.append(round(float(e['score'] or 0) * ratio, 1))

        avg_score = round(sum(scores) / len(scores), 1)
        last_score = scores[-1]
        composite = round(avg_score * 0.6 + last_score * 0.4, 1)

        if composite >= 90:
            level, level_idx = '优秀', 4
        elif composite >= 75:
            level, level_idx = '良好', 3
        elif composite >= 60:
            level, level_idx = '合格', 2
        else:
            level, level_idx = '薄弱', 1

        # ── 薄弱知识点：所有错题关联 ──
        weak = _total(sql_repo.execute_query(
            """SELECT DISTINCT qb.knowledge_point_id, qb.knowledge_point_name,
                    COUNT(*) as wrong_count
               FROM exam_answers ea
               JOIN question_bank qb ON ea.question_id = qb.id
               WHERE ea.student_id = ? AND ea.is_correct = 0
                 AND qb.knowledge_point_id IS NOT NULL AND qb.knowledge_point_id != ''
               GROUP BY qb.knowledge_point_id, qb.knowledge_point_name
               ORDER BY wrong_count DESC""",
            (student_id,)))

        # 批量查 Neo4j 获取 category
        kp_ids = [w['knowledge_point_id'] for w in weak]
        node_map = graph_repo.get_nodes_by_ids(kp_ids) if kp_ids else {}

        weak_points = []
        for w in weak:
            nprop = node_map.get(w['knowledge_point_id'], {})
            weak_points.append({
                'knowledge_point_id': w['knowledge_point_id'],
                'name': w['knowledge_point_name'] or nprop.get('name', ''),
                'category': nprop.get('category', ''),
                'wrong_count': w['wrong_count']
            })

        return {
            'composite_score': composite,
            'avg_score': avg_score,
            'last_exam': {
                'title': exams[-1]['title'],
                'score': float(exams[-1]['score'] or 0),
                'max_score': float(exams[-1]['max_score'] or 0),
                'pct': last_score
            },
            'level': level,
            'level_index': level_idx,
            'weak_points': weak_points,
            'exam_count': len(exams),
            'history_scores': scores
        }

    @staticmethod
    def get_learning_path(student_id):
        """基于薄弱点规划学习路径：从已知知识点 → 薄弱点的前置依赖链"""

        # 获取薄弱点
        weak_ids = sql_repo.execute_query(
            """SELECT DISTINCT qb.knowledge_point_id
               FROM exam_answers ea
               JOIN question_bank qb ON ea.question_id = qb.id
               WHERE ea.student_id = ? AND ea.is_correct = 0
                 AND qb.knowledge_point_id IS NOT NULL AND qb.knowledge_point_id != ''""",
            (student_id,))
        weak_id_set = set((r['knowledge_point_id'] for r in weak_ids))

        # 获取已掌握知识点（答对的题）
        good_ids = sql_repo.execute_query(
            """SELECT DISTINCT qb.knowledge_point_id
               FROM exam_answers ea
               JOIN question_bank qb ON ea.question_id = qb.id
               WHERE ea.student_id = ? AND ea.is_correct = 1
                 AND qb.knowledge_point_id IS NOT NULL AND qb.knowledge_point_id != ''""",
            (student_id,))
        good_id_set = set((r['knowledge_point_id'] for r in good_ids))

        if not weak_id_set:
            return LearningPathService._get_entry_path()

        # 为每个薄弱点找最短前置路径（从已知点出发，沿 PREDECESSOR 反向追溯）
        path_results = []
        all_covered_ids = set()

        for wid in weak_id_set:
            best_path = None
            best_len = 999

            # 对每个已知点，尝试找路径（跳过与薄弱点相同的知识点，避免起点=终点）
            for gid in good_id_set:
                if gid == wid:
                    continue
                r = graph_repo.find_paths(gid, wid, max_depth=8)
                if r:
                    for p in r:
                        pnodes = p.get('nodes', [])
                        plen = len(pnodes)
                        if plen < best_len:
                            best_len = plen
                            best_path = pnodes

            if best_path:
                path_results.append({
                    'target_id': wid,
                    'path': best_path
                })
                for n in best_path:
                    all_covered_ids.add(n.get('id', ''))

        # 没有已知点的情况：对所有薄弱点，尝试两两之间找 PREDECESSOR 链
        if not path_results and len(weak_id_set) >= 2:
            weak_list = list(weak_id_set)
            # 找一条覆盖最多薄弱点的链：任取两点之间的最短路径
            for i in range(len(weak_list)):
                for j in range(i + 1, len(weak_list)):
                    r = graph_repo.find_paths(weak_list[i], weak_list[j], max_depth=8)
                    if r:
                        for p in r:
                            pnodes = p.get('nodes', [])
                            pid_set = set(n.get('id', '') for n in pnodes)
                            # 检查覆盖了多少薄弱点
                            covered = pid_set & weak_id_set
                            if len(covered) >= 2:
                                path_results.append({
                                    'target_id': weak_list[j],
                                    'path': pnodes
                                })
                                for n in pnodes:
                                    all_covered_ids.add(n.get('id', ''))
                                break

        # 如果还没有路径：没有已知点、薄弱点间也没关系，就返回单纯列表
        if not path_results:
            nodes = []
            for wid in weak_id_set:
                node = graph_repo.get_node_by_id(wid)
                if node:
                    nodes.append({
                        'id': wid, 'name': node.get('name', wid),
                        'category': node.get('category', '')
                    })
            return {
                'paths': [],
                'recommended_sequence': nodes,
                'message': '暂无知识点间前置关系，按错误次数推荐学习顺序'
            }

        # ── 构建推荐序列（同类聚合） ──
        seq = []
        seen = set()
        for pr in path_results:
            for n in pr['path']:
                nid = n.get('id', '')
                if nid not in seen:
                    seen.add(nid)
                    seq.append({
                        'id': nid,
                        'name': (n.get('properties', {}) or {}).get('name', nid),
                        'category': (n.get('properties', {}) or {}).get('category', ''),
                        'is_weak': nid in weak_id_set,
                        'is_known': nid in good_id_set
                    })

        seq.sort(key=lambda x: (x['category'] or 'zzz'))

        return {
            'paths': path_results,
            'recommended_sequence': seq,
            'message': f'共找到 {len(seq)} 个知识点，按分类和难度排列'
        }

    @staticmethod
    def _get_entry_path():
        """新学生兜底：推送入门级知识点 + 关联学习资源"""
        entry_points = graph_repo.get_entry_points()

        if not entry_points:
            return {'paths': [], 'recommended_sequence': [], 'message': '暂无可推荐的知识点'}

        # 批量查询关联的学习资源
        kp_ids = [n['id'] for n in entry_points if n.get('id')]
        resources = {}
        if kp_ids:
            placeholders = ','.join(['?' for _ in kp_ids])
            rows = sql_repo.execute_query(
                f"""SELECT id, title, type, knowledge_point_id, url, tags
                    FROM learning_resources
                    WHERE knowledge_point_id IN ({placeholders})
                    ORDER BY title ASC
                    LIMIT 100""",
                tuple(kp_ids))
            for r in (_total(rows)):
                kid = r['knowledge_point_id']
                if kid not in resources:
                    resources[kid] = []
                resources[kid].append(r)

        # 构建推荐序列
        seq = []
        for node in entry_points:
            nid = node.get('id', '')
            seq.append({
                'id': nid,
                'name': node.get('name', nid),
                'category': node.get('category', ''),
                'is_weak': False,
                'is_known': False,
                'is_entry': True,
                'resources': resources.get(nid, [])
            })

        return {'paths': [], 'recommended_sequence': seq, 'message': '入门级知识点推荐'}

    @staticmethod
    def get_track_recommendations(student_id):
        """基于答题记录的领域偏好分析，返回领域级学习路径和资源推荐"""
        from .resource_service import ResourceService

        # ── 1. 获取学生所有答题关联的知识点及 tracks ──
        answers = _total(sql_repo.execute_query(
            """SELECT ea.question_id, ea.is_correct, qb.knowledge_point_id, qb.knowledge_point_name
               FROM exam_answers ea
               JOIN question_bank qb ON ea.question_id = qb.id
               WHERE ea.student_id = ?
                 AND qb.knowledge_point_id IS NOT NULL AND qb.knowledge_point_id != ''""",
            (student_id,)))

        if not answers:
            return LearningPathService._get_track_entry_recommendations()

        # ── 2. 批量查 Neo4j 获取 tracks ──
        kp_ids = list(set(a['knowledge_point_id'] for a in answers))
        node_map = graph_repo.get_nodes_by_ids(kp_ids) if kp_ids else {}

        # ── 3. 按 track 汇总 ──
        track_stats = {}  # track_name → { total, correct, wrong, categories }
        for a in answers:
            kp_id = a['knowledge_point_id']
            node = node_map.get(kp_id, {})
            kp_tracks = node.get('tracks', [])
            if not kp_tracks:
                kp_tracks = ['未分类']
            if isinstance(kp_tracks, str):
                kp_tracks = [kp_tracks]
            for track in kp_tracks:
                track = track.strip()
                if not track:
                    continue
                if track not in track_stats:
                    track_stats[track] = {'total': 0, 'correct': 0, 'wrong': 0, 'categories': set()}
                track_stats[track]['total'] += 1
                track_stats[track]['categories'].add(node.get('category', ''))
                if a['is_correct']:
                    track_stats[track]['correct'] += 1
                else:
                    track_stats[track]['wrong'] += 1

        if not track_stats:
            return LearningPathService._get_track_entry_recommendations()

        # ── 4. 计算每个 track 的专注度评分 ──
        max_questions = max(s['total'] for s in track_stats.values())
        ranked_tracks = []
        for track, stats in track_stats.items():
            volume_weight = stats['total'] / max_questions if max_questions else 0
            accuracy = stats['correct'] / stats['total'] if stats['total'] else 0
            # focus_score: 题目量权重 70% + 正确率权重 30%（正确率越高越专注）
            focus_score = round((volume_weight * 70 + accuracy * 30), 1)
            ranked_tracks.append({
                'track': track,
                'focus_score': focus_score,
                'question_count': stats['total'],
                'correct': stats['correct'],
                'wrong': stats['wrong'],
                'categories': list(stats['categories'])
            })

        # 按 focus_score 降序
        ranked_tracks.sort(key=lambda x: x['focus_score'], reverse=True)
        dominant_tracks = ranked_tracks[:5]

        # ── 5. 为每个主导 track 构建领域级路径 ──
        path_recommendations = []
        resource_recommendations = []

        for dt in dominant_tracks:
            track_name = dt['track']
            # 从 Neo4j 获取该 track 下按 category 分组的入门节点
            try:
                with graph_repo._session() as session:
                    # 获取该 track 下的顶级 category（无上级 CONTAINS 的节点）
                    result = session.run(
                        "MATCH (kp:KnowledgePoint) "
                        "WHERE ANY(t IN kp.tracks WHERE t = $track) "
                        "OPTIONAL MATCH (parent:KnowledgePoint)-[:CONTAINS]->(kp) "
                        "WITH kp, COUNT(parent) as parent_count "
                        "WHERE parent_count = 0 "
                        "RETURN kp.name as name, kp.category as category, elementId(kp) as nid "
                        "ORDER BY kp.category, kp.name LIMIT 10",
                        track=track_name
                    )
                    entry_nodes = [{'name': r['name'], 'category': r['category'], 'id': r['nid']} for r in result]

                    # 统计该 track 下的子领域（category 分布）
                    cat_result = session.run(
                        "MATCH (kp:KnowledgePoint) "
                        "WHERE ANY(t IN kp.tracks WHERE t = $track) "
                        "RETURN DISTINCT kp.category as category, COUNT(kp) as cnt "
                        "ORDER BY cnt DESC LIMIT 8",
                        track=track_name
                    )
                    sub_areas = [{'name': r['category'] or '未分类', 'count': r['cnt']} for r in cat_result]

                path_recommendations.append({
                    'track': track_name,
                    'focus_score': dt['focus_score'],
                    'sub_areas': sub_areas,
                    'entry_points': entry_nodes
                })
            except Exception:
                path_recommendations.append({
                    'track': track_name,
                    'focus_score': dt['focus_score'],
                    'sub_areas': [],
                    'entry_points': []
                })

            # ── 6. 获取该 track 相关的学习资源 ──
            try:
                # 找到该 track 下所有 KPs 的 elementId
                with graph_repo._session() as session:
                    res_result = session.run(
                        "MATCH (kp:KnowledgePoint) "
                        "WHERE ANY(t IN kp.tracks WHERE t = $track) "
                        "RETURN elementId(kp) as nid LIMIT 200",
                        track=track_name
                    )
                    track_kp_ids = [r['nid'] for r in res_result]

                if track_kp_ids:
                    track_resources = ResourceService.get_for_path(track_kp_ids)
                    # 合并所有资源并去重
                    seen_titles = set()
                    merged = []
                    for kid, res_list in (track_resources.get('data', {}) or {}).items():
                        for r in res_list:
                            if r['title'] not in seen_titles:
                                seen_titles.add(r['title'])
                                merged.append(r)
                    if merged:
                        resource_recommendations.append({
                            'track': track_name,
                            'resources': merged[:8]  # 每个 track 最多 8 个资源
                        })
            except Exception:
                pass

        return {
            'dominant_tracks': dominant_tracks,
            'path_recommendations': path_recommendations,
            'resource_recommendations': resource_recommendations
        }

    @staticmethod
    def _get_track_entry_recommendations():
        """无答题记录时返回通用推荐（无需查询 Neo4j，前端已有兜底提示）"""
        return {'dominant_tracks': [], 'path_recommendations': [], 'resource_recommendations': []}


learning_path_service = LearningPathService()
