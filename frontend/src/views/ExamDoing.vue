<template>
  <div class="page-container">
    <template v-if="!examData">
      <UiLoading />
    </template>

    <template v-else-if="submitted">
      <div class="result-box">
        <h1>{{ timeExpired ? '时间到，已自动交卷' : '交卷成功!' }}</h1>
        <p v-if="timeExpired" class="timeup-tip">答题时间已到，系统已自动保存并提交你的试卷</p>
        <p v-if="myScore !== null">客观题得分：{{ myScore }} 分</p>
        <p v-else>试卷已提交，主观题将由教师批阅</p>
        <router-link :to="`/exams/${eid}/result`" class="btn btn-primary">查看成绩</router-link>
        <router-link to="/exams" class="btn btn-outline">返回任务中心</router-link>
      </div>
    </template>

    <template v-else>
      <!-- 顶部标题栏 -->
      <div class="exam-header">
        <h1>
          {{ examData.exam_title }}
          <span class="task-type-badge" :class="isHomework ? 'task-type-homework' : 'task-type-exam'">{{ isHomework ? '作业' : '考试' }}</span>
        </h1>
        <div class="exam-info">
          <span>{{ examData.questions?.length || 0 }} 题</span>
          <span>总分：{{ examData.total_score }} 分</span>
          <span v-if="focusLostCount > 0" class="focus-warning">⚠ 切屏 {{ focusLostCount }} 次</span>
        </div>
      </div>

      <!-- 分屏布局：左侧题目区 + 右侧答题卡 -->
      <div class="doing-layout">
        <!-- 主题目区 -->
        <div class="doing-main">
          <div class="q-progress">
            <span>第 <strong>{{ currentIndex + 1 }}</strong> / {{ questions.length }} 题</span>
            <span class="q-progress-dot" :class="answeredCount === questions.length ? 'done' : ''">
              {{ answeredCount === questions.length ? '全部已答' : `已答 ${answeredCount} 题` }}
            </span>
          </div>

          <div class="card question-card" v-if="currentQuestion">
            <div class="q-header">
              <span class="q-num">{{ currentIndex + 1 }}.</span>
              <span class="type-tag" :class="'type-' + currentQuestion.type">{{ typeLabel(currentQuestion.type) }}</span>
              <span class="q-score">{{ currentQuestion.score || 0 }} 分</span>
              <button class="btn btn-xs flag-btn" :class="{ active: flagged.has(currentQuestion.id) }" @click="toggleFlag(currentQuestion.id)">
                {{ flagged.has(currentQuestion.id) ? '已标记复查' : '标记复查' }}
              </button>
            </div>
            <div class="q-title">{{ currentQuestion.title }}</div>

            <!-- 选择题 -->
            <div v-if="currentQuestion.type === 'choice'" class="q-options">
              <label v-for="(opt, oi) in (currentQuestion.options || [])" :key="oi" class="opt-item" :class="{ selected: isOptionSelected(currentQuestion, oi) }">
                <input
                  :type="currentQuestion.is_multi ? 'checkbox' : 'radio'"
                  :name="'q_' + currentQuestion.id"
                  :value="oi"
                  :checked="isOptionSelected(currentQuestion, oi)"
                  @change="onChoiceChange(currentQuestion, oi, $event)"
                />
                <span class="opt-letter">{{ String.fromCharCode(65 + oi) }}.</span>
                <span>{{ opt }}</span>
              </label>
              <div class="q-tip" v-if="!currentQuestion.is_multi && !isHomework">💡 键盘可直接按 1-{{ (currentQuestion.options || []).length }} 选择答案</div>
            </div>

            <!-- 判断题 -->
            <div v-if="currentQuestion.type === 'judge'" class="q-options">
              <label class="opt-item" :class="{ selected: answers[currentQuestion.id] === '对' }">
                <input type="radio" :name="'q_' + currentQuestion.id" value="对" :checked="answers[currentQuestion.id] === '对'" @change="answers[currentQuestion.id] = '对'; saveAnswer(currentQuestion.id)" />
                <span class="opt-letter">对</span>
              </label>
              <label class="opt-item" :class="{ selected: answers[currentQuestion.id] === '错' }">
                <input type="radio" :name="'q_' + currentQuestion.id" value="错" :checked="answers[currentQuestion.id] === '错'" @change="answers[currentQuestion.id] = '错'; saveAnswer(currentQuestion.id)" />
                <span class="opt-letter">错</span>
              </label>
            </div>

            <!-- 填空题 / 主观题 -->
            <div v-if="currentQuestion.type === 'fill' || currentQuestion.type === 'subjective'" class="q-textarea">
              <textarea
                v-model="answers[currentQuestion.id]"
                class="input"
                rows="4"
                :placeholder="currentQuestion.type === 'fill' ? '请输入答案' : '请输入你的作答'"
                @blur="saveAnswer(currentQuestion.id)"
              ></textarea>
            </div>
          </div>

          <!-- 上一题/下一题 -->
          <div class="q-nav">
            <button class="btn btn-outline" :disabled="currentIndex <= 0" @click="goTo(currentIndex - 1)">← 上一题</button>
            <div class="q-nav-center">
              <span v-if="flagged.size" class="flagged-hint">已标记 {{ flagged.size }} 题待复查</span>
            </div>
            <button class="btn btn-outline" :disabled="currentIndex >= questions.length - 1" @click="goTo(currentIndex + 1)">
              {{ currentIndex >= questions.length - 1 ? '最后一题' : '下一题 →' }}
            </button>
          </div>
        </div>

        <!-- 右侧答题卡 -->
        <aside class="answer-card-panel">
          <div class="answer-card card">
            <div class="timer-box" v-if="!isHomework">
              <span class="timer-label">剩余时间</span>
              <span class="timer-value" :class="{ 'timer-danger': timeLeft <= 300 }">{{ formatTime(timeLeft) }}</span>
            </div>
            <div class="timer-box homework-box" v-else>
              <span class="timer-label">作业模式</span>
              <span class="timer-value">不限时</span>
            </div>

            <div class="card-title">答题卡</div>
            <div class="card-grid">
              <button
                v-for="(q, i) in questions" :key="q.id"
                class="card-cell"
                :class="cardCellClass(q.id)"
                @click="goTo(i)"
              >{{ i + 1 }}</button>
            </div>

            <div class="card-legend">
              <span><i class="legend-dot dot-answered"></i>已答</span>
              <span><i class="legend-dot dot-flagged"></i>标记</span>
              <span><i class="legend-dot dot-unanswered"></i>未答</span>
            </div>

            <div class="card-stats">
              <span>已答 {{ answeredCount }}/{{ questions.length }}</span>
              <span v-if="flagged.size">标记 {{ flagged.size }}</span>
            </div>

            <button class="btn btn-primary btn-block" @click="doSubmit" :disabled="submitting">
              {{ submitting ? '提交中...' : (isHomework ? '提交作业' : '提交试卷') }}
            </button>
          </div>
        </aside>
      </div>
    </template>

    <!-- 交卷确认弹窗 -->
    <div v-if="showSubmitConfirm" class="modal-overlay" @click.self="showSubmitConfirm = false">
      <div class="confirm-modal">
        <p>{{ confirmMsg }}</p>
        <div v-if="unAnsweredList.length" class="confirm-detail">
          <div class="confirm-detail-title">未作答题目：</div>
          <div class="unanswered-chips">
            <span v-for="n in unAnsweredList" :key="n" class="unanswered-chip">{{ n }}</span>
          </div>
        </div>
        <div v-if="flaggedList.length" class="confirm-detail">
          <div class="confirm-detail-title">标记待复查题目：</div>
          <div class="flagged-chips">
            <span v-for="n in flaggedList" :key="n" class="flagged-chip">⚑ {{ n }}</span>
          </div>
        </div>
        <div class="confirm-actions">
          <button class="btn" @click="showSubmitConfirm = false">继续答题</button>
          <button class="btn btn-danger" @click="_executeSubmit">确认交卷</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import { useFeedback } from '../composables/useFeedback'

