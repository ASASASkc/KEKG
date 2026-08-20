<template>
  <div class="two-col">
    <!-- 侧边栏 -->
    <aside class="col-sidebar">
      <!-- 搜索 -->
      <div class="sidebar-search">
        <input v-model="searchKw" class="input" placeholder="搜索知识点..."
          @keyup.enter="doSearch" />
        <button class="btn btn-sm btn-primary" @click="doSearch">搜索</button>
      </div>

      <!-- 拓展选择 -->
      <div class="track-selector">
        <label class="track-label">选择拓展：</label>
        <select v-model="selectedTrack" class="input input-sm" @change="loadTrackGraph">
          <option v-for="t in tracks" :key="t.name" :value="t.name">{{ t.name }} ({{ t.node_count }})</option>
        </select>
      </div>

      <!-- 当前拓展标签 -->
      <div v-if="currentLabel" class="current-label">
        <span class="label-badge">{{ getGroupDisplayName(currentLabel) }}</span>
      </div>

      <!-- 搜索结果 -->
      <div v-if="searchResults.length" class="search-results">
        <h4>搜索结果 ({{ searchResults.length }})</h4>
        <div v-for="n in searchResults" :key="n.id" class="node-item"
          :class="{ active: selectedNode?.id === n.id }" @click="selectNode(n)">
          <span class="node-dot" :style="{ background: catColor[n.properties?.category] || '#94a3b8' }"></span>
          <span class="node-label">{{ n.properties?.name }}</span>
        </div>
      </div>

      <!-- 选中节点详情 -->
      <div v-if="selectedNode" class="node-detail card">
        <KnowledgeCard :node="selectedNode" @saved="onNodeSaved" @deleted="onNodeDeleted" />
        <div class="detail-actions">
          <button class="btn btn-sm btn-primary" @click="viewNeighbors(selectedNode.id)">
            展开邻居 (+1层)
          </button>
        </div>
      </div>

      <!-- 路径查询 -->
      <div v-if="selectedNode" class="path-panel card">
        <h5>路径查询</h5>
        <div class="path-search-row">
          <input v-model="pathTargetKw" class="input input-sm" placeholder="搜索目标知识点..."
            @keyup.enter="searchPathTarget" />
          <button class="btn btn-sm btn-primary" @click="searchPathTarget">搜索</button>
        </div>
        <div v-if="pathTargetResults.length" class="path-search-results">
          <div v-for="n in pathTargetResults" :key="n.id" class="path-result-item"
            :class="{ active: pathTargetNode?.id === n.id }"
            @click="selectPathTarget(n)">
            <span class="node-dot" :style="{ background: catColor[n.properties?.category] || '#94a3b8' }"></span>
            <span>{{ n.properties?.name }}</span>
          </div>
        </div>
        <div v-if="pathTargetNode" class="path-target-info">
          <span class="path-target-label">目标：</span>
          <strong>{{ pathTargetNode.properties?.name }}</strong>
          <button class="btn btn-xs btn-secondary" @click="clearPathTarget">清除</button>
        </div>
        <button v-if="pathTargetNode" class="btn btn-sm btn-primary" style="margin-top:6px;width:100%"
          @click="findPath">查找最短路径</button>
        <div v-if="pathResult !== null && pathResult.length === 0" class="path-empty">
          未找到路径
        </div>
        <div v-if="pathResult && pathResult.length > 0" class="path-results">
          <div class="path-found">
            <span class="path-idx">找到路径 ({{ pathResult[0].nodes.length }} 步)</span>
          </div>
          <div class="path-steps-visual">
            <template v-for="(node, idx) in pathResult[0].nodes" :key="node.id">
              <span class="path-step-node" :style="{ outlineColor: catColor[node.properties?.category] || '#94a3b8' }"
                @click="selectNode(node)">
                {{ node.properties?.name || node.id }}
              </span>
              <span v-if="idx < pathResult[0].relationships.length" class="path-step-arrow"
                :title="pathResult[0].relationships[idx]?.type">
                &#8594;
              </span>
            </template>
          </div>
          <button class="btn btn-xs btn-primary" style="margin-top:6px" @click="highlightPathOnGraph">
            在图谱中高亮
          </button>
        </div>
      </div>

      <!-- 子图谱导航 -->
      <SubGraphPanel
        v-if="selectedNode"
        :node="selectedNode"
        @enter-subgraph="enterSubGraph"
        @expand-neighbors="viewNeighbors"
        @select-child="selectNode"
      />

      <!-- 外部链接 -->
      <div v-if="externalLinks.length > 0" class="external-links">
        <h4>学习资源</h4>
        <a v-for="(link, i) in externalLinks" :key="i"
           :href="link.url" target="_blank" rel="noopener"
           class="ext-link">
          {{ link.title }}
        </a>
      </div>

      <!-- 图例 -->
      <div class="legend">
        <h4>图例</h4>
        <template v-if="selectedTrack && selectedTrack !== '公共基础' && trackColor[selectedTrack]">
          <div class="legend-item">
            <span class="legend-dot" :style="{ background: trackColor[selectedTrack] }"></span>
            <span>{{ selectedTrack }}</span>
          </div>
        </template>
        <template v-else>
          <div v-for="(color, cat) in catColor" :key="cat" class="legend-item">
            <span class="legend-dot" :style="{ background: color }"></span>
            <span>{{ cat }}</span>
          </div>
        </template>
      </div>
    </aside>

    <!-- 图谱区 -->
    <section class="col-main">
      <!-- 面包屑导航 -->
      <div v-if="breadcrumb.length" class="breadcrumb-bar">
        <span v-for="(b, idx) in breadcrumb" :key="idx" class="breadcrumb-item">
          <span v-if="idx > 0" class="breadcrumb-sep">></span>
          <a v-if="idx < breadcrumb.length - 1" class="breadcrumb-link"
            @click="navigateToBreadcrumb(idx)">{{ b.name }}</a>
          <span v-else class="breadcrumb-current">{{ b.name }}</span>
        </span>
        <button v-if="graphHistory.length > 0" class="btn btn-xs btn-secondary"
          @click="goBack" title="返回上级">
          &larr; 返回
        </button>
      </div>
      <div ref="chartRef" class="chart-container"></div>
      <div id="practice-target"></div>
      <div v-if="loading" class="loading-overlay">
        <div class="loading-spinner"></div>
        <p>正在加载拓展"{{ selectedTrack }}"...</p>
      </div>
      <div v-else-if="!graphData.nodes.length" class="empty-hint">
        <div class="empty-icon">&#9671;</div>
        <p>{{ emptyHintMessage }}</p>
      </div>
      <div v-if="graphData.nodes.length" class="graph-info">
        <span>{{ graphData.nodes.length }} 节点 · {{ graphData.relationships.length }} 关系</span>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import api from '../api'
