<template>
  <div class="page-container">
    <div class="page-top">
      <h1>学习路径</h1>
      <p class="page-subtitle">基于答题情况的个性化学习规划</p>
    </div>

    <UiLoading v-if="loading" />
    <div v-else-if="error" class="empty-card">
      <p>加载失败：{{ error }}</p>
      <button class="btn btn-primary" @click="retry" style="margin-top:12px">重试</button>
    </div>

    <template v-else-if="assessment">
      <!-- 水平评估卡片 -->
      <div class="card assess-card">
        <div class="assess-left">
          <div class="score-big">{{ assessment.composite_score }}</div>
          <div class="score-label">综合评分</div>
          <div class="level-tag" :class="'lv-' + assessment.level_index">{{ assessment.level }}</div>
        </div>
        <div class="assess-right">
          <div class="formula-hint">均分 {{ assessment.avg_score }} × 60% + 末考 {{ assessment.last_exam?.pct || 0 }} × 40%</div>
          <div class="assess-detail" v-if="assessment.last_exam">
            <span>最近考试：{{ assessment.last_exam.title }}</span>
            <span>{{ assessment.last_exam.score }}/{{ assessment.last_exam.max_score }}（{{ assessment.last_exam.pct }}分）</span>
          </div>
          <div class="assess-detail" v-if="!assessment.last_exam">暂无考试记录</div>
          <div class="assess-detail">共参加 {{ assessment.exam_count }} 次考试</div>

          <!-- 历史分数小图 -->
          <div v-if="assessment.history_scores?.length > 1" ref="trendRef" class="mini-chart"></div>
        </div>
      </div>

      <!-- 薄弱知识点 -->
      <div class="card" v-if="assessment.weak_points?.length">
        <h3>薄弱知识点（{{ assessment.weak_points.length }} 个）</h3>
        <div class="weak-list">
          <div v-for="wp in assessment.weak_points" :key="wp.knowledge_point_id" class="weak-item">
            <span class="weak-name">{{ wp.name }}</span>
            <span class="weak-cat" v-if="wp.category">{{ wp.category }}</span>
            <span class="weak-count">错 {{ wp.wrong_count }} 次</span>
          </div>
        </div>
      </div>

      <!-- 学习路径 -->
      <div class="card" v-if="path && path.recommended_sequence?.length">
        <h3>推荐学习路线</h3>
        <p class="form-hint">{{ path.message }}</p>
        <div class="path-chain">
          <template v-for="(node, idx) in path.recommended_sequence" :key="node.id">
            <div class="path-node" :class="{ 'is-weak': node.is_weak, 'is-known': node.is_known }" @click="toggleNodeResources(node)">
              <div class="node-step">{{ idx + 1 }}</div>
              <div class="node-info">
                <div class="node-name">{{ node.name }}</div>
                <div class="node-meta">
                  <span v-if="node.category" class="tag">{{ node.category }}</span>
                  <span v-if="node.is_weak" class="tag tag-weak">薄弱</span>
                  <span v-if="node.is_known" class="tag tag-known">已掌握</span>
                  <span v-if="node._resources?.length" class="tag tag-res" title="有学习资源">📦 {{ node._resources.length }}</span>
                </div>
              </div>
            </div>
            <div v-if="idx < path.recommended_sequence.length - 1" class="path-arrow">→</div>

            <!-- 该节点的学习资源 -->
            <div v-if="node._expanded && node._resources && node._resources.length" class="node-resources">
              <div class="res-title">关联资源（{{ node._resources.length }}）</div>
              <div v-for="r in node._resources" :key="r.id" class="res-item">
                <span class="res-icon">{{ resIcon(r.type) }}</span>
                <span class="res-name">{{ r.title }}</span>
                <span class="res-type-tag" :class="'r-' + r.type">{{ resTypeLabel(r.type) }}</span>
                <a v-if="r.url" :href="r.url" target="_blank" class="res-link">打开</a>
              </div>
            </div>
          </template>
        </div>
      </div>

      <div class="card empty-card" v-else-if="!loading">
        <p>{{ path?.message || '暂无学习路径推荐，请先完成考试' }}</p>
      </div>

      <!-- 领域偏好推送 -->
      <div class="card" v-if="trackRecs">
        <h3>📊 领域偏好推送</h3>
        <p class="form-hint">根据你的答题行为，分析你在各个知识领域中的专注度</p>

        <!-- 主导领域 -->
        <div class="track-bars" v-if="trackRecs.dominant_tracks?.length">
          <div v-for="t in trackRecs.dominant_tracks" :key="t.track" class="track-bar-row">
            <span class="track-name">{{ t.track }}</span>
            <div class="track-bar">
              <div class="track-bar-fill" :style="{ width: t.focus_score + '%' }"></div>
            </div>
            <span class="track-score">{{ t.focus_score }}</span>
          </div>
        </div>
        <p v-else class="form-hint">暂无答题数据，完成考试后开始分析</p>

        <!-- 领域级学习路径 -->
        <div v-if="trackRecs.path_recommendations?.length">
          <h4 style="margin-top:20px">推荐学习路线</h4>
          <div v-for="pr in trackRecs.path_recommendations" :key="pr.track" class="track-section">
            <div class="track-section-header">
              <span class="track-section-title">{{ pr.track }}</span>
              <span class="track-section-score">专注度 {{ pr.focus_score }}</span>
            </div>
            <div v-if="pr.sub_areas?.length" class="sub-areas">
              <span v-for="sa in pr.sub_areas" :key="sa.name" class="sub-area-tag">
                {{ sa.name }}（{{ sa.count }}）
              </span>
            </div>
            <div v-if="pr.entry_points?.length" class="entry-points">
              <span class="entry-hint">建议从以下知识点开始：</span>
              <div v-for="ep in pr.entry_points.slice(0, 5)" :key="ep.id" class="entry-item">
                <router-link :to="'/graph/' + ep.id">{{ ep.name }}</router-link>
                <span class="tag" v-if="ep.category">{{ ep.category }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 资源推荐 -->
        <div v-if="trackRecs.resource_recommendations?.length">
          <h4 style="margin-top:20px">推荐学习资源</h4>
          <div v-for="rr in trackRecs.resource_recommendations" :key="rr.track" class="track-res-section">
            <div class="track-res-header">{{ rr.track }}</div>
            <div v-for="r in rr.resources" :key="r.id" class="res-row">
              <span class="res-icon">{{ resIcon(r.type) }}</span>
              <span class="res-name">{{ r.title }}</span>
              <span class="res-type-tag" :class="'r-' + r.type">{{ resTypeLabel(r.type) }}</span>
              <a v-if="r.url" :href="r.url" target="_blank" class="res-link">打开</a>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 学习数据看板 -->
    <div class="card dash-card" v-if="dashboard">
      <h3>学习数据看板</h3>
      <div class="dash-stats">
        <div class="dash-stat">
          <div class="dash-num">{{ fmtMinutes(dashboard.study_minutes) }}</div>
          <div class="dash-label">总学习时长</div>
        </div>
        <div class="dash-stat">
          <div class="dash-num">{{ dashboard.practice_redo?.total || 0 }}</div>
          <div class="dash-label">刷题总数</div>
        </div>
        <div class="dash-stat">
          <div class="dash-num">{{ dashboard.practice_redo?.rate ?? 0 }}%</div>
          <div class="dash-label">刷题正确率</div>
        </div>
        <div class="dash-stat">
          <div class="dash-num">{{ dashboard.plan?.active || 0 }}<span class="dash-sub">/{{ dashboard.plan?.total || 0 }}</span></div>
          <div class="dash-label">进行中计划</div>
        </div>
        <div class="dash-stat">
          <div class="dash-num">{{ dashboard.plan?.avg_progress ?? 0 }}%</div>
          <div class="dash-label">平均进度</div>
        </div>
      </div>
      <div class="dash-heat-wrap">
        <div class="dash-heat" v-if="dashboard.weekly_heatmap?.length">
          <div v-for="(d, i) in dashboard.weekly_heatmap" :key="i"
               class="hm-cell" :class="'hm-' + heatLevel(d.count)"
               :title="d.date + '：' + d.count + ' 次活动'"></div>
        </div>
        <p v-else class="form-hint">暂无活动记录</p>
        <div class="dash-legend">
          <span class="lg-label">少</span>
          <span class="lg-cell hm-0"></span>
          <span class="lg-cell hm-1"></span>
          <span class="lg-cell hm-2"></span>
          <span class="lg-cell hm-3"></span>
          <span class="lg-cell hm-4"></span>
          <span class="lg-label">多</span>
        </div>
      </div>
    </div>

    <!-- 自定义学习计划 -->
    <div class="card plan-section">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
        <h3 style="margin:0;">自定义学习计划</h3>
        <button class="btn btn-sm btn-primary" @click="openPlanCreate">新建计划</button>
      </div>
      <UiLoading v-if="plansLoading" />
      <UiEmpty v-else-if="plans.length === 0" text="暂无自定义学习计划，点击'新建计划'开始" />
      <div v-else class="plan-list">
        <div v-for="plan in plans" :key="plan.id" class="plan-card" :class="{ 'plan-done': plan.status === 'done' }">
          <div class="plan-main">
            <div class="plan-header">
              <span class="plan-title">{{ plan.title }}</span>
              <span class="plan-status" :class="'ps-' + plan.status">{{ statusLabel(plan.status) }}</span>
            </div>
            <div v-if="plan.description" class="plan-desc">{{ plan.description }}</div>
            <div class="plan-meta">
              <span v-if="plan.target_date">目标日期：{{ plan.target_date }}</span>
              <span v-if="plan.knowledge_point_ids?.length">{{ plan.knowledge_point_ids.length }} 个知识点</span>
              <span class="plan-qlink" @click.stop="togglePlanQuestions(plan)">
                题单 {{ plan.question_done }}/{{ plan.question_total }}
              </span>
            </div>
            <div class="plan-stats-row" @click="toggleCalendar(plan)" title="点击查看打卡日历">
              <span class="plan-stat">📅 {{ plan.total_checkins || 0 }} 天</span>
              <span class="plan-stat">⏱ {{ plan.total_study_minutes || 0 }} 分钟</span>
              <span class="plan-stat">📝 {{ plan.total_questions || 0 }} 题</span>
            </div>
            <div class="plan-progress-bar">
              <div class="plan-bar-fill" :style="{ width: plan.progress + '%' }"></div>
            </div>
            <div class="plan-progress-text">进度 {{ plan.progress }}%</div>
            <!-- 题单明细 -->
            <div v-if="plan._showQuestions" class="plan-questions">
              <div v-if="plan._qLoading" class="cal-loading">...</div>
              <template v-else>
                <div v-if="plan._qItems?.length" class="plan-q-list">
                  <router-link v-for="q in plan._qItems" :key="q.id"
                               :to="'/practice/' + q.id" class="plan-q-item"
                               :class="'pq-' + q.status">
                    <span class="type-tag" :class="'type-' + q.type">{{ typeLabel(q.type) }}</span>
                    <span class="plan-q-title">{{ q.title }}</span>
                    <span class="plan-q-status">{{ qStatusText(q.status) }}</span>
                  </router-link>
                </div>
                <p v-else class="form-hint">该计划暂未绑定题目</p>
              </template>
            </div>
          </div>
          <div class="plan-actions">
            <button class="btn btn-xs btn-checkin" @click="openCheckin(plan)">打卡</button>
            <button class="btn-text" @click="openPlanEdit(plan)">编辑</button>
            <input type="range" class="plan-slider" min="0" max="100" :value="plan.progress"
                   @change="setProgress(plan, $event)" title="拖拽调整进度" />
            <button class="btn-text btn-danger-text" @click="deletePlan(plan.id)">删除</button>
          </div>
          <!-- 日历 -->
          <div class="plan-calendar" v-if="plan._showCalendar" ref="calendarRefs" :data-plan-id="plan.id">
            <div class="cal-header">
              <button class="cal-nav" @click="shiftCalMonth(plan, -1)">←</button>
              <span class="cal-month-label">{{ plan._calYearMonth || currentYearMonth }}</span>
              <button class="cal-nav" @click="shiftCalMonth(plan, 1)">→</button>
              <span class="cal-streak" v-if="plan._streak > 0">🔥 连续 {{ plan._streak }} 天</span>
              <button class="cal-close" @click="plan._showCalendar = false">×</button>
            </div>
            <div class="cal-weekdays">
              <span v-for="w in calWeekdays" :key="w">{{ w }}</span>
            </div>
            <div class="cal-grid">
              <div v-for="(d, di) in plan._calDays" :key="di"
                   class="cal-day" :class="{ 'cal-today': d.isToday, 'cal-checked': d.checked, 'cal-other': d.otherMonth }"
                   :title="d.dateStr + (d.checked ? ' | ' + formatCalDuration(d.mins) : '')">
                <span class="cal-day-num">{{ d.day }}</span>
                <span v-if="d.checked" class="cal-dot"></span>
              </div>
            </div>
            <div v-if="plan._calLoading" class="cal-loading">...</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 计划编辑弹窗 -->
    <div class="modal-overlay" v-if="planForm.show" @click.self="closePlanForm">
      <div class="plan-modal">
        <div class="plan-modal-header">
          <h3>{{ planForm.editId ? '编辑计划' : '新建计划' }}</h3>
          <button class="modal-close-btn" @click="closePlanForm">&times;</button>
        </div>
        <div class="plan-modal-body">
          <label class="form-label">计划标题 <span class="required">*</span></label>
          <input class="form-input" v-model="planForm.title" placeholder="例如：本周复习计划" />

          <label class="form-label">描述</label>
          <textarea class="form-input form-textarea" v-model="planForm.description" rows="3" placeholder="计划描述（可选）"></textarea>

          <label class="form-label">目标日期</label>
          <input type="date" class="form-input" v-model="planForm.target_date" />

          <label class="form-label">目标进度 (%)</label>
          <input type="number" class="form-input" v-model.number="planForm.progress" min="0" max="100" />

          <label class="form-label">绑定题目（可选，构成题单）</label>
          <div class="plan-q-picker">
            <div class="plan-q-search">
              <input class="form-input" v-model="qPicker.keyword" placeholder="搜索题目关键词..."
                     @input="debounceSearchQuestions" />
              <span class="plan-q-count">已选 {{ planForm.question_ids.length }} 题</span>
            </div>
            <div class="plan-q-options" v-if="qPicker.options.length">
              <label v-for="q in qPicker.options" :key="q.id" class="plan-q-opt"
                     :class="{ 'q-opt-on': planForm.question_ids.includes(q.id) }">
                <input type="checkbox" :value="q.id" v-model="planForm.question_ids" />
                <span class="type-tag" :class="'type-' + q.type">{{ typeLabel(q.type) }}</span>
                <span class="plan-q-opt-title">{{ q.title }}</span>
                <span class="q-opt-tick" v-if="planForm.question_ids.includes(q.id)">✓</span>
              </label>
            </div>
            <p v-else-if="qPicker.searched" class="form-hint">无匹配题目（仅显示已审核题目）</p>
            <button v-if="planForm.question_ids.length" class="btn-text" @click="planForm.question_ids = []">清空已选</button>
          </div>
        </div>
        <div class="plan-modal-footer">
          <button class="btn btn-ghost" @click="closePlanForm">取消</button>
          <button class="btn btn-primary" @click="submitPlan" :disabled="!planForm.title.trim()">
            {{ planForm.editId ? '保存' : '创建' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 打卡弹窗 -->
    <div class="modal-overlay" v-if="checkinForm.show" @click.self="closeCheckin">
      <div class="plan-modal">
        <div class="plan-modal-header">
          <h3>打卡 — {{ checkinForm.planTitle }}</h3>
          <button class="modal-close-btn" @click="closeCheckin">&times;</button>
        </div>
        <div class="plan-modal-body">
          <label class="form-label">学习时长（分钟）</label>
          <input type="number" class="form-input" v-model.number="checkinForm.minutes" min="0" placeholder="0" />

          <label class="form-label">做题数量</label>
          <input type="number" class="form-input" v-model.number="checkinForm.questions" min="0" placeholder="0" />

          <label class="form-label">备注</label>
          <textarea class="form-input form-textarea" v-model="checkinForm.notes" rows="2" placeholder="今天学了什么？（可选）"></textarea>
        </div>
        <div class="plan-modal-footer">
          <button class="btn btn-ghost" @click="closeCheckin">取消</button>
          <button class="btn btn-primary" @click="doCheckin">打卡</button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch, reactive, computed } from 'vue'
import api from '../api'
import * as echarts from 'echarts'
import { useFeedback } from '../composables/useFeedback'
import { authStore } from '../stores/auth'

const { tip, ask } = useFeedback()

const loading = ref(true)
const error = ref('')
const assessment = ref(null)
const path = ref(null)
const trackRecs = ref(null)
const trendRef = ref(null)
let trendChart = null

// 学习数据看板
const dashboard = ref(null)
async function loadDashboard() {
  const uid = authStore.user?.id
  if (!uid) return
  try {
    const r = await api.get(`/users/${uid}/profile`)
    if (r.success) dashboard.value = r.data.stats
  } catch (e) {
    console.error('加载学习看板失败:', e)
  }
}
function fmtMinutes(mins) {
  const m = Number(mins) || 0
  if (m < 60) return `${m} 分钟`
  if (m < 24 * 60) {
    const h = Math.floor(m / 60)
    const r = m % 60
    return r ? `${h}h${r}m` : `${h} 小时`
  }
  return `${(m / 60 / 24).toFixed(1)} 天`
}
function heatLevel(c) {
  const n = Number(c) || 0
  if (n <= 0) return 0
  if (n === 1) return 1
  if (n <= 3) return 2
  if (n <= 6) return 3
  return 4
}

// 自定义学习计划
const plans = ref([])
const plansLoading = ref(false)
const planForm = reactive({
  show: false, editId: null, title: '', description: '', target_date: '', progress: 0,
  question_ids: []
})

// 题单选择器
const qPicker = reactive({ keyword: '', options: [], searched: false })
let qSearchTimer = null
function debounceSearchQuestions() {
  clearTimeout(qSearchTimer)
  qSearchTimer = setTimeout(searchQuestions, 300)
}
async function searchQuestions() {
  try {
    const r = await api.get('/practice/questions', {
      params: { page: 1, page_size: 10, keyword: qPicker.keyword || '' }
    })
    qPicker.options = (r.data && r.data.items) || []
    qPicker.searched = true
  } catch (e) {
    console.error('搜索题目失败:', e)
  }
}

// 打卡
const checkinForm = reactive({
  show: false, planId: null, planTitle: '', minutes: 0, questions: 0, notes: ''
})
const calWeekdays = ['日', '一', '二', '三', '四', '五', '六']
const currentYearMonth = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
})