const { tip, ask } = useFeedback()

const route = useRoute()
const eid = computed(() => route.params.eid)

const examData = ref(null)
const answers = ref({})
const submitted = ref(false)
const submitting = ref(false)
const showSubmitConfirm = ref(false)
const confirmMsg = ref('')
const unAnsweredList = ref([])
const flaggedList = ref([])
const pendingForce = ref(false)
const myScore = ref(null)
const timeExpired = ref(false)
const timeLeft = ref(0)
const isHomework = ref(false)
const focusLostCount = ref(0)

// 分屏答题状态
const currentIndex = ref(0)
const flagged = ref(new Set())
let timer = null

const TYPE_MAP = { choice: '选择题', judge: '判断题', fill: '填空题', subjective: '主观题' }
function typeLabel(t) { return TYPE_MAP[t] || t }

const questions = computed(() => examData.value?.questions || [])
const currentQuestion = computed(() => questions.value[currentIndex.value])
const answeredCount = computed(() => Object.keys(answers.value).filter(k => answers.value[k]).length)

onMounted(async () => {
  try {
    const r = await api.post(`/exams/${eid.value}/start`)
    if (r.success) {
      examData.value = r.data
      // 判断是否为作业模式
      isHomework.value = r.data.task_type === 'homework'
      // 填充已有答案
      if (r.data.questions) {
        r.data.questions.forEach(q => {
          if (q.saved_answer) answers.value[q.id] = q.saved_answer
        })
      }
      // 作业模式不启动倒计时
      if (!isHomework.value && r.data.duration_minutes && r.data.started_at) {
        const end = new Date(r.data.started_at).getTime() + r.data.duration_minutes * 60000
        const now = Date.now()
        timeLeft.value = Math.max(0, Math.floor((end - now) / 1000))
        if (timeLeft.value > 0) {
          timer = setInterval(() => {
            timeLeft.value--
            if (timeLeft.value <= 0) {
              clearInterval(timer)
              doSubmit(true)
            }
          }, 1000)
        }
      }
    }
  } catch (e) {
    tip(e.message || '加载失败')
    window.history.back()
  }
  // 切屏检测：仅依赖 visibilitychange，避免与 blur 重复计数
  document.addEventListener('visibilitychange', handleVisibilityChange)
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  window.removeEventListener('keydown', onKeydown)
})

