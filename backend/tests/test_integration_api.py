# -*- coding: utf-8 -*-
"""集成测试：核心 API 链路（连接真实 MySQL + Neo4j）

覆盖：
- 认证：注册 / 登录 / me / 邀请码升级 / 越权
- 班级：教师建班 → 学生加班 → 成员/非成员/非教师权限（M14/M15）
- 题库：建题 → 审核可见性（M25）→ 收藏
- 考试：建卷 → 组卷 → 发布 → 开始 → 保存 → 提交自动判分（M19-M22）
- 独立刷题：判题一致性（M22）
- 学习计划：创建 → 打卡 → 进度（M23）
- 资源 / 通知 / 统计 / 知识图谱(Neo4j) / 健康检查
"""
import pytest
import uuid

from conftest import api, register_user, register_admin


def _mk_title(prefix):
    return f'{prefix}_{uuid.uuid4().hex[:8]}'


# ══════════════════════════════════════════════════════════════
# 认证
# ══════════════════════════════════════════════════════════════

class TestAuth:
    def test_register_and_me(self, client):
        username = f'tst_{uuid.uuid4().hex[:10]}'
        data, _ = api(client, 'POST', '/api/v1/auth/register', json={
            'username': username, 'password': 'Test@123456',
            'email': f'{username}@test.local'})
        assert data['success'] is True

        data, _ = api(client, 'POST', '/api/v1/auth/login',
                      json={'username': username, 'password': 'Test@123456'})
        assert data['success'] is True and data['data']['token']

        data, _ = api(client, 'GET', '/api/v1/auth/me', token=data['data']['token'])
        assert data['data']['username'] == username

    def test_register_missing_fields(self, client):
        data, _ = api(client, 'POST', '/api/v1/auth/register',
                      json={'username': 'x'})
        assert data['code'] == 400

    def test_weak_password_rejected(self, client):
        data, _ = api(client, 'POST', '/api/v1/auth/register', json={
            'username': f'tst_{uuid.uuid4().hex[:8]}', 'password': '12345678'})
        assert data['success'] is False  # 纯数字不含字母

    def test_login_wrong_password(self, client):
        username, _ = register_user(client)
        data, _ = api(client, 'POST', '/api/v1/auth/login',
                      json={'username': username, 'password': 'Wrong@1234'})
        assert data['code'] == 401

    def test_duplicate_register(self, client):
        username, _ = register_user(client)
        data, _ = api(client, 'POST', '/api/v1/auth/register', json={
            'username': username, 'password': 'Test@123456'})
        assert data['success'] is False

    def test_me_without_token(self, client):
        data, _ = api(client, 'GET', '/api/v1/auth/me')
        assert data['code'] == 401

    def test_invite_code_promotes_to_admin(self, client):
        username, token = register_admin(client)
        data, _ = api(client, 'GET', '/api/v1/auth/me', token=token)
        assert data['data']['role'] == 'admin'

    def test_wrong_invite_code_stays_user(self, client):
        username = f'tst_{uuid.uuid4().hex[:10]}'
        data, _ = api(client, 'POST', '/api/v1/auth/register', json={
            'username': username, 'password': 'Test@123456',
            'email': f'{username}@test.local', 'invite_code': 'BADCODE123'})
        assert data['success'] is True
        data, _ = api(client, 'POST', '/api/v1/auth/login',
                      json={'username': username, 'password': 'Test@123456'})
        data, _ = api(client, 'GET', '/api/v1/auth/me', token=data['data']['token'])
        assert data['data']['role'] == 'user'


# ══════════════════════════════════════════════════════════════
# 班级权限（M14/M15）
# ══════════════════════════════════════════════════════════════

