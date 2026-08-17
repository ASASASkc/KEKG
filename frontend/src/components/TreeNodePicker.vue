<template>
  <div class="tp-node">
    <div
      :class="['tp-row', isLeaf ? 'tp-leaf' : 'tp-group']"
      :style="{ paddingLeft: (depth - 1) * 20 + 'px' }"
      @click="onRowClick"
    >
      <span v-if="!isLeaf" :class="['tp-arrow', expanded ? 'tp-arrow-open' : '']">▶</span>
      <span v-else class="tp-arrow tp-arrow-placeholder" />
      <input
        type="checkbox"
        class="tp-check"
        :checked="isFullySelected"
        :indeterminate.prop="isPartiallySelected"
        @click.stop
        @change="onCheckboxChange"
      />
      <span class="tp-dot" :style="{ background: dotColor }" />
      <span :class="['tp-name', isLeaf ? 'tp-name-leaf' : 'tp-name-group']">{{ node.name }}</span>
      <span v-if="!isLeaf" class="tp-count">({{ leafCount }})</span>
    </div>
    <template v-if="!isLeaf && expanded && node.children">
      <TreeNodePicker
        v-for="child in node.children"
        :key="child._id || child.elementId || child.name"
        :node="child"
        :depth="depth + 1"
        :expand-all="expandAll"
        :selected-ids="selectedIds"
        :leaf-count-map="leafCountMap"
        @toggle="(n) => $emit('toggle', n)"
        @select="(n, checked) => $emit('select', n, checked)"
      />
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  node: { type: Object, required: true },
  depth: { type: Number, default: 1 },
  expandAll: { type: Boolean, default: false },
  selectedIds: { type: Set, default: () => new Set() },
  leafCountMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['toggle', 'select'])

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316']

const expanded = ref(false)
const isLeaf = computed(() => !props.node.children || !props.node.children.length)
const leafCount = computed(() => props.leafCountMap?.[props.node.name] || 0)
const dotColor = computed(() => COLORS[(props.depth - 1) % COLORS.length])

function getNodeId(n) {
  return n._id || n.elementId || ''
}

const isFullySelected = computed(() => {
  if (isLeaf.value) return props.selectedIds.has(getNodeId(props.node))
  if (!props.node.children) return false
  return props.node.children.every(c => isNodeFullySelected(c))
})

const isPartiallySelected = computed(() => {
  if (isLeaf.value || isFullySelected.value || !props.node.children) return false
  return props.node.children.some(c => isNodePartiallyOrFullySelected(c))
})

function isNodeFullySelected(n) {
  const nid = getNodeId(n)
  if (!n.children || !n.children.length) return nid && props.selectedIds.has(nid)
  return n.children.every(c => isNodeFullySelected(c))
}

function isNodePartiallyOrFullySelected(n) {
  const nid = getNodeId(n)
  if (!n.children || !n.children.length) return nid && props.selectedIds.has(nid)
  return n.children.some(c => isNodePartiallyOrFullySelected(c))
}

watch(() => props.expandAll, v => { expanded.value = v })

function onRowClick() {
  if (!isLeaf.value) expanded.value = !expanded.value
}

function onCheckboxChange(e) {
  emit('select', props.node, e.target.checked)
}
</script>

<style scoped>
.tp-node { user-select: none; }
.tp-row { display: flex; align-items: center; gap: 4px; padding: 3px 6px; border-radius: 4px; cursor: pointer; transition: background 0.1s; }
.tp-row:hover { background: rgba(59,130,246,0.05); }
.tp-arrow { font-size: 10px; color: #94a3b8; width: 12px; text-align: center; flex-shrink: 0; transition: transform 0.15s; }
.tp-arrow-open { transform: rotate(90deg); }
.tp-arrow-placeholder { width: 12px; flex-shrink: 0; }
.tp-check { flex-shrink: 0; accent-color: #3b82f6; cursor: pointer; margin: 0; }
.tp-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.tp-name { font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tp-name-group { font-weight: 600; color: #1e293b; }
.tp-name-leaf { color: #475569; }
.tp-count { font-size: 10px; color: #94a3b8; }
</style>
