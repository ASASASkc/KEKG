<template>
  <div class="page-wrapper">
    <div class="page-card">
      <h2 class="page-title">操作审计日志</h2>
      <p class="page-subtitle">按模块、操作、结果和时间范围筛选审计记录</p>

      <!-- 筛选 -->
      <div class="filter-bar">
        <input v-model="filter.module" placeholder="模块" class="input" @keyup.enter="search" />
        <input v-model="filter.action" placeholder="操作" class="input" @keyup.enter="search" />
        <input v-model="filter.result" placeholder="结果（success/fail）" class="input" @keyup.enter="search" />
        <input type="date" v-model="filter.date_from" class="input date-input" />
        <span class="date-sep">至</span>
        <input type="date" v-model="filter.date_to" class="input date-input" />
        <button class="btn btn-primary" @click="search">搜索</button>
        <button class="btn btn-ghost" @click="resetFilter">重置</button>
      </div>

      <!-- 列表 -->
      <div class="table-wrap" v-if="items.length">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width:60px">ID</th>
              <th style="width:150px">时间</th>
              <th style="width:90px">模块</th>
              <th style="width:90px">操作</th>
              <th>详情</th>
              <th style="width:80px">结果</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in items" :key="row.id">
              <td>{{ row.id }}</td>
              <td class="td-time">{{ row.created_at }}</td>
              <td>{{ row.module }}</td>
              <td><span class="action-tag">{{ row.action }}</span></td>
              <td class="td-detail">{{ row.detail }}</td>
              <td>
                <span class="result-tag" :class="row.result === 'fail' ? 'result-fail' : 'result-ok'">
                  {{ row.result === 'fail' ? '失败' : '成功' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="td-center td-empty">暂无审计日志记录</div>

      <!-- 分页 -->
      <div class="pager" v-if="pagination && pagination.total_pages > 1">
        <button class="btn btn-sm btn-ghost" :disabled="pagination.page <= 1" @click="goPage(pagination.page - 1)">上一页</button>
        <span class="page-info">第 {{ pagination.page }} / {{ pagination.total_pages }} 页（共 {{ pagination.total }} 条）</span>
        <button class="btn btn-sm btn-ghost" :disabled="pagination.page >= pagination.total_pages" @click="goPage(pagination.page + 1)">下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api'

const items = ref([])
const pagination = ref(null)

const filter = reactive({
  module: '',
  action: '',
  result: '',
  date_from: '',
  date_to: ''
})

async function loadPage(page = 1) {
  try {
    const params = { page, page_size: 20 }
    for (const k of ['module', 'action', 'result', 'date_from', 'date_to']) {
      if (filter[k]) params[k] = filter[k]
    }
    const r = await api.get('/logs/operations', { params })
    if (r.success) {
      items.value = r.data?.items || []
      pagination.value = r.data || null
    }
  } catch {
    items.value = []
  }
}

function search() { loadPage(1) }
function resetFilter() {
  Object.assign(filter, { module: '', action: '', result: '', date_from: '', date_to: '' })
  loadPage(1)
}
function goPage(p) { loadPage(p) }

onMounted(() => loadPage())
</script>

<style scoped>
.page-wrapper { padding: 32px 48px; max-width: 1200px; margin: 0 auto; }
.page-title { font-size: 19px; color: var(--text-white); margin-bottom: 4px; }
.page-subtitle { font-size: 11px; color: var(--text-light); margin-bottom: 24px; }

.filter-bar {
  display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
  margin-bottom: 20px;
}
.input {
  background: var(--bg-primary); border: 1px solid var(--border-color); color: var(--text-primary);
  padding: 7px 12px; border-radius: var(--radius-sm); font-size: 11px;
}
.date-input { width: 140px; }
.date-sep { color: var(--text-light); font-size: 11px; }

.table-wrap { overflow-x: auto; }
.data-table {
  width: 100%; border-collapse: collapse; font-size: 11px;
}
.data-table th {
  text-align: left; padding: 10px 12px;
  background: var(--bg-sub); color: var(--text-light);
  border-bottom: 1px solid var(--border); font-weight: 600;
}
.data-table td {
  padding: 10px 12px; border-bottom: 1px solid var(--border-color);
  color: var(--text-primary);
}
.td-center { text-align: center; color: var(--text-light); padding: 40px 0; }
.td-empty { font-size: 12px; }
.td-detail { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-time { color: var(--text-light); font-size: 11px; white-space: nowrap; }

.action-tag {
  background: rgba(59,130,246,0.15); color: var(--accent-blue);
  padding: 2px 8px; border-radius: 4px; font-size: 11px;
}
.result-tag { padding: 2px 8px; border-radius: 4px; font-size: 11px; }
.result-ok { background: rgba(16,185,129,0.15); color: #10b981; }
.result-fail { background: rgba(239,68,68,0.15); color: #ef4444; }

.pager {
  display: flex; justify-content: center; align-items: center;
  margin-top: 24px; gap: 16px;
}
.page-info { color: var(--text-light); font-size: 11px; }
</style>
