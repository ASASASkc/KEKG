<template>
  <div class="page-container">
    <div class="page-top">
      <a href="javascript:void(0)" class="back-link" @click="backToBank">&larr; 返回题库</a>
      <h1 v-if="q">刷题</h1>
    </div>

    <UiLoading v-if="loading" />

    <template v-else-if="q">
      <!-- 题目头部 -->
      <div class="q-head">
        <span class="type-tag" :class="'type-' + q.type">{{ typeLabel(q.type) }}</span>
        <span class="star-rating" :class="'star-' + starLevel(q.difficulty)">{{ starText(q.difficulty) }}</span>
        <span v-if="q.pass_rate !== null && q.pass_rate !== undefined" class="pass-rate" :class="passRateClass(q.pass_rate)">通过率 {{ q.pass_rate }}%</span>
        <span v-if="q.topic" class="topic-tag">{{ q.topic }}</span>
        <button class="fav-btn" :class="{ active: q.is_favorite }" @click="toggleFavorite" title="收藏">
          {{ q.is_favorite ? '★ 已收藏' : '☆ 收藏' }}
        </button>
        <span v-if="result" class="result-badge" :class="result.is_correct === 1 ? 'badge-correct' : 'badge-wrong'">
          {{ result.is_correct === 1 ? '✓ 回答正确' : (result.is_correct === 0 ? '✗ 回答错误' : '已提交') }}
        </span>
      </div>

      <div class="card q-card">
        <div class="q-title">{{ q.title }}</div>

        <!-- 选择题 -->
        <div v-if="q.type === 'choice'" class="q-options">
          <label
            v-for="(opt, oi) in (q.options || [])" :key="oi"
            class="opt-item"
            :class="optionClass(oi)"
          >
            <input
              :type="q.is_multi ? 'checkbox' : 'radio'"
              :name="'opt_' + q.id"
              :value="oi"
              :checked="isOptionSelected(oi)"
              :disabled="!!result"
              @change="onOptionChange(q, oi, $event)"
            />
            <span class="opt-letter">{{ String.fromCharCode(65 + oi) }}.</span>
            <span>{{ opt }}</span>
            <span v-if="result && isCorrectOption(oi)" class="opt-flag">✓</span>
            <span v-if="result && result.is_correct === 0 && isMyWrongOption(oi)" class="opt-flag flag-wrong">✗</span>
          </label>
        </div>

        <!-- 判断题 -->
        <div v-if="q.type === 'judge'" class="q-options">
          <label class="opt-item" :class="judgeClass('对')">
            <input type="radio" :name="'j_' + q.id" value="对" v-model="answer" :disabled="!!result" />
            <span class="opt-letter">对</span>
            <span v-if="result && isCorrectOption('对')" class="opt-flag">✓</span>
          </label>
          <label class="opt-item" :class="judgeClass('错')">
            <input type="radio" :name="'j_' + q.id" value="错" v-model="answer" :disabled="!!result" />
            <span class="opt-letter">错</span>
            <span v-if="result && isCorrectOption('错')" class="opt-flag">✓</span>
          </label>
        </div>

        <!-- 填空/主观题 -->
        <div v-if="q.type === 'fill' || q.type === 'subjective'" class="q-textarea">
          <textarea
            v-model="answer"
            class="input"
            rows="4"
            :placeholder="q.type === 'fill' ? '请输入答案' : '请输入你的作答'"
            :disabled="!!result"
          ></textarea>
        </div>

        <!-- 作答/重做 -->
        <div class="q-actions" v-if="!result">
          <button class="btn btn-primary" @click="submit" :disabled="submitting">提交答案</button>
          <span v-if="submitted && !result" class="hint">正在判题...</span>
        </div>

        <!-- 判题结果 -->
        <div v-if="result" class="result-panel" :class="result.is_correct === 1 ? 'panel-correct' : 'panel-wrong'">
          <div class="result-title">
            {{ result.is_correct === 1 ? '回答正确' : (result.is_correct === 0 ? '回答错误' : '已提交') }}
          </div>
          <div class="result-row">
            <span class="result-label">正确答案：</span>
            <strong>{{ result.correct_answer }}</strong>
          </div>
          <div v-if="result.explanation" class="result-row">
            <span class="result-label">解析：</span>
            <span class="explanation">{{ result.explanation }}</span>
          </div>
        </div>
      </div>

      <div class="q-actions-bottom">
        <a href="javascript:void(0)" class="btn btn-outline" @click="backToBank">返回题库</a>
        <router-link :to="`/practice/${nextQid}`" v-if="nextQid" class="btn btn-primary">下一题 →</router-link>
      </div>
    </template>

    <div v-else class="empty-state">
      <p>题目不存在或已被下架</p>
      <a href="javascript:void(0)" class="btn btn-primary" @click="backToBank">返回题库</a>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { useFeedback } from '../composables/useFeedback'

