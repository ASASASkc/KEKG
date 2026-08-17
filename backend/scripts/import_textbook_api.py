"""
通过 POST /api/import/json 将教材数据导入到运行中的 Flask
节点名使用完整路径确保唯一性
"""
import urllib.request
import json

BASE = 'http://127.0.0.1:5000'


def post(path, body):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(BASE + path, data,
                                 {'Content-Type': 'application/json'}, method='POST')
    return json.loads(urllib.request.urlopen(req).read().decode())


def build_import_data(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    root = raw[0]
    book_title = root['topic']['title']
    chapters = root['topic'].get('topics', [])

    CAT = {
        '第1章': '基础', '第2章': '基础', '第3章': '核心',
        '第4章': '数据结构', '第5章': '数据结构', '第6章': '核心',
        '第7章': '进阶', '第8章': '核心', '第9章': '进阶',
        '第10章': '数据科学', '第11章': '进阶',
    }

    def get_cat(titles):
        for t in titles:
            for p, c in CAT.items():
                if t.startswith(p):
                    return c
        return '未分类'

    def flatten(node, parent_path=(), level=0):
        title = node['title'].strip()
        path = parent_path + (title,)
        children = node.get('topics', [])
        is_leaf = not children

        if is_leaf:
            desc = title
        else:
            ct = [c['title'].strip() for c in children[:8]]
            desc = '包含: ' + ', '.join(ct)
            if len(children) > 8:
                desc += f' ... 等{len(children)}项'

        full_name = ' > '.join(path)
        display_name = title

        result = [{
            'name': full_name,
            'display_name': display_name,
            'category': get_cat(path),
            'difficulty_level': min(level + 1, 6),
            'description': desc,
            'source': book_title,
            'textbook_level': level,
            'textbook_path': full_name,
            'is_leaf': str(is_leaf),
            'children_count': str(len(children)),
        }]

        for c in children:
            result.extend(flatten(c, path, level + 1))

        return result

    nodes = []
    nodes.append({
        'name': book_title,
        'display_name': book_title,
        'category': '基础',
        'difficulty_level': 1,
        'description': f'共{len(chapters)}章，涵盖Python基础到游戏开发',
        'source': book_title,
        'textbook_level': 0,
        'textbook_path': book_title,
        'is_leaf': 'False',
        'children_count': str(len(chapters)),
    })
    for ch in chapters:
        nodes.extend(flatten(ch, (book_title,), 1))

    rels = []
    for n in nodes:
        path_parts = n['textbook_path'].split(' > ')
        if len(path_parts) <= 1:
            continue
        parent_name = ' > '.join(path_parts[:-1])
        rels.append({
            'source': parent_name,
            'target': n['name'],
            'type': 'CONTAINS',
            'description': f'{path_parts[-2]} → {path_parts[-1]}',
        })

    return nodes, rels


if __name__ == '__main__':
    import os
    json_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'Python核心知识点.json')
    if not os.path.exists(json_path):
        print(f'文件不存在: {json_path}')
        exit(1)

    print('构建导入数据...')
    nodes, rels = build_import_data(json_path)
    print(f'  节点: {len(nodes)}')
    print(f'  关系: {len(rels)}')

    BATCH = 150
    print('\n导入节点...')
    for start in range(0, len(nodes), BATCH):
        end = min(start + BATCH, len(nodes))
        batch = {'nodes': nodes[start:end], 'relationships': [],
                 'label': 'TextbookKnowledge', 'source': 'Python快速编程入门（第3版）'}
        r = post('/api/import/json', batch)
        print(f'  [{start+1}-{end}] {r["message"]}')

    print('\n导入关系...')
    for start in range(0, len(rels), BATCH):
        end = min(start + BATCH, len(rels))
        batch = {'nodes': [], 'relationships': rels[start:end],
                 'label': 'TextbookKnowledge', 'source': 'Python快速编程入门（第3版）'}
        r = post('/api/import/json', batch)
        rel_created = r['data'].get('relationships_created', 0)
        rel_skipped = r['data'].get('relationships_skipped', 0)
        print(f'  [{start+1}-{end}] 创建: {rel_created}, 跳过: {rel_skipped}')

    print('\n验证...')
    r = json.loads(urllib.request.urlopen(BASE + '/api/health').read().decode())
    print(f'  总节点: {r["data"]["nodes"]}')
    print(f'  总关系: {r["data"]["relationships"]}')
    print('\n导入完成!')