import { useFeedback } from '../composables/useFeedback'
import KnowledgeCard from '../components/KnowledgeCard.vue'
import SubGraphPanel from '../components/SubGraphPanel.vue'

const route = useRoute()
const { tip } = useFeedback()
const chartRef = ref(null)
let chart = null
let resizeObserver = null

const searchKw = ref('')
const currentLabel = computed(() => route.query.label || '')
const searchResults = ref([])
const selectedNode = ref(null)
const externalLinks = computed(() => {
  if (!selectedNode.value) return []
  const props = selectedNode.value.properties || {}
  try {
    const el = props.external_links
    if (!el) return []
    const links = typeof el === 'string' ? JSON.parse(el) : el
    return Array.isArray(links) ? links : []
  } catch { return [] }
})
const graphData = ref({ nodes: [], relationships: [] })
const tracks = ref([])
const selectedTrack = ref('')
const loading = ref(false)
const trackLoaded = ref(false)

// ── 路径查询 ──
const pathTargetKw = ref('')
const pathTargetResults = ref([])
const pathTargetNode = ref(null)
const pathResult = ref(null) // null = 未查询, [] = 无结果, [...] = 有结果

const GROUP_NAMES = {
  'KnowledgePoint': '系统知识图谱',
  'TextbookKnowledge': '教材知识图谱'
}

function getGroupDisplayName(label) {
  return GROUP_NAMES[label] || label
}

// ── 空状态提示语 ──
const emptyHintMessage = computed(() => {
  if (loading.value) return ''
  if (trackLoaded.value && !graphData.value.nodes.length) {
    return `拓展"${selectedTrack.value}"暂无数据`
  }
  if (!selectedTrack.value) return '请选择拓展开始探索知识图谱'
  return '搜索知识点开始探索知识图谱'
})

