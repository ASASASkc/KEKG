# -*- coding: utf-8 -*-
"""操作日志路由"""

from flask import Blueprint, request
from ..utils.auth import require_dev
from ..utils.rate_limit import rate_limit
from ..utils.response import ok, fail
from ..utils.pagination import get_pagination_params, paginate_response
from ..repositories.sql_repo import sql_repo
from ..services.log_service import LogService

log_bp = Blueprint('log', __name__)


@log_bp.route('/logs', methods=['GET'])
@require_dev
def get_logs():
    """查询操作日志（分页+过滤）—— 仅开发者"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        page_size = min(page_size, 100)

        result = LogService.query(
            page=page,
            page_size=page_size,
            user_id=request.args.get('user_id', type=int),
            action=request.args.get('action'),
            module=request.args.get('module'),
            result=request.args.get('result'),
            keyword=request.args.get('keyword'),
            start_date=request.args.get('start_date'),
            end_date=request.args.get('end_date')
        )
        return ok(result)
    except Exception as e:
        return fail(str(e))


@log_bp.route('/logs/error', methods=['POST'])
@rate_limit(max_requests=30, window_seconds=60)
def log_frontend_error():
    """接收前端错误上报——无需认证"""
    try:
        data = request.get_json(silent=True) or {}
        LogService.log_error(
            source='frontend',
            action='frontend_error',
            module=data.get('module', 'frontend'),
            detail=data.get('detail', ''),
            error_type=data.get('error_type', ''),
            traceback=data.get('traceback', ''),
            endpoint=data.get('endpoint', ''),
            ip=request.remote_addr or ''
        )
        return ok({'logged': True})
    except Exception as e:
        return fail(str(e))


@log_bp.route('/logs/clear', methods=['DELETE'])
@require_dev
def clear_logs():
    """清理日志——仅开发者"""
    try:
        days = request.args.get('days', type=int)
        action = request.args.get('action')
        LogService.clear_logs(days=days, action=action)
        return ok({'cleared': True})
    except Exception as e:
        return fail(str(e))


@log_bp.route('/logs/actions', methods=['GET'])
@require_dev
def get_log_actions():
    """获取所有操作类型"""
    try:
        return ok(LogService.get_actions())
    except Exception as e:
        return fail(str(e))


@log_bp.route('/logs/modules', methods=['GET'])
@require_dev
def get_log_modules():
    """获取所有模块类型"""
    try:
        return ok(LogService.get_modules())
    except Exception as e:
        return fail(str(e))


@log_bp.route('/logs/operations', methods=['GET'])
@require_dev
def list_operation_logs():
    """查询操作审计日志（分页+筛选）—— 仅开发者"""
    page, page_size = get_pagination_params(request.args)

    condition = "WHERE 1=1"
    params = []
    for field, db_field in [('module', 'operation_module'), ('action', 'operation_type'), ('result', 'operation_result')]:
        val = request.args.get(field)
        if val:
            condition += f" AND {db_field} LIKE ?"
            params.append(f'%{val}%')

    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    if date_from:
        condition += " AND created_at >= ?"
        params.append(date_from)
    if date_to:
        condition += " AND created_at <= ?"
        params.append(date_to + ' 23:59:59')

    count_rows = sql_repo.execute_query(
        f"SELECT COUNT(*) as total FROM operation_logs {condition}", params
    )
    total = count_rows[0]['total'] if count_rows else 0

    offset = (page - 1) * page_size
    rows = sql_repo.execute_query(
        f"SELECT id, operation_type AS action, operation_module AS module, detail, operation_result AS result, created_at "
        f"FROM operation_logs {condition} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [page_size, offset]
    )
    items = [{
        'id': r['id'],
        'module': r.get('module', ''),
        'action': r.get('action', ''),
        'detail': r.get('detail', ''),
        'result': r.get('result', ''),
        'created_at': str(r['created_at']) if r.get('created_at') else '',
    } for r in rows]

    return ok(paginate_response(items, page, page_size, total))
