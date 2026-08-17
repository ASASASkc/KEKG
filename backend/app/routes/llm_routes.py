# -*- coding: utf-8 -*-
"""
LLM 路由 — API 配置 + AI 出题 + AI 练习
"""
import json
import uuid
import random
import hashlib
import logging
import time
from flask import Blueprint, request, jsonify, g
from ..services.llm_service import LLMService, QuestionGenerator, KnowledgeEnricher
from ..services.question_service import question_service
from ..repositories.graph_repo import graph_repo
from ..repositories.sql_repo import sql_repo
from ..utils.auth import require_auth, require_admin
from ..utils.rate_limit import rate_limit

llm_bp = Blueprint('llm', __name__)

# LLM 专用 logger
llm_logger = logging.getLogger('llm')
if not llm_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '[LLM] %(asctime)s | %(levelname)s | %(message)s',
        datefmt='%H:%M:%S'
    ))
    llm_logger.addHandler(handler)
    llm_logger.setLevel(logging.DEBUG)


def _log_req(route_name: str, extra: str = ''):
    """记录请求入口"""
    method = request.method
    path = request.path
    user = g.get('current_user', {}).get('username', '?') if hasattr(g, 'current_user') else '?'
    body = ''
    if request.is_json:
        try:
            raw = request.get_json(force=True, silent=True) or {}
            body = json.dumps(raw, ensure_ascii=False)
            if len(body) > 300:
                body = body[:300] + '...(truncated)'
        except Exception:
            body = '(parse-error)'
    llm_logger.info('[REQ-IN] %s %s | user=%s | body=%s%s',
                    method, path, user, body, f' | {extra}' if extra else '')


def _log_resp(route_name: str, status_code: int, duration_ms: float, body: dict = None):
    """记录响应出口"""
    body_str = ''
    if body:
        body_str = json.dumps(body, ensure_ascii=False)
        if len(body_str) > 400:
            body_str = body_str[:400] + '...(truncated)'
    llm_logger.info('[RESP-OUT] %s | HTTP=%d | %.0fms | %s',
                    route_name, status_code, duration_ms, body_str)


# ── 配置管理 ────────────────────────────────


@llm_bp.route('/llm/config', methods=['GET'])
@require_admin
def get_config():
    """获取 LLM 配置（管理员）"""
    t0 = time.time()
    _log_req('get_config')
    llm_logger.debug('[get_config] 查询 system_config 表...')
    data = LLMService.get_config()
    llm_logger.debug('[get_config] has_key=%s, model=%s', data.get('has_key'), data.get('model'))
    resp = {'code': 200, 'success': True, 'data': data, 'message': 'ok'}
    _log_resp('get_config', 200, (time.time() - t0) * 1000, resp)
    return jsonify(resp)


@llm_bp.route('/llm/config', methods=['POST'])
@require_admin
def save_config():
    """保存 LLM 配置（管理员）"""
    t0 = time.time()
    _log_req('save_config')
    data = request.get_json(force=True) or {}
    api_key = data.get('api_key', '').strip()
    base_url = data.get('base_url', '').strip()
    model = data.get('model', '').strip()

    if not api_key:
        llm_logger.warning('[save_config] api_key 为空，拒绝')
        _log_resp('save_config', 400, (time.time() - t0) * 1000)
        return jsonify({
            'code': 400, 'success': False, 'message': 'API Key 不能为空'
        }), 400

    llm_logger.info('[save_config] 保存配置: base_url=%s, model=%s', base_url or 'default', model or 'default')
    result = LLMService.save_config(api_key, base_url, model)
    resp = {'code': 200, 'success': True, 'data': result, 'message': '配置已保存'}
    _log_resp('save_config', 200, (time.time() - t0) * 1000, resp)
    return jsonify(resp)


# ============ 外部链接补全 ============

_links_tasks = {}  # task_id -> {status, current, total, enriched, failed, skipped, details, ...}

