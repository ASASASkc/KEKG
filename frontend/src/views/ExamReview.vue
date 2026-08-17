<template>
  <div class="page-container">
    <div class="page-top">
      <div>
        <router-link to="/exams" class="back-link">&larr; 返回考试中心</router-link>
        <h1>批阅试卷</h1>
        <p class="page-subtitle" v-if="examInfo">{{ examInfo.title }}</p>
      </div>
      <button class="btn btn-outline btn-sm" @click="exportResults" v-if="submissions.length">导出 Excel</button>
    </div>

    <UiLoading v-if="loading" />

    <template v-else>
      <!-- 试卷题目预览 -->
      <div class="section">
        <h3>试卷题目 ({{ examInfo?.questions?.length || 0 }} 题)</h3>
        <div v-if="examInfo?.questions?.length" class="questions-preview">
          <div v-for="(q, i) in examInfo.questions" :key="q.question_id" class="q-preview-item">
            <span class="q-num">{{ i + 1 }}.</span>
            <span class="type-tag" :class="'type-' + q.type">{{ typeLabel(q.type) }}</span>
            <span class="q-preview-title">{{ q.title }}</span>
            <span class="q-score">{{ q.score }}分</span>
          </div>
        </div>
        <UiEmpty v-else text="暂无题目" />
      </div>

      <!-- 排行榜（教师可见） -->
      <div class="section">
        <RankingPanel :eid="eid" />
      </div>

      <!-- 学生列表 -->
      <div class="section">
        <h3>提交记录 ({{ submissions.length }})</h3>
        <table v-if="submissions.length" class="data-table">
          <thead>
            <tr>
              <th>学生</th>
              <th>提交时间</th>
              <th>客观题得分</th>
              <th>最终得分</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in submissions" :key="s.id" :class="{ 'row-active': reviewingSid === s.id }">
              <td>{{ s.username || 'ID:' + s.student_id }}</td>
              <td>{{ formatDate(s.submit_time) }}</td>
              <td>{{ s.auto_score ?? '-' }}</td>
              <td>{{ s.total_score ?? '-' }}</td>
              <td>
                <span class="status-tag" :class="s.is_reviewed ? 'status-reviewed' : 'status-pending'">
                  {{ s.is_reviewed ? '已批阅' : '待批阅' }}
                </span>
              </td>
              <td>
                <button class="btn btn-xs btn-outline" @click="openReview(s)">批阅</button>
                <button v-if="!s.is_reviewed" class="btn btn-xs btn-primary" @click="doFinalize(s.id)">完成批阅</button>
              </td>
            </tr>
          </tbody>
        </table>
        <UiEmpty v-else text="暂无提交记录" />
      </div>

      <!-- 批阅区域 -->
      <div v-if="reviewingSid" class="card review-section">
        <div class="review-top-bar">
          <h3>批阅学生: {{ reviewingStudent?.username || 'ID:' + reviewingSid }}</h3>
          <div class="review-top-actions">
            <button class="btn btn-ghost btn-sm" @click="saveAllReviews">暂存评分</button>
            <button class="btn btn-primary btn-sm" @click="doFinalize(reviewingSid)" v-if="!reviewingStudent?.is_reviewed">完成批阅</button>
          </div>
        </div>
        <UiLoading v-if="reviewLoading" />
        <UiEmpty v-else-if="reviewAnswers.length === 0" text="该学生尚未作答任何题目，或答题数据未保存成功。" />
        <div v-for="a in reviewAnswers" :key="a.id" class="review-item">
          <div class="review-q">
            <span class="type-tag" :class="'type-' + a.q_type">{{ typeLabel(a.q_type) }}</span>
            <span>{{ a.q_title }}</span>
          </div>
          <div class="review-answer">
            <span class="review-label">学生答案：</span>
            <span>{{ a.student_answer || '未作答' }}</span>
          </div>
          <div class="review-correct" v-if="a.q_answer">
            <span class="review-label">正确答案：</span>
            <span>{{ a.q_answer }}</span>
          </div>
          <div class="review-score" v-if="a.q_type === 'subjective'">
            <label>评分：</label>
            <input v-model.number="scores[a.id]" class="input input-sm" type="number" min="0" :max="a.max_score" style="width:70px" @change="saveReview(a.id)" />
            <span class="score-max">/ {{ a.max_score }} 分</span>
          </div>
          <div class="review-score" v-else>
            <span class="review-label">得分：</span>
            <span>{{ a.score ?? '-' }} / {{ a.max_score }} 分</span>
          </div>
          <div class="review-comment">
            <input v-model="comments[a.id]" class="input input-sm" placeholder="评语（可选）" @blur="saveReview(a.id)" />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import RankingPanel from '../components/RankingPanel.vue'
import { useFeedback } from '../composables/useFeedback'

const { tip, ask } = useFeedback()

const route = useRoute()
const eid = computed(() => route.params.eid)

const examInfo = ref(null)
const submissions = ref([])
const loading = ref(true)
const reviewingSid = ref(null)
const reviewingStudent = ref(null)
const reviewAnswers = ref([])
const reviewLoading = ref(false)
const scores = ref({})
const comments = ref({})

const TYPE_MAP = { choice: '选择题', judge: '判断题', fill: '填空题', subjective: '主观题' }
function typeLabel(t) { return TYPE_MAP[t] || t }

onMounted(async () => {
  loading.value = true
  try {
    const r1 = await api.get(`/exams/${eid.value}`)
    if (r1.success) examInfo.value = r1.data
    const r2 = await api.get(`/exams/${eid.value}/submissions`)
    if (r2.success) submissions.value = r2.data?.items || r2.data
  } catch (e) { console.error(e) }
  finally { loading.value = false }
})

