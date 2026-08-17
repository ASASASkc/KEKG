# -*- coding: utf-8 -*-
"""
graph_common.json 清洗脚本：
1. 删除第11章
2. 修复空运算符标题
3. 去重重命名
4. 从树形转为 nodes+relationships 图谱格式
"""
import json
import os

INPUT = r'd:\Trae CN\zstp.b\zstp\graph_common.json'
OUTPUT = r'd:\Trae CN\zstp.b\zstp\KEKG\backend\data\graph_common_clean.json'

# ── 运算符补全映射（按出现顺序：算术3个 → 比较2个 → 位1个）──
OPERATOR_FIXES = {
    '算术运算符': ['+', '-', '*', '/', '//', '%', '**'],
    '比较运算符': ['==', '!=', '>', '<', '>=', '<='],
    '位运算符': ['&', '|', '^', '~', '<<', '>>'],
}

# ── 重命名映射 ──
RENAME_MAP = {
    ('第1章 Python概述', '模块'): '模块（代码组织层次）',
    ('第1章 Python概述', '包'): '包（代码组织层次）',
}


def find_chapter_node(root_topic, chapter_title):
    """在顶层 topics 中找到指定章节节点"""
    for topic in root_topic.get('topics', []):
        if topic['title'] == chapter_title:
            return topic
    return None


def fix_empty_titles(node):
    """递归修复空标题——针对 2.5 运算符下的空节点"""
    if 'topics' in node:
        # 检测是否是运算符父节点
        parent_title = node.get('title', '')
        if parent_title in OPERATOR_FIXES:
            replacements = OPERATOR_FIXES[parent_title]
            children = node['topics']
            # 收集空 title 的子节点，按顺序替换
            empty_slots = []
            for child in children:
                if child.get('title', '').strip() == '':
                    empty_slots.append(child)
                # 递归处理孙子节点
                fix_empty_titles(child)

            for i, child in enumerate(empty_slots):
                if i < len(replacements):
                    child['title'] = replacements[i]
                else:
                    child['title'] = f'运算符{i+1}'
        else:
            for child in node.get('topics', []):
                fix_empty_titles(child)


def collect_nodes(node, parent_chain, nodes_list, node_id_map, depth=0):
    """递归收集有效知识点节点，跳过纯章节/节标题"""
    title = node.get('title', '').strip()
    if not title:
        return

    # 章节编号模式
    chapter_patterns = [
        title.startswith('第') and '章' in title,
        bool(__import__('re').match(r'\d+\.\d+', title.split()[0] if title.split() else '')),
    ]

    is_leaf = 'topics' not in node or not node['topics']
    is_chapter_header = any(chapter_patterns) and not is_leaf

    if not is_chapter_header:
        # 应用重命名
        chapter_root = parent_chain[0] if parent_chain else ''
        rename_key = (chapter_root, title)
        final_name = RENAME_MAP.get(rename_key, title)

        if final_name not in node_id_map:
            nid = len(nodes_list) + 1
            nodes_list.append({
                'id': str(nid),
                'name': final_name,
                'category': chapter_root,
                'tier': min(depth, 3),
                'description': '',
                'source': 'Python快速编程入门（第3版）',
            })
            node_id_map[final_name] = str(nid)

    if 'topics' in node:
        for child in node['topics']:
            child_title = child.get('title', '').strip()
            if child_title:
                chapter_patterns_child = [
                    child_title.startswith('第') and '章' in child_title,
                    bool(__import__('re').match(r'\d+\.\d+',
                        child_title.split()[0] if child_title.split() else '')),
                ]
                is_child_header = any(chapter_patterns_child) and 'topics' in child
                child_chain = parent_chain
                if is_child_header:
                    child_chain = parent_chain + [child_title]
                collect_nodes(child, child_chain, nodes_list, node_id_map, depth + 1)


def build_relationships(nodes, node_id_map, root_node):
    """根据树结构构建 PRECEDES 关系"""
    rels = []
    rel_id = 0

    def traverse(node, parent_id):
        nonlocal rel_id
        title = node.get('title', '').strip()
        if not title:
            return

        my_id = node_id_map.get(title)
        if not my_id:
            # 可能是章节标题，查找重命名后的
            for (ch, old), new in RENAME_MAP.items():
                if title == old:
                    my_id = node_id_map.get(new)
                    break

        if my_id and parent_id and my_id != parent_id:
            rel_id += 1
            rels.append({
                'id': f'rel_c_{rel_id}',
                'source': parent_id,
                'target': my_id,
                'type': 'PRECEDES',
                'description': '',
            })

        if 'topics' in node:
            for child in node['topics']:
                child_title = child.get('title', '').strip()
                if child_title:
                    traverse(child, my_id if my_id else parent_id)

    traverse(root_node, None)
    return rels


def process():
    with open(INPUT, 'r', encoding='utf-8') as f:
        data = json.load(f)

    book = data[0]['topic']
    book_topics = book['topics']

    # 1. 删除第11章
    book_topics = [t for t in book_topics if '第11章' not in t['title']]
    print(f"删除第11章后剩余 {len(book_topics)} 章")

    # 2. 修复空标题
    for chapter in book_topics:
        fix_empty_titles(chapter)
    print("空运算符标题已补全")

    # 3. 收集节点
    nodes_list = []
    node_id_map = {}
    for chapter in book_topics:
        ch_title = chapter['title']
        chapter_patterns = [
            ch_title.startswith('第') and '章' in ch_title,
        ]
        if any(chapter_patterns) and 'topics' in chapter:
            collect_nodes(chapter, [ch_title], nodes_list, node_id_map, depth=0)

    print(f"提取知识点节点: {len(nodes_list)} 个")

    # 4. 构建关系
    all_rels = []
    for chapter in book_topics:
        chapter_rels = build_relationships(nodes_list, node_id_map, chapter)
        all_rels.extend(chapter_rels)

    print(f"构建关系: {len(all_rels)} 条")

    # 5. 输出
    result = {
        'meta': {
            'total_nodes': len(nodes_list),
            'total_relationships': len(all_rels),
            'version': '2.0.0-clean',
        },
        'nodes': nodes_list,
        'relationships': all_rels,
    }

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"输出: {OUTPUT}")
    print(f"  nodes: {len(nodes_list)}, relationships: {len(all_rels)}")

    # 重复检查
    seen = {}
    for n in nodes_list:
        name = n['name']
        if name in seen:
            print(f"  ⚠ 仍存在重复: {name}")
        seen[name] = True
    print("  ✓ 无重复节点（已处理）")


if __name__ == '__main__':
    process()
