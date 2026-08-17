<template>
  <div class="practice-page">
    <!-- 左侧导航 -->
    <div class="left-sidebar" :style="{ width: leftWidth + 'px' }">
      <div class="sidebar-header">
        <h2>练习中心</h2>
      </div>
      <div class="sidebar-nav">
        <button class="nav-item" :class="{ active: activeModule === 'ai' }" @click="switchModule('ai')">
          AI智能出题
        </button>
        <button class="nav-item" :class="{ active: activeModule === 'code' }" @click="switchModule('code')">
          代码练习
        </button>
        <button class="nav-item" :class="{ active: activeModule === 'bank' }" @click="switchModule('bank')">
          题库刷题
        </button>
      </div>

      <!-- AI出题配置 -->
      <div v-if="activeModule === 'ai'" class="sidebar-body">
        <div v-if="state === 'config'" class="config-section">
          <div class="form-group">
            <label>已选知识点（{{ selectedKps.length }} 个）</label>
            <div class="kp-tags" v-if="selectedKps.length">
              <span v-for="kp in selectedKps" :key="kp.id" class="kp-tag">
                {{ kp.name }}
                <button class="kp-tag-remove" @click="removeKp(kp.id)">&times;</button>
              </span>
              <button class="kp-tag kp-clear-all" @click="clearAllKps">清空</button>
            </div>
            <button class="btn btn-graph-pick" @click="openPicker">
              {{ selectedKps.length ? '继续选择知识点' : '从知识树选择知识点' }}
            </button>
          </div>

          <div class="form-group">
            <label>题型</label>
            <div class="type-checkboxes">
              <label v-for="t in questionTypes" :key="t.value" class="type-check">
                <input type="checkbox" :value="t.value" v-model="selectedTypes" />
                <span>{{ t.label }}</span>
              </label>
            </div>
          </div>

          <button class="btn btn-generate" :disabled="!selectedKps.length || generating" @click="doGenerate">
            <span v-if="generating" class="btn-spinner"></span>
            {{ generating ? 'AI 出题中...' : '开始生成练习' }}
          </button>
          <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
        </div>

        <!-- AI答题信息 -->
        <div v-if="state === 'answering'" class="answering-info">
          <div class="info-row">
            <span class="info-label">知识点</span>
            <span class="info-value">{{ result.knowledge_points.slice(0, 5).join('、') }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">难度</span>
            <span class="info-value">{{ result.difficulty }}/12</span>
          </div>
          <div class="info-row">
            <span class="info-label">题目数</span>
            <span class="info-value">{{ result.questions.length }} 题</span>
          </div>
          <button class="btn btn-ghost" @click="resetConfig" style="margin-top:12px;">返回重选</button>
        </div>

        <!-- 结果摘要 -->
        <div v-if="state === 'result'" class="answering-info">
          <div class="score-display" :class="scoreClass">
            <span class="score-big">{{ scoreResult.score }}</span><span class="score-sm">分</span>
          </div>
          <p style="text-align:center;font-size:13px;color:var(--text-light);">
            共 {{ scoreResult.total }} 题，答对 {{ scoreResult.correct }} 题
          </p>
          <button class="btn btn-ghost" @click="resetConfig" style="margin-top:12px;width:100%;">再做一组</button>
        </div>
      </div>

      <!-- 代码编辑器 -->
      <div v-if="activeModule === 'code'" class="sidebar-body">
        <!-- 我的代码片段 -->
        <div class="snippet-section">
          <div class="section-label" @click="snippetExpanded = !snippetExpanded">
            <span class="toggle-arrow">{{ snippetExpanded ? '▼' : '▶' }}</span>
            我的片段 <span class="count-text">({{ snippets.length }})</span>
          </div>
          <div v-if="snippetsLoading" class="list-hint">加载中...</div>
          <div v-if="snippetExpanded && !snippetsLoading" class="snippet-list">
            <div v-for="snip in snippets" :key="snip.id" class="snippet-item"
                 :class="{ active: currentSnippetId === snip.id }"
                 @click="openSnippet(snip)">
              <div class="snip-title">{{ snip.title }}</div>
              <div class="snip-meta">{{ (snip.updated_at || '').slice(0, 10) }}</div>
              <button class="snip-delete" @click.stop="deleteSnippet(snip)" title="删除">&times;</button>
            </div>
            <div v-if="!snippets.length" class="list-hint">暂无保存的片段</div>
          </div>
        </div>

        <!-- 编程习题（折叠） -->
        <div class="exercise-section" style="margin-top:16px;">
          <div class="section-label" @click="exerciseExpanded = !exerciseExpanded">
            <span class="toggle-arrow">{{ exerciseExpanded ? '▼' : '▶' }}</span>
            编程习题
            <button class="btn btn-xs btn-primary" @click.stop="showCreateCodeModal = true" style="margin-left:auto;" v-if="exerciseExpanded">+ 新建</button>
          </div>
          <div v-if="exerciseExpanded" class="code-exercise-list" style="margin-top:6px;">
            <div class="exercise-filter">
              <button class="filter-btn" :class="{ active: !myOnly }" @click="switchExerciseFilter(false)">全部</button>
              <button class="filter-btn" :class="{ active: myOnly }" @click="switchExerciseFilter(true)">我的</button>
            </div>
            <div v-if="codeLoading" class="list-hint">加载中...</div>
            <div v-for="ex in codeExercises" :key="ex.id" class="code-item"
                 :class="{ active: selectedCodeEx?.id === ex.id }"
                 @click="selectCodeExercise(ex)">
              <div class="ci-title">{{ ex.title }}</div>
              <div class="ci-meta">
                <span class="ci-lang">{{ ex.language || 'python' }}</span>
                <span class="ci-diff">难度 {{ '★'.repeat(ex.difficulty || 1) }}</span>
                <span class="ci-author" v-if="ex.created_by_name">@{{ ex.created_by_name }}</span>
              </div>
            </div>
            <div v-if="!codeLoading && !codeExercises.length" class="list-hint">暂无练习题</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 可拖拽分界线 -->
    <div class="splitter" @mousedown="startResize"></div>

    <!-- 右侧内容区 -->
    <div class="right-content">
      <!-- AI练习模块 -->
      <template v-if="activeModule === 'ai'">
        <!-- 答题区 -->
        <div v-if="state === 'answering'" class="content-panel">
          <div class="content-header">
            <div class="content-title">AI 练习题</div>
            <button class="btn btn-submit" :disabled="submitting" @click="doSubmit">
              {{ submitting ? '判题中...' : '提交答案' }}
            </button>
          </div>

          <div v-for="(q, qi) in result.questions" :key="q.id" class="question-card">
            <div class="q-header">
              <span class="q-num">{{ qi + 1 }}</span>
              <span class="q-type-badge">{{ typeLabel(q.type) }}</span>
            </div>
            <p class="q-title">{{ q.title }}</p>
            <div v-if="q.type === 'choice'" class="q-options">
              <label v-for="(opt, oi) in q.options" :key="oi" class="q-opt" :class="{ picked: answerMap[q.id] === opt }">
                <input type="radio" :name="'q' + q.id" :value="opt" v-model="answerMap[q.id]" /><span>{{ opt }}</span>
              </label>
            </div>
            <div v-if="q.type === 'multi_choice'" class="q-options">
              <label v-for="(opt, oi) in q.options" :key="oi" class="q-opt" :class="{ picked: multiMap[q.id]?.includes(opt) }">
                <input type="checkbox" :value="opt" v-model="multiMap[q.id]" /><span>{{ opt }}</span>
              </label>
            </div>
            <div v-if="q.type === 'judge'" class="q-judge">
              <label class="q-opt" :class="{ picked: answerMap[q.id] === '对' }">
                <input type="radio" :name="'q' + q.id" value="对" v-model="answerMap[q.id]" /><span>对 / 正确</span>
              </label>
              <label class="q-opt" :class="{ picked: answerMap[q.id] === '错' }">
                <input type="radio" :name="'q' + q.id" value="错" v-model="answerMap[q.id]" /><span>错 / 错误</span>
              </label>
            </div>
            <div v-if="q.type === 'subjective'" class="q-subj">
              <textarea v-model="answerMap[q.id]" class="form-textarea" rows="3" placeholder="请输入你的答案..."></textarea>
            </div>
          </div>
        </div>

        <!-- 结果区 -->
        <div v-if="state === 'result'" class="content-panel">
          <div class="score-msg-text">{{ scoreMsg }}</div>
          <div v-for="(d, di) in scoreResult.details" :key="di" class="result-card" :class="d.is_correct ? 'rc-ok' : 'rc-err'">
            <div class="rc-header">
              <span class="rc-num">{{ di + 1 }}</span>
              <span class="rc-icon">{{ d.is_correct ? '✓' : '✗' }}</span>
              <span class="rc-type">{{ typeLabel(d.type) }}</span>
            </div>
            <p class="rc-title">{{ d.title }}</p>
            <div class="rc-detail">
              <p><strong>你的答案：</strong><span :class="d.is_correct ? 'text-ok' : 'text-err'">{{ d.your_answer || '未作答' }}</span></p>
              <p v-if="!d.is_correct"><strong>正确答案：</strong><span class="text-ok">{{ d.correct_answer }}</span></p>
            </div>
            <div v-if="d.explanation" class="rc-explanation"><strong>解析：</strong>{{ d.explanation }}</div>
          </div>
        </div>

        <!-- 配置空状态 -->
        <div v-if="state === 'config'" class="content-panel placeholder-panel">
          <div class="placeholder-icon">📝</div>
          <p>从左侧选择知识点并配置题型，AI 将为你生成专属练习题</p>
        </div>
      </template>

      <!-- 代码编辑器模块 -->
      <template v-if="activeModule === 'code'">
        <div class="content-panel code-editor-panel">
          <div class="content-header">
            <div class="content-title">{{ editorTitle }}</div>
            <div class="header-actions">
              <button class="btn btn-sm btn-primary" @click="runCode" :disabled="codeRunning">▶ 运行</button>
              <button class="btn btn-sm" @click="saveSnippet" :disabled="codeRunning" style="margin-left:6px;">💾 保存</button>
              <button v-if="selectedCodeEx" class="btn btn-sm btn-submit" @click="submitCode" :disabled="codeRunning" style="margin-left:6px;">提交习题</button>
            </div>
          </div>

          <!-- 习题描述 -->
          <div class="exercise-desc" v-if="selectedCodeEx?.description">{{ selectedCodeEx.description }}</div>

          <!-- 代码编辑器（始终可见） -->
          <div class="code-editor-wrapper">
            <div class="line-numbers" ref="lineNumbers" @scroll="syncEditorScroll">
              <div v-for="n in lineCount" :key="n" class="line-num">{{ n }}</div>
            </div>
            <textarea v-model="codeText" class="code-textarea code-textarea-pro"
                      placeholder="# 在此编写你的 Python 代码..." spellcheck="false"
                      ref="codeEditor" @scroll="syncLineScroll" @keydown="handleTab"></textarea>
          </div>

          <!-- 输出面板 -->
          <div class="output-panel" v-if="codeOutput">
            <div class="output-section-label">输入</div>
            <pre class="output-content input-content">{{ codeText }}</pre>
            <div class="output-metrics">
              <span>运行时间: {{ codeMetrics.execTime }}ms</span>
            </div>
            <div class="output-section-label">输出</div>
            <pre class="output-content" :class="{ 'output-error': codeOutputError }">{{ codeOutput }}</pre>
          </div>

          <!-- 答案区 - 仅提交习题后可见 -->
          <div v-if="codeSubmitted && selectedCodeEx" style="margin-top:16px;">
            <h3 style="font-size:14px;margin-bottom:8px;">答案参考</h3>
            <div class="answer-tabs">
              <button class="tab-sm" :class="{ active: codeAnswerTab === 'ai' }" @click="codeAnswerTab = 'ai'">AI答案</button>
              <button class="tab-sm" :class="{ active: codeAnswerTab === 'users' }" @click="codeAnswerTab = 'users'">用户答案</button>
            </div>
            <div v-if="codeAnswerTab === 'ai'" style="margin-top:10px;">
              <button v-if="!aiCodeAnswer" class="btn btn-sm btn-primary" @click="generateAIAnswer" :disabled="aiAnswerLoading" style="margin-bottom:10px;">
                {{ aiAnswerLoading ? '生成中...' : '生成AI答案' }}
              </button>
              <pre v-if="aiCodeAnswer" class="answer-code">{{ aiCodeAnswer }}</pre>
              <div v-else-if="!aiAnswerLoading" class="list-hint">点击生成AI参考答案</div>
            </div>
            <div v-if="codeAnswerTab === 'users'" style="margin-top:10px;">
              <div v-for="ans in userCodeAnswers" :key="ans.id" class="answer-card">
                <div class="answer-info">
                  <span>{{ ans.username || '匿名用户' }}</span>
                  <span class="answer-type-tag">{{ ans.answer_type === 'ai' ? 'AI' : '用户' }}</span>
                </div>
                <pre class="answer-code">{{ ans.code }}</pre>
                <div v-if="ans.explanation" class="answer-exp">{{ ans.explanation }}</div>
              </div>
              <div v-if="!userCodeAnswers.length" class="list-hint">暂无用户分享的答案</div>
              <div style="margin-top:12px;padding:10px;border:1px solid var(--border-subtle);border-radius:6px;">
                <textarea v-model="shareCodeText" class="share-input" placeholder="分享你的代码..."></textarea>
                <textarea v-model="shareExplanation" class="share-input" placeholder="说明（可选）..." style="margin-top:4px;"></textarea>
                <button class="btn btn-sm btn-primary" @click="shareCodeAnswer" style="margin-top:6px;">分享答案</button>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- 题库刷题模块 -->
      <template v-if="activeModule === 'bank'">
        <PracticeCenter class="bank-panel" />
      </template>
    </div>

    <!-- 知识树选择器弹窗 -->
    <div v-if="pickerOpen" class="picker-overlay" @click.self="closePicker">
      <div class="picker-modal">
        <div class="picker-header">
          <h3>勾选知识点</h3>
          <span class="picker-count">已选 {{ pickerSelectedIds.size }} / {{ pickerLeafCount }} 个叶子节点</span>
          <button class="btn btn-sm" @click="toggleExpandAll">{{ pickerExpandAll ? '折叠全部' : '展开全部' }}</button>
          <button class="modal-close-btn" @click="closePicker">&times;</button>
        </div>
        <div v-if="pickerLoading" class="picker-loading">
          <div class="spinner"></div><p>加载知识树...</p>
        </div>
        <div v-else class="picker-tree">
          <TreeNodePicker
            v-for="node in pickerTree.children"
            :key="node.name"
            :node="node" :depth="1" :expand-all="pickerExpandAll"
            :selected-ids="pickerSelectedIds" :leaf-count-map="pickerLeafCountMap"
            @toggle="onToggleNode" @select="onCheckNode"
          />
        </div>
        <div class="picker-footer">
          <span class="picker-hint">点击箭头展开/折叠 | 勾选叶子节点</span>
          <div class="picker-actions">
            <button class="btn btn-primary" @click="confirmPicker">确认选择（{{ pickerSelectedIds.size }} 个）</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 保存代码片段弹窗 -->
    <div v-if="showSaveSnippetModal" class="picker-overlay" @click.self="showSaveSnippetModal = false">
      <div class="picker-modal" style="height:auto;max-width:400px;">
        <div class="picker-header">
          <h3>保存代码片段</h3>
          <button class="modal-close-btn" @click="showSaveSnippetModal = false">&times;</button>
        </div>
        <div style="padding:16px;">
          <div class="form-group">
            <label>片段名称</label>
            <input v-model="snippetTitleInput" class="input" style="width:100%;box-sizing:border-box;" @keyup.enter="doSaveSnippet" autofocus />
          </div>
          <div style="text-align:right;margin-top:12px;">
            <button class="btn" @click="showSaveSnippetModal = false" style="margin-right:8px;">取消</button>
            <button class="btn btn-primary" @click="doSaveSnippet">保存</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 新建代码题弹窗 -->
    <div v-if="showCreateCodeModal" class="picker-overlay" @click.self="showCreateCodeModal = false">
      <div class="picker-modal" style="height:auto;max-height:80vh;">
        <div class="picker-header">
          <h3>新建练习题</h3>
          <button class="modal-close-btn" @click="showCreateCodeModal = false">&times;</button>
        </div>
        <div style="padding:16px;overflow-y:auto;">
          <div class="form-group"><label>标题</label><input v-model="newCodeEx.title" class="input" style="width:100%;box-sizing:border-box;" /></div>
          <div class="form-group"><label>描述</label><textarea v-model="newCodeEx.description" class="form-textarea" rows="3"></textarea></div>
          <div class="form-group"><label>模板代码</label><textarea v-model="newCodeEx.template_code" class="form-textarea code-input" rows="5" placeholder="# 初始代码模板..." style="font-family:monospace;"></textarea></div>
          <div class="form-group"><label>难度 (1-5)</label><input v-model.number="newCodeEx.difficulty" class="input" type="number" min="1" max="5" style="width:80px;" /></div>
          <div style="text-align:right;margin-top:12px;">
            <button class="btn" @click="showCreateCodeModal = false" style="margin-right:8px;">取消</button>
            <button class="btn btn-primary" @click="createCodeExercise">创建</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import TreeNodePicker from '../components/TreeNodePicker.vue'
import PracticeCenter from './PracticeCenter.vue'
import { useFeedback } from '../composables/useFeedback'

const { tip, ask } = useFeedback()

const router = useRouter()
import { authStore } from '../stores/auth'

// ── 模块切换 ──
const activeModule = ref('ai')
const leftWidth = ref(300)
let isResizing = false

function startResize(e) {
  isResizing = true
  document.addEventListener('mousemove', onResize)
  document.addEventListener('mouseup', stopResize)
  e.preventDefault()
}

function onResize(e) {
  if (!isResizing) return
  const w = Math.max(220, Math.min(500, e.clientX))
  leftWidth.value = w
}

function stopResize() {
  isResizing = false
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', stopResize)
}

function switchModule(mod) {
  activeModule.value = mod
  if (mod === 'code') {
    if (!codeExercises.value.length) loadCodeExercises()
    if (!snippets.value.length && !snippetsLoading.value) loadSnippets()
  }
}

// ── AI 练习状态 ──
const state = ref('config')
const errorMsg = ref('')
const generating = ref(false)
const submitting = ref(false)

const selectedKps = ref([])
const questionTypes = [
  { value: 'choice', label: '选择题' },
  { value: 'multi_choice', label: '多选题' },
  { value: 'judge', label: '判断题' },
  { value: 'subjective', label: '简答题' },
]
const selectedTypes = ref([])

const result = reactive({ session_id: '', knowledge_points: [], difficulty: 0, questions: [] })
const answerMap = reactive({})
const multiMap = reactive({})
const scoreResult = reactive({ total: 0, correct: 0, score: 0, details: [] })

const typeMap = { choice: '单选', multi_choice: '多选', judge: '判断', subjective: '简答' }
function typeLabel(t) { return typeMap[t] || t }

const scoreClass = computed(() => {
  if (scoreResult.score >= 80) return 'score-high'
  if (scoreResult.score >= 60) return 'score-mid'
  return 'score-low'
})
const scoreMsg = computed(() => {
  if (scoreResult.score >= 90) return '非常棒！你对这些知识点掌握得很好！'
  if (scoreResult.score >= 70) return '不错！继续加油，巩固薄弱环节。'
  if (scoreResult.score >= 50) return '还需努力，建议复习相关知识点后再试。'
  return '建议重新学习这些知识点，再来挑战。'
})

// ── 代码编辑器状态 ──
const codeExercises = ref([])
const codeLoading = ref(false)
const myOnly = ref(false)
const selectedCodeEx = ref(null)
const codeText = ref('')
const codeOutput = ref('')
const codeOutputError = ref(false)
const codeRunning = ref(false)
const codeMetrics = ref({ execTime: 0, memory: 0 })
const codeSubmitted = ref(false)
const codeAnswerTab = ref('ai')
const codeEditor = ref(null)
const lineNumbers = ref(null)

// 代码片段
const snippets = ref([])
const snippetsLoading = ref(false)
const currentSnippetId = ref(0)
const showSaveSnippetModal = ref(false)
const snippetTitleInput = ref('')

// 折叠状态
const snippetExpanded = ref(true)
const exerciseExpanded = ref(false)

// 编辑器标题
const editorTitle = computed(() => {
  if (selectedCodeEx.value) return selectedCodeEx.value.title
  return '代码编辑器'
})

const lineCount = computed(() => {
  const lines = codeText.value.split('\n')
  return Math.max(lines.length, 20)
})

function syncLineScroll() {
  if (lineNumbers.value && codeEditor.value) {
    lineNumbers.value.scrollTop = codeEditor.value.scrollTop
  }
}
function syncEditorScroll() {
  if (codeEditor.value && lineNumbers.value) {
    codeEditor.value.scrollTop = lineNumbers.value.scrollTop
  }
}
function handleTab(e) {
  if (e.key === 'Tab') {
    e.preventDefault()
    const ta = e.target
    const start = ta.selectionStart
    const end = ta.selectionEnd
    codeText.value = codeText.value.substring(0, start) + '    ' + codeText.value.substring(end)
    setTimeout(() => { ta.selectionStart = ta.selectionEnd = start + 4 }, 0)
  }
}
const aiCodeAnswer = ref('')
const aiAnswerLoading = ref(false)
const userCodeAnswers = ref([])
const shareCodeText = ref('')
const shareExplanation = ref('')
const showCreateCodeModal = ref(false)
const newCodeEx = ref({ title: '', description: '', template_code: '', difficulty: 1 })

// ── 知识树选择器 ──
const pickerOpen = ref(false)
const pickerLoading = ref(false)
const pickerTree = ref({ children: [] })
const pickerSelectedIds = reactive(new Set())
const pickerLeafCount = ref(0)
const pickerLeafCountMap = reactive({})
const pickerExpandAll = ref(false)

function removeKp(id) { selectedKps.value = selectedKps.value.filter(k => k.id !== id) }
function clearAllKps() { selectedKps.value = [] }

async function openPicker() {
  pickerOpen.value = true
  pickerLoading.value = true
  pickerSelectedIds.clear()
  selectedKps.value.forEach(k => pickerSelectedIds.add(k.id))
  try {
    const r = await api.get('/graph/full-tree')
    if (r.success && r.data) {
      pickerTree.value = r.data
      computeLeafCounts(pickerTree.value, pickerLeafCountMap)
      pickerLeafCount.value = pickerLeafCountMap[pickerTree.value.name] || 0
    }
  } catch (e) { console.error(e) }
  pickerLoading.value = false
}

function computeLeafCounts(node, map) {
  if (!node.children || !node.children.length) { map[node.name] = 1; return 1 }
  let total = 0
  for (const c of node.children) total += computeLeafCounts(c, map)
  map[node.name] = total
  return total
}

function onToggleNode() {}
function onCheckNode(node, checked) {
  if (!node.children || !node.children.length) {
    const nid = node._id || node.elementId
    if (!nid) return
    if (checked) pickerSelectedIds.add(nid)
    else pickerSelectedIds.delete(nid)
  } else {
    toggleSubtree(node, checked)
  }
}
function toggleSubtree(node, checked) {
  if (!node.children || !node.children.length) {
    const nid = node._id || node.elementId
    if (nid) { if (checked) pickerSelectedIds.add(nid); else pickerSelectedIds.delete(nid) }
    return
  }
  for (const c of node.children) toggleSubtree(c, checked)
}

function confirmPicker() {
  const nameMap = {}
  collectNames(pickerTree.value, nameMap)
  const current = new Map(selectedKps.value.map(k => [k.id, k.name]))
  pickerSelectedIds.forEach(id => { current.set(id, nameMap[id] || id) })
  selectedKps.value = [...current.entries()].map(([id, name]) => ({ id, name }))
  closePicker()
}
function collectNames(node, map) {
  const nid = node._id || node.elementId
  if (nid) map[nid] = node.name
  if (node.children) node.children.forEach(c => collectNames(c, map))
}
function toggleExpandAll() { pickerExpandAll.value = !pickerExpandAll.value }
function closePicker() { pickerOpen.value = false }

// ── AI 生成 / 提交 ──
async function doGenerate() {
  if (!selectedKps.value.length) return
  generating.value = true; errorMsg.value = ''
  try {
    const payload = {
      knowledge_point_ids: selectedKps.value.map(k => k.id),
      total_questions: selectedTypes.value.length,
      question_types: selectedTypes.value.length ? selectedTypes.value : null,
    }
    const r = await api.post('/practice/generate', payload)
    if (r.success) {
      result.session_id = r.data.session_id
      result.knowledge_points = r.data.knowledge_points
      result.difficulty = r.data.difficulty
      result.questions = r.data.questions
      Object.keys(answerMap).forEach(k => delete answerMap[k])
      Object.keys(multiMap).forEach(k => delete multiMap[k])
      r.data.questions.forEach(q => {
        if (q.type === 'multi_choice') multiMap[q.id] = []
        else answerMap[q.id] = ''
      })
      state.value = 'answering'; window.scrollTo(0, 0)
    } else { errorMsg.value = r.message || '生成失败' }
  } catch (e) { errorMsg.value = e.message || '网络错误' }
  generating.value = false
}

async function doSubmit() {
  submitting.value = true
  try {
    const extractLetter = (opt) => {
      if (!opt) return ''
      const m = opt.match(/^([A-Z])[.、)]/)
      return m ? m[1] : opt
    }
    const answers = result.questions.map(q => ({
      question_id: q.id,
      answer: q.type === 'multi_choice'
        ? (multiMap[q.id] || []).map(extractLetter).join(',')
        : extractLetter(answerMap[q.id] || ''),
    }))
    const r = await api.post('/practice/submit', { session_id: result.session_id, answers })
    if (r.success) {
      scoreResult.total = r.data.total; scoreResult.correct = r.data.correct
      scoreResult.score = r.data.score; scoreResult.details = r.data.details
      state.value = 'result'; window.scrollTo(0, 0)
    } else { tip(r.message || '提交失败') }
  } catch (e) { tip(e.message || '网络错误') }
  submitting.value = false
}

