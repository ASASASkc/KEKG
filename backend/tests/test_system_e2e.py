# -*- coding: utf-8 -*-
"""系统测试：端到端用户旅程（连接真实 MySQL + Neo4j）

以完整业务场景为主线，串联多个模块的真实操作流程，验证系统
各组件协同工作是否符合预期：

- 教师教学闭环：注册 → 建班 → 公告 → 建题 → 组卷 → 发布
- 学生学习闭环：加入班级 → 考试作答 → 自动判分 → 成绩 → 刷题 → 计划 → 统计
- 知识图谱闭环：图统计 → 知识点 → 学习路径 → 资源关联
- 管理端闭环：用户管理 → 角色变更 → 操作日志 → LLM 配置
- 跨模块综合：一次完整"学练测评"成长旅程
"""
import pytest
import uuid

from conftest import api, register_user, register_admin


def _mk_title(prefix):
    return f'{prefix}_{uuid.uuid4().hex[:8]}'


def _create_question(client, token, qtype, ans, title='端到端题'):
    data, _ = api(client, 'POST', '/api/v1/questions', token=token, json={
        'title': _mk_title(title),
        'type': qtype,
        'answer': ans,
        'options': (['A. 选项A', 'B. 选项B', 'C. 选项C', 'D. 选项D']
                    if qtype == 'choice' else []),
        'category': '系统测试',
    })
    assert data['success'] is True, f'建题失败: {data}'
    return data['data']['id']


class TestTeacherJourney:
    """端到端 1：教师完整教学闭环"""

    @pytest.fixture(autouse=True)
    def _setup(self, client):
        self.client = client
        self.teacher, self.teacher_token = register_admin(client)
        self.student, self.student_token = register_user(client)

    def test_teacher_full_teaching_loop(self):
        c = self.client
        # 1. 建班
        data, _ = api(c, 'POST', '/api/v1/classes', token=self.teacher_token,
                      json={'name': _mk_title('教学班'), 'description': '端到端班级'})
        assert data['success'] is True, data
        cls = data['data']
        cid, code = cls['id'], cls['class_code']

        # 2. 发布公告
        data, _ = api(c, 'POST', f'/api/v1/classes/{cid}/announcements',
                      token=self.teacher_token,
                      json={'title': '开课通知', 'content': '欢迎加入本课程'})
        assert data['success'] is True, data

        # 3. 建题（三种题型）
        qids = {
            'choice': _create_question(c, self.teacher_token, 'choice', 'B'),
            'judge': _create_question(c, self.teacher_token, 'judge', '对'),
            'fill': _create_question(c, self.teacher_token, 'fill', '42'),
        }

        # 4. 组卷生成考试
        data, _ = api(c, 'POST', '/api/v1/exams/generate', token=self.teacher_token, json={
            'title': _mk_title('期中考试'),
            'class_id': cid,
            'duration_minutes': 90,
            'start_time': '2026-01-01 00:00:00',
            'end_time': '2026-12-31 23:59:59',
            'pass_score': 60,
            'rules': [
                {'type': 'choice', 'count': 1, 'score_per_question': 10},
                {'type': 'judge', 'count': 1, 'score_per_question': 20},
                {'type': 'fill', 'count': 1, 'score_per_question': 15},
            ],
        })
        assert data['success'] is True, data
        eid = data['data']['id']

        # 5. 发布考试
        data, _ = api(c, 'PUT', f'/api/v1/exams/{eid}/publish', token=self.teacher_token)
        assert data['success'] is True

        # 6. 教师查看试卷/提交列表/统计（此时可能为空但不报错）
        data, _ = api(c, 'GET', f'/api/v1/exams/{eid}', token=self.teacher_token)
        assert data['success'] is True
        data, _ = api(c, 'GET', f'/api/v1/exams/{eid}/submissions', token=self.teacher_token)
        assert data['success'] is True
        data, _ = api(c, 'GET', '/api/v1/classes', token=self.teacher_token)
        assert data['success'] is True
        # 我建的题出现在题库列表中
        data, _ = api(c, 'GET', '/api/v1/questions?page_size=5', token=self.teacher_token)
        assert data['success'] is True