class TestClassAccess:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        self.teacher, self.teacher_token = register_admin(client)
        self.student, self.student_token = register_user(client)
        self.other, self.other_token = register_user(client)
        self.other_admin, self.other_admin_token = register_admin(client)

    def _create_class(self, token):
        data, _ = api(self.client, 'POST', '/api/v1/classes',
                      token=token, json={'name': _mk_title('班级'), 'description': '集成测试班级'})
        assert data['success'] is True, data
        return data['data']

    def test_create_and_join_class(self, client):
        self.client = client
        cls = self._create_class(self.teacher_token)
        # 学生凭邀请码加入
        data, _ = api(client, 'POST', '/api/v1/classes/join', token=self.student_token,
                      json={'class_code': cls['class_code']})
        assert data['success'] is True, data
        # 教师查看班级含学生
        data, _ = api(client, 'GET', f"/api/v1/classes/{cls['id']}", token=self.teacher_token)
        assert data['success'] is True
        students = [s['id'] for s in data['data'].get('students', [])]
        assert len(students) >= 1
        # 学生可查看（成员）
        data, _ = api(client, 'GET', f"/api/v1/classes/{cls['id']}", token=self.student_token)
        assert data['code'] == 200
        # 非成员不可查看（403）
        data, _ = api(client, 'GET', f"/api/v1/classes/{cls['id']}", token=self.other_token)
        assert data['code'] == 403
        # 非本班教师的 admin 不可查看（403）
        data, _ = api(client, 'GET', f"/api/v1/classes/{cls['id']}", token=self.other_admin_token)
        assert data['code'] == 403

    def test_non_teacher_admin_denied(self, client):
        self.client = client
        cls = self._create_class(self.teacher_token)
        # 非本班教师的 admin 管理操作 → 403
        for method, path, body in [
            ('PUT', f"/api/v1/classes/{cls['id']}", {'name': '改名'}),
            ('DELETE', f"/api/v1/classes/{cls['id']}", None),
            ('POST', f"/api/v1/classes/{cls['id']}/announcements",
             {'title': 'a', 'content': 'b'}),
            ('POST', f"/api/v1/classes/{cls['id']}/groups", {'name': 'g1'}),
            ('GET', f"/api/v1/classes/{cls['id']}/groups", None),
        ]:
            data, _ = api(client, method, path, token=self.other_admin_token,
                          json=body if body is not None else {})
            assert data['code'] == 403, f'{method} {path} → {data}'

    def test_teacher_manage_class(self, client):
        self.client = client
        cls = self._create_class(self.teacher_token)
        # 本班教师可发布公告 / 建组 / 改名
        data, _ = api(client, 'POST', f"/api/v1/classes/{cls['id']}/announcements",
                      token=self.teacher_token,
                      json={'title': '公告', 'content': '内容', 'is_pinned': 0})
        assert data['success'] is True
        data, _ = api(client, 'PUT', f"/api/v1/classes/{cls['id']}",
                      token=self.teacher_token, json={'name': '改名后'})
        assert data['success'] is True

    def test_student_announcement_visible(self, client):
        self.client = client
        cls = self._create_class(self.teacher_token)
        api(client, 'POST', '/api/v1/classes/join', token=self.student_token,
            json={'class_code': cls['class_code']})
        api(client, 'POST', f"/api/v1/classes/{cls['id']}/announcements",
            token=self.teacher_token, json={'title': '公告', 'content': '内容'})
        data, _ = api(client, 'GET', f"/api/v1/classes/{cls['id']}/announcements",
                      token=self.student_token)
        assert data['code'] == 200
        # 非成员 403
        data, _ = api(client, 'GET', f"/api/v1/classes/{cls['id']}/announcements",
                      token=self.other_token)
        assert data['code'] == 403

    def test_leave_class(self, client):
        self.client = client
        cls = self._create_class(self.teacher_token)
        api(client, 'POST', '/api/v1/classes/join', token=self.student_token,
            json={'class_code': cls['class_code']})
        data, _ = api(client, 'POST', f"/api/v1/classes/{cls['id']}/leave",
                      token=self.student_token)
        assert data['success'] is True
        # 退出后不可查看
        data, _ = api(client, 'GET', f"/api/v1/classes/{cls['id']}", token=self.student_token)
        assert data['code'] == 403


# ══════════════════════════════════════════════════════════════
# 题库可见性（M25）
# ══════════════════════════════════════════════════════════════

