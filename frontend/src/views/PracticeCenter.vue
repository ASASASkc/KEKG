<template>
  <div class="page-container">
    <div class="page-top">
      <h1>题库练习</h1>
      <p class="page-subtitle">按知识点刷题，逐步巩固（数据来自系统题库）</p>
      <router-link to="/practice/history" class="btn btn-sm btn-outline hist-link">📜 我的提交记录</router-link>
    </div>

    <!-- 统计条 -->
    <div class="stats-bar">
      <div class="stat-item"><span class="stat-num">{{ stats.total }}</span><span class="stat-label">总题数</span></div>
      <div class="stat-item"><span class="stat-num stat-blue">{{ stats.done }}</span><span class="stat-label">已做</span></div>
      <div class="stat-item"><span class="stat-num stat-green">{{ stats.correct }}</span><span class="stat-label">答对</span></div>
      <div class="stat-item"><span class="stat-num stat-red">{{ stats.wrong }}</span><span class="stat-label">答错</span></div>
      <div class="stat-item">
        <span class="stat-num" :class="stats.done > 0 ? 'stat-blue' : ''">{{ stats.done > 0 ? Math.round(stats.correct / stats.done * 100) + '%' : '-' }}</span>
        <span class="stat-label">正确率</span>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <select v-model="filterType" class="input input-sm" @change="doSearch">
        <option value="">全部题型</option>
        <option value="choice">选择题</option>
        <option value="judge">判断题</option>
        <option value="fill">填空题</option>
        <option value="subjective">主观题</option>
      </select>
      <select v-model="filterDifficulty" class="input input-sm" @change="doSearch">
        <option value="">全部难度</option>
        <option v-for="s in 4" :key="s" :value="s">{{ '★'.repeat(s) }}</option>
      </select>
      <select v-model="filterStatus" class="input input-sm" @change="doSearch">
        <option value="">我的状态</option>
        <option value="undone">未做</option>
        <option value="done">已做</option>
        <option value="wrong">做错</option>
      </select>
      <select v-model="filterSort" class="input input-sm" @change="doSearch">
        <option value="">默认排序</option>
        <option value="rate_desc">通过率 ↓</option>
        <option value="rate_asc">通过率 ↑</option>
        <option value="diff_desc">难度 ↓</option>
        <option value="diff_asc">难度 ↑</option>
      </select>
      <div class="search-box">
        <input v-model="filterKeyword" class="input input-sm" placeholder="搜索题目关键词..." @keyup.enter="doSearch" />
        <button class="btn btn-outline btn-sm" @click="doSearch">搜索</button>
      </div>
      <button class="btn btn-sm" :class="favOnly ? 'btn-primary' : 'btn-outline'" @click="toggleFavOnly">★ 只看收藏</button>
    </div>

    <UiLoading v-if="loading" />

    <template v-else>
      <!-- 题目列表 -->
      <div v-if="questions.length" class="q-list">
        <router-link v-for="q in questions" :key="q.id" :to="`/practice/${q.id}`" class="q-row">
          <div class="q-left">
            <span class="type-tag" :class="'type-' + q.type">{{ typeLabel(q.type) }}</span>
            <span class="q-title">{{ q.title }}</span>
          </div>
          <div class="q-right">
            <span class="fav-star" :class="{ active: q.is_favorite }" title="收藏" @click.stop="toggleFavorite(q)">★</span>
            <span class="star-rating" :class="'star-' + starLevel(q.difficulty)">{{ starText(q.difficulty) }}</span>
            <span class="my-status" :class="'my-' + q.my_status">{{ statusText(q.my_status) }}</span>
          </div>
        </router-link>
      </div>
      <UiEmpty v-else text="暂无匹配题目，换个筛选条件试试" />

      <!-- 分页 -->
      <div class="pagination" v-if="totalPages > 1">
        <button class="btn btn-xs btn-outline" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <span class="page-info">{{ page }} / {{ totalPages }}</span>
        <button class="btn btn-xs btn-outline" :disabled="page >= totalPages" @click="goPage(page + 1)">下一页</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const loading = ref(true)
const questions = ref([])
const page = ref(1)
const pageSize = 20
const totalPages = ref(1)
const stats = ref({ total: 0, done: 0, correct: 0, wrong: 0 })

const filterType = ref('')
const filterDifficulty = ref('')
const filterStatus = ref('')
const filterSort = ref('')
const filterKeyword = ref('')
const favOnly = ref(false)

const TYPE_MAP = { choice: '选择题', judge: '判断题', fill: '填空题', subjective: '主观题' }
function typeLabel(t) { return TYPE_MAP[t] || t }

function starLevel(d) {
  if (!d) return 0
  return Math.min(4, Math.max(1, Math.ceil(Number(d) / 3)))
}
function starText(d) {
  const lv = starLevel(d)
  return lv ? '★'.repeat(lv) : '-'
}
function statusText(s) {
  return { undone: '未做', done: '已做', wrong: '做错' }[s] || ''
}

