"""
Neo4j 图存储实现 — 替代内存 InMemoryGraphRepository
使用 bolt 协议连接 Neo4j 5.x，接口与 InMemoryGraphRepository 兼容
支持事务：begin_transaction / commit_transaction / rollback_transaction
"""
from contextlib import contextmanager
import re
import threading
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired
from ..config import Config


class Neo4jGraphRepository:
    """Neo4j 图仓库 — 接口兼容 InMemoryGraphRepository"""

    def __init__(self):
        self._driver = None
        # 事务必须按线程隔离：并发请求共享同一写事务会交叉提交/错乱
        self._local = threading.local()

    @property
    def _tx(self):
        return getattr(self._local, 'tx', None)

    @_tx.setter
    def _tx(self, value):
        self._local.tx = value

    # ── 连接管理 ────────────────────────────────

    def _reconnect(self):
        """强制重建 driver（连接断开时调用）"""
        if self._driver:
            try:
                self._driver.close()
            except Exception:
                pass
        self._driver = None
        self._tx = None

    def _get_driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                Config.NEO4J_URI,
                auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD),
                max_connection_lifetime=3600,
                connection_acquisition_timeout=10,
                connection_timeout=10,
            )
            self._driver.verify_connectivity()
        return self._driver

    @contextmanager
    def _session(self):
        """获取 session：事务模式下返回 tx，否则创建新 session。"""
        if self._tx is not None:
            yield self._tx
            return

        session = self._get_driver().session()
        try:
            yield session
        finally:
            session.close()

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    def test_connection(self):
        """测试 Neo4j 连接可用性（轻量）"""
        try:
            sess = self._get_driver().session()
            sess.run("RETURN 1")
            sess.close()
            return True
        except Exception:
            return False

    # ── 事务管理 ────────────────────────────────

    def begin_transaction(self):
        """开启 Neo4j 事务（连接失败时自动重连一次）"""
        if self._tx is not None:
            return
        for attempt in range(2):
            try:
                session = self._get_driver().session()
                self._tx = session.begin_transaction()
                break
            except (ServiceUnavailable, SessionExpired, ConnectionError, OSError):
                self._reconnect()
                if attempt >= 1:
                    raise

    def commit_transaction(self):
        """提交 Neo4j 事务"""
        if self._tx is not None:
            try:
                self._tx.commit()
            finally:
                self._tx.close()
                self._tx = None

    def rollback_transaction(self):
        """回滚 Neo4j 事务"""
        if self._tx is not None:
            try:
                self._tx.rollback()
            finally:
                self._tx.close()
                self._tx = None

    # ── 节点操作 ────────────────────────────────

    def create_node(self, label, properties):
        labels = [label] if isinstance(label, str) else label
        labels = [self._validate_label(l) for l in labels]
        label_expr = ':'.join(labels)
        with self._session() as session:
            result = session.run(
                f'CREATE (n:{label_expr}) SET n += $props RETURN n, elementId(n) as nid',
                props=dict(properties)
            )
            record = result.single()
            node = record['n']
            return {
                'id': record['nid'],
                'labels': labels,
                'properties': dict(node.items())
            }

    _LABEL_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    _KEY_PATTERN = re.compile(r'^[a-zA-Z_][\w\u4e00-\u9fa5]*$')

    @classmethod
    def _validate_label(cls, label):
        """校验 Neo4j label 仅含安全字符，防止 Cypher 注入"""
        if not isinstance(label, str) or not cls._LABEL_PATTERN.match(label):
            raise ValueError(f'无效的图谱标签: {label}')
        return label

    @classmethod
    def _validate_type(cls, rel_type):
        """校验关系类型仅含安全字符，防止 Cypher 注入"""
        if not isinstance(rel_type, str) or not cls._LABEL_PATTERN.match(rel_type):
            raise ValueError(f'无效的关系类型: {rel_type}')
        return rel_type

    @classmethod
    def _validate_key(cls, key):
        """校验属性名仅含安全字符，防止 Cypher 注入"""
        if not isinstance(key, str) or not cls._KEY_PATTERN.match(key):
            raise ValueError(f'无效的属性名: {key}')
        return key

    def get_all_nodes(self, label=None):
        with self._session() as session:
            if label:
                label = self._validate_label(label)
                result = session.run(
                    f'MATCH (n:`{label}`) RETURN n, elementId(n) as nid'
                )
            else:
                result = session.run(
                    'MATCH (n) RETURN n, elementId(n) as nid'
                )
            nodes = []
            for record in result:
                n = record['n']
                nodes.append({
                    'id': record['nid'],
                    'labels': list(n.labels),
                    'properties': dict(n.items())
                })
            return nodes

    def get_node_by_id(self, node_id):
        with self._session() as session:
            result = session.run(
                'MATCH (n) WHERE elementId(n) = $nid RETURN n, elementId(n) as nid',
                nid=str(node_id)
            )
            record = result.single()
            if record:
                n = record['n']
                return {
                    'id': record['nid'],
                    'labels': list(n.labels),
                    'properties': dict(n.items())
                }
            return None

    def update_node(self, node_id, properties):
        with self._session() as session:
            result = session.run(
                'MATCH (n) WHERE elementId(n) = $nid SET n += $props RETURN n, elementId(n) as nid',
                nid=str(node_id), props=dict(properties)
            )
            record = result.single()
            if record:
                n = record['n']
                return {
                    'id': record['nid'],
                    'labels': list(n.labels),
                    'properties': dict(n.items())
                }
            return None

    def delete_node(self, node_id):
        with self._session() as session:
            result = session.run(
                'MATCH (n) WHERE elementId(n) = $nid '
                'OPTIONAL MATCH (n)-[r]-() '
                'DELETE r, n '
                'RETURN count(n) as cnt',
                nid=str(node_id)
            )
            record = result.single()
            return record and record['cnt'] > 0

    def get_nodes_by_ids(self, node_ids):
        if not node_ids:
            return {}
        with self._session() as session:
            result = session.run(
                'UNWIND $ids as nid '
                'MATCH (n) WHERE elementId(n) = nid '
                'RETURN elementId(n) as nid, n',
                ids=[str(nid) for nid in node_ids]
            )
            node_map = {}
            for record in result:
                n = record['n']
                node_map[record['nid']] = dict(n.items())
            return node_map

    def get_node_by_property(self, label, key, value):
        with self._session() as session:
            query = f'MATCH (n:`{label}`) WHERE n.`{key}` = $val RETURN n, elementId(n) as nid LIMIT 1'
            result = session.run(query, val=value)
            record = result.single()
            if record:
                n = record['n']
                return {
                    'id': record['nid'],
                    'labels': list(n.labels),
                    'properties': dict(n.items())
                }
            return None

    # ── 关系操作 ────────────────────────────────

    def create_relationship(self, start_id, end_id, rel_type, properties=None):
        with self._session() as session:
            result = session.run(
                'MATCH (a), (b) '
                'WHERE elementId(a) = $sid AND elementId(b) = $eid '
                'MERGE (a)-[r:`' + rel_type + '`]->(b) '
                'SET r += $props '
                'RETURN r, elementId(a) as sid, elementId(b) as eid',
                sid=str(start_id), eid=str(end_id), props=dict(properties or {})
            )
            record = result.single()
            if record:
                return {
                    'id': record['r'].element_id,
                    'type': rel_type,
                    'start_node': record['sid'],
                    'end_node': record['eid'],
                    'properties': dict(record['r'].items())
                }
            return None

    def get_all_relationships(self, rel_type=None):
        with self._session() as session:
            if rel_type:
                rel_type = self._validate_type(rel_type)
                result = session.run(
                    f'MATCH ()-[r:`{rel_type}`]->() '
                    'RETURN r, elementId(startNode(r)) as sid, elementId(endNode(r)) as eid'
                )
            else:
                result = session.run(
                    'MATCH ()-[r]->() '
                    'RETURN r, elementId(startNode(r)) as sid, elementId(endNode(r)) as eid'
                )
            rels = []
            for record in result:
                r = record['r']
                rels.append({
                    'id': r.element_id,
                    'type': r.type,
                    'start_node': record['sid'],
                    'end_node': record['eid'],
                    'properties': dict(r.items())
                })
            return rels

    def get_relationship_by_id(self, rel_id):
        with self._session() as session:
            result = session.run(
                'MATCH ()-[r]->() WHERE elementId(r) = $rid '
                'RETURN r, elementId(startNode(r)) as sid, elementId(endNode(r)) as eid',
                rid=str(rel_id)
            )
            record = result.single()
            if record:
                r = record['r']
                return {
                    'id': r.element_id,
                    'type': r.type,
                    'start_node': record['sid'],
                    'end_node': record['eid'],
                    'properties': dict(r.items())
                }
            return {}

    def delete_relationship(self, rel_id):
        with self._session() as session:
            result = session.run(
                'MATCH ()-[r]->() WHERE elementId(r) = $rid '
                'DELETE r RETURN count(r) as cnt',
                rid=str(rel_id)
            )
            record = result.single()
            return record and record['cnt'] > 0

    # ── 图查询操作 ──────────────────────────────

    def get_neighbors(self, node_id, rel_type=None, direction='both', depth=1):
        nid = str(node_id)

        if direction == 'outgoing':
            dir_pattern = '-[r]->'
        elif direction == 'incoming':
            dir_pattern = '<-[r]-'
        else:
            dir_pattern = '-[r]-'

        with self._session() as session:
            check = session.run(
                'MATCH (n) WHERE elementId(n) = $nid RETURN n LIMIT 1', nid=nid
            )
            if not check.single():
                return {'nodes': [], 'relationships': []}

            rel_filter = ''
            rel_param = {}
            if rel_type:
                # 参数化绑定，防止 rel_type 被拼接进 Cypher 造成注入
                rel_filter = ' AND type(r) = $rel_type'
                rel_param = {'rel_type': rel_type}

            query = (
                'MATCH (center)'
                f'{dir_pattern}(neighbor) '
                'WHERE elementId(center) = $nid'
                f'{rel_filter} '
                'RETURN DISTINCT neighbor, elementId(neighbor) as nid, '
                'r, elementId(r) as rid, '
                'elementId(startNode(r)) as sid, elementId(endNode(r)) as eid'
            )

            result = session.run(query, nid=nid, **rel_param)
            nodes_map = {}
            rels_map = {}
            for record in result:
                nei = record['neighbor']
                nei_id = record['nid']
                if nei_id not in nodes_map:
                    nodes_map[nei_id] = {
                        'id': nei_id,
                        'labels': list(nei.labels),
                        'properties': dict(nei.items())
                    }
                r = record['r']
                rid = record['rid']
                if rid not in rels_map:
                    rels_map[rid] = {
                        'id': rid,
                        'type': r.type,
                        'start_node': record['sid'],
                        'end_node': record['eid'],
                        'properties': dict(r.items())
                    }

        return {
            'nodes': list(nodes_map.values()),
            'relationships': list(rels_map.values())
        }

    def find_paths(self, start_id, end_id, max_depth=5):
        # Neo4j shortestPath 在起终点为同一节点时抛异常，直接短路返回空
        if str(start_id) == str(end_id):
            return []
        with self._session() as session:
            result = session.run(
                'MATCH (start), (end) '
                'WHERE elementId(start) = $sid AND elementId(end) = $eid '
                'MATCH path = shortestPath((start)-[*..' + str(max_depth) + ']-(end)) '
                'RETURN nodes(path) as path_nodes, relationships(path) as path_rels',
                sid=str(start_id), eid=str(end_id)
            )
            paths = []
            for record in result:
                pnodes = []
                prels = []
                for n in record['path_nodes']:
                    pnodes.append({
                        'id': n.element_id,
                        'labels': list(n.labels),
                        'properties': dict(n.items())
                    })
                for r in record['path_rels']:
                    prels.append({
                        'id': r.element_id,
                        'type': r.type,
                        'start_node': r.start_node.element_id,
                        'end_node': r.end_node.element_id,
                        'properties': dict(r.items())
                    })
                paths.append({'nodes': pnodes, 'relationships': prels})
            return paths

    def get_subgraph(self, center_id, depth=1):
        nid = str(center_id)
        with self._session() as session:
            result = session.run(
                'MATCH (center) WHERE elementId(center) = $nid '
                'OPTIONAL MATCH (center)-[*..' + str(depth) + ']-(neighbor) '
                'RETURN DISTINCT center, elementId(center) as cid, '
                'neighbor, elementId(neighbor) as nid',
                nid=nid
            )
            nodes_map = {}
            for record in result:
                center = record.get('center')
                if center:
                    nodes_map[record['cid']] = {
                        'id': record['cid'],
                        'labels': list(center.labels),
                        'properties': dict(center.items())
                    }
                neighbor = record.get('neighbor')
                if neighbor:
                    nei_id = record['nid']
                    if nei_id not in nodes_map:
                        nodes_map[nei_id] = {
                            'id': nei_id,
                            'labels': list(neighbor.labels),
                            'properties': dict(neighbor.items())
                        }

            if len(nodes_map) > 1:
                rels_result = session.run(
                    'MATCH (a)-[r]-(b) '
                    'WHERE elementId(a) IN $node_ids AND elementId(b) IN $node_ids '
                    'RETURN DISTINCT r, elementId(startNode(r)) as sid, elementId(endNode(r)) as eid',
                    node_ids=list(nodes_map.keys())
                )
                rels = []
                seen = set()
                for record in rels_result:
                    rid = record['r'].element_id
                    if rid not in seen:
                        seen.add(rid)
                        rels.append({
                            'id': rid,
                            'type': record['r'].type,
                            'start_node': record['sid'],
                            'end_node': record['eid'],
                            'properties': dict(record['r'].items())
                        })
            else:
                rels = []

        return {'nodes': list(nodes_map.values()), 'relationships': rels}

    def get_entry_points(self):
        with self._session() as session:
            result = session.run(
                """MATCH (n:KnowledgePoint)
                   RETURN n.name as name, n
                   ORDER BY n.name ASC
                   LIMIT 30"""
            )
            nodes = []
            for record in result:
                node = record['n']
                props = dict(node.items()) if node else {}
                nodes.append({
                    'id': record['name'] or props.get('name', ''),
                    'name': props.get('name', ''),
                    'category': props.get('category', ''),
                })
            return nodes

    def get_statistics(self):
        with self._session() as session:
            node_count = session.run('MATCH (n) RETURN count(n) as cnt').single()['cnt']
            rel_count = session.run('MATCH ()-[r]->() RETURN count(r) as cnt').single()['cnt']

            label_result = session.run(
                'MATCH (n) UNWIND labels(n) AS label '
                'RETURN label, count(*) AS cnt'
            )
            labels_dist = {r['label']: r['cnt'] for r in label_result}

            type_result = session.run(
                'MATCH ()-[r]->() '
                'RETURN type(r) AS relationshipType, count(r) AS cnt'
            )
            rel_types = {r['relationshipType']: r['cnt'] for r in type_result}

            return {
                'node_count': node_count,
                'relationship_count': rel_count,
                'labels_distribution': labels_dist,
                'relationship_types': rel_types
            }

    def clear_all(self):
        with self._session() as session:
            session.run('MATCH (n) DETACH DELETE n')

    def search_nodes(self, keyword, label=None):
        kw = keyword.lower()
        with self._session() as session:
            if label:
                query = (
                    'MATCH (n:KnowledgePoint) '
                    'WHERE coalesce(n.tracks, "") CONTAINS $label_quoted '
                    '  AND (toLower(coalesce(n.name, "")) CONTAINS $kw '
                    '    OR toLower(coalesce(n.description, "")) CONTAINS $kw) '
                    'WITH n, elementId(n) as nid, '
                    '  CASE WHEN toLower(coalesce(n.name, "")) = $kw THEN 0 '
                    '       WHEN toLower(coalesce(n.name, "")) STARTS WITH $kw THEN 1 '
                    '       ELSE 2 END as score '
                    'RETURN n, nid '
                    'ORDER BY score, toLower(coalesce(n.name, "")) '
                    'LIMIT 20'
                )
            else:
                query = (
                    'MATCH (n:KnowledgePoint) '
                    'WHERE toLower(coalesce(n.name, "")) CONTAINS $kw '
                    '   OR toLower(coalesce(n.description, "")) CONTAINS $kw '
                    'WITH n, elementId(n) as nid, '
                    '  CASE WHEN toLower(coalesce(n.name, "")) = $kw THEN 0 '
                    '       WHEN toLower(coalesce(n.name, "")) STARTS WITH $kw THEN 1 '
                    '       ELSE 2 END as score '
                    'RETURN n, nid '
                    'ORDER BY score, toLower(coalesce(n.name, "")) '
                    'LIMIT 20'
                )
            result = session.run(query, kw=kw, label_quoted=f'"{label}"')
            nodes = []
            for record in result:
                n = record['n']
                nodes.append({
                    'id': record['nid'],
                    'labels': list(n.labels),
                    'properties': dict(n.items())
                })
            return nodes


# 全局单例
graph_repo = Neo4jGraphRepository()