// ── 答题卡状态 ──
function cardCellClass(qid) {
  const cls = []
  if (qid === currentQuestion.value?.id) cls.push('current')
  if (answers.value[qid]) cls.push('answered')
  else if (flagged.value.has(qid)) cls.push('flagged')
  return cls
}

function goTo(i) {
  if (i >= 0 && i < questions.value.length) currentIndex.value = i
}
function prev() { goTo(currentIndex.value - 1) }
function next() { goTo(currentIndex.value + 1) }

function toggleFlag(qid) {
  const s = new Set(flagged.value)
  if (s.has(qid)) s.delete(qid)
  else s.add(qid)
  flagged.value = s
}

// ── 键盘导航 ──
function onKeydown(e) {
  if (submitted.value || !examData.value) return
  const tag = e.target?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
  if (e.key === 'ArrowLeft') { prev(); e.preventDefault() }
  else if (e.key === 'ArrowRight') { next(); e.preventDefault() }
  else if (/^[1-9]$/.test(e.key)) {
    const q = currentQuestion.value
    // 单选选择题支持数字键快捷作答
    if (q && q.type === 'choice' && !q.is_multi) {
      const idx = Number(e.key) - 1
      if (idx < (q.options || []).length) {
        answers.value[q.id] = String.fromCharCode(65 + idx)
        saveAnswer(q.id)
        e.preventDefault()
      }
    }
  }
}

// ── 切屏计数（修复 blur 与 visibilitychange 重复触发）──
function handleVisibilityChange() {
  if (document.hidden) focusLostCount.value++
}

// ── 作答 ──
function isOptionSelected(q, idx) {
  const ans = answers.value[q.id] || ''
  if (q.is_multi) {
    const selected = ans.split(',').map(s => s.trim())
    return selected.includes(String.fromCharCode(65 + idx))
  }
  return ans === String.fromCharCode(65 + idx)
}

function onChoiceChange(q, idx, e) {
  if (q.is_multi) {
    const letter = String.fromCharCode(65 + idx)
    let selected = (answers.value[q.id] || '').split(',').map(s => s.trim()).filter(Boolean)
    if (e.target.checked) {
      if (!selected.includes(letter)) selected.push(letter)
    } else {
      selected = selected.filter(s => s !== letter)
    }
    answers.value[q.id] = selected.join(',')
  } else {
    answers.value[q.id] = String.fromCharCode(65 + idx)
  }
  saveAnswer(q.id)
}

// 各题答案保存串行链：保证同一题保存按顺序执行，交卷前等待全部落库（避免 blur 保存与交卷竞态）
const saveChains = {}

function enqueueSave(qid, payload) {
  const prev = saveChains[qid] || Promise.resolve()
  const task = prev
    .catch(() => {})
    .then(() => api.post(`/exams/${eid.value}/answers`, payload))
    .catch(e => console.warn('答案保存失败，提交时可能丢失:', e))
  saveChains[qid] = task
  return task
}

