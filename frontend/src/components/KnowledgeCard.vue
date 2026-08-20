<template>
  <div class="knowledge-card">
    <!-- 公共头部 -->
    <div class="card-header">
      <!-- 编辑模式 -->
      <template v-if="editing">
        <div class="edit-field">
          <input v-model="editForm.name" class="input input-sm" placeholder="名称 *" />
          <span v-if="editForm.name === '' && submitAttempted" class="inline-err">名称不能为空</span>
        </div>
        <div class="edit-row">
          <select v-model="editForm.category" class="input input-sm">
            <option value="">分类</option>
            <option>基础</option><option>核心</option><option>进阶</option>
            <option>数据结构</option><option>数据科学</option>
          </select>
        </div>
        <textarea v-model="editForm.description" class="input input-sm" rows="3" placeholder="描述"></textarea>
        <textarea v-model="editForm.syntax" class="input input-sm code-input" rows="6" placeholder="语法格式（代码）"></textarea>
        <p v-if="feedbackMsg" :class="feedbackMsg.type">{{ feedbackMsg.text }}</p>
        <div class="edit-actions">
          <button class="btn btn-sm btn-primary" :disabled="saving" @click="doSave">
            {{ saving ? '保存中...' : '保存' }}
          </button>
          <button class="btn btn-sm btn-secondary" @click="cancelEdit">取消</button>
          <button class="btn btn-sm btn-danger" :disabled="deleting" @click="doDelete"
            style="margin-left: auto">
            {{ deleting ? '删除中...' : '删除' }}
          </button>
        </div>
      </template>

      <!-- 显示模式 -->
      <template v-else>
        <div class="node-name-row">
          <h3 class="node-name">{{ node.properties?.name || node.name || '未命名节点' }}</h3>
          <button v-if="!treeMode && authStore.isLoggedIn" class="btn-practice-icon" @click="openPractice" title="AI 练习此知识点">
            AI 练习
          </button>
          <button v-if="!treeMode && isAdmin" class="btn-edit-icon" @click="startEdit" title="编辑此知识点">
            &#9998; 编辑
          </button>
        </div>
        <div class="node-meta">
          <span class="tag" :class="categoryClass">{{ node.properties?.category || '未分类' }}</span>
          <span v-if="node.properties?.source" class="tag tag-source">{{ node.properties.source }}</span>
        </div>
        <p class="node-desc">{{ node.properties?.description }}</p>

        <!-- 语法格式 -->
        <div v-if="node.properties?.syntax" class="section syntax-section">
          <h4 class="section-title">语法格式</h4>
          <pre class="syntax-block"><code>{{ node.properties.syntax }}</code></pre>
        </div>

        <!-- 示例列表 -->
        <div v-if="parsedExamples.length" class="section">
          <h4 class="section-title">示例</h4>
          <div v-for="(ex, idx) in parsedExamples" :key="idx" class="example-item">
            <div class="example-desc">{{ ex.desc }}</div>
            <pre v-if="ex.code" class="code-block"><code>{{ ex.code }}</code></pre>
            <div v-if="ex.output" class="example-output">输出: {{ ex.output }}</div>
          </div>
        </div>

        <!-- 学习资源链接 -->
        <div v-if="parsedMoocLinks.length" class="section">
          <h4 class="section-title">学习资源</h4>
          <div class="resource-links">
            <a v-for="(link, idx) in parsedMoocLinks" :key="idx"
              :href="link.url" target="_blank" rel="noopener"
              class="resource-link">
              {{ link.title || link.url }}
            </a>
          </div>
        </div>
      </template>
    </div>

    <!-- 理论模板 / 实践模板 -->
    <div v-if="!editing">
      <div v-if="isTheory" class="card-theory">
        <div class="section">
          <h4 class="section-title">关键知识点</h4>
          <ul class="point-list">
            <li v-for="(pt, idx) in keyPoints" :key="idx">
              <span class="point-marker">&#8226;</span>
              <span>{{ pt }}</span>
            </li>
          </ul>
        </div>
        <div v-if="prerequisites.length" class="section">
          <h4 class="section-title">前置知识</h4>
          <div class="prereq-tags">
            <span v-for="(pre, idx) in prerequisites" :key="idx" class="tag tag-prereq">{{ pre }}</span>
          </div>
        </div>
      </div>

      <div v-if="isPractice" class="card-practice">
        <div class="section">
          <h4 class="section-title">应用场景</h4>
          <p class="section-desc">{{ practiceScenario }}</p>
        </div>
        <div v-if="relatedPractices.length" class="section">
          <h4 class="section-title">相关实践</h4>
          <div class="prereq-tags">
            <span v-for="(rp, idx) in relatedPractices" :key="idx" class="tag tag-prereq">{{ rp }}</span>
          </div>
        </div>
      </div>

      <div class="section" v-if="node.properties?.code_example">
        <div class="code-block-wrap">
          <div class="code-header">
            <span class="code-lang"></span>
          </div>
          <pre class="code-block"><code>{{ node.properties?.code_example || '' }}</code></pre>
        </div>
      </div>
  </div>
  </div>

  <!-- ===== AI 练习面板（传送到右侧图谱区） ===== -->
  <Teleport to="#practice-target">
  <div v-if="practiceVisible" class="practice-panel" ref="practicePanelRef" :style="panelStyle">
      <!-- 加载中 -->
      <div v-if="practiceLoading" class="practice-loading">
        <div class="practice-spinner"></div>
        <p>AI 出题中...</p>
      </div>

      <!-- 题目展示与作答 -->
      <template v-else-if="practiceState === 'answering'">
        <div class="practice-header" @mousedown="startDrag">
          <span class="drag-handle">⠿</span>
          <h3>AI 练习 - {{ node.properties?.name }}</h3>
          <button class="modal-close-btn" @click="closePractice">&times;</button>
        </div>
        <div class="practice-body">
          <div class="practice-question">
            <span class="pq-type-tag">{{ questionTypeLabel }}</span>
            <p class="pq-title">{{ practiceQuestion.title }}</p>
          </div>

          <!-- 选择题：单选 -->
          <div v-if="practiceQuestion.type === 'choice'" class="practice-options">
            <label
              v-for="(opt, idx) in practiceQuestion.options"
              :key="idx"
              class="po-option"
              :class="{ selected: practiceAnswer === opt }"
            >
              <input type="radio" :value="opt" v-model="practiceAnswer" />
              <span>{{ opt }}</span>
            </label>
          </div>

          <!-- 选择题：多选 -->
          <div v-if="practiceQuestion.type === 'multi_choice'" class="practice-options">
            <label
              v-for="(opt, idx) in practiceQuestion.options"
              :key="idx"
              class="po-option"
              :class="{ selected: practiceMultiAnswer.includes(opt) }"
            >
              <input type="checkbox" :value="opt" v-model="practiceMultiAnswer" />
              <span>{{ opt }}</span>
            </label>
          </div>

          <!-- 判断题 -->
          <div v-if="practiceQuestion.type === 'judge'" class="practice-judge">
            <button
              class="btn-judge"
              :class="{ active: practiceAnswer === '正确' }"
              @click="practiceAnswer = '正确'"
            >正确</button>
            <button
              class="btn-judge"
              :class="{ active: practiceAnswer === '错误' }"
              @click="practiceAnswer = '错误'"
            >错误</button>
          </div>

          <!-- 编程题 -->
          <div v-if="practiceQuestion.type === 'code'" class="practice-code">
            <div v-if="practiceQuestion.code_template" class="pc-template">
              <span class="pc-label">代码模板：</span>
              <pre class="pc-template-code">{{ practiceQuestion.code_template }}</pre>
            </div>
            <textarea
              v-model="practiceAnswer"
              class="pc-editor"
              rows="8"
              placeholder="在此输入你的代码..."
            ></textarea>
          </div>

          <!-- 简答题 -->
          <div v-if="practiceQuestion.type === 'subjective'" class="practice-subjective">
            <textarea
              v-model="practiceAnswer"
              class="ps-editor"
              rows="5"
              placeholder="在此输入你的答案..."
            ></textarea>
          </div>

          <!-- 提交按钮 -->
          <div class="practice-submit">
            <button
              class="btn btn-primary"
              :disabled="practiceSubmitting || !canSubmitAnswer"
              @click="doCheckAnswer"
            >
              {{ practiceSubmitting ? '提交中...' : '提交答案' }}
            </button>
          </div>
        </div>
      </template>

      <!-- 判题结果 -->
      <template v-else-if="practiceState === 'result'">
        <div class="practice-header" :class="practiceResult.correct ? 'result-correct' : 'result-wrong'" @mousedown="startDrag">
          <span class="drag-handle">⠿</span>
          <h3>{{ practiceResult.correct ? '回答正确' : '回答错误' }}</h3>
          <button class="modal-close-btn" @click="closePractice">&times;</button>
        </div>
        <div class="practice-body">
          <div class="practice-question">
            <span class="pq-type-tag">{{ questionTypeLabel }}</span>
            <p class="pq-title">{{ practiceQuestion.title }}</p>
          </div>

          <div class="pr-explanation">
            <h4>解析</h4>
            <p>{{ practiceResult.explanation || '暂无解析' }}</p>
          </div>

          <!-- 对于选择题，显示正确答案 -->
          <div v-if="practiceQuestion.type === 'choice' || practiceQuestion.type === 'multi_choice'" class="pr-answer-display">
            <span class="pr-label">正确答案：</span>
            <span class="pr-value">{{ formatAnswer(practiceQuestion.answer) }}</span>
          </div>

          <div class="pr-actions">
            <button class="btn btn-outline" @click="doNextQuestion">再来一题</button>
            <button class="btn btn-ghost" @click="closePractice">结束练习</button>
          </div>
        </div>
      </template>

      <!-- 错误状态 -->
      <template v-else-if="practiceState === 'error'">
        <div class="practice-header result-wrong" @mousedown="startDrag">
          <span class="drag-handle">⠿</span>
          <h3>出题失败</h3>
          <button class="modal-close-btn" @click="closePractice">&times;</button>
        </div>
        <div class="practice-body">
          <p class="pr-error-msg">{{ practiceError }}</p>
          <div class="pr-actions">
            <button class="btn btn-primary" @click="doNextQuestion">重试</button>
            <button class="btn btn-ghost" @click="closePractice">关闭</button>
          </div>
        </div>
      </template>
    <div class="resize-handle" @mousedown.stop="startResize"></div>
  </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import api from '../api'
