"""
MySQL 关系型数据访问层 — 统一后端
"""
import threading
import re
import logging
import pymysql
import pymysql.err
from dbutils.pooled_db import PooledDB
from ..config import Config

_logger = logging.getLogger('sql_repo')

_pool = None


class _MySQLCursorWrapper:
    """包装 pymysql DictCursor，兼容 sqlite3.Cursor 接口"""

    def __init__(self, cursor):
        self._cursor = cursor
        self._rowcount = 0
        self._lastrowid = 0
        self._rows = []

    def execute(self, sql, params=None):
        converted = _MySQLConnectionWrapper._convert_sql(sql)
        self._cursor.execute(converted, params or ())
        self._lastrowid = self._cursor.lastrowid
        self._rowcount = self._cursor.rowcount
        try:
            self._rows = self._cursor.fetchall()
        except Exception:
            self._rows = []
        return self

    def fetchall(self):
        return self._rows

    @property
    def rowcount(self):
        return self._rowcount

    @property
    def lastrowid(self):
        return self._lastrowid

    def __iter__(self):
        return iter(self._rows)


class _MySQLConnectionWrapper:
    """包装 pymysql Connection，兼容 sqlite3.Connection 接口"""

    def __init__(self, conn):
        self._conn = conn

    @staticmethod
    def _convert_sql(sql):
        """将 SQLite 方言转为 MySQL：? → %s, 函数名转换"""
        replacements = [
            ("datetime('now','localtime')", 'NOW()'),
            ('RANDOM()', 'RAND()'),
            ('INSERT OR IGNORE', 'INSERT IGNORE'),
            ('INSERT OR REPLACE', 'REPLACE'),
        ]
        for old, new in replacements:
            sql = sql.replace(old, new)

        parts = []
        in_string = False
        string_char = None
        i = 0
        while i < len(sql):
            ch = sql[i]
            if in_string:
                parts.append(ch)
                if ch == string_char:
                    if i + 1 < len(sql) and sql[i + 1] == string_char:
                        parts.append(string_char)
                        i += 2
                        continue
                    if i > 0 and sql[i - 1] == '\\':
                        pass
                    else:
                        in_string = False
                i += 1
            elif ch in ("'", '"'):
                parts.append(ch)
                in_string = True
                string_char = ch
                i += 1
            elif ch == '?':
                parts.append('%s')
                i += 1
            else:
                parts.append(ch)
                i += 1
        return ''.join(parts)

    def execute(self, sql, params=None):
        cursor = self._conn.cursor(pymysql.cursors.DictCursor)
        wrapper = _MySQLCursorWrapper(cursor)
        wrapper.execute(sql, params)
        return wrapper

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def cursor(self):
        return self._conn.cursor(pymysql.cursors.DictCursor)

    @property
    def open(self):
        try:
            self._conn.ping(reconnect=True)
            return True
        except Exception:
            return False


