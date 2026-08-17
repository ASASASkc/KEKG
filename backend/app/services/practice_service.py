"""学生独立刷题服务：题库浏览、作答记录、我的状态统计"""
from app.repositories import sql_repo
from app.services.question_service import QuestionService, judge_answer

class PracticeService:

    @staticmethod
    def _judge(qtype, user_ans, correct):
        """判题：统一规则（与考试自动判分一致）"""
        return judge_answer(qtype, user_ans, correct)

    @staticmethod
    def _my_map(user_id):
        """当前用户每题最新一次的作答结果: {question_id: is_correct(None 表示主观题已做)}"""
        rows = sql_repo.execute_query(
            """SELECT pa.question_id, pa.is_correct FROM practice_attempts pa
               JOIN (SELECT question_id, MAX(id) AS max_id FROM practice_attempts
                     WHERE user_id = ? GROUP BY question_id) t
                 ON pa.id = t.max_id""",
            (user_id,))
        return {r['question_id']: r['is_correct'] for r in rows}

    @staticmethod
    def _pass_rates(qids):
        """每题全班通过率: {question_id: 0-100 或 None}"""
        if not qids:
            return {}
        marks = ','.join(['?'] * len(qids))
        rows = sql_repo.execute_query(
            f"SELECT question_id, COUNT(*) AS total, SUM(is_correct = 1) AS correct "
            f"FROM exam_answers WHERE question_id IN ({marks}) GROUP BY question_id",
            qids)
        rates = {}
        for r in rows:
            total = r['total'] or 0
            if total > 0:
                rates[r['question_id']] = round((r['correct'] or 0) * 100 / total, 1)
        return rates

    @staticmethod
    def list(user_id, page=1, page_size=20, qtype='', difficulty_min=None,
             difficulty_max=None, topic='', keyword='', status='', sort='',
             favorite_only=False):
        """题库列表（仅已审核题目），附带通过率与我的状态"""
        conditions = ["status = 'approved'"]
        params = []
        if qtype:
            conditions.append("type = ?")
            params.append(qtype)
        if difficulty_min is not None:
            conditions.append("difficulty >= ?")
            params.append(difficulty_min)
        if difficulty_max is not None:
            conditions.append("difficulty <= ?")
            params.append(difficulty_max)
        if topic:
            conditions.append("topic = ?")
            params.append(topic)
        if keyword:
            conditions.append("title LIKE ?")
            params.append(f'%{keyword}%')
        if favorite_only:
            conditions.append(
                "id IN (SELECT question_id FROM question_favorites WHERE user_id = ?)")
            params.append(user_id)
        where = "WHERE " + " AND ".join(conditions)

        count_row = sql_repo.execute_query(
            f"SELECT COUNT(*) AS cnt FROM question_bank {where}", params)
        total = count_row[0]['cnt'] if count_row else 0

        offset = (page - 1) * page_size
        rows = sql_repo.execute_query(
            f"SELECT * FROM question_bank {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [page_size, offset])

        my_map = PracticeService._my_map(user_id)
        rates = PracticeService._pass_rates([r['id'] for r in rows])

        items = []
        for r in rows:
            qid = r['id']
            my_status = 'undone'
            if qid in my_map:
                my_status = 'wrong' if my_map[qid] == 0 else 'done'
            items.append({
                'id': qid,
                'title': r['title'],
                'type': r['type'],
                'difficulty': r['difficulty'],
                'category': r.get('category', ''),
                'topic': r.get('topic', ''),
                'pass_rate': rates.get(qid),
                'my_status': my_status,
            })

        # 批量标记收藏状态
        fav_ids = QuestionService.get_favorite_ids(
            user_id, [i['id'] for i in items])
        for it in items:
            it['is_favorite'] = it['id'] in fav_ids

        # 我的状态过滤（依赖 my_map，需在 Python 层筛选）
        if status in ('undone', 'done', 'wrong'):
            items = [i for i in items if i['my_status'] == status]

        # 排序
        if sort == 'rate_asc':
            items.sort(key=lambda i: i['pass_rate'] if i['pass_rate'] is not None else -1)
        elif sort == 'rate_desc':
            items.sort(key=lambda i: -(i['pass_rate'] if i['pass_rate'] is not None else -1))
        elif sort == 'diff_asc':
            items.sort(key=lambda i: i['difficulty'])
        elif sort == 'diff_desc':
            items.sort(key=lambda i: -i['difficulty'])

        # 我的统计（覆盖筛选前的全部已审核题目）
        stat_rows = sql_repo.execute_query(
            f"SELECT COUNT(*) AS cnt FROM question_bank {where}", params)
        stats = {
            'total': stat_rows[0]['cnt'] if stat_rows else 0,
            'done': len([qid for qid, c in my_map.items() if c is not None]),
            'wrong': len([c for c in my_map.values() if c == 0]),
            'correct': len([c for c in my_map.values() if c == 1]),
        }

        return {
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': max(1, (total + page_size - 1) // page_size),
            'stats': stats,
        }

    @staticmethod
    def get_question(user_id, qid):
        """单题详情（含我的最近作答记录与通过率）"""
        rows = sql_repo.execute_query(
            "SELECT * FROM question_bank WHERE id = ? AND status = 'approved'", (qid,))
        if not rows:
            return None
        q = rows[0]
        item = QuestionService._format(q)
        last = sql_repo.execute_query(
            "SELECT user_answer, is_correct, created_at FROM practice_attempts "
            "WHERE user_id = ? AND question_id = ? ORDER BY id DESC LIMIT 1",
            (user_id, qid))
        item['last_attempt'] = dict(last[0]) if last else None
        rates = PracticeService._pass_rates([qid])
        item['pass_rate'] = rates.get(qid)
        fav_rows = sql_repo.execute_query(
            "SELECT 1 FROM question_favorites WHERE user_id = ? AND question_id = ?",
            (user_id, qid))
        item['is_favorite'] = bool(fav_rows)
        return item

    @staticmethod
    def submit(user_id, question_id, answer, elapsed_seconds=0):
        """提交一次作答，记录并返回判题结果"""
        rows = sql_repo.execute_query(
            "SELECT * FROM question_bank WHERE id = ? AND status = 'approved'", (question_id,))
        if not rows:
            return False, None, '题目不存在'
        q = rows[0]
        is_correct = PracticeService._judge(q['type'], answer, q['answer'])
        sql_repo.execute_insert(
            "INSERT INTO practice_attempts (user_id, question_id, user_answer, is_correct, elapsed_seconds) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, question_id, answer or '', is_correct, int(elapsed_seconds or 0)))
        return True, {
            'question_id': q['id'],
            'q_type': q['type'],
            'is_multi': q.get('is_multi', 0),
            'is_correct': is_correct,
            'correct_answer': q['answer'],
            'explanation': q.get('explanation'),
        }, '提交成功'

    @staticmethod
    def history(user_id, page=1, page_size=20, question_id=None):
        """我的提交记录：历次作答时间线（题目/答案/结果/用时/时间）"""
        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        conditions = ["pa.user_id = ?"]
        params = [user_id]
        if question_id:
            conditions.append("pa.question_id = ?")
            params.append(question_id)
        where = " AND ".join(conditions)

        count_row = sql_repo.execute_query(
            f"SELECT COUNT(*) AS cnt FROM practice_attempts pa WHERE {where}", params)
        total = count_row[0]['cnt'] if count_row else 0

        offset = (page - 1) * page_size
        rows = sql_repo.execute_query(
            f"""SELECT pa.id, pa.question_id, pa.user_answer, pa.is_correct,
                       pa.elapsed_seconds, pa.created_at,
                       qb.title AS question_title, qb.type AS q_type
                FROM practice_attempts pa
                JOIN question_bank qb ON pa.question_id = qb.id
                WHERE {where}
                ORDER BY pa.id DESC
                LIMIT ? OFFSET ?""",
            params + [page_size, offset])
        items = []
        for r in rows:
            items.append({
                'id': r['id'],
                'question_id': r['question_id'],
                'question_title': r['question_title'],
                'q_type': r['q_type'],
                'user_answer': r['user_answer'],
                'is_correct': r['is_correct'],
                'elapsed_seconds': r.get('elapsed_seconds') or 0,
                'created_at': str(r['created_at']) if r.get('created_at') else '',
            })
        return {
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': max(1, (total + page_size - 1) // page_size),
        }
