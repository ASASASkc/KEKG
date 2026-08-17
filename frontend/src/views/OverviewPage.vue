<template>
  <div class="page-container">
    <h1 class="page-title">图谱概览</h1>
    <p class="page-subtitle">五级树形结构展示知识图谱的全貌</p>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="error-banner card">
      <span class="error-icon">&#9888;</span>
      <span>{{ errorMsg }}</span>
      <button class="btn btn-sm btn-primary" @click="loadTree" style="margin-left: auto;">重试</button>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>加载知识树中...</p>
    </div>

    <!-- 主体内容 -->
    <template v-else-if="treeData">
      <!-- 工具栏 -->
      <div class="toolbar">
        <button class="btn btn-sm btn-secondary" @click="toggleExpandAll">
          {{ expandAll ? '折叠全部' : '展开全部' }}
        </button>
        <span class="toolbar-info" v-if="treeSummary">共 {{ treeSummary.total }} 个节点</span>
      </div>

      <div class="overview-layout">
        <!-- 左侧树形区 -->
        <div class="tree-panel card">
          <!-- L1 根节点 -->
          <div class="tree-root">
            <div class="tree-row root-row" @click="onSelectNode(treeData)">
              <span class="tree-toggle open">v</span>
              <span class="tree-dot" style="background: #3b82f6;"></span>
              <span class="tree-name root-name">{{ treeData.name }}</span>
              <span class="tree-count">({{ countAllChildren(treeData) }})</span>
            </div>
            <!-- L2 子节点递归 -->
            <div class="tree-children root-children">
              <TreeNode
                v-for="child in treeData.children"
                :key="child.name"
                :node="child"
                :depth="0"
                :expandAll="expandAll"
                @select="onSelectNode"
              />
            </div>
          </div>
        </div>

        <!-- 右侧详情区 -->
        <div class="detail-panel" v-if="selectedNode">
          <!-- 叶子节点：显示 KnowledgeCard -->
          <div v-if="isLeaf(selectedNode)">
            <div v-if="leafLoading" class="card" style="padding:20px;text-align:center;color:#64748b">加载知识点详情...</div>
            <KnowledgeCard
              v-else
              :node="wrapLeafNode(selectedNode)"
              :treeMode="false"
              class="card"
            />
            <button class="btn btn-primary view-graph-btn"
              @click="goToGraph(selectedNode.name)"
              style="margin-top:12px;width:100%">
              在图谱中查看
            </button>
          </div>
          <!-- 非叶子节点：显示统计面板 -->
          <div v-else class="card stats-card">
            <div class="stats-header">
              <h3>{{ selectedNode.name }}</h3>
              <span class="level-badge">{{ getLevelName(selectedNode) }}</span>
            </div>
            <div class="stats-grid">
              <div class="stat-box">
                <span class="stat-num">{{ statsData.totalDescendants }}</span>
                <span class="stat-label">子节点总数</span>
              </div>
              <div class="stat-box">
                <span class="stat-num">{{ statsData.directChildren }}</span>
                <span class="stat-label">直接子节点</span>
              </div>
              <div class="stat-box" v-if="statsData.maxDepth > 0">
                <span class="stat-num">{{ statsData.maxDepth }}</span>
                <span class="stat-label">最大深度</span>
              </div>
            </div>
            <!-- 各层级统计 -->
            <div class="level-stats" v-if="Object.keys(statsData.levelCounts).length">
              <h4>各层级分布</h4>
              <div class="level-row" v-for="(count, level) in statsData.levelCounts" :key="level">
                <span class="level-label">{{ level }}</span>
                <span class="level-bar-wrap">
                  <span class="level-bar" :style="{ width: barWidth(count, statsData.totalDescendants) }"></span>
                </span>
                <span class="level-count">{{ count }}</span>
              </div>
            </div>
            <button class="btn btn-primary view-graph-btn"
              @click="goToGraph(selectedNode.name)">
              在图谱中查看
            </button>
          </div>
        </div>

        <!-- 无选中 -->
        <div v-else class="card detail-panel empty-panel">
          <p>点击左侧节点查看详情</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h, defineComponent, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import KnowledgeCard from '../components/KnowledgeCard.vue'

const router = useRouter()

// ── 状态 ──
const treeData = ref(null)
const loading = ref(false)
const errorMsg = ref('')
const selectedNode = ref(null)
const expandAll = ref(false)

// ── 数据加载 ──
onMounted(() => {
  loadTree()
})

async function loadTree() {
  loading.value = true
  errorMsg.value = ''
  selectedNode.value = null
  try {
    const r = await api.get('/graph/full-tree')
    if (r.success && r.data) {
      treeData.value = r.data
    } else {
      errorMsg.value = r.message || '加载知识树失败'
    }
  } catch (e) {
    errorMsg.value = e.message || '网络错误，请检查连接后重试'
    console.error('加载知识树失败:', e)
  } finally {
    loading.value = false
  }
}

// ── 展开/折叠全部 ──
function toggleExpandAll() {
  expandAll.value = !expandAll.value
}

// ── 树概要统计 ──
const treeSummary = computed(() => {
  if (!treeData.value) return null
  return { total: countAllChildren(treeData.value) + 1 }
})

