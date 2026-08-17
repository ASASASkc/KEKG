# -*- coding: utf-8 -*-
"""Markdown 批量导入解析与模板生成工具"""
import io
import yaml

RESOURCE_TYPE_MAP = {
    'doc': 'doc', '文档': 'doc', '讲义': 'doc', '论文': 'doc', '资料': 'doc',
    'video': 'video', '视频': 'video', '教学视频': 'video',
    'link': 'link', '链接': 'link', '网址': 'link', '参考': 'link',
    'exercise': 'exercise', '练习': 'exercise', '习题': 'exercise',
    'project': 'project', '项目': 'project', '案例': 'project', '开源': 'project',
}


def _normalize_type(raw: str) -> str:
    raw = raw.strip()
    return RESOURCE_TYPE_MAP.get(raw, RESOURCE_TYPE_MAP.get(raw.lower(), ''))


def parse_resources_markdown(text: str, created_by=1) -> dict:
    """解析 Markdown 文本，按 --- 分隔提取资源

    每条资源：
        ---
        YAML frontmatter (标题/类型/知识点ID/难度/链接/标签)
        ---
        Markdown 内容 (可选)
    """
    resources = []
    errors = []
    lines = text.split('\n')

    state = 'idle'          # idle | in_fm | in_body
    fm_lines = []           # 当前条目的 frontmatter 行
    body_lines = []         # 当前条目的 body 行
    in_code_block = False   # 是否在代码块内
    seq = 0

    def _flush():
        nonlocal seq, fm_lines, body_lines, state
        if not fm_lines:
            fm_lines = []
            body_lines = []
            state = 'idle'
            return

        seq += 1
        fm_text = '\n'.join(fm_lines)
        body = '\n'.join(body_lines).strip()

        try:
            meta = yaml.safe_load(fm_text)
            if not isinstance(meta, dict):
                errors.append({'row': seq, 'message': 'frontmatter 解析失败'})
                fm_lines = []
                body_lines = []
                state = 'idle'
                return
        except yaml.YAMLError as e:
            errors.append({'row': seq, 'message': f'YAML 错误: {e}'})
            fm_lines = []
            body_lines = []
            state = 'idle'
            return

        title = str(meta.get('title', meta.get('标题', ''))).strip()
        if not title:
            errors.append({'row': seq, 'message': '缺少标题'})
            fm_lines = []
            body_lines = []
            state = 'idle'
            return

        rtype_raw = str(meta.get('type', meta.get('类型', '')))
        rtype = _normalize_type(rtype_raw)
        if not rtype:
            errors.append({'row': seq, 'message': f'未识别的类型: {rtype_raw}'})
            fm_lines = []
            body_lines = []
            state = 'idle'
            return

        kpid = str(meta.get('knowledge_point_id', meta.get('知识点ID', ''))).strip()
        if not kpid:
            errors.append({'row': seq, 'message': f'缺少知识点ID (标题={title})'})
            fm_lines = []
            body_lines = []
            state = 'idle'
            return

        url = str(meta.get('url', meta.get('链接', ''))).strip()
        tags = str(meta.get('tags', meta.get('标签', ''))).strip()

        # content: body 优先，否则看 meta 里的 content/内容
        content = body.strip()
        if not content:
            content = str(meta.get('content', meta.get('内容', ''))).strip()

        resources.append({
            'title': title,
            'rtype': rtype,
            'knowledge_point_id': kpid,
            'url': url,
            'content': content,
            'tags': tags,
            'created_by': created_by,
        })

        fm_lines = []
        body_lines = []
        state = 'idle'

    for line in lines:
        stripped = line.strip()

        # 检测代码块边界
        if stripped.startswith('```'):
            in_code_block = not in_code_block

        # 代码块内的所有内容保留原样
        if in_code_block:
            if state == 'in_body':
                body_lines.append(line)
            elif state == 'in_fm':
                fm_lines.append(line)
            continue

        # 分隔线 --- (非代码块内)
        if stripped in ('---', '___'):
            if state == 'idle':
                state = 'in_fm'
                continue
            elif state == 'in_fm':
                # 有 YAML 内容才切到 body；否则跳过连续的空 ---
                effective = [l for l in fm_lines if l.strip()]
                if not effective:
                    continue  # 留在 in_fm，等下一个 --- 或真正的 YAML 行
                state = 'in_body'
                continue
            elif state == 'in_body':
                # body 中遇到 ---，结束当前条目，开始下一个
                _flush()
                state = 'in_fm'
                continue

        # 普通行
        if state == 'idle':
            if stripped:  # 跳过非 frontmatter 的无意义行
                pass
        elif state == 'in_fm':
            fm_lines.append(stripped)
        elif state == 'in_body':
            body_lines.append(line)  # body 保留原始行（包括缩进）

    # 文件末尾还有未刷新的条目
    _flush()

    return {
        'resources': resources,
        'errors': errors,
        'total_rows': seq,
    }


def generate_template_markdown() -> str:
    """生成 Markdown 导入模板"""
    return """---
title: Python基础教程
type: doc
knowledge_point_id: py_01
tags: 入门, 必学
---

# Python 基础教程

Python 是一种解释型、面向对象的编程语言，由 Guido van Rossum 于 1991 年创建。

## 变量与数据类型

```python
x = 10              # 整数
y = "Hello World"   # 字符串
z = [1, 2, 3]       # 列表
d = {"name": "张三", "age": 20}  # 字典
```

## 控制流

```python
if x > 5:
    print("x 大于 5")
elif x == 5:
    print("x 等于 5")
else:
    print("x 小于 5")
```

## 循环

```python
for i in range(5):
    print(f"第 {i} 次循环")
```

---

---
title: Python 变量与类型讲解视频
type: video
knowledge_point_id: py_var_01
url: https://www.bilibili.com/video/BVxxx
tags: 入门, 视频教学
---

---
title: Python 官方文档 - 内置函数
type: link
knowledge_point_id: py_func_01
url: https://docs.python.org/zh-cn/3/library/functions.html
tags: 官方, 参考
---

---
title: 变量与类型小练习
type: exercise
knowledge_point_id: py_var_01
tags: 练习, 基础
---

1. 请写出 Python 中的 5 种基本数据类型
2. 判断以下变量的类型:

```python
a = 42
b = 3.14
c = "hello"
d = [1, 2, 3]
e = (1, 2)
f = {"key": "value"}
g = {1, 2, 3}
```

---
title: 开源项目：Python 记账工具
type: project
knowledge_point_id: py_project_01
url: https://github.com/example/py-finance
tags: 实战, 进阶, 完整项目
---

一个完整的 Python 命令行记账工具，适合学习函数、类、文件操作的综合应用。

## 功能
- 收支记录
- 分类统计
- CSV 导出
"""


def generate_template_bytes() -> io.BytesIO:
    """生成模板文件的 BytesIO"""
    text = generate_template_markdown()
    return io.BytesIO(text.encode('utf-8'))
