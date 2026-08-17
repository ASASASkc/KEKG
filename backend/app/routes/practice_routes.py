"""学生独立刷题接口"""
from flask import Blueprint, request, jsonify
from app.utils.auth import require_auth
from app.services.practice_service import PracticeService

practice_bp = Blueprint('practice', __name__)


@practice_bp.route('/practice/questions', methods=['GET'])
@require_auth
def list_questions():
    user_id = request.current_user['user_id']
    args = request.args
    kwargs = {
        'page': int(args.get('page', 1)),
        'page_size': min(int(args.get('page_size', 20)), 100),
        'qtype': args.get('type', ''),
        'topic': args.get('topic', ''),
        'keyword': args.get('keyword', ''),
        'status': args.get('status', ''),
        'sort': args.get('sort', ''),
        'favorite_only': args.get('favorites') in ('1', 'true'),
    }
    if args.get('difficulty_min'):
        kwargs['difficulty_min'] = int(args.get('difficulty_min'))
    if args.get('difficulty_max'):
        kwargs['difficulty_max'] = int(args.get('difficulty_max'))
    data = PracticeService.list(user_id, **kwargs)
    return jsonify({'code': 200, 'success': True, 'data': data, 'message': '操作成功'})


@practice_bp.route('/practice/questions/<int:qid>', methods=['GET'])
@require_auth
def question_detail(qid):
    user_id = request.current_user['user_id']
    item = PracticeService.get_question(user_id, qid)
    if not item:
        return jsonify({'code': 404, 'success': False, 'message': '题目不存在'}), 404
    return jsonify({'code': 200, 'success': True, 'data': item, 'message': '操作成功'})


@practice_bp.route('/practice/attempts', methods=['POST'])
@require_auth
def submit_attempt():
    user_id = request.current_user['user_id']
    data = request.get_json() or {}
    qid = data.get('question_id')
    answer = data.get('answer', '')
    elapsed = data.get('elapsed_seconds', 0)
    if not qid:
        return jsonify({'code': 400, 'success': False, 'message': '缺少题目 ID'}), 400
    ok, res, msg = PracticeService.submit(user_id, int(qid), answer, elapsed_seconds=elapsed)
    if not ok:
        return jsonify({'code': 404, 'success': False, 'message': msg}), 404
    return jsonify({'code': 200, 'success': True, 'data': res, 'message': msg})


@practice_bp.route('/practice/history', methods=['GET'])
@require_auth
def practice_history():
    """我的提交记录（分页时间线）"""
    user_id = request.current_user['user_id']
    args = request.args
    data = PracticeService.history(
        user_id,
        page=max(1, args.get('page', 1, type=int)),
        page_size=min(max(1, args.get('page_size', 20, type=int)), 100),
        question_id=args.get('question_id', type=int))
    return jsonify({'code': 200, 'success': True, 'data': data, 'message': '操作成功'})