function resetConfig() { state.value = 'config'; errorMsg.value = '' }

// ── 代码练习 ──
async function loadCodeExercises() {
  codeLoading.value = true
  try {
    const params = myOnly.value ? { my: '1' } : {}
    const r = await api.get('/code-exercises', { params })
    if (r.success) codeExercises.value = r.data?.items || []
  } catch (e) { console.error('加载代码练习失败:', e) }
  codeLoading.value = false
}

function switchExerciseFilter(showMy) {
  myOnly.value = showMy
  loadCodeExercises()
}

async function selectCodeExercise(ex) {
  selectedCodeEx.value = ex
  currentSnippetId.value = 0
  codeText.value = ex.template_code || ''
  codeOutput.value = ''
  codeOutputError.value = false
  codeMetrics.value = { execTime: 0, memory: 0 }
  codeSubmitted.value = false
  aiCodeAnswer.value = ''
  userCodeAnswers.value = []
  loadExistingAnswers()
}

async function loadExistingAnswers() {
  if (!selectedCodeEx.value) return
  try {
    const r = await api.get(`/code-exercises/${selectedCodeEx.value.id}/answers`)
    if (r.success && r.data) {
      userCodeAnswers.value = r.data.filter(a => a.answer_type !== 'ai') || []
      const aiAns = r.data.find(a => a.answer_type === 'ai')
      if (aiAns) aiCodeAnswer.value = aiAns.code
    }
  } catch (e) { /* ignore */ }
}

