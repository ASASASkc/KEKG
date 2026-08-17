# -*- coding: utf-8 -*-
"""单元测试：核心业务纯逻辑（不依赖数据库连接）

覆盖：统一判题规则（M22）、判断题归一化、难度计算、
     ExamService 时间解析、分页工具
"""
import pytest

from app.services.question_service import judge_answer, normalize_judge, QuestionService
from app.services.exam_service import ExamService
from app.utils.pagination import get_pagination_params, paginate_list, paginate_response


class TestNormalizeJudge:
    def test_positive_forms(self):
        for v in ('对', '√', '✓', 'true', 'T', 'TRUE', 'yes', 'y', '1', '正确', '是'):
            assert normalize_judge(v) == '对', v
        for v in ('错', '×', '✗', 'false', 'F', 'no', 'n', '0', '错误', '否'):
            assert normalize_judge(v) == '错', v

    def test_unrecognized_keeps_value(self):
        assert normalize_judge('  abc  ') == 'abc'
        assert normalize_judge('') == ''
        assert normalize_judge(None) == ''


class TestJudgeAnswer:
    """统一判题规则：choice 精确、judge 归一化、fill 宽松、主观题 None"""

    def test_choice_exact(self):
        assert judge_answer('choice', 'A', 'A') == 1
        assert judge_answer('choice', 'B', 'A') == 0
        assert judge_answer('choice', ' a ', 'A') == 0  # 选择题不宽松

    def test_judge_normalized_match(self):
        assert judge_answer('judge', '√', '对') == 1
        assert judge_answer('judge', 'true', '对') == 1
        assert judge_answer('judge', '×', '错') == 1
        assert judge_answer('judge', '0', '错') == 1
        assert judge_answer('judge', '对', '错') == 0

    def test_fill_loose_match(self):
        assert judge_answer('fill', '3.14', '3.14') == 1
        assert judge_answer('fill', ' 3.14 ', '3.14') == 1
        assert judge_answer('fill', '北京', '北京！') == 1   # 全角标点
        assert judge_answer('fill', 'ABC', 'abc') == 1      # 大小写不敏感
        assert judge_answer('fill', '北京', '上海') == 0

    def test_subjective_returns_none(self):
        assert judge_answer('subjective', '任意内容', '参考答案') is None
        assert judge_answer('code', 'print(1)', '# 模板') is None

    def test_empty_user_answer(self):
        assert judge_answer('choice', '', 'A') == 0
        assert judge_answer('choice', None, 'A') == 0


class TestCalcDifficulty:
    def test_zero_or_negative(self):
        assert QuestionService.calc_difficulty(0) == 1
        assert QuestionService.calc_difficulty(-1) == 1

    def test_normal(self):
        assert QuestionService.calc_difficulty(1) == 1
        assert QuestionService.calc_difficulty(2) == 2
        assert QuestionService.calc_difficulty(4) == 3
        assert QuestionService.calc_difficulty(16) == 5

    def test_upper_bound(self):
        assert QuestionService.calc_difficulty(4096) == 12
        assert QuestionService.calc_difficulty(10**9) == 12


class TestParseDt:
    def test_full_format(self):
        from datetime import datetime
        assert ExamService._parse_dt('2026-08-11 10:30:00') == datetime(2026, 8, 11, 10, 30, 0)

    def test_t_separator(self):
        from datetime import datetime
        assert ExamService._parse_dt('2026-08-11T10:30:00') == datetime(2026, 8, 11, 10, 30, 0)

    def test_no_seconds(self):
        from datetime import datetime
        assert ExamService._parse_dt('2026-08-11 10:30') == datetime(2026, 8, 11, 10, 30)

    def test_date_only(self):
        from datetime import datetime
        assert ExamService._parse_dt('2026-08-11') == datetime(2026, 8, 11)

    def test_invalid(self):
        assert ExamService._parse_dt('not-a-date') is None
        assert ExamService._parse_dt('2026-13-99') is None

    def test_none_or_empty(self):
        assert ExamService._parse_dt(None) is None
        assert ExamService._parse_dt('') is None


class _FakeArgs:
    """模拟 Flask request.args"""

    def __init__(self, values):
        self._v = values

    def get(self, key, default=None):
        return self._v.get(key, default)


class TestPagination:
    def test_default_params(self):
        page, size = get_pagination_params(_FakeArgs({}))
        assert (page, size) == (1, 20)

    def test_valid_params(self):
        page, size = get_pagination_params(_FakeArgs({'page': '3', 'page_size': '50'}))
        assert (page, size) == (3, 50)

    def test_invalid_values(self):
        assert get_pagination_params(_FakeArgs({'page': 'abc', 'page_size': 'xyz'})) == (1, 20)
        assert get_pagination_params(_FakeArgs({'page': '0', 'page_size': '0'})) == (1, 1)
        assert get_pagination_params(_FakeArgs({'page': '-5', 'page_size': '999'})) == (1, 100)

    def test_paginate_list(self):
        data = list(range(25))
        items, total = paginate_list(data, 1, 10)
        assert len(items) == 10 and total == 25
        items2, total2 = paginate_list(data, 3, 10)
        assert len(items2) == 5 and total2 == 25

    def test_paginate_list_empty(self):
        assert paginate_list([], 1, 10) == ([], 0)

    def test_paginate_response_shape(self):
        resp = paginate_response([1, 2], 1, 10, 25)
        assert resp['items'] == [1, 2]
        p = resp['pagination']
        assert p['page'] == 1 and p['total'] == 25 and p['total_pages'] == 3
        assert p['has_next'] is True and p['has_prev'] is False