class MySQLRepository:
    """MySQL 仓库 — 关系型数据访问层"""

    _instance = None
    _lock = threading.Lock()

    @staticmethod
    def _init_pool():
        global _pool
        if _pool is not None:
            return
        _pool = PooledDB(
            creator=pymysql,
            maxconnections=30,
            mincached=2,
            maxcached=30,
            blocking=True,
            ping=1,
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE,
            charset='utf8mb4',
            autocommit=True,
            connect_timeout=10,
            read_timeout=30,
            write_timeout=30,
            cursorclass=pymysql.cursors.DictCursor
        )

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._local = threading.local()
        return cls._instance

    @property
    def _conn(self):
        if not hasattr(self._local, 'conn'):
            self._local.conn = None
        return self._local.conn

    @_conn.setter
    def _conn(self, value):
        self._local.conn = value

    @property
    def _transaction_level(self):
        if not hasattr(self._local, 'level'):
            self._local.level = 0
        return self._local.level

    @_transaction_level.setter
    def _transaction_level(self, value):
        self._local.level = value

    def begin_transaction(self):
        """开启事务（支持嵌套）"""
        if self._transaction_level == 0:
            conn = self.connect()
            conn.execute("SET autocommit=0")
            conn.execute("BEGIN")
        self._transaction_level += 1

    def commit_transaction(self):
        """提交事务"""
        if self._transaction_level > 0:
            self._transaction_level -= 1
            if self._transaction_level == 0 and self._conn:
                self._conn.commit()
                self._conn.execute("SET autocommit=1")

    def rollback_transaction(self):
        """回滚事务"""
        if self._transaction_level > 0:
            self._transaction_level -= 1
            if self._transaction_level == 0 and self._conn:
                self._conn.rollback()
                self._conn.execute("SET autocommit=1")

    def in_transaction(self):
        return self._transaction_level > 0

    def connect(self):
        # ping 底层原始连接，死连接自动重连
        if self._conn is not None:
            try:
                self._conn._conn.ping(reconnect=True)
            except Exception:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

        if self._conn is None:
            with self._lock:
                if self._conn is None:
                    MySQLRepository._init_pool()
                    raw = _pool.connection()
                    self._conn = _MySQLConnectionWrapper(raw)
        return self._conn

    def _close_conn(self):
        """关闭并清空连接（出错时调用）"""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _ensure_connected(self):
        """确保连接可用，丢失则自动重连（别名，实际 connect() 已包含检查）"""
        return self.connect()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute_query(self, query, params=None, retries=2):
        for attempt in range(retries + 1):
            try:
                conn = self._ensure_connected()
                cur = conn.execute(query, params)
                return cur.fetchall()
            except (pymysql.err.InternalError, pymysql.err.OperationalError,
                    ValueError, TypeError, OSError):
                if self._transaction_level > 0 or attempt >= retries:
                    # 事务中不得重连重建连接：会丢失事务上下文并造成静默部分提交
                    raise
                self._close_conn()

    def execute_update(self, query, params=None, retries=2):
        for attempt in range(retries + 1):
            try:
                conn = self.connect()
                cur = conn.execute(query, params)
                if not self._transaction_level:
                    conn.commit()
                return cur.rowcount
            except (pymysql.err.InternalError, pymysql.err.OperationalError,
                    ValueError, TypeError, OSError):
                if self._transaction_level > 0 or attempt >= retries:
                    raise
                self._close_conn()
            except Exception:
                raise

    def execute_insert(self, query, params=None, retries=2):
        for attempt in range(retries + 1):
            try:
                conn = self._ensure_connected()
                cur = conn.execute(query, params)
                if not self._transaction_level:
                    conn.commit()
                return cur.lastrowid
            except (pymysql.err.InternalError, pymysql.err.OperationalError,
                    ValueError, TypeError, OSError):
                if self._transaction_level > 0 or attempt >= retries:
                    raise
                self._close_conn()
            except Exception:
                raise

    def execute_many(self, query, params_list):
        conn = self._ensure_connected()
        converted = _MySQLConnectionWrapper._convert_sql(query)
        cursor = conn.cursor()
        cursor.executemany(converted, params_list or [])
        if not self._transaction_level:
            conn.commit()
        return cursor

    def begin(self):
        """开始事务（兼容旧 API，统一走 autocommit 管理）"""
        self.begin_transaction()

    def commit(self):
        """提交事务（兼容旧 API，统一走 autocommit 管理）"""
        self.commit_transaction()

    def rollback(self):
        """回滚事务（兼容旧 API，统一走 autocommit 管理）"""
        self.rollback_transaction()
    
    def create_tables(self):
        conn = self._ensure_connected()
        ddl_statements = [
            """CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                email VARCHAR(100),
                role VARCHAR(20) DEFAULT 'user',
                is_dev TINYINT DEFAULT 0,
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                parent_id INT DEFAULT 0,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS operation_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                username VARCHAR(50),
                operation_type VARCHAR(50) NOT NULL,
                operation_module VARCHAR(100),
                detail TEXT,
                operation_ip VARCHAR(50),
                operation_result VARCHAR(20) DEFAULT 'success',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS system_config (
                id INT AUTO_INCREMENT PRIMARY KEY,
                `key` VARCHAR(100) UNIQUE NOT NULL,
                `value` TEXT,
                description TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS knowledge_points_meta (
                id INT AUTO_INCREMENT PRIMARY KEY,
                graph_node_id VARCHAR(300) NOT NULL,
                name VARCHAR(255) NOT NULL,
                category VARCHAR(100),
                knowledge_level VARCHAR(100),
                difficulty_level INT DEFAULT 1,
                description TEXT,
                source VARCHAR(255),
                course_id VARCHAR(50),
                code_example TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS classes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                class_code VARCHAR(20) UNIQUE NOT NULL,
                teacher_id INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS class_students (
                id INT AUTO_INCREMENT PRIMARY KEY,
                class_id INT NOT NULL,
                student_id INT NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uk_class_student (class_id, student_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS question_bank (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title TEXT NOT NULL,
                type VARCHAR(20) NOT NULL,
                category VARCHAR(50) NOT NULL DEFAULT '',
                difficulty INT NOT NULL,
                is_multi INT DEFAULT 0,
                options TEXT,
                answer TEXT NOT NULL,
                explanation TEXT,
                knowledge_point_id VARCHAR(50),
               knowledge_point_name TEXT,
               topic VARCHAR(100) DEFAULT '',
               created_by INT NOT NULL,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
               status VARCHAR(20) DEFAULT 'approved',
               code_template TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS question_kp_map (
                id INT AUTO_INCREMENT PRIMARY KEY,
                question_id INT NOT NULL,
                knowledge_point_id VARCHAR(50) NOT NULL,
                UNIQUE(question_id, knowledge_point_id)
            )""",

            """CREATE TABLE IF NOT EXISTS exam_papers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                task_type VARCHAR(20) DEFAULT 'exam',
                description TEXT,
                class_id INT NOT NULL,
                duration_minutes INT NOT NULL DEFAULT 120,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                total_score INT NOT NULL DEFAULT 100,
                pass_score INT NOT NULL DEFAULT 60,
                created_by INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) DEFAULT 'draft'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS exam_questions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                exam_id INT NOT NULL,
                question_id INT NOT NULL,
                score INT NOT NULL DEFAULT 0,
                sort_order INT NOT NULL DEFAULT 0
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS exam_answers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                exam_id INT NOT NULL,
                student_id INT NOT NULL,
                question_id INT NOT NULL,
                student_answer TEXT,
                is_correct INT,
                score INT DEFAULT 0,
                max_score INT NOT NULL,
                review_status VARCHAR(20) DEFAULT 'pending',
                reviewed_by INT,
                review_comment TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                UNIQUE KEY uk_exam_answer (exam_id, student_id, question_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS exam_submissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                exam_id INT NOT NULL,
                student_id INT NOT NULL,
                status VARCHAR(20) DEFAULT 'not_started',
                start_time TIMESTAMP,
                submit_time TIMESTAMP,
                total_score INT,
                auto_score INT DEFAULT 0,
                review_score INT DEFAULT 0,
                is_reviewed INT DEFAULT 0,
                UNIQUE KEY uk_exam_submission (exam_id, student_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS question_categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS relationship_meta (
                id INT AUTO_INCREMENT PRIMARY KEY,
                graph_rel_id VARCHAR(300) NOT NULL,
                source_node_id VARCHAR(300),
                target_node_id VARCHAR(300),
                type VARCHAR(50) NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS graph_labels (
                label VARCHAR(100) PRIMARY KEY,
                display_name VARCHAR(200) NOT NULL,
                description TEXT,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS learning_resources (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                type VARCHAR(20) NOT NULL DEFAULT 'doc',
                url TEXT,
                content TEXT,
                knowledge_point_id VARCHAR(50) NOT NULL,
                tags VARCHAR(200),
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(10) DEFAULT 'active'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS practice_sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                session_id VARCHAR(36) NOT NULL UNIQUE,
                student_id INT NOT NULL,
                question_ids JSON,
                kp_summary VARCHAR(500),
                total INT DEFAULT 0,
                correct_count INT DEFAULT 0,
                score DECIMAL(5,1) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS user_activity_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                activity_type VARCHAR(30) NOT NULL,
                activity_subtype VARCHAR(50),
                knowledge_points TEXT,
                score DECIMAL(5,1),
                related_id INT,
                detail TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS code_exercises (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                language VARCHAR(20) DEFAULT 'python',
                template_code TEXT,
                test_cases TEXT,
                knowledge_point_id VARCHAR(50),
                knowledge_point_name TEXT,
                difficulty INT DEFAULT 1,
                created_by INT,
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS code_submissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                exercise_id INT NOT NULL,
                user_id INT NOT NULL,
                code TEXT,
                output TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                score INT DEFAULT 0,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS code_answers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                exercise_id INT NOT NULL,
                answer_type VARCHAR(20) NOT NULL,
                user_id INT,
                code TEXT,
                explanation TEXT,
                likes INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

            """CREATE TABLE IF NOT EXISTS code_snippets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                title VARCHAR(200) NOT NULL,
                code TEXT,
                language VARCHAR(20) DEFAULT 'python',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        ]

        for stmt in ddl_statements:
            self.execute_update(stmt)

        # study_plans 表（自定义学习计划）
        try:
            conn = self._ensure_connected()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS study_plans (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    knowledge_point_ids JSON,
                    target_date DATE,
                    progress INT DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'active',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_user_id (user_id),
                    INDEX idx_status (status)
                )
            """)
            conn.commit()
        except Exception as e:
            _logger.warning('migration failed: %s', e)

        # study_plans.question_ids（题单化：绑定题目清单，安全迁移）
        try:
            conn = self._ensure_connected()
            conn.execute("ALTER TABLE study_plans ADD COLUMN question_ids JSON")
            conn.commit()
        except Exception as e:
            _logger.warning('migration failed: %s', e)

        # study_plan_checkins 表（学习计划打卡）
        try:
            conn = self._ensure_connected()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS study_plan_checkins (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    plan_id INT NOT NULL,
                    user_id INT NOT NULL,
                    checkin_date DATE NOT NULL,
                    study_minutes INT DEFAULT 0,
                    question_count INT DEFAULT 0,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_plan_date (plan_id, user_id, checkin_date),
                    INDEX idx_plan_id (plan_id),
                    INDEX idx_user_id (user_id)
                )
            """)
            conn.commit()
        except Exception as e:
            _logger.warning('migration failed: %s', e)

        # bg_tasks 表（后台任务状态持久化）
        try:
            conn = self._ensure_connected()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bg_tasks (
                    task_id VARCHAR(36) PRIMARY KEY,
                    task_type VARCHAR(100),
                    status VARCHAR(20) DEFAULT 'pending',
                    progress INT DEFAULT 0,
                    result LONGTEXT,
                    error TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_status (status),
                    INDEX idx_updated_at (updated_at)
                )
            """)
            conn.commit()
        except Exception as e:
            _logger.warning('migration failed: %s', e)

        # class_announcements 表（班级公告）
        try:
            conn = self._ensure_connected()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS class_announcements (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    class_id INT NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    content TEXT,
                    created_by INT NOT NULL,
                    is_pinned TINYINT DEFAULT 0,
                    status VARCHAR(20) DEFAULT 'active',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_class_id (class_id),
                    INDEX idx_status (status)
                )
            """)
            conn.commit()
        except Exception as e:
            _logger.warning('migration failed: %s', e)

        # student_groups 表（班级学生分组）
        try:
            conn = self._ensure_connected()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS student_groups (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    class_id INT NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    created_by INT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_class_id (class_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS student_group_members (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    group_id INT NOT NULL,
                    student_id INT NOT NULL,
                    UNIQUE KEY uk_group_student (group_id, student_id),
                    INDEX idx_group_id (group_id),
                    INDEX idx_student_id (student_id)
                )
            """)
            conn.commit()
        except Exception as e:
            _logger.warning('migration failed: %s', e)

        # practice_attempts 表（学生独立刷题记录）
        try:
            conn = self._ensure_connected()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS practice_attempts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    question_id INT NOT NULL,
                    user_answer TEXT,
                    is_correct INT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_practice_user (user_id, question_id)
                )
            """)
            conn.commit()
        except Exception as e:
            _logger.warning('migration failed: %s', e)

        # practice_attempts.elapsed_seconds（提交记录用时，安全迁移）
        try:
            conn = self._ensure_connected()
            conn.execute("ALTER TABLE practice_attempts ADD COLUMN elapsed_seconds INT DEFAULT 0")
            conn.commit()
        except Exception as e:
            _logger.warning('migration failed: %s', e)

        # notifications 表（站内通知）
        try:
            conn = self._ensure_connected()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    type VARCHAR(30) NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    content TEXT,
                    related_id INT DEFAULT 0,
                    related_type VARCHAR(20) DEFAULT '',
                    is_read TINYINT DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_notif_user (user_id, is_read),
                    INDEX idx_notif_time (user_id, created_at)
                )
            """)
            conn.commit()
        except Exception as e:
            _logger.warning('migration failed: %s', e)

        # exam_analyses 表（教师发布的标准解析，可按题置顶）
        try:
            conn = self._ensure_connected()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS exam_analyses (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    exam_id INT NOT NULL,
                    question_id INT NOT NULL,
                    content TEXT NOT NULL,
                    is_pinned TINYINT DEFAULT 1,
                    created_by INT DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_exam_question (exam_id, question_id),
                    INDEX idx_exam (exam_id)
                )
            """)
            conn.commit()
        except Exception as e:
            _logger.warning('migration failed: %s', e)

        # 迁移：安全执行（忽略已存在的列/表错误）
        # 注意：topic、code_template、task_type 已内置在对应表的 DDL 中，不再需要 ALTER
        migrations = [
            # knowledge_point_name 列扩容
            """ALTER TABLE question_bank MODIFY COLUMN knowledge_point_name TEXT""",
            # exam_submissions 添加 attempt_count 列
            """ALTER TABLE exam_submissions ADD COLUMN attempt_count INT DEFAULT 1 AFTER status""",
            # exam_papers 添加 max_attempts 列（可配置答题次数，NULL=考试1次/作业无限）
            """ALTER TABLE exam_papers ADD COLUMN max_attempts INT DEFAULT NULL AFTER pass_score""",
            # exam_papers 添加 weight_config 列（加权配置 JSON）
            """ALTER TABLE exam_papers ADD COLUMN weight_config TEXT AFTER max_attempts""",
            # user_activity_log 添加 notes 列
            """ALTER TABLE user_activity_log ADD COLUMN notes TEXT AFTER detail""",
            # status 列扩容 + 默认值更新（AI 审核流程）
            """ALTER TABLE question_bank MODIFY COLUMN status VARCHAR(20) DEFAULT 'approved'""",
            # 将旧 active 状态统一为 approved
            """UPDATE question_bank SET status = 'approved' WHERE status = 'active'""",
            # exam_submissions 添加 review_draft 列（批阅草稿状态）
            """ALTER TABLE exam_submissions ADD COLUMN review_draft INT DEFAULT 0 AFTER is_reviewed""",
            # users 添加 is_dev 列（开发者标识，替代"用户名=admin"的脆弱判定）
            """ALTER TABLE users ADD COLUMN is_dev TINYINT DEFAULT 0 AFTER role""",
            # 存量迁移：默认开发者账号（admin/admin）置为 is_dev=1
            """UPDATE users SET is_dev = 1 WHERE username = 'admin' AND role = 'admin'""",
            # exam_answers 添加 redo_status 列（错题重练状态：redo_pending / redo_correct）
            """ALTER TABLE exam_answers ADD COLUMN redo_status VARCHAR(20)""",
            # 性能索引：活动统计/错题本按 user_id、student_id 查询，避免全表扫描
            """ALTER TABLE user_activity_log ADD INDEX idx_ual_user (user_id)""",
            """ALTER TABLE exam_answers ADD INDEX idx_ea_student (student_id, is_correct)""",
            """ALTER TABLE question_bank ADD INDEX idx_qb_kp (knowledge_point_id)""",
        ]
        for stmt in migrations:
            try:
                self.execute_update(stmt)
            except Exception as e:
                _logger.warning('[SQLRepo] migration failed: %s', str(e))

        # rate_limit_logs 表（全局限流 MySQL 集中滑动窗口，多 worker 共享）
        try:
            conn = self._ensure_connected()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rate_limit_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    rl_key VARCHAR(255) NOT NULL,
                    request_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_rl_key_time (rl_key, request_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            conn.commit()
        except Exception as e:
            _logger.warning('migration failed: %s', e)

        # achievements 表（成就徽章定义）
        try:
            conn = self._ensure_connected()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS achievements (
                    code VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description VARCHAR(255) NOT NULL,
                    icon VARCHAR(20) DEFAULT '',
                    condition_type VARCHAR(30) NOT NULL,
                    condition_value INT NOT NULL DEFAULT 0,
                    sort_order INT DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            conn.commit()
        except Exception as e:
            _logger.warning('migration failed: %s', e)

        # user_achievements 表（用户已解锁徽章）
        try:
            conn = self._ensure_connected()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_achievements (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    achievement_code VARCHAR(50) NOT NULL,
                    unlocked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_user_ach (user_id, achievement_code),
                    INDEX idx_ach_user (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            conn.commit()
        except Exception as e:
            _logger.warning('migration failed: %s', e)

        # question_favorites 表（题目收藏，每人每题唯一）
        try:
            conn = self._ensure_connected()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS question_favorites (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    question_id INT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_fav_user_q (user_id, question_id),
                    INDEX idx_fav_user (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            conn.commit()
        except Exception as e:
            _logger.warning('migration failed: %s', e)


# 全局单例
sql_repo = MySQLRepository()