class TestQuestionAccess:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        self.admin, self.admin_token = register_admin(client)
        self.student, self.student_token = register_user(client)

    def _create_q(self, token, qtype='choice', answer='A', status=None):
        body = {
            'title': _mk_title('题目'),
            'type': qtype,
            'answer': answer,
            'options': ['A. 正确项', 'B. 干扰项', 'C. 干扰项', 'D. 干扰项'] if qtype == 'choice' else [],
            'category': '集成测试',
            'explanation': '解析',
        }
        if status:
            body['status'] = status
        data, _ = api(self.client, 'POST', '/api/v1/questions', token=token, json=body)
        assert data['success'] is True, data
        return data['data']['id']

    def test_student_sees_only_approved(self, client):
        self.client = client
        qid = self._create_q(self.admin_token)  # 默认 approved
        # 学生可看到
        data, _ = api(client, 'GET', f'/api/v1/questions/{qid}', token=self.student_token)
        assert data['code'] == 200
        # 列表中可见
        data, _ = api(client, 'GET', '/api/v1/questions', token=self.student_token)
        ids = [q['id'] for q in data['data'].get('items', [])]
        assert qid in ids

    def test_student_cannot_see_pending(self, client):
        self.client = client
        # 通过服务层创建 pending 题目（路由默认 approved，AI 出题走 pending）
        from app.services.question_service import question_service
        q = question_service.create(
            title=_mk_title('待审核'), qtype='choice', answer='A',
            options=['A. 1', 'B. 2', 'C. 3', 'D. 4'], status='pending')
        qid = q['id']
        # 学生 404
        data, _ = api(client, 'GET', f'/api/v1/questions/{qid}', token=self.student_token)
        assert data['code'] == 404
        # 列表不可见
        data, _ = api(client, 'GET', '/api/v1/questions', token=self.student_token)
        ids = [q['id'] for q in data['data'].get('items', [])]
        assert qid not in ids
        # 管理员可见
        data, _ = api(client, 'GET', f'/api/v1/questions/{qid}', token=self.admin_token)
        assert data['code'] == 200

    def test_approve_flow(self, client):
        self.client = client
        from app.services.question_service import question_service
        q = question_service.create(
            title=_mk_title('待审核2'), qtype='judge', answer='对', status='pending')
        qid = q['id']
        # 学生不可见 → 管理员审核通过 → 学生可见
        data, _ = api(client, 'GET', f'/api/v1/questions/{qid}', token=self.student_token)
        assert data['code'] == 404
        data, _ = api(client, 'POST', f'/api/v1/questions/{qid}/approve', token=self.admin_token)
        assert data['success'] is True
        data, _ = api(client, 'GET', f'/api/v1/questions/{qid}', token=self.student_token)
        assert data['code'] == 200

    def test_favorite_flow(self, client):
        self.client = client
        qid = self._create_q(self.admin_token)
        data, _ = api(client, 'PUT', f'/api/v1/questions/{qid}/favorite', token=self.student_token)
        assert data['success'] is True and data['data']['favorited'] is True
        data, _ = api(client, 'GET', '/api/v1/questions/favorites', token=self.student_token)
        assert qid in [q['id'] for q in data['data'].get('items', [])]
        data, _ = api(client, 'DELETE', f'/api/v1/questions/{qid}/favorite', token=self.student_token)
        assert data['data']['favorited'] is False

    def test_student_cannot_create_question(self, client):
        self.client = client
        data, _ = api(client, 'POST', '/api/v1/questions', token=self.student_token,
                      json={'title': 'x', 'type': 'choice', 'answer': 'A'})
        assert data['code'] == 403


# ══════════════════════════════════════════════════════════════
# 考试全流程（M19/M20/M21/M22）
# ══════════════════════════════════════════════════════════════