async function runCode() {
  codeRunning.value = true
  codeOutput.value = '运行中...'
  codeOutputError.value = false
  codeMetrics.value = { execTime: 0, memory: 0 }
  try {
    const r = await api.post('/code-run', { code: codeText.value, language: 'python' })
    codeOutput.value = (r.data && r.data.output) || '(无输出)'
    codeOutputError.value = !!(r.data && r.data.error)
    codeMetrics.value = {
      execTime: (r.data && r.data.exec_time) || 0,
      memory: (r.data && r.data.memory) || 0
    }
  } catch (e) {
    codeOutput.value = '运行失败: ' + (e.message || '未知错误')
    codeOutputError.value = true
  }
  codeRunning.value = false
}

async function submitCode() {
  if (!selectedCodeEx.value) return
  codeRunning.value = true
  try {
    const r = await api.post('/code-submit', { exercise_id: selectedCodeEx.value.id, code: codeText.value })
    if (r.success) {
      codeOutput.value = r.data.output || '(无输出)'
      codeOutputError.value = !!r.data.error
      router.push(`/code-solution/${selectedCodeEx.value.id}`)
    }
  } catch (e) {
    codeOutput.value = '提交失败: ' + (e.message || '未知错误')
  }
  codeRunning.value = false
}

async function generateAIAnswer() {
  if (!selectedCodeEx.value) return
  aiAnswerLoading.value = true
  try {
    const r = await api.post(`/code-exercises/${selectedCodeEx.value.id}/ai-answer`)
    if (r.success) {
      aiCodeAnswer.value = r.data.code
      const ansRes = await api.get(`/code-exercises/${selectedCodeEx.value.id}/answers`)
      if (ansRes.success) userCodeAnswers.value = ansRes.data || []
    }
  } catch (e) { tip('AI生成失败: ' + (e.message || '未知错误')) }
  aiAnswerLoading.value = false
}

