<template>
  <div class="page-container">
    <h1 class="page-title">知识点管理</h1>
    <p class="page-subtitle">浏览和管理知识图谱中的知识点</p>

    <div class="toolbar">
      <div class="toolbar-row">
        <div class="search-wrapper">
          <input v-model="searchKw" class="input search-box" placeholder="搜索知识点..."
            @input="onSearchInput"
            @keyup.enter="doSearch"
            @focus="searchKw.trim().length >= 1 && searchSuggestions.length && (showSuggestions = true)"
            @blur="onBlur" />
          <div v-if="showSuggestions && searchSuggestions.length" class="search-dropdown">
            <div
              v-for="item in searchSuggestions"
              :key="item.id"
              class="search-dropdown-item"
              @mousedown.prevent="goResult(item)"
            >
              <span class="sr-name">{{ item.properties?.name }}</span>
              <span class="sr-cat">{{ item.properties?.category || '未分类' }}</span>
            </div>
          </div>
        </div>
        <span class="result-count" v-if="pagination.total">
          共 {{ pagination.total }} 个知识点
        </span>
        <button v-if="authStore.isAdmin" class="btn btn-sm btn-primary" @click="showCreate = true" style="margin-left: auto">+ 新建</button>
      </div>
    </div>

    <!-- 列表模式 -->
    <div class="kp-list" v-if="items.length">
      <div v-for="item in items" :key="item.id" class="kp-row card">
        <span class="kp-dot" :class="getCatClass(item.properties?.category)"></span>
        <div class="kp-info">
          <span class="kp-name">{{ item.properties?.name }}</span>
          <span class="kp-desc-trunc">{{ truncate(item.properties?.description, 60) }}</span>
        </div>
        <span class="tag" :class="getCatClass(item.properties?.category)">{{ item.properties?.category || '-' }}</span>
        <div class="kp-actions">
          <router-link :to="`/graph/${item.id}`" class="btn btn-sm btn-secondary">图谱</router-link>
          <button v-if="authStore.isAdmin" class="btn btn-sm btn-secondary" @click="doDelete(item.id)">删除</button>
        </div>
      </div>
    </div>
    <UiEmpty v-else text="暂无知识点数据" />

    <!-- 分页 -->
    <div class="pagination" v-if="pagination.total_pages > 1">
      <button class="btn btn-sm btn-secondary" :disabled="pagination.page <= 1" @click="goPage(pagination.page - 1)">上一页</button>
      <span class="page-info">{{ pagination.page }} / {{ pagination.total_pages }}</span>
      <button class="btn btn-sm btn-secondary" :disabled="pagination.page >= pagination.total_pages" @click="goPage(pagination.page + 1)">下一页</button>
    </div>

    <!-- 创建模态 -->
    <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
      <div class="modal card">
        <h2>新建知识点</h2>
        <form @submit.prevent="doCreate">
          <input v-model="form.name" class="input" placeholder="名称 *" required />
          <select v-model="form.category" class="input" style="margin-top:12px">
            <option value="">分类</option>
            <option>基础</option><option>核心</option><option>进阶</option>
            <option>数据结构</option><option>数据科学</option>
          </select>
          <textarea v-model="form.description" class="input" style="margin-top:12px" placeholder="描述" rows="3"></textarea>
          <div class="modal-actions">
            <button type="button" class="btn btn-sm btn-secondary" @click="showCreate = false">取消</button>
            <button type="submit" class="btn btn-sm btn-primary">创建</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { authStore } from '../stores/auth'
import { useFeedback } from '../composables/useFeedback'

const { tip, ask } = useFeedback()

const route = useRoute()
const router = useRouter()
const items = ref([])
const searchKw = ref('')
const searchSuggestions = ref([])
const showSuggestions = ref(false)
const showCreate = ref(false)
const form = ref({ name: '', category: '', description: '' })
const pagination = ref({ page: 1, page_size: 30, total: 0, total_pages: 1 })
let searchTimer = null
let searchSeq = 0

const currentLabel = computed(() => route.query.label || '')

function getCatClass(c) {
  const m = { '基础': 'cat-basic', '核心': 'cat-core', '进阶': 'cat-advanced',
    '数据结构': 'cat-structure', '数据科学': 'cat-data' }
  return m[c] || ''
}

function truncate(t, n) {
  if (!t) return ''
  return t.length > n ? t.slice(0, n) + '...' : t
}

onMounted(async () => {
  await loadPage(1)
})

// 当导航栏切换拓展时自动刷新
watch(() => route.query.label, () => {
  searchKw.value = ''
  loadPage(1)
})

async function loadPage(page) {
  try {
    const label = currentLabel.value ? `&label=${encodeURIComponent(currentLabel.value)}` : ''
    const r = await api.get(`/knowledge-points?page=${page}&page_size=30${label}`)
    if (r.success) {
      items.value = r.data.items || []
      pagination.value = {
        page: r.data.page,
        page_size: r.data.page_size,
        total: r.data.total,
        total_pages: r.data.total_pages
      }
    }
  } catch (e) { console.error('加载知识点列表失败:', e); tip('知识点列表加载失败，请稍后重试') }
}

