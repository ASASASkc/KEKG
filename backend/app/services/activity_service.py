# -*- coding: utf-8 -*-
"""用户活动日志服务"""
from datetime import datetime, timedelta
from ..repositories.sql_repo import sql_repo


class ActivityService:

    # 八个知识赛道（按知识树的顶层分组）
    TRACKS = [
        '公共基础', '大模型', '数据分析及可视化', '机器学习',
        '深度学习', '网络爬虫', '自动化运维', '自然语言处理'
    ]

    @staticmethod
    def log(user_id, activity_type, activity_subtype='',
            knowledge_points='', score=0, related_id=0, detail='', notes=''):
        """记录一条用户活动"""
        sql_repo.execute_insert(
            """INSERT INTO user_activity_log
               (user_id, activity_type, activity_subtype, knowledge_points, score, related_id, detail, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, activity_type, activity_subtype, knowledge_points, score, related_id, detail, notes)
        )

    @staticmethod
    def get_user_activities(user_id, page=1, page_size=20):
        """分页查询用户活动"""
        offset = (page - 1) * page_size
        rows = sql_repo.execute_query(
            """SELECT * FROM user_activity_log
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            (user_id, page_size, offset)
        )
        total = sql_repo.execute_query(
            "SELECT COUNT(*) as cnt FROM user_activity_log WHERE user_id = ?",
            (user_id,)
        )
        return {
            'items': [dict(r) for r in rows],
            'total': total[0]['cnt'] if total else 0
        }

    @staticmethod
    def get_day_activities(user_id, date):
        """获取某天的活动详情列表（合并 活动日志 / 独立刷题 / 学习打卡）"""
        items = []
        rows = sql_repo.execute_query(
            """SELECT * FROM user_activity_log
               WHERE user_id = ? AND DATE(created_at) = ?
               ORDER BY created_at DESC""",
            (user_id, date)
        )
        items.extend(dict(r) for r in rows)

        pra_rows = sql_repo.execute_query(
            """SELECT pa.id, pa.is_correct, pa.created_at, qb.title
               FROM practice_attempts pa
               JOIN question_bank qb ON pa.question_id = qb.id
               WHERE pa.user_id = ? AND DATE(pa.created_at) = ?
               ORDER BY pa.created_at DESC""",
            (user_id, date)
        )
        for r in pra_rows:
            items.append({
                'id': r['id'],
                'activity_type': 'practice',
                'activity_subtype': '独立刷题',
                'detail': r['title'],
                'score': None,
                'knowledge_points': '',
                'related_id': 0,
                'notes': '正确' if r['is_correct'] else '错误',
                'created_at': r['created_at']
            })

        chk_rows = sql_repo.execute_query(
            """SELECT id, plan_id, study_minutes, question_count, notes, created_at
               FROM study_plan_checkins
               WHERE user_id = ? AND checkin_date = ?""",
            (user_id, date)
        )
        for r in chk_rows:
            notes = r['notes'] or ''
            if r['study_minutes']:
                notes = (notes + ' ' if notes else '') + f"{r['study_minutes']}分钟"
            if r['question_count']:
                notes = (notes + ' ' if notes else '') + f"{r['question_count']}题"
            items.append({
                'id': r['id'],
                'activity_type': 'checkin',
                'activity_subtype': '学习打卡',
                'detail': '学习计划打卡',
                'score': None,
                'knowledge_points': '',
                'related_id': r['plan_id'],
                'notes': notes.strip(),
                'created_at': r['created_at']
            })
        return items

    @staticmethod
    def get_user_stats(user_id, heatmap_end=None):
        """获取用户统计数据总览"""
        now = datetime.now()
        if heatmap_end:
            try:
                now = datetime.strptime(heatmap_end, '%Y-%m-%d') + timedelta(days=1)
            except ValueError:
                pass

        # 总练习天数
        days = sql_repo.execute_query(
            "SELECT COUNT(DISTINCT DATE(created_at)) as cnt FROM user_activity_log WHERE user_id = ?",
            (user_id,)
        )
        active_days = days[0]['cnt'] if days else 0

        # 考试统计
        exam_rows = sql_repo.execute_query(
            """SELECT COUNT(*) as total, COALESCE(ROUND(AVG(total_score), 1), 0) as avg_score,
                      SUM(CASE WHEN total_score >= (SELECT pass_score FROM exam_papers WHERE id = es.exam_id) THEN 1 ELSE 0 END) as passed
               FROM exam_submissions es
               WHERE es.student_id = ? AND es.status IN ('submitted', 'reviewed')""",
            (user_id,)
        )
        exam = exam_rows[0] if exam_rows else {'total': 0, 'avg_score': 0, 'passed': 0}

        # AI练习统计
        practice_rows = sql_repo.execute_query(
            "SELECT COUNT(*) as total, COALESCE(ROUND(AVG(score), 1), 0) as avg_score FROM practice_sessions WHERE student_id = ? AND status = 'done'",
            (user_id,)
        )
        practice = practice_rows[0] if practice_rows else {'total': 0, 'avg_score': 0}

        # 代码练习统计
        code_rows = sql_repo.execute_query(
            "SELECT COUNT(*) as total, COALESCE(ROUND(AVG(score), 1), 0) as avg_score FROM code_submissions WHERE user_id = ?",
            (user_id,)
        )
        code = code_rows[0] if code_rows else {'total': 0, 'avg_score': 0}

        # 90天活动热力图（网格状）
        weekly = ActivityService._build_heatmap(user_id, now, 365)

        # 独立刷题统计（题库练习）
        pra = sql_repo.execute_query(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct "
            "FROM practice_attempts WHERE user_id = ?",
            (user_id,))
        practice_redo = pra[0] if pra else {'total': 0, 'correct': 0}

        # 难度分布（独立刷题按题目难度分组）
        diff_rows = sql_repo.execute_query(
            """SELECT qb.difficulty AS d, COUNT(*) AS total,
                      SUM(CASE WHEN pa.is_correct = 1 THEN 1 ELSE 0 END) AS correct
               FROM practice_attempts pa
               JOIN question_bank qb ON pa.question_id = qb.id
               WHERE pa.user_id = ?
               GROUP BY qb.difficulty ORDER BY qb.difficulty""",
            (user_id,))
        difficulty_dist = []
        for r in diff_rows:
            d = r['d'] or 0
            total = r['total'] or 0
            difficulty_dist.append({
                'level': d,
                'star': min(4, max(1, (d + 2) // 3)),
                'total': total,
                'correct': r['correct'] or 0,
                'rate': round((r['correct'] or 0) * 100 / total, 1) if total else 0,
            })

        # 连续打卡天数（学习计划）
        chk_dates = sql_repo.execute_query(
            "SELECT DISTINCT checkin_date FROM study_plan_checkins WHERE user_id = ? ORDER BY checkin_date DESC",
            (user_id,))
        streak_days = 0
        if chk_dates:
            from datetime import date

            def _d(v):
                return v.strftime('%Y-%m-%d') if hasattr(v, 'strftime') else str(v)[:10]

            cursor = date.today()
            seen = {_d(r['checkin_date']) for r in chk_dates}
            while cursor.strftime('%Y-%m-%d') in seen:
                streak_days += 1
                cursor -= timedelta(days=1)

        # 赛道知识点掌握
        track_mastery = ActivityService._build_track_mastery(user_id)

        # 总活动次数
        total_rows = sql_repo.execute_query(
            "SELECT COUNT(*) as cnt FROM user_activity_log WHERE user_id = ?", (user_id,)
        )
        total_activities = total_rows[0]['cnt'] if total_rows else 0

        # 学习打卡总时长与题量
        chk_sum = sql_repo.execute_query(
            "SELECT COALESCE(SUM(study_minutes),0) AS mins, COALESCE(SUM(question_count),0) AS qcnt "
            "FROM study_plan_checkins WHERE user_id = ?",
            (user_id,))
        study_minutes = int(chk_sum[0]['mins']) if chk_sum else 0
        checkin_questions = int(chk_sum[0]['qcnt']) if chk_sum else 0

        # 学习计划统计（总数/进行中/已完成/平均进度）
        plan_rows = sql_repo.execute_query(
            "SELECT status, COUNT(*) AS cnt FROM study_plans "
            "WHERE user_id = ? AND status != 'deleted' GROUP BY status",
            (user_id,))
        plan_cnt = {'active': 0, 'done': 0, 'paused': 0}
        for r in plan_rows:
            if r['status'] in plan_cnt:
                plan_cnt[r['status']] = r['cnt']
        avg_prog = sql_repo.execute_query(
            "SELECT COALESCE(ROUND(AVG(progress),1),0) AS avg_progress FROM study_plans "
            "WHERE user_id = ? AND status != 'deleted'",
            (user_id,))
        plan_avg_progress = float(avg_prog[0]['avg_progress']) if avg_prog else 0

        # 最近活动
        recent = sql_repo.execute_query(
            """SELECT id, activity_type, activity_subtype, detail, score,
                      knowledge_points, related_id, created_at
               FROM user_activity_log WHERE user_id = ?
               ORDER BY created_at DESC LIMIT 20""",
            (user_id,)
        )

        return {
            'active_days': active_days,
            'total_activities': total_activities,
            'exam': {
                'total': exam['total'],
                'avg_score': float(exam['avg_score']),
                'passed': exam['passed']
            },
            'practice': {
                'total': practice['total'],
                'avg_score': float(practice['avg_score'])
            },
            'code': {
                'total': code['total'],
                'avg_score': float(code['avg_score'])
            },
            'practice_redo': {
                'total': practice_redo['total'] or 0,
                'correct': practice_redo['correct'] or 0,
                'rate': round((practice_redo['correct'] or 0) * 100 / (practice_redo['total'] or 0), 1) if (practice_redo['total'] or 0) else 0
            },
            'difficulty_dist': difficulty_dist,
            'streak_days': streak_days,
            'weekly_heatmap': weekly,
            'track_mastery': track_mastery,
            'study_minutes': study_minutes,
            'checkin_questions': checkin_questions,
            'plan': {
                'total': sum(plan_cnt.values()),
                'active': plan_cnt['active'],
                'done': plan_cnt['done'],
                'avg_progress': plan_avg_progress
            },
            'recent_activities': [dict(r) for r in recent]
        }

    @staticmethod
    def _build_heatmap(user_id, now, days_count=365):
        """构建年度热力图：合并 活动日志 / 独立刷题 / 学习打卡 三数据源每日活跃度"""
        start = (now - timedelta(days=days_count - 1)).strftime('%Y-%m-%d')
        end = now.strftime('%Y-%m-%d')

        def _dkey(v):
            return v.strftime('%Y-%m-%d') if hasattr(v, 'strftime') else str(v)[:10]

        act_rows = sql_repo.execute_query(
            "SELECT DATE(created_at) d, COUNT(*) c FROM user_activity_log "
            "WHERE user_id = ? AND DATE(created_at) BETWEEN ? AND ? GROUP BY DATE(created_at)",
            (user_id, start, end))
        pra_rows = sql_repo.execute_query(
            "SELECT DATE(created_at) d, COUNT(*) c FROM practice_attempts "
            "WHERE user_id = ? AND DATE(created_at) BETWEEN ? AND ? GROUP BY DATE(created_at)",
            (user_id, start, end))
        chk_rows = sql_repo.execute_query(
            "SELECT checkin_date d FROM study_plan_checkins "
            "WHERE user_id = ? AND checkin_date BETWEEN ? AND ?",
            (user_id, start, end))

        act_map = {_dkey(r['d']): r['c'] for r in act_rows}
        pra_map = {_dkey(r['d']): r['c'] for r in pra_rows}
        chk_set = {_dkey(r['d']) for r in chk_rows}

        result = []
        for i in range(days_count - 1, -1, -1):
            dt = now - timedelta(days=i)
            day = dt.strftime('%Y-%m-%d')
            count = (act_map.get(day, 0) or 0) + (pra_map.get(day, 0) or 0) + (1 if day in chk_set else 0)
            result.append({
                'date': day,
                'count': count,
                'day_of_week': dt.weekday(),  # 0=Mon, 6=Sun
                'week': (days_count - 1 - i) // 7
            })
        return result

    @staticmethod
    def _build_track_mastery(user_id):
        """构建八个赛道的知识点掌握情况。
        每个赛道下的子知识点，做对5道以上相关题目标记为"已掌握"。
        """
        # 子类别 → 赛道映射
        CAT_TO_TRACK = {
            'python_basics': '公共基础', 'python_advanced': '公共基础', '数据结构': '公共基础',
            'Python基础与环境': '公共基础', '基础': '公共基础', '核心': '公共基础', '进阶': '公共基础',
            'data_processing': '公共基础', '未分类': '公共基础', '数值计算': '公共基础',
            'RAG技术': '大模型', 'Prompt工程': '大模型', '主流大模型': '大模型',
            'Agent与工具调用': '大模型', '大模型基础': '大模型', '大模型应用开发': '大模型',
            '大模型评估与安全': '大模型', '大模型微调': '大模型', '开发框架与工具': '大模型',
            '统计分析与建模': '数据分析及可视化', '数据清洗与预处理': '数据分析及可视化',
            '表格数据分析': '数据分析及可视化', '数据可视化': '数据分析及可视化',
            '数据科学': '数据分析及可视化', '数据存储': '数据分析及可视化',
            '数据预处理': '数据分析及可视化', 'Python基础爬虫库': '数据分析及可视化',
            '机器学习基础': '机器学习', '无监督学习': '机器学习', '集成学习': '机器学习',
            '监督学习': '机器学习', '模型评估与调优': '机器学习', 'scikit-learn库': '机器学习',
            '正则化技术': '机器学习', '机器学习应用': '机器学习', 'practical_scenarios': '机器学习',
            '卷积神经网络': '深度学习', '神经网络基础': '深度学习', '循环神经网络': '深度学习',
            '计算机视觉应用': '深度学习', '深度学习训练技巧': '深度学习', '生成模型': '深度学习',
            '深度学习基础': '深度学习', '序列模型': '深度学习', '自监督学习': '深度学习',
            '迁移学习与预训练': '深度学习', 'PyTorch框架': '深度学习',
            'Transformer架构': '深度学习', 'Transformer与预训练': '深度学习',
            'Seq2Seq与注意力': '深度学习',
            '动态网页爬取': '网络爬虫', '爬虫框架': '网络爬虫', '爬虫进阶与优化': '网络爬虫',
            '反爬虫与应对策略': '网络爬虫', 'HTTP基础与网络原理': '网络爬虫',
            '分布式爬虫': '网络爬虫', '网络爬虫基础': '网络爬虫',
            '实际应用场景与案例': '网络爬虫', '数据解析技术': '网络爬虫',
            '实际应用场景': '网络爬虫',
            'network_automation_libs': '自动化运维', 'network_fundamentals': '自动化运维',
            'configuration_management': '自动化运维', 'monitoring_alerting': '自动化运维',
            'devops_tools': '自动化运维', 'version_control': '自动化运维',
            '文本预处理': '自然语言处理', 'NLP基础': '自然语言处理', 'NLP任务': '自然语言处理',
            'NLP评估指标': '自然语言处理', '词向量技术': '自然语言处理',
            '传统NLP方法': '自然语言处理', 'NLP工具与库': '自然语言处理',
        }

        # 计算每个赛道系统总知识点数
        meta_rows = sql_repo.execute_query(
            "SELECT category, COUNT(*) as cnt FROM knowledge_points_meta GROUP BY category"
        )
        system_totals = {t: 0 for t in ActivityService.TRACKS}
        for mr in meta_rows:
            cat = mr['category'] or '未分类'
            track = CAT_TO_TRACK.get(cat, '公共基础')
            system_totals[track] = system_totals.get(track, 0) + mr['cnt']
        answer_rows = sql_repo.execute_query(
            """SELECT qb.knowledge_point_name, ea.is_correct
               FROM exam_answers ea
               JOIN question_bank qb ON ea.question_id = qb.id
               WHERE ea.student_id = ? AND ea.is_correct IS NOT NULL
                 AND qb.knowledge_point_name IS NOT NULL AND qb.knowledge_point_name != ''""",
            (user_id,)
        )

        # 统计每个知识点名称的做题情况
        kp_stats = {}  # kp_name -> {correct, total}
        for r in answer_rows:
            names = [n.strip() for n in r['knowledge_point_name'].split(',') if n.strip()]
            for name in names:
                if name not in kp_stats:
                    kp_stats[name] = {'correct': 0, 'total': 0}
                kp_stats[name]['total'] += 1
                if r['is_correct']:
                    kp_stats[name]['correct'] += 1

        # 尝试从 knowledge_points_meta 获取赛道-知识点映射
        meta_rows = sql_repo.execute_query(
            "SELECT name, category FROM knowledge_points_meta WHERE category IS NOT NULL AND category != ''"
        )
        # 构建 name → category → track 映射
        name_to_category = {}
        for mr in meta_rows:
            cat = mr['category'].strip()
            nm = mr['name'].strip()
            if cat and nm:
                name_to_category[nm] = cat

        # 按赛道分组：直接用 CAT_TO_TRACK 映射
        tracks_data = {t: {'sub_points': [], 'total_correct': 0, 'total_count': 0} for t in ActivityService.TRACKS}

        for kp_name, stats in kp_stats.items():
            cat = name_to_category.get(kp_name, '未分类')
            track = CAT_TO_TRACK.get(cat, '公共基础')
            tracks_data[track]['sub_points'].append({
                'name': kp_name,
                'correct': stats['correct'],
                'total': stats['total'],
                'mastered': stats['correct'] >= 5
            })
            tracks_data[track]['total_correct'] += stats['correct']
            tracks_data[track]['total_count'] += stats['total']

        # 构建结果，只返回有数据的赛道
        result = []
        for track_name in ActivityService.TRACKS:
            td = tracks_data[track_name]
            # 即使没有答题数据也展示赛道（显示为灰色/未掌握）
            sub = sorted(td['sub_points'], key=lambda x: x['correct'], reverse=True)
            mastered_count = sum(1 for s in sub if s['mastered'])
            total_kp = len(sub)
            result.append({
                'track': track_name,
                'total_kp': total_kp,
                'mastered_kp': mastered_count,
                'total_system_kp': system_totals.get(track_name, 0),
                'total_correct': td['total_correct'],
                'total_count': td['total_count'],
                'sub_points': sub[:30]  # 最多展示30个子知识点
            })

        return result


activity_service = ActivityService()