async function openReview(sub) {
  reviewingSid.value = sub.id
  reviewingStudent.value = sub
  scores.value = {}
  comments.value = {}
  reviewLoading.value = true
  reviewAnswers.value = []
  try {
    const r = await api.get(`/exams/${eid.value}/submissions/${sub.id}`)
    if (r.success && r.data?.answers) {
      reviewAnswers.value = r.data.answers
      r.data.answers.forEach(a => {
        scores.value[a.id] = a.score || 0
        comments.value[a.id] = a.review_comment || ''
      })
    }
  } catch (e) { console.error(e) }
  finally { reviewLoading.value = false }
}

async function saveReview(aid) {
  try {
    await api.put(`/exams/${eid.value}/answers/${aid}/review`, {
      score: scores.value[aid] || 0,
      comment: comments.value[aid] || ''
    })
  } catch (e) { console.error('保存批阅失败:', e) }
}

async function saveAllReviews() {
  const reviews = reviewAnswers.value.map(a => ({
    answer_id: a.id,
    score: scores.value[a.id] || 0,
    comment: comments.value[a.id] || ''
  }))
  try {
    await api.put(`/exams/${eid.value}/batch-review`, { reviews })
    await api.put(`/exams/${eid.value}/submissions/${reviewingSid.value}/draft`, { draft: 1 })
    tip('评分已暂存')
  } catch (e) { tip('暂存失败: ' + (e.message || '')) }
}

function exportResults() {
  window.open(`${api.defaults.baseURL}/exams/${eid.value}/export-results`, '_blank')
}

function doFinalize(sid) {
  ask('确认完成批阅？将计算最终总分。', async () => {
    try {
      const r = await api.post(`/exams/${eid.value}/submissions/${sid}/finalize`)
      if (r.success) {
        // 刷新提交列表
        const r2 = await api.get(`/exams/${eid.value}/submissions`)
        if (r2.success) submissions.value = r2.data?.items || r2.data
        reviewingSid.value = null
        reviewAnswers.value = []
      }
    } catch (e) { tip('操作失败') }
  })
}

function formatDate(d) {
  if (!d) return '-'
  return d.slice(0, 16).replace('T', ' ')
}
</script>

<style scoped>
.page-container { max-width: 900px; margin: 0 auto; padding: 32px 24px; }
.page-top { margin-bottom: 20px; }
.back-link { font-size: 11px; color: var(--accent-blue); text-decoration: none; display: inline-block; margin-bottom: 8px; }
.back-link:hover { text-decoration: underline; }
.page-top h1 { font-size: 19px; margin: 0; }
.page-subtitle { font-size: 11px; color: var(--text-secondary); margin: 4px 0 0; }

.section { margin-bottom: 24px; }
.section h3 { font-size: 14px; margin: 0 0 12px; }

.loading-text { text-align: center; padding: 40px; color: var(--text-secondary); }
.empty-msg { text-align: center; padding: 24px; color: var(--text-light); font-size: 11px; }

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
.row-active td { background: #eff6ff; }

.status-tag { font-size: 10px; padding: 2px 8px; border-radius: 4px; }
.status-reviewed { background: #d1fae5; color: #065f46; }
.status-pending { background: #fef3c7; color: #92400e; }

.review-section { padding: 20px; margin-top: 20px; }
.review-top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; gap: 12px; }
.review-top-bar h3 { font-size: 13px; margin: 0; }
.review-top-actions { display: flex; gap: 8px; flex-shrink: 0; }
.review-item {
  padding: 14px; margin-bottom: 12px; border: 1px solid #e2e8f0; border-radius: 8px;
  background: #fafbfc;
}
.review-q { font-size: 11px; margin-bottom: 6px; display: flex; gap: 6px; align-items: center; }
.review-answer, .review-correct, .review-score, .review-comment { font-size: 11px; margin-bottom: 4px; }
.review-label { font-weight: 500; color: var(--text-secondary); }
.review-score { display: flex; align-items: center; gap: 6px; }
.review-score label { font-weight: 500; color: var(--text-secondary); }
.score-max { color: var(--text-light); font-size: 11px; }

.type-tag { font-size: 10px; padding: 1px 7px; border-radius: 3px; font-weight: 500; }
.type-choice { background: #dbeafe; color: #1e40af; }
.type-judge { background: #d1fae5; color: #065f46; }
.type-fill { background: #fef3c7; color: #92400e; }
.type-subjective { background: #ede9fe; color: #5b21b6; }

/* 试卷题目预览 */
.questions-preview { background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.q-preview-item {
  display: flex; align-items: center; gap: 8px; padding: 10px 14px;
  border-bottom: 1px solid #f1f5f9; font-size: 11px;
}
.q-preview-item:last-child { border-bottom: none; }
.q-num { font-weight: 600; color: var(--text-secondary); min-width: 24px; }
.q-preview-title { flex: 1; color: #334155; }
.q-score { color: var(--text-light); font-size: 11px; min-width: 40px; text-align: right; }

.btn { padding: 8px 16px; font-size: 11px; border-radius: 6px; cursor: pointer; border: 1px solid transparent; text-decoration: none; display: inline-block; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover { background: #2563eb; }
.btn-outline { border-color: #cbd5e1; color: #334155; background: #fff; }
.btn-outline:hover { border-color: #3b82f6; color: #3b82f6; }
.btn-xs { padding: 3px 10px; font-size: 10px; }
.btn-sm { padding: 6px 12px; font-size: 11px; }
.btn-ghost { border-color: #cbd5e1; background: #fff; color: #334155; }
.btn-ghost:hover { background: #f1f5f9; }
.input { padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 11px; box-sizing: border-box; }
.input-sm { width: auto; }
.input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.1); }
</style>