async function saveAnswer(qid) {
  if (!answers.value[qid]) return
  await enqueueSave(qid, { question_id: qid, answer: answers.value[qid] })
}

// ── 交卷 ──
async function doSubmit(force = false) {
  const total = questions.value.length
  const aCount = answeredCount.value
  if (!force && aCount < total) {
    const unanswered = questions.value
      .map((q, i) => ({ q, i }))
      .filter(({ q }) => !answers.value[q.id])
      .map(({ i }) => i + 1)
    const flaggedNum = questions.value
      .map((q, i) => ({ q, i }))
      .filter(({ q }) => flagged.value.has(q.id))
      .map(({ i }) => i + 1)
    confirmMsg.value = `还有 ${total - aCount} 题未作答，确定提交吗？`
    unAnsweredList.value = unanswered
    flaggedList.value = flaggedNum
    pendingForce.value = false
    showSubmitConfirm.value = true
    return
  }
  await _executeSubmit()
}

async function _executeSubmit() {
  showSubmitConfirm.value = false
  submitting.value = true
  try {
    // 等待所有进行中的答案保存完成，避免竞态丢失最后一次作答
    await Promise.all(Object.values(saveChains).map(p => Promise.resolve(p).catch(() => {})))
    const r = await api.post(`/exams/${eid.value}/submit`, {
      focus_lost_count: focusLostCount.value
    })
    if (r.success) {
      myScore.value = r.data?.auto_score ?? 0
      timeExpired.value = !!r.data?.time_expired
    }
    submitted.value = true
    if (timer) clearInterval(timer)
  } catch (e) {
    tip(e.message || '提交失败')
  }
  finally { submitting.value = false }
}

function formatTime(sec) {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}
</script>

<style scoped>
.page-container { max-width: 1100px; margin: 0 auto; padding: 24px; }
.loading-text { text-align: center; padding: 60px; color: var(--text-secondary); }