// ── 销毁图表（同时清理 ResizeObserver，避免重复观察） ──
function disposeChart() {
  if (resizeObserver) { resizeObserver.disconnect(); resizeObserver = null }
  if (chart) { chart.dispose(); chart = null }
}

// ── 拓展加载 ──

async function loadTrackGraph() {
  const track = selectedTrack.value
  if (!track) {
    clearAllState()
    disposeChart()
    trackLoaded.value = false
    return
  }
  try {
    loading.value = true
    clearAllState()
    disposeChart()
    const r = await api.get(`/graph/track/${encodeURIComponent(track)}`)
    if (r.success) {
      trackLoaded.value = true
      graphData.value = r.data || { nodes: [], relationships: [] }
      if (graphData.value.nodes.length) {
        await nextTick()
        renderChart()
      }
    } else {
      trackLoaded.value = true
      graphData.value = { nodes: [], relationships: [] }
    }
  } catch (e) {
    console.error('加载拓展图谱失败:', e)
    tip('图谱加载失败，请稍后重试')
    trackLoaded.value = true
    graphData.value = { nodes: [], relationships: [] }
  } finally {
    loading.value = false
  }
}

// ── 统一清空所有状态 ──
function clearAllState() {
  searchResults.value = []
  selectedNode.value = null
  graphData.value = { nodes: [], relationships: [] }
  breadcrumb.value = []
  graphHistory.value = []
  // 清空路径查询状态
  pathTargetKw.value = ''
  pathTargetResults.value = []
  pathTargetNode.value = null
  pathResult.value = null
}

async function loadTracks() {
  try {
    const r = await api.get('/graph/tracks')
    if (r.success) {
      tracks.value = r.data?.items || r.data
    }
  } catch (e) { console.error('加载拓展列表失败:', e); tip('拓展列表加载失败，请稍后重试') }
}

// ── KnowledgeCard 事件处理 ──
function onNodeSaved(updatedData) {
  if (selectedNode.value) {
    selectedNode.value.properties = {
      ...selectedNode.value.properties,
      ...(updatedData.properties || updatedData)
    }
  }
}

function onNodeDeleted(deletedId) {
  graphData.value.nodes = graphData.value.nodes.filter(n => n.id !== deletedId)
  graphData.value.relationships = graphData.value.relationships.filter(
    r => r.start_node !== deletedId && r.end_node !== deletedId
  )
  selectedNode.value = null
  searchResults.value = searchResults.value.filter(n => n.id !== deletedId)
  nextTick(() => renderChart())
}

const catColor = {
  '基础': '#3b82f6', '核心': '#8b5cf6', '进阶': '#10b981',
  '数据结构': '#06b6d4', '数据科学': '#f59e0b', '未分类': '#94a3b8'
}

// 拓展板块颜色映射
const trackColor = {
  '网络爬虫':       '#f59e0b',
  '数据分析及可视化': '#06b6d4',
  '机器学习':       '#10b981',
  '深度学习':       '#3b82f6',
  '大模型':         '#8b5cf6',
  '自然语言处理':    '#f43f5e',
  '自动化运维':     '#f97316',
}

function getNodeColor(node) {
  // 优先用拓展颜色（公共基础除外，使用分类颜色）
  let tracks = node.properties?.tracks
  if (typeof tracks === 'string') {
    try { tracks = JSON.parse(tracks) } catch (e) { tracks = [] }
  }
  if (Array.isArray(tracks) && tracks.length > 0) {
    for (const t of tracks) {
      if (t !== '公共基础' && trackColor[t]) {
        return trackColor[t]
      }
    }
  }
  // 回退到分类颜色
  return catColor[node.properties?.category] || '#94a3b8'
}

// ── 图历史栈与面包屑 ──
const graphHistory = ref([]) // [{nodeId, breadcrumb, graphData}]
const breadcrumb = ref([])  // [{id, name}]

function pushHistory(node) {
  graphHistory.value.push({
    nodeId: node.id,
    breadcrumb: [...breadcrumb.value],
    graphData: JSON.parse(JSON.stringify(graphData.value))
  })
}

async function enterSubGraph(nodeId) {
  const node = graphData.value.nodes.find(n => n.id === nodeId)
  if (!node) return
  pushHistory(node)
  breadcrumb.value.push({ id: nodeId, name: node.properties?.name || nodeId })
  try {
    const r = await api.get(`/graph/node/${nodeId}/children`)
    if (r.success && r.data.nodes?.length) {
      graphData.value = r.data
      // 保留 selectedNode，让侧边栏继续显示当前节点信息和子图谱导航
      await nextTick()
      renderChart()
    }
  } catch (e) { console.error('加载子图失败:', e); tip('子图加载失败，请稍后重试') }
}