@llm_bp.route('/llm/links-enrich', methods=['POST'])
@require_admin
def links_enrich():
    """启动外部链接补全任务"""
    import uuid, time as _time, threading as _threading
    t0 = time.time()
    _log_req('links-enrich')
    data = request.get_json(force=True) or {}
    track_filter = data.get('track', '').strip()

    enricher = KnowledgeEnricher()

    llm_logger.info('[links-enrich] 筛选节点, track="%s"...', track_filter or '全部')
    import json as _json
    kp_ids = []
    kp_names = {}
    with graph_repo._session() as session:
        result = session.run("MATCH (n:KnowledgePoint) RETURN elementId(n) as nid, n.tracks as tracks, n.name as name, n.external_links as el")
        for record in result:
            if track_filter:
                try:
                    ts = _json.loads(record['tracks']) if isinstance(record['tracks'], str) else record['tracks']
                except Exception:
                    ts = []
                if track_filter not in (ts if isinstance(ts, list) else []):
                    continue
            # 跳过已有 external_links 的节点
            el = record.get('el')
            if el and el != '' and el != '[]' and el != 'null':
                continue
            kp_ids.append(record['nid'])
            kp_names[record['nid']] = record['name']
    llm_logger.info('[links-enrich] 筛选到 %d 个需补全的节点', len(kp_ids))

    if not kp_ids:
        _log_resp('links-enrich', 400, (time.time() - t0) * 1000)
        return jsonify({'code': 400, 'success': False, 'message': '所有节点已有外部链接'}), 400

    task_id = str(uuid.uuid4())
    _links_tasks[task_id] = {
        'status': 'running', 'track': track_filter or '全部拓展',
        'current': 0, 'total': len(kp_ids),
        'enriched': 0, 'failed': 0, 'skipped': 0,
        'details': [], 'start_time': _time.time(),
    }

    def do_links_enrich():
        import json as __json
        enriched = 0; failed = 0; skipped = 0
        details = []
        for idx, nid in enumerate(kp_ids):
            task = _links_tasks.get(task_id)
            if not task: return
            name = kp_names.get(nid, '?')
            node = graph_repo.get_node_by_id(str(nid))
            if not node:
                failed += 1; details.append({'id': str(nid)[:30], 'name': name, 'status': 'not_found'})
            else:
                # 重试最多 2 次（应对 API 限流/网络波动）
                llm_error = False
                result = None
                for attempt in range(3):
                    try:
                        result = enricher.enrich_external_links_single(node)
                        break
                    except Exception as e:
                        if attempt < 2:
                            _time.sleep(2)
                        else:
                            llm_error = True
                            failed += 1
                            details.append({'id': str(nid)[:30], 'name': name, 'status': 'llm_error',
                                            'error': str(e)[:80]})
                if llm_error:
                    pass  # already counted
                elif result and result.get('links'):
                    try:
                        with graph_repo._session() as s:
                            s.run(
                                "MATCH (n:KnowledgePoint) WHERE elementId(n) = $nid SET n.external_links = $links",
                                {'nid': str(nid), 'links': __json.dumps(result['links'], ensure_ascii=False)}
                            )
                        enriched += 1
                        details.append({'id': str(nid)[:30], 'name': name, 'status': 'enriched', 'links': result['links']})
                    except Exception as e:
                        failed += 1
                        details.append({'id': str(nid)[:30], 'name': name, 'status': 'db_error', 'error': str(e)[:80]})
                else:
                    failed += 1
                    details.append({'id': str(nid)[:30], 'name': name, 'status': 'empty_result'})

            task['current'] = idx + 1
            task['enriched'] = enriched
            task['failed'] = failed
            task['skipped'] = skipped
            task['details'] = details[-20:]

            if (idx + 1) % 3 == 0:
                _time.sleep(0.5)

        task = _links_tasks.get(task_id)
        if task:
            task['status'] = 'done'; task['done'] = True
            task['enriched'] = enriched; task['failed'] = failed; task['skipped'] = skipped
        llm_logger.info('[links-enrich] 完成: task=%s, enriched=%d, failed=%d', task_id[:8], enriched, failed)

    t = _threading.Thread(target=do_links_enrich)
    t.daemon = True; t.start()

    resp = {'code': 200, 'success': True, 'data': {'task_id': task_id, 'total': len(kp_ids)},
            'message': f'已启动外部链接补全任务，共 {len(kp_ids)} 个知识点'}
    _log_resp('links-enrich', 200, (time.time() - t0) * 1000, resp)
    return jsonify(resp)

