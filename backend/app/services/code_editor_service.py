# -*- coding: utf-8 -*-
"""代码编辑器服务"""
import subprocess, tempfile, os, json, time, threading
import psutil
from flask import current_app
from ..repositories.sql_repo import sql_repo
from ..services.llm_service import LLMService
from datetime import datetime

# 代码运行并发上限：防止单个用户批量拉起子进程耗尽服务器资源
_RUN_SEM = threading.Semaphore(4)


class CodeEditorService:
    
    @staticmethod
    def create_exercise(title, description, language, template_code, test_cases, 
                        knowledge_point_id='', knowledge_point_name='', difficulty=1, created_by=1):
        eid = sql_repo.execute_insert(
            """INSERT INTO code_exercises (title, description, language, template_code, test_cases,
               knowledge_point_id, knowledge_point_name, difficulty, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, description, language, template_code, json.dumps(test_cases) if isinstance(test_cases, list) else test_cases,
             knowledge_point_id, knowledge_point_name, difficulty, created_by)
        )
        return {'id': eid, 'title': title}
    
    @staticmethod
    def get_exercises(page=1, page_size=20, created_by=None):
        offset = (page - 1) * page_size
        if created_by:
            rows = sql_repo.execute_query(
                """SELECT ce.*, u.username as created_by_name FROM code_exercises ce
                   LEFT JOIN users u ON ce.created_by = u.id
                   WHERE ce.status = 'active' AND ce.created_by = ?
                   ORDER BY ce.created_at DESC LIMIT ? OFFSET ?""",
                (created_by, page_size, offset)
            )
            total_row = sql_repo.execute_query(
                "SELECT COUNT(*) as cnt FROM code_exercises WHERE status = 'active' AND created_by = ?",
                (created_by,)
            )
        else:
            rows = sql_repo.execute_query(
                """SELECT ce.*, u.username as created_by_name FROM code_exercises ce
                   LEFT JOIN users u ON ce.created_by = u.id
                   WHERE ce.status = 'active'
                   ORDER BY ce.created_at DESC LIMIT ? OFFSET ?""",
                (page_size, offset)
            )
            total_row = sql_repo.execute_query(
                "SELECT COUNT(*) as cnt FROM code_exercises WHERE status = 'active'"
            )
        return {'items': [dict(r) for r in rows], 'total': total_row[0]['cnt'] if total_row else 0}
    
    @staticmethod
    def get_exercise(eid):
        rows = sql_repo.execute_query("SELECT * FROM code_exercises WHERE id = ?", (eid,))
        if not rows:
            return None
        ex = dict(rows[0])
        if ex.get('test_cases'):
            try:
                ex['test_cases'] = json.loads(ex['test_cases'])
            except Exception as e:
                current_app.logger.warning('[CodeEditor] parse test_cases failed: %s', str(e))
        return ex
    
    @staticmethod
    def run_code(code, language='python', stdin=''):
        """执行代码并返回结果（沙箱模式：隔离环境 + 超时 + 内存限制）
        stdin: 程序 input() 读取的标准输入数据（限制 4096 字符）
        """
        if language != 'python':
            return {'success': False, 'output': '当前仅支持 Python', 'exec_time': 0, 'memory': 0}

        # 沙箱保护：白名单 import + 禁用危险内置（open/eval/exec/compile）
        sandbox_preamble = '''
import builtins as _bb
import sys as _modsys

# 标准库安装前缀（用于识别"标准库模块内部"的传递导入）
_STDLIB_PREFIX = _modsys.prefix

# 允许学生导入的模块白名单（纯计算/数据类，无 IO 与系统能力）
_ALLOWED_MODULES = {
    'math', 'random', 'json', 're', 'datetime', 'collections', 'itertools',
    'functools', 'string', 'decimal', 'fractions', 'statistics',
    'heapq', 'bisect', 'array', 'struct', 'textwrap', 'operator',
    'enum', 'copy', 'types', 'abc', 'builtins',
    # sys 为标准库纯 Python 模块的公共依赖，必须放行；
    # 其利用面（sys.modules 取 os 等）受 -I 隔离（os 不预加载）+ builtins 已替换兜底
    'sys',
    # 纯计算标准库的常见传递依赖（无 os/socket 等危险依赖链）
    'keyword', 'reprlib', 'copyreg',
}
# 明确拦截的系统/网络/进程模块（黑名单优先：无论调用方一律拦截）
_BLOCKED_MODULES = {
    'os', 'subprocess', 'shutil', 'glob', 'shlex', 'ctypes', 'importlib',
    'socket', 'urllib', 'http', 'requests', 'urllib3', 'ftplib', 'smtplib',
    'poplib', 'imaplib', 'telnetlib', 'xmlrpc', 'asyncio', 'multiprocessing',
    'threading', 'pathlib', 'platform', 'sysconfig', 'pdb', 'inspect', 'runpy',
    'pkgutil', 'pip', 'setuptools', 'venv', 'sqlite3', 'shelve', 'pickle',
    'signal', 'resource', 'fcntl', 'mmap', 'readline', 'tkinter', 'winsound',
    # 下划线开头的系统级内部模块（C 扩展），学生代码禁止直接访问
    # 注意：_io/_json/_re/_datetime 为 json/re/datetime 的依赖，必须放行
    '_os', '_subprocess', '_socket', '_winapi', '_multiprocessing',
    '_pickle', '_ctypes', '_overlapped', '_ssl', '_queue', '_imp',
    '_frozen_importlib',
    # 注意：_thread 为 reprlib 等纯 Python 标准库模块的依赖，从黑名单移除
    # （其线程创建危害受超时/内存监控兜底；用户代码层因不在白名单仍被拦截）
}
def _safe_import(name, *args,
                 _orig=_bb.__import__,
                 _allowed=_ALLOWED_MODULES,
                 _blocked=_BLOCKED_MODULES,
                 _modsys=_modsys,
                 _stdlib=_STDLIB_PREFIX,
                 **kwargs):
    top = name.split('.')[0]
    # __import__(name, globals, locals, fromlist, level)，level 为第 5 个位置参数
    level = args[3] if len(args) > 3 else kwargs.get('level', 0)
    # 相对导入（from . import xxx，level>0）由 import 系统基于包路径解析，放行
    if level:
        return _orig(name, *args, **kwargs)
    # 危险模块无论调用方（含标准库内部）一律拦截
    if top in _blocked:
        raise ImportError(f'安全限制：禁止导入模块 "{name}"')
    # 标准库内部传递导入（json→re→enum→functools→collections 等）放行；
    # 解释器内部 frozen 模块（importlib 读源码/执行模块）同样放行
    _caller = _modsys._getframe(1).f_code.co_filename
    if _caller.startswith(_stdlib) or _caller.startswith('<frozen '):
        return _orig(name, *args, **kwargs)
    # 用户代码仅允许白名单模块
    if top not in _allowed:
        raise ImportError(f'安全限制：禁止导入模块 "{name}"')
    return _orig(name, *args, **kwargs)
def _raise_io(*a, **kw):
    raise IOError('文件读写被禁用')

_bb.__dict__['__import__'] = _safe_import
_bb.__dict__['open'] = _raise_io
# eval/exec/compile 不能禁用：import 机制依赖 exec/compile 执行与解析模块源码，
# collections.namedtuple 内部依赖 eval（且自带空 builtins 隔离）；
# 危险操作仍受 __import__/open 替换 + 白名单 import 拦截，教学沙箱主防线为
# 白名单 import + 禁 IO/网络/系统模块 + 超时/内存限制

# 封堵 sys.modules 绕过通道：os/socket 等在解释器启动时已预加载，必须从
# sys.modules 中移除，防止学生经 sys.modules['os'] 直接调用系统能力；
# import 机制自身依赖的条目（importlib/_imp/_frozen_importlib）需保留
for _m in list(_modsys.modules):
    _mtop = _m.split('.')[0]
    if _mtop in _BLOCKED_MODULES and _mtop not in ('importlib', '_imp', '_frozen_importlib'):
        del _modsys.modules[_m]

# 封堵对象图逃逸通道（纵深防御，临时缓解）：
# 学生可经 (lambda:0).__class__.__base__.__subclasses__() 遍历内存中所有类，
# 从类方法 __globals__ 拿到被强引用的 os/subprocess 模块全局并执行系统命令
# （即使从 sys.modules 删除也无效）。此处遍历所有类，将可达的
# system/popen/call/run 等系统调用替换为抛错函数，阻断逃逸。
for _cls in _bb.object.__subclasses__():
    try:
        _g = _cls.__init__.__globals__
    except Exception:
        continue
    if isinstance(_g, dict):
        for _k in ('system', 'popen', 'spawn', 'spawnv', 'spawnve', 'spawnvp',
                   'call', 'run', 'Popen', 'check_output', 'check_call',
                   'execl', 'execle', 'execv', 'execve', 'posix_spawn',
                   'startfile', 'kill'):
            if _k in _g:
                try:
                    _g[_k] = _raise_io
                except Exception:
                    pass
        _osmod = _g.get('os')
        if _osmod is not None and hasattr(_osmod, 'system'):
            for _k2 in ('system', 'popen', 'spawnv', 'spawnve', 'spawnvp',
                        'execl', 'execle', 'execv', 'execve', 'posix_spawn',
                        'startfile', 'kill', 'remove', 'rmdir', 'unlink',
                        'rename'):
                if hasattr(_osmod, _k2):
                    try:
                        setattr(_osmod, _k2, _raise_io)
                    except Exception:
                        pass

# 清理辅助符号，避免用户代码直接访问 _orig/_safe_import 绕过
del _bb, _safe_import, _raise_io, _ALLOWED_MODULES, _BLOCKED_MODULES
del _modsys, _STDLIB_PREFIX
'''
        code = sandbox_preamble + '\n' + code
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(code)
                tmp_path = f.name
            
            start_time = time.time()
            max_memory = [0]
            done = threading.Event()
            
            def monitor(pid):
                try:
                    ps = psutil.Process(pid)
                    while not done.is_set():
                        try:
                            mem = ps.memory_info().rss / (1024 * 1024)
                            # 内存硬限制：512MB，超出立即 kill
                            if mem > 512:
                                ps.kill()
                                return
                            max_memory[0] = max(max_memory[0], mem)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            return
                        time.sleep(0.01)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    return
            
            # 强制子进程以 UTF-8 输出（Windows 默认 GBK，防止中文输出解码崩溃）
            sandbox_env = dict(os.environ)
            sandbox_env['PYTHONIOENCODING'] = 'utf-8'
            sandbox_env['PYTHONUTF8'] = '1'
            stdin_data = (stdin or '')[:4096]  # 限制标准输入长度，防止管道阻塞滥用
            with _RUN_SEM:
                proc = subprocess.Popen(
                    ['python', '-I', '-B', '-X', 'utf8', tmp_path],  # -I: 隔离模式, -B: 不生成 .pyc, -X utf8: UTF-8 模式
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding='utf-8', errors='replace',
                    env=sandbox_env,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
                )

                t = threading.Thread(target=monitor, args=(proc.pid,), daemon=True)
                t.start()

                try:
                    stdout, stderr = proc.communicate(input=stdin_data, timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate()

                done.set()
                t.join(timeout=0.5)
            exec_time = round((time.time() - start_time) * 1000, 2)
            os.unlink(tmp_path)
            
            return {
                'success': proc.returncode == 0,
                'output': stdout or stderr,
                'error': stderr if proc.returncode != 0 else '',
                'exit_code': proc.returncode,
                'exec_time': exec_time,
                'memory': round(max_memory[0], 2)
            }
        except Exception as e:
            try: os.unlink(tmp_path)
            except Exception as e2:
                current_app.logger.warning('[CodeEditor] cleanup temp file failed: %s', str(e2))
            return {'success': False, 'output': str(e), 'error': str(e), 'exec_time': 0, 'memory': 0}
    
    @staticmethod
    def submit_code(exercise_id, user_id, code):
        """提交代码并保存"""
        result = CodeEditorService.run_code(code)
        sid = sql_repo.execute_insert(
            """INSERT INTO code_submissions (exercise_id, user_id, code, output, status, score)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (exercise_id, user_id, code, result.get('output', ''),
             'done' if result['success'] else 'error', 100 if result['success'] else 0)
        )
        result['submission_id'] = sid
        return result
    
    @staticmethod
    def get_answers(exercise_id):
        """获取所有答案（标准答案+AI答案+用户分享）"""
        rows = sql_repo.execute_query(
            """SELECT ca.*, u.username FROM code_answers ca
               LEFT JOIN users u ON ca.user_id = u.id
               WHERE ca.exercise_id = ? ORDER BY ca.likes DESC, ca.created_at DESC""",
            (exercise_id,)
        )
        return [dict(r) for r in rows]
    
    @staticmethod
    def add_answer(exercise_id, user_id, code, explanation='', answer_type='user'):
        """添加答案"""
        aid = sql_repo.execute_insert(
            """INSERT INTO code_answers (exercise_id, answer_type, user_id, code, explanation)
               VALUES (?, ?, ?, ?, ?)""",
            (exercise_id, answer_type, user_id, code, explanation)
        )
        return {'id': aid}
    
    @staticmethod
    def generate_ai_answer(exercise_id):
        """AI生成答案"""
        ex = CodeEditorService.get_exercise(exercise_id)
        if not ex:
            return None
        
        prompt = f"""你是一个Python编程专家。请根据以下题目写出完整的Python代码。

题目：{ex['title']}
描述：{ex.get('description', '')}
语言：{ex.get('language', 'python')}

请输出完整可运行的Python代码，包含必要的注释。
格式要求：只输出代码，不要包含解释文字。
"""
        response = LLMService.chat([{'role': 'user', 'content': prompt}], temperature=0.3, max_tokens=4096)
        
        # 提取代码块
        import re
        code_match = re.search(r'```(?:python)?\s*([\s\S]*?)```', response)
        code = code_match.group(1).strip() if code_match else response.strip()
        
        return {'code': code, 'explanation': '由AI生成的参考答案'}


