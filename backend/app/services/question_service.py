# -*- coding: utf-8 -*-
"""题库管理服务"""
import json
import re
import pymysql
from ..repositories.sql_repo import sql_repo


# 判断题答案：对 / 错 的常见写法归一化
_JUDGE_POSITIVE = {'对', '√', '✓', 'true', 't', 'yes', 'y', '1', '正确', '是'}
_JUDGE_NEGATIVE = {'错', '×', '✗', 'false', 'f', 'no', 'n', '0', '错误', '否'}


def normalize_judge(value):
    """将判断题答案归一化为 '对' 或 '错'，无法识别则原文返回"""
    v = (value or '').strip().lower()
    if v in _JUDGE_POSITIVE:
        return '对'
    if v in _JUDGE_NEGATIVE:
        return '错'
    return (value or '').strip()


def judge_answer(qtype, user_ans, correct):
    """统一判题规则：choice/judge 精确匹配（judge 先归一化），fill 宽松匹配，主观题不判对错返回 None。

    返回 1=正确, 0=错误, None=不自动判分（主观/编程题）。
    """
    if qtype in ('subjective', 'code'):
        return None
    if qtype == 'judge':
        user_ans = normalize_judge(user_ans)
        correct = normalize_judge(correct)
    u = (user_ans or '').strip()
    c = (correct or '').strip()
    if qtype == 'fill':
        def norm(s):
            return re.sub(r'[\s，。；、,.!！?？、()（）]', '', s).lower()
        return 1 if norm(u) == norm(c) else 0
    return 1 if u == c else 0


