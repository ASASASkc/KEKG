# -*- coding: utf-8 -*-
"""操作日志服务 — 记录与查询"""

from datetime import datetime
from ..repositories.sql_repo import sql_repo


class LogService:

    @staticmethod
    def log(user_id, username, action, module='', detail='', ip='', result='success'):
        """记录一条操作日志"""
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sql_repo.execute_insert(
            """INSERT INTO operation_logs (user_id, username, operation_type, operation_module, detail, operation_ip, operation_result, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, action, module, detail, ip, result, ts)
        )

    @staticmethod
    def log_error(source='backend', action='system_error', module='system',
                  detail='', error_type='', traceback='', endpoint='', ip=''):
        """记录系统错误（前端或后端）"""
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        full_detail = f'[{source}] {detail}'
        if error_type:
            full_detail += f' | type={error_type}'
        if traceback:
            full_detail += f' | trace={traceback[:800]}'
        if endpoint:
            full_detail += f' | endpoint={endpoint}'
        sql_repo.execute_insert(
            """INSERT INTO operation_logs (user_id, username, operation_type, operation_module, detail, operation_ip, operation_result, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (0, 'system', action, module, full_detail, ip, 'error', ts)
        )

    @staticmethod
    def clear_logs(days=None, action=None):
        """清理日志
        days: 删除 N 天前的日志（None 表示全部）
        action: 仅删除特定操作类型的日志
        """
        conditions = []
        params = []
        if days:
            conditions.append("created_at < DATE_SUB(NOW(), INTERVAL ? DAY)")
            params.append(int(days))
        if action:
            conditions.append("operation_type = ?")
            params.append(action)
        if not conditions:
            sql_repo.execute_update("DELETE FROM operation_logs")
            return

        where = ' WHERE ' + ' AND '.join(conditions)
        sql_repo.execute_update(f"DELETE FROM operation_logs {where}", params)

    @staticmethod
    def query(page=1, page_size=20, user_id=None, action=None, module=None,
              result=None, keyword=None, start_date=None, end_date=None):
        """分页查询操作日志，支持多条件过滤"""
        conditions = []
        params = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(int(user_id))
        if action:
            conditions.append("operation_type = ?")
            params.append(action)
        if module:
            conditions.append("operation_module LIKE ?")
            params.append(f'%{module}%')
        if result:
            conditions.append("operation_result = ?")
            params.append(result)
        if keyword:
            conditions.append("(detail LIKE ? OR username LIKE ?)")
            params.extend([f'%{keyword}%', f'%{keyword}%'])
        if start_date:
            conditions.append("created_at >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("created_at <= ?")
            params.append(end_date + ' 23:59:59')

        where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''

        # 总数
        total_row = sql_repo.execute_query(
            f"SELECT COUNT(*) AS cnt FROM operation_logs {where}", params
        )
        total = total_row[0]['cnt'] if total_row else 0

        # 分页数据
        offset = (page - 1) * page_size
        rows = sql_repo.execute_query(
            f"""SELECT id, user_id, username, operation_type AS action, operation_module AS module,
                       detail, operation_ip AS ip, operation_result AS result, created_at
                FROM operation_logs {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?""",
            params + [page_size, offset]
        )

        return {
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': max(1, (total + page_size - 1) // page_size),
            'items': rows
        }

    @staticmethod
    def get_actions():
        """返回所有操作类型列表（去重）"""
        rows = sql_repo.execute_query(
            "SELECT DISTINCT operation_type FROM operation_logs ORDER BY operation_type"
        )
        return [r['operation_type'] for r in rows]

    @staticmethod
    def get_modules():
        """返回所有模块列表（去重）"""
        rows = sql_repo.execute_query(
            "SELECT DISTINCT operation_module FROM operation_logs ORDER BY operation_module"
        )
        return [r['operation_module'] for r in rows]
