# -*- coding: utf-8 -*-
"""
知识图谱业务服务层
"""
import time
from ..repositories.graph_repo import graph_repo

# ── 图谱分组缓存 (60 秒 TTL) ──
_graph_groups_cache = {'data': None, 'expires_at': 0}

class KnowledgeService:
    """知识点管理服务"""

    @staticmethod
    def create(name, category=None, level=None, difficulty=1,
               description=None, source=None, course_id=None):
        # 参数校验
        if not name or not name.strip():
            raise ValueError('知识点名称不能为空')
        node = graph_repo.create_node('KnowledgePoint', {
            'name': name.strip(),
            'category': category or level or '未分类',
            'knowledge_level': level or category or '未分类',
            'difficulty_level': int(difficulty),
            'description': description or '',
            'source': source or '',
            'course_id': course_id
        })
        return node

    @staticmethod
    def get_all(label=None, page=1, page_size=30):
        nodes = graph_repo.get_all_nodes(label)
        total = len(nodes)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            'items': nodes[start:end],
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': max(1, (total + page_size - 1) // page_size)
        }

    @staticmethod
    def get_by_id(node_id):
        node = graph_repo.get_node_by_id(node_id)
        if node and node.get('id'):
            return node
        return None

    @staticmethod
    def update(node_id, **kwargs):
        props = {k: v for k, v in kwargs.items() if v is not None and v != ''}
        if not props:
            raise ValueError('没有要更新的字段')
        # 统一 category 和 knowledge_level
        if 'category' in props and 'knowledge_level' not in props:
            props['knowledge_level'] = props['category']
        if 'knowledge_level' in props and 'category' not in props:
            props['category'] = props['knowledge_level']
        node = graph_repo.update_node(node_id, props)
        return node

    @staticmethod
    def delete(node_id):
        return graph_repo.delete_node(node_id)

    @staticmethod
    def search(keyword, label=None):
        return graph_repo.search_nodes(keyword, label)

    @staticmethod
    def get_graph_groups():
        """获取所有知识图谱组及其统计（带 60 秒缓存）"""
        now = time.time()
        cached = _graph_groups_cache.get('data')
        if cached and now < _graph_groups_cache.get('expires_at', 0):
            return cached

        all_nodes = graph_repo.get_all_nodes()
        groups = {}
        for n in all_nodes:
            for lb in n.get('labels', []):
                if lb not in groups:
                    groups[lb] = {'label': lb, 'node_count': 0, 'relationship_count': 0, 'categories': {}}
                groups[lb]['node_count'] += 1
                cat = n.get('properties', {}).get('category', '未分类')
                groups[lb]['categories'][cat] = groups[lb]['categories'].get(cat, 0) + 1

        # 统计每个图谱组的关系数（关系两端节点都属于该图谱组才算）
        all_rels = graph_repo.get_all_relationships()
        node_label_map = {}
        for n in all_nodes:
            for lb in n.get('labels', []):
                node_label_map.setdefault(n['id'], set()).add(lb)

        for r in all_rels:
            start_labels = node_label_map.get(r['start_node'], set())
            end_labels = node_label_map.get(r['end_node'], set())
            common = start_labels & end_labels
            for lb in common:
                if lb in groups:
                    groups[lb]['relationship_count'] += 1

        result = list(groups.values())
        _graph_groups_cache['data'] = result
        _graph_groups_cache['expires_at'] = now + 60
        return result

    @staticmethod
    def get_neighbors(node_id, direction='both', depth=1):
        return graph_repo.get_neighbors(node_id, direction=direction, depth=depth)


class RelationService:
    """关系管理服务"""

    RELATION_TYPES = ['PREDECESSOR', 'SUCCESSOR', 'BELONGS_TO', 'RELATED_TO',
                      'CONTAINS', 'DEPENDS_ON', 'EXTENDS']

    @staticmethod
    def create(source_id, target_id, rel_type, description=None):
        if not source_id or not target_id:
            raise ValueError('源节点和目标节点不能为空')
        if rel_type not in RelationService.RELATION_TYPES:
            raise ValueError(f'不支持的关系类型: {rel_type}')
        rel = graph_repo.create_relationship(source_id, target_id, rel_type,
                                             {'description': description or ''})
        if rel is None:
            raise ValueError('节点不存在，无法创建关系')
        return rel

    @staticmethod
    def get_all():
        return graph_repo.get_all_relationships()

    @staticmethod
    def get_by_type(rel_type):
        return graph_repo.get_all_relationships(rel_type)

    @staticmethod
    def delete(rel_id):
        graph_repo.delete_relationship(rel_id)
        return True

    @staticmethod
    def find_path(start_id, end_id, max_depth=5):
        return graph_repo.find_paths(start_id, end_id, max_depth)


knowledge_service = KnowledgeService()
relation_service = RelationService()