// ── 选中的统计 ──
const statsData = computed(() => {
  const node = selectedNode.value
  if (!node || isLeaf(node)) return { totalDescendants: 0, directChildren: 0, maxDepth: 0, levelCounts: {} }
  return computeStats(node, 0)
})

// ── 叶子节点详情（API 加载）──
const leafDetail = ref(null)
const leafLoading = ref(false)

// ── 叶子判定 ──
function isLeaf(node) {
  return !node.children || node.children.length === 0
}

// ── 叶子节点包装（KnowledgeCard 需要特定结构） ──
function wrapLeafNode(node) {
  const detail = leafDetail.value
  if (detail) {
    return {
      id: detail.elementId || node.name,
      name: node.name,
      properties: {
        name: node.name,
        description: detail.description || '',
        category: detail.category || '',
        difficulty: detail.difficulty || 1,
        source: detail.source || '',
      }
    }
  }
  return {
    id: node.name,
    name: node.name,
    properties: {
      name: node.name
    }
  }
}

// ── 层级名称 ──
function getLevelName(node) {
  if (!treeData.value) return ''
  const depth = findNodeDepth(treeData.value, node.name)
  return depth >= 0 ? getLevelNameByDepth(depth + 1) : ''
}

// ── 在树中搜索节点深度 ──
function findNodeDepth(root, targetName, currentDepth = 0) {
  if (root.name === targetName) return currentDepth
  if (!root.children) return -1
  for (const child of root.children) {
    const result = findNodeDepth(child, targetName, currentDepth + 1)
    if (result >= 0) return result
  }
  return -1
}

// ── 递归统计 ──
function computeStats(node, depth) {
  const children = node.children || []
  let totalDescendants = children.length
  let maxDepth = 0
  const levelCounts = {}

  for (const child of children) {
    const sub = computeStats(child, depth + 1)
    totalDescendants += sub.totalDescendants
    if (sub.maxDepth + 1 > maxDepth) maxDepth = sub.maxDepth + 1

    // 统计子节点层级
    const childLevel = depth + 2 // L2=2, L3=3, ...
    const levelName = getLevelNameByDepth(childLevel)
    levelCounts[levelName] = (levelCounts[levelName] || 0) + 1

    // 合并更深层级
    for (const [lvl, cnt] of Object.entries(sub.levelCounts)) {
      levelCounts[lvl] = (levelCounts[lvl] || 0) + cnt
    }
  }

  return { totalDescendants, directChildren: children.length, maxDepth, levelCounts }
}

function getLevelNameByDepth(d) {
  const names = { 2: '拓展', 3: '章', 4: '节', 5: '知识点' }
  return names[d] || `L${d}`
}

// ── 递归计数 ──
function countAllChildren(node) {
  let count = 0
  if (node.children) {
    for (const c of node.children) {
      count += 1 + countAllChildren(c)
    }
  }
  return count
}

// ── 进度条宽度 ──
function barWidth(count, total) {
  if (!total) return '0%'
  return Math.max(2, (count / total) * 100) + '%'
}

// ── 节点点击 ──
async function onSelectNode(node) {
  selectedNode.value = node
  if (isLeaf(node)) {
    const nid = node._id || node.name
    leafLoading.value = true
    leafDetail.value = null
    try {
      const r = await api.get(`/knowledge-points/${encodeURIComponent(nid)}`)
      if (r.success) leafDetail.value = r.data
    } catch (e) { console.error('加载知识点详情失败:', e) }
    finally { leafLoading.value = false }
  } else {
    leafDetail.value = null
  }
}

// ── 跳转图谱 ──
function goToGraph(nodeName) {
  router.push('/graph/' + encodeURIComponent(nodeName))
}

// ── 递归树节点组件 ──
const TreeNode = defineComponent({
  name: 'TreeNode',
  props: {
    node: Object,
    depth: Number,
    expandAll: Boolean
  },
  emits: ['select'],
  setup(props, { emit }) {
    // 默认展开：depth < 1 即 L2（拓展）默认展开，L3+ 默认折叠
    const expanded = ref(props.depth < 1)
    const hasChildren = computed(() => props.node.children?.length > 0)

    // 监听 expandAll 信号做全部展开/折叠
    watch(() => props.expandAll, (val) => {
      if (hasChildren.value) {
        expanded.value = val
      }
    })

    function onClick() {
      if (hasChildren.value) {
        expanded.value = !expanded.value
      }
      emit('select', props.node)
    }

    return () => {
      const n = props.node
      const leaf = !hasChildren.value
      const levelColor = getLevelColor(props.depth)

      return h('div', { class: 'tree-node' }, [
        h('div', {
          class: ['tree-row', { 'row-leaf': leaf }],
          style: { paddingLeft: `${props.depth * 20 + 8}px` },
          onClick
        }, [
          hasChildren.value
            ? h('span', { class: ['tree-toggle', { open: expanded.value }] }, expanded.value ? 'v' : '>')
            : h('span', { class: 'tree-leaf-icon' }),
          h('span', { class: 'tree-dot', style: { background: levelColor } }),
          h('span', { class: 'tree-name', title: n.name }, n.name),
          h('span', { class: 'tree-count' }, hasChildren.value ? `(${countAllChildren(n)})` : '')
        ]),
        expanded.value && n.children
          ? h('div', { class: 'tree-children' },
              n.children.map(c => h(TreeNode, {
                node: c,
                depth: props.depth + 1,
                expandAll: props.expandAll,
                onSelect: (node) => emit('select', node)
              }))
            )
          : null
      ])
    }
  }
})