import { authStore } from '../stores/auth'
import { useFeedback } from '../composables/useFeedback'

const { tip } = useFeedback()

const props = defineProps({
  node: { type: Object, default: () => ({ properties: {} }) },
  treeMode: { type: Boolean, default: false }
})

const emit = defineEmits(['saved', 'deleted'])

const editing = ref(false)
const saving = ref(false)
const deleting = ref(false)
const submitAttempted = ref(false)
const feedbackMsg = ref(null)
const editForm = ref({ name: '', category: '', description: '', syntax: '' })

const isAdmin = computed(() => authStore.isAdmin)

// ── AI 练习相关 ──
const practiceVisible = ref(false)
const practiceLoading = ref(false)
const practiceState = ref('answering') // 'answering' | 'result' | 'error'
const practiceQuestion = ref({ title: '', type: '', options: [], answer: '', explanation: '', code_template: '' })
const practiceSessionId = ref('')
const practiceAnswer = ref('')
const practiceMultiAnswer = ref([])
const practiceSubmitting = ref(false)
const practiceResult = ref({ correct: false, explanation: '' })
const practiceError = ref('')

const questionTypeLabel = computed(() => {
  const m = {
    choice: '单选题', multi_choice: '多选题', judge: '判断题',
    code: '编程题', subjective: '简答题'
  }
  return m[practiceQuestion.value.type] || practiceQuestion.value.type
})