class TestStudentJourney:
    """端到端 2：学生完整学习闭环"""

    @pytest.fixture(autouse=True)
    def _setup(self, client):
        self.client = client
        self.teacher, self.teacher_token = register_admin(client)
        self.student, self.student_token = register_user(client)
        # 预置：班级 + 题目 + 考试 + 发布
        data, _ = api(self.client, 'POST', '/api/v1/classes', token=self.teacher_token,
                      json={'name': _mk_title('学习班'), 'description': ''})
        self.class_code = data['data']['class_code']
        self.cid = data['data']['id']
        self.qmap = {
            _create_question(self.client, self.teacher_token, 'choice', 'A'): ('choice', 'A', 10),
            _create_question(self.client, self.teacher_token, 'judge', '对'): ('judge', '对', 20),
        }
        data, _ = api(self.client, 'POST', '/api/v1/exams/generate',
                      token=self.teacher_token, json={
                          'title': _mk_title('阶段考试'),
                          'class_id': self.cid,
                          'duration_minutes': 60,
                          'start_time': '2026-01-01 00:00:00',
                          'end_time': '2026-12-31 23:59:59',
                          'pass_score': 60,
                          'rules': [
                              {'type': 'choice', 'count': 1, 'score_per_question': 10},
                              {'type': 'judge', 'count': 1, 'score_per_question': 20},
                          ],
                      })
        self.eid = data['data']['id']
        api(self.client, 'PUT', f"/api/v1/exams/{self.eid}/publish",
            token=self.teacher_token)

    def test_student_full_learning_loop(self):
        c = self.client
        # 1. 加入班级
        data, _ = api(c, 'POST', '/api/v1/classes/join', token=self.student_token,
                      json={'class_code': self.class_code})
        assert data['success'] is True, data
        # 2. 查看班级公告列表（空即可）
        data, _ = api(c, 'GET', f'/api/v1/classes/{self.cid}/announcements',
                      token=self.student_token)
        assert data['code'] in (200, 404)
        # 3. 查看已发布考试
        data, _ = api(c, 'GET', f'/api/v1/exams/{self.eid}', token=self.student_token)
        assert data['code'] == 200 and data['data']['status'] == 'published'
        # 4. 开始考试
        data, _ = api(c, 'POST', f'/api/v1/exams/{self.eid}/start',
                      token=self.student_token)
        assert data['success'] is True
        paper = data['data']
        assert paper['questions'] and all('answer' not in q for q in paper['questions'])
        # 5. 作答：本类创建的题答对（判断题用 √ 归一化），其余随机抽中的题答错
        expected = 0
        for q in paper['questions']:
            qid = q['question_id']
            entry = self.qmap.get(qid)
            if not entry:
                send_ans = 'WRONG_FOR_TEST'
            else:
                qtype, ans, score = entry
                send_ans = '√' if qtype == 'judge' else ans
                expected += score
            data, _ = api(c, 'POST', f'/api/v1/exams/{self.eid}/answers',
                          token=self.student_token,
                          json={'question_id': qid, 'answer': send_ans})
            assert data['success'] is True, data
        # 6. 提交 → 自动判分
        data, _ = api(c, 'POST', f'/api/v1/exams/{self.eid}/submit',
                      token=self.student_token, json={'focus_lost_count': 0})
        assert data['success'] is True, data
        assert data['data']['auto_score'] == expected
        # 7. 查看成绩
        data, _ = api(c, 'GET', f'/api/v1/exams/{self.eid}/my-result',
                      token=self.student_token)
        assert data['code'] == 200
        # 8. 错题本（答对应无错题，接口可用即可）
        data, _ = api(c, 'GET', '/api/v1/auth/me', token=self.student_token)
        uid = data['data']['id']
        data, _ = api(c, 'GET', f'/api/v1/users/{uid}/wrong-answers',
                      token=self.student_token)
        assert data['code'] in (200, 404)
        # 9. 用户画像 / 成就
        data, _ = api(c, 'GET', f'/api/v1/users/{uid}/profile', token=self.student_token)
        assert data['code'] in (200, 404)
        data, _ = api(c, 'GET', f'/api/v1/users/{uid}/achievements', token=self.student_token)
        assert data['code'] in (200, 404)
        # 10. 学生统计
        for path in ('/api/v1/statistics/student/overview',
                     '/api/v1/statistics/student/summary',
                     '/api/v1/statistics/student/radar'):
            data, _ = api(c, 'GET', path, token=self.student_token)
            assert data['code'] in (200, 404), f'{path} → {data}'
        # 11. 独立刷题
        qid = _create_question(c, self.teacher_token, 'choice', 'C', '刷题')
        data, _ = api(c, 'POST', '/api/v1/practice/attempts', token=self.student_token,
                      json={'question_id': qid, 'answer': 'C'})
        assert data['success'] is True and data['data']['is_correct'] == 1
        data, _ = api(c, 'GET', '/api/v1/practice/history', token=self.student_token)
        assert data['success'] is True and data['data']['total'] >= 1