// 安全超时：15 秒后强制结束 loading
let safetyTimer = null
function clearSafetyTimer() {
  if (safetyTimer) { clearTimeout(safetyTimer); safetyTimer = null }
}

async function retry() {
  clearSafetyTimer()
  loading.value = true
  error.value = ''
  assessment.value = null
  path.value = null
  trackRecs.value = null
  await loadData()
}

onMounted(async () => {
  await loadData()
  loadDashboard()
})

async function loadData(retry = true) {
  clearSafetyTimer()
  safetyTimer = setTimeout(() => {
    if (loading.value) {
      loading.value = false
      if (!error.value) error.value = '加载超时，请刷新页面重试'
    }
  }, 15000)

  try {
    const [a, p, tr] = await Promise.all([
      api.get('/learning/assessment'),
      api.get('/learning/path'),
      api.get('/learning/track-recommendations')
    ])
    if (a.data) assessment.value = a.data
    if (p.data) {
      path.value = p.data
      await loadResources()
    }
    if (tr.data) trackRecs.value = tr.data
    await loadPlans()
  } catch (e) {
    if (retry) {
      await new Promise(r => setTimeout(r, 500))
      return loadData(false)
    }
    error.value = e?.message || e?.data?.message || '网络请求失败'
    console.error('加载学习路径失败:', e)
  } finally {
    loading.value = false
    clearSafetyTimer()
  }
}

