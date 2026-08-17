# -*- coding: utf-8 -*-
"""
LLM 服务 — DeepSeek API 调用封装
"""
import json
import base64
import logging
import requests
from flask import current_app
from ..repositories.sql_repo import sql_repo

# LLM 专用 logger
_llm_logger = logging.getLogger('llm')


def _get_encode_key():
    """从配置获取加密密钥"""
    key = current_app.config.get('LLM_ENCODE_KEY')
    if not key:
        # 开发环境回退（不应在生产中使用）
        _llm_logger.warning('[LLM] LLM_ENCODE_KEY 未配置，使用硬编码回退密钥')
        key = "kekg_llm_2024" * 2
    # 确保 32 字节
    if isinstance(key, str):
        key = key.encode('utf-8')
    if len(key) < 32:
        key = (key * (32 // len(key) + 1))[:32]
    return key


def _mask_key(key: str) -> str:
    """编码 API key（XOR 混淆）"""
    if not key:
        return ""
    ek = _get_encode_key()
    key_bytes = key.encode('utf-8')
    cycle = (ek * ((len(key_bytes) // len(ek)) + 1))[:len(key_bytes)]
    return base64.urlsafe_b64encode(
        bytes([a ^ b for a, b in zip(key_bytes, cycle)])
    ).decode()


def _unmask_key(encoded: str) -> str:
    """解码 API key"""
    if not encoded:
        return ""
    ek = _get_encode_key()
    data = base64.urlsafe_b64decode(encoded)
    cycle = (ek * ((len(data) // len(ek)) + 1))[:len(data)]
    return bytes([a ^ b for a, b in zip(data, cycle)]).decode('utf-8')


class LLMService:
    """LLM 服务"""
    
    # 配置默认值（优先从 current_app.config 读取，此处仅作最终兜底）
    _CONFIG_FALLBACK = {
        'llm_api_key': '',
        'llm_base_url': 'https://api.deepseek.com',
        'llm_model': 'deepseek-chat',
    }

    # config key → Config 类属性映射
    _CONFIG_ENV_MAP = {
        'llm_base_url': 'LLM_BASE_URL',
        'llm_model': 'LLM_MODEL',
        'llm_api_key': 'LLM_API_KEY',
    }

    @classmethod
    def _get_config(cls, key: str) -> str:
        # 1. 优先从数据库读取（用户可在 UI 中修改）
        rows = sql_repo.execute_query(
            "SELECT value FROM system_config WHERE `key` = %s", (key,)
        )
        if rows:
            return rows[0]['value'] or ''
        # 2. 从 Flask app config 读取（.env 注入）
        try:
            env_key = cls._CONFIG_ENV_MAP.get(key)
            if env_key:
                val = current_app.config.get(env_key)
                if val:
                    return val
        except RuntimeError:
            pass
        # 3. 兜底默认值
        return cls._CONFIG_FALLBACK.get(key, '')
    
    @classmethod
    def _set_config(cls, key: str, value: str):
        sql_repo.execute_update(
            "INSERT INTO system_config (`key`, value) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE value = VALUES(value)",
            (key, value)
        )
    
    @classmethod
    def get_config(cls) -> dict:
        """获取 LLM 配置（含脱敏后的 API key）"""
        api_key = cls._get_config('llm_api_key')
        masked = ''
        if api_key:
            try:
                real = _unmask_key(api_key)
                if len(real) > 8:
                    masked = real[:4] + '*' * (len(real) - 8) + real[-4:]
                else:
                    masked = '*' * len(real)
            except Exception:
                masked = '***'
        
        return {
            'api_key': api_key,
            'api_key_masked': masked,
            'base_url': cls._get_config('llm_base_url') or 'https://api.deepseek.com',
            'model': cls._get_config('llm_model') or 'deepseek-chat',
            'has_key': bool(api_key),
        }
    
    @classmethod
    def save_config(cls, api_key: str, base_url: str, model: str) -> dict:
        """保存 LLM 配置"""
        if api_key:
            cls._set_config('llm_api_key', _mask_key(api_key))
        if base_url:
            cls._set_config('llm_base_url', base_url)
        if model:
            cls._set_config('llm_model', model)
        return cls.get_config()
    
    @classmethod
    def get_api_key(cls) -> str:
        """获取解密后的 API key"""
        encoded = cls._get_config('llm_api_key')
        if not encoded:
            return ''
        try:
            return _unmask_key(encoded)
        except Exception:
            return ''
    
    @classmethod
    def test_connection(cls) -> dict:
        """测试 API 连接"""
        api_key = cls.get_api_key()
        if not api_key:
            return {'success': False, 'message': '请先配置 API Key'}
        
        base_url = cls._get_config('llm_base_url') or 'https://api.deepseek.com'
        model = cls._get_config('llm_model') or 'deepseek-chat'
        url = f"{base_url.rstrip('/')}/v1/chat/completions"
        
        try:
            resp = requests.post(
                url,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': 'hi'}],
                    'max_tokens': 10,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                return {'success': True, 'message': f'连接成功 ({model})'}
            data = resp.json()
            err = data.get('error', {}).get('message', resp.text[:200])
            return {'success': False, 'message': f'API 错误: {err}'}
        except requests.exceptions.Timeout:
            return {'success': False, 'message': '连接超时，请检查网络或 API 地址'}
        except Exception as e:
            return {'success': False, 'message': f'连接失败: {str(e)[:200]}'}
    
    @classmethod
    def chat(cls, messages: list, temperature: float = 0.7, max_tokens: int = 8192) -> str:
        """通用对话调用"""
        api_key = cls.get_api_key()
        if not api_key:
            raise ValueError('请先配置 LLM API Key')
        
        base_url = cls._get_config('llm_base_url') or 'https://api.deepseek.com'
        model = cls._get_config('llm_model') or 'deepseek-chat'
        url = f"{base_url.rstrip('/')}/v1/chat/completions"
        
        msg_len = sum(len(m.get('content', '')) for m in messages)
        _llm_logger.info('[LLM.chat] 调用 %s (%s) | tokens=%d, temp=%.1f, msgs_len=%d',
                         model, url, max_tokens, temperature, msg_len)
        
        resp = requests.post(
            url,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': model,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        usage = data.get('usage', {})
        content = data['choices'][0]['message']['content']
        _llm_logger.info('[LLM.chat] 完成 | prompt_tokens=%s, completion_tokens=%s, total=%s | content_len=%d',
                         usage.get('prompt_tokens', '?'),
                         usage.get('completion_tokens', '?'),
                         usage.get('total_tokens', '?'),
                         len(content))
        return content


class QuestionGenerator:
    """LLM 出题引擎 — 根据知识点信息批量生成题目"""

    VALID_TYPES = ('choice', 'multi_choice', 'judge', 'code', 'subjective')

    TYPE_DESC = {
        'choice': '单选题（4个选项A/B/C/D，只有一个正确答案）',
        'multi_choice': '多选题（4个选项A/B/C/D，可多个正确答案，answer用逗号分隔）',
        'judge': '判断题（答案填"对"或"错"）',
        'code': '编程题（需包含函数签名和至少一个测试用例，code_template字段必填）',
        'subjective': '简答题（答案为简短文字说明）',
    }

    @staticmethod
    def calc_difficulty(kp_count):
        """根据知识点数量计算难度: log2(kp_count)+1，上限 12"""
        import math
        if kp_count <= 0:
            return 1
        return min(int(math.log2(kp_count)) + 1, 12)

    @staticmethod
    def _build_kp_context(kp_info):
        """将知识点信息列表拼成上下文文本"""
        parts = []
        for i, kp in enumerate(kp_info):
            props = kp.get('properties', {}) if isinstance(kp, dict) else {}
            parts.append(f"【知识点 {i + 1}】")
            parts.append(f"名称: {props.get('name', '未知')}")
            if props.get('description'):
                parts.append(f"描述: {props.get('description')}")
            if props.get('syntax'):
                parts.append(f"语法: {props.get('syntax')}")
            if props.get('examples'):
                parts.append(f"示例: {props.get('examples')}")
            if props.get('code_example'):
                parts.append(f"代码示例: {props.get('code_example')}")
            parts.append("")
        return '\n'.join(parts)

    @staticmethod
    def _build_prompt(kp_context, question_types, questions_per_kp, difficulty):
        """组装完整 Prompt"""
        type_list = [QuestionGenerator.TYPE_DESC[t] for t in question_types]

        prompt = f"""你是一个专业的教育出题专家。请根据以下知识点信息，为每个知识点生成{questions_per_kp}道高质量题目。

{{
            "知识点信息"
        }}

{kp_context}

{{
            "出题要求"
        }}
1. 题目类型（请均衡分配各类型）：{', '.join(type_list)}
2. 难度等级：{difficulty}/12（12为最高难度）
3. 题目语言：中文
4. 每个知识点生成恰好{questions_per_kp}道题目
5. 题目应贴近知识点内容，考察理解深度而非简单记忆

{{
            "输出格式"
        }}
请严格按照以下 JSON 数组格式输出（仅输出 JSON，不要包含任何其他文字说明）：

```json
[
  {{
    "title": "题目内容",
    "type": "choice/multi_choice/judge/code/subjective",
    "options": ["A. 选项A", "B. 选项B", "C. 选项C", "D. 选项D"],
    "answer": "正确答案（多选用逗号分隔，判断填对/错）",
    "explanation": "题目解析说明",
    "code_template": "编程题必填：包含函数签名和至少一个测试用例。非编程题填空字符串"
  }}
]
```

注意：
- 编程题 code_template 字段必填，包含函数签名和至少一个测试用例
- 选择题和多选题 options 必填，至少4个选项（带A/B/C/D前缀）
- 判断题答案仅填"对"或"错"，options 填空数组
- 简答题 answer 填简要答案即可
- 所有字段均为字符串类型（options 为字符串数组）"""

        return prompt

    @staticmethod
    def _parse_response(response_text):
        """解析 LLM 返回的 JSON（优先提取 ```json 代码块，回退原始解析）"""
        import re

        # 优先提取 ```json ... ``` 代码块
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response_text)
        if json_match:
            json_str = json_match.group(1).strip()
            _llm_logger.debug('[QuestionGenerator] 解析: 提取到 ```json 代码块, len=%d', len(json_str))
        else:
            # 回退：查找 JSON 数组
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                json_str = json_match.group(0)
                _llm_logger.debug('[QuestionGenerator] 解析: 提取到 JSON 数组, len=%d', len(json_str))
            else:
                json_str = response_text
                _llm_logger.warning('[QuestionGenerator] 解析: 未找到 JSON 结构, raw_len=%d, raw_preview=%s',
                                    len(response_text), response_text[:200])

        try:
            data = json.loads(json_str)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # 兼容 {"questions": [...]} 等包装格式
                for key in ('questions', 'data', 'items', 'results'):
                    if key in data and isinstance(data[key], list):
                        _llm_logger.debug('[QuestionGenerator] 解析: 从 "%s" 键提取 %d 条', key, len(data[key]))
                        return data[key]
                return [data]
        except json.JSONDecodeError as e:
            _llm_logger.error('[QuestionGenerator] JSON 解析失败: %s | raw=%s...', str(e), json_str[:300])
            return []

    @staticmethod
    def _sanitize_question(q):
        """校验 title/type/answer 必填，type 必须在有效范围内"""
        if not isinstance(q, dict):
            return False
        title = (q.get('title') or '').strip()
        qtype = (q.get('type') or '').strip()
        answer = (q.get('answer') or '').strip()

        if not title or not qtype or not answer:
            return False
        if qtype not in QuestionGenerator.VALID_TYPES:
            return False

        # 编程题必须提供 code_template
        if qtype == 'code' and not (q.get('code_template') or '').strip():
            return False

        return True

    @classmethod
    def generate_questions(cls, knowledge_points, questions_per_kp, question_types=None):
        """
        主入口：批量生成题目

        Args:
            knowledge_points: 知识点节点列表
            questions_per_kp: 每个知识点生成题目数（1-5）
            question_types: 题型列表，默认全部

        Returns:
            list[dict]: 有效的题目列表
        """
        if question_types is None:
            question_types = list(cls.VALID_TYPES)
        else:
            question_types = [t for t in question_types if t in cls.VALID_TYPES]
            if not question_types:
                question_types = list(cls.VALID_TYPES)

        kp_context = cls._build_kp_context(knowledge_points)
        difficulty = cls.calc_difficulty(len(knowledge_points))
        _llm_logger.info('[QuestionGenerator] 生成题目: kp=%d, per_kp=%d, difficulty=%d, types=%s',
                         len(knowledge_points), questions_per_kp, difficulty, question_types)
        
        prompt = cls._build_prompt(kp_context, question_types, questions_per_kp, difficulty)
        _llm_logger.debug('[QuestionGenerator] Prompt 长度: %d chars', len(prompt))

        messages = [{'role': 'user', 'content': prompt}]
        response_text = LLMService.chat(messages, temperature=0.8, max_tokens=16384)

        questions = cls._parse_response(response_text)
        _llm_logger.info('[QuestionGenerator] LLM 返回 %d 条记录，解析出 %d 条',
                         len(questions) if questions else 0, len(questions) if questions else 0)
        
        valid_questions = [q for q in questions if cls._sanitize_question(q)]
        invalid_count = len(questions) - len(valid_questions)
        if invalid_count > 0:
            _llm_logger.warning('[QuestionGenerator] %d 条题目校验未通过，已丢弃', invalid_count)

        return valid_questions


class KnowledgeEnricher:
    """LLM 知识点补全引擎 — 批量补全 description + syntax examples"""

    PROMPT_TEMPLATE = """你是一个专业的技术教育专家。请根据知识点名称，生成清晰的中文描述和语法案例。

知识点名称：{name}
所属分类：{category}
现有描述：{current_desc}
现有语法：{current_syntax}

请输出 JSON（仅输出 JSON，不要其他内容）：
{{
  "description": "一段 80-200 字的中文描述，清晰解释该知识点的核心概念、用途和关键要点",
  "syntax": "语法说明或代码示例，30-200 字。如果是编程概念给代码示例；如果是理论概念给关键公式或要点"
}}

要求：
- description 简洁清晰，适合学生快速理解
- syntax 根据知识点类型灵活处理：编程类给 Python 代码示例，理论类给公式/要点
- 如果现有描述/语法已足够好，可适当精简优化后输出
- 不要凭空编造不存在的内容"""

    def __init__(self):
        self._llm = LLMService

    @staticmethod
    def _build_prompt(node):
        """根据节点属性组装补全 Prompt"""
        props = node.get('properties', {}) if isinstance(node, dict) else {}
        name = props.get('name', '')
        category = props.get('category', '')
        current_desc = props.get('description', '') or '（暂无描述）'
        current_syntax = props.get('syntax', '') or '（暂无语法说明）'

        prompt = KnowledgeEnricher.PROMPT_TEMPLATE.format(
            name=name,
            category=category,
            current_desc=current_desc[:300],
            current_syntax=current_syntax[:300],
        )
        return prompt

    @staticmethod
    def _parse_response(response_text):
        """解析 LLM 返回的 JSON，提取 description + syntax"""
        import re
        json_str = None

        # 策略1：提取 ```json ``` 代码块
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response_text)
        if json_match:
            json_str = json_match.group(1).strip()

        # 策略2：提取完整 { } 对
        if not json_str:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group(0)

        # 策略3：尝试从截断的 JSON 中用正则直接提取字段
        def extract_field(field_name):
            m = re.search(r'"' + field_name + r'"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', response_text)
            return m.group(1) if m else ''

        if json_str:
            try:
                data = json.loads(json_str)
                return {
                    'description': (data.get('description') or '').strip(),
                    'syntax': (data.get('syntax') or '').strip(),
                }
            except json.JSONDecodeError as e:
                _llm_logger.error('[KnowledgeEnricher] JSON 解析失败: %s | raw=%s',
                                  str(e), response_text[:200])

        # JSON 解析失败（可能被截断），用正则兜底提取
        desc = extract_field('description')
        syntax = extract_field('syntax')
        if desc or syntax:
            _llm_logger.warning('[KnowledgeEnricher] 正则兜底提取: desc=%d字 syntax=%d字',
                                len(desc), len(syntax))
            return {'description': desc, 'syntax': syntax}

        _llm_logger.error('[KnowledgeEnricher] 所有解析策略均失败, raw=%s', response_text[:200])
        return {'description': '', 'syntax': ''}

    def enrich_single(self, node):
        """
        补全单个知识点

        Args:
            node: Neo4j 节点 dict（含 properties）

        Returns:
            dict: {'name': str, 'description': str, 'syntax': str} 或 None
        """
        props = node.get('properties', {}) if isinstance(node, dict) else {}
        name = props.get('name', '')
        prompt = self._build_prompt(node)
        _llm_logger.debug('[KnowledgeEnricher] 补全: "%s" prompt_len=%d', name, len(prompt))

        try:
            response_text = self._llm.chat(
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.3,
                max_tokens=1024,
            )
        except Exception as e:
            _llm_logger.error('[KnowledgeEnricher] LLM 调用失败: "%s" — %s', name, str(e))
            return None

        result = self._parse_response(response_text)
        result['name'] = name
        if result['description'] or result['syntax']:
            _llm_logger.debug('[KnowledgeEnricher] 成功: "%s" desc_len=%d syntax_len=%d',
                              name, len(result['description']), len(result['syntax']))
            return result

        _llm_logger.warning('[KnowledgeEnricher] 解析为空: "%s"', name)
        return None

    def enrich_batch(self, node_ids, progress_callback=None):
        """
        批量补全知识点

        Args:
            node_ids: list[str] - Neo4j elementId 列表
            progress_callback: callable(current, total, result) 进度回调

        Returns:
            dict: {enriched: int, failed: int, total: int, details: [...]}
        """
        from ..repositories.graph_repo import graph_repo
        total = len(node_ids)
        enriched = 0
        failed = 0
        details = []

        for idx, nid in enumerate(node_ids):
            node = graph_repo.get_node_by_id(str(nid))
            if not node:
                _llm_logger.warning('[KnowledgeEnricher] 节点未找到: %s', nid)
                failed += 1
                details.append({'id': str(nid), 'name': '?', 'status': 'not_found'})
                if progress_callback:
                    progress_callback(idx + 1, total, {'id': str(nid), 'name': '?', 'status': 'not_found'})
                continue

            result = self.enrich_single(node)
            name = (node.get('properties', {}) or {}).get('name', '?') if isinstance(node, dict) else '?'

            if result and (result['description'] or result['syntax']):
                # 写回 Neo4j
                try:
                    with graph_repo._session() as session:
                        set_clauses = []
                        params = {'nid': nid}
                        if result['description']:
                            set_clauses.append("n.description = $description")
                            params['description'] = result['description']
                        if result['syntax']:
                            set_clauses.append("n.syntax = $syntax")
                            params['syntax'] = result['syntax']
                        if set_clauses:
                            session.run(
                                "MATCH (n:KnowledgePoint) WHERE elementId(n) = $nid "
                                "SET " + ", ".join(set_clauses),
                                params
                            )
                    enriched += 1
                    details.append({'id': str(nid), 'name': name, 'status': 'enriched',
                                    'description': result['description'][:80],
                                    'syntax': result['syntax'][:80]})
                    if progress_callback:
                        progress_callback(idx + 1, total, details[-1])
                except Exception as e:
                    _llm_logger.error('[KnowledgeEnricher] 写回 Neo4j 失败: "%s" — %s', name, str(e))
                    failed += 1
                    details.append({'id': str(nid), 'name': name, 'status': 'db_error', 'error': str(e)})
                    if progress_callback:
                        progress_callback(idx + 1, total, details[-1])
            else:
                failed += 1
                details.append({'id': str(nid), 'name': name, 'status': 'empty_result'})
                if progress_callback:
                    progress_callback(idx + 1, total, details[-1])

        _llm_logger.info('[KnowledgeEnricher] 批量完成: enriched=%d, failed=%d, total=%d',
                         enriched, failed, total)
        return {'enriched': enriched, 'failed': failed, 'total': total, 'details': details}

    # ============ 外部链接补全 ============

    LINKS_PROMPT = """你是一个IT教育资源推荐专家。请为以下知识点推荐 1-3 个高质量学习链接。

知识点名称：{name}
所属分类：{category}
知识点描述：{desc}

请推荐：
- 中文课程/教程链接优先（B站、中国大学MOOC、实验楼、菜鸟教程、廖雪峰等）
- 其次推荐对应技术栈的官方文档
- 链接必须是真实存在的，不要编造

输出 JSON（仅输出 JSON）：
{{
  "links": [
    {{"title": "链接标题（含来源平台名）", "url": "https://..."}},
    {{"title": "链接标题（含来源平台名）", "url": "https://..."}}
  ]
}}

要求：
- 至少 1 个，最多 3 个链接
- 优先中文资源
- URL 必须是真实的、可访问的
- 标题清晰说明资源类型（教程/文档/视频/课程）"""

    def enrich_external_links_single(self, node):
        """为单个节点生成外部链接"""
        props = node.get('properties', {}) if isinstance(node, dict) else {}
        name = props.get('name', '')
        category = props.get('category', '')
        desc = (props.get('description', '') or '')[:200]
        prompt = self.LINKS_PROMPT.format(name=name, category=category, desc=desc)
        _llm_logger.debug('[LinksEnricher] 补全链接: "%s"', name)

        try:
            response_text = self._llm.chat(
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.3,
                max_tokens=512,
            )
        except Exception as e:
            _llm_logger.error('[LinksEnricher] LLM 调用失败: "%s" — %s', name, str(e))
            raise  # 由上层路由重试

        # 解析 JSON
        import re
        json_str = None
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response_text)
        if json_match:
            json_str = json_match.group(1).strip()
        if not json_str:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group(0)
        if json_str:
            try:
                import json as _json
                data = _json.loads(json_str)
                links = data.get('links', [])
                valid_links = [l for l in links if l.get('url', '').startswith('http')]
                if valid_links:
                    return {'links': valid_links}
            except Exception as e:
                _llm_logger.error('[LinksEnricher] JSON 解析失败: "%s" — %s', name, str(e))
        return None
