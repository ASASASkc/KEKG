<template>
  <div class="page-container">
    <div class="page-top">
      <div>
        <router-link to="/exams" class="back-link">&larr; 返回考试中心</router-link>
        <h1>考试成绩</h1>
      </div>
    </div>

    <UiLoading v-if="loading" />

    <template v-else-if="result">
      <!-- 成绩摘要 -->
      <div class="card result-summary">
        <div class="summary-header">
          <h3>{{ result.exam_title || '考试' }}</h3>
          <span class="status-tag" :class="result.passed ? 'status-pass' : 'status-fail'">
            {{ result.passed ? '通过' : '未通过' }}
          </span>
        </div>
        <div class="score-display">
          <div class="score-main">
            <span class="score-number">{{ result.total_score ?? '-' }}</span>
            <span class="score-unit">分</span>
          </div>
        </div>
        <div class="summary-info">
          <div class="info-item">
            <span class="info-label">客观题得分</span>
            <span class="info-value">{{ result.auto_score ?? '-' }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">主观题得分</span>
            <span class="info-value">{{ result.review_score ?? '-' }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">及格线</span>
            <span class="info-value">{{ result.pass_score || 60 }} 分</span>
          </div>
          <div class="info-item">
            <span class="info-label">提交时间</span>
            <span class="info-value">{{ formatDate(result.submitted_at) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">答题用时</span>
            <span class="info-value">
              {{ usedTime }}
              <span v-if="isOvertime" class="overtime-tag">已超时</span>
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">作答次数</span>
            <span class="info-value">{{ result.attempt_count ?? 1 }} 次</span>
          </div>
          <div class="info-item">
            <span class="info-label">批阅状态</span>
            <span class="info-value" :style="{ color: result.is_reviewed ? '#16a34a' : '#92400e' }">
              {{ result.is_reviewed ? '已批阅' : '待批阅' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Tab 切换 -->
      <div class="tab-bar">
        <button class="tab-btn" :class="{ active: activeTab === 'detail' }" @click="activeTab = 'detail'">答题详情</button>
        <button class="tab-btn" :class="{ active: activeTab === 'analysis' }" @click="openAnalysis">分析报告</button>
      </div>

      <!-- 答题详情 Tab -->
      <div class="card" v-if="activeTab === 'detail' && result.answers?.length">
        <div class="answer-item" v-for="(a, idx) in result.answers" :key="a.id">
          <div class="answer-header">
            <span class="answer-num">{{ idx + 1 }}.</span>
            <span class="answer-title">{{ a.q_title }}</span>
            <span class="answer-type-tag">{{ typeLabel(a.q_type) }}</span>
            <span class="answer-score" :class="{ correct: a.is_correct, wrong: a.is_correct === 0 }">
              {{ a.score ?? 0 }} / {{ a.max_score_q ?? a.max_score }}
            </span>
          </div>
          <div class="answer-detail" v-if="a.q_type === 'choice'">
            <div class="options-row">
              <span v-for="(opt, oi) in (a.q_options || [])" :key="oi"
                class="option-chip"
                :class="{
                  'option-selected': isSelected(a.student_answer, oi),
                  'option-correct': isCorrectOpt(a.q_answer, oi)
                }">
                {{ opt }}
              </span>
            </div>
          </div>
          <div class="answer-detail" v-else-if="a.q_type === 'subjective'">
            <div class="detail-row"><strong>你的答案：</strong><span class="answer-text">{{ a.student_answer || '（未作答）' }}</span></div>
            <div class="detail-row" v-if="a.q_answer"><strong>参考答案：</strong><span class="answer-text correct-text">{{ a.q_answer }}</span></div>
          </div>
          <div class="answer-detail" v-else>
            <div class="detail-row"><strong>你的答案：</strong><span class="answer-text">{{ a.student_answer || '（未作答）' }}</span></div>
            <div class="detail-row"><strong>正确答案：</strong><span class="answer-text correct-text">{{ a.q_answer }}</span></div>
          </div>
          <div class="answer-detail" v-if="a.q_explanation">
            <span class="explanation-label">解析：</span><span class="explanation-text">{{ a.q_explanation }}</span>
          </div>
          <div class="answer-detail teacher-analysis" v-if="a.exam_analysis">
            <span class="explanation-label teacher-label">教师解析：</span><span class="explanation-text">{{ a.exam_analysis }}</span>
          </div>
        </div>
      </div>

      <!-- 分析报告 Tab -->
      <div v-show="activeTab === 'analysis'">
        <UiLoading v-if="analysisLoading" />
        <template v-else-if="analysis">
          <!-- 成绩位置对比 -->
          <div class="card">
            <h3>成绩对比</h3>
            <div class="compare-row">
              <div class="compare-card">
                <div class="compare-value">{{ analysis.total_score ?? '-' }}</div>
                <div class="compare-label">你的得分</div>
              </div>
              <div class="compare-divider"></div>
              <div class="compare-card">
                <div class="compare-value">{{ analysis.class_avg ?? '-' }}</div>
                <div class="compare-label">班级均分</div>
              </div>
              <div class="compare-divider"></div>
              <div class="compare-card">
                <div class="compare-value">{{ analysis.class_max ?? '-' }}</div>
                <div class="compare-label">班级最高</div>
              </div>
              <div class="compare-divider"></div>
              <div class="compare-card">
                <div class="compare-value">{{ analysis.class_min ?? '-' }}</div>
                <div class="compare-label">班级最低</div>
              </div>
            </div>
            <div v-if="analysis.class_count" class="compare-footer">共 {{ analysis.class_count }} 人提交</div>
          </div>

          <!-- 用时分析 -->
          <div class="card" v-if="analysis.time_taken_minutes != null">
            <h3>用时分析</h3>
            <div class="time-row">
              <div class="time-card">
                <span class="time-value">{{ analysis.time_taken_minutes }}</span>
                <span class="time-unit">分钟</span>
                <span class="time-label">实际用时</span>
              </div>
              <div class="time-card" v-if="analysis.duration_minutes">
                <span class="time-value">{{ analysis.duration_minutes }}</span>
                <span class="time-unit">分钟</span>
                <span class="time-label">考试时长</span>
              </div>
              <div class="time-card" v-if="analysis.duration_minutes">
                <span class="time-value" :style="{ color: analysis.time_taken_minutes > analysis.duration_minutes ? '#ef4444' : '#16a34a' }">
                  {{ analysis.time_taken_minutes > analysis.duration_minutes ? '超时' : '提前' }}
                </span>
                <span class="time-label">完成情况</span>
              </div>
            </div>
          </div>

          <!-- 题型得分率图表 -->
          <div class="card" v-show="analysis.type_breakdown && Object.keys(analysis.type_breakdown).length">
            <h3>题型得分率</h3>
            <BaseChart v-if="typeChartOption" :option="typeChartOption" height="200px" />
          </div>
          <div class="card" v-show="analysis.type_breakdown && Object.keys(analysis.type_breakdown).length === 0">
            <h3>题型得分率</h3>
            <UiEmpty text="暂无题型数据" />
          </div>

          <!-- 知识点得分率图表 -->
          <div class="card" v-show="analysis.kp_breakdown && Object.keys(analysis.kp_breakdown).length">
            <h3>知识点得分率</h3>
            <div ref="kpChartRef" class="analysis-chart analysis-chart-tall"></div>
          </div>
          <div class="card" v-show="analysis.kp_breakdown && Object.keys(analysis.kp_breakdown).length === 0">
            <h3>知识点得分率</h3>
            <UiEmpty text="暂无知识点数据" />
          </div>

          <!-- 每题分析 -->
          <div class="card" v-if="analysis.per_question?.length">
            <h3>每题分析（正确率 · 知识点 · 难度）</h3>
            <div class="pq-item" v-for="q in analysis.per_question" :key="q.question_id"
                 :class="{ 'pq-wrong': q.is_correct === 0, 'pq-correct': q.is_correct === 1 }">
              <div class="pq-header">
                <span class="pq-num">{{ q.sort_order }}.</span>
                <span class="pq-title">{{ q.title }}</span>
                <span class="pq-type-tag">{{ typeLabel(q.type) }}</span>
              </div>
              <div class="pq-meta">
                <span class="pq-tag pq-diff" :class="'diff-' + q.difficulty">{{ q.difficulty_label }}</span>
                <span class="pq-tag pq-kp">{{ q.knowledge_point }}</span>
                <span class="pq-score">{{ q.your_score }}/{{ q.max_score }} 分</span>
              </div>
              <div class="pq-rate-row">
                <span class="pq-rate-label">全班正确率</span>
                <div class="pq-rate-bar">
                  <div class="pq-rate-fill" :style="{ width: (q.class_correct_rate || 0) + '%' }"></div>
                </div>
                <span class="pq-rate-val">{{ q.class_correct_rate ?? '--' }}%</span>
                <span class="pq-rate-detail" v-if="q.class_total">({{ q.class_correct }}/{{ q.class_total }})</span>
              </div>
            </div>
          </div>
        </template>
        <UiEmpty v-else-if="!analysisLoading" text="暂无分析数据" />
      </div>
    </template>

    <UiEmpty v-else text="暂无成绩记录" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import * as echarts from 'echarts'
import BaseChart from '../components/BaseChart.vue'

const route = useRoute()
const eid = route.params.eid

const result = ref(null)
const loading = ref(true)
const activeTab = ref('detail')
const analysis = ref(null)
const analysisLoading = ref(false)
const kpChartRef = ref(null)
let kpChart = null

onMounted(async () => {
  try {
    const r = await api.get(`/exams/${eid}/my-result`)
    if (r.success) {
      const data = r.data
      result.value = {
        ...(data.submission || data),
        exam_title: data.submission ? (data.exam_title || '') : data.exam_title,
        answers: data.answers || [],
        passed: data.passed ?? ((data.submission?.total_score || data.total_score || 0) >= (data.pass_score || 60))
      }
    }
  } catch (e) { /* 404 means not submitted */ }
  finally { loading.value = false }
})

onUnmounted(() => {
  if (kpChart) { kpChart.dispose(); kpChart = null }
})

function formatDate(d) {
  if (!d) return '-'
  return d.slice(0, 16).replace('T', ' ')
}

// 答题用时（submit_time - start_time）与超时标记
const usedTime = computed(() => {
  const s = result.value?.start_time
  const e = result.value?.submitted_at || result.value?.submit_time
  if (!s || !e) return '-'
  const diff = new Date(e).getTime() - new Date(s).getTime()
  if (!(diff > 0)) return '-'
  const sec = Math.floor(diff / 1000)
  const m = Math.floor(sec / 60)
  const r = sec % 60
  return r > 0 ? `${m}分${r}秒` : `${m}分钟`
})

const isOvertime = computed(() => {
  const dur = result.value?.duration_minutes
  if (!dur || dur <= 0) return false
  const s = result.value?.start_time
  const e = result.value?.submitted_at || result.value?.submit_time
  if (!s || !e) return false
  const diff = new Date(e).getTime() - new Date(s).getTime()
  return diff > dur * 60000
})

const TYPE_LABELS = { choice: '选择', judge: '判断', fill: '填空', subjective: '主观', code: '编程' }
function typeLabel(t) { return TYPE_LABELS[t] || t }

function isSelected(studentAns, idx) {
  if (!studentAns) return false
  try {
    const arr = typeof studentAns === 'string' ? JSON.parse(studentAns) : studentAns
    return Array.isArray(arr) ? arr.includes(String.fromCharCode(65 + idx)) : studentAns === String.fromCharCode(65 + idx)
  } catch { return studentAns === String.fromCharCode(65 + idx) }
}
function isCorrectOpt(correctAns, idx) {
  if (!correctAns) return false
  try {
    const arr = typeof correctAns === 'string' ? JSON.parse(correctAns) : correctAns
    return Array.isArray(arr) ? arr.includes(String.fromCharCode(65 + idx)) : correctAns === String.fromCharCode(65 + idx)
  } catch { return correctAns === String.fromCharCode(65 + idx) }
}

async function openAnalysis() {
  activeTab.value = 'analysis'
  if (analysis.value) return
  analysisLoading.value = true
  try {
    const r = await api.get(`/exams/${eid}/analysis`)
    if (r.success) {
      analysis.value = r.data
      await nextTick()
      renderCharts()
    }
  } catch (e) {
    console.error('加载分析报告失败:', e)
  } finally {
    analysisLoading.value = false
  }
}

function renderCharts() {
  // 使用 requestAnimationFrame 确保浏览器完成布局后再初始化图表
  requestAnimationFrame(() => {
    renderKpChart()
  })
}

// 题型得分率图表（由 BaseChart 组件渲染）
const typeChartOption = computed(() => {
  const tb = analysis.value?.type_breakdown
  if (!tb) return null
  const types = Object.keys(tb)
  if (types.length === 0) return null
  const rates = types.map(t => tb[t].max_score > 0 ? Math.round(tb[t].score / tb[t].max_score * 100) : 0)
  return {
    tooltip: { trigger: 'axis', formatter: p => `${p[0].name}<br/>得分率: ${p[0].value}%` },
    grid: { top: 10, right: 20, bottom: 20, left: 40 },
    xAxis: { data: types.map(t => typeLabel(t)), axisLabel: { fontSize: 11 } },
    yAxis: { max: 100, axisLabel: { fontSize: 10, formatter: '{value}%' } },
    series: [{
      type: 'bar', data: rates,
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#3b82f6' }, { offset: 1, color: '#93c5fd' }
        ]),
        borderRadius: [4, 4, 0, 0]
      },
      barWidth: 40,
      label: { show: true, position: 'top', fontSize: 11, formatter: '{c}%' }
    }]
  }
})

function renderKpChart() {
  if (!kpChartRef.value || !analysis.value?.kp_breakdown) return
  const kb = analysis.value.kp_breakdown
  const kps = Object.keys(kb)
  if (kps.length === 0) return
  if (kpChart) kpChart.dispose()
  kpChart = echarts.init(kpChartRef.value)
  const rates = kps.map(k => kb[k].max_score > 0 ? Math.round(kb[k].score / kb[k].max_score * 100) : 0)

  kpChart.setOption({
    tooltip: { trigger: 'axis', formatter: p => `${p[0].name}<br/>得分率: ${p[0].value}%<br/>(${kb[p[0].name].score}/${kb[p[0].name].max_score}分)` },
    grid: { top: 10, right: 30, bottom: 60, left: 40 },
    xAxis: { type: 'category', data: kps.map(k => k.length > 8 ? k.slice(0, 8) + '...' : k), axisLabel: { fontSize: 10, rotate: 45 } },
    yAxis: { max: 100, axisLabel: { fontSize: 10, formatter: '{value}%' } },
    series: [{
      type: 'bar', data: rates,
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#8b5cf6' }, { offset: 1, color: '#c4b5fd' }
        ]),
        borderRadius: [4, 4, 0, 0]
      },
      barWidth: 28,
      label: { show: true, position: 'top', fontSize: 10, formatter: '{c}%' }
    }]
  })
  kpChart.resize()
}

