# -*- coding: utf-8 -*-
"""AI 练习路由 — 普通用户自助出题练习"""
import time
import uuid
import json
import re
import logging
from flask import Blueprint, request, jsonify, current_app

from ..utils.auth import require_auth
from ..utils.rate_limit import rate_limit
from ..services.llm_service import LLMService, QuestionGenerator
from ..services.question_service import QuestionService
from ..services.task_manager import submit as submit_task
from ..repositories.graph_repo import graph_repo
from ..repositories.sql_repo import sql_repo

ai_practice_bp = Blueprint('ai_practice', __name__)
llm_logger = logging.getLogger('llm')


def _calc_difficulty(kp_count: int) -> int:
    import math
    if kp_count <= 0:
        return 1
    return min(int(math.log2(kp_count)) + 1, 12)


# ═══════════════════════════════════════════════
#  生成练习题目
# ═══════════════════════════════════════════════

@ai_practice_bp.route('/practice/generate', methods=['POST'])
@require_auth
@rate_limit(max_requests=5, window_seconds=60)
def generate_practice():
    """普通用户选知识点 → LLM 出题 → 入库 → 返回题目（不含答案）"""
    user = request.current_user
    if user.get('role') == 'admin':
        return jsonify({'code': 403, 'success': False, 'data': None,
                        'message': 'AI 练习仅限学生使用，管理员请用题库管理'}), 403

    data = request.get_json(force=True) or {}
    kp_ids = data.get('knowledge_point_ids', [])
    total = data.get('total_questions', 5)
    qtypes = data.get('question_types', None)

    if not kp_ids or not isinstance(kp_ids, list):
        return jsonify({'code': 400, 'success': False, 'data': None,
                        'message': '请选择至少一个知识点'}), 400

    if len(kp_ids) > 30:
        return jsonify({'code': 400, 'success': False, 'data': None,
                        'message': '知识点数量过多（最多 30 个）'}), 400

    current_app.logger.warning('[AIPractice] kp_ids=%s total=%d types=%s', kp_ids[:5], total, qtypes)
    llm_logger.info('[AIPractice] request: kp_ids=%s total=%s types=%s', kp_ids[:5], total, qtypes)
    try:
        total = int(total)
        if total < 1 or total > 30:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'code': 400, 'success': False, 'data': None,
                        'message': '题目数量须为 1-30'}), 400

    current_app.logger.info('[AIPractice] kp_ids=%s total=%d types=%s', kp_ids[:5], total, qtypes)

    if qtypes is not None:
        if not isinstance(qtypes, list):
            qtypes = [qtypes]
        qtypes = [t for t in qtypes if t in QuestionGenerator.VALID_TYPES]
        if not qtypes:
            return jsonify({'code': 400, 'success': False, 'data': None,
                            'message': '请选择至少一种题型'}), 400

    # 获取知识点信息
    kp_info_list = []
    for kp_id in kp_ids:
        node = graph_repo.get_node_by_id(kp_id)
        if node:
            kp_info_list.append({'elementId': kp_id, 'properties': node.get('properties', {})})

    if not kp_info_list:
        return jsonify({'code': 400, 'success': False, 'data': None,
                        'message': '未找到有效知识点'}), 400

    kp_names = [kp['properties'].get('name', '未知') for kp in kp_info_list]
    kp_name_str = '、'.join(kp_names)
    # KP 多时精简上下文，防止 prompt 过长
    if len(kp_info_list) > 10:
        kp_context = QuestionGenerator._build_kp_context(kp_info_list[:10])
        kp_context += f'\n……（共 {len(kp_info_list)} 个知识点，其余从略——请基于知识点名称出题）'
    else:
        kp_context = QuestionGenerator._build_kp_context(kp_info_list)
    difficulty = _calc_difficulty(len(kp_info_list))

    # LLM 出题
    valid_types = qtypes if qtypes else list(QuestionGenerator.VALID_TYPES)
    type_list = [QuestionGenerator.TYPE_DESC[t] for t in valid_types]

    prompt = f"""你是一个专业的教育出题专家。请根据以下知识点，为学生生成{total}道练习题。

知识点：{kp_name_str}

{kp_context}

要求：
1. 共生成恰好 {total} 道题目
2. 必须每种题型各出 1 道：{', '.join(type_list)}
3. 难度等级：{difficulty}/12（12为最高难度）
4. 语言：中文

请按 JSON 数组格式输出（仅输出 JSON）：
```json
[
  {{
    "title": "题目内容",
    "type": "choice/multi_choice/judge/subjective",
    "options": ["A. 选项A", "B. 选项B", "C. 选项C", "D. 选项D"],
    "answer": "正确答案",
    "explanation": "解析"
  }}
]
```"""

    try:
        llm_logger.info('[AIPractice] LLM: kp=%s, total=%d, diff=%d', kp_names, total, difficulty)
        response_text = LLMService.chat([{'role': 'user', 'content': prompt}], temperature=0.8, max_tokens=16384)
        current_app.logger.warning('[AIPractice] LLM response len=%d first=%s', len(response_text), response_text[:200])
        questions_data = QuestionGenerator._parse_response(response_text)
        if isinstance(questions_data, dict):
            for key in ('questions', 'data', 'items', 'results'):
                if key in questions_data and isinstance(questions_data[key], list):
                    questions_data = questions_data[key]
                    break
            else:
                questions_data = [questions_data]
        if not isinstance(questions_data, list):
            questions_data = []
        llm_logger.info('[AIPractice] LLM returned %d questions', len(questions_data))
    except Exception as e:
        llm_logger.error('[AIPractice] LLM error: %s', str(e))
        return jsonify({'code': 500, 'success': False, 'data': None,
                        'message': f'AI 出题失败: {str(e)[:200]}'}), 500

    # 入库
    session_id = str(uuid.uuid4())
    saved = []

    for qd in questions_data:
        title = (qd.get('title') or '').strip()
        qtype = (qd.get('type') or 'choice').strip().lower()
        # 兼容中文题型名
        qtype_map = {
            '单选题': 'choice', '单选题（4个选项）': 'choice', '单选': 'choice',
            '多选题': 'multi_choice', '多选': 'multi_choice',
            '判断题': 'judge', '判断': 'judge',
            '编程题': 'code', '编程': 'code',
            '主观题': 'subjective', '简答题': 'subjective', '简答': 'subjective', '问答题': 'subjective',
        }
        if qtype in qtype_map:
            qtype = qtype_map[qtype]
        if not title or qtype not in QuestionGenerator.VALID_TYPES:
            llm_logger.warning('[AIPractice] skipped question: title="%s" type="%s"', title[:60], qtype)
            continue
        try:
            # 映射：multi_choice → choice + is_multi=True
            is_multi = False
            mapped_type = qtype
            if qtype == 'multi_choice':
                mapped_type = 'choice'
                is_multi = True

            qid = QuestionService.create(
                title=title,
                qtype=mapped_type,
                answer=(qd.get('answer') or '').strip(),
                explanation=(qd.get('explanation') or '').strip(),
                knowledge_point_ids=kp_ids,
                knowledge_point_name=kp_name_str[:500],
                options=qd.get('options'),
                is_multi=is_multi,
                topic='',
                status='pending',
            )
            qid_num = qid.get('id') if isinstance(qid, dict) else qid
            saved.append({
                'id': qid_num,
                'title': title,
                'type': qtype,
                'options': qd.get('options', []),
                'answer': (qd.get('answer') or '').strip(),
                'explanation': (qd.get('explanation') or '').strip(),
            })
        except Exception as e:
            llm_logger.warning('[AIPractice] save failed: "%s" — %s', title[:60], str(e))
            current_app.logger.warning('[AIPractice] save failed: title="%s" error=%s', title[:80], str(e))

    if not saved:
        qd_sample = json.dumps(questions_data[:3] if questions_data else [], ensure_ascii=False, indent=2)[:500]
        current_app.logger.warning('[AIPractice] NO valid questions! count=%d sample=%s',
                                  len(questions_data), qd_sample)
        return jsonify({'code': 500, 'success': False, 'data': None,
                        'message': f'AI 未能生成有效题目，请重试。LLM返回了{len(questions_data)}条但均未通过校验'}), 500

    # 保存 session
    qids_json = json.dumps([q['id'] for q in saved])
    try:
        sql_repo.execute_insert(
            "INSERT INTO practice_sessions (session_id, student_id, question_ids, kp_summary, total) "
            "VALUES (%s, %s, %s, %s, %s)",
            (session_id, user['user_id'], qids_json, kp_name_str, len(saved))
        )
    except Exception as e:
        current_app.logger.error('[AIPractice] session save failed: %s', str(e))

    # 返回：不含答案
    safe = [{'id': q['id'], 'title': q['title'], 'type': q['type'], 'options': q['options']} for q in saved]

    return jsonify({
        'code': 200, 'success': True,
        'data': {'session_id': session_id, 'knowledge_points': kp_names,
                 'difficulty': difficulty, 'questions': safe},
        'message': f'已生成 {len(safe)} 道题目'
    })


