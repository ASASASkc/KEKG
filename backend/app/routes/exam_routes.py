# -*- coding: utf-8 -*-
"""考试路由"""
from flask import Blueprint, request, jsonify, current_app
from ..services.exam_service import exam_service
from ..utils.operation_logger import record_log
from ..utils.auth import require_auth, require_admin
from ..utils.pagination import get_pagination_params, paginate_list, paginate_response
from ..utils.rate_limit import rate_limit
from ..repositories.sql_repo import sql_repo

exam_bp = Blueprint('exam', __name__)

# ── 教师管理 ──
@exam_bp.route('/exams', methods=['POST'])
@require_admin
def create_exam():
    data = request.get_json(force=True) or {}
    user_id = request.current_user['user_id']
    task_type = data.get('task_type', 'exam')
    e = exam_service.create(
        title=data.get('title', ''), class_id=data.get('class_id', 0),
        duration_minutes=data.get('duration_minutes', 120),
        start_time=data.get('start_time', ''), end_time=data.get('end_time', ''),
        description=data.get('description', ''), pass_score=data.get('pass_score', 60),
        created_by=user_id, task_type=task_type,
        max_attempts=data.get('max_attempts'),
        weight_config=data.get('weight_config')
    )
    record_log('创建任务', '考试管理', f'创建{"考试" if task_type == "exam" else "作业"} "{e["title"]}"')
    return jsonify({'code': 200, 'success': True, 'data': e, 'message': '创建成功'})

