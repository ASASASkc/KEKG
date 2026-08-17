# -*- coding: utf-8 -*-
"""
后台任务管理器 — 使用 ThreadPoolExecutor 异步执行耗时操作（LLM 调用等）
"""
import uuid
import time
import json
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any, Dict, Optional
import logging

_logger = logging.getLogger('task_manager')

# 线程池（12 个并发后台任务，适配班级规模）
_executor = ThreadPoolExecutor(max_workers=12, thread_name_prefix='bg-task')

def _task_from_db_row(row: Optional[dict]) -> Optional[dict]:
    if not row:
        return None
    return {
        'task_id': row['task_id'],
        'type': row['task_type'],
        'status': row['status'],
        'progress': row.get('progress', 0) or 0,
        'result': json.loads(row['result']) if row.get('result') else None,
        'error': row.get('error'),
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }

# 任务过期时间（24 小时）
_TASK_TTL = 86400


def submit(task_type: str, fn: Callable, *args, **kwargs) -> str:
    """
    提交后台任务，返回 task_id。
    前端通过 GET /api/tasks/<task_id>/status 轮询结果。
    """
    from ..repositories.sql_repo import sql_repo
    task_id = str(uuid.uuid4())
    now = time.time()
    sql_repo.execute_insert(
        "INSERT INTO bg_tasks (task_id, task_type, status, progress, result, error, created_at, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, FROM_UNIXTIME(%s), FROM_UNIXTIME(%s))",
        (task_id, task_type, 'pending', 0, None, None, now, now)
    )
    _executor.submit(_run, task_id, fn, *args, **kwargs)
    return task_id


def _run(task_id: str, fn: Callable, *args, **kwargs):
    from ..repositories.sql_repo import sql_repo
    now = time.time()
    sql_repo.execute_update(
        "UPDATE bg_tasks SET status = %s, updated_at = FROM_UNIXTIME(%s) WHERE task_id = %s",
        ('running', now, task_id)
    )
    try:
        result = fn(*args, **kwargs)
        result_json = json.dumps(result, ensure_ascii=False) if result is not None else None
        now = time.time()
        sql_repo.execute_update(
            "UPDATE bg_tasks SET status = %s, result = %s, progress = %s, updated_at = FROM_UNIXTIME(%s) WHERE task_id = %s",
            ('done', result_json, 100, now, task_id)
        )
    except Exception as e:
        _logger.error('[TaskManager] task %s failed: %s', task_id, str(e))
        err_msg = str(e)[:500]
        now = time.time()
        sql_repo.execute_update(
            "UPDATE bg_tasks SET status = %s, error = %s, updated_at = FROM_UNIXTIME(%s) WHERE task_id = %s",
            ('failed', err_msg, now, task_id)
        )


def get_status(task_id: str) -> Optional[dict]:
    """获取任务状态"""
    from ..repositories.sql_repo import sql_repo
    rows = sql_repo.execute_query(
        "SELECT * FROM bg_tasks WHERE task_id = %s", (task_id,)
    )
    if not rows:
        return None
    row = rows[0]
    return {
        'task_id': row['task_id'],
        'type': row.get('task_type', ''),
        'status': row.get('status', 'unknown'),
        'progress': row.get('progress', 0) or 0,
        'result': json.loads(row['result']) if row.get('result') else None,
        'error': row.get('error'),
        'created_at': row['created_at'].timestamp() if hasattr(row['created_at'], 'timestamp') else time.time(),
        'updated_at': row['updated_at'].timestamp() if hasattr(row['updated_at'], 'timestamp') else time.time(),
    }


def cleanup_expired():
    """清理过期任务（可被定时任务调用）"""
    from ..repositories.sql_repo import sql_repo
    sql_repo.execute_update(
        "DELETE FROM bg_tasks WHERE updated_at < DATE_SUB(NOW(), INTERVAL %s SECOND)",
        (_TASK_TTL,)
    )
