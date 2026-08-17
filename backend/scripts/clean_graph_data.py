# -*- coding: utf-8 -*-
"""
数据清洗脚本
功能：
1. 删除 name 为空或仅空格的节点
2. 修复悬挂关系（source/target 不存在于有效节点中）
3. 合并同名同分类重复节点（保留更丰富的 attributes）
4. 输出清洗报告到 backend/data/clean_report.json
"""
import json
import os
import glob
from datetime import datetime

# 项目根目录（backend/）
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BACKEND_DIR, 'data')
REPORT_PATH = os.path.join(DATA_DIR, 'clean_report.json')


def clean_graph_data(json_path: str) -> dict:
    """
    清洗单个 JSON 图谱文件。
    返回清洗后的数据 dict，格式：{"meta": {...}, "nodes": [...], "relationships": [...]}
    """
    filename = os.path.basename(json_path)

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    nodes = data.get('nodes', [])
    rels = data.get('relationships', [])

    before_nodes = len(nodes)
    before_rels = len(rels)

    deleted_empty_nodes = []
    fixed_dangling_rels = []
    merged_duplicates = []

    # ── Step 1: 删除空 name 节点 ──
    valid_nodes = []
    name_to_indices = {}  # name -> list of indices in valid_nodes (for dedup tracking)

    for node in nodes:
        name = (node.get('name') or '').strip()
        if not name:
            deleted_empty_nodes.append({
                'id': node.get('id', ''),
                'name': node.get('name', ''),
                'category': node.get('category', ''),
            })
            continue
        valid_nodes.append(dict(node))
        idx = len(valid_nodes) - 1
        name_to_indices.setdefault(name, []).append(idx)

    # ── Step 2: 合并同名同分类重复 ──
    # 按 (name, category) 分组
    group_map = {}  # (name, category) -> list of (index, node)
    for i, node in enumerate(valid_nodes):
        key = (node.get('name', '').strip(), (node.get('category') or '').strip())
        group_map.setdefault(key, []).append((i, node))

    # 标记需要删除的索引
    remove_indices = set()
    id_remap = {}  # old_id -> merged_keep_id

    for key, group in group_map.items():
        if len(group) <= 1:
            continue
        # 按 attributes 丰富度排序：description 长度 > source 非空 > 整体字段数
        def richness(idx_node):
            _, n = idx_node
            desc_len = len((n.get('description') or '').strip())
            has_source = 1 if (n.get('source') or '').strip() else 0
            field_count = len([v for v in n.values() if v])
            return (desc_len, has_source, field_count, -len(json.dumps(n, ensure_ascii=False)))

        group.sort(key=richness, reverse=True)

        # 保留第一个（最丰富的）
        keep_idx, keep_node = group[0]
        removed = []

        for idx, node in group[1:]:
            removed.append({
                'id': node.get('id', ''),
                'name': node.get('name', ''),
                'category': node.get('category', ''),
            })
            remove_indices.add(idx)
            # 建立 ID 重映射：被删除节点的 ID -> 保留节点的 ID
            id_remap[node.get('id', '')] = keep_node.get('id', '')

        # 合并 attributes：将其他节点的独有属性合并到保留节点
        for idx, node in group[1:]:
            for k, v in node.items():
                if k in ('id', 'name', 'category'):
                    continue
                if v and not keep_node.get(k):
                    keep_node[k] = v

        merged_duplicates.append({
            'kept': {'id': keep_node.get('id', ''), 'name': keep_node.get('name', ''), 'category': keep_node.get('category', '')},
            'removed': removed,
        })

    # 重建节点列表（移除标记的）
    final_nodes = [node for i, node in enumerate(valid_nodes) if i not in remove_indices]

    # 构建有效 ID 集合
    valid_ids = {str(node.get('id', '')) for node in final_nodes}

    # ── Step 3: 修复悬挂关系 ──
    final_rels = []
    for rel in rels:
        source = str(rel.get('source', '') or rel.get('from', '') or '')
        target = str(rel.get('target', '') or rel.get('to', '') or '')

        # 如果 source/target 在被删除的重复节点中，重映射到保留节点
        if source in id_remap:
            source = id_remap[source]
        if target in id_remap:
            target = id_remap[target]

        if source not in valid_ids or target not in valid_ids:
            fixed_dangling_rels.append({
                'id': rel.get('id', ''),
                'source': source,
                'target': target,
                'type': rel.get('type', ''),
                'reason': f'source missing' if source not in valid_ids else 'target missing',
            })
            continue

        # 更新关系中的 source/target
        clean_rel = dict(rel)
        clean_rel['source'] = source
        clean_rel['target'] = target
        final_rels.append(clean_rel)

    after_nodes = len(final_nodes)
    after_rels = len(final_rels)

    # ── 构建清洗后数据 ──
    cleaned = {
        'meta': dict(data.get('meta', {})),
        'nodes': final_nodes,
        'relationships': final_rels,
    }
    cleaned['meta']['total_nodes'] = after_nodes
    cleaned['meta']['total_relationships'] = after_rels
    cleaned['meta']['cleaned_at'] = datetime.now().isoformat()

    # ── 生成报告 ──
    report_entry = {
        'file': filename,
        'deleted_empty_nodes': deleted_empty_nodes,
        'fixed_dangling_rels': fixed_dangling_rels,
        'merged_duplicates': merged_duplicates,
        'before_nodes': before_nodes,
        'after_nodes': after_nodes,
        'before_rels': before_rels,
        'after_rels': after_rels,
    }

    print(f"[{filename}]  nodes: {before_nodes} -> {after_nodes} (-{before_nodes - after_nodes}), "
          f"rels: {before_rels} -> {after_rels} (-{before_rels - after_rels})")
    if deleted_empty_nodes:
        print(f"  删除空节点: {len(deleted_empty_nodes)}")
    if merged_duplicates:
        total_removed = sum(len(m['removed']) for m in merged_duplicates)
        print(f"  合并重复: {len(merged_duplicates)} 组, 移除 {total_removed} 个")
    if fixed_dangling_rels:
        print(f"  悬挂关系: {len(fixed_dangling_rels)}")

    return cleaned, report_entry