// ── 层级颜色 ──
function getLevelColor(depth) {
  const colors = {
    0: '#3b82f6',  // L2 拓展 - 蓝
    1: '#8b5cf6',  // L3 章 - 紫
    2: '#10b981',  // L4 节 - 绿
    3: '#f59e0b',  // L5 知识点 - 橙
  }
  return colors[depth] || '#94a3b8'
}
</script>

<style scoped>
.page-container { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }
.page-title { font-size: 25px; font-weight: 700; margin-bottom: 6px; color: var(--text-primary); }
.page-subtitle { color: var(--text-secondary); margin-bottom: 20px; }

/* 错误提示 */
.error-banner {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 20px; margin-bottom: 20px;
  background: #fef2f2; border-color: #fecaca;
  color: #dc2626; font-size: 12px;
}
.error-icon { font-size: 16px; flex-shrink: 0; }

/* 加载中 */
.loading-state {
  display: flex; flex-direction: column; align-items: center;
  padding: 80px 24px; gap: 16px; color: var(--text-secondary);
}
.spinner {
  width: 36px; height: 36px;
  border: 3px solid var(--border-color);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 工具栏 */
.toolbar {
  display: flex; align-items: center; gap: 16px;
  margin-bottom: 16px;
}
.toolbar-info { font-size: 11px; color: var(--text-light); }

/* 主布局 */
.overview-layout { display: flex; gap: 20px; align-items: flex-start; }

/* 树面板 */
.tree-panel {
  flex: 1; min-width: 0; padding: 16px 20px;
  max-height: calc(100vh - 200px); overflow-y: auto;
}

/* 根节点 */
.tree-root { padding: 0; }
.root-row {
  padding: 6px 8px; font-weight: 600; font-size: 13px;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 6px;
}
.root-name { color: var(--accent-blue); }

/* 通用树行 */
.tree-list, .tree-children { font-size: 11px; }
.tree-row {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 6px; border-radius: var(--radius-sm);
  cursor: pointer; transition: background 0.12s; user-select: none;
  line-height: 1.6;
}
.tree-row:hover { background: var(--bg-secondary); }
.tree-row.row-leaf { opacity: 0.85; }
.tree-row.row-leaf:hover { opacity: 1; }

.tree-toggle {
  width: 14px; text-align: center; font-size: 10px;
  color: var(--text-light); flex-shrink: 0;
  transition: transform 0.15s;
}
.tree-toggle.open { transform: rotate(90deg); }

.tree-leaf-icon { width: 14px; flex-shrink: 0; }

.tree-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.tree-name {
  flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.tree-count {
  font-size: 10px; color: var(--text-light); flex-shrink: 0;
}

/* 右侧详情面板 */
.detail-panel { width: 320px; flex-shrink: 0; }
.empty-panel {
  padding: 32px 20px; text-align: center; color: var(--text-light);
}
.empty-panel p { font-size: 12px; }

/* 统计卡片 */
.stats-card { padding: 20px; }
.stats-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.stats-header h3 {
  font-size: 14px; font-weight: 600; color: var(--text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  flex: 1; margin-right: 8px;
}
.level-badge {
  font-size: 10px; padding: 2px 8px; border-radius: 10px;
  background: var(--bg-secondary); color: var(--text-light);
  flex-shrink: 0;
}

.stats-grid {
  display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px;
}
.stat-box {
  display: flex; flex-direction: column; align-items: center;
  padding: 10px 14px; background: var(--bg-secondary);
  border-radius: var(--radius-sm); min-width: 80px; flex: 1;
}
.stat-num { font-size: 19px; font-weight: 700; color: var(--accent-blue); }
.stat-label { font-size: 10px; color: var(--text-light); margin-top: 2px; }

/* 层级分布 */
.level-stats { margin-bottom: 16px; }
.level-stats h4 {
  font-size: 11px; font-weight: 600; color: var(--text-secondary);
  margin-bottom: 8px;
}
.level-row {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 4px; font-size: 11px;
}
.level-label {
  width: 42px; flex-shrink: 0;
  color: var(--text-secondary); font-weight: 500;
}
.level-bar-wrap {
  flex: 1; height: 6px; background: var(--bg-secondary);
  border-radius: 3px; overflow: hidden;
}
.level-bar {
  height: 100%; background: var(--accent-blue);
  border-radius: 3px; transition: width 0.3s;
  min-width: 2px;
}
.level-count {
  width: 32px; text-align: right; flex-shrink: 0;
  color: var(--text-light); font-weight: 500;
}

.view-graph-btn {
  width: 100%; margin-top: 4px;
}
</style>