async function shareCodeAnswer() {
  if (!selectedCodeEx.value || !shareCodeText.value) return
  try {
    await api.post(`/code-exercises/${selectedCodeEx.value.id}/answers`, {
      code: shareCodeText.value, explanation: shareExplanation.value, answer_type: 'user'
    })
    shareCodeText.value = ''; shareExplanation.value = ''
    const r = await api.get(`/code-exercises/${selectedCodeEx.value.id}/answers`)
    if (r.success) userCodeAnswers.value = r.data || []
  } catch (e) { tip('分享失败') }
}

async function createCodeExercise() {
  try {
    const r = await api.post('/code-exercises', newCodeEx.value)
    if (r.success) {
      showCreateCodeModal.value = false
      newCodeEx.value = { title: '', description: '', template_code: '', difficulty: 1 }
      await loadCodeExercises()
    }
  } catch (e) { tip('创建失败: ' + (e.message || '未知错误')) }
}

// ── 代码片段 ──

async function loadSnippets() {
  snippetsLoading.value = true
  try {
    const r = await api.get('/code-snippets')
    if (r.success) snippets.value = r.data || []
  } catch (e) { console.error('加载代码片段失败:', e) }
  snippetsLoading.value = false
}

function openSnippet(snip) {
  selectedCodeEx.value = null
  currentSnippetId.value = snip.id
  codeText.value = snip.code || ''
  codeOutput.value = ''
  codeOutputError.value = false
  codeSubmitted.value = false
}