def clean_all() -> list:
    """
    扫描 backend/data/graph_*.json，对所有文件逐一清洗，汇总报告。
    返回每个文件的清洗报告条目列表。
    """
    pattern = os.path.join(DATA_DIR, 'graph_*.json')
    files = sorted(glob.glob(pattern))

    if not files:
        print("未找到 graph_*.json 文件")
        return []

    all_reports = []
    summary = {
        'generated_at': datetime.now().isoformat(),
        'total_files': len(files),
        'total_deleted_empty_nodes': 0,
        'total_fixed_dangling_rels': 0,
        'total_merged_groups': 0,
        'total_nodes_before': 0,
        'total_nodes_after': 0,
        'total_rels_before': 0,
        'total_rels_after': 0,
        'files': [],
    }

    for filepath in files:
        try:
            cleaned_data, report_entry = clean_graph_data(filepath)
            all_reports.append(report_entry)

            # 累加统计
            summary['total_deleted_empty_nodes'] += len(report_entry['deleted_empty_nodes'])
            summary['total_fixed_dangling_rels'] += len(report_entry['fixed_dangling_rels'])
            summary['total_merged_groups'] += len(report_entry['merged_duplicates'])
            summary['total_nodes_before'] += report_entry['before_nodes']
            summary['total_nodes_after'] += report_entry['after_nodes']
            summary['total_rels_before'] += report_entry['before_rels']
            summary['total_rels_after'] += report_entry['after_rels']
            summary['files'].append({
                'file': os.path.basename(filepath),
                'status': 'ok',
                'before_nodes': report_entry['before_nodes'],
                'after_nodes': report_entry['after_nodes'],
            })

            # 回写清洗后的数据覆盖原文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"[{os.path.basename(filepath)}] 清洗失败: {e}")
            summary['files'].append({
                'file': os.path.basename(filepath),
                'status': 'error',
                'error': str(e),
            })

    # 写入汇总报告
    report = {
        'summary': summary,
        'details': all_reports,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n清洗报告已输出: {REPORT_PATH}")
    print(f"  总文件数: {summary['total_files']}")
    print(f"  删除空节点: {summary['total_deleted_empty_nodes']}")
    print(f"  修复悬挂关系: {summary['total_fixed_dangling_rels']}")
    print(f"  合并重复组: {summary['total_merged_groups']}")
    print(f"  节点: {summary['total_nodes_before']} -> {summary['total_nodes_after']}")
    print(f"  关系: {summary['total_rels_before']} -> {summary['total_rels_after']}")

    return all_reports


if __name__ == '__main__':
    clean_all()