const canSubmitAnswer = computed(() => {
  if (practiceQuestion.value.type === 'multi_choice') {
    return practiceMultiAnswer.value.length > 0
  }
  return !!practiceAnswer.value
})

function formatAnswer(answer) {
  if (!answer) return ''
  if (Array.isArray(answer)) return answer.join(', ')
  return String(answer)
}

async function openPractice() {
  practiceVisible.value = true
  practiceState.value = 'answering'
  practiceLoading.value = true
  practiceAnswer.value = ''
  practiceMultiAnswer.value = []
  practiceSubmitting.value = false
  practiceResult.value = { correct: false, explanation: '' }
  practiceError.value = ''

  try {
    const r = await api.post('/llm/practice', {
      knowledge_point_id: props.node.id
    })
    if (r.success && r.data && r.data.question) {
      practiceQuestion.value = r.data.question
      practiceSessionId.value = r.data.session_id || ''
      practiceState.value = 'answering'
    } else {
      practiceState.value = 'error'
      practiceError.value = r.message || '获取题目失败'
    }
  } catch (e) {
    practiceState.value = 'error'
    practiceError.value = e.message || '网络错误，请重试'
  } finally {
    practiceLoading.value = false
  }
}

async function doCheckAnswer() {
  practiceSubmitting.value = true
  try {
    let userAnswer = practiceAnswer.value
    if (practiceQuestion.value.type === 'multi_choice') {
      userAnswer = JSON.stringify(practiceMultiAnswer.value)
    }

    const r = await api.post('/llm/practice/check', {
      session_id: practiceSessionId.value,
      question: practiceQuestion.value,
      user_answer: userAnswer
    })
    if (r.success && r.data) {
      practiceResult.value = {
        correct: !!r.data.correct,
        explanation: r.data.explanation || ''
      }
      practiceState.value = 'result'
    } else {
      practiceState.value = 'error'
      practiceError.value = r.message || '判题失败'
    }
  } catch (e) {
    practiceState.value = 'error'
    practiceError.value = e.message || '网络错误，请重试'
  } finally {
    practiceSubmitting.value = false
  }
}