async function loadResources() {
  if (!path.value?.recommended_sequence?.length) return
  const kpIds = path.value.recommended_sequence.map(n => n.id)
  try {
    const { data: resMap } = await api.post('/resources/for-path', { knowledge_point_ids: kpIds })
    const map = resMap || {}
    path.value.recommended_sequence.forEach(n => {
      n._resources = map[n.id] || []
      n._expanded = false
    })
  } catch { /* ignore */ }
}

function toggleNodeResources(node) {
  node._expanded = !node._expanded
}

function resIcon(type) {
  const m = { doc: '📄', video: '🎬', link: '🔗', exercise: '✏️', project: '📁' }
  return m[type] || '📌'
}

function resTypeLabel(type) {
  const m = { doc: '文档', video: '视频', link: '链接', exercise: '练习', project: '项目' }
  return m[type] || type
}

// ── 自定义学习计划 ──
function statusLabel(s) {
  const m = { active: '进行中', done: '已完成', paused: '已暂停' }
  return m[s] || s
}

async function loadPlans() {
  plansLoading.value = true
  try {
    const res = await api.get('/learning/plans')
    if (res.success) plans.value = res.data || []
  } catch (e) {
    console.error('加载计划失败:', e)
  } finally {
    plansLoading.value = false
  }
}