@llm_bp.route('/llm/links-enrich/status/<task_id>', methods=['GET'])
@require_admin
def links_enrich_status(task_id):
    """查询外部链接补全任务状态"""
    task = _links_tasks.get(task_id)
    if not task:
        return jsonify({'code': 404, 'success': False, 'message': '任务不存在'}), 404
    return jsonify({
        'code': 200, 'success': True,
        'data': {
            'status': task['status'], 'current': task['current'], 'total': task['total'],
            'enriched': task['enriched'], 'failed': task['failed'], 'skipped': task.get('skipped', 0),
            'track': task['track'], 'details': task.get('details', [])[-10:],
            'elapsed': round(time.time() - task['start_time'], 1),
        }
    })


@llm_bp.route('/llm/test', methods=['POST'])
@require_admin
def test_connection():
    """测试 LLM 连接"""
    t0 = time.time()
    _log_req('test_connection')
    llm_logger.info('[test_connection] 开始测试 DeepSeek 连接...')
    result = LLMService.test_connection()
    llm_logger.info('[test_connection] 结果: %s', result)
    resp = {'code': 200, 'success': result['success'], 'data': result, 'message': result['message']}
    _log_resp('test_connection', 200, (time.time() - t0) * 1000, resp)
    return jsonify(resp)


# ── 管理端：AI 批量出题 ─────────────────────


