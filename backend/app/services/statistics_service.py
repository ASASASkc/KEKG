# -*- coding: utf-8 -*-
"""成绩统计服务"""
from decimal import Decimal
from ..repositories.sql_repo import sql_repo
from ..repositories.graph_repo import graph_repo


def _sanitize(obj):
    """递归转换 Decimal → float, 确保 JSON 可序列化"""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


class StatisticsService:

    @staticmethod
    def student_overview(student_id, start_date=None, end_date=None):
        """学生总览"""
        conditions = ["es.student_id = ?", "es.status = 'submitted'"]
        params = [student_id]
        if start_date:
            conditions.append("ep.start_time >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("ep.start_time <= ?")
            params.append(end_date + ' 23:59:59')

        where = "WHERE " + " AND ".join(conditions)

        subs = sql_repo.execute_query(
            f"""SELECT es.*, ep.title as exam_title, ep.pass_score
               FROM exam_submissions es
               JOIN exam_papers ep ON es.exam_id = ep.id
               {where}
               ORDER BY es.submit_time DESC""",
            params)
        exams = [dict(s) for s in subs]

        total_exams = len(exams)
        passed_exams = sum(1 for s in exams if (s['total_score'] or 0) >= (s['pass_score'] or 60))
        scores = [s['total_score'] or 0 for s in exams]
        avg_score = round(sum(scores) / total_exams, 1) if total_exams else 0
        highest_score = max(scores) if scores else 0

        # 分数段分布
        distribution = {'0-59': 0, '60-69': 0, '70-79': 0, '80-89': 0, '90-100': 0}
        for s in scores:
            if s < 60: distribution['0-59'] += 1
            elif s < 70: distribution['60-69'] += 1
            elif s < 80: distribution['70-79'] += 1
            elif s < 90: distribution['80-89'] += 1
            else: distribution['90-100'] += 1

        return _sanitize({
            'total_exams': total_exams,
            'passed_exams': passed_exams,
            'avg_score': avg_score,
            'highest_score': highest_score,
            'distribution': distribution,
            'recent_exams': exams
        })

    @staticmethod
    def student_exam_detail(eid, student_id):
        """学生单次考试分析"""
        answers = sql_repo.execute_query(
            """SELECT ea.*, qb.type as q_type, qb.difficulty as q_difficulty, qb.is_multi
               FROM exam_answers ea
               JOIN question_bank qb ON ea.question_id = qb.id
               WHERE ea.exam_id = ? AND ea.student_id = ?""",
            (eid, student_id))

        sub = sql_repo.execute_query(
            "SELECT * FROM exam_submissions WHERE exam_id = ? AND student_id = ?",
            (eid, student_id))
        if not sub:
            return None

        total_score = sub[0]['total_score'] or 0
        total_max = sum(a['max_score'] for a in answers)

        by_type = StatisticsService._group_by_field(answers, 'q_type')
        by_difficulty = StatisticsService._group_by_field(answers, 'q_difficulty',
                                                          lambda d: 'low' if d <= 3 else ('medium' if d <= 6 else 'high'))

        return _sanitize({
            'total_score': total_score,
            'total_max': total_max,
            'score_rate': round(total_score / total_max, 2) if total_max else 0,
            'by_type': by_type,
            'by_difficulty': by_difficulty
        })

    @staticmethod
    def class_exam_detail(eid, class_id):
        """班级单次考试分析"""
        subs = sql_repo.execute_query(
            """SELECT es.*, u.username
               FROM exam_submissions es
               JOIN users u ON es.student_id = u.id
               JOIN class_students cs ON es.student_id = cs.student_id AND cs.class_id = ?
               WHERE es.exam_id = ? AND es.status = 'submitted'""",
            (class_id, eid))

        if not subs:
            return None

        scores = [s['total_score'] or 0 for s in subs]
        student_count = len(subs)

        exam = sql_repo.execute_query("SELECT total_score FROM exam_papers WHERE id = ?", (eid,))
        total_max = exam[0]['total_score'] if exam else 100

        score_rates = [s / total_max for s in scores if total_max > 0]
        avg_rate = round(sum(score_rates) / len(score_rates), 2) if score_rates else 0

        # 分数段分布
        distribution = {'0-59': 0, '60-69': 0, '70-79': 0, '80-89': 0, '90-100': 0}
        for s in scores:
            if s < 60:
                distribution['0-59'] += 1
            elif s < 70:
                distribution['60-69'] += 1
            elif s < 80:
                distribution['70-79'] += 1
            elif s < 90:
                distribution['80-89'] += 1
            else:
                distribution['90-100'] += 1

        # 各题正确率 — 有答案就统计，没答案也要返回题目列表（正确率 0）
        question_stats = sql_repo.execute_query(
            """SELECT eq.question_id, qb.title, qb.type, qb.difficulty, eq.score as max_score,
                      COALESCE(
                        AVG(CASE WHEN ea.is_correct = 1 THEN 1.0 ELSE 0.0 END), 0
                      ) as correct_rate
               FROM exam_questions eq
               JOIN question_bank qb ON eq.question_id = qb.id
               LEFT JOIN exam_answers ea ON eq.question_id = ea.question_id
                   AND ea.exam_id = ? AND ea.student_id IN (
                       SELECT student_id FROM class_students WHERE class_id = ?
                   )
               WHERE eq.exam_id = ?
               GROUP BY eq.question_id, qb.title, qb.type, qb.difficulty, eq.score, eq.sort_order
               ORDER BY eq.sort_order""",
            (eid, class_id, eid))

        return _sanitize({
            'student_count': student_count,
            'average_score': round(sum(scores) / student_count, 1),
            'max_score': max(scores),
            'min_score': min(scores),
            'pass_rate': round(len([s for s in scores if s >= 60]) / student_count * 100, 1),
            'score_rates': score_rates,
            'distribution': distribution,
            'question_stats': [dict(q) for q in question_stats],
            'students': [dict(s) for s in subs]
        })

    @staticmethod
    def class_summary(class_id, start_date=None, end_date=None):
        """班级历史汇总 — 返回聚合统计"""
        # 班级学生总数
        total_students = sql_repo.execute_query(
            "SELECT COUNT(*) as cnt FROM class_students WHERE class_id = ?", (class_id,))[0]['cnt']

        conditions = ["ep.class_id = ?"]
        params = [class_id]
        if start_date:
            conditions.append("ep.start_time >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("ep.start_time <= ?")
            params.append(end_date + ' 23:59:59')

        where = "WHERE " + " AND ".join(conditions)

        exam_list = sql_repo.execute_query(
            f"""SELECT ep.id as exam_id, ep.title, ep.total_score, ep.pass_score,
                       AVG(es.total_score) as avg_score,
                       COUNT(DISTINCT CASE WHEN es.status='submitted' THEN es.student_id END) as submitted_count
                FROM exam_papers ep
                LEFT JOIN exam_submissions es ON ep.id = es.exam_id
                {where}
                GROUP BY ep.id
                ORDER BY ep.start_time DESC""",
            params)
        exams = [dict(r) for r in exam_list]

        # 汇总计算
        exam_count = len(exams)
        all_avgs = [e['avg_score'] for e in exams if e['avg_score'] is not None]
        overall_avg = round(sum(all_avgs) / len(all_avgs), 1) if all_avgs else 0

        # 整体分布
        all_scores_data = sql_repo.execute_query(
            f"""SELECT es.total_score, ep.pass_score
                FROM exam_submissions es
                JOIN exam_papers ep ON es.exam_id = ep.id
                {where.replace('ep.class_id', 'ep.class_id').replace('ep.start_time', 'ep.start_time')}
                AND es.status = 'submitted'""",
            params)
        scores = [s['total_score'] or 0 for s in all_scores_data]
        pass_count = sum(1 for s in all_scores_data if (s['total_score'] or 0) >= (s['pass_score'] or 60))
        total_submissions = len(scores)

        distribution = {'0-59': 0, '60-69': 0, '70-79': 0, '80-89': 0, '90-100': 0}
        for s in scores:
            if s < 60: distribution['0-59'] += 1
            elif s < 70: distribution['60-69'] += 1
            elif s < 80: distribution['70-79'] += 1
            elif s < 90: distribution['80-89'] += 1
            else: distribution['90-100'] += 1

        sorted_scores = sorted(scores)
        n = len(sorted_scores)
        if n == 0:
            median_score = 0
        elif n % 2 == 1:
            median_score = sorted_scores[n // 2]
        else:
            median_score = round((sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2, 1)

        return _sanitize({
            'total_students': total_students,
            'exam_count': exam_count,
            'avg_score': overall_avg,
            'median_score': median_score,
            'pass_rate': round(pass_count / total_submissions * 100, 1) if total_submissions else 0,
            'total_submissions': total_submissions,
            'distribution': distribution,
            'by_exam': exams
        })

    @staticmethod
    def student_summary(student_id, start_date=None, end_date=None):
        """学生历史汇总"""
        conditions = ["es.student_id = ?", "es.status = 'submitted'"]
        params = [student_id]
        if start_date:
            conditions.append("ep.start_time >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("ep.start_time <= ?")
            params.append(end_date + ' 23:59:59')

        where = "WHERE " + " AND ".join(conditions)

        summary = sql_repo.execute_query(
            f"""SELECT ep.id as exam_id, ep.title, ep.total_score,
                       es.total_score, es.submit_time
                FROM exam_submissions es
                JOIN exam_papers ep ON es.exam_id = ep.id
                {where}
                ORDER BY es.submit_time DESC""",
            params)
        return [dict(r) for r in summary]

    @staticmethod
    def _group_by_field(answers, field, transform=None):
        groups = {}
        for a in answers:
            key = a[field]
            if transform:
                key = transform(key)
            if key not in groups:
                groups[key] = {'score': 0, 'max': 0, 'count': 0}
            groups[key]['score'] += a['score'] or 0
            groups[key]['max'] += a['max_score'] or 0
            groups[key]['count'] += 1
        for k, v in groups.items():
            v['rate'] = round(v['score'] / v['max'], 2) if v['max'] else 0
        return groups

    @staticmethod
    def student_radar(student_id):
        """学生知识点分类掌握度（雷达图数据）"""
        # 获取该学生所有已提交的答题
        answers = sql_repo.execute_query(
            """SELECT ea.*, qb.knowledge_point_id
               FROM exam_answers ea
               JOIN exam_submissions es ON ea.exam_id = es.exam_id AND ea.student_id = es.student_id
               JOIN question_bank qb ON ea.question_id = qb.id
               WHERE ea.student_id = ? AND es.status = 'submitted'""",
            (student_id,))

        if not answers:
            return _sanitize({'categories': [], 'radar': [], 'total_answers': 0})

        # 收集所有 knowledge_point_id
        kp_ids = list(set(a['knowledge_point_id'] for a in answers if a.get('knowledge_point_id')))

        # 批量查 Neo4j 获取 category
        node_map = graph_repo.get_nodes_by_ids(kp_ids) if kp_ids else {}

        # 按 category 聚合
        cat_scores = {}
        for a in answers:
            kpid = a.get('knowledge_point_id', '')
            nprop = node_map.get(kpid, {})
            cat = nprop.get('category', '未分类')
            if cat not in cat_scores:
                cat_scores[cat] = {'score': 0, 'max': 0, 'count': 0}
            cat_scores[cat]['score'] += a['score'] or 0
            cat_scores[cat]['max'] += a['max_score'] or 0
            cat_scores[cat]['count'] += 1

        radar = []
        categories = []
        for cat, v in sorted(cat_scores.items()):
            rate = round(v['score'] / v['max'] * 100, 1) if v['max'] else 0
            categories.append(cat)
            radar.append({
                'category': cat,
                'accuracy': rate,
                'answered': v['count'],
                'score': v['score'],
                'max': v['max']
            })

        return _sanitize({
            'categories': categories,
            'radar': radar,
            'total_answers': len(answers)
        })

    @staticmethod
    def class_weak_points(eid, class_id):
        """班级薄弱知识点排行（按正确率升序）"""
        # 获取该班级该次考试所有答题（含知识点信息）
        answers = sql_repo.execute_query(
            """SELECT ea.*, qb.knowledge_point_id, qb.knowledge_point_name
               FROM exam_answers ea
               JOIN question_bank qb ON ea.question_id = qb.id
               JOIN class_students cs ON ea.student_id = cs.student_id AND cs.class_id = ?
               WHERE ea.exam_id = ?""",
            (class_id, eid))

        if not answers:
            return _sanitize({'weak_points': [], 'total_answers': 0})

        # 收集 knowledge_point_id
        kp_ids = list(set(
            a['knowledge_point_id'] for a in answers if a.get('knowledge_point_id')
        ))

        # 批量查 Neo4j 获取 category
        node_map = graph_repo.get_nodes_by_ids(kp_ids) if kp_ids else {}

        # 按知识点聚合
        kp_scores = {}
        for a in answers:
            kpid = a.get('knowledge_point_id', '')
            kpname = a.get('knowledge_point_name', '') or (node_map.get(kpid, {}).get('name', '未知'))
            if kpid not in kp_scores:
                nprop = node_map.get(kpid, {})
                kp_scores[kpid] = {
                    'knowledge_point_id': kpid,
                    'knowledge_point_name': kpname,
                    'category': nprop.get('category', '未分类'),
                    'score': 0, 'max': 0, 'correct': 0, 'total': 0
                }
            kp_scores[kpid]['score'] += a['score'] or 0
            kp_scores[kpid]['max'] += a['max_score'] or 0
            kp_scores[kpid]['total'] += 1
            if (a['is_correct'] or 0) == 1:
                kp_scores[kpid]['correct'] += 1

        # 排序：正确率升序（薄弱在前）
        weak = []
        for kpid, v in kp_scores.items():
            rate = round(v['correct'] / v['total'] * 100, 1) if v['total'] else 0
            v['accuracy'] = rate
            weak.append(v)

        weak.sort(key=lambda x: x['accuracy'])

        return _sanitize({'weak_points': weak, 'total_answers': len(answers)})


statistics_service = StatisticsService()