function openPlanCreate() {
  planForm.show = true
  planForm.editId = null
  planForm.title = ''
  planForm.description = ''
  planForm.target_date = ''
  planForm.progress = 0
  planForm.question_ids = []
  qPicker.keyword = ''
  qPicker.options = []
  qPicker.searched = false
  searchQuestions()
}

function openPlanEdit(plan) {
  planForm.show = true
  planForm.editId = plan.id
  planForm.title = plan.title || ''
  planForm.description = plan.description || ''
  planForm.target_date = plan.target_date || ''
  planForm.progress = plan.progress || 0
  planForm.question_ids = plan.question_ids ? [...plan.question_ids] : []
  qPicker.keyword = ''
  qPicker.options = []
  qPicker.searched = false
  searchQuestions()
}

function closePlanForm() {
  planForm.show = false
}

async function submitPlan() {
  if (!planForm.title.trim()) return
  try {
    const payload = {
      title: planForm.title.trim(),
      description: planForm.description,
      target_date: planForm.target_date || null,
      progress: planForm.progress || 0,
      question_ids: planForm.question_ids
    }
    if (planForm.editId) {
      await api.put(`/learning/plans/${planForm.editId}`, payload)
    } else {
      await api.post('/learning/plans', payload)
    }
    closePlanForm()
    await loadPlans()
  } catch (e) {
    console.error('保存计划失败:', e)
  }
}