async function saveSnippet() {
  if (currentSnippetId.value) {
    // 编辑已有片段 — 直接保存
    try {
      await api.put(`/code-snippets/${currentSnippetId.value}`, { code: codeText.value })
      await loadSnippets()
    } catch (e) { tip('保存失败: ' + (e.message || '未知错误')) }
  } else {
    // 新建片段 — 弹出命名框
    snippetTitleInput.value = '未命名片段'
    showSaveSnippetModal.value = true
  }
}

async function doSaveSnippet() {
  const title = snippetTitleInput.value.trim()
  if (!title) return
  try {
    const r = await api.post('/code-snippets', { title, code: codeText.value, language: 'python' })
    if (r.success) {
      currentSnippetId.value = r.data.id
      showSaveSnippetModal.value = false
      await loadSnippets()
    }
  } catch (e) { tip('保存失败: ' + (e.message || '未知错误')) }
}

function deleteSnippet(snip) {
  ask('确定删除片段 "' + snip.title + '"？', async () => {
    try {
      await api.delete(`/code-snippets/${snip.id}`)
      if (currentSnippetId.value === snip.id) {
        currentSnippetId.value = 0
        codeText.value = ''
      }
      await loadSnippets()
    } catch (e) { tip('删除失败: ' + (e.message || '未知错误')) }
  })
}
</script>

