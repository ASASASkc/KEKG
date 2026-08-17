# -*- coding: utf-8 -*-
"""学习资源管理服务"""
from ..repositories.sql_repo import sql_repo
from ..repositories.graph_repo import graph_repo


class ResourceService:

    TYPES = ['doc', 'video', 'link', 'exercise', 'project']
    TYPE_LABELS = {'doc': '文档', 'video': '视频', 'link': '链接', 'exercise': '练习', 'project': '项目'}

    @staticmethod
    def create(title, rtype, knowledge_point_id, url='', content='', tags='', created_by=1):
        if not title or not title.strip():
            raise ValueError('标题不能为空')
        if rtype not in ResourceService.TYPES:
            raise ValueError(f'无效类型: {rtype}')
        if not knowledge_point_id:
            raise ValueError('请指定关联知识点')

        rid = sql_repo.execute_insert(
            """INSERT INTO learning_resources (title, type, url, content, knowledge_point_id,
               tags, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (title.strip(), rtype, url or '', content or '', knowledge_point_id,
             tags or '', created_by)
        )
        return {'id': rid, 'title': title.strip()}

    @staticmethod
    def update(rid, **kwargs):
        e = sql_repo.execute_query("SELECT * FROM learning_resources WHERE id = ?", (rid,))
        if not e:
            raise ValueError('资源不存在')

        fields = []
        params = []
        for k in ('title', 'type', 'url', 'content', 'knowledge_point_id', 'tags'):
            if k in kwargs:
                fields.append(f"{k} = ?")
                params.append(kwargs[k] if kwargs[k] else '')

        if fields:
            params.append(rid)
            sql_repo.execute_update(f"UPDATE learning_resources SET {', '.join(fields)} WHERE id = ?", params)
        return True

    @staticmethod
    def delete(rid):
        sql_repo.execute_update("DELETE FROM learning_resources WHERE id = ?", (rid,))

    @staticmethod
    def batch_delete(ids):
        placeholders = ','.join('?' * len(ids))
        sql_repo.execute_update(f"DELETE FROM learning_resources WHERE id IN ({placeholders})", ids)

    @staticmethod
    def get_by_id(rid):
        rows = sql_repo.execute_query("SELECT * FROM learning_resources WHERE id = ?", (rid,))
        return dict(rows[0]) if rows else None

    @staticmethod
    def query(page=1, page_size=20, rtype='', knowledge_point_id='', keyword=''):
        conditions = ["status = 'active'"]
        params = []

        if rtype:
            conditions.append("type = ?")
            params.append(rtype)
        if knowledge_point_id:
            conditions.append("knowledge_point_id = ?")
            params.append(knowledge_point_id)
        if keyword:
            conditions.append("(title LIKE ? OR tags LIKE ?)")
            params.extend([f'%{keyword}%', f'%{keyword}%'])

        where = "WHERE " + " AND ".join(conditions)
        total = sql_repo.execute_query(f"SELECT COUNT(*) as cnt FROM learning_resources {where}", params)
        total = total[0]['cnt'] if total else 0

        offset = (page - 1) * page_size
        rows = sql_repo.execute_query(
            f"SELECT * FROM learning_resources {where} ORDER BY type, id DESC LIMIT ? OFFSET ?",
            params + [page_size, offset]
        )
        return {
            'items': [dict(r) for r in rows],
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': max(1, (total + page_size - 1) // page_size)
        }

    @staticmethod
    def get_by_knowledge_point(knowledge_point_id):
        """按知识点获取资源（学习路径推送用）"""
        rows = sql_repo.execute_query(
            """SELECT * FROM learning_resources
               WHERE knowledge_point_id = ? AND status = 'active'
               ORDER BY type""",
            (knowledge_point_id,)
        )
        return [dict(r) for r in rows]

    @staticmethod
    def get_for_path(knowledge_point_ids):
        """批量按知识点获取资源"""
        if not knowledge_point_ids:
            return {}
        placeholders = ','.join('?' * len(knowledge_point_ids))
        rows = sql_repo.execute_query(
            f"""SELECT * FROM learning_resources
                WHERE knowledge_point_id IN ({placeholders})
                  AND status = 'active'
                ORDER BY type""",
            knowledge_point_ids
        )
        result = {}
        for r in rows:
            d = dict(r)
            kpid = d['knowledge_point_id']
            if kpid not in result:
                result[kpid] = []
            result[kpid].append(d)
        return result

    @staticmethod
    def import_markdown(text: str, created_by=1):
        """从 Markdown 文本导入学习资源"""
        from ..utils.markdown_helper import parse_resources_markdown
        result = parse_resources_markdown(text, created_by)
        resources = result.get('resources', [])
        errors = result.get('errors', [])

        sql_repo.begin_transaction()
        try:
            success = 0
            skipped = 0
            for r in resources:
                try:
                    rows = sql_repo.execute_query(
                        "SELECT id FROM learning_resources WHERE title = ?",
                        (r['title'],))
                    if rows:
                        skipped += 1
                        continue
                    ResourceService.create(**r)
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
                    'errors': errors,
                    'total_rows': result.get('total_rows', 0),
                }
            sql_repo.commit_transaction()
            return {
                'success_count': success,
                'skipped_count': skipped,
                'error_count': len(errors),
                'errors': errors,
                'total_rows': result.get('total_rows', 0),
            }
        except Exception:
            sql_repo.rollback_transaction()
            raise
