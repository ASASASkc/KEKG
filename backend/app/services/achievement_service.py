# -*- coding: utf-8 -*-
"""成就徽章服务（连续打卡 3/7/14/30 天解锁徽章 + 用户徽章墙）"""
from datetime import date, timedelta
from ..repositories.sql_repo import sql_repo

# 徽章定义（condition_type=checkin_streak 表示以连续打卡天数为条件）
BADGES = [
    {'code': 'checkin_3',  'name': '初露锋芒', 'description': '连续打卡 3 天',
     'icon': '3日', 'condition_type': 'checkin_streak', 'condition_value': 3,  'sort_order': 1},
    {'code': 'checkin_7',  'name': '持之以恒', 'description': '连续打卡 7 天',
     'icon': '7日', 'condition_type': 'checkin_streak', 'condition_value': 7,  'sort_order': 2},
    {'code': 'checkin_14', 'name': '坚持不懈', 'description': '连续打卡 14 天',
     'icon': '14日', 'condition_type': 'checkin_streak', 'condition_value': 14, 'sort_order': 3},
    {'code': 'checkin_30', 'name': '学习大师', 'description': '连续打卡 30 天',
     'icon': '30日', 'condition_type': 'checkin_streak', 'condition_value': 30, 'sort_order': 4},
]


class AchievementService:

    @staticmethod
    def ensure_definitions():
        """确保徽章定义写入表中（幂等，INSERT IGNORE）"""
        for b in BADGES:
            sql_repo.execute_update(
                """INSERT IGNORE INTO achievements
                   (code, name, description, icon, condition_type, condition_value, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (b['code'], b['name'], b['description'], b['icon'],
                 b['condition_type'], b['condition_value'], b['sort_order'])
            )

    @staticmethod
    def _calc_streak_days(user_id):
        """计算用户当前连续打卡天数（从今天向前连续，中断则归零）"""
        rows = sql_repo.execute_query(
            "SELECT DISTINCT checkin_date FROM study_plan_checkins WHERE user_id = ? ORDER BY checkin_date DESC",
            (user_id,))
        if not rows:
            return 0
        seen = set()
        for r in rows:
            v = r['checkin_date']
            seen.add(v.strftime('%Y-%m-%d') if hasattr(v, 'strftime') else str(v)[:10])
        cursor = date.today()
        streak = 0
        while cursor.strftime('%Y-%m-%d') in seen:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    @staticmethod
    def refresh_for_user(user_id):
        """重新计算连续打卡天数，解锁所有达标徽章（幂等），返回当前连续天数"""
        AchievementService.ensure_definitions()
        streak = AchievementService._calc_streak_days(user_id)
        for b in BADGES:
            if b['condition_type'] == 'checkin_streak' and streak >= b['condition_value']:
                try:
                    sql_repo.execute_insert(
                        "INSERT IGNORE INTO user_achievements (user_id, achievement_code) VALUES (?, ?)",
                        (user_id, b['code'])
                    )
                except Exception:
                    pass  # 解锁失败不阻断徽章墙
        return streak

    @staticmethod
    def get_wall(user_id):
        """获取用户徽章墙：全部徽章定义 + 解锁状态"""
        AchievementService.ensure_definitions()
        AchievementService.refresh_for_user(user_id)

        defs = sql_repo.execute_query(
            "SELECT * FROM achievements ORDER BY sort_order")
        unlocked = sql_repo.execute_query(
            "SELECT achievement_code, unlocked_at FROM user_achievements WHERE user_id = ?",
            (user_id,))
        umap = {r['achievement_code']: r['unlocked_at'] for r in unlocked}

        items = []
        for d in defs:
            code = d['code']
            ua = umap.get(code)
            items.append({
                'code': code,
                'name': d['name'],
                'description': d['description'],
                'icon': d['icon'],
                'unlocked': code in umap,
                'unlocked_at': str(ua) if ua else None,
            })
        return {
            'streak_days': AchievementService._calc_streak_days(user_id),
            'items': items,
        }


achievement_service = AchievementService()