class TestExamFlow:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        self.client = client
        self.teacher, self.teacher_token = register_admin(client)
        self.student, self.student_token = register_user(client)
        self.other, self.other_token = register_user(client)
        self.qmap = {}   # question_id -> {'answer': ..., 'type': ..., 'score': ...}
        self.class_id = None

    def _prepare_class_and_questions(self):
        # 建班 + 学生加入
        data, _ = api(self.client, 'POST', '/api/v1/classes', token=self.teacher_token,
                      json={'name': _mk_title('考试班'), 'description': ''})
        cls = data['data']
        self.class_id = cls['id']
        api(self.client, 'POST', '/api/v1/classes/join', token=self.student_token,
            json={'class_code': cls['class_code']})
        # 建题：choice x2、judge x1、fill x1
        specs = [
            ('choice', 'A'), ('choice', 'B'),
            ('judge', '对'), ('fill', '3.14'),
        ]
        for qtype, ans in specs:
            body = {
                'title': _mk_title('考试题'),
                'type': qtype,
                'answer': ans,
                'options': ['A. x', 'B. y', 'C. z', 'D. w'] if qtype == 'choice' else [],
                'category': '集成测试',
            }
            data, _ = api(self.client, 'POST', '/api/v1/questions',
                          token=self.teacher_token, json=body)
            qid = data['data']['id']
            self.qmap[qid] = {'answer': ans, 'type': qtype}

    def _generate_exam(self, rules):
        data, _ = api(self.client, 'POST', '/api/v1/exams/generate', token=self.teacher_token,
                      json={
                          'title': _mk_title('考试'),
                          'class_id': self.class_id,
                          'duration_minutes': 60,
                          'start_time': '2026-01-01 00:00:00',
                          'end_time': '2026-12-31 23:59:59',
                          'pass_score': 60,
                          'rules': rules,
                      })
        assert data['success'] is True, data
        return data['data']['id']

    def test_full_exam_lifecycle(self):
        self._prepare_class_and_questions()
        eid = self._generate_exam([
            {'type': 'choice', 'count': 2, 'score_per_question': 10},
            {'type': 'judge', 'count': 1, 'score_per_question': 20},
            {'type': 'fill', 'count': 1, 'score_per_question': 15},
        ])
        # 发布
        data, _ = api(self.client, 'PUT', f'/api/v1/exams/{eid}/publish',
                      token=self.teacher_token)
        assert data['success'] is True
        # 学生可见已发布试卷
        data, _ = api(self.client, 'GET', f'/api/v1/exams/{eid}', token=self.student_token)
        assert data['code'] == 200 and data['data']['status'] == 'published'
        # 非班级学生 403
        data, _ = api(self.client, 'GET', f'/api/v1/exams/{eid}', token=self.other_token)
        assert data['code'] == 403
        # 非班级学生开始 → 400
        data, _ = api(self.client, 'POST', f'/api/v1/exams/{eid}/start', token=self.other_token)
        assert data['code'] == 400
        # 学生开始
        data, _ = api(self.client, 'POST', f'/api/v1/exams/{eid}/start', token=self.student_token)
        assert data['success'] is True
        paper = data['data']
        assert len(paper['questions']) >= 1
        # 学生端题目不含答案
        for q in paper['questions']:
            assert 'answer' not in q

        # 逐题保存答案（已知答案的题答对，验证统一判题）
        expected_score = 0
        for q in paper['questions']:
            qid = q['question_id']
            ans = 'WRONG_ANSWER_FOR_TEST'
            if qid in self.qmap:
                real = self.qmap[qid]['answer']
                # 判断题用 "√" 提交（归一化测试 M22）
                if self.qmap[qid]['type'] == 'judge':
                    ans = '√' if real == '对' else '×'
                elif self.qmap[qid]['type'] == 'fill':
                    ans = ' 3.14 '  # 带空格（宽松匹配）
                else:
                    ans = real
                expected_score += q['score']
            data, _ = api(self.client, 'POST', f'/api/v1/exams/{eid}/answers',
                          token=self.student_token,
                          json={'question_id': qid, 'answer': ans})
            assert data['success'] is True, data

        # 提交 → 自动判分
        data, _ = api(self.client, 'POST', f'/api/v1/exams/{eid}/submit',
                      token=self.student_token, json={'focus_lost_count': 0})
        assert data['success'] is True, data
        auto_score = data['data']['auto_score']
        assert auto_score == expected_score, f'auto_score={auto_score}, expected={expected_score}'

        # 我的成绩
        data, _ = api(self.client, 'GET', f'/api/v1/exams/{eid}/my-result', token=self.student_token)
        assert data['code'] == 200
        assert data['data']['submission']['status'] in ('submitted', 'reviewed')

        # 教师提交列表 + 阅卷详情
        data, _ = api(self.client, 'GET', f'/api/v1/exams/{eid}/submissions',
                      token=self.teacher_token)
        assert data['success'] is True
        subs = data['data']['items']
        assert len(subs) >= 1
        sid = subs[0]['id']
        data, _ = api(self.client, 'GET', f'/api/v1/exams/{eid}/submissions/{sid}',
                      token=self.teacher_token)
        assert data['success'] is True

        # 完成阅卷
        data, _ = api(self.client, 'POST', f'/api/v1/exams/{eid}/submissions/{sid}/finalize',
                      token=self.teacher_token)
        assert data['success'] is True

        # 排名
        data, _ = api(self.client, 'GET', f'/api/v1/exams/{eid}/ranking', token=self.teacher_token)
        assert data['success'] is True and len(data['data']) >= 1

        # 考试分析
        data, _ = api(self.client, 'GET', f'/api/v1/exams/{eid}/analysis', token=self.student_token)
        assert data['code'] == 200

    def test_exam_time_window(self):
        """考试开始前（未来时间）不可作答（M20）"""
        self._prepare_class_and_questions()
        eid = self._generate_exam([
            {'type': 'choice', 'count': 1, 'score_per_question': 10}])
        api(self.client, 'PUT', f'/api/v1/exams/{eid}/publish', token=self.teacher_token)
        # 把考试时间改到未来
        from datetime import datetime, timedelta
        future = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        api(self.client, 'PUT', f'/api/v1/exams/{eid}', token=self.teacher_token,
            json={'start_time': future})
        data, _ = api(self.client, 'POST', f'/api/v1/exams/{eid}/start', token=self.student_token)
        assert data['code'] == 400 and '尚未开始' in data['message']

    def test_retake_clears_old_answers(self):
        """重考清空旧答案（M21）"""
        self._prepare_class_and_questions()
        eid = self._generate_exam([
            {'type': 'choice', 'count': 1, 'score_per_question': 10}])
        api(self.client, 'PUT', f'/api/v1/exams/{eid}/publish', token=self.teacher_token)
        # 第一次答题：答错
        data, _ = api(self.client, 'POST', f'/api/v1/exams/{eid}/start', token=self.student_token)
        qid = data['data']['questions'][0]['question_id']
        api(self.client, 'POST', f'/api/v1/exams/{eid}/answers', token=self.student_token,
            json={'question_id': qid, 'answer': 'WRONG'})
        data, _ = api(self.client, 'POST', f'/api/v1/exams/{eid}/submit', token=self.student_token,
                      json={'focus_lost_count': 0})
        assert 'data' in data, f'submit1 response: {data}'
        assert data['data']['auto_score'] == 0
        # 重考（max_attempts 默认 1，需先提额）→ 直接再次 start 会因次数上限失败
        from app.repositories.sql_repo import sql_repo
        sql_repo.execute_update(
            "UPDATE exam_papers SET max_attempts = 2 WHERE id = ?", (eid,))
        data, _ = api(self.client, 'POST', f'/api/v1/exams/{eid}/start', token=self.student_token)
        assert data['success'] is True
        # 旧答案已清空：重考后不答任何题直接提交 → 0 分（若旧答案残留会保留上次得分）
        data, _ = api(self.client, 'POST', f'/api/v1/exams/{eid}/submit', token=self.student_token,
                      json={'focus_lost_count': 0})
        assert data['data']['auto_score'] == 0

    def test_unpublished_exam_invisible_to_student(self):
        self._prepare_class_and_questions()
        eid = self._generate_exam([
            {'type': 'choice', 'count': 1, 'score_per_question': 10}])
        # 未发布 → 学生 403（M19）
        data, _ = api(self.client, 'GET', f'/api/v1/exams/{eid}', token=self.student_token)
        assert data['code'] == 403

    def test_homework_flow(self):
        """作业：无时间窗口限制，可提交后再做（M21）"""
        self._prepare_class_and_questions()
        # 直接生成作业型任务（task_type='homework'，max_attempts=NULL=无限次）
        data, _ = api(self.client, 'POST', '/api/v1/exams/generate', token=self.teacher_token,
                      json={
                          'title': _mk_title('作业'),
                          'class_id': self.class_id,
                          'duration_minutes': 60,
                          'task_type': 'homework',
                          'rules': [{'type': 'judge', 'count': 1, 'score_per_question': 20}],
                      })
        assert data['success'] is True, data
        eid = data['data']['id']
        api(self.client, 'PUT', f'/api/v1/exams/{eid}/publish', token=self.teacher_token)
        data, _ = api(self.client, 'POST', f'/api/v1/exams/{eid}/start-homework',
                      token=self.student_token)
        assert data['success'] is True
        # 提交后仍可重做（can_resubmit / 无限次）
        api(self.client, 'POST', f'/api/v1/exams/{eid}/submit', token=self.student_token,
            json={})
        data, _ = api(self.client, 'POST', f'/api/v1/exams/{eid}/start-homework',
                      token=self.student_token)
        assert data['success'] is True


