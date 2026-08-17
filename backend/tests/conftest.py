# -*- coding: utf-8 -*-
"""pytest 全局配置：测试应用、鉴权 fixtures、性能记录、测试数据清理

- 集成/系统测试连接真实 MySQL + Neo4j（.env 配置）
- 测试数据使用 tst_ / tstadmin_ 前缀，结束后统一清理
- 全局限流（300 req/min/IP）在测试环境禁用，避免干扰
"""
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app import create_app
from app.repositories.sql_repo import sql_repo

# 全局性能记录：[{method, path, status, ms}, ...]
PERF = []


def _auth_headers(token):
    return {'Authorization': f'Bearer {token}'}


def api(client, method, path, token=None, **kwargs):
    """带鉴权 + 计时的 API 调用，返回 (resp_json, elapsed_ms)
    注意：_extract_token 优先读 Cookie，会话级 client 会累积登录 Cookie，
    覆盖 Bearer token 导致身份错乱，故每次调用前清空 Cookie 罐。"""
    jar = getattr(client, 'cookie_jar', None)
    if jar is not None:
        try:
            jar.clear()
        except Exception:
            pass
    headers = dict(kwargs.get('headers') or {})
    if token:
        headers.update(_auth_headers(token))
    kwargs['headers'] = headers
    start = time.perf_counter()
    resp = client.open(path, method=method, **kwargs)
    elapsed = (time.perf_counter() - start) * 1000
    data = resp.get_json(silent=True) or {}
    PERF.append({
        'method': method, 'path': path,
        'status': resp.status_code, 'ms': round(elapsed, 2)
    })
    return data, elapsed


@pytest.fixture(scope='session')
def app():
    application = create_app('development')
    # testing=True：异常直接抛出（带完整 traceback），而不是被吞成通用 500
    application.testing = True
    # 测试环境禁用全局限流（300 req/min/IP），避免批量用例触发 429
    bf = application.before_request_funcs.get(None, [])
    application.before_request_funcs[None] = [
        f for f in bf if getattr(f, '__name__', '') != 'global_rate_limit']
    # 禁用接口级限流（登录 10/min、组卷 5/min 等），限流为 MySQL 持久化滑动窗口
    import app.utils.rate_limit as rl_mod
    rl_mod.check_limit = lambda *a, **k: (False, 9999, 0)
    yield application


@pytest.fixture(scope='session')
def client(app):
    # use_cookies=False：测试统一用 Bearer token，避免登录 Cookie 污染后续请求身份
    with app.test_client(use_cookies=False) as c:
        yield c


@pytest.fixture(scope='session')
def admin_token(client):
    """系统默认管理员 token（admin/admin123，应用初始化时创建）"""
    data, _ = api(client, 'POST', '/api/v1/auth/login',
                  json={'username': 'admin', 'password': 'admin123'})
    assert data.get('success'), f'默认 admin 登录失败: {data}'
    return data['data']['token']


def _register_and_login(client, username, password, extra=None):
    """注册 + 登录，返回 (username, token)"""
    payload = {
        'username': username,
        'password': password,
        'email': f'{username}@test.local',
    }
    if extra:
        payload.update(extra)
    data, _ = api(client, 'POST', '/api/v1/auth/register', json=payload)
    assert data.get('success'), f'注册失败: {data}'
    # 注册接口不返回 token，需登录获取
    data, _ = api(client, 'POST', '/api/v1/auth/login',
                  json={'username': username, 'password': password})
    assert data.get('success'), f'登录失败: {data}'
    return username, data['data']['token']


def register_user(client, prefix='tst'):
    """注册唯一普通用户，返回 (username, token)"""
    username = f'{prefix}_{uuid.uuid4().hex[:10]}'
    return _register_and_login(client, username, 'Test@123456')


def register_admin(client, prefix='tstadmin'):
    """注册唯一管理员（邀请码升级），返回 (username, token)"""
    from app.services.auth_service import auth_service
    code = auth_service.get_invite_code()
    username = f'{prefix}_{uuid.uuid4().hex[:10]}'
    username, token = _register_and_login(
        client, username, 'Test@123456', extra={'invite_code': code})
    # 校验已升级为管理员
    data, _ = api(client, 'GET', '/api/v1/auth/me', token=token)
    assert data.get('data', {}).get('role') == 'admin', f'邀请码未升级为 admin: {data}'
    return username, token


