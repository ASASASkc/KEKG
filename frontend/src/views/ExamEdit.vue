<template>
  <div class="page-container">
    <div class="page-top">
      <div>
        <router-link to="/classes" class="back-link">&larr; 返回班级</router-link>
        <h1>{{ isEdit ? '编辑考试' : '新建考试' }}</h1>
      </div>
    </div>

    <UiLoading v-if="loading" />

    <template v-else>
      <!-- 基本信息 -->
      <div class="card form-card">
        <h3>基本信息</h3>
        <div class="form-group">
          <label>考试标题 <span class="required">*</span></label>
          <input v-model="form.title" class="input" placeholder="如：第一单元测试" />
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>班级 <span class="required">*</span></label>
            <select v-model="form.class_id" class="input" :disabled="isEdit">
              <option :value="0">请选择</option>
              <option v-for="c in myClasses" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>任务类型</label>
            <select v-model="form.task_type" class="input">
              <option value="exam">考试</option>
              <option value="homework">作业</option>
            </select>
          </div>
          <div class="form-group" v-if="form.task_type !== 'homework'">
            <label>时长（分钟）</label>
            <input v-model.number="form.duration_minutes" class="input" type="number" min="1" />
          </div>
          <div class="form-group">
            <label>及格分</label>
            <input v-model.number="form.pass_score" class="input" type="number" min="0" max="10000" />
          </div>
          <div class="form-group">
            <label>允许答题次数</label>
            <input v-model.number="form.max_attempts" class="input" type="number" min="1" :placeholder="form.task_type === 'exam' ? '默认1次' : '默认不限'" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>开始时间 <span class="required">*</span></label>
            <input v-model="form.start_time" class="input" type="datetime-local" />
          </div>
          <div class="form-group">
            <label>结束时间 <span class="required">*</span></label>
            <input v-model="form.end_time" class="input" type="datetime-local" />
          </div>
        </div>
        <div class="form-group">
          <label>考试说明</label>
          <textarea v-model="form.description" class="input" rows="2" placeholder="可选"></textarea>
        </div>
      </div>

      <!-- 智能组卷 -->
      <div class="card form-card">
        <h3>智能组卷规则</h3>
        <p class="form-hint">配置每类题型的抽题规则。每题分数 × 数量 = 该题型总分，所有题型总分应合计为 <strong>100 分</strong>。</p>
        <div v-for="(rule, idx) in form.rules" :key="idx" class="rule-row">
          <select v-model="rule.type" class="input input-sm" style="width:110px">
            <option value="">题型</option>
            <option value="choice">选择题</option>
            <option value="judge">判断题</option>
            <option value="fill">填空题</option>
            <option value="subjective">主观题</option>
          </select>
          <input v-model.number="rule.count" class="input input-sm" type="number" min="0" placeholder="数量" style="width:70px" />
          <input v-model.number="rule.score_per_question" class="input input-sm" type="number" min="0" placeholder="每题分" style="width:70px" />
          <span class="rule-subtotal">{{ rule.count * rule.score_per_question || 0 }} 分</span>
          <button class="btn btn-xs btn-ghost" @click="form.rules.splice(idx, 1)">删除</button>
          <div class="rule-extra" v-if="rule.type">
            <span class="extra-label">限定知识点：</span>
            <span v-for="t in topics" :key="t" class="topic-chip" :class="{ active: (rule.topics || []).includes(t) }" @click="toggleTopic(rule, t)">{{ t }}</span>
            <span v-if="!topics.length" class="extra-hint">暂无知识点可选</span>
          </div>
        </div>
        <button class="btn btn-sm btn-outline" @click="addRule">+ 添加规则</button>
        <div class="total-score" :class="{ 'score-ok': totalScore === 100, 'score-warn': totalScore !== 100 }">
          当前总分：<strong>{{ totalScore }}</strong> 分
          <span v-if="totalScore !== 100">（{{ totalScore < 100 ? '还差 ' + (100 - totalScore) + ' 分' : '超出 ' + (totalScore - 100) + ' 分' }}）</span>
          <span v-else class="score-ok-text">总分正确</span>
        </div>
      </div>

      <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>

      <!-- AI 组卷 知识点选择（树形选择器） -->
      <div class="kp-select-section" v-if="!isEdit">
        <label class="kp-select-label">AI 组卷知识点范围（可选，不选则全自动）</label>
        <div class="kp-tags" v-if="examKpPickedKps.length">
          <span v-for="kp in examKpPickedKps" :key="kp.id" class="kp-tag">
            {{ kp.properties?.name || kp.name }}
            <button class="kp-tag-remove" @click="removeExamKp(kp.id)">&times;</button>
          </span>
          <button class="kp-tag kp-clear-all" @click="clearExamKps">清空全部</button>
        </div>
        <button class="btn btn-graph-pick" @click="openExamKpPicker">
          <span class="gp-icon">📂</span>
          {{ examKpPickedKps.length ? '继续选择知识点' : '从知识树中选择知识点' }}
        </button>
      </div>

      <!-- 知识树选择器弹窗 -->
      <div v-if="examKpPickerOpen" class="picker-overlay" @click.self="closeExamKpPicker">
        <div class="picker-modal">
          <div class="picker-header">
            <h3>勾选知识点</h3>
            <span class="picker-count">已选 {{ examKpPickerSelectedIds.size }} / {{ examKpPickerLeafCount }} 个叶子节点</span>
            <button class="btn btn-sm" @click="examKpExpandAll = !examKpExpandAll">{{ examKpExpandAll ? '折叠全部' : '展开全部' }}</button>
            <button class="modal-close-btn" @click="closeExamKpPicker">&times;</button>
          </div>
          <UiLoading v-if="examKpPickerLoading" />
          <div v-else class="picker-tree">
            <TreeNodePicker
              v-for="node in examKpPickerTree.children"
              :key="node.name"
              :node="node"
              :depth="1"
              :expand-all="examKpExpandAll"
              :selected-ids="examKpPickerSelectedIds"
              :leaf-count-map="examKpLeafCountMap"
              @toggle="() => {}"
              @select="onExamKpCheckNode"
            />
          </div>
          <div class="picker-footer">
            <span class="picker-hint">💡 点击箭头展开/折叠 | 勾选叶子节点 | 非叶子节点勾选=选中所有子节点</span>
            <div class="picker-actions">
              <button class="btn btn-primary" @click="confirmExamKpPicker">确认选择（{{ examKpPickerSelectedIds.size }} 个）</button>
            </div>
          </div>
        </div>
      </div>

      <div class="form-actions">
        <router-link to="/classes" class="btn btn-ghost">取消</router-link>
        <button v-if="authStore.isAdmin" class="btn btn-ai" @click="showAiModal = true" title="使用 AI 批量生成题目">
          AI 出题
        </button>
        <button class="btn btn-primary" @click="doCreate" :disabled="savingAI || saving" v-if="!isEdit">
          {{ saving ? '创建中...' : '题库组卷' }}
        </button>
        <button class="btn btn-primary btn-ai-create" @click="doCreateAI" :disabled="saving" v-if="!isEdit">
          {{ savingAI ? 'AI生成中...' : 'AI 直接组卷' }}
        </button>
        <button class="btn btn-primary" @click="doUpdate" :disabled="saving" v-if="isEdit">
          {{ saving ? '保存中...' : '保存修改' }}
        </button>
      </div>
    </template>

    <!-- ===== AI 出题模态框 ===== -->
    <div v-if="showAiModal" class="modal-overlay" @click.self="showAiModal = false">
      <div class="modal ai-modal">
        <div class="ai-modal-header">
          <h3>AI 批量出题</h3>
          <button class="modal-close-btn" @click="closeAiModal">&times;</button>
        </div>

        <div class="ai-modal-body">
          <!-- 知识点搜索与选择 -->
          <div class="ai-section">
            <label class="ai-label">选择知识点</label>
            <div class="kp-search-wrap">
              <input
                v-model="aiSearchKw"
                class="input"
                placeholder="搜索知识点名称..."
                @input="onAiSearchInput"
              />
              <button v-if="aiSearching" class="btn btn-sm btn-ghost" disabled>搜索中...</button>
            </div>

            <!-- 搜索结果 -->
            <div v-if="aiSearchResults.length" class="ai-search-results">
              <div
                v-for="kp in aiSearchResults"
                :key="kp.id"
                class="ai-search-item"
                :class="{ selected: isKpSelected(kp.id) }"
                @click="toggleKp(kp)"
              >
                <span class="ai-kp-name">{{ kp.properties?.name || kp.name }}</span>
                <span class="ai-kp-cat">{{ kp.properties?.category || '' }}</span>
                <span v-if="isKpSelected(kp.id)" class="ai-check">&#10003;</span>
              </div>
            </div>
            <div v-else-if="aiSearchKw && !aiSearching" class="ai-no-result">无匹配结果</div>

            <!-- 已选知识点标签 -->
            <div v-if="aiSelectedKps.length" class="ai-selected-tags">
              <span class="ai-tag-label">已选 {{ aiSelectedKps.length }} 个知识点：</span>
              <span
                v-for="kp in aiSelectedKps"
                :key="kp.id"
                class="ai-tag"
              >
                {{ kp.properties?.name || kp.name }}
                <span class="ai-tag-remove" @click.stop="removeKp(kp.id)">&times;</span>
              </span>
            </div>
          </div>

          <!-- 参数设置 -->
          <div class="ai-section">
            <label class="ai-label">每知识点题数</label>
            <input
              v-model.number="aiQuestionsPerKp"
              class="input"
              type="number"
              min="1"
              max="5"
              style="width: 120px;"
            />
          </div>

          <div class="ai-section">
            <label class="ai-label">题型选择</label>
            <div class="ai-type-checkboxes">
              <label v-for="qt in aiQuestionTypes" :key="qt.value" class="ai-checkbox-label">
                <input type="checkbox" :value="qt.value" v-model="aiSelectedTypes" />
                <span>{{ qt.label }}</span>
              </label>
            </div>
          </div>

          <!-- 生成按钮 -->
          <div class="ai-section ai-actions">
            <button
              class="btn btn-primary"
              @click="doAiGenerate"
              :disabled="aiGenerating || !aiCanGenerate"
            >
              {{ aiGenerating ? '生成中...' : '生成题目' }}
            </button>
          </div>

          <!-- 结果展示 -->
          <div v-if="aiResult" class="ai-result">
            <h4>生成结果</h4>
            <div class="ai-result-grid">
              <div class="ai-stat ai-stat-created">
                <span class="ai-stat-num">{{ aiResult.created }}</span>
                <span class="ai-stat-label">成功</span>
              </div>
              <div class="ai-stat ai-stat-skipped">
                <span class="ai-stat-num">{{ aiResult.skipped }}</span>
                <span class="ai-stat-label">跳过</span>
              </div>
              <div class="ai-stat ai-stat-failed">
                <span class="ai-stat-num">{{ aiResult.failed }}</span>
                <span class="ai-stat-label">失败</span>
              </div>
              <div class="ai-stat ai-stat-total">
                <span class="ai-stat-num">{{ aiResult.total }}</span>
                <span class="ai-stat-label">总计</span>
              </div>
            </div>
            <div v-if="aiResult.failed_kps && aiResult.failed_kps.length" class="ai-failed-kps">
              <p class="ai-failed-title">失败的知识点：</p>
              <span v-for="fkp in aiResult.failed_kps" :key="fkp" class="ai-failed-tag">{{ fkp }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { authStore } from '../stores/auth'
import TreeNodePicker from '../components/TreeNodePicker.vue'
import { useFeedback } from '../composables/useFeedback'

const { tip } = useFeedback()
const route = useRoute()
const router = useRouter()
const eid = computed(() => route.query.edit || '')

const isEdit = computed(() => !!eid.value)
const loading = ref(false)
const saving = ref(false)
const savingAI = ref(false)
const myClasses = ref([])
const topics = ref([])
const errorMsg = ref('')

const form = ref({
  title: '',
  class_id: 0,
  task_type: 'exam',
  duration_minutes: 120,
  pass_score: 60,
  start_time: '',
  end_time: '',
  description: '',
  max_attempts: null,
  rules: [
    { type: 'choice', count: 10, score_per_question: 5 },
        { type: 'judge', count: 10, score_per_question: 2 },
        { type: 'fill', count: 6, score_per_question: 5 }
  ]
})

const totalScore = computed(() => {
  return form.value.rules
    .filter(r => r.type && r.count > 0)
    .reduce((sum, r) => sum + (r.count || 0) * (r.score_per_question || 0), 0)
})

// 当选择作业时，自动将时长设为 0
watch(() => form.value.task_type, (val) => {
  if (val === 'homework') form.value.duration_minutes = 0
})

// ── AI 组卷知识点选择（树形选择器）──
const examKpPickedKps = ref([])
const examKpPickedIds = computed(() => examKpPickedKps.value.map(k => k.id))

const examKpPickerOpen = ref(false)
const examKpPickerLoading = ref(false)
const examKpPickerTree = ref({ children: [] })
const examKpPickerSelectedIds = reactive(new Set())
const examKpPickerLeafCount = ref(0)
const examKpLeafCountMap = reactive({})
const examKpExpandAll = ref(false)

function removeExamKp(id) {
  examKpPickedKps.value = examKpPickedKps.value.filter(k => k.id !== id)
}
function clearExamKps() { examKpPickedKps.value = [] }

async function openExamKpPicker() {
  examKpPickerOpen.value = true
  examKpPickerLoading.value = true
  examKpPickerSelectedIds.clear()
  examKpPickedKps.value.forEach(k => examKpPickerSelectedIds.add(k.id))
  try {
    const r = await api.get('/graph/full-tree')
    if (r.success && r.data) {
      examKpPickerTree.value = r.data
      computeLeafCounts(examKpPickerTree.value, examKpLeafCountMap)
      examKpPickerLeafCount.value = examKpLeafCountMap[examKpPickerTree.value.name] || 0
    }
  } catch (e) { console.error(e); tip('知识树加载失败，请稍后重试') }
  examKpPickerLoading.value = false
}

function computeLeafCounts(node, map) {
  if (!node.children || !node.children.length) { map[node.name] = 1; return 1 }
  let total = 0
  for (const c of node.children) total += computeLeafCounts(c, map)
  map[node.name] = total
  return total
}

function onExamKpCheckNode(node, checked) {
  if (!node.children || !node.children.length) {
    const nid = node._id || node.elementId
    if (!nid) return
    if (checked) examKpPickerSelectedIds.add(nid)
    else examKpPickerSelectedIds.delete(nid)
  } else {
    toggleSubtree(node, checked)
  }
}

function toggleSubtree(node, checked) {
  if (!node.children || !node.children.length) {
    const nid = node._id || node.elementId
    if (nid) { if (checked) examKpPickerSelectedIds.add(nid); else examKpPickerSelectedIds.delete(nid) }
    return
  }
  for (const c of node.children) toggleSubtree(c, checked)
}

function confirmExamKpPicker() {
  const nameMap = {}
  collectNames(examKpPickerTree.value, nameMap)
  const current = new Map(examKpPickedKps.value.map(k => [k.id, k.properties?.name || k.name]))
  examKpPickerSelectedIds.forEach(id => { current.set(id, nameMap[id] || id) })
  examKpPickedKps.value = [...current.entries()].map(([id, name]) => ({ id, name }))
  closeExamKpPicker()
}

function collectNames(node, map) {
  const nid = node._id || node.elementId
  if (nid) map[nid] = node.name
  if (node.children) node.children.forEach(c => collectNames(c, map))
}

function closeExamKpPicker() { examKpPickerOpen.value = false }

// ── AI 出题相关 ──
const showAiModal = ref(false)
const aiSearchKw = ref('')
const aiSearching = ref(false)
const aiSearchResults = ref([])
const aiSelectedKps = ref([])
const aiQuestionsPerKp = ref(3)
const aiSelectedTypes = ref(['choice', 'judge', 'code'])
const aiGenerating = ref(false)
const aiResult = ref(null)

let aiSearchTimer = null
let aiSearchSeq = 0

const aiQuestionTypes = [
  { value: 'choice', label: '单选' },
  { value: 'multi_choice', label: '多选' },
  { value: 'judge', label: '判断' },
  { value: 'code', label: '编程' },
  { value: 'subjective', label: '简答' }
]

const aiCanGenerate = computed(() => {
  return aiSelectedKps.value.length > 0 && aiSelectedTypes.value.length > 0 && aiQuestionsPerKp.value >= 1 && aiQuestionsPerKp.value <= 5
})

function isKpSelected(id) {
  return aiSelectedKps.value.some(k => k.id === id)
}

function toggleKp(kp) {
  const idx = aiSelectedKps.value.findIndex(k => k.id === kp.id)
  if (idx >= 0) {
    aiSelectedKps.value.splice(idx, 1)
  } else {
    aiSelectedKps.value.push(kp)
  }
}

function removeKp(id) {
  const idx = aiSelectedKps.value.findIndex(k => k.id === id)
  if (idx >= 0) aiSelectedKps.value.splice(idx, 1)
}

function onAiSearchInput() {
  clearTimeout(aiSearchTimer)
  aiSearchTimer = setTimeout(() => doAiSearch(), 300)
}

async function doAiSearch() {
  const kw = aiSearchKw.value.trim()
  if (!kw) {
    aiSearchResults.value = []
    return
  }
  const seq = ++aiSearchSeq
  aiSearching.value = true
  try {
    const r = await api.get(`/knowledge-points/search?keyword=${encodeURIComponent(kw)}`)
    if (seq !== aiSearchSeq) return
    if (r.success) {
      aiSearchResults.value = Array.isArray(r.data) ? r.data : (r.data.items || [])
    }
  } catch (e) {
    aiSearchResults.value = []
  } finally {
    aiSearching.value = false
  }
}

async function doAiGenerate() {
  aiResult.value = null
  aiGenerating.value = true
  try {
    const knowledge_point_ids = aiSelectedKps.value.map(k => k.id)
    const r = await api.post('/llm/generate-questions', {
      knowledge_point_ids,
      questions_per_kp: aiQuestionsPerKp.value,
      question_types: aiSelectedTypes.value
    })
    if (r.success) {
      aiResult.value = r.data
    } else {
      aiResult.value = { created: 0, skipped: 0, failed: 0, total: 0, failed_kps: [], error: r.message || '生成失败' }
    }
  } catch (e) {
    aiResult.value = { created: 0, skipped: 0, failed: 0, total: 0, failed_kps: [], error: e.message || '请求失败' }
  } finally {
    aiGenerating.value = false
  }
}

function closeAiModal() {
  showAiModal.value = false
  aiSearchKw.value = ''
  aiSearchResults.value = []
  aiSelectedKps.value = []
  aiResult.value = null
}

onMounted(async () => {
  loading.value = true
  await fetchMyClasses()
  await fetchTopics()

  const cid = route.query.class_id
  if (cid) form.value.class_id = parseInt(cid)

  if (eid.value) {
    try {
      const r = await api.get(`/exams/${eid.value}`)
      if (r.success) {
        const e = r.data
        form.value = {
          title: e.title, class_id: e.class_id,
          task_type: e.task_type || 'exam',
          duration_minutes: e.duration_minutes, pass_score: e.pass_score,
          start_time: e.start_time?.slice(0, 16) || '',
          end_time: e.end_time?.slice(0, 16) || '',
          description: e.description || '',
          rules: []
        }
      }
    } catch (e) { console.error(e); tip('考试信息加载失败，请稍后重试') }
  }
  loading.value = false
})

async function fetchMyClasses() {
  try {
    const r = await api.get('/classes')
    if (r.success) myClasses.value = r.data?.items || r.data
  } catch (e) { console.error('加载班级列表失败:', e); tip('班级加载失败，请稍后重试') }
}

function addRule() {
  form.value.rules.push({ type: '', count: 1, score_per_question: 1, topics: [] })
}

function toggleTopic(rule, t) {
  if (!rule.topics) rule.topics = []
  const idx = rule.topics.indexOf(t)
  if (idx >= 0) rule.topics.splice(idx, 1)
  else rule.topics.push(t)
}

async function fetchTopics() {
  try {
    const r = await api.get('/question-topics')
    if (r.success) topics.value = r.data || []
  } catch (e) { console.error(e); tip('题型加载失败，请稍后重试') }
}

async function doCreate() {
  errorMsg.value = ''
  if (!form.value.title.trim()) { errorMsg.value = '请输入标题'; return }
  if (!form.value.class_id) { errorMsg.value = '请选择班级'; return }
  if (!form.value.start_time || !form.value.end_time) { errorMsg.value = '请选择时间'; return }
  if (form.value.end_time <= form.value.start_time) { errorMsg.value = '结束时间必须晚于开始时间'; return }
  const rules = form.value.rules.filter(r => r.type && r.count > 0)
  if (!rules.length) { errorMsg.value = '请至少添加一条组卷规则'; return }
  if (totalScore.value !== 100) {
    errorMsg.value = `总分必须为 100 分（当前 ${totalScore.value} 分），请调整数量或每题分数`
    return
  }

  saving.value = true
  try {
    const r = await api.post('/exams/generate', {
      ...form.value,
      rules
    })
    if (r.success) {
      router.push(`/classes/${form.value.class_id}`)
    }
  } catch (e) {
    errorMsg.value = e.message || '创建失败'
  }
  finally { saving.value = false }
}

async function doCreateAI() {
  errorMsg.value = ''
  if (!form.value.title.trim()) { errorMsg.value = '请输入标题'; return }
  if (!form.value.class_id) { errorMsg.value = '请选择班级'; return }
  if (!form.value.start_time || !form.value.end_time) { errorMsg.value = '请选择时间'; return }
  if (form.value.end_time <= form.value.start_time) { errorMsg.value = '结束时间必须晚于开始时间'; return }
  const rules = form.value.rules.filter(r => r.type && r.count > 0)
  if (!rules.length) { errorMsg.value = '请至少添加一条组卷规则'; return }
  if (totalScore.value !== 100) {
    errorMsg.value = `总分必须为 100 分（当前 ${totalScore.value} 分），请调整数量或每题分数`
    return
  }

  savingAI.value = true
  errorMsg.value = ''
  try {
    const r = await api.post('/exams/generate-ai', {
      title: form.value.title,
      description: form.value.description,
      rules,
      class_id: form.value.class_id,
      duration_minutes: form.value.duration_minutes,
      pass_score: form.value.pass_score,
      start_time: form.value.start_time,
      end_time: form.value.end_time,
      task_type: form.value.task_type,
      max_attempts: form.value.max_attempts,
      knowledge_point_ids: examKpPickedIds.value,
      knowledge_point_names: examKpPickedKps.value.map(k => k.properties?.name || k.name)
    }, { timeout: 130000 })  // LLM 调用最长 120s，前端留 130s
    if (r.success) {
      router.push(`/classes/${form.value.class_id}`)
    }
  } catch (e) {
    errorMsg.value = e.message || 'AI组卷失败'
  }
  finally { savingAI.value = false }
}

async function doUpdate() {
  errorMsg.value = ''
  if (!form.value.title.trim()) { tip('请输入标题'); return }
  if (!form.value.start_time || !form.value.end_time) { tip('请选择开始和结束时间'); return }
  if (form.value.end_time <= form.value.start_time) { tip('结束时间必须晚于开始时间'); return }
  saving.value = true
  try {
    await api.put(`/exams/${eid.value}`, {
      title: form.value.title, description: form.value.description,
      task_type: form.value.task_type,
      duration_minutes: form.value.duration_minutes, pass_score: form.value.pass_score,
      start_time: form.value.start_time, end_time: form.value.end_time
    })
    router.push(`/classes/${form.value.class_id}`)
  } catch (e) {
    errorMsg.value = e.message || '保存失败'
  }
  finally { saving.value = false }
}

</script>

<style scoped>
.page-container { max-width: 800px; margin: 0 auto; padding: 32px 24px; }
.page-top { margin-bottom: 20px; }
.back-link { font-size: 11px; color: var(--accent-blue); text-decoration: none; display: inline-block; margin-bottom: 8px; }
.back-link:hover { text-decoration: underline; }
.page-top h1 { font-size: 19px; margin: 0; }

.loading-text { text-align: center; padding: 40px; color: var(--text-secondary); }

.form-card { padding: 20px; margin-bottom: 16px; }
.form-card h3 { font-size: 13px; margin: 0 0 14px; }
.form-hint { font-size: 11px; color: var(--text-light); margin-bottom: 12px; }

.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 11px; font-weight: 500; margin-bottom: 4px; color: var(--text-secondary); }
.form-row { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 12px; }
.required { color: #dc2626; }

.rule-row { display: flex; gap: 6px; align-items: center; margin-bottom: 6px; }
.rule-row span { font-size: 11px; color: var(--text-light); }
.rule-subtotal { font-size: 11px; color: var(--text-secondary); min-width: 45px; text-align: right; }
.rule-extra { padding: 4px 0 8px 0; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.extra-label { font-size: 11px; color: var(--text-secondary); }
.extra-hint { font-size: 10px; color: var(--text-light); }
.topic-chip {
  font-size: 10px; padding: 2px 8px; border-radius: 12px; cursor: pointer;
  background: #f1f5f9; color: #64748b; border: 1px solid #e2e8f0; user-select: none;
}
.topic-chip.active { background: #e0e7ff; color: #3730a3; border-color: #a5b4fc; }
.topic-chip:hover { border-color: #94a3b8; }
.total-score { margin-top: 12px; padding: 8px 14px; border-radius: 6px; font-size: 12px; }
.score-ok { background: #d1fae5; color: #065f46; }
.score-warn { background: #fef3c7; color: #92400e; }
.score-ok-text { font-size: 11px; margin-left: 4px; }

.form-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 20px; }
.error-msg { color: #dc2626; font-size: 11px; margin-bottom: 8px; }

.btn { padding: 8px 16px; font-size: 11px; border-radius: 6px; cursor: pointer; border: 1px solid transparent; text-decoration: none; display: inline-block; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover { background: #2563eb; }
.btn-outline { border-color: #cbd5e1; color: #334155; background: #fff; }
.btn-outline:hover { border-color: #3b82f6; color: #3b82f6; }
.btn-ghost { border-color: #cbd5e1; background: #fff; color: #334155; }
.btn-ghost:hover { background: #f1f5f9; }
.btn-sm { padding: 6px 12px; font-size: 11px; }
.btn-xs { padding: 3px 8px; font-size: 10px; }
.input { padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 11px; box-sizing: border-box; }
.input-sm { width: auto; flex-shrink: 0; }
.input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.1); }
textarea.input { resize: vertical; }

/* ── AI 组卷知识点选择（树形选择器）── */
.kp-select-section { margin-bottom: 12px; padding: 10px 12px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; }
.kp-select-label { font-size: 11px; color: #64748b; display: block; margin-bottom: 6px; }
.kp-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; max-height: 120px; overflow-y: auto; }
.kp-tag { background: #dbeafe; color: #1e40af; padding: 2px 8px; border-radius: 4px; font-size: 11px; display: inline-flex; align-items: center; gap: 4px; border: none; cursor: default; }
.kp-tag-remove { background: none; border: none; color: #1e40af; cursor: pointer; font-size: 12px; padding: 0; line-height: 1; }
.kp-tag-remove:hover { color: #dc2626; }
.kp-clear-all { background: #fee2e2; color: #dc2626; cursor: pointer; }
.btn-graph-pick { background: #fff; border: 1px dashed #cbd5e1; color: #64748b; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 11px; }
.btn-graph-pick:hover { border-color: #3b82f6; color: #3b82f6; background: #f0f7ff; }
.gp-icon { font-size: 14px; margin-right: 4px; }

.btn-ai {
  background: linear-gradient(135deg, #8b5cf6, #3b82f6);
  color: #fff;
  border: none;
}
.btn-ai:hover {
  background: linear-gradient(135deg, #7c3aed, #2563eb);
  transform: translateY(-1px);
}

/* ── AI 出题模态框 ── */
.ai-modal {
  width: 560px;
  max-height: 85vh;
  overflow-y: auto;
  padding: 0;
  background: #1e293b;
  border: 1px solid #334155;
  color: #e2e8f0;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}

.ai-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  border-bottom: 1px solid #334155;
}
.ai-modal-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: #e2e8f0;
  margin: 0;
}
.modal-close-btn {
  background: none;
  border: none;
  color: #94a3b8;
  font-size: 19px;
  cursor: pointer;
  line-height: 1;
  padding: 0 4px;
}
.modal-close-btn:hover { color: #e2e8f0; }

.ai-modal-body {
  padding: 20px 24px 24px;
}

.ai-section {
  margin-bottom: 18px;
}
.ai-label {
  display: block;
  font-size: 11px;
  font-weight: 500;
  color: #94a3b8;
  margin-bottom: 8px;
}

/* 知识点搜索 */
.kp-search-wrap {
  display: flex;
  gap: 8px;
  align-items: center;
}
.kp-search-wrap .input {
  flex: 1;
  background: #0f172a;
  border-color: #334155;
  color: #e2e8f0;
}
.kp-search-wrap .input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59,130,246,0.2);
}

.ai-search-results {
  max-height: 180px;
  overflow-y: auto;
  margin-top: 8px;
  border: 1px solid #334155;
  border-radius: 6px;
  background: #0f172a;
}

.ai-search-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.15s;
  border-bottom: 1px solid #1e293b;
}
.ai-search-item:last-child { border-bottom: none; }
.ai-search-item:hover { background: #1e293b; }
.ai-search-item.selected {
  background: rgba(59,130,246,0.15);
}
.ai-kp-name {
  flex: 1;
  font-size: 11px;
  color: #e2e8f0;
}
.ai-kp-cat {
  font-size: 10px;
  color: #64748b;
  padding: 1px 6px;
  background: #1e293b;
  border-radius: 4px;
}
.ai-check {
  color: #3b82f6;
  font-weight: 700;
  font-size: 12px;
}
.ai-no-result {
  margin-top: 8px;
  font-size: 11px;
  color: #64748b;
  padding: 8px 12px;
  background: #0f172a;
  border-radius: 6px;
}

/* 已选知识点标签 */
.ai-selected-tags {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.ai-tag-label {
  font-size: 11px;
  color: #94a3b8;
  margin-right: 4px;
}
.ai-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  font-size: 11px;
  background: rgba(59,130,246,0.15);
  color: #93c5fd;
  border: 1px solid rgba(59,130,246,0.3);
  border-radius: 14px;
}
.ai-tag-remove {
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
  color: #94a3b8;
  margin-left: 2px;
}
.ai-tag-remove:hover { color: #f87171; }

/* 题型多选 */
.ai-type-checkboxes {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.ai-checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 11px;
  color: #cbd5e1;
  user-select: none;
}
.ai-checkbox-label input[type="checkbox"] {
  accent-color: #3b82f6;
  width: 15px;
  height: 15px;
  cursor: pointer;
}

/* 操作按钮区 */
.ai-actions {
  padding-top: 4px;
}

/* 结果展示 */
.ai-result {
  margin-top: 8px;
  padding: 16px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 8px;
}
.ai-result h4 {
  font-size: 12px;
  font-weight: 600;
  color: #e2e8f0;
  margin: 0 0 12px;
}
.ai-result-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}
.ai-stat {
  text-align: center;
  padding: 12px 8px;
  border-radius: 8px;
}
.ai-stat-created { background: rgba(16,185,129,0.15); }
.ai-stat-skipped { background: rgba(245,158,11,0.15); }
.ai-stat-failed { background: rgba(239,68,68,0.15); }
.ai-stat-total { background: rgba(59,130,246,0.15); }
.ai-stat-num {
  display: block;
  font-size: 21px;
  font-weight: 700;
  line-height: 1.2;
}
.ai-stat-created .ai-stat-num { color: #10b981; }
.ai-stat-skipped .ai-stat-num { color: #f59e0b; }
.ai-stat-failed .ai-stat-num { color: #ef4444; }
.ai-stat-total .ai-stat-num { color: #3b82f6; }
.ai-stat-label {
  display: block;
  font-size: 10px;
  color: #94a3b8;
  margin-top: 2px;
}

.ai-failed-kps {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid #334155;
}
.ai-failed-title {
  font-size: 11px;
  color: #94a3b8;
  margin: 0 0 6px;
}
.ai-failed-tag {
  display: inline-block;
  padding: 2px 8px;
  margin: 2px 4px 2px 0;
  font-size: 10px;
  background: rgba(239,68,68,0.15);
  color: #fca5a5;
  border-radius: 4px;
}

/* ── 知识树选择器弹窗 ── */
.picker-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.4); z-index: 1000; display: flex; align-items: center; justify-content: center; }
.picker-modal { background: #fff; border-radius: 12px; width: 620px; max-height: 80vh; display: flex; flex-direction: column; box-shadow: 0 8px 32px rgba(0,0,0,.15); }
.picker-header { display: flex; align-items: center; gap: 12px; padding: 14px 18px; border-bottom: 1px solid #e2e8f0; flex-shrink: 0; }
.picker-header h3 { font-size: 14px; margin: 0; flex-shrink: 0; }
.picker-count { font-size: 11px; color: #64748b; margin-left: auto; }
.picker-loading { text-align: center; padding: 40px; }
.picker-tree { flex: 1; overflow-y: auto; padding: 8px 12px; }
.picker-footer { display: flex; align-items: center; justify-content: space-between; padding: 10px 18px; border-top: 1px solid #e2e8f0; flex-shrink: 0; }
.picker-hint { font-size: 11px; color: #94a3b8; }
.picker-actions { display: flex; gap: 8px; }
.spinner { width: 24px; height: 24px; border: 3px solid #e2e8f0; border-top-color: #3b82f6; border-radius: 50%; animation: spin .6s linear infinite; margin: 0 auto 8px; }
@keyframes spin { to { transform: rotate(360deg); } }

</style>
