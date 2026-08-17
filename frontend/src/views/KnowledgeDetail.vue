<template>
  <div class="page-container">
    <div v-if="node" class="detail-layout">
      <div class="card detail-main">
        <router-link to="/knowledge" class="back-link">&larr; 返回列表</router-link>
        <KnowledgeCard :node="node" />
        <div class="actions-row">
          <router-link :to="`/graph/${node.id}`" class="btn btn-primary">在图谱中查看</router-link>
          <button class="btn btn-secondary" @click="showPathPanel = !showPathPanel">路径查询</button>
        </div>

        <!-- 路径查询 -->
        <div v-if="showPathPanel" class="path-panel">
          <h4>查找从此节点出发的路径</h4>
          <div class="path-search-row">
            <select v-model="pathTargetId" class="input">
              <option value="">选择目标节点...</option>
              <option v-for="n in allNodes" :key="n.id" :value="n.id"
                v-show="n.id !== node.id">{{ n.properties?.name }}</option>
            </select>
            <button class="btn btn-sm btn-primary" @click="doFindPath" :disabled="!pathTargetId">
              查询
            </button>
          </div>
          <div v-if="foundPaths.length" class="path-results">
            <p class="path-hint">找到 {{ foundPaths.length }} 条路径</p>
            <div v-for="(p, i) in foundPaths" :key="i" class="path-line">
              <span class="path-idx">路径{{ i + 1 }}:</span>
              <span>{{ p.nodes?.map(n => n.properties?.name).join(' → ') }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 直接关系 -->
      <div class="card neighbors-card">
        <h3>直接关系 ({{ directRelations.length }})</h3>
        <div v-if="directRelations.length" class="rel-table">
          <div v-for="rel in directRelations" :key="rel.id" class="rel-row">
            <span class="rel-type" :class="getRelClass(rel.type)">{{ rel.type }}</span>
            <span class="rel-direction">
              <template v-if="rel.start_node === node.id">
                → {{ getNodeName(rel.end_node) }}
              </template>
              <template v-else>
                {{ getNodeName(rel.start_node) }} →
              </template>
            </span>
            <span class="rel-desc" v-if="rel.properties?.description">{{ rel.properties?.description }}</span>
            <button v-if="authStore.isAdmin" class="btn btn-sm btn-secondary" @click="doDeleteRel(rel.id)" title="删除关系"
              style="margin-left:auto;padding:2px 8px;font-size: 10px">删除</button>
          </div>
        </div>
        <p v-else class="empty-text">暂无直接关系</p>
      </div>

      <!-- 相关知识节点 -->
      <div class="card neighbors-card">
        <h3>相关知识节点 ({{ relatedNodes.length }})</h3>
        <div class="neighbor-list">
          <div v-for="n in relatedNodes" :key="n.id" class="neighbor-item">
            <span class="node-dot" :class="getCat(n.properties?.category)"></span>
            <router-link :to="`/knowledge/${n.id}`">{{ n.properties?.name }}</router-link>
            <span class="neighbor-cat">{{ n.properties?.category }}</span>
          </div>
        </div>
        <p v-if="!relatedNodes.length" class="empty-text">暂无相关知识节点</p>
      </div>
    </div>
    <UiLoading v-else />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import KnowledgeCard from '../components/KnowledgeCard.vue'
import { authStore } from '../stores/auth'
import { useFeedback } from '../composables/useFeedback'

const { tip, ask } = useFeedback()

const route = useRoute()
const node = ref(null)
const allNodes = ref([])
const directRelations = ref([])
const relatedNodes = ref([])
const foundPaths = ref([])
const showPathPanel = ref(false)
const pathTargetId = ref('')

function getCat(c) {
  const m = { '基础': 'node-category-basic', '核心': 'node-category-core',
    '进阶': 'node-category-advanced', '数据结构': 'node-category-structure',
    '数据科学': 'node-category-data' }
  return m[c] || ''
}

function getRelClass(t) {
  const m = { 'PREDECESSOR': 'rel-pre', 'SUCCESSOR': 'rel-suc', 'BELONGS_TO': 'rel-bel',
    'RELATED_TO': 'rel-rel', 'CONTAINS': 'rel-con', 'DEPENDS_ON': 'rel-dep', 'EXTENDS': 'rel-ext' }
  return m[t] || ''
}

function getNodeName(nid) {
  const n = relatedNodes.value.find(x => x.id === nid)
  return n?.properties?.name || node.value?.id === nid ? node.value?.properties?.name : nid
}

onMounted(async () => {
  try {
    const nid = route.params.id
    const [nodeR, allR, graphR] = await Promise.all([
      api.get(`/knowledge-points/${nid}`),
      api.get('/knowledge-points'),
      api.get(`/graph/node/${nid}/neighbors?depth=1`)
    ])
    if (nodeR.success) node.value = nodeR.data
    if (allR.success) allNodes.value = allR.data
    if (graphR.success) {
      relatedNodes.value = (graphR.data.nodes || []).filter(n => n.id !== nid)
      // 筛选与当前节点直接相关的关系
      directRelations.value = (graphR.data.relationships || []).filter(
        r => r.start_node === nid || r.end_node === nid
      )
    }
  } catch (e) { console.error('加载知识点详情失败:', e) }
})

async function doFindPath() {
  if (!node.value || !pathTargetId.value) return
  try {
    const r = await api.post('/relationships/find-path', {
      start_id: node.value.id,
      end_id: pathTargetId.value,
      max_depth: 5
    })
    if (r.success) foundPaths.value = r.data
  } catch (e) { console.error('查找路径失败:', e) }
}

function doDeleteRel(relId) {
  ask('确定删除此关系？', async () => {
    try {
      await api.delete(`/relationships/${relId}`)
      directRelations.value = directRelations.value.filter(r => r.id !== relId)
    } catch (e) { console.error('删除关系失败:', e) }
  })
}
</script>

<style scoped>
.detail-layout { max-width: 800px; display: flex; flex-direction: column; gap: 16px; }
.back-link { font-size: 12px; display: inline-block; margin-bottom: 12px; }
h1 { font-size: 23px; margin-bottom: 12px; }
.meta-row { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; font-size: 12px; color: var(--text-secondary); }
.desc { font-size: 13px; color: var(--text-primary); line-height: 1.7; margin-bottom: 16px; }
.actions-row { display: flex; gap: 10px; }

/* 路径查询 */
.path-panel {
  margin-top: 16px; padding: 16px;
  background: var(--bg-secondary); border-radius: var(--radius-md);
}
.path-panel h4 { font-size: 12px; margin-bottom: 10px; color: var(--text-secondary); }
.path-search-row { display: flex; gap: 8px; }
.path-search-row .input { flex: 1; }
.path-results { margin-top: 12px; }
.path-hint { font-size: 11px; color: var(--text-light); margin-bottom: 6px; }
.path-line { font-size: 11px; padding: 4px 0; color: var(--text-primary); }
.path-idx { font-weight: 600; color: var(--accent-blue); margin-right: 8px; }

/* 关系表 */
.neighbors-card h3 { font-size: 14px; margin-bottom: 12px; color: var(--text-secondary); }
.rel-table { display: flex; flex-direction: column; gap: 8px; }
.rel-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; background: var(--bg-secondary);
  border-radius: var(--radius-sm); font-size: 11px;
}
.rel-type {
  padding: 2px 8px; border-radius: 8px;
  font-size: 10px; font-weight: 600; flex-shrink: 0;
}
.rel-pre { background: #dbeafe; color: #1d4ed8; }
.rel-suc { background: #fce7f3; color: #be185d; }
.rel-bel { background: #ede9fe; color: #6d28d9; }
.rel-rel { background: #d1fae5; color: #047857; }
.rel-con { background: #cffafe; color: #0e7490; }
.rel-dep { background: #fef3c7; color: #b45309; }
.rel-ext { background: #e0e7ff; color: #4338ca; }
.rel-direction { font-weight: 500; }
.rel-desc { color: var(--text-light); font-size: 11px; }

.neighbor-list { display: flex; flex-wrap: wrap; gap: 10px; }
.neighbor-item { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.neighbor-cat { font-size: 10px; color: var(--text-light); }

.node-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.tag { padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 500; }
.node-category-basic { background: #dbeafe; color: #1d4ed8; }
.node-category-core { background: #ede9fe; color: #6d28d9; }
.node-category-advanced { background: #d1fae5; color: #047857; }
.node-category-structure { background: #cffafe; color: #0e7490; }
.node-category-data { background: #fef3c7; color: #b45309; }

.empty { text-align: center; padding: 60px; color: var(--text-light); }
.empty-text { color: var(--text-light); font-size: 12px; }
</style>