// ── 题单明细 ──
const TYPE_MAP = { choice: '选择', judge: '判断', fill: '填空', subjective: '主观', code: '编程' }
function typeLabel(t) { return TYPE_MAP[t] || t }

function qStatusText(s) {
  return { done: '已掌握', wrong: '待重练', undone: '未做' }[s] || s
}

async function togglePlanQuestions(plan) {
  if (plan._showQuestions) {
    plan._showQuestions = false
    return
  }
  plan._showQuestions = true
  plan._qLoading = true
  try {
    const res = await api.get(`/learning/plans/${plan.id}/questions`)
    if (res.success) {
      plan._qItems = res.data.items || []
      plan.question_done = res.data.done
      plan.question_total = res.data.total
      plan.progress = res.data.progress || plan.progress
    }
  } catch (e) {
    console.error('加载题单失败:', e)
  } finally {
    plan._qLoading = false
  }
}

async function setProgress(plan, event) {
  const val = parseInt(event.target.value)
  try {
    await api.put(`/learning/plans/${plan.id}`, { progress: val })
    plan.progress = val
    if (val >= 100) plan.status = 'done'
  } catch (e) {
    console.error('更新进度失败:', e)
  }
}

function deletePlan(planId) {
  ask('确定删除该学习计划？', async () => {
    try {
      await api.delete(`/learning/plans/${planId}`)
      await loadPlans()
    } catch (e) {
      console.error('删除计划失败:', e)
    }
  })
}

// ── 打卡 & 日历 ──

function openCheckin(plan) {
  checkinForm.show = true
  checkinForm.planId = plan.id
  checkinForm.planTitle = plan.title
  checkinForm.minutes = 0
  checkinForm.questions = 0
  checkinForm.notes = ''
}

function closeCheckin() {
  checkinForm.show = false
}

async function doCheckin() {
  if (!checkinForm.planId) return
  try {
    await api.post(`/learning/plans/${checkinForm.planId}/checkin`, {
      study_minutes: checkinForm.minutes || 0,
      question_count: checkinForm.questions || 0,
      notes: checkinForm.notes
    })
    closeCheckin()
    await loadPlans()
    // Refresh calendar if open
    const plan = plans.value.find(p => p.id === checkinForm.planId)
    if (plan && plan._showCalendar) {
      await loadCalCheckins(plan)
    }
  } catch (e) {
    console.error('打卡失败:', e)
  }
}

async function toggleCalendar(plan) {
  if (plan._showCalendar) {
    plan._showCalendar = false
    return
  }
  plan._showCalendar = true
  plan._calYearMonth = plan._calYearMonth || currentYearMonth.value
  await loadCalCheckins(plan)
}

async function loadCalCheckins(plan) {
  plan._calLoading = true
  try {
    const res = await api.get(`/learning/plans/${plan.id}/checkins?month=${plan._calYearMonth}`)
    if (res.success) {
      plan._streak = res.data.streak || 0
      buildCalDays(plan, res.data.checkins || [])
    }
  } catch (e) {
    console.error('加载打卡记录失败:', e)
  } finally {
    plan._calLoading = false
  }
}