function navigateToBreadcrumb(idx) {
  const target = breadcrumb.value[idx]
  // 回退到相应层级
  while (graphHistory.value.length > idx) goBack()
  // 选中目标节点
  const node = graphData.value.nodes.find(n => n.id === target.id)
  if (node) selectNode(node)
}

function goBack() {
  if (!graphHistory.value.length) return
  const prev = graphHistory.value.pop()
  breadcrumb.value = prev.breadcrumb
  graphData.value = prev.graphData
  selectedNode.value = null
  searchResults.value = []
  nextTick(() => renderChart())
}

// ── 初始化 ──

onMounted(async () => {
  await loadTracks()
  // 检查 URL query 参数（从首页搜索跳转过来的）
  if (route.query.nodeId) {
    await loadNodeById(route.query.nodeId)
  } else if (route.query.search) {
    searchKw.value = route.query.search
    await doSearch(true)
  }
  // route.params.nodeId 由下面的 watch(immediate) 处理，此处不再重复
  // 无特定参数时默认加载"公共基础"拓展
  if (!route.query.search && !route.params.nodeId && !route.query.nodeId) {
    selectedTrack.value = '公共基础'
    await loadTrackGraph()
  }
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  disposeChart()
  window.removeEventListener('resize', onResize)
})

watch(() => route.params.nodeId, async (nid) => {
  if (nid) await loadNodeById(nid)
}, { immediate: true })

// 监听 route.query.label 变化，切换到对应拓展
watch(() => route.query.label, async (newLabel, oldLabel) => {
  if (newLabel && newLabel !== oldLabel) {
    clearAllState()
    trackLoaded.value = false
    disposeChart()
    selectedTrack.value = newLabel
    await loadTrackGraph()
  }
})

async function loadNodeById(nid) {
  try {
    const r = await api.get(`/knowledge-points/${nid}`)
    if (r.success && r.data) {
      const node = { ...r.data, properties: { ...r.data.properties } }
      await selectNode({ id: nid, labels: ['KnowledgePoint'], properties: r.data.properties || node.properties })
    }
  } catch (e) { console.error('加载节点详情失败:', e); tip('节点详情加载失败，请稍后重试') }
}

// ── 搜索与选择 ──

async function doSearch(fromHomepage) {
  const kw = searchKw.value.trim()
  if (!kw) return
  try {
    const label = currentLabel.value ? `&label=${encodeURIComponent(currentLabel.value)}` : ''
    const r = await api.get(`/knowledge-points/search?keyword=${encodeURIComponent(kw)}${label}`)
    if (r.success) {
      searchResults.value = r.data
      // 从首页跳转过来时，把搜索结果直接显示在图谱中
      if (fromHomepage && r.data.length > 0) {
        graphData.value = {
          nodes: r.data,
          relationships: []
        }
        selectNode(r.data[0])
      } else if (r.data.length > 0) {
        selectNode(r.data[0])
      }
    }
  } catch (e) { console.error('搜索节点失败:', e); tip('节点搜索失败，请稍后重试') }
}

async function selectNode(node) {
  selectedNode.value = node
  try {
    const r = await api.get(`/graph/node/${node.id}/neighbors?depth=3`)
    if (r.success) {
      const center = graphData.value.nodes.find(n => n.id === node.id) || node
      const existingIds = new Set(graphData.value.nodes.map(n => n.id))
      const neighborNodes = (r.data.nodes || []).filter(n => !existingIds.has(n.id) || n.id === node.id)
      const nodeMap = {}
      ;[center, ...neighborNodes].forEach(n => { nodeMap[n.id] = n })
      const rels = (r.data.relationships || []).filter(rel => nodeMap[rel.start_node] && nodeMap[rel.end_node])
      // 构建去重后的节点和关系集合
      const allNodes = [...graphData.value.nodes.filter(n => n.id !== node.id),
        center, ...neighborNodes.filter(n => n.id !== center.id)]
      const allRels = [...graphData.value.relationships, ...rels]
      const uniqueRels = []
      const seenRels = new Set()
      allRels.forEach(rel => {
        const k = `${rel.start_node}-${rel.end_node}-${rel.type}`
        if (!seenRels.has(k)) { seenRels.add(k); uniqueRels.push(rel) }
      })
      graphData.value = { nodes: allNodes, relationships: uniqueRels }
      await nextTick()
      renderChart()
    }
  } catch (e) { console.error('展开子节点失败:', e); tip('子节点展开失败，请稍后重试') }
}

