<template>
  <div class="subgraph-panel" v-if="node">
    <div class="panel-header">
      <span class="panel-title">子图谱</span>
      <span class="child-count" v-if="childCount !== null">{{ childCount }} 个子知识点</span>
    </div>
    <div class="panel-actions">
      <button class="btn btn-sm btn-primary" @click="$emit('enter-subgraph', node.id)"
        :disabled="childCount === 0">
        进入子图谱
      </button>
      <button class="btn btn-sm btn-secondary" @click="$emit('expand-neighbors', node.id)"
        v-if="childCount !== null && childCount > 0">
        加载子节点
      </button>
    </div>
    <div v-if="recentChildren.length" class="child-list">
      <h5>子节点 ({{ recentChildren.length }})</h5>
      <div v-for="child in recentChildren" :key="child.id" class="child-item"
        @click="$emit('select-child', child)">
        <span class="child-dot" :style="{ background: catColor[child.properties?.category] || '#94a3b8' }"></span>
        <span class="child-name">{{ child.properties?.name }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import api from '../api'

const props = defineProps({
  node: { type: Object, default: null }
})

defineEmits(['enter-subgraph', 'expand-neighbors', 'select-child'])

const childCount = ref(null)
const recentChildren = ref([])

const catColor = {
  '基础': '#3b82f6', '核心': '#8b5cf6', '进阶': '#10b981',
  '数据结构': '#06b6d4', '数据科学': '#f59e0b', '未分类': '#94a3b8'
}

watch(() => props.node?.id, async (nid) => {
  if (!nid) {
    childCount.value = null
    recentChildren.value = []
    return
  }
  try {
    const r = await api.get(`/graph/node/${nid}/children`)
    if (r.success) {
      recentChildren.value = (r.data.nodes || []).slice(0, 10)
      childCount.value = r.data.nodes?.length || 0
    }
  } catch (e) {
    childCount.value = null
  }
}, { immediate: true })
</script>

<style scoped>
.subgraph-panel {
  margin-top: 12px; padding: 12px;
  background: var(--bg-secondary); border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}
.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.panel-title { font-size: 12px; font-weight: 600; color: var(--text-primary); }
.child-count { font-size: 11px; color: var(--accent-blue); font-weight: 500; }
.panel-actions { display: flex; gap: 6px; margin-bottom: 10px; }

.child-list h5 { font-size: 11px; color: var(--text-secondary); margin-bottom: 6px; }
.child-item {
  display: flex; align-items: center; gap: 8px;
  padding: 5px 8px; border-radius: var(--radius-sm);
  cursor: pointer; font-size: 11px; transition: background 0.15s;
}
.child-item:hover { background: var(--bg-primary); }
.child-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.child-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-primary); }
</style>