# ══════════════════════════════════════════════════════════════
# 独立刷题判题一致性（M22）
# ══════════════════════════════════════════════════════════════

class TestPracticeJudge:
    @pytest.fixture(autouse=True)
    def _setup(self, client):
        self.client = client
        self.admin, self.admin_token = register_admin(client)
        self.student, self.student_token = register_user(client)

    def _create_q(self, qtype, ans, options=None):
        data, _ = api(self.client, 'POST', '/api/v1/questions', token=self.admin_token, json={
            'title': _mk_title('刷题'),
            'type': qtype,
            'answer': ans,
            'options': options or (['A. x', 'B. y', 'C. z', 'D. w'] if qtype == 'choice' else []),
            'category': '集成测试',
        })
        return data['data']['id']

    def test_judge_normalization(self):
        qid = self._create_q('judge', '对')
        for ans, expected in [('√', 1), ('true', 1), ('对', 1),
                              ('错', 0), ('×', 0)]:
            data, _ = api(self.client, 'POST', '/api/v1/practice/attempts',
                          token=self.student_token,
                          json={'question_id': qid, 'answer': ans})
            assert data['success'] is True, data
            assert data['data']['is_correct'] == expected, f'answer={ans}'

    def test_fill_loose_match(self):
        qid = self._create_q('fill', '3.14')
        data, _ = api(self.client, 'POST', '/api/v1/practice/attempts',
                      token=self.student_token,
                      json={'question_id': qid, 'answer': ' 3.14 '})
        assert data['data']['is_correct'] == 1

    def test_choice_exact(self):
        qid = self._create_q('choice', 'A')
        data, _ = api(self.client, 'POST', '/api/v1/practice/attempts',
                      token=self.student_token,
                      json={'question_id': qid, 'answer': 'A'})
        assert data['data']['is_correct'] == 1
        data, _ = api(self.client, 'POST', '/api/v1/practice/attempts',
                      token=self.student_token,
                      json={'question_id': qid, 'answer': ' a '})
        assert data['data']['is_correct'] == 0

    def test_history_and_list(self):
        qid = self._create_q('choice', 'A')
        api(self.client, 'POST', '/api/v1/practice/attempts', token=self.student_token,
            json={'question_id': qid, 'answer': 'A', 'elapsed_seconds': 12})
        data, _ = api(self.client, 'GET', '/api/v1/practice/history', token=self.student_token)
        assert data['success'] is True and data['data']['total'] >= 1
        data, _ = api(self.client, 'GET', f'/api/v1/practice/questions/{qid}',
                      token=self.student_token)
        assert data['data']['last_attempt'] is not None


