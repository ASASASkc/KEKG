# -*- coding: utf-8 -*-
"""全局限流器（MySQL 集中滑动窗口，多 worker/多进程共享）

替代原内存滑窗实现：内存方案在多 worker 下各自独立计数，限流形同虚设；
迁移至 MySQL 后计数集中存储，所有 worker 共享同一窗口。
"""
import time
import random
from datetime import timedelta
from functools import wraps
from flask import jsonify, request
from ..repositories.sql_repo import sql_repo

_MAX_KEY_LEN = 255


def _cleanup_old(key, window_seconds):
    """删除该 key 已过期的请求记录（概率性执行，降低每请求 DB 往返开销）"""
    if random.random() < 0.05:
        sql_repo.execute_update(
            "DELETE FROM rate_limit_logs WHERE rl_key = ? AND request_time < NOW() - INTERVAL ? SECOND",
            (key, window_seconds)
        )


def _maybe_global_cleanup():
    """概率性全表清理（1% 概率），防止表无限增长"""
    if random.random() < 0.01:
        sql_repo.execute_update(
            "DELETE FROM rate_limit_logs WHERE request_time < NOW() - INTERVAL 1 DAY"
        )


def check_limit(key, max_requests, window_seconds=60):
    """核心检查函数（供全局中间件/装饰器调用）

    返回 (is_limited, remaining, reset_at)
    """
    key = key[:_MAX_KEY_LEN]
    _cleanup_old(key, window_seconds)
    _maybe_global_cleanup()

    rows = sql_repo.execute_query(
        """SELECT COUNT(*) AS cnt, MIN(request_time) AS oldest
           FROM rate_limit_logs
           WHERE rl_key = ? AND request_time >= NOW() - INTERVAL ? SECOND""",
        (key, window_seconds)
    )
    cnt = rows[0]['cnt'] if rows and rows[0].get('cnt') is not None else 0
    if cnt >= max_requests:
        oldest = rows[0].get('oldest') if rows else None
        if oldest:
            reset_at = int((oldest + timedelta(seconds=window_seconds)).timestamp())
        else:
            reset_at = int(time.time() + window_seconds)
        return True, 0, reset_at

    sql_repo.execute_insert(
        "INSERT INTO rate_limit_logs (rl_key) VALUES (?)",
        (key,)
    )
    return False, max_requests - cnt - 1, int(time.time() + window_seconds)


def rate_limit(max_requests=10, window_seconds=60):
    """装饰器：在 window_seconds 窗口内最多 max_requests 次请求（MySQL 集中滑窗）"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                key = f"{request.remote_addr}:{request.path}"
                limited, _, _ = check_limit(key, max_requests, window_seconds)
                if limited:
                    return jsonify({
                        'code': 429, 'success': False,
                        'message': '请求过于频繁，请稍后再试'
                    }), 429
            except Exception:
                pass  # 限流故障时放行，保证业务可用
            return f(*args, **kwargs)
        return wrapper
    return decorator