async function viewNeighbors(nodeId) {
  try {
    const r = await api.get(`/graph/node/${nodeId}/neighbors?depth=1`)
    if (r.success) {
      const existingIds = new Set(graphData.value.nodes.map(n => n.id))
      const newNodes = (r.data.nodes || []).filter(n => !existingIds.has(n.id))
      const allNodes = [...graphData.value.nodes, ...newNodes]
      const allRels = [...graphData.value.relationships, ...(r.data.relationships || [])]
      const uniqueRels = []
      const seen = new Set()
      allRels.forEach(rel => {
        const k = `${rel.start_node}-${rel.end_node}-${rel.type}`
        if (!seen.has(k)) { seen.add(k); uniqueRels.push(rel) }
      })
      graphData.value = { nodes: allNodes, relationships: uniqueRels }
      await nextTick()
      renderChart()
    }
  } catch (e) { console.error('展开邻居失败:', e); tip('邻居展开失败，请稍后重试') }
}

// ── 路径查询 ──

async function searchPathTarget() {
  const kw = pathTargetKw.value.trim()
  if (!kw) return
  try {
    const label = currentLabel.value ? `&label=${encodeURIComponent(currentLabel.value)}` : ''
    const r = await api.get(`/knowledge-points/search?keyword=${encodeURIComponent(kw)}${label}`)
    if (r.success) {
      pathTargetResults.value = r.data
      pathTargetNode.value = null
      pathResult.value = null
    }
  } catch (e) { console.error('搜索目标节点失败:', e); tip('目标节点搜索失败，请稍后重试') }
}

function selectPathTarget(node) {
  pathTargetNode.value = node
  pathTargetResults.value = []
  pathResult.value = null
}

function clearPathTarget() {
  pathTargetNode.value = null
  pathResult.value = null
  pathTargetKw.value = ''
}

async function findPath() {
  if (!selectedNode.value || !pathTargetNode.value) return
  try {
    const r = await api.post('/graph/path', {
      start_id: selectedNode.value.id,
      end_id: pathTargetNode.value.id,
      max_depth: 5
    })
    if (r.success) {
      pathResult.value = r.data
      if (r.data && r.data.length > 0) {
        // 自动高亮
        highlightPathOnGraph()
      }
    }
  } catch (e) { console.error('路径查询失败:', e); tip('路径查询失败，请稍后重试') }
}

function highlightPathOnGraph() {
  if (!pathResult.value || !pathResult.value.length) return
  const path = pathResult.value[0]
  const hlIds = path.nodes.map(n => n.id)
  // 把路径上的节点加入图谱
  const existingIds = new Set(graphData.value.nodes.map(n => n.id))
  const existingRelKeys = new Set(graphData.value.relationships.map(r => `${r.start_node}-${r.end_node}-${r.type}`))
  const newNodes = path.nodes.filter(n => !existingIds.has(n.id))
  const newRels = path.relationships.filter(r => !existingRelKeys.has(`${r.start_node}-${r.end_node}-${r.type}`))
  if (newNodes.length || newRels.length) {
    graphData.value = {
      nodes: [...graphData.value.nodes, ...newNodes],
      relationships: [...graphData.value.relationships, ...newRels]
    }
  }
  nextTick(() => renderChart(hlIds))
}

// ── ECharts 渲染 ──