function goPage(p) {
  pagination.value.page = p
  loadPage(p)
}

function onSearchInput() {
  clearTimeout(searchTimer)
  const kw = searchKw.value.trim()
  if (kw.length < 1) {
    searchSuggestions.value = []
    showSuggestions.value = false
    loadPage(1)
    return
  }
  // 拉取下拉建议
  searchTimer = setTimeout(async () => {
    const seq = ++searchSeq
    try {
      const label = currentLabel.value ? `&label=${encodeURIComponent(currentLabel.value)}` : ''
      const r = await api.get(`/knowledge-points/search?keyword=${encodeURIComponent(kw)}${label}`)
      if (seq !== searchSeq) return
      if (r.success) {
        searchSuggestions.value = (r.data || []).slice(0, 8)
        showSuggestions.value = searchSuggestions.value.length > 0
      }
    } catch (e) { /* ignore */ }
  }, 300)
}

function onBlur() {
  setTimeout(() => { showSuggestions.value = false }, 200)
}

function goResult(item) {
  showSuggestions.value = false
  searchSuggestions.value = []
  router.push({ path: '/graph', query: { nodeId: item.id } })
}

async function doSearch() {
  const kw = searchKw.value.trim()
  if (kw) {
    const label = currentLabel.value ? `&label=${encodeURIComponent(currentLabel.value)}` : ''
    const r = await api.get(`/knowledge-points/search?keyword=${encodeURIComponent(kw)}${label}`)
    if (r.success) {
      items.value = r.data
      pagination.value = { page: 1, page_size: r.data.length, total: r.data.length, total_pages: 1 }
    }
  } else {
    await loadPage(1)
  }
}

async function doCreate() {
  if (!form.value.name) return
  try {
    const r = await api.post('/knowledge-points', {
      name: form.value.name,
      category: form.value.category,
      description: form.value.description
    })
    if (r.success) {
      showCreate.value = false
      form.value = { name: '', category: '', description: '' }
      await loadPage(1)
    }
  } catch (e) { console.error('创建知识点失败:', e); tip('操作失败，请重试') }
}

function doDelete(id) {
  ask('确定删除？将同时删除关联关系', async () => {
    try {
      await api.delete(`/knowledge-points/${id}`)
      items.value = items.value.filter(i => i.id !== id)
    } catch (e) { console.error('删除知识点失败:', e); tip('操作失败，请重试') }
  })
}
</script>

<style scoped>
.page-container { max-width: 900px; margin: 0 auto; padding: 32px 24px; }
.page-title { font-size: 25px; font-weight: 700; margin-bottom: 6px; }
.page-subtitle { color: var(--text-secondary); margin-bottom: 24px; }

.toolbar { margin-bottom: 16px; }
.toolbar-row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.search-wrapper { flex: 1; min-width: 200px; max-width: 360px; position: relative; }
.search-box { width: 100%; box-sizing: border-box; }
.result-count { font-size: 11px; color: var(--text-light); white-space: nowrap; }

/* 搜索下拉 */
.search-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 4px;
  max-height: 260px;
  overflow-y: auto;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
  z-index: 100;
}
.search-dropdown-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 9px 14px;
  font-size: 11px;
  cursor: pointer;
  transition: background 0.12s;
}
.search-dropdown-item:hover { background: var(--bg-secondary); }
.sr-name { color: var(--text-primary); font-weight: 500; }
.sr-cat {
  font-size: 10px;
  color: var(--text-light);
  background: var(--bg-tertiary);
  padding: 2px 8px;
  border-radius: 10px;
  flex-shrink: 0;
  margin-left: 8px;
}

/* 列表 */
.kp-list { display: flex; flex-direction: column; gap: 6px; margin-bottom: 20px; }
.kp-row {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px; transition: background 0.15s;
}
.kp-row:hover { background: var(--bg-secondary); }
.kp-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.cat-basic { background: #3b82f6; }
.cat-core { background: #8b5cf6; }
.cat-advanced { background: #10b981; }
.cat-structure { background: #06b6d4; }
.cat-data { background: #f59e0b; }

.kp-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.kp-name { font-weight: 600; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.kp-desc-trunc { font-size: 11px; color: var(--text-light); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }


.kp-actions { display: flex; gap: 6px; flex-shrink: 0; }

.tag { padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 500; white-space: nowrap; }
.cat-basic.tag { background: #dbeafe; color: #1d4ed8; }
.cat-core.tag { background: #ede9fe; color: #6d28d9; }
.cat-advanced.tag { background: #d1fae5; color: #047857; }
.cat-structure.tag { background: #cffafe; color: #0e7490; }
.cat-data.tag { background: #fef3c7; color: #b45309; }

.empty { text-align: center; padding: 60px; color: var(--text-light); }

/* 分页 */
.pagination { display: flex; justify-content: center; align-items: center; gap: 16px; }
.page-info { font-size: 12px; color: var(--text-secondary); }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 200; }
.modal { width: 460px; max-height: 80vh; overflow-y: auto; }
.modal h2 { margin-bottom: 20px; font-size: 18px; }
.modal-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
</style>