@exam_bp.route('/exams/generate', methods=['POST'])
@require_admin
@rate_limit(max_requests=5, window_seconds=60)
def generate_exam():
    data = request.get_json(force=True) or {}
    user_id = request.current_user['user_id']
    task_type = data.get('task_type', 'exam')
    try:
        e = exam_service.generate(
            title=data.get('title', ''), class_id=data.get('class_id', 0),
            duration_minutes=data.get('duration_minutes', 120),
            start_time=data.get('start_time', ''), end_time=data.get('end_time', ''),
            rules=data.get('rules', []), description=data.get('description', ''),
            pass_score=data.get('pass_score', 60), created_by=user_id,
            task_type=task_type
        )
        record_log('生成任务', '考试管理', f'生成{"考试" if task_type == "exam" else "作业"} "{data.get("title", "")}"')
        return jsonify({'code': 200, 'success': True, 'data': e, 'message': '生成成功'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400

@exam_bp.route('/exams/generate-ai', methods=['POST'])
@require_admin
@rate_limit(max_requests=3, window_seconds=120)
def generate_exam_ai():
    """AI 组卷：管理员指定题型+数量，LLM 生成试卷。难度由知识点量自动计算"""
    data = request.get_json(force=True) or {}
    user_id = request.current_user['user_id']
    kp_ids = data.get('knowledge_point_ids', [])
    if not isinstance(kp_ids, list):
        kp_ids = []
    kp_names = data.get('knowledge_point_names', [])
    if not isinstance(kp_names, list):
        kp_names = []
    task_type = data.get('task_type', 'exam')
    try:
        e = exam_service.generate_ai(
            title=data.get('title', ''),
            description=data.get('description', ''),
            rules=data.get('rules', []),
            knowledge_point_ids=kp_ids,
            knowledge_point_names=kp_names,
            class_id=data.get('class_id', 0),
            duration_minutes=data.get('duration_minutes', 60),
            start_time=data.get('start_time', ''),
            end_time=data.get('end_time', ''),
            pass_score=data.get('pass_score', 60),
            created_by=user_id,
            task_type=task_type
        )
        record_log('AI组卷', '考试管理', f'AI生成{"考试" if task_type == "exam" else "作业"} "{e["title"]}"，共 {e["question_count"]} 题')
        return jsonify({'code': 200, 'success': True, 'data': e, 'message': f'AI组卷完成，共 {e["question_count"]} 题'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'code': 500, 'success': False, 'message': f'AI组卷失败: {str(e)}'}), 500

@exam_bp.route('/exams', methods=['GET'])
@require_auth
def list_exams():
    user_id = request.current_user['user_id']
    role = request.current_user.get('role', 'user')
    class_id = request.args.get('class_id', type=int)
    page, page_size = get_pagination_params(request.args)
    if class_id:
        if role == 'admin':
            exams = exam_service.get_by_class(class_id)
        else:
            # 学生查看班级考试也过滤草稿，并带上个人提交状态
            exams = exam_service.get_by_class_published(class_id, user_id)
    elif role == 'admin':
        exams = exam_service.get_admin_exams(user_id)
    else:
        exams = exam_service.get_by_student(user_id)
    items, total = paginate_list(exams, page, page_size)
    return jsonify({
        'code': 200, 'success': True,
        'data': paginate_response(items, page, page_size, total),
        'message': '操作成功'
    })

@exam_bp.route('/exams/<int:eid>', methods=['GET'])
@require_auth
def get_exam(eid):
    e = exam_service.get_by_id(eid)
    if not e:
        return jsonify({'code': 404, 'success': False, 'message': '试卷不存在'}), 404
    role = request.current_user.get('role', 'user')
    if role != 'admin':
        # 学生仅可查看本班已发布试卷
        if e.get('status') != 'published':
            return jsonify({'code': 403, 'success': False, 'message': '试卷未发布或已关闭'}), 403
        if e.get('class_id'):
            membership = sql_repo.execute_query(
                "SELECT id FROM class_students WHERE class_id = ? AND student_id = ?",
                (e.get('class_id'), request.current_user['user_id']))
            if not membership:
                return jsonify({'code': 403, 'success': False, 'message': '你不在该试卷的班级中'}), 403
    return jsonify({'code': 200, 'success': True, 'data': e, 'message': '操作成功'})

@exam_bp.route('/exams/<int:eid>', methods=['PUT'])
@require_admin
def update_exam(eid):
    data = request.get_json(force=True) or {}
    exam_service.update(eid, **data)
    record_log('编辑试卷', '考试管理', f'编辑试卷 ID={eid}')
    return jsonify({'code': 200, 'success': True, 'message': '更新成功'})

@exam_bp.route('/exams/<int:eid>', methods=['DELETE'])
@require_admin
def delete_exam(eid):
    exam_service.delete(eid)
    record_log('删除试卷', '考试管理', f'删除试卷 ID={eid}')
    return jsonify({'code': 200, 'success': True, 'message': '已删除'})

@exam_bp.route('/exams/<int:eid>/publish', methods=['PUT'])
@require_admin
def publish_exam(eid):
    exam_service.publish(eid)
    record_log('发布试卷', '考试管理', f'发布试卷 ID={eid}')
    return jsonify({'code': 200, 'success': True, 'message': '已发布'})

@exam_bp.route('/exams/<int:eid>/close', methods=['PUT'])
@require_admin
def close_exam(eid):
    exam_service.close(eid)
    record_log('关闭试卷', '考试管理', f'关闭试卷 ID={eid}')
    return jsonify({'code': 200, 'success': True, 'message': '已关闭'})

@exam_bp.route('/exams/<int:eid>/ranking', methods=['GET'])
@require_admin
def exam_ranking(eid):
    """班级内考试排名（教师可见）"""
    data = exam_service.get_ranking(eid)
    return jsonify({'code': 200, 'success': True, 'data': data, 'message': '操作成功'})

@exam_bp.route('/exams/<int:eid>/analyses/<int:qid>', methods=['PUT'])
@require_admin
def set_analysis(eid, qid):
    """教师发布/更新某题标准解析"""
    data = request.get_json(force=True) or {}
    try:
        exam_service.set_analysis(eid, qid, data.get('content', ''), request.current_user['user_id'])
        record_log('发布解析', '考试管理', f'考试{eid} 题目{qid} 发布解析')
        return jsonify({'code': 200, 'success': True, 'message': '解析已发布'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400

@exam_bp.route('/exams/<int:eid>/analyses/<int:qid>', methods=['DELETE'])
@require_admin
def delete_analysis(eid, qid):
    """删除某题标准解析"""
    exam_service.delete_analysis(eid, qid)
    record_log('删除解析', '考试管理', f'考试{eid} 题目{qid} 删除解析')
    return jsonify({'code': 200, 'success': True, 'message': '解析已删除'})

# ── 学生答题 ──
@exam_bp.route('/exams/<int:eid>/start', methods=['POST'])
@require_auth
def start_exam(eid):
    user_id = request.current_user['user_id']
    try:
        result = exam_service.start_exam(eid, user_id)
        return jsonify({'code': 200, 'success': True, 'data': result, 'message': '开始答题'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400

@exam_bp.route('/exams/<int:eid>/start-homework', methods=['POST'])
@require_auth
def start_homework(eid):
    user_id = request.current_user['user_id']
    try:
        result = exam_service.start_homework(eid, user_id)
        return jsonify({'code': 200, 'success': True, 'data': result, 'message': '开始做作业'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400

@exam_bp.route('/exams/<int:eid>/answers', methods=['POST'])
@require_auth
def save_answer(eid):
    user_id = request.current_user['user_id']
    data = request.get_json(force=True) or {}
    try:
        exam_service.save_answer(eid, user_id, data.get('question_id'), data.get('answer', ''))
        return jsonify({'code': 200, 'success': True, 'message': '已保存'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400

@exam_bp.route('/exams/<int:eid>/submit', methods=['POST'])
@require_auth
def submit_exam(eid):
    user_id = request.current_user['user_id']
    data = request.get_json(force=True) or {}
    try:
        result = exam_service.submit_exam(eid, user_id)
        record_log('提交试卷', '考试管理', f'学生 {user_id} 提交试卷 {eid}，切屏 {data.get("focus_lost_count", 0)} 次')
        # 记录活动日志
        try:
            from ..services.activity_service import activity_service
            paper = sql_repo.execute_query(
                "SELECT title, task_type FROM exam_papers WHERE id = ?", (eid,))
            if paper:
                atype = 'exam' if paper[0].get('task_type', 'exam') == 'exam' else 'homework'
                detail = f'{"考试" if atype == "exam" else "作业"} "{paper[0]["title"]}" 得分 {result.get("auto_score", 0)}'
                activity_service.log(
                    user_id=user_id,
                    activity_type=atype,
                    activity_subtype='submit',
                    knowledge_points='',
                    score=result.get('auto_score', 0),
                    related_id=eid,
                    detail=detail
                )
        except Exception as e:
            current_app.logger.warning('[Exam] activity log failed: %s', str(e))
        return jsonify({'code': 200, 'success': True, 'data': result, 'message': '提交成功'})
    except ValueError as e:
        return jsonify({'code': 400, 'success': False, 'message': str(e)}), 400

@exam_bp.route('/exams/<int:eid>/my-result', methods=['GET'])
@require_auth
def my_result(eid):
    user_id = request.current_user['user_id']
    result = exam_service.get_my_result(eid, user_id)
    if not result:
        return jsonify({'code': 404, 'success': False, 'message': '未找到提交记录'}), 404
    # 补充试卷信息（标题/时长/及格线），供前端展示用时与超时标记
    paper = exam_service.get_paper_meta(eid)
    if paper:
        result['exam_title'] = paper.get('title', '')
        result['duration_minutes'] = paper.get('duration_minutes')
        result['pass_score'] = paper.get('pass_score')
        result['task_type'] = paper.get('task_type', 'exam')
    return jsonify({'code': 200, 'success': True, 'data': result, 'message': '操作成功'})


@exam_bp.route('/exams/<int:eid>/analysis', methods=['GET'])
@require_auth
def exam_analysis(eid):
    """获取考试分析报告"""
    user_id = request.current_user['user_id']
    result = exam_service.get_exam_analysis(eid, user_id)
    if not result:
        return jsonify({'code': 404, 'success': False, 'message': '未找到提交记录'}), 404
    return jsonify({'code': 200, 'success': True, 'data': result, 'message': '操作成功'})

# ── 教师阅卷 ──
@exam_bp.route('/exams/<int:eid>/submissions', methods=['GET'])
@require_admin
def get_submissions(eid):
    page, page_size = get_pagination_params(request.args)
    subs = exam_service.get_submissions(eid)
    items, total = paginate_list(subs, page, page_size)
    return jsonify({
        'code': 200, 'success': True,
        'data': paginate_response(items, page, page_size, total),
        'message': '操作成功'
    })

@exam_bp.route('/exams/<int:eid>/submissions/<int:sid>', methods=['GET'])
@require_admin
def get_submission_detail(eid, sid):
    """教师查看某个学生的完整答题详情"""
    result = exam_service.get_submission_detail(eid, sid)
    if not result:
        return jsonify({'code': 404, 'success': False, 'message': '未找到提交记录'}), 404
    return jsonify({'code': 200, 'success': True, 'data': result, 'message': '操作成功'})


@exam_bp.route('/exams/<int:eid>/answers/<int:aid>/review', methods=['PUT'])
@require_admin
def review_answer(eid, aid):
    data = request.get_json(force=True) or {}
    user_id = request.current_user['user_id']
    exam_service.review_answer(aid, data.get('score', 0), data.get('comment', ''), user_id)
    return jsonify({'code': 200, 'success': True, 'message': '已审批'})

@exam_bp.route('/exams/<int:eid>/submissions/<int:sid>/finalize', methods=['POST'])
@require_admin
def finalize_review(eid, sid):
    total = exam_service.finalize_review(eid, sid)
    record_log('完成阅卷', '考试管理', f'完成试卷 {eid} 学生 {sid} 阅卷，总分={total}')
    return jsonify({'code': 200, 'success': True, 'data': {'total_score': total}, 'message': '阅卷完成'})


@exam_bp.route('/exams/<int:eid>/batch-review', methods=['PUT'])
@require_admin
def batch_review(eid):
    """批量评分"""
    user_id = request.current_user['user_id']
    data = request.get_json(force=True) or {}
    reviews = data.get('reviews', [])
    if not reviews or not isinstance(reviews, list):
        return jsonify({'code': 400, 'success': False, 'message': '请提供评分数组'}), 400
    try:
        result = exam_service.batch_review(eid, reviews, user_id)
        return jsonify({'code': 200, 'success': True, 'data': result, 'message': f'已完成 {result["reviewed_count"]} 题评分'})
    except Exception as e:
        return jsonify({'code': 500, 'success': False, 'message': str(e)}), 500


@exam_bp.route('/exams/<int:eid>/submissions/<int:sid>/draft', methods=['PUT'])
@require_admin
def set_review_draft(eid, sid):
    """暂存/取消暂存"""
    data = request.get_json(force=True) or {}
    is_draft = data.get('draft', 1)
    result = exam_service.set_review_draft(eid, sid, is_draft)
    return jsonify({'code': 200, 'success': True, 'data': result})


@exam_bp.route('/exams/<int:eid>/export-results', methods=['GET'])
@require_admin
def export_results(eid):
    """导出考试成绩为 Excel"""
    result = exam_service.export_results(eid)
    if not result:
        return jsonify({'code': 404, 'success': False, 'message': '未找到考试记录'}), 404
    import io
    try:
        import openpyxl
    except ImportError:
        return jsonify({'code': 500, 'success': False, 'message': '请安装 openpyxl 依赖'}), 500
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '考试成绩'
    headers = ['序号', '学生', '总分']
    for q in result['questions']:
        headers.append(f"第{q['sort_order']+1}题({q['max_score']}分)")
    headers.extend(['状态', '通过'])
    ws.append(headers)
    for i, r in enumerate(result['results'], 1):
        row = [i, r.get('username', ''), r.get('total_score') or 0]
        scores = r.get('scores', {})
        for q in result['questions']:
            row.append(scores.get(q['question_id'], ''))
        row.append('已批阅' if r.get('is_reviewed') else '待批阅')
        row.append('是' if (r.get('total_score') or 0) >= (result.get('pass_score') or 60) else '否')
        ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    from flask import send_file
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'考试成绩_{result["exam_title"]}.xlsx'
    )