async function doNextQuestion() {
  practiceAnswer.value = ''
  practiceMultiAnswer.value = []
  practiceSubmitting.value = false
  practiceResult.value = { correct: false, explanation: '' }
  practiceError.value = ''
  practiceState.value = 'answering'
  practiceLoading.value = true

  try {
    const r = await api.post('/llm/practice', {
      knowledge_point_id: props.node.id
    })
    if (r.success && r.data && r.data.question) {
      practiceQuestion.value = r.data.question
      practiceSessionId.value = r.data.session_id || ''
      practiceState.value = 'answering'
    } else {
      practiceState.value = 'error'
      practiceError.value = r.message || '获取题目失败'
    }
  } catch (e) {
    practiceState.value = 'error'
    practiceError.value = e.message || '网络错误，请重试'
  } finally {
    practiceLoading.value = false
  }
}

function closePractice() {
  practiceVisible.value = false
  practiceLoading.value = false
  practiceAnswer.value = ''
  practiceMultiAnswer.value = []
}

// ── 拖拽 ──
const practicePanelRef = ref(null)
const panelStyle = ref({})
const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })

function startDrag(e) {
  if (e.target.tagName === 'BUTTON') return
  isDragging.value = true
  const rect = practicePanelRef.value.getBoundingClientRect()
  dragOffset.value = { x: e.clientX - rect.left, y: e.clientY - rect.top }
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  e.preventDefault()
}