# ═══════════════════════════════════════════════
#  异步生成练习题目
# ═══════════════════════════════════════════════

@ai_practice_bp.route('/practice/generate-async', methods=['POST'])
@require_auth
@rate_limit(max_requests=5, window_seconds=60)
def generate_practice_async():
    """异步版：立即返回 task_id，前端轮询 /api/tasks/<id>/status 获取结果"""
    user = request.current_user
    if user.get('role') == 'admin':
        return jsonify({'code': 403, 'success': False, 'data': None,
                        'message': 'AI 练习仅限学生使用'}), 403

    data = request.get_json(force=True) or {}
    kp_ids = data.get('knowledge_point_ids', [])
    total = data.get('total_questions', 5)
    qtypes = data.get('question_types', None)

    if not kp_ids or not isinstance(kp_ids, list):
        return jsonify({'code': 400, 'success': False, 'data': None,
                        'message': '请选择至少一个知识点'}), 400

    if len(kp_ids) > 30:
        return jsonify({'code': 400, 'success': False, 'data': None,
                        'message': '知识点数量过多（最多 30 个）'}), 400

    try:
        total = int(total)
        if total < 1 or total > 30:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'code': 400, 'success': False, 'data': None,
                        'message': '题目数量须为 1-30'}), 400

    if qtypes is not None:
        if not isinstance(qtypes, list):
            qtypes = [qtypes]
        qtypes = [t for t in qtypes if t in QuestionGenerator.VALID_TYPES]
        if not qtypes:
            return jsonify({'code': 400, 'success': False, 'data': None,
                            'message': '请选择至少一种题型'}), 400

    # 提交后台任务
    task_id = submit_task(
        'ai_generate_practice',
        _run_generate_task,
        kp_ids, total, qtypes, user['user_id']
    )

    return jsonify({
        'code': 200, 'success': True,
        'data': {'task_id': task_id, 'message': '出题任务已提交'},
        'message': '出题任务已提交，请轮询获取结果'
    })