@llm_bp.route('/llm/generate-questions', methods=['POST'])
@require_admin
@rate_limit(max_requests=3, window_seconds=120)
def generate_questions():
    """
    管理员批量生成题目

    Request:
        knowledge_point_ids: list[str] - Neo4j elementId 列表
        questions_per_kp: int - 每个知识点生成题目数 (1-5)
        question_types: list[str] - 题型过滤（可选，默认全部）
    """
    t0 = time.time()
    _log_req('generate_questions')
    data = request.get_json(force=True) or {}
    kp_ids = data.get('knowledge_point_ids', [])
    questions_per_kp = data.get('questions_per_kp', 1)
    question_types = data.get('question_types', None)

    if not kp_ids or not isinstance(kp_ids, list):
        llm_logger.warning('[generate_questions] knowledge_point_ids 为空或非数组')
        _log_resp('generate_questions', 400, (time.time() - t0) * 1000)
        return jsonify({
            'code': 400,
            'success': False,
            'data': None,
            'message': '请提供知识点ID列表 knowledge_point_ids'
        }), 400

    try:
        questions_per_kp = int(questions_per_kp)
        if questions_per_kp < 1 or questions_per_kp > 5:
            raise ValueError
    except (ValueError, TypeError):
        llm_logger.warning('[generate_questions] questions_per_kp=%s 无效', questions_per_kp)
        _log_resp('generate_questions', 400, (time.time() - t0) * 1000)
        return jsonify({
            'code': 400,
            'success': False,
            'data': None,
            'message': 'questions_per_kp 必须为 1-5 的整数'
        }), 400

    if question_types is not None:
        if not isinstance(question_types, list):
            question_types = [question_types]
        question_types = [t for t in question_types if t in QuestionGenerator.VALID_TYPES]
        if not question_types:
            llm_logger.warning('[generate_questions] question_types 过滤后为空')
            _log_resp('generate_questions', 400, (time.time() - t0) * 1000)
            return jsonify({
                'code': 400,
                'success': False,
                'data': None,
                'message': f'无效的题型，支持: {", ".join(QuestionGenerator.VALID_TYPES)}'
            }), 400

    llm_logger.info('[generate_questions] 入参: kp_count=%d, per_kp=%d, types=%s',
                    len(kp_ids), questions_per_kp, question_types or 'all')

    # 1. 从 Neo4j 查询知识点全量信息
    llm_logger.debug('[generate_questions] 查询 Neo4j 知识点...')
    knowledge_points = []
    failed_kps = []
    for kp_id in kp_ids:
        node = graph_repo.get_node_by_id(str(kp_id))
        if node:
            knowledge_points.append(node)
        else:
            llm_logger.warning('[generate_questions] Neo4j 未找到节点: %s', kp_id)
            failed_kps.append(kp_id)

    llm_logger.debug('[generate_questions] Neo4j 查询完成: found=%d, not_found=%d',
                     len(knowledge_points), len(failed_kps))

    if not knowledge_points:
        llm_logger.error('[generate_questions] 无有效知识点')
        _log_resp('generate_questions', 400, (time.time() - t0) * 1000)
        return jsonify({
            'code': 400,
            'success': False,
            'data': None,
            'message': '未找到任何有效知识点'
        }), 400

    # 2. 分批处理（超过 10 个知识点时分批）
    batch_size = 10
    batch_count = (len(knowledge_points) + batch_size - 1) // batch_size
    llm_logger.info('[generate_questions] 分 %d 批处理', batch_count)

    created = 0
    skipped = 0
    failed = 0
    all_questions = []
    batch_failed_kps = []

    for i in range(0, len(knowledge_points), batch_size):
        batch = knowledge_points[i:i + batch_size]
        batch_idx = i // batch_size + 1
        llm_logger.info('[generate_questions] 处理第 %d/%d 批 (%d 个知识点)...',
                        batch_idx, batch_count, len(batch))
        batch_t0 = time.time()
        try:
            generated = QuestionGenerator.generate_questions(
                knowledge_points=batch,
                questions_per_kp=questions_per_kp,
                question_types=question_types
            )
            llm_logger.info('[generate_questions] 第 %d 批 LLM 返回 %d 题 (%.1fs)',
                            batch_idx, len(generated), time.time() - batch_t0)
        except Exception as e:
            llm_logger.error('[generate_questions] 第 %d 批 LLM 调用失败: %s',
                             batch_idx, str(e), exc_info=True)
            for kp in batch:
                batch_failed_kps.append(kp.get('name', kp.get('id', 'unknown')))
            failed += 1
            continue

        for idx, q in enumerate(generated):
            try:
                qtype = q.get('type', 'choice').strip()
                title = (q.get('title') or '').strip()

                # 去重检查
                if question_service._title_exists(title):
                    skipped += 1
                    llm_logger.debug('[generate_questions] 跳过重复: "%s"', title[:60])
                    all_questions.append({**q, '_status': 'skipped', '_reason': '重复题目'})
                    continue

                # 解析 options
                options = q.get('options', [])
                if isinstance(options, str):
                    try:
                        options = json.loads(options)
                    except Exception:
                        options = [o.strip() for o in options.replace('\n', ',').split(',') if o.strip()]

                qtype_map = {
                    'choice': 'choice',
                    'multi_choice': 'choice',
                    'judge': 'judge',
                    'code': 'code',
                    'subjective': 'subjective',
                }
                system_type = qtype_map.get(qtype, qtype)
                is_multi = (qtype == 'multi_choice')

                # 每题关联批量中的所有知识点（跨知识点综合题 → 难度更高）
                batch_kp_ids = [kp.get('name', kp.get('id', '')) for kp in batch]
                batch_kp_ids = [k for k in batch_kp_ids if k]

                question_service.create(
                    title=title,
                    qtype=system_type,
                    knowledge_point_ids=batch_kp_ids,
                    answer=(q.get('answer') or '').strip(),
                    options=options if options else None,
                    is_multi=is_multi,
                    explanation=(q.get('explanation') or '').strip(),
                    code_template=(q.get('code_template') or '').strip(),
                    created_by=request.current_user.get('user_id', 1)
                )
                created += 1
                all_questions.append({**q, '_status': 'created'})
            except Exception as e:
                failed += 1
                llm_logger.warning('[generate_questions] 题目入库失败: "%s" — %s',
                                   title[:60] if title else '(empty)', str(e))
                all_questions.append({**q, '_status': 'failed', '_reason': str(e)})

    all_failed_kps = list(set(failed_kps + batch_failed_kps))
    llm_logger.info('[generate_questions] 完成: created=%d, skipped=%d, failed=%d, total_time=%.1fs',
                    created, skipped, failed, time.time() - t0)

    resp = {
        'code': 200,
        'success': True,
        'data': {
            'created': created,
            'skipped': skipped,
            'failed': failed,
            'total': created + skipped + failed,
            'failed_kps': all_failed_kps,
            'questions': all_questions
        },
        'message': f'生成完成：新增 {created} 题，跳过 {skipped} 题，失败 {failed} 题'
    }
    _log_resp('generate_questions', 200, (time.time() - t0) * 1000, {
        'created': created, 'skipped': skipped, 'failed': failed
    })
    return jsonify(resp)