.result-box {
  text-align: center; padding: 60px 24px; background: #fff;
  border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.result-box h1 { font-size: 25px; color: #16a34a; margin: 0 0 12px; }
.timeup-tip { color: #92400e; font-weight: 500; }
.result-box p { font-size: 13px; color: var(--text-secondary); margin-bottom: 24px; }
.result-box .btn { margin: 0 6px; }

.exam-header { margin-bottom: 16px; }
.exam-header h1 { margin: 0 0 6px; font-size: 18px; }
.exam-info { display: flex; gap: 16px; font-size: 11px; color: var(--text-secondary); }

/* ── 分屏布局 ── */
.doing-layout { display: flex; gap: 16px; align-items: flex-start; }
.doing-main { flex: 1; min-width: 0; }
.answer-card-panel { width: 250px; flex-shrink: 0; }

.q-progress {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 10px; font-size: 11px; color: var(--text-secondary);
  padding: 0 4px;
}
.q-progress strong { color: #1e293b; font-size: 13px; }
.q-progress-dot.done { color: #16a34a; font-weight: 600; }

.question-card { padding: 24px; margin-bottom: 12px; min-height: 300px; }
.q-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.q-num { font-weight: 700; font-size: 14px; color: var(--accent-blue); }
.q-score { margin-left: auto; font-size: 11px; color: var(--text-light); }
.flag-btn { border: 1px solid #cbd5e1; color: #64748b; background: #fff; }
.flag-btn.active { background: #fef3c7; color: #92400e; border-color: #f59e0b; }
.q-title { font-size: 13px; margin-bottom: 16px; line-height: 1.7; }

.q-options { display: flex; flex-direction: column; gap: 8px; }
.opt-item {
  display: flex; align-items: center; gap: 8px; padding: 10px 14px;
  border-radius: 8px; border: 1px solid #e2e8f0; cursor: pointer; font-size: 12px;
  transition: all 0.15s;
}
.opt-item:hover { border-color: #3b82f6; background: #eff6ff; }
.opt-item.selected { border-color: #3b82f6; background: #dbeafe; }
.opt-item input { margin: 0; }
.opt-letter { font-weight: 600; color: var(--text-secondary); width: 18px; }
.q-tip { font-size: 11px; color: var(--text-light); margin-top: 8px; }
.q-textarea { margin-top: 8px; }

.type-tag { font-size: 10px; padding: 1px 7px; border-radius: 3px; font-weight: 500; }
.type-choice { background: #dbeafe; color: #1e40af; }
.type-judge { background: #d1fae5; color: #065f46; }
.type-fill { background: #fef3c7; color: #92400e; }
.type-subjective { background: #ede9fe; color: #5b21b6; }

.q-nav { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.q-nav-center { font-size: 11px; color: var(--text-light); }
.flagged-hint { color: #92400e; }

/* ── 右侧答题卡 ── */
.answer-card { padding: 16px; position: sticky; top: 76px; }
.timer-box {
  text-align: center; padding: 10px; border-radius: 8px;
  background: #f8fafc; margin-bottom: 12px;
}
.timer-label { display: block; font-size: 10px; color: var(--text-secondary); margin-bottom: 2px; }
.timer-value { font-size: 19px; font-weight: 700; color: #1e293b; font-variant-numeric: tabular-nums; }
.timer-value.timer-danger { color: #dc2626; animation: pulse 1s infinite; }
@keyframes pulse { 50% { opacity: 0.6; } }
.homework-box .timer-value { font-size: 13px; color: #7c3aed; }

.card-title { font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; }
.card-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-bottom: 10px; }
.card-cell {
  aspect-ratio: 1; border: 1px solid #e2e8f0; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; cursor: pointer; background: #fff; color: #64748b;
  transition: all 0.12s;
}
.card-cell:hover { border-color: #3b82f6; }
.card-cell.answered { background: #3b82f6; color: #fff; border-color: #3b82f6; }
.card-cell.flagged { background: #fef3c7; color: #92400e; border-color: #f59e0b; }
.card-cell.current { outline: 2px solid #3b82f6; outline-offset: 1px; }

.card-legend { display: flex; gap: 12px; font-size: 10px; color: var(--text-secondary); margin-bottom: 8px; }
.legend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 3px; vertical-align: -1px; }
.dot-answered { background: #3b82f6; }
.dot-flagged { background: #f59e0b; }
.dot-unanswered { background: #fff; border: 1px solid #cbd5e1; }

.card-stats { display: flex; gap: 12px; font-size: 11px; color: var(--text-secondary); margin-bottom: 12px; }
.btn-block { width: 100%; }

/* 交卷确认弹窗 */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.35);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.confirm-modal {
  background: #fff; border-radius: 10px; padding: 24px 28px; max-width: 400px;
  box-shadow: 0 8px 30px rgba(0,0,0,0.15); text-align: center;
}
.confirm-modal p { font-size: 13px; margin: 0 0 16px; line-height: 1.5; }
.confirm-detail { text-align: left; margin-bottom: 10px; }
.confirm-detail-title { font-size: 11px; color: var(--text-secondary); margin-bottom: 6px; }
.unanswered-chips, .flagged-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.unanswered-chip {
  min-width: 26px; padding: 3px 8px; text-align: center; font-size: 11px;
  border: 1px solid #cbd5e1; border-radius: 5px; color: #64748b;
}
.flagged-chip {
  padding: 3px 8px; font-size: 11px;
  background: #fef3c7; color: #92400e; border-radius: 5px;
}
.confirm-actions { display: flex; justify-content: center; gap: 12px; margin-top: 16px; }

.btn { padding: 8px 16px; font-size: 11px; border-radius: 6px; cursor: pointer; border: 1px solid transparent; text-decoration: none; display: inline-block; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover { background: #2563eb; }
.btn-outline { border-color: #cbd5e1; color: #334155; background: #fff; }
.btn-outline:hover { border-color: #3b82f6; color: #3b82f6; }
.btn-outline:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-danger { background: #dc2626; color: #fff; }
.btn-danger:hover { background: #b91c1c; }
.btn-xs { padding: 3px 10px; font-size: 10px; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.input { padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 11px; width: 100%; box-sizing: border-box; }
.input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.1); }
textarea.input { resize: vertical; }

.task-type-badge { font-size: 10px; padding: 2px 8px; border-radius: 4px; font-weight: 500; margin-left: 8px; vertical-align: middle; }
.task-type-exam { background: #dbeafe; color: #1e40af; }
.task-type-homework { background: #ede9fe; color: #6d28d9; }
.focus-warning { color: #dc2626; font-weight: 500; font-size: 11px; }

/* ── 移动端：答题页上下分屏（RA） ── */
@media (max-width: 960px) {
  .doing-layout { flex-direction: column; }
  .answer-card-panel { width: 100%; }
  .page-container { padding: 16px 12px; }
  .exam-header { flex-direction: column; align-items: flex-start; gap: 6px; }
  .question-card { padding: 16px; }
}
</style>
