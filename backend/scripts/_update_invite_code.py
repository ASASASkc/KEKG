# -*- coding: utf-8 -*-
"""更新系统邀请码为强随机值（安全加固）"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.repositories.sql_repo import sql_repo

sql_repo.execute_update(
    "UPDATE system_config SET value = ? WHERE `key` = 'invite_code'",
    ('189826E6302F',))
print('invite_code updated')
