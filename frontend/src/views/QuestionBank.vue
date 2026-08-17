<template>
  <div class="page-container">
    <div class="page-top">
      <div>
        <h1>题库管理</h1>
        <p class="page-subtitle">管理分层测试题目</p>
      </div>
      <div class="top-actions">
        <button v-if="authStore.isAdmin" class="btn btn-primary" @click="openCreate">+ 新建题目</button>
        <button class="btn btn-outline" @click="goStats">统计分析</button>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="filter-bar">
      <select v-model="filterType" class="input input-sm" @change="doSearch">
        <option value="">全部类型</option>
        <option value="choice">选择题</option>
        <option value="judge">判断题</option>
        <option value="fill">填空题</option>
        <option value="subjective">主观题</option>
      </select>
      <select v-model="filterDifficulty" class="input input-sm" @change="doSearch">
        <option value="">全部难度</option>
        <option v-for="s in 4" :key="s" :value="s">{{ '★'.repeat(s) }}</option>
      </select>
      <select v-model="filterTopic" class="input input-sm" @change="doSearch">
        <option value="">全部知识点</option>
        <option v-for="t in topics" :key="t" :value="t">{{ t }}</option>
      </select>
      <select v-if="authStore.isAdmin" v-model="filterStatus" class="input input-sm" @change="doSearch">
        <option value="">全部状态</option>
        <option value="pending">待审核</option>
        <option value="approved">已通过</option>
        <option value="rejected">已驳回</option>
      </select>
      <input v-model="filterKeyword" class="input input-sm" placeholder="搜索题目..." @keyup.enter="doSearch" style="flex:1;min-width:160px" />
      <button class="btn btn-sm btn-outline" @click="doSearch">搜索</button>
      <button v-if="authStore.isAdmin" class="btn btn-sm btn-ai" @click="showAiModal = true">AI 出题</button>
      <button v-if="authStore.isAdmin && selectedIds.length" class="btn btn-sm btn-danger" @click="confirmBatchDelete">批量删除({{ selectedIds.length }})</button>
      <div class="dropdown-wrap" v-if="authStore.isAdmin">
        <button class="btn btn-sm btn-outline" @click="showExportMenu = !showExportMenu" :disabled="exporting">{{ exporting ? '导出中...' : '导出' }}</button>
        <div class="dropdown-menu" v-if="showExportMenu">
          <div class="dropdown-item" @click="doExport('excel'); showExportMenu = false">导出 Excel</div>
          <div class="dropdown-item" @click="doExport('word'); showExportMenu = false">导出 Word</div>
        </div>
      </div>
      <button v-if="authStore.isAdmin" class="btn btn-sm btn-outline" @click="showImport = true">导入 Excel</button>
      <button v-if="authStore.isAdmin" class="btn btn-sm btn-outline" @click="showWordImport = true">导入 Word</button>
    </div>

    <!-- 列表 -->
    <UiLoading v-if="loading" />

    <table v-else class="data-table">
      <thead>
        <tr>
          <th style="width:40px">
            <input type="checkbox" @change="toggleAll" :checked="allSelected" v-if="authStore.isAdmin" />
          </th>
          <th style="width:60px">ID</th>
          <th>题目</th>
          <th style="width:80px">类型</th>
          <th style="width:70px">难度</th>
          <th style="width:80px">知识点</th>
          <th style="width:80px">通过率</th>
          <th style="width:70px">状态</th>
          <th style="width:160px" v-if="authStore.isAdmin">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="q in questions" :key="q.id">
          <td v-if="authStore.isAdmin">
            <input type="checkbox" :checked="selectedIds.includes(q.id)" @change="toggleSelect(q.id)" />
          </td>
          <td>{{ q.id }}</td>
          <td>
            <div class="q-title" @click="openDetail(q)" style="cursor:pointer">{{ q.title }}</div>
            <div class="q-options-preview" v-if="q.options && q.options.length">
              {{ q.options.join(' | ') }}
            </div>
          </td>
          <td><span class="type-tag" :class="'type-' + q.type">{{ typeLabel(q.type) }}</span></td>
          <td>
            <span class="star-rating" :class="'star-' + starLevel(q.difficulty)">
              {{ starText(q.difficulty) }}
            </span>
            <span v-if="!q.difficulty" class="text-muted">-</span>
          </td>
          <td><span class="topic-tag" v-if="q.topic">{{ q.topic }}</span><span v-else>-</span></td>
          <td>
            <span v-if="q.pass_rate !== null && q.pass_rate !== undefined" class="pass-rate" :class="passRateClass(q.pass_rate)">
              {{ q.pass_rate }}%
            </span>
            <span v-else class="text-muted">-</span>
          </td>
          <td><span class="status-tag" :class="'status-' + (q.status || 'approved')">{{ statusLabel(q.status) }}</span></td>
          <td v-if="authStore.isAdmin" class="action-cell">
            <template v-if="q.status === 'pending'">
              <button class="btn btn-xs btn-success-text" @click="doApprove(q.id)">通过</button>
              <button class="btn btn-xs btn-danger-text" @click="doReject(q.id)">驳回</button>
            </template>
            <template v-else-if="q.status === 'approved' || !q.status">
              <button class="btn btn-xs btn-outline" @click="openEdit(q)">编辑</button>
              <button class="btn btn-xs btn-danger-text" @click="doDelete(q.id)">删除</button>
            </template>
            <span v-else-if="q.status === 'rejected'" class="status-label-rejected">已驳回</span>
          </td>
        </tr>
      </tbody>
    </table>

    <UiEmpty v-if="!loading && questions.length === 0" text="暂无题目" />

    <!-- 分页 -->
    <div class="pagination" v-if="totalPages > 1">
      <button class="btn btn-sm btn-outline" :disabled="page <= 1" @click="page--; doSearch()">上一页</button>
      <span class="page-info">{{ page }} / {{ totalPages }}</span>
      <button class="btn btn-sm btn-outline" :disabled="page >= totalPages" @click="page++; doSearch()">下一页</button>
    </div>

    <!-- 创建/编辑弹窗 -->
    <div v-if="showForm" class="modal-mask" @click.self="showForm = false">
      <div class="modal-card wide">
        <h4>{{ editingQuestion ? '编辑题目' : '新建题目' }}</h4>
        <div class="form-group">
          <label>题目内容 <span class="required">*</span></label>
          <textarea v-model="form.title" class="input" rows="3" placeholder="请输入题目内容"></textarea>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>题目类型 <span class="required">*</span></label>
            <select v-model="form.type" class="input">
              <option value="">请选择</option>
              <option value="choice">选择题</option>
              <option value="judge">判断题</option>
              <option value="fill">填空题</option>
              <option value="subjective">主观题</option>
            </select>
          </div>
          <div class="form-group">
            <label>难度</label>
            <select v-model="form.difficulty" class="input">
              <option value="">自动计算</option>
              <option v-for="d in 12" :key="d" :value="d">难度 {{ d }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>知识点</label>
            <select v-model="form.topic" class="input">
              <option value="">无</option>
              <option v-for="t in topics" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
        </div>
        <!-- 选择题选项 -->
        <div class="form-group" v-if="form.type === 'choice'">
          <label>
            <input type="checkbox" v-model="form.is_multi" /> 多选题
          </label>
          <label>选项 <span class="required">*</span></label>
          <div v-for="(opt, idx) in form.options" :key="idx" class="option-row">
            <span class="opt-label">{{ String.fromCharCode(65 + idx) }}.</span>
            <input v-model="form.options[idx]" class="input input-sm" style="flex:1" :placeholder="'选项 ' + String.fromCharCode(65 + idx)" />
            <button class="btn btn-xs btn-ghost" @click="form.options.splice(idx, 1)" v-if="form.options.length > 2">-</button>
          </div>
          <button class="btn btn-xs btn-outline" @click="form.options.push('')">+ 添加选项</button>
        </div>
        <!-- 判断题选项 -->
        <div class="form-group" v-if="form.type === 'judge'">
          <label>答案 <span class="required">*</span></label>
          <select v-model="form.answer" class="input input-sm" style="width:160px">
            <option value="">请选择</option>
            <option value="对">对 (正确)</option>
            <option value="错">错 (错误)</option>
          </select>
        </div>
        <!-- 选择题/填空题/主观题答案 -->
        <div class="form-group" v-if="form.type !== 'judge'">
          <label>答案<span v-if="form.type !== 'subjective'"> <span class="required">*</span></span></label>
          <input v-model="form.answer" class="input" :placeholder="form.type === 'choice' ? '如：A 或 A,B（多选题用逗号分隔）' : form.type === 'subjective' ? '可选参考答案' : '如：答案内容'" />
        </div>
        <div class="form-group">
          <label>解析</label>
          <textarea v-model="form.explanation" class="input" rows="2" placeholder="题目解析（可选）"></textarea>
        </div>
        <div class="form-group">
          <label>关联知识点</label>
          <input v-model="formKpSearch" class="input" placeholder="搜索知识点..." @input="onFormKpSearch" />
          <div v-if="formKpResults.length" class="kp-result-list">
            <div v-for="kp in formKpResults" :key="kp.id"
                 class="kp-result-item" :class="{picked: formKpPickedIds.includes(kp.id)}"
                 @click="toggleFormKp(kp)">
              {{ kp.properties?.name || kp.name }}
              <span v-if="formKpPickedIds.includes(kp.id)">&#10003;</span>
            </div>
          </div>
          <div v-if="formKpPickedIds.length" class="ai-chips" style="margin-top:6px">
            <span v-for="kp in formKpPickedKps" :key="kp.id" class="ai-chip">
              {{ kp.properties?.name || kp.name }} <span class="ai-chip-x" @click="removeFormKp(kp.id)">&times;</span>
            </span>
          </div>
        </div>
        <div v-if="formError" class="error-msg">{{ formError }}</div>
        <div class="modal-actions">
          <button class="btn btn-ghost" @click="showForm = false">取消</button>
          <button class="btn btn-primary" @click="saveQuestion" :disabled="saving">{{ saving ? '保存中...' : '保存' }}</button>
        </div>
      </div>
    </div>

    <!-- 查看详情弹窗 -->
    <div v-if="detailQuestion" class="modal-mask" @click.self="detailQuestion = null">
      <div class="modal-card wide">
        <h4>题目详情</h4>
        <div class="detail-block">
          <div class="detail-row"><span class="detail-label">ID：</span>{{ detailQuestion.id }}</div>
          <div class="detail-row"><span class="detail-label">类型：</span>{{ typeLabel(detailQuestion.type) }}</div>

          <div class="detail-row"><span class="detail-label">难度：</span>{{ detailQuestion.difficulty || '-' }}</div>
          <div class="detail-row"><span class="detail-label">知识点：</span>{{ detailQuestion.topic || '-' }}</div>
          <div class="detail-row"><span class="detail-label">题目：</span>{{ detailQuestion.title }}</div>
          <div class="detail-row" v-if="detailQuestion.options && detailQuestion.options.length">
            <span class="detail-label">选项：</span>
            <span v-for="(o, i) in detailQuestion.options" :key="i">{{ String.fromCharCode(65 + i) }}. {{ o }}<br /></span>
          </div>
          <div class="detail-row"><span class="detail-label">答案：</span>{{ detailQuestion.answer || '-' }}</div>
          <div class="detail-row"><span class="detail-label">解析：</span>{{ detailQuestion.explanation || '-' }}</div>
        </div>
        <div class="modal-actions">
          <button class="btn btn-ghost" @click="detailQuestion = null">关闭</button>
        </div>
      </div>
    </div>

    <!-- 批量删除确认 -->
    <div v-if="showBatchDelete" class="modal-mask" @click.self="showBatchDelete = false">
      <div class="modal-card">
        <h4>确认批量删除</h4>
        <p>确定要删除选中的 {{ selectedIds.length }} 道题目吗？此操作不可撤销。</p>
        <div class="modal-actions">
          <button class="btn btn-ghost" @click="showBatchDelete = false">取消</button>
          <button class="btn btn-danger" @click="doBatchDelete" :disabled="saving">确认删除</button>
        </div>
      </div>
    </div>

    <!-- Excel 导入弹窗 -->
    <div v-if="showImport" class="modal-mask" @click.self="closeImport">
      <div class="modal-card wide">
        <h4>导入 Excel 题目</h4>

        <!-- Excel 文件上传 -->
        <div class="form-group">
          <label>选择 .xlsx 文件</label>
          <div class="file-upload-area">
            <input type="file" accept=".xlsx,.xls" @change="onFileSelect" ref="fileInput" />
            <p v-if="importFile" class="file-name">已选择: {{ importFile.name }}</p>
            <p v-else class="file-hint">支持 .xlsx / .xls 格式，模板：题目、类型、分类、难度、是否多选、选项ABCD、答案、解析</p>
          </div>
        </div>

        <div v-if="importResult" class="import-result">
          <div class="result-line success" v-if="importResult.success_count">成功导入 {{ importResult.success_count }} 题</div>
          <div class="result-line warn" v-if="importResult.skipped_count">跳过重复 {{ importResult.skipped_count }} 题</div>
          <div class="result-line error" v-if="importResult.error_count">失败 {{ importResult.error_count }} 题</div>
          <div class="result-line warn" v-if="importResult.total_rows">共 {{ importResult.total_rows }} 行数据</div>
          <div v-for="e in importResult.errors" :key="e.row" class="result-line warn">第{{ e.row }}行: {{ e.message }}</div>
        </div>
        <div class="modal-actions">
          <button class="btn btn-ghost" @click="closeImport">关闭</button>
          <button class="btn btn-primary" @click="doImportExcel" :disabled="importing || !importFile">
            {{ importing ? '导入中...' : '上传并导入' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Word 导入弹窗 -->
    <div v-if="showWordImport" class="modal-mask" @click.self="closeWordImport">
      <div class="modal-card wide">
        <h4>导入 Word 题目</h4>

        <!-- Word 文件上传 -->
        <div class="form-group">
          <label>选择 .docx 文件</label>
          <div class="file-upload-area">
            <input type="file" accept=".docx" @change="onWordFileSelect" ref="wordFileInput" />
            <p v-if="wordImportFile" class="file-name">已选择: {{ wordImportFile.name }}</p>
            <p v-else class="file-hint">支持 .docx 格式，表格列：题目、类型、分类、难度、是否多选、选项ABCD、答案、解析</p>
          </div>
        </div>

        <div v-if="wordImportResult" class="import-result">
          <div class="result-line success" v-if="wordImportResult.success_count">成功导入 {{ wordImportResult.success_count }} 题</div>
          <div class="result-line error" v-if="wordImportResult.error_count">失败 {{ wordImportResult.error_count }} 题</div>
          <div class="result-line warn" v-if="wordImportResult.total_rows">共 {{ wordImportResult.total_rows }} 行数据</div>
          <div v-for="e in wordImportResult.errors" :key="e.row" class="result-line warn">第{{ e.row }}行: {{ e.message }}</div>
        </div>
        <div class="modal-actions">
          <button class="btn btn-ghost" @click="closeWordImport">关闭</button>
          <button class="btn btn-primary" @click="doImportWord" :disabled="wordImporting || !wordImportFile">
            {{ wordImporting ? '导入中...' : '上传并导入' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ===== AI 出题弹窗 ===== -->
    <div v-if="showAiModal" class="modal-overlay" @click.self="showAiModal = false">
      <div class="modal" style="max-width:600px">
        <h3>AI 批量出题</h3>
        <div class="form-group">
          <label>选择知识点</label>
          <input v-model="aiSearchKw" class="input" placeholder="搜索知识点..." @input="onAiSearch" />
          <div v-if="aiSearchResults.length" class="kp-result-list">
            <div v-for="kp in aiSearchResults" :key="kp.id"
                 class="kp-result-item" :class="{picked: aiPickedIds.includes(kp.id)}"
                 @click="toggleAiKp(kp)">
              {{ kp.properties?.name || kp.name }}
              <span v-if="aiPickedIds.includes(kp.id)">&#10003;</span>
            </div>
          </div>
          <div v-if="aiPickedIds.length" class="ai-chips">
            <span v-for="kp in aiPickedKps" :key="kp.id" class="ai-chip">
              {{ kp.properties?.name || kp.name }} <span class="ai-chip-x" @click="removeAiKp(kp.id)">&times;</span>
            </span>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>每知识点题数</label>
            <input v-model.number="aiQPerKp" class="input" type="number" min="1" max="5" style="width:80px" />
          </div>
          <div class="form-group">
            <label>题型</label>
            <div style="display:flex;gap:8px;flex-wrap:wrap;padding-top:4px">
              <label v-for="t in aiTypes" :key="t.v"><input type="checkbox" :value="t.v" v-model="aiSelTypes" /> {{ t.l }}</label>
            </div>
          </div>
        </div>
        <div v-if="aiResult" class="ai-result" :class="aiResult.success ? 'success' : 'error'">
          {{ aiResult.message }}
        </div>
        <div class="modal-actions">
          <button class="btn btn-ghost" @click="showAiModal = false">取消</button>
          <button class="btn btn-ai" @click="doAiGenerate" :disabled="aiLoading || !aiPickedIds.length">
            {{ aiLoading ? '生成中...' : '开始生成' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { authStore } from '../stores/auth'
import { useFeedback } from '../composables/useFeedback'

const { tip, ask } = useFeedback()

const router = useRouter()
const questions = ref([])
const loading = ref(true)
const page = ref(1)
const pageSize = ref(20)
const totalPages = ref(0)
const filterType = ref('')
const filterDifficulty = ref('')
const filterTopic = ref('')
const filterKeyword = ref('')
const filterStatus = ref('')
const selectedIds = ref([])
const exporting = ref(false)
const showExportMenu = ref(false)
const saving = ref(false)

// AI 出题
const showAiModal = ref(false)
const aiSearchKw = ref('')
const aiSearchResults = ref([])
const aiPickedKps = ref([])
const aiPickedIds = ref([])
const aiQPerKp = ref(1)
const aiTypes = [{ v: 'choice', l: '选择' }, { v: 'judge', l: '判断' }, { v: 'fill', l: '填空' }, { v: 'subjective', l: '简答' }, { v: 'code', l: '编程' }]
const aiSelTypes = ref(['choice', 'judge', 'fill'])
const aiLoading = ref(false)
const aiResult = ref(null)

let aiSearchTimer = null
let aiSearchSeq = 0
function onAiSearch() {
  clearTimeout(aiSearchTimer)
  const kw = aiSearchKw.value.trim()
  if (!kw) { aiSearchResults.value = []; return }
  aiSearchTimer = setTimeout(async () => {
    const seq = ++aiSearchSeq
    try {
      const r = await api.get(`/knowledge-points/search?keyword=${encodeURIComponent(kw)}`)
      if (seq !== aiSearchSeq) return
      aiSearchResults.value = (r.data || []).filter(kp => !aiPickedIds.value.includes(kp.id))
    } catch { aiSearchResults.value = [] }
  }, 300)
}
function toggleAiKp(kp) {
  if (aiPickedIds.value.includes(kp.id)) {
    aiPickedKps.value = aiPickedKps.value.filter(k => k.id !== kp.id)
    aiPickedIds.value = aiPickedIds.value.filter(id => id !== kp.id)
  } else {
    aiPickedKps.value.push(kp)
    aiPickedIds.value.push(kp.id)
  }
  aiSearchResults.value = aiSearchResults.value.filter(kp => !aiPickedIds.value.includes(kp.id))
}
function removeAiKp(id) {
  aiPickedKps.value = aiPickedKps.value.filter(k => k.id !== id)
  aiPickedIds.value = aiPickedIds.value.filter(i => i !== id)
}
async function doAiGenerate() {
  if (!aiPickedIds.value.length) return
  aiLoading.value = true
  aiResult.value = null
  try {
    const r = await api.post('/llm/generate-questions', {
      knowledge_point_ids: aiPickedIds.value,
      questions_per_kp: aiQPerKp.value,
      question_types: aiSelTypes.value
    })
    aiResult.value = { success: r.success, message: r.message }
    if (r.success) {
      aiPickedKps.value = []
      aiPickedIds.value = []
      doSearch() // 刷新列表
    }
  } catch (e) {
    aiResult.value = { success: false, message: e.message || '生成失败' }
  }
  finally { aiLoading.value = false }
}

// 手动表单知识点选择
const formKpSearch = ref('')
const formKpResults = ref([])
const formKpPickedKps = ref([])
const formKpPickedIds = ref([])
let formKpTimer = null
let formKpSeq = 0
function onFormKpSearch() {
  clearTimeout(formKpTimer)
  const kw = formKpSearch.value.trim()
  if (!kw) { formKpResults.value = []; return }
  formKpTimer = setTimeout(async () => {
    const seq = ++formKpSeq
    try {
      const r = await api.get(`/knowledge-points/search?keyword=${encodeURIComponent(kw)}`)
      if (seq !== formKpSeq) return
      formKpResults.value = (r.data || []).filter(kp => !formKpPickedIds.value.includes(kp.id))
    } catch { formKpResults.value = [] }
  }, 300)
}
function toggleFormKp(kp) {
  if (formKpPickedIds.value.includes(kp.id)) {
    formKpPickedKps.value = formKpPickedKps.value.filter(k => k.id !== kp.id)
    formKpPickedIds.value = formKpPickedIds.value.filter(id => id !== kp.id)
  } else {
    formKpPickedKps.value.push(kp)
    formKpPickedIds.value.push(kp.id)
  }
  formKpResults.value = formKpResults.value.filter(kp => !formKpPickedIds.value.includes(kp.id))
}
function removeFormKp(id) {
  formKpPickedKps.value = formKpPickedKps.value.filter(k => k.id !== id)
  formKpPickedIds.value = formKpPickedIds.value.filter(i => i !== id)
}

// 导入
const showImport = ref(false)
const importFile = ref(null)
const fileInput = ref(null)
const importing = ref(false)
const importResult = ref(null)

// Word 导入
const showWordImport = ref(false)
const wordImportFile = ref(null)
const wordFileInput = ref(null)
const wordImporting = ref(false)
const wordImportResult = ref(null)

// 表单
const showForm = ref(false)
const editingQuestion = ref(null)
const form = ref(getEmptyForm())
const formError = ref('')

// 详情
const detailQuestion = ref(null)

// 批量删除
const showBatchDelete = ref(false)

const allSelected = computed(() => {
  return questions.value.length > 0 && questions.value.every(q => selectedIds.value.includes(q.id))
})

function getEmptyForm() {
  return {
    title: '', type: '',
    options: ['', '', '', ''], is_multi: false,
    answer: '', difficulty: '', explanation: '',
    knowledge_point_name: '', topic: ''
  }
}

function typeLabel(t) {
  const m = { choice: '选择题', judge: '判断题', fill: '填空题', subjective: '主观题' }
  return m[t] || t
}

// 难度星级（1-12 → 1-4 星）
function starLevel(d) {
  if (!d) return 0
  return Math.min(4, Math.max(1, Math.ceil(Number(d) / 3)))
}
function starText(d) {
  const lv = starLevel(d)
  return lv ? '★'.repeat(lv) : ''
}
function passRateClass(rate) {
  if (rate >= 80) return 'pass-high'
  if (rate >= 50) return 'pass-mid'
  return 'pass-low'
}

function statusLabel(s) {
  const m = { pending: '待审核', approved: '已通过', rejected: '已驳回' }
  return m[s] || '已通过'
}

function doApprove(id) {
  ask('确认审核通过此题？', async () => {
    try {
      await api.post(`/questions/${id}/approve`)
      doSearch()
    } catch (e) { tip('审核失败: ' + (e.message || '')) }
  })
}

function doReject(id) {
  ask('确认驳回此题目？', async () => {
    try {
      await api.post(`/questions/${id}/reject`)
      doSearch()
    } catch (e) { tip('驳回失败: ' + (e.message || '')) }
  })
}

onMounted(() => {
  doSearch()
})

async function doSearch() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filterType.value) params.type = filterType.value
    // 难度星级筛选：1星=difficulty 1-3, 2星=4-6, 3星=7-9, 4星=10-12
    if (filterDifficulty.value) {
      const s = Number(filterDifficulty.value)
      params.difficulty_min = (s - 1) * 3 + 1
      params.difficulty_max = s * 3
    }
    if (filterTopic.value) params.topic = filterTopic.value
    if (filterKeyword.value) params.keyword = filterKeyword.value
    if (filterStatus.value) params.status = filterStatus.value
    const r = await api.get('/questions', { params })
    if (r.success) {
      questions.value = r.data.items || []
      totalPages.value = r.data.total_pages || Math.ceil((r.data.total || 0) / pageSize.value)
    }
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

function toggleSelect(id) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

function toggleAll(e) {
  if (e.target.checked) selectedIds.value = questions.value.map(q => q.id)
  else selectedIds.value = []
}

function doDelete(id) {
  ask('确定删除此题？', async () => {
    try {
      await api.delete(`/questions/${id}`)
      questions.value = questions.value.filter(q => q.id !== id)
    } catch (e) { tip('删除失败') }
  })
}

function confirmBatchDelete() {
  showBatchDelete.value = true
}

async function doBatchDelete() {
  saving.value = true
  try {
    await api.post('/questions/batch-delete', { ids: selectedIds.value })
    selectedIds.value = []
    showBatchDelete.value = false
    doSearch()
  } catch (e) { tip('批量删除失败') }
  finally { saving.value = false }
}

async function doExport(fmt) {
  exporting.value = true
  try {
    const idsParam = selectedIds.value.length ? selectedIds.value.join(',') : ''
    const url = `/questions/export/${fmt}${idsParam ? '?ids=' + idsParam : ''}`

    const resp = await fetch(`/api/v1${url}`, { credentials: 'include' })
    if (resp.ok) {
      const blob = await resp.blob()
      const extMap = { excel: 'xlsx', word: 'docx' }
      downloadBlob(blob, `questions.${extMap[fmt] || fmt}`)
    }
  } catch (e) { console.error(e) }
  finally { exporting.value = false }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

function onFileSelect(e) {
  importFile.value = e.target.files?.[0] || null
}

function closeImport() {
  showImport.value = false
  importFile.value = null
  importResult.value = null
  if (fileInput.value) fileInput.value.value = ''
}

async function doImportExcel() {
  if (!importFile.value) return
  importing.value = true
  importResult.value = null
  try {
    const formData = new FormData()
    formData.append('file', importFile.value)
    const resp = await fetch('/api/v1/questions/import/excel', {
      method: 'POST',
      credentials: 'include',
      body: formData
    })
    const r = await resp.json()
    if (r.success) {
      importResult.value = r.data
      if (r.data.success_count > 0) doSearch()
    } else {
      importResult.value = { success_count: 0, error_count: 1, errors: [{ row: 0, message: r.message }] }
    }
  } catch (e) {
    importResult.value = { success_count: 0, error_count: 1, errors: [{ row: 0, message: e.message || '导入失败' }] }
  }
  finally { importing.value = false }
}

function onWordFileSelect(e) {
  wordImportFile.value = e.target.files?.[0] || null
}

function closeWordImport() {
  showWordImport.value = false
  wordImportFile.value = null
  wordImportResult.value = null
  if (wordFileInput.value) wordFileInput.value.value = ''
}

async function doImportWord() {
  if (!wordImportFile.value) return
  wordImporting.value = true
  wordImportResult.value = null
  try {
    const formData = new FormData()
    formData.append('file', wordImportFile.value)
    const resp = await fetch('/api/v1/questions/import/word', {
      method: 'POST',
      credentials: 'include',
      body: formData
    })
    const r = await resp.json()
    if (r.success) {
      wordImportResult.value = r.data
      if (r.data.success_count > 0) doSearch()
    } else {
      wordImportResult.value = { success_count: 0, error_count: 1, errors: [{ row: 0, message: r.message }] }
    }
  } catch (e) {
    wordImportResult.value = { success_count: 0, error_count: 1, errors: [{ row: 0, message: e.message || '导入失败' }] }
  }
  finally { wordImporting.value = false }
}

function openCreate() {
  editingQuestion.value = null
  form.value = getEmptyForm()
  formError.value = ''
  formKpSearch.value = ''
  formKpResults.value = []
  formKpPickedKps.value = []
  formKpPickedIds.value = []
  showForm.value = true
}

function openEdit(q) {
  editingQuestion.value = q
  form.value = {
    title: q.title, type: q.type,
    options: q.options?.length ? [...q.options] : ['', '', '', ''],
    is_multi: !!q.is_multi, answer: q.answer || '',
    category: q.category || '', difficulty: q.difficulty || '', explanation: q.explanation || '',
    knowledge_point_name: q.knowledge_point_name || '', topic: q.topic || ''
  }
  formError.value = ''
  showForm.value = true
}

function openDetail(q) {
  detailQuestion.value = q
}

async function saveQuestion() {
  const f = form.value
  // 从表单知识点选择器构建
  const kpNames = formKpPickedKps.value.map(k => k.properties?.name || k.name)
  const kpIds = [...formKpPickedIds.value]
  if (!f.title.trim()) { formError.value = '请输入题目内容'; return }
  if (!f.type) { formError.value = '请选择题型'; return }
  if (f.type === 'choice' && f.options.filter(o => o.trim()).length < 2) {
    formError.value = '选择题至少需要2个选项'; return
  }
  if (f.type !== 'subjective' && !f.answer.trim()) {
    formError.value = f.type === 'choice' ? '请填写正确答案' : '请输入答案'; return
  }
  formError.value = ''
  saving.value = true
  const payload = {
    title: f.title.trim(), type: f.type,
    answer: f.answer.trim(), difficulty: f.difficulty || null,
    explanation: f.explanation.trim(),
    knowledge_point_name: kpNames.join('、') || f.knowledge_point_name || '',
    knowledge_point_ids: kpIds.length ? kpIds : undefined,
    topic: f.topic || '',
    is_multi: f.type === 'choice' ? f.is_multi : false,
    options: f.type === 'choice' ? f.options.filter(o => o.trim()) : null
  }
  try {
    if (editingQuestion.value) {
      await api.put(`/questions/${editingQuestion.value.id}`, payload)
    } else {
      await api.post('/questions', payload)
    }
    showForm.value = false
    doSearch()
  } catch (e) {
    formError.value = e.message || '保存失败'
  }
  finally { saving.value = false }
}

function goStats() {
  router.push('/statistics')
}
</script>

<style scoped>
.page-container { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }
.page-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; flex-wrap: wrap; gap: 12px; }
.page-top h1 { font-size: 19px; margin: 0; }
.page-subtitle { font-size: 11px; color: var(--text-secondary); margin: 4px 0 0; }
.top-actions { display: flex; gap: 8px; }

.filter-bar {
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
  margin-bottom: 16px; padding: 12px 16px; background: #fff;
  border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.loading-text { text-align: center; padding: 40px; color: var(--text-secondary); }
.empty-msg { text-align: center; padding: 40px; color: var(--text-light); }

.data-table {
  width: 100%; border-collapse: collapse; background: #fff;
  border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.data-table th, .data-table td {
  padding: 10px 14px; text-align: left; font-size: 11px; border-bottom: 1px solid #f1f5f9;
}
.data-table th { background: #f8fafc; font-weight: 600; color: var(--text-secondary); font-size: 11px; }
.data-table tr:last-child td { border-bottom: none; }
.data-table tr:hover td { background: #f8fafc; }

.q-title { font-weight: 500; color: #1e293b; }
.q-title:hover { color: var(--accent-blue); }
.q-options-preview { font-size: 10px; color: var(--text-light); margin-top: 2px; }
.action-cell { display: flex; gap: 6px; }

.type-tag { font-size: 10px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.type-choice { background: #dbeafe; color: #1e40af; }
.type-judge { background: #d1fae5; color: #065f46; }
.type-fill { background: #fef3c7; color: #92400e; }
.type-subjective { background: #ede9fe; color: #5b21b6; }

.status-tag { font-size: 10px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.status-pending { background: #fef3c7; color: #92400e; }
.status-approved { background: #d1fae5; color: #065f46; }
.status-rejected { background: #fee2e2; color: #dc2626; }
.status-label-rejected { font-size: 11px; color: #9ca3af; }

.topic-tag { font-size: 10px; padding: 2px 6px; border-radius: 4px; background: #e0e7ff; color: #3730a3; font-weight: 500; }

/* 难度星级（力扣风格） */
.star-rating { font-size: 11px; letter-spacing: 1px; }
.star-1 { color: #10b981; }
.star-2 { color: #3b82f6; }
.star-3 { color: #f59e0b; }
.star-4 { color: #ef4444; }
.text-muted { color: var(--text-light); }

/* 通过率 */
.pass-rate { font-size: 11px; font-weight: 600; }
.pass-high { color: #16a34a; }
.pass-mid { color: #d97706; }
.pass-low { color: #dc2626; }

.pagination { display: flex; gap: 12px; align-items: center; justify-content: center; margin-top: 20px; }
.page-info { font-size: 11px; color: var(--text-secondary); }

.modal-mask {
  position: fixed; inset: 0; background: rgba(0,0,0,0.35);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal-card {
  background: #fff; border-radius: 10px; padding: 24px; width: 560px; max-height: 85vh; overflow-y: auto;
  box-shadow: 0 8px 30px rgba(0,0,0,0.15);
}
.modal-card.wide { width: 640px; }
.modal-card h4 { margin: 0 0 16px; font-size: 14px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }

.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 11px; font-weight: 500; margin-bottom: 4px; color: var(--text-secondary); }
.form-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
.required { color: #dc2626; }
.option-row { display: flex; gap: 6px; align-items: center; margin-bottom: 4px; }
.opt-label { font-size: 11px; font-weight: 600; width: 18px; color: var(--text-secondary); }
.error-msg { color: #dc2626; font-size: 11px; margin-bottom: 8px; }

.detail-block { margin-bottom: 16px; }
.detail-row { font-size: 11px; margin-bottom: 6px; line-height: 1.6; }
.detail-label { font-weight: 600; color: var(--text-secondary); }

.btn { padding: 8px 16px; font-size: 11px; border-radius: 6px; cursor: pointer; border: 1px solid transparent; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover { background: #2563eb; }
.btn-outline { border-color: #cbd5e1; color: #334155; background: #fff; }
.btn-outline:hover { border-color: #3b82f6; color: #3b82f6; }
.btn-ghost { border-color: #cbd5e1; background: #fff; color: #334155; }
.btn-ghost:hover { background: #f1f5f9; }
.btn-danger { background: #dc2626; color: #fff; }
.btn-danger:hover { background: #b91c1c; }
.btn-sm { padding: 6px 12px; font-size: 11px; }
.btn-xs { padding: 3px 10px; font-size: 10px; }
.btn-danger-text { border: none; color: #dc2626; background: transparent; cursor: pointer; font-size: 10px; }
.btn-danger-text:hover { text-decoration: underline; }
.btn-success-text { border: none; color: #16a34a; background: transparent; cursor: pointer; font-size: 10px; }
.btn-success-text:hover { text-decoration: underline; }
.input { padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 11px; width: 100%; box-sizing: border-box; }
.input-sm { padding: 5px 10px; font-size: 11px; width: auto; }
.input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.1); }
textarea.input { resize: vertical; }

.dropdown-wrap { position: relative; }
.dropdown-menu {
  position: absolute; top: 100%; right: 0; background: #fff; border: 1px solid #e2e8f0;
  border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); z-index: 100; min-width: 120px;
  padding: 4px 0; margin-top: 4px;
}
.dropdown-item {
  padding: 7px 14px; font-size: 11px; cursor: pointer; color: #334155;
}
.dropdown-item:hover { background: #f1f5f9; color: var(--accent-blue); }

.import-result { margin-bottom: 12px; padding: 10px; background: #f8fafc; border-radius: 6px; max-height: 150px; overflow-y: auto; }
.result-line { font-size: 11px; padding: 2px 0; }
.result-line.success { color: #16a34a; }
.result-line.error { color: #dc2626; }
.result-line.warn { color: #92400e; }

.file-upload-area { padding: 12px; border: 2px dashed #cbd5e1; border-radius: 8px; text-align: center; }
.file-upload-area input[type="file"] { font-size: 11px; }
.file-name { font-size: 11px; color: #16a34a; margin: 8px 0 0; }
.file-hint { font-size: 10px; color: var(--text-light); margin: 8px 0 0; }

/* AI modal */
.kp-result-list { max-height:200px;overflow-y:auto;border:1px solid #e2e8f0;border-radius:6px;margin-top:4px; }
.kp-result-item { padding:6px 10px;cursor:pointer;display:flex;justify-content:space-between;border-bottom:1px solid #f1f5f9;font-size: 11px; }
.kp-result-item:hover { background:#f0fdf4; }
.kp-result-item.picked { background:#dcfce7;color:#166534; }
.ai-chips { display:flex;gap:4px;flex-wrap:wrap;margin-top:6px; }
.ai-chip { background:#dbeafe;color:#1e40af;padding:2px 8px;border-radius:4px;font-size: 11px;display:inline-flex;align-items:center;gap:4px; }
.ai-chip-x { cursor:pointer;font-weight:bold; }
.ai-result { padding:8px 12px;border-radius:6px;margin-top:8px;font-size: 11px; }
.ai-result.success { background:#dcfce7;color:#166534; }
.ai-result.error { background:#fee2e2;color:#dc2626; }
.btn-ai { background: linear-gradient(135deg, #8b5cf6, #6366f1); color: #fff; border: none; }
.btn-ai:hover { opacity: 0.9; }
.btn-ai-create { background: linear-gradient(135deg, #10b981, #059669); color: #fff; border: none; }
.btn-ai-create:hover { opacity: 0.9; }
</style>