const { tip, ask } = useFeedback()

const route = useRoute()
const router = useRouter()
const qid = route.params.qid

// 返回题库：优先回退到来源页（练习中心/学习计划），无历史则进入练习中心
function backToBank() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/ai-practice')
  }
}

const q = ref(null)
const loading = ref(true)
const answer = ref('')
const result = ref(null)
const submitting = ref(false)
const submitted = ref(false)
const nextQid = ref('')
// 记录进入时间用于统计单题用时
const enterTime = Date.now()

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
function passRateClass(rate) {
  if (rate >= 80) return 'pass-high'
  if (rate >= 50) return 'pass-mid'
  return 'pass-low'
}

onMounted(async () => {
  try {
    const r = await api.get(`/practice/questions/${qid}`)
    if (r.success) {
      q.value = r.data
      // 恢复最近一次作答（若已提交过则直接展示结果，回填正确答案与解析）
      const last = r.data.last_attempt
      if (last) {
        answer.value = last.user_answer || ''
        result.value = {
          is_correct: last.is_correct,
          correct_answer: r.data.answer || '',
          explanation: r.data.explanation || ''
        }
        // 判题结果面板需要正确答案与解析
        submitted.value = true
        fetchNext()
      }
      // 新题：nextQid 留空，待提交成功后再计算，避免未作答即可点"下一题"跳走
    }
  } catch (e) { console.error(e) }
  finally { loading.value = false }
})

async function fetchNext() {
  try {
    // 拉取同类型题目列表，找下一道题
    const r = await api.get('/practice/questions', { params: { page: 1, page_size: 100, type: q.value?.type || '', sort: 'diff_asc' } })
    if (r.success) {
      const items = r.data.items || []
      const idx = items.findIndex(i => String(i.id) === String(qid))
      const target = idx >= 0 ? items[idx + 1] : null
      if (target) nextQid.value = target.id
    }
  } catch (e) { /* 静默：无下一题 */ }
}

function isOptionSelected(oi) {
  const a = answer.value || ''
  if (q.value.is_multi) return a.split(',').map(s => s.trim()).includes(String.fromCharCode(65 + oi))
  return a === String.fromCharCode(65 + oi)
}

function onOptionChange(qq, oi, e) {
  if (qq.is_multi) {
    const letter = String.fromCharCode(65 + oi)
    let sel = (answer.value || '').split(',').map(s => s.trim()).filter(Boolean)
    if (e.target.checked) { if (!sel.includes(letter)) sel.push(letter) }
    else sel = sel.filter(s => s !== letter)
    answer.value = sel.join(',')
  } else {
    answer.value = String.fromCharCode(65 + oi)
  }
}

function optionClass(oi) {
  const letter = String.fromCharCode(65 + oi)
  if (result.value?.is_correct === 0 && isMyWrongOption(oi)) return 'opt-wrong'
  if (result.value && isCorrectOption(letter)) return 'opt-correct'
  if (isOptionSelected(oi) && !result.value) return 'selected'
  return ''
}
function judgeClass(v) {
  if (result.value?.is_correct === 0 && (answer.value || '').trim() === v) return 'opt-wrong'
  if (result.value && isCorrectOption(v)) return 'opt-correct'
  if ((answer.value || '').trim() === v && !result.value) return 'selected'
  return ''
}
function isMyWrongOption(oi) {
  const letter = typeof oi === 'number' ? String.fromCharCode(65 + oi) : oi
  const a = (answer.value || '').trim()
  return result.value?.is_correct === 0 && a.split(',').map(s => s.trim()).includes(letter)
}
function isCorrectOption(letter) {
  const c = (result.value?.correct_answer || '').trim()
  if (q.value?.type === 'judge') return c === letter
  return c.split(',').map(s => s.trim()).includes(String(letter))
}

async function submit() {
  if (!answer.value) { tip('请先作答'); return }
  submitting.value = true
  submitted.value = true
  try {
    const elapsed = Math.max(1, Math.round((Date.now() - enterTime) / 1000))
    const r = await api.post('/practice/attempts', { question_id: q.value.id, answer: answer.value, elapsed_seconds: elapsed })
    if (r.success) {
      result.value = r.data
      fetchNext()
    }
  } catch (e) { tip(e.message || '提交失败') }
  finally { submitting.value = false }
}

async function toggleFavorite() {
  if (!q.value) return
  try {
    if (q.value.is_favorite) {
      await api.delete(`/questions/${q.value.id}/favorite`)
    } else {
      await api.put(`/questions/${q.value.id}/favorite`)
    }
    q.value.is_favorite = !q.value.is_favorite
  } catch (e) { tip('收藏操作失败') }
}
</script>

