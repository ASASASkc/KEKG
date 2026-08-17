<template>
  <div class="page-container">
    <h1 class="page-title">图谱管理</h1>
    <p class="page-subtitle">创建新知识图谱、管理已有图谱、导入导出图谱数据</p>

    <!-- ── 图谱标签管理 ── -->
    <div class="card">
      <div class="card-header">
        <h2>我的图谱</h2>
        <button v-if="authStore.isAdmin" class="btn btn-primary" @click="showCreateDialog = true">+ 创建图谱</button>
      </div>
      <div v-if="labels.length === 0" class="empty-state">
        暂无自定义图谱，点击"创建图谱"开始
      </div>
      <div v-else class="label-grid">
        <div v-for="lb in labels" :key="lb.label" class="label-card">
          <div class="label-info">
            <span class="label-name">{{ lb.display_name }}</span>
            <span class="label-tag">{{ lb.label }}</span>
            <span class="label-meta" v-if="lb.description">{{ lb.description }}</span>
          </div>
          <div class="label-right">
            <span class="label-count">{{ lb.node_count }} 节点</span>
            <button v-if="authStore.isAdmin" class="btn btn-sm btn-danger" @click="confirmDelete(lb)" :disabled="deleting">
              删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 创建图谱弹窗 ── -->
    <div v-if="showCreateDialog" class="modal-overlay" @click.self="showCreateDialog = false">
      <div class="modal">
        <h3>创建新图谱</h3>
        <div class="form-group">
          <label>图谱标识（英文，用于系统内部）</label>
          <input v-model="newLabel" class="input" placeholder="例: MathKnowledge" />
        </div>
        <div class="form-group">
          <label>图谱名称（中文，用于前端显示）</label>
          <input v-model="newDisplayName" class="input" placeholder="例: 数学知识图谱" />
        </div>
        <div class="form-group">
          <label>描述（可选）</label>
          <input v-model="newDescription" class="input" placeholder="简要描述该图谱的用途" />
        </div>
        <div class="modal-actions">
          <button class="btn btn-ghost" @click="showCreateDialog = false">取消</button>
          <button class="btn btn-primary" @click="doCreateLabel" :disabled="creating">
            {{ creating ? '创建中...' : '确认创建' }}
          </button>
        </div>
        <p v-if="createError" class="error-msg">{{ createError }}</p>
      </div>
    </div>

    <!-- ── 删除确认弹窗 ── -->
    <div v-if="deleteTarget" class="modal-overlay" @click.self="deleteTarget = null">
      <div class="modal modal-sm">
        <h3>确认删除图谱</h3>
        <p>将永久删除图谱 <strong>{{ deleteTarget.display_name }}</strong> 及其所有 {{ deleteTarget.node_count }} 个节点和关联关系。此操作不可撤销。</p>
        <div class="modal-actions">
          <button class="btn btn-ghost" @click="deleteTarget = null">取消</button>
          <button class="btn btn-danger" @click="doDeleteLabel" :disabled="deleting">
            {{ deleting ? '删除中...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── 数据导入 ── -->
    <div class="card" v-if="authStore.isAdmin">
      <h2>数据导入</h2>

      <!-- JSON 导入 -->
      <div class="section">
        <h3>JSON 格式导入</h3>
        <p class="hint">粘贴 JSON 数据: { "nodes": [...], "relationships": [...] }，节点会写入所选目标图谱</p>
        <div class="import-row">
          <textarea v-model="jsonInput" class="input code-area" rows="6"
            placeholder='{"nodes":[{"name":"节点A","category":"分类"}],"relationships":[{"source":"节点A","target":"节点B","type":"RELATED_TO"}]}'
          ></textarea>
          <div class="import-actions">
            <select v-model="importTargetLabel" class="input" style="max-width:200px">
              <option v-for="lb in importLabelOptions" :key="lb.value" :value="lb.value">
                {{ lb.text }}
              </option>
            </select>
            <input v-model="jsonSource" class="input" placeholder="数据来源（可选）" style="max-width:160px" />
            <button class="btn btn-primary" @click="doImportJson" :disabled="!jsonInput.trim() || importing">
              {{ importing ? '导入中...' : '导入 JSON' }}
            </button>
          </div>
        </div>
      </div>

      <!-- CSV 导入 -->
      <div class="section">
        <h3>CSV 格式导入</h3>
        <p class="hint">粘贴 CSV 内容: node,名称,分类,难度,描述 / rel,源节点,目标节点,关系类型,描述</p>
        <div class="import-row">
          <textarea v-model="csvInput" class="input code-area" rows="4"
            placeholder="node,函数,核心,5,Python函数的定义和调用&#10;rel,函数,装饰器,RELATED_TO,关联描述"
          ></textarea>
          <button class="btn btn-primary" @click="doImportCsv" :disabled="!csvInput.trim() || importing">
            {{ importing ? '导入中...' : '导入 CSV' }}
          </button>
        </div>
      </div>

      <!-- 文件上传导入 -->
      <div class="section">
        <h3>文件上传导入</h3>
        <div class="import-row">
          <div class="file-upload-row">
            <label class="file-label">
              <input type="file" ref="fileInput" accept=".json,.csv" @change="onFileSelected" />
              <span class="file-placeholder">{{ fileInputName || '选择 JSON 或 CSV 文件...' }}</span>
            </label>
            <select v-model="fileLabel" class="input" style="max-width:200px">
              <option v-for="lb in importLabelOptions" :key="lb.value" :value="lb.value">{{ lb.text }}</option>
            </select>
            <input v-model="fileSource" class="input" placeholder="数据来源（可选）" style="max-width:160px" />
            <button class="btn btn-primary" @click="doImportFile" :disabled="!selectedFile || importing">
              {{ importing ? '导入中...' : '上传导入' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 导入结果 -->
    <div v-if="importResult" class="card result-card" :class="importResult.success ? 'result-success' : 'result-error'">
      <h3>{{ importResult.success ? '导入完成' : '导入失败' }}</h3>
      <p>{{ importResult.message }}</p>
      <div v-if="importResult.data" class="result-stats">
        <span>新建节点: {{ importResult.data.nodes_created || 0 }}</span>
        <span>跳过节点: {{ importResult.data.nodes_skipped || 0 }}</span>
        <span>新建关系: {{ importResult.data.relationships_created || 0 }}</span>
      </div>
    </div>

    <!-- ── 数据导出 ── -->
    <div class="card" v-if="authStore.isAdmin">
      <h2>数据导出</h2>
      <div class="export-actions">
        <button class="btn btn-primary" @click="doExportJson" :disabled="exporting">
          {{ exporting ? '导出中...' : '导出全量 JSON' }}
        </button>
        <button class="btn btn-secondary" @click="doExportCsv" :disabled="exporting">
          {{ exporting ? '导出中...' : '导出全量 CSV' }}
        </button>
      </div>
    </div>

    <!-- ── 图谱统计 ── -->
    <div class="card" v-if="stats">
      <div class="card-header">
        <h2>图谱状态</h2>
        <div class="header-actions" v-if="authStore.isAdmin">
          <select v-model="enrichTrack" class="input" style="width:150px;margin-right:8px">
            <option value="">全部拓展</option>
            <option v-for="t in aiTracks" :key="t" :value="t">{{ t }}</option>
          </select>
          <button class="btn btn-ai" @click="startEnrichment" :disabled="enriching || linking">
            {{ enriching ? `补全中 ${enrichCurrent}/${enrichTotal}...` : 'AI 补全' }}
          </button>
          <button class="btn btn-ai" @click="startLinksEnrich" :disabled="enriching || linking">
            {{ linking ? `链接中 ${linkCurrent}/${linkTotal}...` : '外部链接' }}
          </button>
        </div>
      </div>
      <!-- 补全进度条 -->
      <div v-if="enriching" class="enrich-progress">
        <div class="progress-bar">
          <div class="progress-fill-enriched" :style="{ width: enrichPctEnriched + '%' }" title="已补全"></div>
          <div class="progress-fill-skipped" :style="{ width: enrichPctSkipped + '%' }" title="已跳过"></div>
        </div>
        <div class="progress-legend">
          <span class="legend-enriched">补全 {{ enrichEnriched }}</span>
          <span class="legend-skipped">跳过 {{ enrichSkipped }}</span>
          <span class="legend-failed">失败 {{ enrichFailed }}</span>
          <span class="legend-total">总 {{ enrichTotal }} ({{ enrichPct }}%)</span>
        </div>
      </div>
      <div v-if="enrichResult" class="enrich-result" :class="{ 'enrich-error': enrichResult.failed > 0 }">
        {{ enrichResult.enriched }} 成功, {{ enrichResult.skipped || 0 }} 跳过, {{ enrichResult.failed }} 失败, 耗时 {{ enrichResult.elapsed }}s
      </div>
      <!-- 链接补全进度条 -->
      <div v-if="linking" class="enrich-progress">
        <div class="progress-bar">
          <div class="progress-fill-enriched" :style="{ width: linkPctEnriched + '%' }" title="已补全"></div>
          <div class="progress-fill-skipped" :style="{ width: linkPctSkipped + '%' }" title="已跳过"></div>
        </div>
        <div class="progress-legend">
          <span class="legend-enriched">补全 {{ linkEnriched }}</span>
          <span class="legend-skipped">跳过 {{ linkSkipped }}</span>
          <span class="legend-failed">失败 {{ linkFailed }}</span>
          <span class="legend-total">总 {{ linkTotal }} ({{ linkPct }}%)</span>
        </div>
      </div>
      <div v-if="linkResult" class="enrich-result" :class="{ 'enrich-error': linkResult.failed > 0 }">
        链接: {{ linkResult.enriched }} 成功, {{ linkResult.skipped || 0 }} 跳过, {{ linkResult.failed }} 失败, 耗时 {{ linkResult.elapsed }}s
      </div>
      <div class="stats-grid">
        <div class="stat-box">
          <span class="stat-num">{{ stats.node_count }}</span>
          <span class="stat-label">总节点</span>
        </div>
        <div class="stat-box">
          <span class="stat-num">{{ stats.relationship_count }}</span>
          <span class="stat-label">总关系</span>
        </div>
        <div class="stat-box" v-for="(cnt, lb) in stats.labels_distribution" :key="lb">
          <span class="stat-num">{{ cnt }}</span>
          <span class="stat-label">{{ lb }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import api from '../api'
import { authStore } from '../stores/auth'
import { useFeedback } from '../composables/useFeedback'

const { tip, ask } = useFeedback()

// ── 图谱标签 ──
const labels = ref([])
const showCreateDialog = ref(false)
const newLabel = ref('')
const newDisplayName = ref('')
const newDescription = ref('')
const creating = ref(false)
const createError = ref('')
const deleteTarget = ref(null)
const deleting = ref(false)
const activePolls = []  // 所有轮询 interval ID，onUnmounted 时统一清除

// ── 导入 ──
const jsonInput = ref('')
const jsonSource = ref('')
const csvInput = ref('')
const importing = ref(false)
const importResult = ref(null)
const fileInput = ref(null)
const selectedFile = ref(null)
const fileInputName = ref('')
const fileLabel = ref('KnowledgePoint')
const fileSource = ref('')
const importTargetLabel = ref('KnowledgePoint')

// ── 导出 ──
const exporting = ref(false)

// ── 统计 ──
const stats = ref(null)

// ── AI 补全 ──
const enrichTrack = ref('')
const enriching = ref(false)
const enrichCurrent = ref(0)
const enrichTotal = ref(0)
const enrichEnriched = ref(0)
const enrichSkipped = ref(0)
const enrichFailed = ref(0)
const enrichResult = ref(null)
const aiTracks = ['公共基础', '网络爬虫', '数据分析及可视化', '机器学习', '深度学习', '大模型', '自然语言处理', '自动化运维']

const enrichPct = computed(() => {
  if (enrichTotal.value === 0) return 0
  return Math.round((enrichCurrent.value / enrichTotal.value) * 100)
})
const enrichPctEnriched = computed(() => {
  if (enrichTotal.value === 0) return 0
  return Math.round((enrichEnriched.value / enrichTotal.value) * 100)
})
const enrichPctSkipped = computed(() => {
  if (enrichTotal.value === 0) return 0
  return Math.round((enrichSkipped.value / enrichTotal.value) * 100)
})

async function startEnrichment() {
  if (enriching.value) return
  enriching.value = true
  enrichCurrent.value = 0
  enrichTotal.value = 0
  enrichEnriched.value = 0
  enrichSkipped.value = 0
  enrichFailed.value = 0
  enrichResult.value = null

  try {
    // 启动任务
    const r = await api.post('/llm/enrich', { track: enrichTrack.value || '' })
    if (!r.success) {
      tip(r.message)
      enriching.value = false
      return
    }
    const taskId = r.data.task_id
    enrichTotal.value = r.data.total

    // 轮询进度（每秒一次）
    const poll = setInterval(async () => {
      try {
        const s = await api.get(`/llm/enrich/status/${taskId}`)
        if (s.success) {
          enrichCurrent.value = s.data.current
          enrichEnriched.value = s.data.enriched
          enrichSkipped.value = s.data.skipped || 0
          enrichFailed.value = s.data.failed
          if (s.data.status === 'done') {
            clearInterval(poll)
            activePolls.splice(activePolls.indexOf(poll), 1)
            enrichResult.value = s.data
            enriching.value = false
            await loadStats()
          }
        }
      } catch (e) { /* ignore poll errors */ }
    }, 1000)
    activePolls.push(poll)
  } catch (e) {
    console.error('AI补全失败:', e)
    enriching.value = false
  }
}

// ── 外部链接补全 ──
const linking = ref(false)
const linkCurrent = ref(0)
const linkTotal = ref(0)
const linkEnriched = ref(0)
const linkSkipped = ref(0)
const linkFailed = ref(0)
const linkResult = ref(null)

const linkPct = computed(() => {
  if (linkTotal.value === 0) return 0
  return Math.round((linkCurrent.value / linkTotal.value) * 100)
})
const linkPctEnriched = computed(() => {
  if (linkTotal.value === 0) return 0
  return Math.round((linkEnriched.value / linkTotal.value) * 100)
})
const linkPctSkipped = computed(() => {
  if (linkTotal.value === 0) return 0
  return Math.round((linkSkipped.value / linkTotal.value) * 100)
})

async function startLinksEnrich() {
  if (linking.value) return
  linking.value = true
  linkCurrent.value = 0
  linkTotal.value = 0
  linkEnriched.value = 0
  linkSkipped.value = 0
  linkFailed.value = 0
  linkResult.value = null

  try {
    const r = await api.post('/llm/links-enrich', { track: enrichTrack.value || '' })
    if (!r.success) {
      tip(r.message)
      linking.value = false
      return
    }
    const taskId = r.data.task_id
    linkTotal.value = r.data.total

    const poll = setInterval(async () => {
      try {
        const s = await api.get(`/llm/links-enrich/status/${taskId}`)
        if (s.success) {
          linkCurrent.value = s.data.current
          linkEnriched.value = s.data.enriched
          linkSkipped.value = s.data.skipped || 0
          linkFailed.value = s.data.failed
          if (s.data.status === 'done') {
            clearInterval(poll)
            activePolls.splice(activePolls.indexOf(poll), 1)
            linkResult.value = s.data
            linking.value = false
            await loadStats()
          }
        }
      } catch (e) { /* ignore poll errors */ }
    }, 1000)
    activePolls.push(poll)
  } catch (e) {
    console.error('链接补全失败:', e)
    linking.value = false
  }
}

// ── 导入目标图谱选择（含所有已有图谱） ──
const importLabelOptions = computed(() => {
  const opts = labels.value.map(lb => ({
    value: lb.label,
    text: `${lb.display_name} (${lb.node_count} 节点)`
  }))
  // 确保默认选项存在
  if (!opts.find(o => o.value === 'KnowledgePoint')) {
    opts.unshift({ value: 'KnowledgePoint', text: '系统知识图谱 (KnowledgePoint)' })
  }
  if (!opts.find(o => o.value === 'TextbookKnowledge')) {
    opts.push({ value: 'TextbookKnowledge', text: '教材知识图谱 (TextbookKnowledge)' })
  }
  return opts
})

onMounted(async () => {
  await Promise.all([loadLabels(), loadStats()])
})

onUnmounted(() => {
  activePolls.forEach(id => clearInterval(id))
  activePolls.length = 0
})

async function loadLabels() {
  try {
    const r = await api.get('/graph-management/labels')
    if (r.success) labels.value = r.data?.items || r.data
  } catch (e) { console.error('加载图谱列表失败:', e) }
}

async function loadStats() {
  try {
    const r = await api.get('/graph/statistics')
    if (r.success) stats.value = r.data
  } catch (e) { console.error('加载统计失败:', e) }
}

// ── 创建图谱 ──
async function doCreateLabel() {
  const label = newLabel.value.trim()
  const dn = newDisplayName.value.trim()
  if (!label) {
    createError.value = '图谱标识不能为空'
    return
  }
  if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(label)) {
    createError.value = '图谱标识只能包含英文字母、数字和下划线，且以字母开头'
    return
  }
  creating.value = true
  createError.value = ''
  try {
    const r = await api.post('/graph-management/labels', {
      label,
      display_name: dn || label,
      description: newDescription.value.trim()
    })
    if (r.success) {
      showCreateDialog.value = false
      newLabel.value = ''
      newDisplayName.value = ''
      newDescription.value = ''
      await Promise.all([loadLabels(), loadStats()])
    } else {
      createError.value = r.message
    }
  } catch (e) {
    createError.value = e.message || '创建失败'
  } finally {
    creating.value = false
  }
}

// ── 删除图谱 ──
function confirmDelete(lb) {
  deleteTarget.value = lb
}

async function doDeleteLabel() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    const r = await api.delete(`/graph-management/labels/${encodeURIComponent(deleteTarget.value.label)}`)
    if (r.success) {
      deleteTarget.value = null
      await Promise.all([loadLabels(), loadStats()])
    }
  } catch (e) {
    console.error('删除失败:', e)
  } finally {
    deleting.value = false
  }
}

// ── 文件选择 ──
function onFileSelected(e) {
  const file = e.target.files?.[0]
  if (file) {
    selectedFile.value = file
    fileInputName.value = file.name
  }
}

// ── JSON 导入 ──
async function doImportJson() {
  let data
  try {
    data = JSON.parse(jsonInput.value)
  } catch (e) {
    importResult.value = { success: false, message: 'JSON 格式错误: ' + e.message }
    return
  }
  importing.value = true
  importResult.value = null
  try {
    const body = typeof data === 'object' && !Array.isArray(data) ? data : { nodes: Array.isArray(data) ? data : [] }
    body.label = importTargetLabel.value
    body.source = jsonSource.value || '用户导入'
    const r = await api.post('/import/json', body)
    importResult.value = r
    if (r.success) {
      jsonInput.value = ''
      jsonSource.value = ''
      await Promise.all([loadLabels(), loadStats()])
    }
  } catch (e) {
    importResult.value = { success: false, message: e.message || '导入失败' }
  } finally {
    importing.value = false
  }
}

// ── CSV 导入 ──
async function doImportCsv() {
  importing.value = true
  importResult.value = null
  try {
    const r = await api.post('/import/csv', { content: csvInput.value })
    importResult.value = r
    if (r.success) {
      csvInput.value = ''
      await Promise.all([loadLabels(), loadStats()])
    }
  } catch (e) {
    importResult.value = { success: false, message: e.message || '导入失败' }
  } finally {
    importing.value = false
  }
}

// ── 文件导入 ──
async function doImportFile() {
  if (!selectedFile.value) return
  importing.value = true
  importResult.value = null
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    formData.append('label', fileLabel.value)
    formData.append('source', fileSource.value || '用户导入')
    const r = await api.post('/import/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    importResult.value = r
    if (r.success) {
      selectedFile.value = null
      fileInputName.value = ''
      if (fileInput.value) fileInput.value.value = ''
      await Promise.all([loadLabels(), loadStats()])
    }
  } catch (e) {
    importResult.value = { success: false, message: e.message || '导入失败' }
  } finally {
    importing.value = false
  }
}

// ── 导出 ──
async function doExportJson() {
  exporting.value = true
  try {
    const r = await api.get('/export/json')
    const blob = new Blob([JSON.stringify(r.data, null, 2)], { type: 'application/json' })
    downloadBlob(blob, 'knowledge_graph_export.json')
  } catch (e) {
    window.open('/api/v1/export/json', '_blank')
  } finally {
    exporting.value = false
  }
}

async function doExportCsv() {
  exporting.value = true
  try {
    const response = await fetch('/api/v1/export/csv', { credentials: 'include' })
    if (!response.ok) throw new Error('导出失败')
    const blob = await response.blob()
    downloadBlob(blob, 'kekg_export.csv')
  } catch (e) {
    // fallback
  } finally {
    setTimeout(() => { exporting.value = false }, 2000)
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.page-container { max-width: 960px; margin: 0 auto; padding: 32px 24px; }
.page-title { font-size: 25px; font-weight: 700; margin-bottom: 6px; }
.page-subtitle { color: var(--text-secondary); margin-bottom: 28px; }

.card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 24px;
  margin-bottom: 20px;
}
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.header-actions { display: flex; align-items: center; }
.card h2 { font-size: 16px; font-weight: 600; margin: 0 0 16px; }
.card h3 { font-size: 13px; font-weight: 600; margin-bottom: 8px; color: var(--text-secondary); }

.section {
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border-color);
}
.section:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }

.empty-state { color: var(--text-light); font-size: 12px; padding: 24px 0; text-align: center; }

/* 图谱标签列表 */
.label-grid { display: flex; flex-direction: column; gap: 10px; }
.label-card {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 18px; background: var(--bg-secondary);
  border-radius: var(--radius-sm); border: 1px solid var(--border-color);
}
.label-info { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.label-name { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.label-tag {
  font-size: 10px; padding: 2px 8px; border-radius: 10px;
  background: rgba(59,130,246,0.12); color: var(--accent-blue);
  font-family: monospace;
}
.label-meta { font-size: 11px; color: var(--text-light); }
.label-right { display: flex; align-items: center; gap: 16px; }
.label-count { font-size: 11px; font-weight: 600; color: var(--accent-blue); }

/* 弹窗 */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 300;
}
.modal {
  background: var(--bg-primary); border-radius: var(--radius-md);
  padding: 28px; min-width: 420px; max-width: 500px;
}
.modal-sm { max-width: 400px; }
.modal h3 { font-size: 16px; font-weight: 600; margin-bottom: 16px; }
.modal p { font-size: 12px; color: var(--text-secondary); margin-bottom: 16px; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 11px; font-weight: 500; margin-bottom: 4px; color: var(--text-secondary); }
.modal-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
.error-msg { color: #ef4444; font-size: 11px; margin-top: 8px; }

/* 导入区 */
.import-row { display: flex; flex-direction: column; gap: 10px; }
.import-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.code-area { font-family: 'Consolas', 'Courier New', monospace; font-size: 11px; line-height: 1.5; resize: vertical; }
.hint { font-size: 11px; color: var(--text-light); margin-bottom: 8px; }

.file-upload-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.file-label {
  display: flex; align-items: center; cursor: pointer;
  padding: 8px 12px; border: 1px dashed #cbd5e1; border-radius: 6px; font-size: 11px;
  color: var(--text-secondary); min-width: 200px;
}
.file-label:hover { border-color: var(--accent-blue); color: var(--accent-blue); }
.file-label input[type="file"] { display: none; }
.file-placeholder { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 导入结果 */
.result-card { border-left: 4px solid; }
.result-success { border-left-color: #10b981; }
.result-error { border-left-color: #ef4444; }
.result-card h3 { font-size: 14px; margin-bottom: 4px; }
.result-card p { font-size: 12px; color: var(--text-secondary); }
.result-stats { display: flex; gap: 20px; margin-top: 10px; font-size: 11px; color: var(--text-primary); }

/* 导出 */
.export-actions { display: flex; gap: 10px; }

/* 统计 */
.stats-grid { display: flex; gap: 20px; flex-wrap: wrap; }
.stat-box {
  display: flex; flex-direction: column; align-items: center;
  padding: 12px 20px; background: var(--bg-secondary);
  border-radius: var(--radius-sm); min-width: 100px;
}
.stat-num { font-size: 21px; font-weight: 700; color: var(--accent-blue); }
.stat-label { font-size: 11px; color: var(--text-light); margin-top: 4px; }

/* 按钮 */
.btn { cursor: pointer; padding: 8px 20px; border-radius: var(--radius-sm); font-size: 12px; font-weight: 500; border: none; }
.btn-sm { padding: 6px 14px; font-size: 11px; }
.btn-primary { background: var(--accent-blue); color: white; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-ai { 
  background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; 
  font-weight: 600; transition: all 0.2s;
}
.btn-ai:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(99,102,241,0.4); }
.btn-ai:disabled { opacity: 0.7; cursor: not-allowed; }

/* AI 补全进度 */
.enrich-progress { margin: 8px 0 12px; display: flex; flex-direction: column; gap: 6px; }
.progress-bar { height: 10px; background: #2a2a3a; border-radius: 4px; display: flex; overflow: hidden; }
.progress-fill-enriched { height: 100%; background: linear-gradient(90deg, #22c55e, #10b981); transition: width 0.3s; }
.progress-fill-skipped { height: 100%; background: linear-gradient(90deg, #6b7280, #9ca3af); transition: width 0.3s; }
.progress-legend { display: flex; gap: 16px; margin-top: 6px; font-size: 11px; color: #94a3b8; flex-wrap: wrap; }
.legend-enriched { color: #22c55e; }
.legend-skipped { color: #9ca3af; }
.legend-failed { color: #ef4444; }
.legend-total { color: #94a3b8; margin-left: auto; }
.progress-text { font-size: 11px; color: var(--text-secondary); white-space: nowrap; }
.enrich-result { font-size: 11px; padding: 6px 12px; background: #d1fae5; color: #065f46; border-radius: 4px; margin-bottom: 10px; }
.enrich-error { background: #fee2e2; color: #991b1b; }
.btn-secondary { background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border-color); }
.btn-danger { background: #dc2626; color: white; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-ghost { background: transparent; color: var(--text-secondary); border: 1px solid var(--border-color); }
.btn-ghost:hover { border-color: var(--text-primary); color: var(--text-primary); }

.input {
  padding: 8px 12px; border: 1px solid var(--border-color); border-radius: var(--radius-sm);
  font-size: 12px; background: var(--bg-primary); color: var(--text-primary);
}
.input:focus { outline: none; border-color: var(--accent-blue); }
</style>