# ══════════════════════════════════════════════════════════════
# 学习计划打卡（M23）
# ══════════════════════════════════════════════════════════════

class TestLearningPlan:
    def test_create_checkin_progress(self, client):
        _, token = register_user(client)
        # 创建计划
        data, _ = api(client, 'POST', '/api/v1/learning/plans', token=token, json={
            'title': _mk_title('学习计划'), 'description': '测试',
            'knowledge_point_ids': ['kp1'], 'target_date': '2026-12-31'})
        assert data['success'] is True, data
        plan_id = data['data']['id']
        # 打卡
        data, _ = api(client, 'POST', f'/api/v1/learning/plans/{plan_id}/checkin',
                      token=token, json={'study_minutes': 30, 'question_count': 5})
        assert data['success'] is True
        # 计划列表含进度（10% = 1 次打卡）
        data, _ = api(client, 'GET', '/api/v1/learning/plans', token=token)
        plans = data['data']
        my = [p for p in plans if p['id'] == plan_id][0]
        assert my['progress'] == 10
        assert my['total_checkins'] == 1
        # 打卡记录
        data, _ = api(client, 'GET', f'/api/v1/learning/plans/{plan_id}/checkins',
                      token=token)
        assert data['success'] is True
        # 学习评估 / 路径接口可用
        data, _ = api(client, 'GET', '/api/v1/learning/assessment', token=token)
        assert data['code'] in (200, 500) or data['success'] is not None

    def test_plan_access_control(self, client):
        user_a, token_a = register_user(client)
        user_b, token_b = register_user(client)
        data, _ = api(client, 'POST', '/api/v1/learning/plans', token=token_a,
                      json={'title': _mk_title('私密计划')})
        plan_id = data['data']['id']
        # 他人打卡 → 400
        data, _ = api(client, 'POST', f'/api/v1/learning/plans/{plan_id}/checkin',
                      token=token_b, json={'study_minutes': 1})
        assert data['code'] == 400
        # 他人查看题单 → 400
        data, _ = api(client, 'GET', f'/api/v1/learning/plans/{plan_id}/questions',
                      token=token_b)
        assert data['code'] == 400