def _run_generate_task(kp_ids, total, qtypes, user_id):
    """后台任务：执行 LLM 出题 + 入库（在子线程中运行）"""
    import logging as _logging
    _task_logger = _logging.getLogger('llm')

    kp_info_list = []
    for kp_id in kp_ids:
        node = graph_repo.get_node_by_id(kp_id)
        if node:
            kp_info_list.append({'elementId': kp_id, 'properties': node.get('properties', {})})

    if not kp_info_list:
        return {'code': 400, 'success': False, 'message': '未找到有效知识点'}

    kp_names = [kp['properties'].get('name', '未知') for kp in kp_info_list]
    kp_name_str = '、'.join(kp_names)

    if len(kp_info_list) > 10:
        kp_context = QuestionGenerator._build_kp_context(kp_info_list[:10])
        kp_context += f'\n……（共 {len(kp_info_list)} 个知识点，其余从略）'
    else:
        kp_context = QuestionGenerator._build_kp_context(kp_info_list)

    difficulty = _calc_difficulty(len(kp_info_list))

    valid_types = qtypes if qtypes else list(QuestionGenerator.VALID_TYPES)
    type_list = [QuestionGenerator.TYPE_DESC[t] for t in valid_types]

    prompt = f"""你是一个专业的教育出题专家。请根据以下知识点，为学生生成{total}道练习题。

知识点：{kp_name_str}

{kp_context}

要求：
1. 共生成恰好 {total} 道题目
2. 必须每种题型各出 1 道：{', '.join(type_list)}
3. 难度等级：{difficulty}/12（12为最高难度）
4. 语言：中文

请按 JSON 数组格式输出（仅输出 JSON）：
```json
[
  {{
    "title": "题目内容",
    "type": "choice/multi_choice/judge/subjective",
    "options": ["A. 选项A", "B. 选项B", "C. 选项C", "D. 选项D"],
    "answer": "正确答案",
    "explanation": "解析"
  }}
]
```"""

    _task_logger.info('[AIPracticeAsync] LLM: kp=%s, total=%d, diff=%d', kp_names, total, difficulty)
    try:
        response_text = LLMService.chat([{'role': 'user', 'content': prompt}], temperature=0.8, max_tokens=16384)
        questions_data = QuestionGenerator._parse_response(response_text)
        if isinstance(questions_data, dict):
            for key in ('questions', 'data', 'items', 'results'):
                if key in questions_data and isinstance(questions_data[key], list):
                    questions_data = questions_data[key]
                    break
            else:
                questions_data = [questions_data]
        if not isinstance(questions_data, list):
            questions_data = []
        _task_logger.info('[AIPracticeAsync] LLM returned %d questions', len(questions_data))
    except Exception as e:
        _task_logger.error('[AIPracticeAsync] LLM error: %s', str(e))
        return {'code': 500, 'success': False, 'message': f'AI 出题失败: {str(e)[:200]}'}

    session_id = str(uuid.uuid4())
    saved = []

    for qd in questions_data:
        title = (qd.get('title') or '').strip()
        qtype = (qd.get('type') or 'choice').strip().lower()
        qtype_map = {
            '单选题': 'choice', '单选题（4个选项）': 'choice', '单选': 'choice',
            '多选题': 'multi_choice', '多选': 'multi_choice',
            '判断题': 'judge', '判断': 'judge',
            '编程题': 'code', '编程': 'code',
            '主观题': 'subjective', '简答题': 'subjective', '简答': 'subjective', '问答题': 'subjective',
        }
        if qtype in qtype_map:
            qtype = qtype_map[qtype]
        if not title or qtype not in QuestionGenerator.VALID_TYPES:
            continue
        try:
            is_multi = False
            mapped_type = qtype
            if qtype == 'multi_choice':
                mapped_type = 'choice'
                is_multi = True

            qid = QuestionService.create(
                title=title, qtype=mapped_type,
                answer=(qd.get('answer') or '').strip(),
                explanation=(qd.get('explanation') or '').strip(),
                knowledge_point_ids=kp_ids,
                knowledge_point_name=kp_name_str[:500],
                options=qd.get('options'),
                is_multi=is_multi, topic='',
                status='pending',
            )
            qid_num = qid.get('id') if isinstance(qid, dict) else qid
            saved.append({
                'id': qid_num, 'title': title, 'type': qtype,
                'options': qd.get('options', []),
                'answer': (qd.get('answer') or '').strip(),
                'explanation': (qd.get('explanation') or '').strip(),
            })
        except Exception as e:
            _task_logger.warning('[AIPracticeAsync] save failed: "%s" — %s', title[:60], str(e))

    if not saved:
        return {'code': 500, 'success': False, 'message': f'AI 未能生成有效题目，请重试'}

    # 保存 session
    qids_json = json.dumps([q['id'] for q in saved])
    try:
        sql_repo.execute_insert(
            "INSERT INTO practice_sessions (session_id, student_id, question_ids, kp_summary, total) "
            "VALUES (%s, %s, %s, %s, %s)",
            (session_id, user_id, qids_json, kp_name_str, len(saved))
        )
    except Exception as e:
        _task_logger.error('[AIPracticeAsync] session save failed: %s', str(e))

    safe = [{'id': q['id'], 'title': q['title'], 'type': q['type'], 'options': q['options']} for q in saved]

    return {
        'code': 200, 'success': True,
        'data': {
            'session_id': session_id, 'knowledge_points': kp_names,
            'difficulty': difficulty, 'questions': safe,
        },
        'message': f'已生成 {len(safe)} 道题目',
    }