<style scoped>
.practice-page {
  display: flex; height: calc(100vh - 64px); max-width: 100%;
}

/* 分界线 - 黑色 */
.splitter {
  width: 5px; cursor: col-resize; flex-shrink: 0;
  background: #1e293b;
  transition: background 0.2s; position: relative; z-index: 10;
}
.splitter:hover { background: #3b82f6; }

/* 左侧栏 - 白蓝色调 */
.left-sidebar {
  flex-shrink: 0; background: #ffffff;
  border-right: 1px solid #e0e7ff;
  display: flex; flex-direction: column; overflow: hidden;
  color: #1e293b;
}
.sidebar-header {
  padding: 16px 20px; border-bottom: 1px solid #e0e7ff;
}
.sidebar-header h2 { margin: 0; font-size: 16px; font-weight: 700; color: #1e40af; }
.sidebar-nav {
  display: flex; flex-direction: column; border-bottom: 1px solid #e0e7ff;
  background: #f8faff;
}
.nav-item {
  padding: 12px 20px; border: none; background: transparent;
  color: #64748b; font-size: 13px; font-weight: 500;
  cursor: pointer; transition: all 0.15s; display: block;
  text-align: left; width: 100%;
  border-left: 3px solid transparent;
}
.nav-item:hover { color: #1e40af; background: rgba(59,130,246,0.06); }
.nav-item.active {
  color: #1e40af; border-left-color: #3b82f6;
  background: rgba(59,130,246,0.08); font-weight: 600;
}
.sidebar-body { flex: 1; overflow-y: auto; padding: 16px; }

/* 左侧栏表单元素 */
.form-group label { display: block; font-size: 12px; font-weight: 600; color: #475569; margin-bottom: 6px; }
.kp-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; max-height: 100px; overflow-y: auto; }
.kp-tag {
  display: inline-flex; align-items: center; gap: 4px;
  background: rgba(59,130,246,0.1); color: #3b82f6;
  padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;
}
.kp-tag-remove { background: none; border: none; color: #3b82f6; cursor: pointer; font-size: 14px; padding: 0 2px; }
.kp-clear-all { background: rgba(239,68,68,0.1); color: #ef4444; border: none; cursor: pointer; }

.config-section { display: flex; flex-direction: column; gap: 14px; }
.btn-graph-pick {
  width: 100%; padding: 10px; background: rgba(59,130,246,0.06); color: #3b82f6;
  border: 1.5px dashed rgba(59,130,246,0.3); border-radius: 8px;
  font-size: 13px; cursor: pointer; transition: all 0.15s;
}
.btn-graph-pick:hover { background: rgba(59,130,246,0.12); border-color: #3b82f6; }
.type-checkboxes { display: flex; flex-direction: column; gap: 8px; }
.type-check { display: flex; align-items: center; gap: 3px; font-size: 12px; cursor: pointer; color: #475569; }
.type-check input { accent-color: #3b82f6; }
.btn-generate {
  width: 100%; padding: 12px; background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: #fff; border: none; border-radius: 8px; font-size: 14px; font-weight: 600;
  cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px;
}
.btn-generate:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-spinner { width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; animation: spin 0.6s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: #ef4444; font-size: 12px; text-align: center; }
.btn-ghost {
  width: 100%; padding: 8px; background: transparent; color: #64748b;
  border: 1px solid #e0e7ff; border-radius: 6px; font-size: 12px; cursor: pointer;
}
.btn-ghost:hover { background: rgba(59,130,246,0.05); }
.answering-info { padding: 4px 0; }
.info-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #f1f5f9; }
.info-label { font-size: 11px; color: #94a3b8; }
.info-value { font-size: 12px; color: #334155; }
.score-display { text-align: center; padding: 16px 0; }
.score-big { font-size: 36px; font-weight: 700; }
.score-sm { font-size: 14px; }
.score-high .score-big { color: #10b981; }
.score-mid .score-big { color: #f59e0b; }
.score-low .score-big { color: #ef4444; }

/* 左侧代码列表 */
.code-list-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 10px; font-size: 12px; font-weight: 600; color: #475569;
}
.code-exercise-list { display: flex; flex-direction: column; gap: 4px; }
.code-item {
  padding: 10px 12px; border-radius: 6px; cursor: pointer; transition: background 0.15s;
}
.code-item:hover { background: rgba(59,130,246,0.04); }
.code-item.active { background: rgba(59,130,246,0.08); border: 1px solid rgba(59,130,246,0.2); }
.ci-title { font-size: 13px; font-weight: 500; margin-bottom: 4px; color: #334155; }
.ci-meta { display: flex; gap: 6px; }
.ci-lang { font-size: 10px; color: #3b82f6; background: rgba(59,130,246,0.1); padding: 1px 5px; border-radius: 3px; }
.ci-diff { font-size: 10px; color: #94a3b8; }
.ci-diff-active { color: #1e40af; }
.list-hint { text-align: center; padding: 20px; color: #94a3b8; font-size: 12px; }

/* 代码片段列表 */
.section-label {
  display: flex; align-items: center; gap: 4px;
  font-size: 12px; font-weight: 600; color: #475569;
  cursor: pointer; padding: 4px 0; user-select: none;
}
.section-label:hover { color: #1e40af; }
.toggle-arrow { font-size: 10px; width: 14px; display: inline-block; }
.count-text { color: #94a3b8; font-weight: 400; }
.snippet-list { display: flex; flex-direction: column; gap: 2px; margin-top: 6px; }
.snippet-item {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 10px; border-radius: 6px; cursor: pointer;
  transition: background 0.15s; position: relative;
}
.snippet-item:hover { background: rgba(59,130,246,0.04); }
.snippet-item.active { background: rgba(59,130,246,0.08); border: 1px solid rgba(59,130,246,0.2); }
.snip-title { flex: 1; font-size: 13px; font-weight: 500; color: #334155; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.snip-meta { font-size: 10px; color: #94a3b8; flex-shrink: 0; }
.snip-delete {
  background: none; border: none; color: #94a3b8; cursor: pointer;
  font-size: 16px; padding: 0 4px; line-height: 1; flex-shrink: 0;
  opacity: 0; transition: opacity 0.15s;
}
.snippet-item:hover .snip-delete { opacity: 1; }
.snip-delete:hover { color: #ef4444; }
.btn-xs { padding: 2px 8px; font-size: 10px; border-radius: 4px; border: 1px solid #e0e7ff; background: transparent; color: #64748b; cursor: pointer; }
.btn-xs.btn-primary { background: #3b82f6; color: #fff; border-color: transparent; }

/* 编程习题列表 */
.code-exercise-section { margin-top: 16px; }

/* 习题过滤 */
.exercise-filter { display: flex; gap: 4px; margin-bottom: 8px; }
.filter-btn {
  padding: 2px 10px; font-size: 11px; border: 1px solid #e0e7ff; background: #ffffff;
  color: #64748b; border-radius: 4px; cursor: pointer;
}
.filter-btn.active { background: #3b82f6; color: #fff; border-color: #3b82f6; }
.filter-btn:hover:not(.active) { background: rgba(59,130,246,0.04); }
.ci-author { font-size: 10px; color: #94a3b8; margin-left: auto; }
.btn-sm { padding: 4px 10px; font-size: 11px; border-radius: 5px; border: 1px solid #e0e7ff; background: transparent; color: #64748b; cursor: pointer; }
.btn-sm.btn-primary { background: #3b82f6; color: #fff; border-color: transparent; }

/* 右侧内容 - 白蓝色调 */
.right-content { flex: 1; overflow-y: auto; min-width: 0; background: #f8fafc; }
.content-panel { padding: 24px 32px; max-width: 860px; }
.content-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid #e0e7ff;
}
.content-title { font-size: 18px; font-weight: 700; color: #1e40af; }
.header-actions { display: flex; align-items: center; }
.placeholder-panel { text-align: center; padding: 80px 40px; }
.placeholder-icon { font-size: 48px; margin-bottom: 16px; }
.placeholder-panel p { color: #64748b; font-size: 14px; }
.btn-submit { padding: 8px 20px; background: #3b82f6; color: #fff; border: none; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; }
.btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }

/* 题目卡片 - 白底 */
.question-card { background: #ffffff; border: 1px solid #e0e7ff; border-radius: 10px; padding: 20px; margin-bottom: 12px; }
.q-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.q-num { width: 24px; height: 24px; border-radius: 50%; background: #3b82f6; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; }
.q-type-badge { background: rgba(59,130,246,0.1); color: #3b82f6; padding: 2px 8px; border-radius: 4px; font-size: 11px; }
.q-title { font-size: 14px; color: #1e293b; margin: 0 0 12px; line-height: 1.6; }
.q-options { display: flex; flex-direction: column; gap: 6px; }
.q-opt {
  display: flex; align-items: center; gap: 8px; padding: 9px 12px;
  border: 1px solid #e0e7ff; border-radius: 8px; cursor: pointer;
  font-size: 13px; transition: all 0.15s; color: #475569;
}
.q-opt:hover { border-color: #3b82f6; }
.q-opt.picked { border-color: #3b82f6; background: rgba(59,130,246,0.06); }
.q-opt input { accent-color: #3b82f6; }
.q-judge { display: flex; gap: 12px; }
.q-judge .q-opt { flex: 1; justify-content: center; }
.form-textarea {
  width: 100%; padding: 10px; border: 1px solid #e0e7ff; border-radius: 8px;
  font-size: 13px; resize: vertical; box-sizing: border-box; background: #ffffff; color: #1e293b;
  font-family: inherit;
}

/* 代码编辑器 - 专业版 */
.code-editor-panel { display: flex; flex-direction: column; }
.exercise-desc {
  font-size: 13px; color: #475569; margin-bottom: 12px; padding: 12px;
  background: #ffffff; border: 1px solid #e0e7ff; border-radius: 6px;
  line-height: 1.7; max-height: 160px; overflow-y: auto;
}
.code-editor-wrapper {
  display: flex; flex: 1; min-height: 420px;
  border: 1px solid #334155; border-radius: 8px;
  overflow: hidden;
}
.line-numbers {
  flex-shrink: 0; width: 44px; background: #1a2332; color: #546e7a;
  font-family: 'Consolas', 'Monaco', monospace; font-size: 13px;
  line-height: 1.6; padding: 12px 0; text-align: right;
  overflow: hidden; user-select: none; min-height: 0;
}
.line-num { padding: 0 10px; }
.code-textarea-pro {
  flex: 1; border: none; border-radius: 0;
  min-height: 420px; padding: 12px 14px;
  background: #0f172a; color: #e2e8f0;
  font-family: 'Consolas', 'Monaco', monospace; font-size: 13px;
  line-height: 1.6; resize: none; outline: none; tab-size: 4;
}
.output-panel { margin-top: 12px; }
.output-section-label { font-size: 11px; color: #64748b; margin-bottom: 4px; font-weight: 600; }
.output-metrics {
  display: flex; gap: 16px; font-size: 11px; color: #64748b;
  padding: 6px 12px; background: #f0f4ff; border-radius: 4px;
  margin: 8px 0; border: 1px solid #e0e7ff;
}
.output-content {
  background: #f1f5f9; color: #1e293b; padding: 12px; border-radius: 6px;
  font-size: 12px; max-height: 150px; overflow-y: auto; margin: 0; border: 1px solid #e0e7ff;
  white-space: pre-wrap; word-break: break-all;
}
.input-content { background: #fffbe6; border-color: #fde68a; }
.output-error { color: #ef4444; }

/* 答案 - 白底 */
.answer-tabs { display: flex; gap: 4px; }
.tab-sm {
  padding: 4px 12px; border: 1px solid #e0e7ff; background: #ffffff;
  color: #64748b; border-radius: 4px; cursor: pointer; font-size: 11px;
}
.tab-sm.active { background: #3b82f6; color: #fff; border-color: #3b82f6; }
.answer-code {
  background: #0f172a; color: #e2e8f0; padding: 12px; border-radius: 6px;
  font-size: 12px; max-height: 250px; overflow-y: auto; margin: 0;
  white-space: pre-wrap; word-break: break-all;
}
.answer-card { margin-bottom: 12px; border: 1px solid #e0e7ff; border-radius: 6px; padding: 12px; background: #ffffff; }
.answer-info { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 12px; color: #475569; }
.answer-type-tag { font-size: 10px; background: rgba(59,130,246,0.1); color: #3b82f6; padding: 1px 6px; border-radius: 3px; }
.answer-exp { font-size: 12px; color: #64748b; margin-top: 8px; }
.share-input {
  width: 100%; background: #ffffff; color: #1e293b;
  border: 1px solid #e0e7ff; border-radius: 4px;
  padding: 8px; font-family: 'Consolas', monospace; font-size: 12px;
  resize: vertical; min-height: 50px; outline: none; box-sizing: border-box;
}

/* 结果卡片 - 白底 */
.score-msg-text { font-size: 14px; color: #64748b; text-align: center; margin-bottom: 20px; }
.result-card {
  background: #ffffff; border-radius: 10px; padding: 16px;
  margin-bottom: 10px; border-left: 4px solid #e0e7ff;
}
.rc-ok { border-left-color: #10b981; }
.rc-err { border-left-color: #ef4444; }
.rc-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.rc-num { font-size: 12px; color: #94a3b8; }
.rc-icon { font-size: 16px; font-weight: 700; }
.rc-ok .rc-icon { color: #10b981; }
.rc-err .rc-icon { color: #ef4444; }
.rc-type { font-size: 11px; background: rgba(59,130,246,0.06); color: #64748b; padding: 2px 6px; border-radius: 4px; }
.rc-title { font-size: 14px; margin: 0 0 8px; color: #1e293b; }
.rc-detail p { font-size: 13px; margin: 0 0 4px; color: #475569; }
.text-ok { color: #10b981; }
.text-err { color: #ef4444; }
.rc-explanation { font-size: 12px; color: #64748b; background: #f8fafc; padding: 10px; border-radius: 6px; margin-top: 8px; }

/* 弹窗 - 不透明白蓝色 */
.picker-overlay { position: fixed; inset: 0; z-index: 1000; background: rgba(15,23,42,0.7); display: flex; align-items: center; justify-content: center; padding: 20px; }
.picker-modal { background: #ffffff; border-radius: 12px; width: 90vw; max-width: 750px; height: 75vh; display: flex; flex-direction: column; overflow: hidden; border: 1px solid #e0e7ff; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
.picker-header { display: flex; align-items: center; gap: 12px; padding: 14px 18px; border-bottom: 1px solid #e0e7ff; flex-shrink: 0; background: #f8faff; }
.picker-header h3 { margin: 0; font-size: 15px; color: #1e40af; }
.picker-count { font-size: 12px; color: #3b82f6; font-weight: 600; }
.modal-close-btn { margin-left: auto; background: none; border: none; font-size: 22px; cursor: pointer; color: #94a3b8; padding: 0 4px; line-height: 1; }
.modal-close-btn:hover { color: #64748b; }
.picker-loading { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: #94a3b8; }
.spinner { width: 28px; height: 28px; border: 3px solid #e0e7ff; border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.6s linear infinite; }
.picker-tree { flex: 1; overflow-y: auto; padding: 12px 16px; background: #ffffff; }
.picker-footer { display: flex; align-items: center; justify-content: space-between; padding: 12px 18px; border-top: 1px solid #e0e7ff; flex-shrink: 0; background: #f8faff; }
.picker-hint { font-size: 11px; color: #94a3b8; }
.picker-actions { display: flex; gap: 8px; }
.btn-primary { padding: 8px 18px; background: #3b82f6; color: #fff; border: none; border-radius: 7px; font-size: 13px; font-weight: 600; cursor: pointer; }

/* 题库刷题模块嵌入适配：随练习中心宽度自适应 */
.bank-panel {
  padding: 24px 28px;
  max-width: none;
}
</style>
