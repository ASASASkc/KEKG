<template>
  <div class="page-container">
    <div class="page-top">
      <div>
        <h1>学习资源管理</h1>
        <p class="page-subtitle">管理知识点关联的学习资源（文档、视频、链接、练习、项目案例）</p>
      </div>
      <div class="top-actions">
        <button v-if="authStore.isAdmin" class="btn btn-primary" @click="openCreate">+ 新建资源</button>
        <button v-if="authStore.isAdmin" class="btn btn-outline" @click="triggerMarkdownImport">📥 导入 Markdown</button>
        <button v-if="authStore.isAdmin" class="btn btn-sm" @click="downloadTemplate" style="margin-left:4px">📋 下载模板(.md)</button>
        <input ref="mdFileRef" type="file" accept=".md,.markdown,.txt" style="display:none" @change="doMarkdownImport" />
      </div>
    </div>

    <!-- 筛选 -->
    <div class="filter-bar">
      <select v-model="filterType" class="input input-sm" @change="doSearch">
        <option value="">全部类型</option>
        <option v-for="t in resourceTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
      </select>
      <input v-model="filterKpId" class="input input-sm" placeholder="知识点名称关键词..." @keyup.enter="doSearch" style="flex:1;min-width:160px" />
      <input v-model="filterKeyword" class="input input-sm" placeholder="搜索标题/标签..." @keyup.enter="doSearch" style="flex:1;min-width:160px" />
      <button class="btn btn-sm btn-outline" @click="doSearch">搜索</button>
      <button v-if="authStore.isAdmin && selectedIds.length" class="btn btn-sm btn-danger" @click="confirmBatchDelete">批量删除({{ selectedIds.length }})</button>
    </div>

    <!-- 导入结果 -->
    <div v-if="importResult" class="import-result">
      <div class="result-line success" v-if="importResult.success_count">成功导入 {{ importResult.success_count }} 条</div>
      <div class="result-line warn" v-if="importResult.skipped_count">跳过重复 {{ importResult.skipped_count }} 条</div>
      <div class="result-line error" v-if="importResult.error_count">失败 {{ importResult.error_count }} 条</div>
      <div v-for="e in importResult.errors" :key="e.row" class="result-line warn">第{{ e.row }}行: {{ e.message }}</div>
      <button class="btn btn-sm" @click="importResult = null" style="margin-top:4px">关闭</button>
    </div>

    <!-- 列表 -->
    <UiLoading v-if="loading" />

    <table v-else class="data-table">
      <thead>
        <tr>
          <th style="width:40px" v-if="authStore.isAdmin">
            <input type="checkbox" @change="toggleAll" :checked="allSelected" />
          </th>
          <th style="width:60px">ID</th>
          <th>标题</th>
          <th style="width:80px">类型</th>
          <th style="width:130px">关联知识点</th>
          <th style="width:80px">标签</th>
          <th style="width:100px">创建时间</th>
          <th style="width:100px" v-if="authStore.isAdmin">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in resources" :key="r.id">
          <td v-if="authStore.isAdmin">
            <input type="checkbox" :checked="selectedIds.includes(r.id)" @change="toggleSelect(r.id)" />
          </td>
          <td>{{ r.id }}</td>
          <td>
            <div class="q-title" @click="openDetail(r)" style="cursor:pointer">{{ r.title }}</div>
            <div class="q-options-preview" v-if="r.url">
              <a :href="r.url" target="_blank" style="color:#3b82f6;font-size: 11px">{{ r.url }}</a>
            </div>
          </td>
          <td><span class="type-tag" :class="'res-' + r.type">{{ typeLabel(r.type) }}</span></td>
          <td><span class="topic-tag">{{ r.knowledge_point_id }}</span></td>
          <td><span class="tags-text">{{ r.tags || '-' }}</span></td>
          <td><span class="date-text">{{ formatDate(r.created_at) }}</span></td>
          <td v-if="authStore.isAdmin">
            <div class="action-btns">
              <button class="btn btn-xs btn-outline" @click="openEdit(r)">编辑</button>
              <button class="btn btn-xs btn-danger" @click="confirmDelete(r.id)">删除</button>
            </div>
          </td>
        </tr>
        <tr v-if="resources.length === 0">
          <td :colspan="authStore.isAdmin ? 9 : 7" style="text-align:center;color:#64748b;padding:32px">暂无资源，点击"新建资源"添加</td>
        </tr>
      </tbody>
    </table>

    <!-- 分页 -->
    <div class="page-bar" v-if="totalPages > 1">
      <button class="btn btn-sm btn-outline" :disabled="page <= 1" @click="page--; doSearch()">上一页</button>
      <span class="page-info">{{ page }} / {{ totalPages }}</span>
      <button class="btn btn-sm btn-outline" :disabled="page >= totalPages" @click="page++; doSearch()">下一页</button>
    </div>

    <!-- ── 创建/编辑弹窗 ── -->
    <div class="modal-overlay" v-if="formVisible" @click.self="formVisible = false">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingId ? '编辑资源' : '新建资源' }}</h3>
          <button class="btn-close" @click="formVisible = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>标题 <span class="required">*</span></label>
            <input v-model="form.title" class="input" placeholder="资源标题" />
          </div>
          <div class="form-row">
            <div class="form-group" style="flex:1">
              <label>类型 <span class="required">*</span></label>
              <select v-model="form.type" class="input">
                <option v-for="t in resourceTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
              </select>
            </div>

          </div>
          <div class="form-group">
            <label>关联知识点 <span class="required">*</span></label>
            <input v-model="form.knowledge_point_id" class="input" list="kp-list" placeholder="输入 Neo4j 知识点名称" />
            <datalist id="kp-list">
              <option v-for="k in knowledgePoints" :key="k.name" :value="k.name">{{ k.name }}</option>
            </datalist>
          </div>
          <div class="form-group">
            <label>外部链接</label>
            <input v-model="form.url" class="input" placeholder="URL（视频、文档链接等）" />
          </div>
          <div class="form-group">
            <label>文本内容</label>
            <textarea v-model="form.content" class="input" rows="3" placeholder="文本描述内容（无链接时使用）" style="resize:vertical"></textarea>
          </div>
          <div class="form-group">
            <label>标签</label>
            <input v-model="form.tags" class="input" placeholder="逗号分隔，如：入门,必看" />
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="formVisible = false">取消</button>
          <button class="btn btn-primary" @click="submitForm" :disabled="submitting">
            {{ submitting ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── 详情弹窗 ── -->
    <div class="modal-overlay" v-if="detail" @click.self="detail = null">
      <div class="modal" style="max-width:600px">
        <div class="modal-header">
          <h3>{{ detail.title }}</h3>
          <button class="btn-close" @click="detail = null">×</button>
        </div>
        <div class="modal-body">
          <div class="detail-row"><strong>类型：</strong><span class="type-tag" :class="'res-' + detail.type">{{ typeLabel(detail.type) }}</span></div>
          <div class="detail-row"><strong>关联知识点：</strong><span class="topic-tag">{{ detail.knowledge_point_id }}</span></div>

          <div class="detail-row"><strong>标签：</strong>{{ detail.tags || '无' }}</div>
          <div class="detail-row" v-if="detail.url"><strong>链接：</strong><a :href="detail.url" target="_blank" style="color:#3b82f6">{{ detail.url }}</a></div>
          <div class="detail-row" v-if="detail.content"><strong>内容：</strong></div>
          <div class="detail-content" v-if="detail.content">{{ detail.content }}</div>
          <div class="detail-row"><strong>创建时间：</strong>{{ formatDate(detail.created_at) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { authStore } from '../stores/auth'
import api from '../api'
import { useFeedback } from '../composables/useFeedback'

const { tip, ask } = useFeedback()

const resources = ref([])
const resourceTypes = ref([
  { value: 'doc', label: '文档' },
  { value: 'video', label: '视频' },
  { value: 'link', label: '链接' },
  { value: 'exercise', label: '练习' },
  { value: 'project', label: '项目' }
])
const knowledgePoints = ref([])
const loading = ref(false)
const filterType = ref('')
const filterKpId = ref('')
const filterKeyword = ref('')
const page = ref(1)
const totalPages = ref(1)
const selectedIds = ref([])

const formVisible = ref(false)
const editingId = ref(null)
const submitting = ref(false)
const form = ref({ title: '', type: 'doc', knowledge_point_id: '', url: '', content: '', tags: '' })

const detail = ref(null)

const allSelected = computed(() => {
  return resources.value.length > 0 && resources.value.every(r => selectedIds.value.includes(r.id))
})

function typeLabel(t) {
  const m = { doc: '文档', video: '视频', link: '链接', exercise: '练习', project: '项目' }
  return m[t] || t
}

function formatDate(t) {
  if (!t) return '-'
  return t.replace('T', ' ').substring(0, 16)
}

async function fetchKnowledgePoints() {
  try {
    const { data } = await api.get('/graph/nodes')
    knowledgePoints.value = data.data?.items || data.data || []
  } catch { /* ignore */ }
}

async function doSearch() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: 50 }
    if (filterType.value) params.type = filterType.value
    if (filterKpId.value) params.knowledge_point_id = filterKpId.value
    if (filterKeyword.value) params.keyword = filterKeyword.value
    const { data } = await api.get('/resources', { params })
    resources.value = data.items
    totalPages.value = data.total_pages
  } catch (e) {
    console.error('加载资源失败:', e)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.value = { title: '', type: 'doc', knowledge_point_id: '', url: '', content: '', tags: '' }
  formVisible.value = true
}

async function openEdit(r) {
  const { data } = await api.get(`/resources/${r.id}`)
  const item = data.data
  editingId.value = r.id
  form.value = { ...item }
  formVisible.value = true
}

async function submitForm() {
  submitting.value = true
  try {
    if (editingId.value) {
      await api.put(`/resources/${editingId.value}`, form.value)
    } else {
      await api.post('/resources', form.value)
    }
    formVisible.value = false
    doSearch()
  } catch (e) {
    tip(e.response?.data?.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

function confirmDelete(id) {
  ask('确认删除？', async () => {
    await api.delete(`/resources/${id}`)
    selectedIds.value = selectedIds.value.filter(i => i !== id)
    doSearch()
  })
}

function confirmBatchDelete() {
  ask(`确认删除选中的 ${selectedIds.value.length} 个资源？`, async () => {
    await api.post('/resources/batch-delete', { ids: selectedIds.value })
    selectedIds.value = []
    doSearch()
  })
}

function toggleAll(e) {
  selectedIds.value = e.target.checked ? resources.value.map(r => r.id) : []
}

function toggleSelect(id) {
  const idx = selectedIds.value.indexOf(id)
  if (idx > -1) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

async function openDetail(r) {
  const { data } = await api.get(`/resources/${r.id}`)
  detail.value = data.data
}

// ── 导入 ──
const mdFileRef = ref(null)
const importResult = ref(null)

function triggerMarkdownImport() { mdFileRef.value?.click() }

async function doMarkdownImport(e) {
  const file = e.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  try {
    const { data } = await api.post('/resources/import/markdown', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    importResult.value = data
    if (data.success_count > 0) doSearch()
  } catch (err) {
    importResult.value = { error_count: 1, errors: [{ row: 0, message: err.response?.data?.message || err.message }] }
  }
  e.target.value = ''
}

// ── 下载模板 ──
function downloadTemplate() {
  api.get('/resources/export/template-markdown', { responseType: 'blob' }).then(res => {
    const blob = res instanceof Blob ? res : new Blob([res])
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '学习资源导入模板.md'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  }).catch(err => {
    console.error('下载模板失败:', err)
    tip('下载模板失败: ' + (err.message || '未知错误'))
  })
}

onMounted(() => {
  fetchKnowledgePoints()
  doSearch()
})
</script>

<style scoped>
/* 复用现有样式 */
.res-doc  { background: #dbeafe; color: #1e40af; }
.res-video { background: #fce7f3; color: #9d174d; }
.res-link { background: #d1fae5; color: #065f46; }
.res-exercise { background: #fef3c7; color: #92400e; }
.res-project { background: #ede9fe; color: #5b21b6; }

.topic-tag {
  display: inline-block;
  background: #e0e7ff;
  color: #4338ca;
  padding: 2px 8px;
  border-radius: 11px;
  font-size: 11px;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tags-text { font-size: 11px; color: var(--text-secondary); }

.date-text { color: #94a3b8; font-size: 11px; }

.detail-row { margin-bottom: 10px; }
.detail-row strong { color: #475569; }
.detail-content {
  background: #f1f5f9;
  padding: 10px;
  border-radius: 6px;
  white-space: pre-wrap;
  font-size: 11px;
  margin-bottom: 10px;
}

.action-btns { display: flex; gap: 4px; }

.required { color: #ef4444; }
</style>