function onDrag(e) {
  if (!isDragging.value) return
  panelStyle.value = {
    position: 'fixed',
    left: (e.clientX - dragOffset.value.x) + 'px',
    top: (e.clientY - dragOffset.value.y) + 'px',
    right: 'auto',
    bottom: 'auto',
  }
}

function stopDrag() {
  isDragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

onUnmounted(() => {
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', stopResize)
})

// ── 缩放 ──
const panelSize = ref({ w: 420, h: 0 })
const isResizing = ref(false)

function startResize(e) {
  isResizing.value = true
  const rect = practicePanelRef.value.getBoundingClientRect()
  panelSize.value = { w: rect.width, h: rect.height }
  dragOffset.value = { x: e.clientX, y: e.clientY }
  document.addEventListener('mousemove', onResize)
  document.addEventListener('mouseup', stopResize)
  e.preventDefault()
}

function onResize(e) {
  if (!isResizing.value) return
  const dw = e.clientX - dragOffset.value.x
  const dh = e.clientY - dragOffset.value.y
  panelStyle.value = {
    ...panelStyle.value,
    width: Math.max(320, panelSize.value.w + dw) + 'px',
    height: Math.max(200, panelSize.value.h + dh) + 'px',
    maxHeight: 'none',
  }
}

function stopResize() {
  isResizing.value = false
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', stopResize)
}

// ── 模板逻辑 ──

const isTheory = computed(() => {
  const c = props.node.properties?.category || ''
  return ['基础', '核心', '数据结构'].includes(c)
})

const isPractice = computed(() => {
  const c = props.node.properties?.category || ''
  return ['进阶', '数据科学'].includes(c)
})

const categoryClass = computed(() => {
  const m = {
    '基础': 'node-category-basic', '核心': 'node-category-core',
    '进阶': 'node-category-advanced', '数据结构': 'node-category-structure',
    '数据科学': 'node-category-data'
  }
  return m[props.node.properties?.category] || ''
})

const keyPoints = computed(() => {
  const desc = props.node.properties?.description || ''
  if (!desc || desc.startsWith('包含:')) return []
  return desc.split(/[；;，,]/).filter(s => s.trim()).slice(0, 6)
})

const prerequisites = computed(() => {
  const path = props.node.properties?.textbook_path || ''
  if (!path) return []
  const parts = path.split(' > ')
  if (parts.length <= 2) return []
  return parts.slice(0, -1).filter(p => p !== props.node.properties?.name).slice(-3)
})

const practiceScenario = computed(() => {
  return props.node.properties?.description || '待补充应用场景说明'
})

const relatedPractices = computed(() => {
  const path = props.node.properties?.textbook_path || ''
  if (!path) return []
  const parts = path.split(' > ')
  if (parts.length <= 2) return []
  return parts.slice(1, -1).filter(p => p !== props.node.properties?.name).slice(-3)
})

const parsedExamples = computed(() => {
  try {
    const raw = props.node.properties?.examples
    if (typeof raw === 'string') return JSON.parse(raw)
    if (Array.isArray(raw)) return raw
    return []
  } catch { return [] }
})

const parsedMoocLinks = computed(() => {
  try {
    const raw = props.node.properties?.mooc_links
    if (typeof raw === 'string') return JSON.parse(raw)
    if (Array.isArray(raw)) return raw
    return []
  } catch { return [] }
})

// ── 编辑操作 ──

function startEdit() {
  editForm.value = {
    name: props.node.properties?.name || '',
    category: props.node.properties?.category || '',
    description: props.node.properties?.description || '',
    syntax: props.node.properties?.syntax || ''
  }
  submitAttempted.value = false
  feedbackMsg.value = null
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  submitAttempted.value = false
  feedbackMsg.value = null
}

async function doSave() {
  submitAttempted.value = true
  if (!editForm.value.name) return

  saving.value = true
  feedbackMsg.value = null
  try {
    const body = {
      name: editForm.value.name,
      category: editForm.value.category,
      description: editForm.value.description,
      syntax: editForm.value.syntax
    }
    const r = await api.put(`/knowledge-points/${props.node.id}`, body)
    if (r.success) {
      editing.value = false
      feedbackMsg.value = { type: 'msg-success', text: '保存成功' }
      emit('saved', r.data)
      setTimeout(() => { feedbackMsg.value = null }, 2000)
    } else {
      feedbackMsg.value = { type: 'msg-error', text: r.message || '保存失败' }
    }
  } catch (e) {
    feedbackMsg.value = { type: 'msg-error', text: '网络错误，请重试' }
  } finally {
    saving.value = false
  }
}

async function doDelete() {
  if (!confirm(`确定删除"${props.node.properties?.name}"？将同时删除关联关系`)) return
  deleting.value = true
  try {
    const r = await api.delete(`/knowledge-points/${props.node.id}`)
    if (r.success) {
      emit('deleted', props.node.id)
    }
  } catch (e) { console.error('删除知识点失败:', e); tip('操作失败，请重试') }
  deleting.value = false
}
</script>

<style scoped>
.knowledge-card { margin-top: 4px; }

.card-header { margin-bottom: 16px; }
.node-name-row { display: flex; align-items: center; gap: 8px; }
.node-name {
  font-size: 16px; font-weight: 600; margin-bottom: 8px;
  color: var(--text-primary); flex: 1;
}

.node-meta { display: flex; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.tag { padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 500; }
.tag-source { background: #fef3c7; color: #92400e;
  max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.tag-prereq { background: #e0e7ff; color: #3730a3; }
.node-desc {
  font-size: 11px; color: var(--text-secondary); line-height: 1.6;
  padding: 8px 12px; background: var(--bg-secondary);
  border-radius: var(--radius-sm);
}

/* 编辑按钮 */
.btn-edit-icon {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px; font-size: 11px; font-weight: 500;
  color: var(--accent-blue); background: transparent;
  border: 1px solid var(--accent-blue); border-radius: var(--radius-sm);
  cursor: pointer; transition: all 0.2s; white-space: nowrap;
}
.btn-edit-icon:hover {
  background: var(--accent-blue); color: #fff;
}

/* 编辑模式 */
.edit-field { margin-bottom: 8px; }
.edit-field .input { width: 100%; }
.edit-row { display: flex; gap: 8px; margin-top: 8px; align-items: flex-start; }
.edit-row .input { flex: 1; }
.edit-actions { display: flex; gap: 6px; margin-top: 10px; align-items: center; }
.input-sm { padding: 6px 10px; font-size: 11px; }
.field-label { display: block; font-size: 11px; color: var(--text-secondary); margin-bottom: 4px; font-weight: 500; }
.inline-err { color: #dc2626; font-size: 10px; flex-shrink: 0; margin-left: 4px; }
.msg-success {
  font-size: 11px; color: #16a34a; background: #f0fdf4;
  padding: 6px 10px; border-radius: 4px; margin-top: 4px;
}
.msg-error {
  font-size: 11px; color: #dc2626; background: #fef2f2;
  padding: 6px 10px; border-radius: 4px; margin-top: 4px;
}
.btn-danger { background: #dc2626; color: #fff; }
.btn-danger:hover { background: #b91c1c; }

/* 分类色 */
.node-category-basic { background: #dbeafe; color: #1d4ed8; }
.node-category-core { background: #ede9fe; color: #6d28d9; }
.node-category-advanced { background: #d1fae5; color: #047857; }
.node-category-structure { background: #cffafe; color: #0e7490; }
.node-category-data { background: #fef3c7; color: #b45309; }

/* 模板 */
.card-theory, .card-practice {
  border-top: 1px solid var(--border-color); padding-top: 12px;
}
.section { margin-bottom: 14px; }
.section-title { font-size: 12px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; }
.section-desc { font-size: 11px; color: var(--text-secondary); line-height: 1.6; }
.point-list { list-style: none; padding: 0; }
.point-list li {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 4px 0; font-size: 11px; color: var(--text-secondary); line-height: 1.5;
}
.point-marker { color: var(--accent-blue); flex-shrink: 0; margin-top: 2px; }
.prereq-tags { display: flex; gap: 6px; flex-wrap: wrap; }

.code-input { font-family: 'Consolas', 'Courier New', monospace; }
.code-block-wrap {
  border: 1px solid #1e293b; border-radius: 8px; overflow: hidden;
  background: #0f172a; margin-top: 6px;
}
.code-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 14px; background: #1e293b;
}
.code-lang { font-size: 10px; color: #94a3b8; }
.code-block {
  margin: 0; padding: 14px; font-size: 11px; line-height: 1.7;
  color: #e2e8f0; white-space: pre-wrap; word-break: break-word;
  min-height: 60px;
}
.code-empty { color: #64748b; font-style: italic; }

/* 语法格式 */
.syntax-section { margin-top: 8px; }
.syntax-block {
  margin: 0; padding: 10px 14px; font-size: 11px; line-height: 1.6;
  background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0;
  border-radius: 6px; white-space: pre-wrap; word-break: break-word;
}

/* 示例 */
.example-item { margin-bottom: 10px; }
.example-desc { font-size: 11px; color: var(--text-secondary); margin-bottom: 4px; font-weight: 500; }
.example-output { font-size: 11px; color: #6366f1; margin-top: 4px; padding-left: 4px; }

/* 资源链接 */
.resource-links { display: flex; flex-direction: column; gap: 4px; }
.resource-link {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 6px 10px; font-size: 11px; color: var(--accent-blue);
  background: #eff6ff; border-radius: 6px; text-decoration: none;
  transition: background 0.15s;
}
.resource-link:hover { background: #dbeafe; text-decoration: underline; }
.resource-link::before { content: '🔗'; font-size: 11px; }

/* ── AI 练习按钮 ── */
.btn-practice-icon {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 10px; font-size: 11px; font-weight: 500;
  color: #a78bfa; background: transparent;
  border: 1px solid #a78bfa; border-radius: var(--radius-sm);
  cursor: pointer; transition: all 0.2s; white-space: nowrap;
}
.btn-practice-icon:hover {
  background: #a78bfa; color: #fff;
}

/* ── AI 练习面板（右侧图谱区浮动） ── */
.practice-panel {
  position: absolute;
  bottom: 12px;
  right: 12px;
  width: 420px;
  max-height: 60vh;
  overflow-y: auto;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  color: #e2e8f0;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
  z-index: 100;
}

.resize-handle {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 16px;
  height: 16px;
  cursor: nwse-resize;
  background: linear-gradient(135deg, transparent 50%, #64748b 50%);
  border-radius: 0 0 8px 0;
}

/* 加载 */
.practice-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 24px;
  gap: 16px;
}
.practice-loading p {
  font-size: 13px;
  color: #94a3b8;
}
.practice-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #334155;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 头部 */
.practice-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  border-bottom: 1px solid #334155;
  background: #0f172a;
  cursor: grab;
  user-select: none;
}
.practice-header:active { cursor: grabbing; }
.drag-handle {
  color: #64748b;
  font-size: 12px;
  margin-right: 10px;
  cursor: grab;
  letter-spacing: 2px;
}
.practice-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: #e2e8f0;
  margin: 0;
}
.practice-header.result-correct {
  background: rgba(16,185,129,0.15);
  border-bottom-color: rgba(16,185,129,0.3);
}
.practice-header.result-correct h3 { color: #10b981; }
.practice-header.result-wrong {
  background: rgba(239,68,68,0.15);
  border-bottom-color: rgba(239,68,68,0.3);
}
.practice-header.result-wrong h3 { color: #ef4444; }

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

.practice-body {
  padding: 20px 24px 24px;
}

/* 题目区 */
.practice-question {
  margin-bottom: 20px;
}
.pq-type-tag {
  display: inline-block;
  padding: 2px 10px;
  font-size: 10px;
  font-weight: 600;
  background: rgba(139,92,246,0.2);
  color: #a78bfa;
  border-radius: 4px;
  margin-bottom: 10px;
}
.pq-title {
  font-size: 13px;
  font-weight: 500;
  color: #e2e8f0;
  line-height: 1.7;
  margin: 0;
}

/* 选项 */
.practice-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
}
.po-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.po-option:hover {
  border-color: #475569;
}
.po-option.selected {
  border-color: #3b82f6;
  background: rgba(59,130,246,0.1);
}
.po-option input[type="radio"],
.po-option input[type="checkbox"] {
  accent-color: #3b82f6;
  width: 16px;
  height: 16px;
  cursor: pointer;
  flex-shrink: 0;
}
.po-option span {
  font-size: 12px;
  color: #e2e8f0;
}

/* 判断题 */
.practice-judge {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}
.btn-judge {
  flex: 1;
  padding: 14px 20px;
  font-size: 13px;
  font-weight: 600;
  border: 2px solid #334155;
  border-radius: 8px;
  background: #0f172a;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-judge:hover {
  border-color: #475569;
  color: #e2e8f0;
}
.btn-judge.active {
  border-color: #3b82f6;
  background: rgba(59,130,246,0.15);
  color: #60a5fa;
}

/* 编程题 */
.practice-code {
  margin-bottom: 20px;
}
.pc-template {
  margin-bottom: 12px;
}
.pc-label {
  font-size: 11px;
  color: #94a3b8;
}
.pc-template-code {
  margin: 6px 0 0;
  padding: 10px 14px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  font-size: 11px;
  color: #e2e8f0;
  font-family: 'Consolas', 'Courier New', monospace;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}
.pc-editor {
  width: 100%;
  padding: 12px 14px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  color: #e2e8f0;
  font-size: 12px;
  font-family: 'Consolas', 'Courier New', monospace;
  line-height: 1.6;
  resize: vertical;
}
.pc-editor:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59,130,246,0.2);
}
.pc-editor::placeholder { color: #64748b; }

/* 简答题 */
.practice-subjective {
  margin-bottom: 20px;
}
.ps-editor {
  width: 100%;
  padding: 12px 14px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.6;
  resize: vertical;
  font-family: var(--font-family);
}
.ps-editor:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59,130,246,0.2);
}
.ps-editor::placeholder { color: #64748b; }

/* 提交按钮 */
.practice-submit {
  padding-top: 4px;
}

/* 结果 */
.pr-explanation {
  margin-bottom: 16px;
  padding: 14px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 8px;
}
.pr-explanation h4 {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  margin: 0 0 8px;
}
.pr-explanation p {
  font-size: 12px;
  color: #e2e8f0;
  line-height: 1.7;
  margin: 0;
}

.pr-answer-display {
  margin-bottom: 20px;
  padding: 10px 14px;
  background: rgba(16,185,129,0.1);
  border: 1px solid rgba(16,185,129,0.25);
  border-radius: 6px;
  font-size: 12px;
}
.pr-label {
  color: #94a3b8;
}
.pr-value {
  color: #10b981;
  font-weight: 600;
}

.pr-actions {
  display: flex;
  gap: 10px;
  padding-top: 4px;
}
.pr-actions .btn-outline {
  border-color: #475569;
  color: #cbd5e1;
  background: transparent;
}
.pr-actions .btn-outline:hover {
  border-color: #3b82f6;
  color: #3b82f6;
}
.pr-actions .btn-ghost {
  border-color: transparent;
  color: #94a3b8;
  background: transparent;
}
.pr-actions .btn-ghost:hover {
  color: #e2e8f0;
}

.pr-error-msg {
  font-size: 12px;
  color: #fca5a5;
  margin-bottom: 20px;
}
</style>