function buildCalDays(plan, checkins) {
  const ym = plan._calYearMonth.split('-')
  const y = parseInt(ym[0]), m = parseInt(ym[1])
  const firstDay = new Date(y, m - 1, 1)
  const lastDay = new Date(y, m, 0)
  const startDow = firstDay.getDay()
  const daysInMonth = lastDay.getDate()

  const today = new Date()
  const todayStr = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`

  const checkinSet = new Map()
  for (const c of checkins) {
    const d = String(c.checkin_date).slice(0, 10)
    checkinSet.set(d, c.study_minutes || 0)
  }

  const days = []
  // Fill before month
  const prevLast = new Date(y, m - 1, 0).getDate()
  for (let i = startDow - 1; i >= 0; i--) {
    const d = prevLast - i
    const ds = `${y}-${String(m-1||12).padStart(2,'0')}-${String(d).padStart(2,'0')}`
    days.push({ day: d, dateStr: ds, isToday: ds === todayStr, checked: checkinSet.has(ds), mins: checkinSet.get(ds) || 0, otherMonth: true })
  }
  // Current month
  for (let d = 1; d <= daysInMonth; d++) {
    const ds = `${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`
    days.push({ day: d, dateStr: ds, isToday: ds === todayStr, checked: checkinSet.has(ds), mins: checkinSet.get(ds) || 0, otherMonth: false })
  }
  // Fill after month
  const remaining = 7 - (days.length % 7)
  if (remaining < 7) {
    for (let d = 1; d <= remaining; d++) {
      const nm = m === 12 ? 1 : m + 1
      const ny = m === 12 ? y + 1 : y
      const ds = `${ny}-${String(nm).padStart(2,'0')}-${String(d).padStart(2,'0')}`
      days.push({ day: d, dateStr: ds, isToday: ds === todayStr, checked: checkinSet.has(ds), mins: checkinSet.get(ds) || 0, otherMonth: true })
    }
  }
  plan._calDays = days
}

async function shiftCalMonth(plan, delta) {
  const ym = plan._calYearMonth.split('-')
  let y = parseInt(ym[0]), m = parseInt(ym[1]) + delta
  if (m < 1) { y--; m = 12 }
  if (m > 12) { y++; m = 1 }
  plan._calYearMonth = `${y}-${String(m).padStart(2, '0')}`
  await loadCalCheckins(plan)
}

function formatCalDuration(mins) {
  if (!mins) return ''
  return mins >= 60 ? `${Math.floor(mins/60)}h${mins%60}m` : `${mins}分钟`
}

watch(assessment, async (val) => {
  if (!val?.history_scores || val.history_scores.length <= 1) return
  await nextTick()
  renderTrend(val.history_scores)
}, { flush: 'post' })

function renderTrend(scores) {
  if (!trendRef.value) return
  if (trendChart) trendChart.dispose()
  trendChart = echarts.init(trendRef.value)
  trendChart.setOption({
    grid: { top: 10, right: 10, bottom: 20, left: 35 },
    xAxis: { show: false, data: scores.map((_, i) => `第${i + 1}次`) },
    yAxis: { min: 0, max: 100, splitNumber: 3, axisLabel: { fontSize: 10 } },
    series: [{
      type: 'line', data: scores, smooth: true,
      lineStyle: { color: '#3b82f6', width: 2 },
      areaStyle: { color: 'rgba(59,130,246,0.1)' },
      itemStyle: { color: '#3b82f6' }
    }]
  })
}
</script>

<style scoped>
.page-container { max-width: 860px; margin: 0 auto; padding: 32px 24px; }
.page-top { margin-bottom: 24px; }
.page-top h1 { font-size: 22px; margin: 0; }
.page-subtitle { font-size: 13px; color: var(--text-secondary); margin: 4px 0 0; }
.loading-text { text-align: center; padding: 60px; color: var(--text-secondary); }
.form-hint { font-size: 12px; color: var(--text-light); margin-bottom: 16px; }

.assess-card {
  display: flex; gap: 32px; align-items: center; padding: 24px 28px; margin-bottom: 16px;
}
.assess-left { text-align: center; min-width: 120px; }
.score-big { font-size: 48px; font-weight: 700; color: #1e293b; line-height: 1.1; }
.score-label { font-size: 12px; color: var(--text-secondary); margin: 4px 0 8px; }
.level-tag { display: inline-block; padding: 3px 14px; border-radius: 12px; font-size: 13px; font-weight: 600; }
.lv-4 { background: #d1fae5; color: #065f46; }
.lv-3 { background: #dbeafe; color: #1e40af; }
.lv-2 { background: #fef3c7; color: #92400e; }
.lv-1 { background: #fee2e2; color: #991b1b; }

.assess-right { flex: 1; }
.formula-hint { font-size: 12px; color: var(--text-light); margin-bottom: 8px; }
.assess-detail { font-size: 13px; color: var(--text-secondary); margin-bottom: 4px; display: flex; gap: 16px; }
.mini-chart { height: 80px; margin-top: 8px; }

.weak-list { display: flex; flex-wrap: wrap; gap: 8px; }
.weak-item {
  display: flex; align-items: center; gap: 8px; padding: 6px 12px;
  background: #fef2f2; border-radius: 6px; font-size: 13px;
}
.weak-name { font-weight: 500; color: #991b1b; }
.weak-cat { font-size: 11px; padding: 1px 6px; background: #fee2e2; border-radius: 3px; color: #b91c1c; }
.weak-count { font-size: 11px; color: #dc2626; }
.tag { font-size: 11px; padding: 1px 6px; border-radius: 3px; background: #f1f5f9; color: #64748b; }
.tag-weak { background: #fee2e2; color: #b91c1c; }
.tag-known { background: #d1fae5; color: #065f46; }

.path-chain { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.path-node {
  display: flex; align-items: center; gap: 8px; padding: 8px 12px;
  background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
  min-width: 140px;
}
.path-node.is-weak { border-color: #fca5a5; background: #fef2f2; }
.path-node.is-known { border-color: #86efac; background: #f0fdf4; }
.node-step {
  width: 24px; height: 24px; border-radius: 50%; background: #3b82f6; color: #fff;
  display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 600; flex-shrink: 0;
}
.is-weak .node-step { background: #dc2626; }
.is-known .node-step { background: #16a34a; }
.node-info { min-width: 0; }
.node-name { font-size: 13px; font-weight: 500; color: #1e293b; }
.node-meta { display: flex; gap: 4px; margin-top: 2px; }
.path-arrow { font-size: 16px; color: #94a3b8; font-weight: 600; flex-shrink: 0; }

.empty-card { padding: 40px; text-align: center; color: var(--text-light); }

/* 资源展示 */
.node-resources {
  width: 100%; padding: 10px 14px; margin: 4px 0 8px;
  background: #f8fafc; border: 1px dashed #e2e8f0; border-radius: 8px;
}
.res-title { font-size: 11px; color: #64748b; margin-bottom: 6px; font-weight: 500; }
.res-item {
  display: flex; align-items: center; gap: 8px; padding: 4px 0;
  font-size: 12px; border-bottom: 1px solid #f1f5f9;
}
.res-item:last-child { border-bottom: none; }
.res-icon { font-size: 14px; }
.res-name { flex: 1; color: #1e293b; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.res-type-tag { padding: 1px 6px; border-radius: 3px; font-size: 10px; }
.r-doc { background: #dbeafe; color: #1e40af; }
.r-video { background: #fce7f3; color: #9d174d; }
.r-link { background: #d1fae5; color: #065f46; }
.r-exercise { background: #fef3c7; color: #92400e; }
.r-project { background: #ede9fe; color: #5b21b6; }
.res-diff { color: #f59e0b; font-size: 11px; }
.res-link { color: #3b82f6; font-size: 11px; text-decoration: underline; flex-shrink: 0; }
.tag-res { background: #e0e7ff; color: #4338ca; cursor: pointer; }
.path-node { cursor: pointer; }

.card { background: #fff; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); padding: 20px; margin-bottom: 16px; }
.card h3 { font-size: 15px; margin: 0 0 12px; }

/* 领域偏好推送 */
.track-bars { margin-bottom: 12px; }
.track-bar-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.track-name { width: 90px; font-size: 13px; font-weight: 500; text-align: right; flex-shrink: 0; }
.track-bar { flex: 1; height: 8px; background: #eee; border-radius: 4px; overflow: hidden; }
.track-bar-fill { height: 100%; background: linear-gradient(90deg, #667eea, #764ba2); border-radius: 4px; transition: width 0.6s; }
.track-score { width: 36px; font-size: 12px; color: #666; text-align: right; }

.track-section { background: #f8f9ff; border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; }
.track-section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.track-section-title { font-weight: 600; font-size: 14px; color: #333; }
.track-section-score { font-size: 12px; color: #764ba2; }
.sub-areas { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.sub-area-tag { background: #eef0ff; color: #555; font-size: 12px; padding: 2px 8px; border-radius: 10px; }
.entry-points { margin-top: 4px; }
.entry-hint { font-size: 12px; color: #999; }
.entry-item { display: flex; align-items: center; gap: 8px; margin-top: 4px; font-size: 13px; }
.entry-item a { color: #667eea; text-decoration: none; }
.entry-item a:hover { text-decoration: underline; }

.track-res-section { margin-bottom: 12px; }
.track-res-header { font-size: 13px; font-weight: 600; color: #555; margin-bottom: 6px; padding-left: 2px; }
.res-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
.res-row .res-name { flex: 1; }
.res-row .res-link { color: #667eea; font-size: 12px; text-decoration: none; }
.res-row .res-link:hover { text-decoration: underline; }

/* 学习数据看板 */
.dash-card { margin-bottom: 16px; }
.dash-stats { display: flex; gap: 12px; margin-bottom: 16px; }
.dash-stat {
  flex: 1; text-align: center; padding: 10px 8px;
  background: #f8fafc; border-radius: 8px;
}
.dash-num { font-size: 20px; font-weight: 700; color: #1e293b; line-height: 1.2; }
.dash-sub { font-size: 12px; color: #94a3b8; font-weight: 500; }
.dash-label { font-size: 11px; color: #94a3b8; margin-top: 2px; }
.dash-heat-wrap { overflow-x: auto; }
.dash-heat {
  display: grid;
  grid-auto-flow: column;
  grid-template-columns: repeat(53, 10px);
  grid-auto-rows: 10px;
  gap: 2px;
  width: max-content;
}
.hm-cell { width: 10px; height: 10px; border-radius: 2px; background: #ebedf0; }
.hm-0 { background: #ebedf0; }
.hm-1 { background: #c6e48b; }
.hm-2 { background: #7bc96f; }
.hm-3 { background: #239a3b; }
.hm-4 { background: #196127; }
.dash-legend { display: flex; align-items: center; gap: 4px; margin-top: 8px; justify-content: flex-end; }
.lg-label { font-size: 11px; color: #94a3b8; }
.lg-cell { width: 10px; height: 10px; border-radius: 2px; }

/* 自定义学习计划 */
.plan-section { margin-top: 16px; }
.plan-list { display: flex; flex-direction: column; gap: 12px; }
.plan-card {
  border: 1px solid #e0e7ff; border-radius: 10px; padding: 16px;
  display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;
  transition: border-color 0.2s;
}
.plan-card:hover { border-color: #93c5fd; }
.plan-card.plan-done { opacity: 0.7; border-color: #d1fae5; background: #f0fdf4; }
.plan-main { flex: 1; min-width: 0; }
.plan-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.plan-title { font-size: 15px; font-weight: 600; color: #1e293b; }
.plan-status { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 500; }
.ps-active { background: #dbeafe; color: #2563eb; }
.ps-done { background: #d1fae5; color: #065f46; }
.ps-paused { background: #fef3c7; color: #92400e; }
.plan-desc { font-size: 12px; color: #64748b; margin-bottom: 6px; }
.plan-meta { font-size: 11px; color: #94a3b8; display: flex; gap: 16px; margin-bottom: 8px; }
.plan-progress-bar { height: 6px; background: #f1f5f9; border-radius: 3px; overflow: hidden; margin-bottom: 4px; }
.plan-bar-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #10b981); border-radius: 3px; transition: width 0.4s; }
.plan-done .plan-bar-fill { background: linear-gradient(90deg, #10b981, #34d399); }
.plan-progress-text { font-size: 11px; color: #94a3b8; }
.plan-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.plan-slider { width: 80px; height: 4px; cursor: pointer; accent-color: #3b82f6; }
.btn-danger-text { color: #ef4444; }
.btn-danger-text:hover { text-decoration: underline; }
.btn-checkin {
  background: #10b981; color: #fff; border: none; padding: 4px 12px;
  border-radius: 4px; font-size: 12px; cursor: pointer;
}
.btn-checkin:hover { background: #059669; }

/* 计划统计行 */
.plan-stats-row {
  display: flex; gap: 16px; margin-bottom: 8px; cursor: pointer;
  padding: 4px 0; border-radius: 4px; transition: background 0.15s;
}
.plan-stats-row:hover { background: #f1f5f9; }
.plan-stat { font-size: 12px; color: #64748b; }

/* 题单 */
.plan-qlink { color: #3b82f6; cursor: pointer; text-decoration: underline; }

/* 题型标签（题单明细 / 题目选择器共用） */
.type-tag { font-size: 11px; padding: 1px 7px; border-radius: 3px; font-weight: 500; flex-shrink: 0; }
.type-choice { background: #dbeafe; color: #1e40af; }
.type-judge { background: #d1fae5; color: #065f46; }
.type-fill { background: #fef3c7; color: #92400e; }
.type-subjective { background: #ede9fe; color: #5b21b6; }
.type-code { background: #fee2e2; color: #991b1b; }
.plan-questions {
  margin-top: 10px; padding: 10px 12px; background: #f8fafc;
  border: 1px solid #e2e8f0; border-radius: 8px;
}
.plan-q-list { display: flex; flex-direction: column; gap: 4px; }
.plan-q-item {
  display: flex; align-items: center; gap: 8px; padding: 6px 8px;
  border-radius: 6px; text-decoration: none; background: #fff;
  border: 1px solid #f1f5f9; font-size: 12px;
}
.plan-q-item:hover { border-color: #93c5fd; }
.plan-q-title { flex: 1; color: #1e293b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.plan-q-status { font-size: 11px; padding: 1px 8px; border-radius: 10px; flex-shrink: 0; }
.pq-done .plan-q-status { background: #d1fae5; color: #065f46; }
.pq-wrong .plan-q-status { background: #fee2e2; color: #991b1b; }
.pq-undone .plan-q-status { background: #f1f5f9; color: #64748b; }

/* 题单选择器 */
.plan-q-picker { border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; }
.plan-q-search { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.plan-q-search .form-input { flex: 1; }
.plan-q-count { font-size: 12px; color: #64748b; white-space: nowrap; }
.plan-q-options { max-height: 180px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
.plan-q-opt {
  display: flex; align-items: center; gap: 8px; padding: 5px 8px;
  border: 1px solid #f1f5f9; border-radius: 6px; cursor: pointer; font-size: 12px;
}
.plan-q-opt:hover { background: #f8fafc; }
.plan-q-opt.q-opt-on { border-color: #93c5fd; background: #eff6ff; }
.plan-q-opt input { margin: 0; }
.plan-q-opt-title { flex: 1; color: #1e293b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.q-opt-tick { color: #3b82f6; font-weight: 700; }

/* 日历 */
.plan-calendar {
  margin-top: 12px; padding: 12px; background: #f8fafc;
  border: 1px solid #e0e7ff; border-radius: 8px;
}
.cal-header {
  display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
}
.cal-nav {
  background: none; border: 1px solid #cbd5e1; border-radius: 4px;
  font-size: 12px; padding: 2px 8px; cursor: pointer; color: #475569;
}
.cal-nav:hover { background: #f1f5f9; }
.cal-month-label { font-size: 13px; font-weight: 600; color: #1e293b; min-width: 80px; text-align: center; }
.cal-streak { font-size: 12px; color: #f59e0b; font-weight: 500; margin-left: auto; }
.cal-close { background: none; border: none; font-size: 16px; color: #94a3b8; cursor: pointer; }
.cal-weekdays { display: grid; grid-template-columns: repeat(7, 1fr); text-align: center; font-size: 11px; color: #94a3b8; margin-bottom: 4px; }
.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
.cal-day {
  aspect-ratio: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; font-size: 12px; border-radius: 4px; color: #475569;
  position: relative; cursor: default;
}
.cal-day.cal-today { background: #eff6ff; font-weight: 700; color: #3b82f6; }
.cal-day.cal-checked { background: #dcfce7; }
.cal-day.cal-other { color: #cbd5e1; }
.cal-day-num { line-height: 1; }
.cal-dot { width: 4px; height: 4px; border-radius: 50%; background: #10b981; margin-top: 2px; }
.cal-loading { text-align: center; font-size: 11px; color: #94a3b8; padding: 4px; }

/* 计划弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 200; }
.plan-modal { background: #fff; border-radius: 12px; width: 440px; max-height: 80vh; box-shadow: 0 8px 30px rgba(0,0,0,0.15); display: flex; flex-direction: column; }
.plan-modal-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #e2e8f0; }
.plan-modal-header h3 { margin: 0; font-size: 16px; color: #1e293b; }
.modal-close-btn { background: none; border: none; font-size: 22px; cursor: pointer; color: #94a3b8; }
.plan-modal-body { padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
.plan-modal-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 16px 20px; border-top: 1px solid #e2e8f0; }
.form-label { font-size: 13px; font-weight: 500; color: #475569; }
.form-label .required { color: #ef4444; }
.form-input { width: 100%; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px; color: #1e293b; outline: none; box-sizing: border-box; }
.form-input:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.1); }
.form-textarea { resize: vertical; font-family: inherit; min-height: 60px; }
.btn-ghost { background: #fff; border: 1px solid #cbd5e1; color: #475569; padding: 6px 16px; border-radius: 6px; font-size: 13px; cursor: pointer; }
.btn-ghost:hover { background: #f1f5f9; }
</style>
