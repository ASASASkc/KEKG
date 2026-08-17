# -*- coding: utf-8 -*-
"""
种子数据 — 从赛道 JSON 文件导入知识点图谱
支持：graph_common.json（公共基础）+ 各赛道 JSON（数据分析、ML、DL 等）
"""
import os
from app.repositories.graph_repo import graph_repo
from app.repositories.sql_repo import sql_repo
from app.services.track_service import track_service

DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def init_all():
    """从 data 目录下所有 graph_*.json 文件导入数据"""
    results = track_service.import_all_tracks(DATA_DIR)

    errors = {k: v.get('error') for k, v in results.items() if 'error' in v}
    if errors:
        raise RuntimeError(f'导入以下文件失败: {errors}')

    total_nodes = sum(r.get('nodes_created', 0) for r in results.values())
    total_rels = sum(r.get('relationships_created', 0) for r in results.values())

    return {
        'imported_files': list(results.keys()),
        'total_nodes_created': total_nodes,
        'total_relationships_created': total_rels,
        'total_nodes': len(graph_repo.get_all_nodes()),
        'total_relationships': len(graph_repo.get_all_relationships()),
    }


def init_track(filepath: str):
    """导入单个赛道 JSON 文件（通过 API 调用）"""
    return track_service.import_track_json(filepath)


if __name__ == '__main__':
    print("初始化种子数据...")
    result = init_all()
    print(f"完成: {result}")