# ── 用户端：节点 AI 练习 ─────────────────────

# 内存缓存练习 session（生产环境可换 Redis）
_practice_sessions = {}


@llm_bp.route('/llm/practice', methods=['POST'])
@require_auth
def practice():
    """
    用户 AI 练习 — 根据知识点生成 1 道题目（不入库）

    Request: {knowledge_point_id: "xxx" (Neo4j elementId)}
    Response: {question: {...}, session_id: "uuid"}
    """
    t0 = time.time()
    _log_req('practice')
    data = request.get_json(force=True) or {}
    kp_id = data.get('knowledge_point_id', '').strip()

    if not kp_id:
        llm_logger.warning('[practice] knowledge_point_id 为空')
        _log_resp('practice', 400, (time.time() - t0) * 1000)
        return jsonify({
            'code': 400, 'success': False, 'data': None,
            'message': '请提供知识点ID knowledge_point_id'
        }), 400

    # 从 Neo4j 查询知识点
    llm_logger.debug('[practice] 查询 Neo4j 节点: %s', kp_id)
    node = graph_repo.get_node_by_id(str(kp_id))
    if not node:
        llm_logger.warning('[practice] Neo4j 未找到节点: %s', kp_id)
        _log_resp('practice', 404, (time.time() - t0) * 1000)
        return jsonify({
            'code': 404, 'success': False, 'data': None,
            'message': '知识点不存在'
        }), 404

    kp_name = node.get('name', '?') if isinstance(node, dict) else getattr(node, 'name', '?')
    # 随机选择 1 种题型，生成 1 题
    random_type = random.choice(list(QuestionGenerator.VALID_TYPES))
    llm_logger.info('[practice] 知识点="%s", 题型=%s, kp_id=%s', kp_name, random_type, kp_id)
    try:
        questions = QuestionGenerator.generate_questions(
            knowledge_points=[node],
            questions_per_kp=1,
            question_types=[random_type]
        )
        llm_logger.info('[practice] LLM 返回 %d 题 (%.1fs)', len(questions), time.time() - t0)
    except Exception as e:
        llm_logger.error('[practice] LLM 生成失败: %s', str(e), exc_info=True)
        _log_resp('practice', 500, (time.time() - t0) * 1000)
        return jsonify({
            'code': 500, 'success': False, 'data': None,
            'message': f'LLM 生成题目失败: {str(e)}'
        }), 500

    if not questions:
        llm_logger.error('[practice] LLM 返回空题目列表')
        _log_resp('practice', 500, (time.time() - t0) * 1000)
        return jsonify({
            'code': 500, 'success': False, 'data': None,
            'message': 'LLM 未能生成有效题目，请重试'
        }), 500

    question = questions[0]
    session_id = str(uuid.uuid4())

    # 缓存 session 信息
    _practice_sessions[session_id] = {
        'question': question,
        'knowledge_point_id': kp_id,
        'correct_answer': question.get('answer', ''),
        'question_title': question.get('title', ''),
    }
    llm_logger.debug('[practice] session=%s 已缓存, title=%s', session_id[:8], question.get('title', '')[:60])

    resp = {
        'code': 200, 'success': True,
        'data': {'question': question, 'session_id': session_id},
        'message': '题目已生成'
    }
    _log_resp('practice', 200, (time.time() - t0) * 1000, {'session_id': session_id[:8]})
    return jsonify(resp)