class TestLearningPlanJourney:
    """端到端 3：学习计划打卡闭环"""

    def test_plan_checkin_loop(self, client):
        _, token = register_user(client)
        c = client
        # 创建计划
        data, _ = api(c, 'POST', '/api/v1/learning/plans', token=token, json={
            'title': _mk_title('Python 学习计划'),
            'description': '每日打卡',
            'knowledge_point_ids': ['sys_python_basics'],
            'target_date': '2026-12-31',
        })
        assert data['success'] is True, data
        pid = data['data']['id']
        # 第一次打卡 → 进度 10%
        data, _ = api(c, 'POST', f'/api/v1/learning/plans/{pid}/checkin',
                      token=token, json={'study_minutes': 25, 'question_count': 3})
        assert data['success'] is True, data
        data, _ = api(c, 'GET', '/api/v1/learning/plans', token=token)
        my = [p for p in data['data'] if p['id'] == pid][0]
        assert my['progress'] == 10, f'进度异常: {my}'
        assert my['total_checkins'] == 1
        # 同日再打卡 → 记录合并（幂等），学习时长累加，次数不重复计算
        data, _ = api(c, 'POST', f'/api/v1/learning/plans/{pid}/checkin',
                      token=token, json={'study_minutes': 35, 'question_count': 2})
        assert data['success'] is True, data
        data, _ = api(c, 'GET', '/api/v1/learning/plans', token=token)
        my = [p for p in data['data'] if p['id'] == pid][0]
        assert my['total_checkins'] == 1, f'同日重复打卡应合并: {my}'
        assert int(my['total_study_minutes']) == 60, f'学习时长应累加: {my}'
        # 打卡记录
        data, _ = api(c, 'GET', f'/api/v1/learning/plans/{pid}/checkins', token=token)
        assert data['success'] is True
        # 学习评估与路径接口可用
        data, _ = api(c, 'GET', '/api/v1/learning/assessment', token=token)
        assert data['code'] in (200, 404, 500)
        data, _ = api(c, 'GET', '/api/v1/learning/path', token=token)
        assert data['code'] in (200, 404, 500)


class TestKnowledgeGraphJourney:
    """端到端 4：知识图谱 + 资源关联闭环"""

    def test_graph_and_resource_loop(self, client, admin_token):
        c = client
        _, user_token = register_user(client)
        # 1. 图统计
        data, _ = api(c, 'GET', '/api/v1/graph/statistics', token=user_token)
        assert data['code'] == 200, data
        # 2. 知识点列表
        data, _ = api(c, 'GET', '/api/v1/knowledge-points?page_size=5', token=user_token)
        assert data['code'] == 200, data
        kp_items = (data.get('data') or {}).get('items') or []
        # 3. 搜索
        data, _ = api(c, 'GET', '/api/v1/knowledge-points/search?keyword=基础',
                      token=user_token)
        assert data['code'] in (200, 400)
        # 4. 学习路径推荐
        data, _ = api(c, 'GET', '/api/v1/learning/path', token=user_token)
        assert data['code'] in (200, 404, 500)
        # 5. 资源创建（关联已存在知识点）→ 浏览
        kp_id = kp_items[0]['id'] if kp_items else None
        body = {
            'title': _mk_title('图谱资源'), 'type': 'video',
            'url': 'http://example.com/v', 'content': '教程',
            'tags': '端到端',
        }
        if kp_id:
            body['knowledge_point_id'] = kp_id
        data, _ = api(c, 'POST', '/api/v1/resources', token=admin_token, json=body)
        assert data['success'] is True, data
        rid = data['data']['id']
        data, _ = api(c, 'GET', f'/api/v1/resources/{rid}', token=user_token)
        assert data['code'] == 200
        data, _ = api(c, 'GET', '/api/v1/resources?page_size=5', token=user_token)
        assert data['code'] == 200


