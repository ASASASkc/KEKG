<template>
  <div class="page-wrapper">
    <div class="page-card">
      <h2 class="page-title">操作日志</h2>
      <p class="page-subtitle">
        记录所有关键操作，仅管理员可查看 |
        <router-link to="/audit-log" class="audit-link">操作审计日志 →</router-link>
      </p>

      <!-- 过滤器 -->
      <div class="filter-bar">
        <input v-model="filter.keyword" class="input" placeholder="搜索关键词..."
          @keyup.enter="doSearch" />
        <select v-model="filter.action" class="input select-sm">
          <option value="">全部操作类型</option>
          <option v-for="a in actions" :key="a" :value="a">{{ a }}</option>
        </select>
        <select v-model="filter.module" class="input select-sm">
          <option value="">全部模块</option>
          <option v-for="m in modules" :key="m" :value="m">{{ m }}</option>
        </select>
        <select v-model="filter.result" class="input select-sm">
          <option value="">全部结果</option>
          <option value="success">成功</option>
          <option value="fail">失败</option>
        </select>
        <input v-model="filter.start_date" type="date" class="input date-input" title="开始日期" />
        <span class="date-sep">至</span>
        <input v-model="filter.end_date" type="date" class="input date-input" title="结束日期" />
        <button class="btn btn-primary" @click="doSearch">查询</button>
        <button class="btn btn-ghost" @click="resetFilter">重置</button>
      </div>

      <!-- 日志表格 -->
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th style="width:60px">ID</th>
              <th style="width:90px">用户</th>
              <th style="width:90px">操作</th>
              <th style="width:80px">模块</th>
              <th>详情</th>
              <th style="width:60px">结果</th>
              <th style="width:150px">时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="7" class="td-center">加载中...</td>
            </tr>
            <tr v-else-if="logs.length === 0">
              <td colspan="7" class="td-center td-empty">暂无操作日志</td>
            </tr>
            <tr v-for="l in logs" :key="l.id">
              <td>{{ l.id }}</td>
              <td>{{ l.username || '匿名' }}</td>
              <td><span class="action-tag">{{ l.action }}</span></td>
              <td>{{ l.module }}</td>
              <td class="td-detail">{{ l.detail }}</td>
              <td>
                <span class="result-tag" :class="l.result === 'success' ? 'result-ok' : 'result-fail'">
                  {{ l.result === 'success' ? '成功' : '失败' }}
                </span>
              </td>
              <td class="td-time">{{ l.created_at }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div class="pager" v-if="totalPages > 1">
        <button class="btn btn-sm btn-ghost" :disabled="page === 1" @click="goPage(page - 1)">上一页</button>
        <span class="page-info">第 {{ page }} / {{ totalPages }} 页（共 {{ total }} 条）</span>
        <button class="btn btn-sm btn-ghost" :disabled="page === totalPages" @click="goPage(page + 1)">下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api'

const logs = ref([])
const loading = ref(false)
const page = ref(1)
const total = ref(0)
const totalPages = ref(1)
const actions = ref([])
const modules = ref([])

const filter = reactive({
  keyword: '',
  action: '',
  module: '',
  result: '',
  start_date: '',
  end_date: ''
})

async function loadActionsAndModules() {
  try {
    const [a, m] = await Promise.all([
      api.get('/logs/actions'),
      api.get('/logs/modules')
    ])
    if (a.success) actions.value = a.data
    if (m.success) modules.value = m.data
  } catch (e) { console.error('加载日志操作和模块失败:', e) }
}

async function doSearch() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: 20 }
    if (filter.keyword) params.keyword = filter.keyword
    if (filter.action) params.action = filter.action
    if (filter.module) params.module = filter.module
    if (filter.result) params.result = filter.result
    if (filter.start_date) params.start_date = filter.start_date
    if (filter.end_date) params.end_date = filter.end_date

    const r = await api.get('/logs', params)
    if (r.success) {
      logs.value = r.data?.items || []
      total.value = r.data?.total || 0
      totalPages.value = r.data?.total_pages || 1
    }
  } catch (e) {
    logs.value = []
  } finally {
    loading.value = false
  }
}

function goPage(p) {
  page.value = p
  doSearch()
}

function resetFilter() {
  filter.keyword = ''
  filter.action = ''
  filter.module = ''
  filter.result = ''
  filter.start_date = ''
  filter.end_date = ''
  page.value = 1
  doSearch()
}

onMounted(async () => {
  await loadActionsAndModules()
  await doSearch()
})
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
.select-sm { min-width: 110px; }
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

.audit-link { color: var(--accent-blue); font-size: 11px; text-decoration: none; }
.audit-link:hover { text-decoration: underline; }
</style>