function renderChart(highlightIds) {
  if (!chartRef.value) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
    // 容器尺寸变化时自动重绘，避免布局调整后画布尺寸失配导致裁剪/留白
    resizeObserver = new ResizeObserver(() => { if (chart) chart.resize() })
    resizeObserver.observe(chartRef.value)
    chart.on('click', (params) => {
      if (params.data && params.data.nodeId) {
        const node = graphData.value.nodes.find(n => n.id === params.data.nodeId)
        if (node) selectNode(node)
      }
    })
  } else {
    chart.resize()
  }

  const nodes = graphData.value.nodes
  const rels = graphData.value.relationships
  if (!nodes.length) return

  const hlSet = new Set(highlightIds || [])

  chart.setOption({
    tooltip: { show: false },
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      force: {
        repulsion: nodes.length > 20 ? 200 : 350,
        edgeLength: [100, 250],
        gravity: 0.06,
        layoutAnimation: true
      },
      label: { show: true, fontSize: 11, color: '#334155',
        formatter: (p) => p.data.name.length > 6 ? p.data.name.slice(0, 6) + '...' : p.data.name },
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: 8,
      lineStyle: { color: '#94a3b8', curveness: 0.2, width: 1.4 },
      emphasis: {
        scale: 1.15
      },
      data: nodes.map(n => ({
        name: n.properties?.name || n.id,
        nodeId: n.id,
        symbolSize: hlSet.has(n.id) ? 32 : (selectedNode.value?.id === n.id ? 36 : 20),
        category: n.properties?.category || '未分类',
        itemStyle: {
          color: getNodeColor(n),
          shadowBlur: hlSet.has(n.id) ? 20 : (selectedNode.value?.id === n.id ? 12 : 0),
          shadowColor: getNodeColor(n)
        },
        label: { fontWeight: hlSet.has(n.id) ? 'bold' : 'normal' }
      })),
      links: rels.map(r => ({
        source: nodes.findIndex(n => n.id === r.start_node),
        target: nodes.findIndex(n => n.id === r.end_node),
        sourceName: nodes.find(n => n.id === r.start_node)?.properties?.name || '?',
        targetName: nodes.find(n => n.id === r.end_node)?.properties?.name || '?',
        relType: r.type
      }))
    }]
  }, { notMerge: false })
}

const onResize = () => { if (chart) chart.resize() }
</script>

<style scoped>
.two-col { display: flex; height: calc(100vh - 64px); overflow: hidden; }
.col-sidebar {
  width: 360px;
  flex-shrink: 0;
  background: var(--bg-primary);
  border-right: 1px solid var(--border-color);
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.col-main {
  flex: 1;
  position: relative;
  background: #fafbfc;
  overflow: hidden;
}
.chart-container { width: 100%; height: 100%; }
#practice-target {
  position: absolute;
  bottom: 0;
  right: 0;
  z-index: 50;
  pointer-events: none;
}
#practice-target > * {
  pointer-events: auto;
}

/* 面包屑 */
.breadcrumb-bar {
  position: absolute; top: 0; left: 0; right: 0;
  display: flex; align-items: center; gap: 4px;
  padding: 8px 16px; background: rgba(255,255,255,0.92);
  border-bottom: 1px solid var(--border-color); z-index: 10;
  font-size: 13px; flex-wrap: wrap;
}
.breadcrumb-item { display: flex; align-items: center; gap: 4px; }
.breadcrumb-sep { color: var(--text-light); margin: 0 2px; }
.breadcrumb-link { color: var(--accent-blue); cursor: pointer; }
.breadcrumb-link:hover { text-decoration: underline; }
.breadcrumb-current { color: var(--text-primary); font-weight: 600; }
.btn-xs { padding: 2px 8px; font-size: 11px; margin-left: auto; }

.sidebar-search { display: flex; gap: 6px; }
.sidebar-search .input { flex: 1; }

.current-label { margin-top: 4px; }
.track-selector { display: flex; align-items: center; gap: 8px; margin-top: 4px; }
.track-selector .track-label { font-size: 13px; color: var(--text-secondary); white-space: nowrap; }
.track-selector .input { flex: 1; }
.label-badge {
  display: inline-block; padding: 4px 12px;
  background: rgba(59,130,246,0.12); color: var(--accent-blue);
  border-radius: 12px; font-size: 12px; font-weight: 500;
}

.search-results { max-height: 200px; overflow-y: auto; }
.search-results h4 { font-size: 13px; color: var(--text-secondary); margin-bottom: 8px; }