def cleanup_test_data():
    """删除所有 tst_ / tstadmin_ 前缀测试用户及其业务数据"""
    try:
        rows = sql_repo.execute_query(
            "SELECT id FROM users WHERE username REGEXP '^(tst|tstadmin)_'")
        ids = [r['id'] for r in rows]
        if not ids:
            return
        marks = ','.join('?' * len(ids))

        def _del(sql, params):
            try:
                sql_repo.execute_update(sql, params)
            except Exception as e:
                print(f'[cleanup] {sql[:60]}... 失败: {e}')

        # 1) 班级相关（教师=测试管理员）
        cls_rows = sql_repo.execute_query(
            f"SELECT id FROM classes WHERE teacher_id IN ({marks})", ids)
        cids = [r['id'] for r in cls_rows]
        if cids:
            cmarks = ','.join('?' * len(cids))
            _del(f"DELETE FROM class_announcements WHERE class_id IN ({cmarks})", cids)
            _del(f"DELETE FROM class_students WHERE class_id IN ({cmarks})", cids)
            _del(f"DELETE FROM student_group_members WHERE group_id IN "
                 f"(SELECT id FROM student_groups WHERE class_id IN ({cmarks}))", cids)
            _del(f"DELETE FROM student_groups WHERE class_id IN ({cmarks})", cids)
            _del(f"DELETE FROM classes WHERE id IN ({cmarks})", cids)
        # 2) 学生分组（按 student_id）
        _del(f"DELETE FROM student_group_members WHERE student_id IN ({marks})", ids)
        # 3) 含 user_id 的业务表
        for t in ('exam_answers', 'exam_submissions', 'practice_attempts',
                  'practice_sessions', 'study_plan_checkins', 'study_plans',
                  'notifications', 'user_activity_log', 'code_submissions',
                  'code_snippets', 'code_answers', 'question_favorites'):
            _del(f"DELETE FROM {t} WHERE user_id IN ({marks})", ids)
        # 4) 题目（测试管理员创建）
        _del(f"DELETE FROM question_kp_map WHERE question_id IN "
             f"(SELECT id FROM question_bank WHERE created_by IN ({marks}))", ids)
        _del(f"DELETE FROM question_bank WHERE created_by IN ({marks})", ids)
        # 5) 试卷（测试管理员创建）
        exam_rows = sql_repo.execute_query(
            f"SELECT id FROM exam_papers WHERE created_by IN ({marks})", ids)
        eids = [r['id'] for r in exam_rows]
        if eids:
            emarks = ','.join('?' * len(eids))
            _del(f"DELETE FROM exam_answers WHERE exam_id IN ({emarks})", eids)
            _del(f"DELETE FROM exam_submissions WHERE exam_id IN ({emarks})", eids)
            _del(f"DELETE FROM exam_questions WHERE exam_id IN ({emarks})", eids)
            _del(f"DELETE FROM exam_analyses WHERE exam_id IN ({emarks})", eids)
            _del(f"DELETE FROM exam_papers WHERE id IN ({emarks})", eids)
        _del(f"DELETE FROM users WHERE id IN ({marks})", ids)
    except Exception as e:  # 清理失败不阻断测试结果
        print(f'[cleanup] 清理测试数据失败: {e}')


@pytest.fixture(scope='session', autouse=True)
def _session_cleanup():
    yield
    _export_perf()
    cleanup_test_data()


def _export_perf():
    """导出本次会话的 API 性能记录（供测试报告引用）"""
    try:
        stats = {}
        for rec in PERF:
            key = (rec['method'], rec['path'])
            bucket = stats.setdefault(key, [])
            bucket.append(rec['ms'])
        rows = []
        for (method, path), times in stats.items():
            rows.append({
                'method': method, 'path': path,
                'count': len(times),
                'avg_ms': round(sum(times) / len(times), 2),
                'max_ms': round(max(times), 2),
                'min_ms': round(min(times), 2),
            })
        rows.sort(key=lambda r: r['avg_ms'], reverse=True)
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'perf_report.json')
        import json
        with open(out, 'w', encoding='utf-8') as f:
            json.dump({'total_calls': len(PERF), 'endpoints': rows},
                      f, ensure_ascii=False, indent=2)
        print(f'[perf] 已导出 {len(PERF)} 次 API 调用统计 → {out}')
    except Exception as e:
        print(f'[perf] 导出失败: {e}')