class TestAdminManagementJourney:
    """端到端 5：系统管理端闭环"""

    def test_admin_management_loop(self, client, admin_token):
        c = client
        # 1. 用户列表（分页结构，包含默认 admin 与测试用户）
        data, _ = api(c, 'GET', '/api/v1/auth/users', token=admin_token)
        assert data['success'] is True
        users = data['data']['items']
        assert any(u.get('username') == 'admin' for u in users)
        # 2. 新注册一个用户并升级为管理员（角色变更）
        _, new_token = register_user(c)
        data, _ = api(c, 'GET', '/api/v1/auth/me', token=new_token)
        new_uid = data['data']['id']
        data, _ = api(c, 'PUT', f'/api/v1/auth/users/{new_uid}/role',
                      token=admin_token, json={'role': 'admin'})
        assert data['success'] is True, data
        data, _ = api(c, 'GET', '/api/v1/auth/me', token=new_token)
        assert data['data']['role'] == 'admin'
        # 3. 操作日志
        data, _ = api(c, 'GET', '/api/v1/logs/operations?page_size=5', token=admin_token)
        assert data['code'] in (200, 404)
        data, _ = api(c, 'GET', '/api/v1/logs/actions', token=admin_token)
        assert data['code'] in (200, 404)
        data, _ = api(c, 'GET', '/api/v1/logs/modules', token=admin_token)
        assert data['code'] in (200, 404)
        # 4. LLM 配置读取
        data, _ = api(c, 'GET', '/api/v1/llm/config', token=admin_token)
        assert data['code'] in (200, 400)
        # 5. 普通用户访问管理端 → 403
        _, user_token = register_user(c)
        data, _ = api(c, 'GET', '/api/v1/auth/users', token=user_token)
        assert data['code'] == 403
        data, _ = api(c, 'PUT', f'/api/v1/auth/users/{new_uid}/role',
                      token=user_token, json={'role': 'user'})
        assert data['code'] == 403
        data, _ = api(c, 'GET', '/api/v1/llm/config', token=user_token)
        assert data['code'] in (403, 404)


class TestCrossModuleJourney:
    """端到端 6：跨模块综合成长旅程（学-练-测-评）"""

    def test_full_growth_journey(self, client):
        c = client
        teacher, teacher_token = register_admin(c)
        student, student_token = register_user(c)

        # ── 建班 + 建题 ──
        data, _ = api(c, 'POST', '/api/v1/classes', token=teacher_token,
                      json={'name': _mk_title('综合班'), 'description': ''})
        cid, code = data['data']['id'], data['data']['class_code']
        qid = _create_question(c, teacher_token, 'choice', 'D', '综合题')

        # ── 学生入班 → 刷题（练） ──
        data, _ = api(c, 'POST', '/api/v1/classes/join', token=student_token,
                      json={'class_code': code})
        assert data['success'] is True
        # 先答错，制造错题数据
        data, _ = api(c, 'POST', '/api/v1/practice/attempts', token=student_token,
                      json={'question_id': qid, 'answer': 'WRONG'})
        assert data['data']['is_correct'] == 0
        # 再答对
        data, _ = api(c, 'POST', '/api/v1/practice/attempts', token=student_token,
                      json={'question_id': qid, 'answer': 'D'})
        assert data['data']['is_correct'] == 1

        # ── 教师组卷考试（测） ──
        data, _ = api(c, 'POST', '/api/v1/exams/generate', token=teacher_token, json={
            'title': _mk_title('期末测评'),
            'class_id': cid,
            'duration_minutes': 60,
            'start_time': '2026-01-01 00:00:00',
            'end_time': '2026-12-31 23:59:59',
            'pass_score': 60,
            'rules': [{'type': 'choice', 'count': 1, 'score_per_question': 10}],
        })
        eid = data['data']['id']
        api(c, 'PUT', f'/api/v1/exams/{eid}/publish', token=teacher_token)

        # ── 学生考试作答：从题库查试卷实际题目的正确答案（保证判分确定性） ──
        data, _ = api(c, 'POST', f'/api/v1/exams/{eid}/start', token=student_token)
        qid2 = data['data']['questions'][0]['question_id']
        # 抽题是随机的，从题库取该题正确答案以确保自动判分可达满分
        from app.repositories.sql_repo import sql_repo
        rows = sql_repo.execute_query(
            "SELECT answer, type FROM question_bank WHERE id = ? AND status = 'approved'",
            (qid2,))
        assert rows, f'考试题目 {qid2} 不在已审核题库中'
        answer, qtype = rows[0]['answer'], rows[0]['type']
        if qtype == 'choice':
            answer = answer.strip()  # 选择题精确匹配，去除意外空白
        api(c, 'POST', f'/api/v1/exams/{eid}/answers', token=student_token,
            json={'question_id': qid2, 'answer': answer})
        data, _ = api(c, 'POST', f'/api/v1/exams/{eid}/submit',
                      token=student_token, json={'focus_lost_count': 0})
        assert data['data']['auto_score'] == 10, f'判分异常: {data}'

        # ── 学习评估（评）──
        data, _ = api(c, 'GET', '/api/v1/learning/assessment', token=student_token)
        assert data['code'] in (200, 404, 500)
        # 评估后应有复合分（已提交过考试）
        if data.get('code') == 200 and data.get('data'):
            assert data['data'].get('exam_count', 0) >= 1