@llm_bp.route('/llm/practice/check', methods=['POST'])
@require_auth
def practice_check():
    """
    用户 AI 练习判题

    Request: {session_id: "xxx", question: {...}, user_answer: "xxx"}
    Response: {correct: bool, explanation: "..."}
    """
    t0 = time.time()
    _log_req('practice_check')
    data = request.get_json(force=True) or {}
    session_id = data.get('session_id', '').strip()
    question = data.get('question', {})
    user_answer = data.get('user_answer', '').strip()

    if not session_id:
        llm_logger.warning('[practice_check] session_id 为空')
        _log_resp('practice_check', 400, (time.time() - t0) * 1000)
        return jsonify({
            'code': 400, 'success': False, 'data': None,
            'message': '请提供 session_id'
        }), 400

    if not user_answer and user_answer != '':
        llm_logger.warning('[practice_check] user_answer 为空')
        _log_resp('practice_check', 400, (time.time() - t0) * 1000)
        return jsonify({
            'code': 400, 'success': False, 'data': None,
            'message': '请提供 user_answer'
        }), 400

    # 从缓存获取 session
    session_data = _practice_sessions.get(session_id)
    if session_data:
        correct_answer = session_data.get('correct_answer', '')
        question_title = session_data.get('question_title', '')
        llm_logger.debug('[practice_check] session=%s 命中缓存', session_id[:8])
    else:
        llm_logger.warning('[practice_check] session=%s 缓存未命中', session_id[:8])
        correct_answer = question.get('answer', '').strip()
        question_title = question.get('title', '').strip()

    if not question_title:
        question_title = question.get('title', '').strip()
    if not correct_answer:
        correct_answer = question.get('answer', '').strip()

    llm_logger.info('[practice_check] 判题: "%s" | 正确答案="%s" | 用户答案="%s"',
                    question_title[:60], correct_answer[:80], user_answer[:80])

    # 调用 LLM 判题
    judge_prompt = f"""你是一个严格的学科教师。请判断学生的答案是否与正确答案一致。

题目：{question_title}
正确答案：{correct_answer}
学生答案：{user_answer}

请判断学生答案是否正确（语义等价即可，不要求一字不差；注意判断的核心是对知识的掌握而非措辞）。

输出JSON格式（仅输出JSON，不要其他内容）：
{{"correct": true/false, "explanation": "简要解释判断原因（50字以内）"}}"""

    try:
        llm_logger.debug('[practice_check] 调用 LLM 判题...')
        judge_t0 = time.time()
        response_text = LLMService.chat(
            messages=[{'role': 'user', 'content': judge_prompt}],
            temperature=0.1,
            max_tokens=256
        )
        llm_logger.debug('[practice_check] LLM 判题返回 (%.1fs): %s',
                         time.time() - judge_t0, response_text[:200])
    except Exception as e:
        llm_logger.error('[practice_check] LLM 判题失败: %s', str(e), exc_info=True)
        _log_resp('practice_check', 500, (time.time() - t0) * 1000)
        return jsonify({
            'code': 500, 'success': False, 'data': None,
            'message': f'LLM 判题失败: {str(e)}'
        }), 500

    # 解析判题结果
    import re
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response_text)
    if json_match:
        judge_json_str = json_match.group(1).strip()
    else:
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            judge_json_str = json_match.group(0)
        else:
            judge_json_str = response_text

    try:
        judge_result = json.loads(judge_json_str)
        is_correct = bool(judge_result.get('correct', False))
        explanation = judge_result.get('explanation', '')
    except json.JSONDecodeError:
        llm_logger.warning('[practice_check] JSON 解析失败，回退关键词判断')
        lower_resp = response_text.lower()
        is_correct = 'true' in lower_resp and 'false' not in lower_resp.replace('"correct": true', '')
        explanation = response_text[:200]

    llm_logger.info('[practice_check] 结果: correct=%s, explanation=%s',
                    is_correct, explanation[:100])

    # 写入 exam_answers（exam_id=0 表示独立练习）
    try:
        student_id = request.current_user.get('user_id', 0)
        question_id = int(hashlib.md5(session_id.encode()).hexdigest()[:8], 16)

        sql_repo.execute_update(
            """INSERT INTO exam_answers
               (exam_id, student_id, question_id, student_answer, is_correct,
                score, max_score, review_status, review_comment, submitted_at, reviewed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NOW(), NOW())""",
            (0, student_id, question_id, user_answer,
             1 if is_correct else 0, 0, 0,
             'done', explanation)
        )
        llm_logger.debug('[practice_check] exam_answers 写入成功')
    except Exception as e:
        llm_logger.warning('[practice_check] exam_answers 写入失败（不影响判题）: %s', str(e))

    # 清理缓存
    _practice_sessions.pop(session_id, None)

    resp = {
        'code': 200, 'success': True,
        'data': {'correct': is_correct, 'explanation': explanation},
        'message': '判题完成'
    }
    _log_resp('practice_check', 200, (time.time() - t0) * 1000,
              {'correct': is_correct})
    return jsonify(resp)


