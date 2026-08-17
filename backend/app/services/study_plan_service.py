# -*- coding: utf-8 -*-
"""自定义学习计划服务"""
import json
from datetime import datetime, date
from ..repositories.sql_repo import sql_repo


class StudyPlanService:

    @staticmethod
    def get_user_plans(user_id):
        """获取用户的所有学习计划（含打卡统计）"""
        rows = sql_repo.execute_query(
            """SELECT sp.*,
                      (SELECT COUNT(*) FROM study_plan_checkins spc WHERE spc.plan_id = sp.id) as total_checkins,
                      (SELECT COALESCE(SUM(study_minutes), 0) FROM study_plan_checkins spc WHERE spc.plan_id = sp.id) as total_study_minutes,
                      (SELECT COALESCE(SUM(question_count), 0) FROM study_plan_checkins spc WHERE spc.plan_id = sp.id) as total_questions
               FROM study_plans sp
               WHERE sp.user_id = ? AND sp.status != 'deleted'
               ORDER BY sp.created_at DESC""",
            (user_id,)
        )
        results = []
        for r in rows:
            plan = StudyPlanService._format(r)
            plan['total_checkins'] = r.get('total_checkins', 0) or 0
            plan['total_study_minutes'] = r.get('total_study_minutes', 0) or 0
            plan['total_questions'] = r.get('total_questions', 0) or 0
            results.append(plan)
        # 批量统计各计划题单完成情况（避免逐计划查询）
        plans_with_q = [p for p in results if p.get('question_ids')]
        if plans_with_q:
            all_qids = sorted({qid for p in plans_with_q for qid in p['question_ids']})
            marks = ','.join(['?'] * len(all_qids))
            qb_rows = sql_repo.execute_query(
                f"SELECT id FROM question_bank WHERE id IN ({marks}) AND status = 'approved'", all_qids)
            valid_ids = {r['id'] for r in qb_rows}
            attempt_rows = sql_repo.execute_query(
                f"""SELECT pa.question_id, pa.is_correct FROM practice_attempts pa
                    JOIN (SELECT question_id, MAX(id) AS mid FROM practice_attempts
                          WHERE user_id = ? AND question_id IN ({marks}) GROUP BY question_id) t
                      ON pa.id = t.mid""",
                (user_id, *all_qids))
            state = {r['question_id']: r['is_correct'] for r in attempt_rows}
            for p in plans_with_q:
                qids = [q for q in p['question_ids'] if q in valid_ids]
                done = sum(1 for q in qids if state.get(q) == 1)
                p['question_total'] = len(qids)
                p['question_done'] = done
        else:
            for p in results:
                p['question_total'] = 0
                p['question_done'] = 0
        return results

    @staticmethod
    def get_plan(plan_id, user_id):
        """获取单个学习计划"""
        rows = sql_repo.execute_query(
            """SELECT * FROM study_plans WHERE id = ? AND user_id = ?""",
            (plan_id, user_id)
        )
        return StudyPlanService._format(rows[0]) if rows else None

    @staticmethod
    def get_plan_questions(plan_id, user_id):
        """获取计划题单明细（题目 + 我的作答状态），并联动更新计划进度"""
        plan = StudyPlanService.get_plan(plan_id, user_id)
        if not plan:
            raise ValueError('计划不存在或无权操作')
        qids = plan.get('question_ids') or []
        if not qids:
            return {'items': [], 'done': 0, 'total': 0, 'progress': plan.get('progress', 0)}
        marks = ','.join(['?'] * len(qids))
        rows = sql_repo.execute_query(
            f"""SELECT id, title, type, difficulty, category FROM question_bank
                WHERE id IN ({marks}) AND status = 'approved'""", qids)
        row_map = {r['id']: r for r in rows}
        ordered = [row_map[q] for q in qids if q in row_map]
        attempt_rows = sql_repo.execute_query(
            f"""SELECT pa.question_id, pa.is_correct FROM practice_attempts pa
                JOIN (SELECT question_id, MAX(id) AS mid FROM practice_attempts
                      WHERE user_id = ? AND question_id IN ({marks}) GROUP BY question_id) t
                  ON pa.id = t.mid""",
            (user_id, *qids))
        state = {r['question_id']: r['is_correct'] for r in attempt_rows}
        items = []
        done = 0
        for q in ordered:
            st = state.get(q['id'])
            status = 'undone'
            if st == 1:
                status = 'done'
                done += 1
            elif st == 0:
                status = 'wrong'
            items.append({
                'id': q['id'], 'title': q['title'], 'type': q['type'],
                'difficulty': q['difficulty'], 'category': q.get('category', ''),
                'status': status
            })
        progress = round(done * 100 / len(items), 1) if items else 0
        # 题单完成度同步到计划进度（不覆盖手动设置的高值）
        if progress > (plan.get('progress') or 0):
            sql_repo.execute_update(
                "UPDATE study_plans SET progress = ? WHERE id = ?", (int(progress), plan_id))
            plan['progress'] = int(progress)
        return {'items': items, 'done': done, 'total': len(items), 'progress': progress}

    @staticmethod
    def create(user_id, title, description='', knowledge_point_ids=None,
               target_date=None, question_ids=None):
        """创建学习计划"""
        if not title or not title.strip():
            raise ValueError('计划标题不能为空')
        kp_json = json.dumps(knowledge_point_ids or [], ensure_ascii=False)
        q_json = json.dumps(question_ids or [], ensure_ascii=False)
        pid = sql_repo.execute_insert(
            """INSERT INTO study_plans (user_id, title, description, knowledge_point_ids, target_date, question_ids)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, title.strip(), description or '', kp_json, target_date or None, q_json)
        )
        return StudyPlanService.get_plan(pid, user_id)

    @staticmethod
    def update(plan_id, user_id, **kwargs):
        """更新学习计划"""
        plan = StudyPlanService.get_plan(plan_id, user_id)
        if not plan:
            raise ValueError('计划不存在或无权操作')

        fields = []
        values = []
        for key in ('title', 'description', 'target_date', 'progress', 'status'):
            if key in kwargs and kwargs[key] is not None:
                if key == 'title' and not kwargs[key].strip():
                    continue
                fields.append(f'{key} = ?')
                values.append(kwargs[key].strip() if key == 'title' else kwargs[key])
        if 'knowledge_point_ids' in kwargs:
            fields.append('knowledge_point_ids = ?')
            values.append(json.dumps(kwargs['knowledge_point_ids'], ensure_ascii=False))
        if 'question_ids' in kwargs:
            fields.append('question_ids = ?')
            values.append(json.dumps(kwargs['question_ids'] or [], ensure_ascii=False))

        if not fields:
            return plan

        values.extend([plan_id, user_id])
        sql_repo.execute_update(
            f"UPDATE study_plans SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
            tuple(values)
        )
        return StudyPlanService.get_plan(plan_id, user_id)

    @staticmethod
    def delete(plan_id, user_id):
        """软删除学习计划"""
        plan = StudyPlanService.get_plan(plan_id, user_id)
        if not plan:
            raise ValueError('计划不存在或无权操作')
        sql_repo.execute_update(
            "UPDATE study_plans SET status = 'deleted' WHERE id = ? AND user_id = ?",
            (plan_id, user_id)
        )
        return {'id': plan_id}

    @staticmethod
    def checkin(plan_id, user_id, study_minutes=0, question_count=0, notes=''):
        """每日打卡"""
        plan = StudyPlanService.get_plan(plan_id, user_id)
        if not plan:
            raise ValueError('计划不存在或无权操作')
        today = date.today().isoformat()
        try:
            sql_repo.execute_insert(
                """INSERT INTO study_plan_checkins (plan_id, user_id, checkin_date, study_minutes, question_count, notes)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON DUPLICATE KEY UPDATE study_minutes = study_minutes + ?,
                                           question_count = question_count + ?,
                                           notes = CONCAT(IFNULL(notes,''), ?)""",
                (plan_id, user_id, today, study_minutes, question_count, notes or '',
                 study_minutes, question_count, '\n' + (notes or '') if notes else '')
            )
        except Exception:
            # Fallback: try update then insert for DBs without ON DUPLICATE KEY
            existing = sql_repo.execute_query(
                "SELECT id FROM study_plan_checkins WHERE plan_id = ? AND user_id = ? AND checkin_date = ?",
                (plan_id, user_id, today))
            if existing:
                sql_repo.execute_update(
                    """UPDATE study_plan_checkins
                       SET study_minutes = study_minutes + ?, question_count = question_count + ?,
                           notes = CONCAT(IFNULL(notes,''), ?)
                       WHERE plan_id = ? AND user_id = ? AND checkin_date = ?""",
                    (study_minutes, question_count, '\n' + (notes or '') if notes else '',
                     plan_id, user_id, today))
            else:
                sql_repo.execute_insert(
                    """INSERT INTO study_plan_checkins (plan_id, user_id, checkin_date, study_minutes, question_count, notes)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (plan_id, user_id, today, study_minutes, question_count, notes or ''))
        # 更新计划进度：不覆盖题单进度（GREATEST 保证只增不减）
        total = sql_repo.execute_query(
            "SELECT COUNT(*) as cnt FROM study_plan_checkins WHERE plan_id = ?", (plan_id,))
        cnt = total[0]['cnt'] if total else 0
        sql_repo.execute_update(
            "UPDATE study_plans SET progress = LEAST(GREATEST(progress, ?), 100) WHERE id = ?",
            (min(cnt * 10, 100), plan_id))
        return {'plan_id': plan_id, 'date': today, 'study_minutes': study_minutes,
                'question_count': question_count}

    @staticmethod
    def get_checkins(plan_id, user_id, year_month=None):
        """获取某计划某月的打卡记录"""
        plan = StudyPlanService.get_plan(plan_id, user_id)
        if not plan:
            raise ValueError('计划不存在或无权操作')
        if year_month:
            start = f'{year_month}-01'
            ym = year_month.split('-')
            y, m = int(ym[0]), int(ym[1])
            if m == 12:
                end = f'{y+1}-01-01'
            else:
                end = f'{y}-{m+1:02d}-01'
            rows = sql_repo.execute_query(
                """SELECT checkin_date, study_minutes, question_count, notes
                   FROM study_plan_checkins
                   WHERE plan_id = ? AND user_id = ? AND checkin_date >= ? AND checkin_date < ?
                   ORDER BY checkin_date""",
                (plan_id, user_id, start, end))
        else:
            rows = sql_repo.execute_query(
                """SELECT checkin_date, study_minutes, question_count, notes
                   FROM study_plan_checkins
                   WHERE plan_id = ? AND user_id = ?
                   ORDER BY checkin_date DESC LIMIT 90""",
                (plan_id, user_id))
        return [dict(r) for r in rows]

    @staticmethod
    def get_checkin_streak(plan_id, user_id):
        """获取连续打卡天数"""
        rows = sql_repo.execute_query(
            """SELECT checkin_date FROM study_plan_checkins
               WHERE plan_id = ? AND user_id = ?
               ORDER BY checkin_date DESC""",
            (plan_id, user_id))
        if not rows:
            return 0
        today = date.today()
        streak = 0
        expected = today
        for r in rows:
            d = r['checkin_date']
            if isinstance(d, str):
                d = date.fromisoformat(d)
            if d == expected or d == expected - date.resolution:
                streak += 1
                expected = d - date.resolution
            elif d < expected - date.resolution:
                break
            # Same day multiple checkins don't break streak
        return streak

    @staticmethod
    def _format(row):
        """格式化计划记录"""
        r = dict(row)
        # 解析 JSON 字段
        for field in ('knowledge_point_ids', 'question_ids'):
            val = r.get(field)
            if isinstance(val, str):
                try:
                    r[field] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    r[field] = []
            elif val is None:
                r[field] = []
        # 日期格式化
        for f in ('target_date', 'created_at', 'updated_at'):
            if r.get(f):
                r[f] = str(r[f])
        return r