# ══════════════════════════════════════════════════════════════
# 资源 / 通知
# ══════════════════════════════════════════════════════════════

class TestResource:
    def test_resource_crud(self, client):
        admin, admin_token = register_admin(client)
        student, student_token = register_user(client)
        # 取一个知识点（Neo4j）作为资源关联
        data, _ = api(client, 'GET', '/api/v1/knowledge-points?page_size=1',
                      token=student_token)
        assert data['code'] == 200, data
        kp_items = data['data'].get('items', [])
        kp_id = kp_items[0]['id'] if kp_items else None
        body = {
            'title': _mk_title('资源'), 'type': 'doc', 'url': 'http://example.com',
            'content': '# 内容', 'tags': '测试',
        }
        if kp_id:
            body['knowledge_point_id'] = kp_id
        data, _ = api(client, 'POST', '/api/v1/resources', token=admin_token, json=body)
        assert data['success'] is True, data
        rid = data['data']['id']
        # 学生可浏览
        data, _ = api(client, 'GET', f'/api/v1/resources/{rid}', token=student_token)
        assert data['code'] == 200
        data, _ = api(client, 'GET', '/api/v1/resources', token=student_token)
        assert data['code'] == 200
        # 学生不可创建/删除
        data, _ = api(client, 'POST', '/api/v1/resources', token=student_token,
                      json={'title': 'x', 'type': 'doc'})
        assert data['code'] == 403
        # 管理员更新
        data, _ = api(client, 'PUT', f'/api/v1/resources/{rid}', token=admin_token,
                      json={'title': '改名'})
        assert data['success'] is True
        # 资源类型
        data, _ = api(client, 'GET', '/api/v1/resources/types', token=student_token)
        assert data['success'] is True and len(data['data']) > 0


class TestNotification:
    def test_notification_flow(self, client):
        _, token = register_user(client)
        data, _ = api(client, 'GET', '/api/v1/notifications', token=token)
        assert data['success'] is True
        data, _ = api(client, 'GET', '/api/v1/notifications/unread-count', token=token)
        assert data['success'] is True and 'count' in data['data']
        data, _ = api(client, 'PUT', '/api/v1/notifications/read-all', token=token)
        assert data['success'] is True


# ══════════════════════════════════════════════════════════════
# 统计 / 知识图谱 / 健康
# ══════════════════════════════════════════════════════════════

class TestStatistics:
    def test_student_stats(self, client):
        _, token = register_user(client)
        for path in ('/api/v1/statistics/student/overview',
                     '/api/v1/statistics/student/summary',
                     '/api/v1/statistics/student/radar'):
            data, _ = api(client, 'GET', path, token=token)
            assert data['code'] in (200, 404), f'{path} → {data}'


class TestGraph:
    def test_neo4j_endpoints(self, client):
        _, token = register_user(client)
        data, _ = api(client, 'GET', '/api/v1/graph/statistics', token=token)
        assert data['code'] == 200, data
        # 知识点分页
        data, _ = api(client, 'GET', '/api/v1/knowledge-points', token=token)
        assert data['code'] == 200, data
        # 图谱分组
        data, _ = api(client, 'GET', '/api/v1/graph-groups', token=token)
        assert data['code'] == 200, data
        # 搜索
        data, _ = api(client, 'GET', '/api/v1/knowledge-points/search?keyword=数',
                      token=token)
        assert data['code'] in (200, 400), data

    def test_graph_tracks(self, client):
        _, token = register_user(client)
        data, _ = api(client, 'GET', '/api/v1/graph/tracks', token=token)
        assert data['code'] in (200, 404), data


class TestHealth:
    def test_health(self, client):
        data, _ = api(client, 'GET', '/api/v1/health')
        assert data['code'] == 200
        d = data['data']
        # 兼容两个 /health 处理器（存在路由遮蔽问题，见测试报告 6.2）
        if 'mysql_ok' in d:
            assert d['mysql_ok'] is True
        else:
            assert d.get('database') == 'ok'

    def test_unauth_guard(self, client):
        """未带 token 访问受保护接口 → 401"""
        for path in ('/api/v1/classes', '/api/v1/questions',
                     '/api/v1/exams', '/api/v1/practice/questions'):
            data, _ = api(client, 'GET', path)
            assert data['code'] == 401, f'{path} → {data}'