onMounted(doSearch)

async function doSearch() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize }
    if (filterType.value) params.type = filterType.value
    if (filterDifficulty.value) {
      const s = Number(filterDifficulty.value)
      params.difficulty_min = (s - 1) * 3 + 1
      params.difficulty_max = s * 3
    }
    if (filterStatus.value) params.status = filterStatus.value
    if (filterSort.value) params.sort = filterSort.value
    if (filterKeyword.value) params.keyword = filterKeyword.value
    if (favOnly.value) params.favorites = 1
    const r = await api.get('/practice/questions', { params })
    if (r.success) {
      questions.value = r.data.items || []
      totalPages.value = r.data.total_pages || 1
      stats.value = r.data.stats || stats.value
    }
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

function goPage(p) {
  page.value = p
  doSearch()
}

function toggleFavOnly() {
  favOnly.value = !favOnly.value
  page.value = 1
  doSearch()
}

async function toggleFavorite(q) {
  try {
    if (q.is_favorite) {
      await api.delete(`/questions/${q.id}/favorite`)
    } else {
      await api.put(`/questions/${q.id}/favorite`)
    }
    q.is_favorite = !q.is_favorite
  } catch (e) { console.error(e) }
}
</script>

<style scoped>
.page-container { max-width: 900px; margin: 0 auto; padding: 32px 24px; }
.page-top h1 { font-size: 22px; margin: 0; }
.page-subtitle { font-size: 13px; color: var(--text-secondary); margin: 4px 0 16px; }
.hist-link { float: right; margin-top: -40px; text-decoration: none; }

/* 统计条 */
.stats-bar {
  display: flex; gap: 12px; margin-bottom: 16px;
  background: #fff; border-radius: 10px; padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.stat-item { flex: 1; text-align: center; }
.stat-num { display: block; font-size: 20px; font-weight: 700; color: #1e293b; }
.stat-blue { color: #3b82f6; }
.stat-green { color: #10b981; }
.stat-red { color: #ef4444; }
.stat-label { font-size: 11px; color: var(--text-secondary); }

/* 筛选栏 */
.filter-bar { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; align-items: center; }
.search-box { display: flex; gap: 6px; flex: 1; min-width: 200px; }
.search-box .input { flex: 1; }

/* 列表（力扣风格行） */
.q-list { background: #fff; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); overflow: hidden; }
.q-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; border-bottom: 1px solid #f1f5f9; text-decoration: none;
  transition: background 0.15s;
}
.q-row:hover { background: #f8fafc; }
.q-row:last-child { border-bottom: none; }
.q-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.q-title { font-size: 14px; color: #1e293b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.q-right { display: flex; align-items: center; gap: 14px; flex-shrink: 0; }

.type-tag { font-size: 11px; padding: 1px 7px; border-radius: 3px; font-weight: 500; flex-shrink: 0; }
.type-choice { background: #dbeafe; color: #1e40af; }
.type-judge { background: #d1fae5; color: #065f46; }
.type-fill { background: #fef3c7; color: #92400e; }
.type-subjective { background: #ede9fe; color: #5b21b6; }

.star-rating { font-size: 12px; letter-spacing: 1px; min-width: 48px; text-align: center; }
.star-1 { color: #10b981; }
.star-2 { color: #3b82f6; }
.star-3 { color: #f59e0b; }
.star-4 { color: #ef4444; }

/* 收藏星标 */
.fav-star { font-size: 15px; color: #cbd5e1; cursor: pointer; user-select: none; line-height: 1; }
.fav-star:hover { color: #f59e0b; }
.fav-star.active { color: #f59e0b; }

.my-status { font-size: 11px; padding: 2px 8px; border-radius: 4px; min-width: 44px; text-align: center; }
.my-done { background: #d1fae5; color: #065f46; }
.my-wrong { background: #fee2e2; color: #991b1b; }
.my-undone { background: #f1f5f9; color: #64748b; }

.loading-text { text-align: center; padding: 40px; color: var(--text-secondary); }
.empty-msg { text-align: center; padding: 40px; color: var(--text-light); font-size: 13px; }
.pagination { display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 16px; }
.page-info { font-size: 13px; color: var(--text-secondary); }

.input { padding: 7px 10px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px; box-sizing: border-box; }
.input-sm { width: auto; }
.input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.1); }
.btn { padding: 7px 14px; font-size: 13px; border-radius: 6px; cursor: pointer; border: 1px solid transparent; text-decoration: none; display: inline-block; }
.btn-outline { border-color: #cbd5e1; color: #334155; background: #fff; }
.btn-outline:hover { border-color: #3b82f6; color: #3b82f6; }
.btn-sm { padding: 5px 12px; font-size: 12px; }
.btn-xs { padding: 3px 10px; font-size: 11px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