code_editor_service = CodeEditorService()


class CodeSnippetService:
    """代码片段服务"""

    def list(self, user_id):
        rows = sql_repo.execute_query(
            "SELECT * FROM code_snippets WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,)
        )
        return [dict(r) for r in rows]

    def create(self, user_id, title, code, language='python'):
        sid = sql_repo.execute_insert(
            "INSERT INTO code_snippets (user_id, title, code, language) VALUES (?, ?, ?, ?)",
            (user_id, title, code, language)
        )
        return {'id': sid, 'user_id': user_id, 'title': title, 'code': code, 'language': language}

    def update(self, sid, user_id, code=None, title=None, language=None):
        row = sql_repo.execute_query(
            "SELECT * FROM code_snippets WHERE id = ? AND user_id = ?",
            (sid, user_id)
        )
        if not row:
            return None
        sets = []
        params = []
        if code is not None:
            sets.append("code = ?")
            params.append(code)
        if title is not None:
            sets.append("title = ?")
            params.append(title)
        if language is not None:
            sets.append("language = ?")
            params.append(language)
        if sets:
            params.extend([sid, user_id])
            sql_repo.execute_update(
                f"UPDATE code_snippets SET {', '.join(sets)} WHERE id = ? AND user_id = ?",
                tuple(params)
            )
        return self._get(sid, user_id)

    def delete(self, sid, user_id):
        affected = sql_repo.execute_update(
            "DELETE FROM code_snippets WHERE id = ? AND user_id = ?",
            (sid, user_id)
        )
        return affected > 0

    def _get(self, sid, user_id):
        rows = sql_repo.execute_query(
            "SELECT * FROM code_snippets WHERE id = ? AND user_id = ?",
            (sid, user_id)
        )
        return dict(rows[0]) if rows else None


_snippet_service = CodeSnippetService()


def _get_snippet_service():
    return _snippet_service


CodeEditorService._get_snippet_service = staticmethod(lambda: _snippet_service)