class QuestionService:

    @staticmethod
    def calc_difficulty(kp_count):
        """根据关联知识点数量自动计算难度: log2(kp_count)+1，上限 12"""
        import math
        if kp_count <= 0:
            return 1
        return min(int(math.log2(kp_count)) + 1, 12)

    @staticmethod
    def get_kp_count(question_id):
        """查询某题关联的知识点数量"""
        rows = sql_repo.execute_query(
            "SELECT COUNT(*) as cnt FROM question_kp_map WHERE question_id = ?",
            (question_id,))
        cnt = rows[0]['cnt'] if rows else 0
        # 兼容：如果没有 map 记录，检查旧 knowledge_point_id 字段
        if cnt == 0:
            rows2 = sql_repo.execute_query(
                "SELECT knowledge_point_id FROM question_bank WHERE id = ?",
                (question_id,))
            if rows2 and rows2[0].get('knowledge_point_id'):
                cnt = 1
        return max(cnt, 1)

    @staticmethod
    def _title_exists(title):
        """检查同 title 题目是否已存在"""
        rows = sql_repo.execute_query(
            "SELECT id FROM question_bank WHERE title = ?", (title.strip(),))
        return len(rows) > 0 if rows else False

    @staticmethod
    def create(title, qtype, answer, options=None, is_multi=False,
               category='', explanation='', knowledge_point_id='', knowledge_point_name='', topic='',
               code_template=None, created_by=1, knowledge_point_ids=None, status='approved'):
        if not title or not title.strip():
            raise ValueError('题目不能为空')
        if qtype not in ('choice', 'judge', 'fill', 'subjective', 'code'):
            raise ValueError('无效的题目类型')

        if qtype in ('choice', 'judge', 'fill', 'code'):
            if not answer or not answer.strip():
                raise ValueError('答案不能为空')

        if qtype == 'choice' and (not options or len(options) < 2):
            raise ValueError('选择题至少需要2个选项')

        if qtype == 'code' and (not code_template or not code_template.strip()):
            raise ValueError('编程题必须提供代码模板')

        # 合并 knowledge_point_ids：优先用新参数，否则从 knowledge_point_id 推导
        kp_ids = []
        if knowledge_point_ids and isinstance(knowledge_point_ids, list):
            kp_ids = [kp for kp in knowledge_point_ids if kp]
        elif knowledge_point_id and knowledge_point_id.strip():
            kp_ids = [knowledge_point_id.strip()]

        # 难度 = log2(知识点数)+1，上限 12
        kp_count = max(len(kp_ids), 1)
        difficulty = QuestionService.calc_difficulty(kp_count)

        options_json = json.dumps(options, ensure_ascii=False) if options else None

        qid = sql_repo.execute_insert(
            """INSERT INTO question_bank (title, type, difficulty, options, answer, is_multi,
               category, explanation, knowledge_point_id, knowledge_point_name, topic, created_by, code_template, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title.strip(), qtype, difficulty, options_json, answer.strip() if answer else '',
             int(is_multi), category, explanation or '',
             kp_ids[0] if kp_ids else '', knowledge_point_name or '', topic or '', created_by,
             code_template or '', status)
        )

        # 写 question_kp_map
        for kp_id in kp_ids:
            sql_repo.execute_insert(
                "INSERT OR IGNORE INTO question_kp_map (question_id, knowledge_point_id) VALUES (?, ?)",
                (qid, kp_id))

        return {'id': qid, 'title': title.strip(), 'type': qtype, 'difficulty': difficulty}

    @staticmethod
    def update(qid, **kwargs):
        existing = sql_repo.execute_query("SELECT * FROM question_bank WHERE id = ?", (qid,))
        if not existing:
            raise ValueError('题目不存在')

        fields = []
        params = []
        for k, v in kwargs.items():
            if k in ('title', 'type', 'category', 'explanation', 'answer',
                     'knowledge_point_id', 'knowledge_point_name', 'topic', 'code_template'):
                fields.append(f"{k} = ?")
                params.append(v if v else '')
            elif k == 'options':
                fields.append("options = ?")
                params.append(json.dumps(v, ensure_ascii=False))
            elif k == 'is_multi':
                fields.append("is_multi = ?")
                params.append(int(v))

        if not fields:
            return True

        fields.append("updated_at = datetime('now','localtime')")
        params.append(qid)
        sql_repo.execute_update(
            f"UPDATE question_bank SET {', '.join(fields)} WHERE id = ?",
            params
        )
        return True

    @staticmethod
    def _cascade_delete(ids):
        """删除题目时级联清理相关引用，避免孤儿数据"""
        if not ids:
            return
        marks = ','.join('?' * len(ids))
        for table in ('exam_questions', 'exam_answers', 'exam_analyses',
                      'practice_attempts', 'question_kp_map', 'question_favorites'):
            sql_repo.execute_update(
                f"DELETE FROM {table} WHERE question_id IN ({marks})", ids)

    @staticmethod
    def delete(qid):
        QuestionService._cascade_delete([qid])
        sql_repo.execute_update("DELETE FROM question_bank WHERE id = ?", (qid,))

    @staticmethod
    def batch_delete(ids):
        QuestionService._cascade_delete(ids)
        placeholders = ','.join('?' * len(ids))
        sql_repo.execute_update(f"DELETE FROM question_bank WHERE id IN ({placeholders})", ids)

    @staticmethod
    def set_status(qid, status):
        """设置题目状态"""
        rows = sql_repo.execute_update(
            "UPDATE question_bank SET status = ? WHERE id = ?",
            (status, qid)
        )
        return rows > 0

    @staticmethod
    def get_by_id(qid):
        rows = sql_repo.execute_query("SELECT * FROM question_bank WHERE id = ?", (qid,))
        if not rows:
            return None
        return QuestionService._format(rows[0])

    @staticmethod
    def query(page=1, page_size=20, qtype='',
              category='', topic='', keyword='', difficulty=None, status=None,
              difficulty_min=None, difficulty_max=None):
        conditions = []
        params = []

        if qtype:
            conditions.append("type = ?")
            params.append(qtype)
        if category:
            conditions.append("category = ?")
            params.append(category)
        if topic:
            conditions.append("topic = ?")
            params.append(topic)
        if difficulty is not None:
            conditions.append("difficulty = ?")
            params.append(difficulty)
        if difficulty_min is not None:
            conditions.append("difficulty >= ?")
            params.append(difficulty_min)
        if difficulty_max is not None:
            conditions.append("difficulty <= ?")
            params.append(difficulty_max)
        if keyword:
            conditions.append("(title LIKE ? OR explanation LIKE ?)")
            params.extend([f'%{keyword}%', f'%{keyword}%'])

        if status is not None:
            conditions.append("status = ?")
            params.append(status)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        count_row = sql_repo.execute_query(
            f"SELECT COUNT(*) as cnt FROM question_bank {where}", params)
        total = count_row[0]['cnt'] if count_row else 0

        offset = (page - 1) * page_size
        rows = sql_repo.execute_query(
            f"SELECT * FROM question_bank {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [page_size, offset]
        )

        # 批量统计每题通过率（基于 exam_answers 的实际作答）
        qids = [r['id'] for r in rows]
        pass_rates = {}
        if qids:
            marks = ','.join(['?'] * len(qids))
            pr_rows = sql_repo.execute_query(
                f"SELECT question_id, COUNT(*) AS total, SUM(is_correct = 1) AS correct "
                f"FROM exam_answers WHERE question_id IN ({marks}) GROUP BY question_id",
                qids)
            for pr in pr_rows:
                total = pr['total'] or 0
                if total > 0:
                    pass_rates[pr['question_id']] = round((pr['correct'] or 0) * 100 / total, 1)

        items = [QuestionService._format(r) for r in rows]
        for it in items:
            it['pass_rate'] = pass_rates.get(it['id'])

        return {
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': max(1, (total + page_size - 1) // page_size)
        }

    @staticmethod
    def get_categories():
        # 从专用分类表 + question_bank 中取所有分类（去重）
        cats = set()
        rows = sql_repo.execute_query("SELECT name FROM question_categories ORDER BY name")
        for r in rows:
            cats.add(r['name'])
        rows2 = sql_repo.execute_query(
            "SELECT DISTINCT category FROM question_bank WHERE category != '' ORDER BY category")
        for r in rows2:
            cats.add(r['category'])
        return sorted(cats)

    @staticmethod
    def get_topics():
        """获取所有题目知识点 topic（去重）"""
        rows = sql_repo.execute_query(
            "SELECT DISTINCT topic FROM question_bank WHERE topic IS NOT NULL AND topic != '' ORDER BY topic")
        return [r['topic'] for r in rows]

    # ── 题目收藏 ──

    @staticmethod
    def add_favorite(user_id, question_id):
        """收藏题目（幂等：重复收藏不报错）"""
        sql_repo.execute_insert(
            "INSERT OR IGNORE INTO question_favorites (user_id, question_id) VALUES (?, ?)",
            (user_id, question_id))

    @staticmethod
    def remove_favorite(user_id, question_id):
        """取消收藏"""
        sql_repo.execute_update(
            "DELETE FROM question_favorites WHERE user_id = ? AND question_id = ?",
            (user_id, question_id))

    @staticmethod
    def get_favorite_ids(user_id, question_ids):
        """批量查询题目是否被当前用户收藏，返回 {question_id: True}"""
        if not question_ids:
            return {}
        marks = ','.join(['?'] * len(question_ids))
        rows = sql_repo.execute_query(
            f"SELECT question_id FROM question_favorites "
            f"WHERE user_id = ? AND question_id IN ({marks})",
            (user_id, *question_ids))
        return {r['question_id']: True for r in rows}

    @staticmethod
    def query_favorites(user_id, page=1, page_size=20):
        """个人收藏夹：分页返回收藏的题目"""
        count_row = sql_repo.execute_query(
            "SELECT COUNT(*) as cnt FROM question_favorites WHERE user_id = ?",
            (user_id,))
        total = count_row[0]['cnt'] if count_row else 0

        offset = (page - 1) * page_size
        rows = sql_repo.execute_query(
            """SELECT qb.* FROM question_favorites f
               JOIN question_bank qb ON f.question_id = qb.id
               WHERE f.user_id = ? AND qb.status = 'approved'
               ORDER BY f.created_at DESC, f.id DESC LIMIT ? OFFSET ?""",
            (user_id, page_size, offset))
        items = [QuestionService._format(r) for r in rows]
        for it in items:
            it['is_favorite'] = True
        return {
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': max(1, (total + page_size - 1) // page_size)
        }

    @staticmethod
    def get_all_for_export(ids=None):
        if ids:
            placeholders = ','.join('?' * len(ids))
            rows = sql_repo.execute_query(
                f"SELECT * FROM question_bank WHERE id IN ({placeholders}) ORDER BY id", ids)
        else:
            rows = sql_repo.execute_query("SELECT * FROM question_bank ORDER BY id")
        return [QuestionService._format(r) for r in rows]

    @staticmethod
    def _format(row):
        r = dict(row)
        if isinstance(r.get('options'), str):
            try:
                r['options'] = json.loads(r['options'])
            except Exception:
                r['options'] = []
        if r.get('options') is None:
            r['options'] = []
        if r.get('code_template') is None:
            r['code_template'] = ''
        r['is_multi'] = bool(r.get('is_multi', 0))
        return r

    # ── 导入导出 ──

    @staticmethod
    def export_json(ids=None):
        questions = QuestionService.get_all_for_export(ids)
        return questions

    @staticmethod
    def export_csv(ids=None):
        """导出为 CSV 文本"""
        import io
        import csv as _csv
        questions = QuestionService.get_all_for_export(ids)
        output = io.StringIO()
        w = _csv.writer(output)
        w.writerow(['type', 'title', 'category', 'difficulty', 'is_multi', 'options', 'answer', 'explanation'])
        for q in questions:
            opts = '|'.join(q.get('options', [])) if isinstance(q.get('options'), list) else ''
            w.writerow([
                q.get('type', ''), q.get('title', ''), q.get('category', ''),
                q.get('difficulty', ''), '是' if q.get('is_multi') else '否',
                opts, q.get('answer', ''), q.get('explanation', '')
            ])
        return output.getvalue()

    @staticmethod
    def import_json(data, created_by=1):
        """JSON 数组导入题目 [{title, type, category, difficulty, ...}]"""
        if isinstance(data, dict):
            data = data.get('questions', data.get('items', [data]))
        if not isinstance(data, list):
            raise ValueError('数据格式错误，需要 JSON 数组')

        sql_repo.begin_transaction()
        try:
            success = 0
            skipped = 0
            errors = []
            for i, item in enumerate(data):
                try:
                    title = item.get('title', '').strip()
                    if QuestionService._title_exists(title):
                        skipped += 1
                        continue
                    options = item.get('options', [])
                    if isinstance(options, str):
                        options = [o.strip() for o in options.replace('|', ',').replace('，', ',').split(',') if o.strip()]
                    QuestionService.create(
                        title=item.get('title', ''),
                        qtype=item.get('type', 'choice'),
                        answer=str(item.get('answer', '')),
                        options=options,
                        is_multi=bool(item.get('is_multi', False)),
                        category=item.get('category', ''),
                        explanation=item.get('explanation', ''),
                        topic=item.get('topic', ''),
                        code_template=item.get('code_template', ''),
                        created_by=created_by
                    )
                    success += 1
                except Exception as e:
                    errors.append({'row': i + 1, 'message': str(e)})
            if errors:
                sql_repo.rollback_transaction()
            else:
                sql_repo.commit_transaction()
            return {'success_count': success, 'skipped_count': skipped, 'error_count': len(errors), 'errors': errors}
        except Exception:
            sql_repo.rollback_transaction()
            raise

    @staticmethod
    def import_csv(content, created_by=1):
        """CSV 文本导入题目"""
        import io
        import csv as _csv
        reader = _csv.DictReader(io.StringIO(content))
        rows = list(reader)
        if not rows:
            raise ValueError('CSV 内容为空')

        sql_repo.begin_transaction()
        try:
            success = 0
            skipped = 0
            errors = []
            for i, row in enumerate(rows):
                try:
                    title = row.get('title', row.get('题目', '')).strip()
                    if QuestionService._title_exists(title):
                        skipped += 1
                        continue
                    qtype = row.get('type', row.get('类型', 'choice')).strip().lower()
                    # 中英文类型映射
                    type_map = {'选择': 'choice', '判断': 'judge', '填空': 'fill', '主观': 'subjective', '编程': 'code'}
                    if qtype in type_map:
                        qtype = type_map[qtype]
                    if qtype not in ('choice', 'judge', 'fill', 'subjective', 'code'):
                        qtype = 'choice'

                    options = []
                    if qtype == 'choice':
                        opts_str = row.get('options', row.get('选项', ''))
                        if not opts_str:
                            opts_list = [row.get(f'选项{k}', '') for k in ['A', 'B', 'C', 'D', 'E', 'F']]
                            opts_str = '|'.join([o for o in opts_list if o])
                        if opts_str:
                            options = [o.strip() for o in opts_str.replace('|', ',').replace('，', ',').split(',') if o.strip()]

                    QuestionService.create(
                        title=title,
                        qtype=qtype,
                        answer=row.get('answer', row.get('答案', '')).strip(),
                        options=options,
                        is_multi=row.get('is_multi', row.get('是否多选', '否')).strip() in ('是', '1', 'true', 'yes'),
                        category=row.get('category', row.get('分类', '')),
                        explanation=row.get('explanation', row.get('解析', '')),
                        topic=row.get('topic', row.get('知识点', '')),
                        code_template=row.get('code_template', row.get('代码模板', '')),
                        created_by=created_by
                    )
                    success += 1
                except Exception as e:
                    errors.append({'row': i + 2, 'message': str(e)})
            if errors:
                sql_repo.rollback_transaction()
            else:
                sql_repo.commit_transaction()
            return {'success_count': success, 'skipped_count': skipped, 'error_count': len(errors), 'errors': errors}
        except Exception:
            sql_repo.rollback_transaction()
            raise


    @staticmethod
    def import_excel(file_stream, created_by=1):
        """从 Excel 文件流导入题目"""
        from ..utils.excel_helper import ExcelHelper
        import io
        # 兼容 Flask FileStorage：先读取为 BytesIO
        import io
        if hasattr(file_stream, 'read'):
            data = file_stream.read()
            file_stream = io.BytesIO(data)
        result = ExcelHelper.parse_excel(file_stream, created_by)
        questions = result.get('questions', [])
        errors = result.get('errors', [])

        sql_repo.begin_transaction()
        try:
            success = 0
            skipped = 0
            for q in questions:
                try:
                    kwargs = dict(q)
                    if 'type' in kwargs:
                        kwargs['qtype'] = kwargs.pop('type')
                    if QuestionService._title_exists(kwargs.get('title', '')):
                        skipped += 1
                        continue
                    QuestionService.create(**kwargs)
                    success += 1
                except Exception as e:
                    errors.append({'row': 0, 'message': str(e)})

            if errors:
                # 任一失败即整体回滚；回滚后不得谎报成功数
                sql_repo.rollback_transaction()
                return {
                    'success_count': 0,
                    'skipped_count': 0,
                    'error_count': len(errors),
                    'total_rows': result.get('total_rows', 0),
                    'errors': errors
                }
            sql_repo.commit_transaction()
            return {
                'success_count': success,
                'skipped_count': skipped,
                'error_count': len(errors),
                'total_rows': result.get('total_rows', 0),
                'errors': errors
            }
        except Exception:
            sql_repo.rollback_transaction()
            raise

    @staticmethod
    def export_excel(ids=None):
        """导出为 Excel 二进制"""
        questions = QuestionService.get_all_for_export(ids)
        from ..utils.excel_helper import ExcelHelper
        return ExcelHelper.generate_excel(questions)

    @staticmethod
    def import_word(file_stream, created_by=1):
        """从 .docx 文件导入题目"""
        import io
        from docx import Document

        doc = Document(io.BytesIO(file_stream.read()))
        tables = doc.tables

        if not tables:
            return {'success_count': 0, 'error_count': 0, 'errors': [{'row': 0, 'message': 'Word文档中没有找到表格'}]}

        sql_repo.begin_transaction()
        try:
            success = 0
            skipped = 0
            errors = []
            row_num = 0

            for table in tables:
                for row in table.rows[1:]:  # 跳过表头
                    row_num += 1
                    cells = [cell.text.strip() for cell in row.cells]
                    if len(cells) < 8:
                        errors.append({'row': row_num, 'message': f'列数不足(需要至少8列，实际{len(cells)}列)'})
                        continue

                    title = cells[0]
                    qtype_map = {'选择题': 'choice', '判断题': 'judge', '填空题': 'fill', '主观题': 'subjective'}
                    qtype = qtype_map.get(cells[1], cells[1])

                    is_multi = cells[4] in ('是', 'true', 'True', '1', 'yes')

                    options = [cells[5], cells[6], cells[7], cells[8]] if len(cells) > 8 else [cells[5], cells[6], cells[7]]
                    options = [o for o in options if o]

                    answer = cells[8] if len(cells) > 8 else cells[7] if len(cells) > 7 else ''
                    explanation = cells[9] if len(cells) > 9 else ''

                    try:
                        if QuestionService._title_exists(title):
                            skipped += 1
                            continue
                        QuestionService.create(
                            title=title, qtype=qtype,
                            answer=answer, options=options if qtype == 'choice' else None,
                            is_multi=is_multi, category=cells[2], explanation=explanation,
                            created_by=created_by
                        )
                        success += 1
                    except Exception as e:
                        errors.append({'row': row_num, 'message': str(e)})

            if errors:
                # 任一失败即整体回滚；回滚后不得谎报成功数
                sql_repo.rollback_transaction()
                return {
                    'success_count': 0,
                    'skipped_count': 0,
                    'error_count': len(errors),
                    'errors': errors,
                    'total_rows': row_num
                }
            sql_repo.commit_transaction()
            return {
                'success_count': success,
                'skipped_count': skipped,
                'error_count': len(errors),
                'errors': errors,
                'total_rows': row_num
            }
        except Exception:
            sql_repo.rollback_transaction()
            raise

    @staticmethod
    def export_word(ids=None):
        """导出为 Word 试卷"""
        questions = QuestionService.get_all_for_export(ids)
        from ..utils.excel_helper import WordHelper
        return WordHelper.generate_exam_paper(questions, title='导出的试卷')

    @staticmethod
    def add_category(name):
        """添加分类，持久化到 question_categories 表"""
        try:
            sql_repo.execute_update(
                "INSERT INTO question_categories (name) VALUES (?)", (name,))
        except pymysql.err.IntegrityError:
            raise ValueError(f'分类"{name}"已存在')
        except Exception as e:
            raise ValueError(f'添加分类失败: {e}')
        return {'name': name}

    @staticmethod
    def delete_category(name):
        """删除分类（仅当没有题目使用该分类时可删）"""
        count = sql_repo.execute_query(
            "SELECT COUNT(*) as cnt FROM question_bank WHERE category = ? AND status = 'approved'", (name,)
        )
        if count and count[0]['cnt'] > 0:
            raise ValueError(f'分类"{name}"下还有 {count[0]["cnt"]} 道题目，无法删除')
        sql_repo.execute_update("DELETE FROM question_categories WHERE name = ?", (name,))
        return True


question_service = QuestionService()
