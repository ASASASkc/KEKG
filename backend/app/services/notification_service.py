# -*- coding: utf-8 -*-
"""站内通知服务"""
from ..repositories.sql_repo import sql_repo


class NotificationService:

    @staticmethod
    def send(user_id, ntype, title, content='', related_id=0, related_type=''):
        """发送一条站内通知"""
        sql_repo.execute_insert(
            """INSERT INTO notifications (user_id, type, title, content, related_id, related_type)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, ntype, title, content or '', related_id, related_type))

    @staticmethod
    def send_many(user_ids, ntype, title, content='', related_id=0, related_type=''):
        """同一事件批量通知多个用户（去重）"""
        for uid in set(user_ids):
            NotificationService.send(uid, ntype, title, content, related_id, related_type)

    @staticmethod
    def list(user_id, page=1, page_size=20):
        """分页查询用户通知"""
        page = max(1, page)
        page_size = min(max(1, page_size), 50)
        offset = (page - 1) * page_size
        rows = sql_repo.execute_query(
            """SELECT id, type, title, content, related_id, related_type, is_read, created_at
               FROM notifications
               WHERE user_id = ?
               ORDER BY created_at DESC, id DESC
               LIMIT ? OFFSET ?""",
            (user_id, page_size, offset))
        total_row = sql_repo.execute_query(
            "SELECT COUNT(*) AS cnt FROM notifications WHERE user_id = ?", (user_id,))
        total = total_row[0]['cnt'] if total_row else 0
        return {
            'items': [dict(r) for r in rows],
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': max(1, (total + page_size - 1) // page_size),
        }

    @staticmethod
    def unread_count(user_id):
        rows = sql_repo.execute_query(
            "SELECT COUNT(*) AS cnt FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,))
        return rows[0]['cnt'] if rows else 0

    @staticmethod
    def mark_read(user_id, nid):
        """标记单条通知已读（仅本人）"""
        sql_repo.execute_update(
            "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (nid, user_id))

    @staticmethod
    def mark_all_read(user_id):
        """全部标记已读"""
        sql_repo.execute_update(
            "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (user_id,))


# 全局单例
notification_service = NotificationService()