watch(activeTab, async (val) => {
  if (val === 'analysis' && analysis.value) {
    await nextTick()
    renderCharts()
  }
})
</script>

<style scoped>
.page-container { max-width: 800px; margin: 0 auto; padding: 32px 24px; }
.page-top { margin-bottom: 20px; }
.back-link { font-size: 11px; color: var(--accent-blue); text-decoration: none; display: inline-block; margin-bottom: 8px; }
.back-link:hover { text-decoration: underline; }
.page-top h1 { font-size: 19px; margin: 0; }

.loading-text { text-align: center; padding: 40px; color: var(--text-secondary); }
.empty-msg { text-align: center; padding: 40px; color: var(--text-light); }

.result-summary { padding: 32px; text-align: center; }
.summary-header { display: flex; align-items: center; justify-content: center; gap: 12px; margin-bottom: 24px; }
.summary-header h3 { margin: 0; font-size: 16px; }
.status-tag { font-size: 11px; padding: 3px 12px; border-radius: 10px; font-weight: 500; }
.status-pass { background: #d1fae5; color: #065f46; }
.status-fail { background: #fee2e2; color: #991b1b; }

.score-display { margin-bottom: 24px; }
.score-number { font-size: 49px; font-weight: 700; color: var(--accent-blue); }
.score-unit { font-size: 18px; color: var(--text-secondary); margin-left: 4px; }

.summary-info { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; text-align: left; }
.overtime-tag {
  font-size: 10px; padding: 1px 6px; border-radius: 4px; margin-left: 4px;
  background: #fee2e2; color: #dc2626; font-weight: 500;
}
.info-item { padding: 8px 12px; background: #f8fafc; border-radius: 6px; display: flex; justify-content: space-between; }
.info-label { font-size: 11px; color: var(--text-secondary); }
.info-value { font-size: 11px; font-weight: 500; }

/* Tab */
.tab-bar { display: flex; gap: 0; margin-bottom: 16px; border-bottom: 2px solid #e2e8f0; }
.tab-btn {
  padding: 10px 24px; border: none; background: none; font-size: 12px; font-weight: 500;
  color: #94a3b8; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -2px;
  transition: all 0.2s;
}
.tab-btn:hover { color: #475569; }
.tab-btn.active { color: #3b82f6; border-bottom-color: #3b82f6; }

/* 答题详情 */
.answer-item { padding: 16px 0; border-bottom: 1px solid #f1f5f9; }
.answer-item:last-child { border-bottom: none; }
.answer-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.answer-num { font-weight: 600; color: var(--text-secondary); min-width: 24px; }
.answer-title { flex: 1; font-size: 12px; font-weight: 500; }
.answer-type-tag { font-size: 10px; padding: 1px 6px; border-radius: 4px; background: #e2e8f0; color: #475569; }
.answer-score { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 4px; background: #f1f5f9; }
.answer-score.correct { background: #d1fae5; color: #065f46; }
.answer-score.wrong { background: #fee2e2; color: #991b1b; }
.answer-detail { margin-left: 32px; margin-top: 4px; }
.detail-row { font-size: 11px; margin: 2px 0; }
.answer-text { color: var(--text-secondary); word-break: break-all; }
.correct-text { color: #16a34a; }
.explanation-label { font-size: 11px; color: var(--accent-blue); }
.explanation-text { font-size: 11px; color: var(--text-secondary); }
.teacher-analysis { margin-top: 2px; padding: 6px 8px; background: #fefce8; border-radius: 4px; }
.teacher-label { color: #b45309; font-weight: 600; }
.options-row { display: flex; gap: 8px; flex-wrap: wrap; }
.option-chip { padding: 4px 12px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 11px; background: #fff; }
.option-selected { border-color: #3b82f6; background: #eff6ff; }
.option-correct { border-color: #16a34a; background: #d1fae5; }
.option-selected.option-correct { background: #d1fae5; border-color: #16a34a; }

/* 分析报告 */
.analysis-chart { width: 100%; height: 200px; }
.analysis-chart-tall { width: 100%; height: 300px; }

.compare-row { display: flex; align-items: stretch; justify-content: space-around; padding: 16px 0; }
.compare-card { text-align: center; flex: 1; }
.compare-value { font-size: 25px; font-weight: 700; color: #1e293b; }
.compare-label { font-size: 11px; color: #94a3b8; margin-top: 4px; }
.compare-divider { width: 1px; background: #e2e8f0; align-self: stretch; }
.compare-footer { text-align: center; font-size: 11px; color: #94a3b8; margin-top: 4px; }

.time-row { display: flex; gap: 16px; padding: 8px 0; }
.time-card {
  flex: 1; text-align: center; padding: 16px; background: #f8fafc;
  border: 1px solid #e2e8f0; border-radius: 8px;
}
.time-value { font-size: 18px; font-weight: 700; color: #1e293b; }
.time-unit { font-size: 12px; color: #64748b; margin-left: 2px; }
.time-label { display: block; font-size: 10px; color: #94a3b8; margin-top: 4px; }

.card { background: #fff; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); padding: 24px; margin-bottom: 16px; }
.card h3 { font-size: 13px; margin: 0 0 16px; color: #1e293b; }

/* 每题分析 */
.pq-item { padding: 12px 0; border-bottom: 1px solid #f1f5f9; }
.pq-item:last-child { border-bottom: none; }
.pq-wrong { border-left: 3px solid #fca5a5; padding-left: 12px; }
.pq-correct { border-left: 3px solid #86efac; padding-left: 12px; }
.pq-header { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 6px; }
.pq-num { font-weight: 600; color: #94a3b8; font-size: 11px; min-width: 20px; }
.pq-title { flex: 1; font-size: 11px; color: #1e293b; font-weight: 500; }
.pq-type-tag { font-size: 10px; padding: 1px 6px; border-radius: 4px; background: #e2e8f0; color: #475569; flex-shrink: 0; }
.pq-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; padding-left: 28px; }
.pq-tag { font-size: 10px; padding: 1px 8px; border-radius: 10px; }
.pq-diff { background: #f1f5f9; color: #64748b; }
.pq-diff.diff-1 { background: #dcfce7; color: #16a34a; }
.pq-diff.diff-2 { background: #dbeafe; color: #2563eb; }
.pq-diff.diff-3 { background: #fef3c7; color: #d97706; }
.pq-diff.diff-4 { background: #fee2e2; color: #dc2626; }
.pq-diff.diff-5 { background: #fce7f3; color: #be185d; }
.pq-kp { background: #ede9fe; color: #7c3aed; }
.pq-score { margin-left: auto; font-size: 11px; font-weight: 600; color: #475569; }
.pq-rate-row { display: flex; align-items: center; gap: 8px; padding-left: 28px; }
.pq-rate-label { font-size: 10px; color: #94a3b8; width: 60px; flex-shrink: 0; }
.pq-rate-bar { flex: 1; height: 6px; background: #f1f5f9; border-radius: 3px; overflow: hidden; }
.pq-rate-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #93c5fd); border-radius: 3px; transition: width 0.3s; }
.pq-rate-val { font-size: 10px; font-weight: 600; color: #3b82f6; min-width: 32px; }
.pq-rate-detail { font-size: 10px; color: #94a3b8; }
</style>