# ═══════════════════════════════════════════════
#  提交答案并判题
# ═══════════════════════════════════════════════

@ai_practice_bp.route('/practice/submit', methods=['POST'])
@require_auth
def submit_practice():
    """提交练习答案 → 判题 → 返回结果"""
    user = request.current_user
    data = request.get_json(force=True) or {}
    session_id = data.get('session_id', '')
    answers = data.get('answers', [])

    if not session_id or not isinstance(answers, list):
        return jsonify({'code': 400, 'success': False, 'data': None,
                        'message': '参数不完整'}), 400

    # 查 session（校验归属，防止越权提交/读取他人练习）
    sessions = sql_repo.execute_query(
        "SELECT * FROM practice_sessions WHERE session_id = %s AND student_id = %s",
        (session_id, user['user_id'])
    )
    if not sessions:
        return jsonify({'code': 404, 'success': False, 'data': None,
                        'message': '未找到该练习记录'}), 404

    sess = sessions[0]
    qids = json.loads(sess.get('question_ids', '[]'))
    if not qids:
        return jsonify({'code': 404, 'success': False, 'data': None,
                        'message': '练习记录为空'}), 404

    # 查题目答案
    placeholders = ','.join(['%s'] * len(qids))
    rows = sql_repo.execute_query(
        f"SELECT id, title, type, answer, explanation FROM question_bank WHERE id IN ({placeholders})",
        qids
    )

    qmap = {str(r['id']): r for r in rows}
    user_answers = {str(a.get('question_id', '')): a.get('answer', '') for a in answers}

    details = []
    correct_count = 0

    for qid in qids:
        qid_str = str(qid)
        qrow = qmap.get(qid_str)
        if not qrow:
            continue
        user_ans = user_answers.get(qid_str, '')
        correct_ans = (qrow['answer'] or '').strip()
        is_correct = _judge(user_ans, correct_ans, qrow.get('type', 'choice'))
        if is_correct:
            correct_count += 1

        details.append({
            'question_id': int(qid),
            'title': qrow['title'],
            'type': qrow.get('type', 'choice'),
            'your_answer': user_ans,
            'correct_answer': correct_ans,
            'is_correct': is_correct,
            'explanation': qrow.get('explanation', ''),
        })

    total = len(qids)
    score = round(correct_count / total * 100, 1) if total > 0 else 0

    # 更新 session
    try:
        sql_repo.execute_update(
            "UPDATE practice_sessions SET score = %s, correct_count = %s, status = 'done' "
            "WHERE session_id = %s AND student_id = %s",
            (score, correct_count, session_id, user['user_id'])
        )
    except Exception as e:
        current_app.logger.error('[AIPractice] session update failed: %s', str(e))

    # 记录活动
    try:
        from ..services.activity_service import activity_service
        kp_names = sess.get('kp_summary', '')
        activity_service.log(
            user_id=user['user_id'],
            activity_type='practice',
            activity_subtype='ai_practice',
            knowledge_points=kp_names,
            score=score,
            related_id=None,
            detail=f'AI练习得分 {score} 分（{correct_count}/{total}）'
        )
    except Exception as e:
        current_app.logger.warning('[AIPractice] activity log failed: %s', str(e))

    return jsonify({
        'code': 200, 'success': True,
        'data': {'session_id': session_id, 'total': total, 'correct': correct_count,
                 'score': score, 'details': details},
        'message': f'得分 {score} 分（{correct_count}/{total}）'
    })


def _judge(user_answer: str, correct_answer: str, qtype: str) -> bool:
    ua = (user_answer or '').strip().lower()
    ca = (correct_answer or '').strip().lower()
    if not ua or not ca:
        return False

    if qtype in ('choice', 'multi_choice'):
        ua_set = set(re.split(r'[,，、\s]+', ua.replace('\n', '')))
        ca_set = set(re.split(r'[,，、\s]+', ca.replace('\n', '')))
        return ua_set == ca_set

    if qtype == 'judge':
        ua_norm = ua.replace('正确', '对').replace('错误', '错')
        ca_norm = ca.replace('正确', '对').replace('错误', '错')
        return ua_norm == ca_norm

    # 主观题：字符级 Jaccard 相似度，避免过于宽松的子串匹配
    ua_chars = set(ua)
    ca_chars = set(ca)
    if not ua_chars or not ca_chars:
        return False
    intersection = ua_chars & ca_chars
    union = ua_chars | ca_chars
    return len(intersection) / len(union) >= 0.6