.node-item {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 10px; border-radius: var(--radius-sm);
  cursor: pointer; font-size: 13px; transition: background 0.15s;
}
.node-item:hover, .node-item.active { background: var(--bg-secondary); }
.node-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.node-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.node-detail { margin-top: 4px; }
.node-name { font-size: 18px; font-weight: 600; margin-bottom: 8px; }
.node-meta { display: flex; gap: 8px; margin-bottom: 10px; }
.tag { padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 500; }
.node-category-basic { background: #dbeafe; color: #1d4ed8; }
.node-category-core { background: #ede9fe; color: #6d28d9; }
.node-category-advanced { background: #d1fae5; color: #047857; }
.node-category-structure { background: #cffafe; color: #0e7490; }
.node-category-data { background: #fef3c7; color: #b45309; }
.tag-level { background: var(--bg-secondary); color: var(--text-secondary); }
.node-desc { font-size: 13px; color: var(--text-secondary); line-height: 1.6; margin-bottom: 10px; }

.detail-actions { display: flex; flex-wrap: wrap; gap: 6px; }

/* 路径查询面板 */
.path-panel { padding: 12px; }
.path-panel h5 { font-size: 13px; font-weight: 600; margin-bottom: 8px; color: var(--text-secondary); }
.path-search-row { display: flex; gap: 6px; }
.path-search-row .input { flex: 1; }
.input-sm { padding: 5px 8px; font-size: 12px; }
.path-search-results { max-height: 120px; overflow-y: auto; margin-top: 4px; }
.path-result-item {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 8px; font-size: 12px; cursor: pointer; border-radius: var(--radius-sm);
}
.path-result-item:hover, .path-result-item.active { background: var(--bg-secondary); }
.path-target-info {
  margin-top: 6px; display: flex; align-items: center; gap: 6px; font-size: 12px;
}
.path-target-label { color: var(--text-secondary); }
.path-empty { padding: 8px; font-size: 12px; color: var(--text-light); }
.path-results { margin-top: 8px; }
.path-found { margin-bottom: 6px; }
.path-idx { font-weight: 600; color: var(--accent-blue); font-size: 12px; }
.path-steps-visual { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
.path-step-node {
  padding: 2px 8px; border-radius: var(--radius-sm);
  font-size: 11px; font-weight: 500; cursor: pointer;
  outline: 2px solid #94a3b8; outline-offset: 1px;
  background: var(--bg-primary); color: var(--text-primary);
  transition: all 0.15s;
}
.path-step-node:hover { opacity: 0.85; transform: scale(1.05); }
.path-step-arrow { color: var(--text-light); font-size: 12px; }

.rel-form { display: flex; flex-direction: column; }

.legend { margin-top: auto; }
.legend h4 { font-size: 13px; color: var(--text-secondary); margin-bottom: 8px; }

/* 外部链接 */
.external-links { margin-top: 8px; padding: 10px; background: var(--bg-card); border-radius: 8px; border: 1px solid var(--border-color); }
.external-links h4 { font-size: 13px; color: var(--text-secondary); margin-bottom: 6px; }
.ext-link { display: block; font-size: 12px; color: #3b82f6; text-decoration: none; padding: 3px 0; border-bottom: 1px solid var(--border-color); }
.ext-link:last-child { border-bottom: none; }
.ext-link:hover { color: #2563eb; text-decoration: underline; }
.legend-item { display: flex; align-items: center; gap: 8px; font-size: 12px; padding: 3px 0; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }

.empty-hint {
  position: absolute; inset: 0;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  color: var(--text-light);
}
.empty-icon { font-size: 48px; margin-bottom: 12px; color: var(--accent-blue); }

/* loading 覆盖层 */
.loading-overlay {
  position: absolute; inset: 0;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  background: rgba(255,255,255,0.85);
  z-index: 20; color: var(--text-secondary);
}
.loading-spinner {
  width: 40px; height: 40px;
  border: 3px solid var(--border-color);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 12px;
}
@keyframes spin { to { transform: rotate(360deg); } }

.graph-info {
  position: absolute; bottom: 12px; left: 12px;
  background: rgba(255,255,255,0.9); padding: 6px 14px;
  border-radius: var(--radius-sm); font-size: 13px;
  color: var(--text-secondary); box-shadow: var(--shadow-sm);
}

/* 窄屏（≤768px）：侧栏纵向堆叠到图谱上方并占满宽度，图例可完整滚动
   桌面宽度下保持"侧栏在左、图谱在右"的两栏布局 */
@media (max-width: 768px) {
  .two-col {
    flex-direction: column;
    height: auto;
  }
  .two-col .col-sidebar {
    width: 100%;
    max-height: 280px;
    border-right: none;
    border-bottom: 1px solid var(--border-color);
  }
  .col-main { min-height: 50vh; }
}
</style>
