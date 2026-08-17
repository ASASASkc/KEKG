<template>
  <div v-if="totalPages > 1" class="ui-pagination">
    <span v-if="showTotal" class="ui-pagination-total">共 {{ total }} 条</span>
    <div class="ui-pagination-pages">
      <button class="ui-page-btn" :disabled="page <= 1" @click="go(page - 1)">&lsaquo;</button>
      <template v-for="p in pageList" :key="p">
        <button
          v-if="p !== '...'"
          class="ui-page-btn"
          :class="{ 'ui-page-active': p === page }"
          @click="go(p)"
        >{{ p }}</button>
        <span v-else class="ui-page-ellipsis">...</span>
      </template>
      <button class="ui-page-btn" :disabled="page >= totalPages" @click="go(page + 1)">&rsaquo;</button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  page: { type: Number, default: 1 },
  total: { type: Number, default: 0 },
  pageSize: { type: Number, default: 10 },
  showTotal: { type: Boolean, default: true },
})

const emit = defineEmits(['update:page', 'change'])

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

// 页码列表：最多显示 7 个，带省略号
const pageList = computed(() => {
  const tp = totalPages.value
  const cur = props.page
  const pages = []
  if (tp <= 7) {
    for (let i = 1; i <= tp; i++) pages.push(i)
    return pages
  }
  const range = new Set([1, tp, cur - 1, cur, cur + 1])
  let prev = 0
  for (const p of [...range].filter(p => p >= 1 && p <= tp).sort((a, b) => a - b)) {
    if (prev && p - prev > 1) pages.push('...')
    pages.push(p)
    prev = p
  }
  return pages
})

function go(p) {
  if (p < 1 || p > totalPages.value || p === props.page) return
  emit('update:page', p)
  emit('change', p)
}
</script>

<style scoped>
.ui-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 0;
  flex-wrap: wrap;
}
.ui-pagination-total { font-size: 11px; color: var(--text-light); }
.ui-pagination-pages { display: flex; align-items: center; gap: 4px; }
.ui-page-btn {
  min-width: 30px;
  height: 30px;
  padding: 0 8px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-primary);
  color: var(--text-secondary);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}
.ui-page-btn:hover:not(:disabled):not(.ui-page-active) { border-color: var(--accent-blue); color: var(--accent-blue); }
.ui-page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.ui-page-active { background: var(--accent-blue); border-color: var(--accent-blue); color: #fff; }
.ui-page-ellipsis { padding: 0 4px; color: var(--text-light); font-size: 11px; }
</style>