# ── 知识点内容补全 ──────────────────────────

import threading as _threading

# 补全任务状态存储 {task_id: {status, current, total, enriched, failed, start_time, track, details: [...]}}
_enrich_tasks = {}


@llm_bp.route('/llm/enrich', methods=['POST'])
@require_admin
def enrich_knowledge_start():
    """
    启动批量补全任务（后台线程执行）

    Request: {track: "xxx" (可选，按拓展筛选)}
    Response: {task_id: "uuid"}
    """
    t0 = time.time()
    _log_req('enrich')
    data = request.get_json(force=True) or {}
    track_filter = data.get('track', '').strip()

    # 获取节点：指定拓展则筛选，否则获取全部
    llm_logger.info('[enrich] 筛选知识点, track="%s"...', track_filter or '全部')
    import json as _json
    kp_ids = []
    kp_names = {}
    with graph_repo._session() as session:
        result = session.run(
            "MATCH (n:KnowledgePoint) RETURN elementId(n) as nid, n.tracks as tracks, n.name as name"
        )
        for record in result:
            if track_filter:
                try:
                    ts = _json.loads(record['tracks']) if isinstance(record['tracks'], str) else record['tracks']
                except Exception:
                    ts = []
                if track_filter not in (ts if isinstance(ts, list) else []):
                    continue
            kp_ids.append(record['nid'])
            kp_names[record['nid']] = record['name']
    llm_logger.info('[enrich] 筛选到 %d 个节点', len(kp_ids))

    if not kp_ids:
        _log_resp('enrich', 400, (time.time() - t0) * 1000)
        return jsonify({
            'code': 400, 'success': False, 'message': '没有找到知识点'
        }), 400

    task_id = str(uuid.uuid4())
    _enrich_tasks[task_id] = {
        'status': 'running',
        'track': track_filter or '全部拓展',
        'current': 0,
        'total': len(kp_ids),
        'enriched': 0,
        'failed': 0,
        'skipped': 0,
        'start_time': time.time(),
        'details': [],
        'done': False,
    }

    def do_enrich():
        """后台执行补全"""
        enricher = KnowledgeEnricher()
        enriched = 0
        failed = 0
        skipped = 0
        details = []

        for idx, nid in enumerate(kp_ids):
            node = graph_repo.get_node_by_id(str(nid))
            name = kp_names.get(nid, '?')

            if not node:
                failed += 1
                details.append({'id': str(nid)[:30], 'name': name, 'status': 'not_found'})
            else:
                props = node.get('properties', {})
                if props.get('description') and props.get('syntax'):
                    skipped += 1
                    details.append({'id': str(nid)[:30], 'name': name, 'status': 'skipped'})
                else:
                    try:
                        result = enricher.enrich_single(node)
                    except Exception as e:
                        failed += 1
                        details.append({'id': str(nid)[:30], 'name': name, 'status': 'llm_error', 'error': str(e)[:80]})
                    else:
                        if result and (result.get('description') or result.get('syntax')):
                            try:
                                with graph_repo._session() as s:
                                    set_clauses = []
                                    params = {'nid': nid}
                                    if result.get('description'):
                                        set_clauses.append("n.description = $description")
                                        params['description'] = result['description']
                                    if result.get('syntax'):
                                        set_clauses.append("n.syntax = $syntax")
                                        params['syntax'] = result['syntax']
                                    if set_clauses:
                                        s.run(
                                            "MATCH (n:KnowledgePoint) WHERE elementId(n) = $nid SET " + ", ".join(set_clauses),
                                            params
                                        )
                                enriched += 1
                                details.append({'id': str(nid)[:30], 'name': name, 'status': 'enriched'})
                            except Exception as e:
                                failed += 1
                                details.append({'id': str(nid)[:30], 'name': name, 'status': 'db_error', 'error': str(e)[:80]})
                        else:
                            failed += 1
                            details.append({'id': str(nid)[:30], 'name': name, 'status': 'empty_result'})

            task = _enrich_tasks[task_id]
            task['current'] = idx + 1
            task['enriched'] = enriched
            task['failed'] = failed
            task['skipped'] = skipped
            task['details'] = details[-20:]  # 仅保留最近 20 条

            # 每 5 个节点暂停 0.5 秒，避免 API 限流
            if (idx + 1) % 5 == 0:
                time.sleep(0.3)

        task = _enrich_tasks[task_id]
        task['status'] = 'done'
        task['done'] = True
        task['enriched'] = enriched
        task['failed'] = failed
        task['skipped'] = skipped
        elapsed = time.time() - task['start_time']
        llm_logger.info('[enrich] 任务完成: task=%s, enriched=%d, failed=%d, skipped=%d, elapsed=%.1fs',
                        task_id[:8], enriched, failed, skipped, elapsed)

    t = _threading.Thread(target=do_enrich)
    t.daemon = True
    t.start()

    resp = {'code': 200, 'success': True, 'data': {'task_id': task_id, 'total': len(kp_ids)},
            'message': f'已启动补全任务，共 {len(kp_ids)} 个知识点'}
    _log_resp('enrich', 200, (time.time() - t0) * 1000, resp)
    return jsonify(resp)


@llm_bp.route('/llm/enrich/status/<task_id>', methods=['GET'])
@require_admin
def enrich_status(task_id):
    """查询补全任务状态"""
    task = _enrich_tasks.get(task_id)
    if not task:
        return jsonify({'code': 404, 'success': False, 'message': '任务不存在'}), 404
    return jsonify({
        'code': 200, 'success': True,
        'data': {
            'status': task['status'],
            'current': task['current'],
            'total': task['total'],
            'enriched': task['enriched'],
            'failed': task['failed'],
            'skipped': task.get('skipped', 0),
            'track': task['track'],
            'details': task.get('details', [])[-10:],
            'elapsed': round(time.time() - task['start_time'], 1),
        }
    })