<style scoped>
.page-container { max-width: 800px; margin: 0 auto; padding: 32px 24px; }
.page-top h1 { font-size: 22px; margin: 0 0 16px; }
.back-link { font-size: 13px; color: var(--accent-blue); text-decoration: none; display: inline-block; margin-bottom: 8px; }
.back-link:hover { text-decoration: underline; }
.loading-text { text-align: center; padding: 60px; color: var(--text-secondary); }
.empty-state { text-align: center; padding: 60px; color: var(--text-secondary); }

.q-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.type-tag { font-size: 11px; padding: 1px 7px; border-radius: 3px; font-weight: 500; }
.type-choice { background: #dbeafe; color: #1e40af; }
.type-judge { background: #d1fae5; color: #065f46; }
.type-fill { background: #fef3c7; color: #92400e; }
.type-subjective { background: #ede9fe; color: #5b21b6; }
.star-rating { font-size: 12px; letter-spacing: 1px; }
.star-1 { color: #10b981; }
.star-2 { color: #3b82f6; }
.star-3 { color: #f59e0b; }
.star-4 { color: #ef4444; }
.pass-rate { font-size: 12px; font-weight: 600; }
.pass-high { color: #16a34a; }
.pass-mid { color: #d97706; }
.pass-low { color: #dc2626; }
.topic-tag { font-size: 11px; padding: 2px 6px; border-radius: 4px; background: #e0e7ff; color: #3730a3; }

/* 收藏按钮 */
.fav-btn {
  border: 1px solid #e2e8f0; background: #fff; color: #64748b;
  font-size: 12px; padding: 3px 10px; border-radius: 6px; cursor: pointer;
  transition: all 0.15s;
}
.fav-btn:hover { border-color: #f59e0b; color: #f59e0b; }
.fav-btn.active { border-color: #f59e0b; background: #fef3c7; color: #b45309; }

.result-badge { font-size: 12px; padding: 2px 10px; border-radius: 4px; font-weight: 600; }
.badge-correct { background: #d1fae5; color: #065f46; }
.badge-wrong { background: #fee2e2; color: #991b1b; }

.q-card { padding: 24px; margin-bottom: 16px; min-height: 220px; }
.q-title { font-size: 15px; line-height: 1.7; margin-bottom: 16px; }

.q-options { display: flex; flex-direction: column; gap: 8px; }
.opt-item {
  display: flex; align-items: center; gap: 8px; padding: 10px 14px;
  border-radius: 8px; border: 1px solid #e2e8f0; cursor: pointer; font-size: 14px;
  transition: all 0.15s; position: relative;
}
.opt-item:hover:not(:has(input:disabled)) { border-color: #3b82f6; background: #eff6ff; }
.opt-item input:disabled { cursor: not-allowed; }
.opt-item.selected { border-color: #3b82f6; background: #dbeafe; }
.opt-item.opt-correct { border-color: #10b981; background: #d1fae5; }
.opt-item.opt-wrong { border-color: #ef4444; background: #fee2e2; }
.opt-letter { font-weight: 600; color: var(--text-secondary); width: 18px; }
.opt-flag { margin-left: auto; color: #059669; font-weight: 700; }
.opt-flag.flag-wrong { color: #dc2626; }
.q-textarea { margin-top: 8px; }

.q-actions { margin-top: 16px; display: flex; align-items: center; gap: 12px; }
.q-actions-bottom { display: flex; justify-content: space-between; margin-top: 16px; }
.hint { font-size: 12px; color: var(--text-light); }

.result-panel {
  margin-top: 18px; padding: 16px; border-radius: 8px; font-size: 13px;
  background: #f8fafc; border: 1px solid #e2e8f0;
}
.panel-correct { border-color: #10b981; background: #f0fdf4; }
.panel-wrong { border-color: #ef4444; background: #fef2f2; }
.result-title { font-size: 14px; font-weight: 700; margin-bottom: 8px; }
.panel-correct .result-title { color: #16a34a; }
.panel-wrong .result-title { color: #dc2626; }
.result-row { margin-bottom: 6px; line-height: 1.6; }
.result-label { font-weight: 500; color: var(--text-secondary); }
.explanation { color: #334155; }

.input { padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px; width: 100%; box-sizing: border-box; }
.input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.1); }
textarea.input { resize: vertical; }
.btn { padding: 8px 16px; font-size: 13px; border-radius: 6px; cursor: pointer; border: 1px solid transparent; text-decoration: none; display: inline-block; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover { background: #2563eb; }
.btn-outline { border-color: #cbd5e1; color: #334155; background: #fff; }
.btn-outline:hover { border-color: #3b82f6; color: #3b82f6; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
