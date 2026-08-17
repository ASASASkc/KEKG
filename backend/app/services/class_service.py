# -*- coding: utf-8 -*-
"""班级管理服务"""
import random
import string
from ..repositories.sql_repo import sql_repo


class ClassService:

    @staticmethod
    def _gen_code():
        """生成6位班级码（最多重试10次防止极端碰撞）"""
        chars = string.ascii_uppercase + string.digits
        for _ in range(10):
            code = ''.join(random.choices(chars, k=6))
            exist = sql_repo.execute_query(
                "SELECT id FROM classes WHERE class_code = ?", (code,))
            if not exist:
                return code
        raise RuntimeError('无法生成唯一班级码，请稍后重试')

    @staticmethod
    def create(name, description, teacher_id):
        if not name or not name.strip():
            raise ValueError('班级名称不能为空')
        code = ClassService._gen_code()
        cid = sql_repo.execute_insert(
            """INSERT INTO classes (name, description, class_code, teacher_id)
               VALUES (?, ?, ?, ?)""",
            (name.strip(), description or '', code, teacher_id)
        )
        return {'id': cid, 'name': name.strip(), 'class_code': code}

    @staticmethod
    def update(cid, name=None, description=None):
        fields = []
        params = []
        if name:
            fields.append("name = ?")
            params.append(name.strip())
        if description is not None:
            fields.append("description = ?")
            params.append(description)
        if fields:
            params.append(cid)
            sql_repo.execute_update(
                f"UPDATE classes SET {', '.join(fields)} WHERE id = ?", params)
        return True

    @staticmethod
    def delete(cid):
        sql_repo.begin_transaction()
        try:
            # 级联删除：先查该班级下所有考试
            cur = sql_repo.execute_query("SELECT id FROM exam_papers WHERE class_id = ?", (cid,))
            exam_ids = [r['id'] for r in cur]
            for eid in exam_ids:
                sql_repo.execute_update("DELETE FROM exam_answers WHERE exam_id = ?", (eid,))
                sql_repo.execute_update("DELETE FROM exam_submissions WHERE exam_id = ?", (eid,))
                sql_repo.execute_update("DELETE FROM exam_questions WHERE exam_id = ?", (eid,))
                sql_repo.execute_update("DELETE FROM exam_papers WHERE id = ?", (eid,))
            sql_repo.execute_update("DELETE FROM class_students WHERE class_id = ?", (cid,))
            sql_repo.execute_update("DELETE FROM classes WHERE id = ?", (cid,))
            sql_repo.commit_transaction()
        except Exception:
            sql_repo.rollback_transaction()
            raise

    @staticmethod
    def get_by_id(cid):
        rows = sql_repo.execute_query("SELECT * FROM classes WHERE id = ?", (cid,))
        if not rows:
            return None
        return ClassService._format_class(rows[0])

    @staticmethod
    def get_teacher_classes(teacher_id):
        rows = sql_repo.execute_query(
            "SELECT * FROM classes WHERE teacher_id = ? ORDER BY id DESC", (teacher_id,))
        return [ClassService._format_class(r) for r in rows]

    @staticmethod
    def get_student_classes(student_id):
        rows = sql_repo.execute_query(
            """SELECT c.* FROM classes c
               JOIN class_students cs ON c.id = cs.class_id
               WHERE cs.student_id = ? ORDER BY c.id DESC""",
            (student_id,))
        return [ClassService._format_class(r) for r in rows]

    @staticmethod
    def join(class_code, student_id):
        rows = sql_repo.execute_query(
            "SELECT id, teacher_id FROM classes WHERE class_code = ?", (class_code,))
        if not rows:
            raise ValueError('班级码无效')
        cls = rows[0]
        if cls['teacher_id'] == student_id:
            raise ValueError('教师不能加入自己创建的班级')
        exist = sql_repo.execute_query(
            "SELECT id FROM class_students WHERE class_id = ? AND student_id = ?",
            (cls['id'], student_id))
        if exist:
            raise ValueError('已在班级中')
        sql_repo.execute_insert(
            "INSERT INTO class_students (class_id, student_id) VALUES (?, ?)",
            (cls['id'], student_id))
        return ClassService.get_by_id(cls['id'])

    @staticmethod
    def remove_student(cid, student_id):
        cls = sql_repo.execute_query(
            "SELECT name FROM classes WHERE id = ?", (cid,))
        sql_repo.execute_update(
            "DELETE FROM class_students WHERE class_id = ? AND student_id = ?",
            (cid, student_id))
        if cls:
            from .notification_service import notification_service
            notification_service.send(
                student_id, 'class_removed', f'你已被移出班级「{cls[0]["name"]}」',
                '', related_id=cid, related_type='class')

    @staticmethod
    def leave_class(cid, student_id):
        """学生主动退出班级（不能是教师）"""
        cls = sql_repo.execute_query(
            "SELECT teacher_id FROM classes WHERE id = ?", (cid,))
        if not cls:
            raise ValueError('班级不存在')
        if cls[0]['teacher_id'] == student_id:
            raise ValueError('教师不能退出自己创建的班级，请解散班级')
        affected = sql_repo.execute_update(
            "DELETE FROM class_students WHERE class_id = ? AND student_id = ?",
            (cid, student_id))
        if affected == 0:
            raise ValueError('你不在该班级中')
        return {'success': True}

    # ── 公告 ──

    @staticmethod
    def get_announcements(cid):
        rows = sql_repo.execute_query(
            """SELECT ca.*, u.username as creator_name
               FROM class_announcements ca
               LEFT JOIN users u ON ca.created_by = u.id
               WHERE ca.class_id = ? AND ca.status = 'active'
               ORDER BY ca.is_pinned DESC, ca.created_at DESC""",
            (cid,))
        return [dict(r) for r in rows]

    @staticmethod
    def create_announcement(cid, title, content, created_by, is_pinned=0):
        if not title or not title.strip():
            raise ValueError('公告标题不能为空')
        aid = sql_repo.execute_insert(
            """INSERT INTO class_announcements (class_id, title, content, created_by, is_pinned)
               VALUES (?, ?, ?, ?, ?)""",
            (cid, title.strip(), content or '', created_by, is_pinned))
        # 通知班级学生有新公告
        rows = sql_repo.execute_query(
            "SELECT student_id FROM class_students WHERE class_id = ?", (cid,))
        if rows:
            from .notification_service import notification_service
            notification_service.send_many(
                [r['student_id'] for r in rows], 'announcement',
                f'新公告：{title.strip()}', content or '',
                related_id=aid, related_type='announcement')
        return {'id': aid, 'title': title.strip()}

    @staticmethod
    def delete_announcement(aid):
        sql_repo.execute_update(
            "UPDATE class_announcements SET status = 'deleted' WHERE id = ?", (aid,))
        return {'success': True}

    # ── 分组 ──

    @staticmethod
    def get_groups(cid):
        rows = sql_repo.execute_query(
            """SELECT sg.*, (SELECT COUNT(*) FROM student_group_members sgm WHERE sgm.group_id = sg.id) as member_count
               FROM student_groups sg
               WHERE sg.class_id = ?
               ORDER BY sg.id""",
            (cid,))
        return [dict(r) for r in rows]

    @staticmethod
    def create_group(cid, name, description='', created_by=None):
        if not name or not name.strip():
            raise ValueError('分组名称不能为空')
        gid = sql_repo.execute_insert(
            "INSERT INTO student_groups (class_id, name, description, created_by) VALUES (?, ?, ?, ?)",
            (cid, name.strip(), description or '', created_by))
        return {'id': gid, 'name': name.strip()}

    @staticmethod
    def delete_group(gid):
        sql_repo.execute_update("DELETE FROM student_group_members WHERE group_id = ?", (gid,))
        sql_repo.execute_update("DELETE FROM student_groups WHERE id = ?", (gid,))
        return {'success': True}

    @staticmethod
    def get_group_members(gid):
        rows = sql_repo.execute_query(
            """SELECT u.id, u.username, u.email FROM student_group_members sgm
               JOIN users u ON sgm.student_id = u.id
               WHERE sgm.group_id = ? ORDER BY u.username""",
            (gid,))
        return [dict(r) for r in rows]

    @staticmethod
    def add_group_member(gid, student_id):
        try:
            sql_repo.execute_insert(
                "INSERT INTO student_group_members (group_id, student_id) VALUES (?, ?)",
                (gid, student_id))
        except Exception:
            raise ValueError('学生已在分组中或不存在')
        return {'success': True}

    @staticmethod
    def remove_group_member(gid, student_id):
        sql_repo.execute_update(
            "DELETE FROM student_group_members WHERE group_id = ? AND student_id = ?",
            (gid, student_id))
        return {'success': True}

    @staticmethod
    def get_students(cid):
        rows = sql_repo.execute_query(
            """SELECT u.id, u.username, u.email, cs.joined_at FROM class_students cs
               JOIN users u ON cs.student_id = u.id
               WHERE cs.class_id = ? ORDER BY cs.joined_at""",
            (cid,))
        return [dict(r) for r in rows]

    @staticmethod
    def _format_class(row):
        r = dict(row)
        # 统计班级学生数，排除教师本人 + 只统计有效用户
        r['student_count'] = sql_repo.execute_query(
            """SELECT COUNT(*) as cnt FROM class_students cs
               JOIN users u ON cs.student_id = u.id
               WHERE cs.class_id = ? AND cs.student_id != ?""",
            (r['id'], r['teacher_id']))[0]['cnt']
        return r


class_service = ClassService()
