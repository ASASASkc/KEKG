# -*- coding: utf-8 -*-
"""考试管理服务"""
import json
import time
import re
from datetime import datetime, timedelta
from ..repositories.sql_repo import sql_repo
from .question_service import question_service, judge_answer, normalize_judge
from .llm_service import LLMService


class ExamService:

    @staticmethod
    def create(title, class_id, duration_minutes, start_time, end_time,
               description='', pass_score=60, created_by=1, task_type='exam',
               max_attempts=None, weight_config=None):
        if not title or not title.strip():
            raise ValueError('试卷标题不能为空')
        if not start_time or not str(start_time).strip():
            start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if not end_time or not str(end_time).strip():
            end_time = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        weight_json = json.dumps(weight_config, ensure_ascii=False) if weight_config else None
        eid = sql_repo.execute_insert(
            """INSERT INTO exam_papers (title, task_type, description, class_id, duration_minutes,
               start_time, end_time, pass_score, max_attempts, weight_config, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title.strip(), task_type, description or '', class_id, duration_minutes,
             start_time, end_time, pass_score, max_attempts, weight_json, created_by)
        )
        return {'id': eid, 'title': title.strip(), 'task_type': task_type}

    @staticmethod
    def generate(title, class_id, duration_minutes, start_time, end_time,
                 rules, description='', pass_score=60, created_by=1, task_type='exam'):
        """智能生成试卷：按规则从题库随机抽题"""
        if not start_time or not str(start_time).strip():
            start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if not end_time or not str(end_time).strip():
            end_time = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        eid = sql_repo.execute_insert(
            """INSERT INTO exam_papers (title, task_type, description, class_id, duration_minutes,
               start_time, end_time, pass_score, created_by, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')""",
            (title.strip(), task_type, description or '', class_id, duration_minutes,
             start_time, end_time, pass_score, created_by)
        )

        total_score = 0
        sort_order = 0
        for rule in rules:
            qtype = rule.get('type', 'choice')
            count = rule.get('count', 0)
            score = rule.get('score_per_question', 0)
            topics = rule.get('topics', [])

            if count <= 0:
                continue

            if topics and len(topics) > 0:
                placeholders = ','.join('?' * len(topics))
                rows = sql_repo.execute_query(
                    f"""SELECT id FROM question_bank
                        WHERE type = ?
                        AND topic IN ({placeholders}) AND status = 'approved'
                        ORDER BY RANDOM() LIMIT ?""",
                    [qtype] + topics + [count]
                )
            else:
                rows = sql_repo.execute_query(
                    """SELECT id FROM question_bank
                       WHERE type = ? AND status = 'approved'
                       ORDER BY RANDOM() LIMIT ?""",
                    (qtype, count)
                )

            for row in rows:
                sql_repo.execute_insert(
                    """INSERT INTO exam_questions (exam_id, question_id, score, sort_order)
                       VALUES (?, ?, ?, ?)""",
                    (eid, row['id'], score, sort_order)
                )
                total_score += score
                sort_order += 1

        sql_repo.execute_update(
            "UPDATE exam_papers SET total_score = ? WHERE id = ?",
            (total_score, eid)
        )
        return {'id': eid, 'total_score': total_score}

    @staticmethod
    def generate_ai(title, description, rules, knowledge_point_ids=None, knowledge_point_names=None,
                    class_id=0, duration_minutes=60, start_time='', end_time='',
                    pass_score=60, created_by=1, task_type='exam'):
        """
        AI 组卷：先从题库抽题，不足则调 LLM 补齐
        难度由知识点数量自动计算: log2(n)+1，上限 12
        
        Args:
            title: 试卷标题
            description: 试卷描述/主题
            rules: [{type, count, score_per_question}, ...]
            knowledge_point_ids: 关联知识点 Neo4j elementId 列表
            knowledge_point_names: 知识点名称列表（传 LLM prompt 用）
        """
        kp_ids = knowledge_point_ids or []
        kp_names = knowledge_point_names or []
        total_score = 0
        sort_order = 0
        all_question_ids = []

        sql_repo.begin_transaction()
        try:
            for rule in rules:
                qtype = rule.get('type', 'choice')
                count = rule.get('count', 0)
                score = rule.get('score_per_question', 0)

                if count <= 0:
                    continue

                # 1. 先从题库抽
                rows = sql_repo.execute_query(
                    """SELECT id FROM question_bank
                       WHERE type = ? AND status = 'approved'
                       ORDER BY RANDOM() LIMIT ?""",
                    (qtype, count)
                )
                got = len(rows)
                for row in rows:
                    all_question_ids.append({'id': row['id'], 'score': score})

                # 2. 不够则 LLM 补齐
                shortfall = count - got
                if shortfall > 0:
                    generated = ExamService._llm_generate(
                        title=title,
                        description=description,
                        knowledge_point_names=kp_names,
                        qtype=qtype,
                        count=shortfall
                    )
                    for gq in generated:
                        try:
                            qid = question_service.create(
                                title=gq['title'],
                                qtype=qtype,
                                answer=gq['answer'],
                                options=gq.get('options'),
                                explanation=gq.get('explanation', ''),
                                code_template=gq.get('code_template', ''),
                                knowledge_point_ids=kp_ids,
                                created_by=created_by,
                                status='pending'
                            )
                            all_question_ids.append({'id': qid['id'], 'score': score})
                        except Exception as e:
                            import logging
                            logging.getLogger(__name__).error('[exam_ai] 题目入库失败: %s', e)

            if not all_question_ids:
                raise ValueError('未能生成任何题目')

            # 3. 创建试卷
            if not start_time or not str(start_time).strip():
                start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if not end_time or not str(end_time).strip():
                end_time = datetime.now().replace(hour=23, minute=59).strftime('%Y-%m-%d %H:%M:%S')

            eid = sql_repo.execute_insert(
                """INSERT INTO exam_papers (title, task_type, description, class_id, duration_minutes,
                   start_time, end_time, pass_score, created_by, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')""",
                (title.strip(), task_type, description or '', class_id, duration_minutes,
                 start_time, end_time, pass_score, created_by)
            )

            for q in all_question_ids:
                sql_repo.execute_insert(
                    """INSERT INTO exam_questions (exam_id, question_id, score, sort_order)
                       VALUES (?, ?, ?, ?)""",
                    (eid, q['id'], q['score'], sort_order)
                )
                total_score += q['score']
                sort_order += 1

            sql_repo.execute_update(
                "UPDATE exam_papers SET total_score = ? WHERE id = ?",
                (total_score, eid)
            )
            sql_repo.commit_transaction()
        except Exception:
            sql_repo.rollback_transaction()
            raise

        return {
            'id': eid,
            'title': title.strip(),
            'total_score': total_score,
            'question_count': len(all_question_ids)
        }

    @staticmethod
    def _llm_generate(title, description, knowledge_point_names, qtype, count):
        """调用 LLM 生成指定数量和类型的题目，围绕指定知识点"""
        type_map = {
            'choice': '单选题（4个选项A/B/C/D，只有一个正确答案）',
            'judge': '判断题（答案填"对"或"错"）',
            'fill': '填空题',
            'subjective': '简答题（答案为简短文字说明）',
            'code': '编程题（需包含 code_template 字段）',
        }
        type_desc = type_map.get(qtype, qtype)

        desc_line = f"\n试卷描述：{description}" if description else ""
        kp_line = ''
        if knowledge_point_names:
            kp_line = '\n知识点范围：' + '、'.join(knowledge_point_names[:20])

        prompt = f"""你是一个专业的教育出题专家。请生成 {count} 道{type_desc}。

试卷主题：{title}{desc_line}{kp_line}
题目语言：中文

请严格按照以下 JSON 数组格式输出（仅输出 JSON，不要包含任何其他文字说明）：

```json
[
  {{
    "title": "题目内容",
    "type": "{qtype}",
    "options": ["A. 选项A", "B. 选项B", "C. 选项C", "D. 选项D"],
    "answer": "正确答案（判断填对/错）",
    "explanation": "题目解析说明",
    "code_template": "编程题必填"
  }}
]
```

注意：
- 选择题 options 必填，至少4个选项（带A/B/C/D前缀）
- 判断题答案仅填"对"或"错"，options 填空数组 []
- 简答题 answer 填简要答案即可
- 编程题必须提供 code_template 字段
- 所有字段均为字符串类型（options 为字符串数组）"""

        messages = [{'role': 'user', 'content': prompt}]
        response_text = LLMService.chat(messages, temperature=0.8, max_tokens=16384)

        # Parse JSON
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response_text)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            arr_match = re.search(r'\[[\s\S]*\]', response_text)
            json_str = arr_match.group(0) if arr_match else response_text

        try:
            questions = json.loads(json_str)
            if isinstance(questions, dict):
                questions = questions.get('questions', [])
            if not isinstance(questions, list):
                questions = []
            return questions[:count]
        except json.JSONDecodeError:
            return []

    # ────────────────── 基础 CRUD ──────────────────

    @staticmethod
    def _parse_options(row, field='options'):
        """将 options/q_options 从 JSON 字符串解析为数组"""
        val = row.get(field)
        if isinstance(val, str):
            try:
                row[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                row[field] = []
        elif val is None:
            row[field] = []

    @staticmethod
    def get_by_id(eid):
        """获取考试详情（含题目列表和班级名）"""
        rows = sql_repo.execute_query(
            """SELECT ep.*, c.name as class_name
               FROM exam_papers ep
               LEFT JOIN classes c ON ep.class_id = c.id
               WHERE ep.id = ? AND ep.status != 'deleted'""", (eid,))
        if not rows:
            return None
        paper = dict(rows[0])
        paper['start_time'] = str(paper.get('start_time', ''))
        paper['end_time'] = str(paper.get('end_time', ''))
        questions = sql_repo.execute_query(
            """SELECT eq.id as eq_id, eq.score, eq.sort_order,
                      qb.id as id, qb.id as question_id, qb.title, qb.type, qb.options,
                      qb.difficulty, qb.knowledge_point_name,
                      ea.content as exam_analysis
               FROM exam_questions eq
               JOIN question_bank qb ON eq.question_id = qb.id
               LEFT JOIN exam_analyses ea ON ea.exam_id = eq.exam_id AND ea.question_id = eq.question_id
               WHERE eq.exam_id = ?
               ORDER BY eq.sort_order""", (eid,))
        paper['questions'] = []
        for q in questions:
            qd = dict(q)
            ExamService._parse_options(qd, 'options')
            paper['questions'].append(qd)
        return paper

    @staticmethod
    def get_by_class(class_id):
        """管理员：获取某班级所有考试（不含已删除）"""
        rows = sql_repo.execute_query(
            """SELECT ep.*, c.name as class_name
               FROM exam_papers ep
               LEFT JOIN classes c ON ep.class_id = c.id
               WHERE ep.class_id = ? AND ep.status != 'deleted'
               ORDER BY ep.id DESC""", (class_id,))
        return [ExamService._paper_row(r) for r in rows]

    @staticmethod
    def get_by_class_published(class_id, student_id):
        """学生：获取某班级已发布考试 + 个人提交状态"""
        rows = sql_repo.execute_query(
            """SELECT ep.*, c.name as class_name,
                      es.status as my_status, es.total_score as my_score, es.id as submission_id,
                      es.attempt_count as my_attempt_count
               FROM exam_papers ep
               LEFT JOIN classes c ON ep.class_id = c.id
               LEFT JOIN exam_submissions es ON ep.id = es.exam_id AND es.student_id = ?
               WHERE ep.class_id = ? AND ep.status = 'published' AND ep.status != 'deleted'
               ORDER BY ep.id DESC""",
            (student_id, class_id))
        return [ExamService._paper_row(r) for r in rows]

    @staticmethod
    def get_admin_exams(user_id):
        """管理员：获取自己创建的所有考试"""
        rows = sql_repo.execute_query(
            """SELECT ep.*, c.name as class_name
               FROM exam_papers ep
               LEFT JOIN classes c ON ep.class_id = c.id
               WHERE ep.created_by = ? AND ep.status != 'deleted'
               ORDER BY ep.id DESC""", (user_id,))
        return [ExamService._paper_row(r) for r in rows]

    @staticmethod
    def get_by_student(user_id):
        """学生：获取自己所在班级的所有已发布考试 + 个人状态"""
        rows = sql_repo.execute_query(
            """SELECT ep.*, c.name as class_name,
                      es.status as my_status, es.total_score as my_score,
                      es.attempt_count as my_attempt_count
               FROM exam_papers ep
               JOIN class_students cs ON ep.class_id = cs.class_id AND cs.student_id = ?
               LEFT JOIN classes c ON ep.class_id = c.id
               LEFT JOIN exam_submissions es ON ep.id = es.exam_id AND es.student_id = ?
               WHERE ep.status = 'published' AND ep.status != 'deleted'
               ORDER BY ep.id DESC""",
            (user_id, user_id))
        return [ExamService._paper_row(r) for r in rows]

    @staticmethod
    def _paper_row(row):
        """标准化考试行输出（附基于时间的动态状态 time_status）"""
        d = dict(row)
        for k in ('start_time', 'end_time', 'created_at'):
            if k in d and d[k] is not None:
                d[k] = str(d[k])
        # 已发布考试按时间计算动态状态：scheduled 未开始 / active 进行中 / expired 已结束
        d['time_status'] = d.get('status', '')
        if d.get('status') == 'published':
            d['time_status'] = ExamService._time_status(
                d.get('start_time'), d.get('end_time'))
        return d

    @staticmethod
    def _parse_time(s):
        """解析 'YYYY-MM-DD HH:MM[:SS]' 或 ISO 时间串，失败返回 None"""
        if not s:
            return None
        s = str(s).replace('T', ' ').split('.')[0].strip()
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _time_status(start_time, end_time):
        """按当前时间计算已发布考试状态：scheduled / active / expired"""
        now = datetime.now()
        end = ExamService._parse_time(end_time)
        if end and now >= end:
            return 'expired'
        start = ExamService._parse_time(start_time)
        if start and now < start:
            return 'scheduled'
        return 'active'

    @staticmethod
    def update(eid, **data):
        """编辑考试基本信息"""
        allowed = ['title', 'description', 'start_time', 'end_time',
                    'duration_minutes', 'pass_score']
        sets = []
        params = []
        for k in allowed:
            if k in data:
                sets.append(f"{k} = ?")
                params.append(data[k])
        if not sets:
            return
        params.append(eid)
        sql_repo.execute_update(
            f"UPDATE exam_papers SET {', '.join(sets)} WHERE id = ?", params)

    @staticmethod
    def delete(eid):
        sql_repo.execute_update("UPDATE exam_papers SET status = 'deleted' WHERE id = ?", (eid,))
        return True

    # ────────────────── 状态流转 ──────────────────

    @staticmethod
    def publish(eid):
        rows = sql_repo.execute_query(
            """SELECT ep.title, cs.student_id
               FROM exam_papers ep
               LEFT JOIN class_students cs ON ep.class_id = cs.class_id
               WHERE ep.id = ? AND ep.status = 'draft'""", (eid,))
        affected = sql_repo.execute_update(
            "UPDATE exam_papers SET status = 'published' WHERE id = ? AND status = 'draft'", (eid,))
        if affected and rows:
            from .notification_service import notification_service
            title = rows[0]['title'] or '新考试'
            notification_service.send_many(
                [r['student_id'] for r in rows if r['student_id']],
                'exam_publish', f'新考试发布：{title}', '请及时参加考试',
                related_id=eid, related_type='exam')
        return {'success': affected > 0}

    @staticmethod
    def close(eid):
        sql_repo.execute_update(
            "UPDATE exam_papers SET status = 'closed' WHERE id = ? AND status = 'published'", (eid,))

    # ────────────────── 学生答题 ──────────────────

    @staticmethod
    def _parse_dt(s):
        """宽容解析时间字符串（兼容 T 分隔符/缺秒/仅日期），失败返回 None"""
        if not s:
            return None
        s = str(s).replace('T', ' ')
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _check_accessible(eid, user_id, check_window=False):
        """校验试卷可作答：存在、已发布、班级归属（考试额外校验时间窗口）"""
        paper = sql_repo.execute_query(
            """SELECT id, status, class_id, task_type, start_time, end_time
               FROM exam_papers WHERE id = ? AND status != 'deleted'""", (eid,))
        if not paper:
            raise ValueError('试卷不存在')
        p = paper[0]
        if p['status'] != 'published':
            raise ValueError('试卷未发布或已关闭')
        if p['class_id']:
            membership = sql_repo.execute_query(
                "SELECT id FROM class_students WHERE class_id = ? AND student_id = ?",
                (p['class_id'], user_id))
            if not membership:
                raise ValueError('你不在该试卷的班级中')
        if check_window:
            now = datetime.now()
            st = ExamService._parse_dt(p['start_time'])
            et = ExamService._parse_dt(p['end_time'])
            if st and now < st:
                raise ValueError('考试尚未开始')
            if et and now > et:
                raise ValueError('考试已结束')
        return p

    @staticmethod
    def start_exam(eid, user_id):
        """学生开始答题：创建或返回 submission，返回试卷题目（不含答案）
           检查 max_attempts 限制"""
        ExamService._check_accessible(eid, user_id, check_window=True)
        paper = ExamService.get_by_id(eid)
        if not paper:
            raise ValueError('试卷不存在')

        sub = sql_repo.execute_query(
            "SELECT * FROM exam_submissions WHERE exam_id = ? AND student_id = ?",
            (eid, user_id))

        max_attempts = paper.get('max_attempts') or 1
        current_attempts = (sub[0].get('attempt_count') or 1) if sub else 0

        # 已提交检查
        if sub and sub[0]['status'] == 'submitted':
            if current_attempts >= max_attempts:
                raise ValueError(f'已达到最大答题次数（{max_attempts}次）')
        elif sub and sub[0]['status'] == 'reviewed':
            if current_attempts >= max_attempts:
                raise ValueError(f'已达到最大答题次数（{max_attempts}次）')

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if sub and sub[0]['status'] == 'in_progress':
            started_at = sub[0]['start_time']
        elif sub and sub[0]['status'] in ('submitted', 'reviewed'):
            # 允许重考：清空旧答案，增加 attempt
            sql_repo.execute_update(
                "DELETE FROM exam_answers WHERE exam_id = ? AND student_id = ?",
                (eid, user_id))
            sql_repo.execute_update(
                """UPDATE exam_submissions SET status = 'in_progress', start_time = ?,
                   attempt_count = COALESCE(attempt_count, 0) + 1
                   WHERE exam_id = ? AND student_id = ?""",
                (now_str, eid, user_id))
            started_at = now_str
        elif sub:
            sql_repo.execute_update(
                """UPDATE exam_submissions SET status = 'in_progress', start_time = ?,
                   attempt_count = COALESCE(attempt_count, 1)
                   WHERE exam_id = ? AND student_id = ?""",
                (now_str, eid, user_id))
            started_at = now_str
        else:
            sql_repo.execute_insert(
                """INSERT INTO exam_submissions (exam_id, student_id, status, start_time, attempt_count)
                   VALUES (?, ?, 'in_progress', ?, 1)""",
                (eid, user_id, now_str))
            started_at = now_str

        # 学生端不返回答案
        for q in paper.get('questions', []):
            q.pop('answer', None)
        paper['started_at'] = str(started_at)
        paper['max_attempts'] = max_attempts
        paper['current_attempt'] = current_attempts + 1 if sub and sub[0]['status'] in ('submitted', 'reviewed') else (current_attempts or 1)
        return paper

    @staticmethod
    def start_homework(eid, user_id):
        """学生开始做作业：无时间限制，可反复进入（受 max_attempts 限制，NULL=无限次）"""
        ExamService._check_accessible(eid, user_id, check_window=False)
        paper = ExamService.get_by_id(eid)
        if not paper:
            raise ValueError('任务不存在')

        sub = sql_repo.execute_query(
            "SELECT * FROM exam_submissions WHERE exam_id = ? AND student_id = ?",
            (eid, user_id))
        max_attempts = paper.get('max_attempts')  # None=无限
        current_attempts = (sub[0].get('attempt_count') or 1) if sub else 0

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if sub and sub[0]['status'] == 'in_progress':
            pass
        elif sub and sub[0]['status'] in ('submitted', 'reviewed'):
            if max_attempts and current_attempts >= max_attempts:
                raise ValueError(f'已达到最大作答次数（{max_attempts}次）')
            # 重新作答：清空旧答案
            sql_repo.execute_update(
                "DELETE FROM exam_answers WHERE exam_id = ? AND student_id = ?",
                (eid, user_id))
            sql_repo.execute_update(
                "UPDATE exam_submissions SET status = 'in_progress', attempt_count = COALESCE(attempt_count, 0) + 1, start_time = ? WHERE exam_id = ? AND student_id = ?",
                (now_str, eid, user_id))
        else:
            if sub:
                sql_repo.execute_update(
                    "UPDATE exam_submissions SET status = 'in_progress', start_time = ?, attempt_count = COALESCE(attempt_count, 1) WHERE exam_id = ? AND student_id = ?",
                    (now_str, eid, user_id))
            else:
                sql_repo.execute_insert(
                    """INSERT INTO exam_submissions (exam_id, student_id, status, start_time, attempt_count)
                       VALUES (?, ?, 'in_progress', ?, 1)""",
                    (eid, user_id, now_str))

        for q in paper.get('questions', []):
            q.pop('answer', None)
        return paper

    @staticmethod
    def save_answer(eid, user_id, qid, ans):
        """保存单题答案"""
        sub = sql_repo.execute_query(
            "SELECT id, start_time FROM exam_submissions WHERE exam_id = ? AND student_id = ?",
            (eid, user_id))
        if not sub:
            raise ValueError('请先开始答题')

        # 考试时长校验：超过截止时间拒绝保存
        paper = sql_repo.execute_query(
            "SELECT duration_minutes, task_type FROM exam_papers WHERE id = ?", (eid,))
        if paper and paper[0]['task_type'] == 'exam':
            started_at = sub[0]['start_time']
            if started_at:
                duration = paper[0]['duration_minutes'] or 60
                deadline = datetime.strptime(str(started_at), '%Y-%m-%d %H:%M:%S') + timedelta(minutes=duration)
                if datetime.now() > deadline:
                    raise ValueError('考试时间已结束')

        sid = sub[0]['id']

        # 判断题归一化
        qrow = sql_repo.execute_query(
            "SELECT type FROM question_bank WHERE id = ?", (qid,))
        if qrow and qrow[0]['type'] == 'judge':
            ans = normalize_judge(ans)

        eq = sql_repo.execute_query(
            "SELECT score FROM exam_questions WHERE exam_id = ? AND question_id = ?",
            (eid, qid))
        max_score = eq[0]['score'] if eq else 0

        sql_repo.execute_update(
            """INSERT INTO exam_answers (exam_id, student_id, question_id, student_answer, max_score, submitted_at)
               VALUES (?, ?, ?, ?, ?, NOW())
               ON DUPLICATE KEY UPDATE student_answer = VALUES(student_answer), submitted_at = NOW()""",
            (eid, user_id, qid, ans, max_score))

    @staticmethod
    def submit_exam(eid, user_id):
        """学生提交试卷，自动评分客观题（事务包裹）"""
        # 验证班级归属
        paper = sql_repo.execute_query(
            "SELECT id, class_id, task_type, duration_minutes FROM exam_papers WHERE id = ?", (eid,))
        if not paper:
            raise ValueError('试卷不存在')
        
        class_id = paper[0]['class_id']
        if class_id:
            membership = sql_repo.execute_query(
                "SELECT id FROM class_students WHERE class_id = ? AND student_id = ?",
                (class_id, user_id))
            if not membership:
                raise ValueError('你不在该考试的班级中')
        
        sub = sql_repo.execute_query(
            "SELECT id, start_time FROM exam_submissions WHERE exam_id = ? AND student_id = ?",
            (eid, user_id))
        if not sub:
            raise ValueError('请先开始答题')
        sub_id = sub[0]['id']

        # 考试时长校验：超过截止时间自动收卷（洛谷到时交卷机制，而非拒绝提交）
        time_expired = False
        if paper[0]['task_type'] == 'exam':
            started_at = sub[0]['start_time']
            if started_at:
                duration = paper[0]['duration_minutes'] or 60
                deadline = datetime.strptime(str(started_at), '%Y-%m-%d %H:%M:%S') + timedelta(minutes=duration)
                if datetime.now() > deadline:
                    time_expired = True

        sql_repo.begin()
        try:
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            sql_repo.execute_update(
                "UPDATE exam_submissions SET status = 'submitted', submit_time = ? WHERE id = ?",
                (now_str, sub_id))

            result = ExamService._auto_score(eid, user_id)
            result['time_expired'] = time_expired

            task_type = paper[0]['task_type']
            if task_type == 'homework':
                result['task_type'] = 'homework'
                result['can_resubmit'] = True

            sql_repo.commit()
            return result
        except Exception:
            sql_repo.rollback()
            raise

    @staticmethod
    def _auto_score(eid, user_id):
        """自动评分客观题（选择题/判断题），主观题保留 is_correct=null"""
        answers = sql_repo.execute_query(
            """SELECT ea.id, ea.question_id, ea.student_answer, ea.score,
                      qb.answer as correct_answer, qb.type, eq.score as max_q_score
               FROM exam_answers ea
               JOIN question_bank qb ON ea.question_id = qb.id
               JOIN exam_questions eq ON ea.exam_id = eq.exam_id AND ea.question_id = eq.question_id
               WHERE ea.exam_id = ? AND ea.student_id = ?""",
            (eid, user_id))
        
        auto_score = 0
        has_subjective = False
        for a in answers:
            qtype = a['type']
            if qtype in ('subjective', 'code'):
                has_subjective = True
                continue
            max_s = a['max_q_score'] or 0
            # 统一判题规则（与独立刷题一致）：judge 归一化、fill 宽松匹配
            is_correct = 1 if judge_answer(qtype, a['student_answer'], a['correct_answer']) else 0
            score = max_s if is_correct else 0
            auto_score += score
            sql_repo.execute_update(
                "UPDATE exam_answers SET is_correct = ?, score = ? WHERE id = ?",
                (is_correct, score, a['id']))

        sql_repo.execute_update(
            "UPDATE exam_submissions SET auto_score = ? WHERE exam_id = ? AND student_id = ?",
            (auto_score, eid, user_id))

        if not has_subjective:
            sql_repo.execute_update(
                "UPDATE exam_submissions SET total_score = ?, is_reviewed = 1 WHERE exam_id = ? AND student_id = ?",
                (auto_score, eid, user_id))
            ExamService._notify_result(eid, user_id, auto_score)

        return {'success': True, 'auto_score': auto_score}

    @staticmethod
    def get_my_result(eid, student_id):
        """学生查看自己的成绩和答题详情"""
        sub = sql_repo.execute_query(
            "SELECT * FROM exam_submissions WHERE exam_id = ? AND student_id = ?",
            (eid, student_id))
        if not sub or sub[0]['status'] not in ('submitted', 'reviewed'):
            return None

        answers = sql_repo.execute_query(
            """SELECT ea.*, qb.title as q_title, qb.type as q_type, qb.difficulty as q_difficulty,
                      qb.answer as q_answer, qb.options as q_options, qb.explanation as q_explanation,
                      eq.score as max_score_q, ea2.content as exam_analysis
               FROM exam_answers ea
               JOIN exam_questions eq ON ea.exam_id = eq.exam_id AND ea.question_id = eq.question_id
               JOIN question_bank qb ON ea.question_id = qb.id
               LEFT JOIN exam_analyses ea2 ON ea2.exam_id = ea.exam_id AND ea2.question_id = ea.question_id
               WHERE ea.exam_id = ? AND ea.student_id = ?
               ORDER BY eq.sort_order""",
            (eid, student_id))
        parsed_answers = []
        for a in answers:
            ad = dict(a)
            ExamService._parse_options(ad, 'q_options')
            parsed_answers.append(ad)
        return {
            'submission': dict(sub[0]),
            'answers': parsed_answers
        }

    @staticmethod
    def get_paper_meta(eid):
        """获取试卷基础信息（标题/时长/及格线/类型）"""
        rows = sql_repo.execute_query(
            "SELECT id, title, task_type, duration_minutes, pass_score FROM exam_papers WHERE id = ?",
            (eid,))
        if not rows:
            return None
        return dict(rows[0])

    # ────────────────── 教师阅卷 ──────────────────

    @staticmethod
    def get_submissions(eid):
        """教师获取考试所有提交列表（含学生信息和得分）"""
        rows = sql_repo.execute_query(
            """SELECT es.id, es.student_id, u.username, es.status, es.start_time,
                      es.submit_time, es.auto_score, es.total_score, es.is_reviewed
               FROM exam_submissions es
               JOIN users u ON es.student_id = u.id
               WHERE es.exam_id = ? AND es.status IN ('submitted', 'reviewed')
               ORDER BY es.submit_time DESC""", (eid,))
        results = []
        for r in rows:
            d = dict(r)
            for k in ('start_time', 'submit_time'):
                if k in d and d[k] is not None:
                    d[k] = str(d[k])
            results.append(d)
        return results

    @staticmethod
    def get_submission_detail(eid, sid):
        """教师查看某个学生的完整答题详情"""
        sub = sql_repo.execute_query(
            """SELECT es.*, u.username
               FROM exam_submissions es
               JOIN users u ON es.student_id = u.id
               WHERE es.id = ? AND es.exam_id = ?""", (sid, eid))
        if not sub:
            return None

        answers = sql_repo.execute_query(
            """SELECT ea.*, qb.title as q_title, qb.type as q_type,
                      qb.answer as q_answer, qb.options as q_options, qb.explanation as q_explanation,
                      eq.score as max_score_q
               FROM exam_answers ea
               JOIN exam_questions eq ON ea.exam_id = eq.exam_id AND ea.question_id = eq.question_id
               JOIN question_bank qb ON ea.question_id = qb.id
               WHERE ea.exam_id = ? AND ea.student_id = (SELECT student_id FROM exam_submissions WHERE id = ?)
               ORDER BY eq.sort_order""",
            (eid, sid))
        parsed_answers = []
        for a in answers:
            ad = dict(a)
            ExamService._parse_options(ad, 'q_options')
            parsed_answers.append(ad)
        return {
            'submission': dict(sub[0]),
            'answers': parsed_answers
        }

    @staticmethod
    def review_answer(aid, score, comment, reviewer_id):
        """主观题评分"""
        sql_repo.execute_update(
            """UPDATE exam_answers SET score = ?, is_correct = (CASE WHEN ? > 0 THEN 1 ELSE 0 END),
               review_comment = ?, review_status = 'reviewed', reviewed_by = ?, reviewed_at = NOW()
               WHERE id = ?""",
            (score, score, comment or '', reviewer_id, aid))

    @staticmethod
    def _notify_result(eid, user_id, score):
        """成绩确定后通知学生"""
        from .notification_service import notification_service
        paper = sql_repo.execute_query(
            "SELECT title FROM exam_papers WHERE id = ?", (eid,))
        title = paper[0]['title'] if paper else '考试'
        notification_service.send(
            user_id, 'exam_result', f'《{title}》成绩已发布',
            f'你的得分：{score} 分', related_id=eid, related_type='exam')

    @staticmethod
    def finalize_review(eid, sid):
        """完成阅卷：汇总所有题目得分写入 total_score"""
        total = sql_repo.execute_query(
            """SELECT COALESCE(SUM(ea.score), 0) as total
               FROM exam_answers ea
               JOIN exam_submissions es ON ea.exam_id = es.exam_id AND ea.student_id = es.student_id
               WHERE es.id = ? AND ea.exam_id = ?""",
            (sid, eid))
        total_score = total[0]['total'] if total else 0
        sql_repo.execute_update(
            "UPDATE exam_submissions SET total_score = ?, is_reviewed = 1, status = 'reviewed' WHERE id = ?",
            (total_score, sid))
        sub = sql_repo.execute_query(
            "SELECT student_id FROM exam_submissions WHERE id = ?", (sid,))
        if sub:
            ExamService._notify_result(eid, sub[0]['student_id'], total_score)
        return total_score

    @staticmethod
    def get_ranking(eid):
        """班级内考试排名（教师可见）：按分数降序、用时升序，同分同时并列"""
        rows = sql_repo.execute_query(
            """SELECT u.id AS student_id, u.username,
                      es.total_score, es.status,
                      TIMESTAMPDIFF(SECOND, es.start_time, es.submit_time) AS duration_sec,
                      es.submit_time, es.attempt_count
               FROM exam_submissions es
               JOIN users u ON es.student_id = u.id
               WHERE es.exam_id = ? AND es.status IN ('submitted', 'reviewed')
               ORDER BY es.total_score DESC, duration_sec ASC, es.submit_time ASC""",
            (eid,))
        result = []
        prev_key = None
        rank = 0
        for i, r in enumerate(rows, 1):
            key = (r['total_score'], r['duration_sec'])
            rank = i if key != prev_key else rank
            result.append({
                'rank': rank,
                'student_id': r['student_id'],
                'username': r['username'],
                'total_score': r['total_score'],
                'status': r['status'],
                'duration_sec': r['duration_sec'],
                'submit_time': str(r['submit_time']) if r['submit_time'] else '',
                'attempt_count': r['attempt_count'],
            })
            prev_key = key
        return result

    @staticmethod
    def set_analysis(eid, question_id, content, created_by):
        """教师发布/更新某题标准解析（upsert）"""
        content = (content or '').strip()
        if not content:
            raise ValueError('解析内容不能为空')
        exists = sql_repo.execute_query(
            "SELECT id FROM exam_analyses WHERE exam_id = ? AND question_id = ?",
            (eid, question_id))
        if exists:
            sql_repo.execute_update(
                "UPDATE exam_analyses SET content = ?, is_pinned = 1, created_by = ? "
                "WHERE exam_id = ? AND question_id = ?",
                (content, created_by, eid, question_id))
        else:
            sql_repo.execute_insert(
                """INSERT INTO exam_analyses (exam_id, question_id, content, is_pinned, created_by)
                   VALUES (?, ?, ?, 1, ?)""",
                (eid, question_id, content, created_by))
        return {'success': True}

    @staticmethod
    def delete_analysis(eid, question_id):
        """删除某题标准解析"""
        sql_repo.execute_update(
            "DELETE FROM exam_analyses WHERE exam_id = ? AND question_id = ?",
            (eid, question_id))
        return {'success': True}

    @staticmethod
    def get_exam_analysis(eid, student_id):
        """生成考试分析报告（含每题正确率、知识点、难度）"""
        sub = sql_repo.execute_query(
            "SELECT * FROM exam_submissions WHERE exam_id = ? AND student_id = ?",
            (eid, student_id))
        if not sub or sub[0]['status'] not in ('submitted', 'reviewed'):
            return None
        sub = dict(sub[0])

        paper = sql_repo.execute_query(
            """SELECT title, total_score, pass_score, duration_minutes,
                      start_time, end_time
               FROM exam_papers WHERE id = ?""", (eid,))
        paper = dict(paper[0]) if paper else {}

        # 每题详情（含知识点、难度、学生答案）
        answers = sql_repo.execute_query(
            """SELECT ea.id, ea.question_id, ea.student_answer, ea.is_correct, ea.score,
                      eq.score as max_score_q, eq.sort_order,
                      qb.title as q_title, qb.type as q_type, qb.difficulty,
                      qb.knowledge_point_name, qb.knowledge_point_id
               FROM exam_answers ea
               JOIN exam_questions eq ON ea.exam_id = eq.exam_id AND ea.question_id = eq.question_id
               JOIN question_bank qb ON ea.question_id = qb.id
               WHERE ea.exam_id = ? AND ea.student_id = ?
               ORDER BY eq.sort_order""",
            (eid, student_id))

        # 每题全班正确率
        q_ids = [a['question_id'] for a in answers]
        q_correct_rates = {}
        if q_ids:
            placeholders = ','.join('?' * len(q_ids))
            cr_rows = sql_repo.execute_query(
                f"""SELECT question_id,
                           COUNT(*) as total_answers,
                           SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_count
                    FROM exam_answers
                    WHERE exam_id = ? AND question_id IN ({placeholders})
                    GROUP BY question_id""",
                [eid] + q_ids)
            for cr in cr_rows:
                total = cr['total_answers'] or 1
                q_correct_rates[cr['question_id']] = {
                    'total': total,
                    'correct': cr['correct_count'] or 0,
                    'rate': round((cr['correct_count'] or 0) / total * 100, 1)
                }

        # 按题型统计
        type_stats = {}
        for a in answers:
            qtype = a['q_type'] or 'unknown'
            if qtype not in type_stats:
                type_stats[qtype] = {'count': 0, 'correct': 0, 'score': 0, 'max_score': 0}
            s = type_stats[qtype]
            s['count'] += 1
            s['score'] += (a['score'] or 0)
            s['max_score'] += (a['max_score_q'] or 0)
            if a['is_correct'] == 1:
                s['correct'] += 1

        # 按知识点统计
        kp_stats = {}
        for a in answers:
            kp = a.get('knowledge_point_name') or '未分类'
            if kp not in kp_stats:
                kp_stats[kp] = {'count': 0, 'correct': 0, 'score': 0, 'max_score': 0}
            s = kp_stats[kp]
            s['count'] += 1
            s['score'] += (a['score'] or 0)
            s['max_score'] += (a['max_score_q'] or 0)
            if a['is_correct'] == 1:
                s['correct'] += 1

        # 班级统计
        class_stats = sql_repo.execute_query(
            """SELECT COUNT(*) as submit_count,
                      AVG(es.total_score) as avg_score,
                      MAX(es.total_score) as max_score,
                      MIN(es.total_score) as min_score
               FROM exam_submissions es
               JOIN users u ON es.student_id = u.id
               JOIN class_students cs ON u.id = cs.student_id
               JOIN exam_papers ep ON es.exam_id = ep.id AND ep.class_id = cs.class_id
               WHERE es.exam_id = ? AND es.status IN ('submitted', 'reviewed')""",
            (eid,))
        class_info = dict(class_stats[0]) if class_stats else {}

        # 用时分析
        time_taken = None
        if sub.get('start_time') and sub.get('submit_time'):
            delta = sub['submit_time'] - sub['start_time']
            time_taken = int(delta.total_seconds() / 60)

        # 每题分析数据
        per_question = []
        DIFFICULTY_LABELS = {1: '基础', 2: '简单', 3: '中等', 4: '较难', 5: '困难'}
        for a in answers:
            qid = a['question_id']
            cr = q_correct_rates.get(qid, {})
            per_question.append({
                'question_id': qid,
                'sort_order': a['sort_order'],
                'title': a['q_title'],
                'type': a['q_type'],
                'difficulty': a.get('difficulty'),
                'difficulty_label': DIFFICULTY_LABELS.get(a.get('difficulty'), '未知'),
                'knowledge_point': a.get('knowledge_point_name') or '未分类',
                'knowledge_point_id': a.get('knowledge_point_id'),
                'your_answer': a['student_answer'],
                'your_score': a['score'] or 0,
                'max_score': a['max_score_q'] or 0,
                'is_correct': a['is_correct'],
                'class_correct_rate': cr.get('rate'),
                'class_total': cr.get('total', 0),
                'class_correct': cr.get('correct', 0),
            })

        return {
            'exam_title': paper.get('title', ''),
            'total_score': sub.get('total_score'),
            'auto_score': sub.get('auto_score'),
            'review_score': sub.get('review_score'),
            'pass_score': paper.get('pass_score', 60),
            'total_max_score': paper.get('total_score', 100),
            'duration_minutes': paper.get('duration_minutes'),
            'time_taken_minutes': time_taken,
            'is_reviewed': sub.get('is_reviewed'),
            'submitted_at': str(sub.get('submit_time', '')),
            'type_breakdown': {t: type_stats[t] for t in sorted(type_stats.keys())},
            'kp_breakdown': dict(sorted(kp_stats.items(), key=lambda x: x[1]['score'] / max(x[1]['max_score'], 1))),
            'class_avg': round(class_info.get('avg_score', 0) or 0, 1),
            'class_max': class_info.get('max_score'),
            'class_min': class_info.get('min_score'),
            'class_count': class_info.get('submit_count'),
            'passed': (sub.get('total_score') or 0) >= (paper.get('pass_score', 60)),
            'per_question': per_question,
        }

    @staticmethod
    def get_wrong_answers(user_id, page=1, page_size=20):
        """获取用户错题列表，按知识点分组"""
        import math as _math
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        # 总数（与主查询 JOIN 条件一致，避免计数偏差）
        count_rows = sql_repo.execute_query(
            """SELECT COUNT(*) AS c
               FROM exam_answers ea
               JOIN question_bank qb ON ea.question_id = qb.id
               JOIN exam_questions eq ON ea.exam_id = eq.exam_id AND ea.question_id = eq.question_id
               JOIN exam_papers ep ON ea.exam_id = ep.id
               JOIN exam_submissions es ON ea.exam_id = es.exam_id AND ea.student_id = es.student_id
               WHERE ea.student_id = ? AND ea.is_correct = 0
                 AND (ea.redo_status IS NULL OR ea.redo_status != 'redo_correct')""",
            (user_id,))
        total = count_rows[0]['c'] if count_rows else 0
        # 当前页数据
        rows = sql_repo.execute_query(
            """SELECT ea.id, ea.exam_id, ea.question_id, ea.student_answer,
                      ea.score as got_score, eq.score as max_score,
                      ea.redo_status,
                      qb.title as q_title, qb.type as q_type, qb.answer as q_answer,
                      qb.options as q_options, qb.explanation as q_analysis,
                      qb.knowledge_point_id, qb.knowledge_point_name,
                      ep.title as exam_title,
                      COALESCE(es.submit_time, es.start_time) as submitted_at
               FROM exam_answers ea
               JOIN question_bank qb ON ea.question_id = qb.id
               JOIN exam_questions eq ON ea.exam_id = eq.exam_id AND ea.question_id = eq.question_id
               JOIN exam_papers ep ON ea.exam_id = ep.id
               JOIN exam_submissions es ON ea.exam_id = es.exam_id AND ea.student_id = es.student_id
               WHERE ea.student_id = ? AND ea.is_correct = 0
                 AND (ea.redo_status IS NULL OR ea.redo_status != 'redo_correct')
               ORDER BY es.submit_time DESC
               LIMIT ? OFFSET ?""",
            (user_id, page_size, (page - 1) * page_size))
        # 解析 options JSON（沿用原逻辑）
        for r in rows:
            if r.get('q_options') and isinstance(r['q_options'], str):
                try:
                    r['q_options'] = json.loads(r['q_options'])
                except Exception:
                    pass
        groups = {}
        for r in rows:
            kp_name = r.get('knowledge_point_name') or '未分类'
            if kp_name not in groups:
                groups[kp_name] = []
            groups[kp_name].append(dict(r))
        return {
            'items': [dict(r) for r in rows],
            'groups': groups,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': _math.ceil(total / page_size) if total else 0,
        }

    @staticmethod
    def delete_wrong_answer(aid, user_id):
        """删除用户的错题记录"""
        sql_repo.execute_update(
            "DELETE FROM exam_answers WHERE id = ? AND student_id = ?",
            (aid, user_id))

    @staticmethod
    def redo_wrong_answer(user_id, aid, is_correct):
        """记录错题重做结果：重做正确 → 标记已掌握（移出错题本），否则保留待重做"""
        rows = sql_repo.execute_query(
            "SELECT id FROM exam_answers WHERE id = ? AND student_id = ?",
            (aid, user_id))
        if not rows:
            return False, '错题记录不存在'
        status = 'redo_correct' if is_correct else 'redo_pending'
        sql_repo.execute_update(
            "UPDATE exam_answers SET redo_status = ? WHERE id = ?",
            (status, aid))
        return True, '已记录'

    # ── 批量评分 ──

    @staticmethod
    def batch_review(eid, reviews, reviewer_id):
        """批量评分：reviews=[{answer_id, score, comment}, ...]"""
        count = 0
        for rv in reviews:
            aid = rv.get('answer_id')
            score = rv.get('score', 0)
            comment = rv.get('comment', '')
            if not aid:
                continue
            sql_repo.execute_update(
                """UPDATE exam_answers
                   SET score = ?, is_correct = (CASE WHEN ? > 0 THEN 1 ELSE 0 END),
                       review_comment = ?, review_status = 'reviewed',
                       reviewed_by = ?, reviewed_at = NOW()
                   WHERE id = ?""",
                (score, score, comment or '', reviewer_id, aid))
            count += 1
        return {'reviewed_count': count}

    @staticmethod
    def set_review_draft(eid, sid, is_draft=1):
        """设置批阅是否暂存（review_draft=1表示未完成批阅）"""
        sql_repo.execute_update(
            "UPDATE exam_submissions SET review_draft = ? WHERE exam_id = ? AND student_id = ?",
            (is_draft, eid, sid))
        return {'success': True}

    @staticmethod
    def export_results(eid):
        """导出考试成绩为结构化数据（供生成 Excel 使用）"""
        paper = sql_repo.execute_query(
            "SELECT title, total_score, pass_score FROM exam_papers WHERE id = ?", (eid,))
        if not paper:
            return None
        paper = dict(paper[0])

        subs = sql_repo.execute_query(
            """SELECT es.*, u.username, u.email
               FROM exam_submissions es
               JOIN users u ON es.student_id = u.id
               WHERE es.exam_id = ? AND es.status IN ('submitted', 'reviewed')
               ORDER BY u.username""",
            (eid,))

        questions = sql_repo.execute_query(
            """SELECT eq.question_id, qb.title as q_title, eq.score as max_score, eq.sort_order
               FROM exam_questions eq
               JOIN question_bank qb ON eq.question_id = qb.id
               WHERE eq.exam_id = ?
               ORDER BY eq.sort_order""",
            (eid,))

        results = []
        for sub in subs:
            s = dict(sub)
            answers = sql_repo.execute_query(
                "SELECT question_id, score FROM exam_answers WHERE exam_id = ? AND student_id = ?",
                (eid, s['student_id']))
            s['scores'] = {a['question_id']: a['score'] for a in answers}
            results.append(s)

        return {
            'exam_title': paper['title'],
            'total_score': paper['total_score'],
            'pass_score': paper['pass_score'],
            'questions': [dict(q) for q in questions],
            'results': results
        }


exam_service = ExamService()
