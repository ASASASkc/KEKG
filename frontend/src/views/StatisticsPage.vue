<template>
  <div class="page-container">
    <div class="page-top">
      <div>
        <h1>统计分析</h1>
        <p class="page-subtitle">考试成绩统计与分析</p>
      </div>
    </div>

    <div class="date-filter">
      <label class="date-label">时间范围：</label>
      <input type="date" v-model="startDate" class="input input-sm" @change="onDateChange" />
      <span class="date-sep">至</span>
      <input type="date" v-model="endDate" class="input input-sm" @change="onDateChange" />
      <button class="btn btn-sm btn-outline" @click="clearDate">清除日期</button>
    </div>

    <div class="tab-bar">
      <button v-if="!authStore.isAdmin" class="tab-btn" :class="{ active: activeTab === 'student' }" @click="activeTab = 'student'">个人统计</button>
      <button v-if="authStore.isAdmin" class="tab-btn" :class="{ active: activeTab === 'class' }" @click="activeTab = 'class'">班级统计</button>
    </div>

    <!-- 个人统计 -->
    <template v-if="activeTab === 'student'">
      <UiLoading v-if="loadingStudent" />
      <UiEmpty v-else-if="loadError"><template>{{ loadError }}</template></UiEmpty>

      <template v-else-if="studentData">
        <div class="stats-grid" v-if="studentData.total_exams > 0">
          <div class="card stat-box">
            <div class="stat-number">{{ studentData.total_exams || 0 }}</div>
            <div class="stat-label">参加考试</div>
          </div>
          <div class="card stat-box">
            <div class="stat-number green">{{ studentData.passed_exams || 0 }}</div>
            <div class="stat-label">通过考试</div>
          </div>
          <div class="card stat-box">
            <div class="stat-number" style="color:#8b5cf6">{{ passRate }}%</div>
            <div class="stat-label">通过率</div>
          </div>
          <div class="card stat-box">
            <div class="stat-number blue">{{ studentData.avg_score ?? '-' }}</div>
            <div class="stat-label">平均分</div>
          </div>
          <div class="card stat-box">
            <div class="stat-number red">{{ studentData.highest_score ?? '-' }}</div>
            <div class="stat-label">最高分</div>
          </div>
        </div>

        <UiEmpty v-if="studentData.total_exams === 0" text="暂无考试记录，参加考试后即可查看统计" />

        <!-- 分数分布图 -->
        <div class="card chart-card" v-if="studentData.distribution">
          <h3>分数分布</h3>
          <div class="chart-row-2">
            <div ref="studentChartRef" class="chart chart-half" style="min-height:280px;width:100%"></div>
            <div ref="studentPieRef" class="chart chart-half" style="min-height:280px;width:100%"></div>
          </div>
        </div>

        <div class="card chart-card" v-if="studentData.recent_exams?.length > 1">
          <h3>考试趋势</h3>
          <div ref="studentTrendRef" class="chart" style="min-height:300px;width:100%"></div>
        </div>

        <!-- 知识点掌握雷达图 -->
        <div class="card chart-card" v-if="studentRadar && studentRadar.radar?.length">
          <h3>知识点掌握度</h3>
          <div class="chart-row-2">
            <div ref="studentRadarRef" class="chart" style="min-height:320px;width:100%"></div>
            <div class="radar-list">
              <div v-for="item in studentRadar.radar" :key="item.category" class="radar-row">
                <span class="radar-cat">{{ item.category }}</span>
                <div class="radar-bar-bg">
                  <div class="radar-bar-fill" :style="{width: item.accuracy + '%', background: accuracyColor(item.accuracy)}"></div>
                </div>
                <span class="radar-val">{{ item.accuracy }}%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 最近考试列表 -->
        <div class="card" v-if="studentData.recent_exams?.length">
          <h3>最近考试</h3>
          <table class="data-table">
            <thead><tr><th>考试</th><th>得分</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="e in studentData.recent_exams" :key="e.exam_id">
                <td>{{ e.exam_title }}</td>
                <td>{{ e.total_score ?? '-' }}</td>
                <td><button class="btn btn-xs btn-outline" @click="loadExamDetail(e.exam_id)">分析</button></td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 单次考试分析 -->
        <template v-if="examDetail">
          <div class="card chart-card" v-if="examDetail.by_type">
            <h3>按题型得分率</h3>
            <div ref="typeChartRef" class="chart"></div>
          </div>
          <div class="card chart-card" v-if="examDetail.by_difficulty">
            <h3>按难度得分率</h3>
            <div ref="diffChartRef" class="chart"></div>
          </div>
        </template>
      </template>
      <UiEmpty v-else text="暂无考试记录" />
    </template>

    <!-- 班级统计 (管理员) -->
    <template v-if="activeTab === 'class' && authStore.isAdmin">
      <div class="filter-row">
        <select v-model="selectedClassId" class="input input-sm" @change="loadClassSummary">
          <option :value="0">选择班级</option>
          <option v-for="c in classList" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
      </div>

      <UiLoading v-if="loadingClass" />

      <template v-else-if="classSummary && selectedClassId">
        <div class="stats-grid">
          <div class="card stat-box">
            <div class="stat-number">{{ classSummary.total_students || 0 }}</div>
            <div class="stat-label">班级人数</div>
          </div>
          <div class="card stat-box">
            <div class="stat-number green">{{ classSummary.pass_rate ?? '-' }}%</div>
            <div class="stat-label">通过率</div>
          </div>
          <div class="card stat-box">
            <div class="stat-number blue">{{ classSummary.avg_score ?? '-' }}</div>
            <div class="stat-label">平均分</div>
          </div>
          <div class="card stat-box">
            <div class="stat-number red">{{ classSummary.exam_count || 0 }}</div>
            <div class="stat-label">考试次数</div>
          </div>
          <div class="card stat-box">
            <div class="stat-number" style="color:#f59e0b">{{ classSummary.median_score ?? '-' }}</div>
            <div class="stat-label">中位数</div>
          </div>
        </div>

        <div class="card chart-card" v-if="classSummary.distribution">
          <h3>分数分布</h3>
          <div class="chart-row-2">
            <div ref="classChartRef" class="chart chart-half" style="min-height:280px;width:100%"></div>
            <div ref="classPieRef" class="chart chart-half" style="min-height:280px;width:100%"></div>
          </div>
        </div>

        <!-- 各考试统计：增加按题目正确率 -->
        <div class="card" v-if="classSummary.by_exam?.length">
          <h3>各考试统计</h3>
          <div v-if="classSummary.by_exam.length > 1" ref="classTrendRef" class="chart" style="height:200px;width:100%;margin-bottom:16px"></div>
          <table class="data-table">
            <thead>
              <tr><th>考试标题</th><th>平均分</th><th>提交人数</th><th>操作</th></tr>
            </thead>
            <tbody>
              <tr v-for="e in classSummary.by_exam" :key="e.exam_id">
                <td>{{ e.title }}</td>
                <td>{{ e.avg_score ?? '-' }}</td>
                <td>{{ e.submitted_count ?? 0 }}</td>
                <td><button class="btn btn-xs btn-outline" @click="loadClassExamDetail(e.exam_id)" :disabled="loadingExamDetail">题目正确率</button></td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 单次考试各题正确率 -->
        <div class="card" v-if="classExamDetail">
          <h3>各题正确率 — {{ classExamDetail.student_count }} 人参与</h3>
          <div v-if="classExamDetail.question_stats?.length">
            <table class="data-table">
              <thead><tr><th>#</th><th>题目</th><th>题型</th><th>正确率</th></tr></thead>
              <tbody>
                <tr v-for="(q, idx) in classExamDetail.question_stats" :key="q.question_id">
                  <td>{{ idx + 1 }}</td>
                  <td>{{ q.title || '(题目ID:' + q.question_id + ')' }}</td>
                  <td><span class="q-type-tag">{{ typeLabelShort(q.type) }}</span></td>
                  <td :style="{color: (q.correct_rate || 0) >= 0.6 ? '#16a34a' : '#dc2626'}">
                    {{ Math.round((q.correct_rate || 0) * 100) }}%
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <UiEmpty v-else text="暂无答题数据" />
          <!-- 学生成绩列表 -->
          <h3 style="margin-top:20px">学生成绩</h3>
          <table class="data-table" v-if="classExamDetail.students?.length">
            <thead><tr><th>学生</th><th>得分</th><th>提交时间</th></tr></thead>
            <tbody>
              <tr v-for="s in classExamDetail.students" :key="s.student_id">
                <td>{{ s.username || 'ID:' + s.student_id }}</td>
                <td>{{ s.total_score ?? '-' }}</td>
                <td>{{ formatDate(s.submit_time) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 班级薄弱知识点 -->
        <div class="card" v-if="classWeakPoints && classWeakPoints.weak_points?.length">
          <h3>薄弱知识点排行</h3>
          <table class="data-table">
            <thead><tr><th>#</th><th>知识点</th><th>分类</th><th>正确率</th></tr></thead>
            <tbody>
              <tr v-for="(wp, idx) in classWeakPoints.weak_points.slice(0, 15)" :key="wp.knowledge_point_id">
                <td>{{ idx + 1 }}</td>
                <td>{{ wp.knowledge_point_name }}</td>
                <td><span class="tag" :style="{background: catBg(wp.category)}">{{ wp.category }}</span></td>
                <td :style="{color: wp.accuracy >= 60 ? '#16a34a' : '#dc2626', fontWeight: '600'}">
                  {{ wp.accuracy }}%
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
      <UiEmpty v-else-if="!selectedClassId" text="请选择一个班级查看统计" />
    </template>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted, computed } from 'vue'
import * as echarts from 'echarts'
import api from '../api'
import { authStore } from '../stores/auth'
import { useFeedback } from '../composables/useFeedback'

const { tip } = useFeedback()

const activeTab = ref(authStore.isAdmin ? 'class' : 'student')
const startDate = ref('')
const endDate = ref('')
const studentData = ref(null)
const loadingStudent = ref(false)
const classList = ref([])
const selectedClassId = ref(0)
const classSummary = ref(null)
const classExamDetail = ref(null)
const loadingClass = ref(false)
const studentChartRef = ref(null)
const studentPieRef = ref(null)
const studentTrendRef = ref(null)
const classChartRef = ref(null)
const classPieRef = ref(null)
const classTrendRef = ref(null)
const typeChartRef = ref(null)
const diffChartRef = ref(null)
const studentRadarRef = ref(null)
const examDetail = ref(null)
const loadError = ref('')
let studentChart = null
let studentPieChart = null
let studentTrendChart = null
let classChart = null
let classPieChart = null
let classTrendChart = null
let typeChart = null
let diffChart = null
let studentRadarChart = null

const loadingExamDetail = ref(false)

const studentRadar = ref(null)
const classWeakPoints = ref(null)

const passRate = computed(() => {
  if (!studentData.value || !studentData.value.total_exams) return 0
  return Math.round(studentData.value.passed_exams / studentData.value.total_exams * 100)
})

function disposeAllCharts() {
  if (studentChart) { studentChart.dispose(); studentChart = null }
  if (studentPieChart) { studentPieChart.dispose(); studentPieChart = null }
  if (studentTrendChart) { studentTrendChart.dispose(); studentTrendChart = null }
  if (classChart) { classChart.dispose(); classChart = null }
  if (classPieChart) { classPieChart.dispose(); classPieChart = null }
  if (classTrendChart) { classTrendChart.dispose(); classTrendChart = null }
  if (typeChart) { typeChart.dispose(); typeChart = null }
  if (diffChart) { diffChart.dispose(); diffChart = null }
  if (studentRadarChart) { studentRadarChart.dispose(); studentRadarChart = null }
}

onMounted(() => {
  loadStudentOverview()
  if (authStore.isAdmin) fetchClassList()
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  disposeAllCharts()
  window.removeEventListener('resize', onResize)
})

function onResize() {
  if (studentChart) studentChart.resize()
  if (studentPieChart) studentPieChart.resize()
  if (studentTrendChart) studentTrendChart.resize()
  if (classChart) classChart.resize()
  if (classPieChart) classPieChart.resize()
  if (classTrendChart) classTrendChart.resize()
  if (typeChart) typeChart.resize()
  if (diffChart) diffChart.resize()
  if (studentRadarChart) studentRadarChart.resize()
}

watch(activeTab, (tab) => {
  if (tab === 'student') loadStudentOverview()
  if (tab === 'class') {
    if (classList.value.length > 0 && !selectedClassId.value) {
      selectedClassId.value = classList.value[0].id
    }
    if (selectedClassId.value) loadClassSummary()
  }
})

// 数据变化时自动渲染图表
watch(studentData, async (data) => {
  if (!data) return
  await nextTick()
  console.log('[Stats] watch studentData triggered, rendering charts')
  renderStudentChart()
  renderStudentPieChart()
  renderStudentTrendChart()
}, { flush: 'post' })

watch(classSummary, async (data) => {
  if (!data) return
  await nextTick()
  console.log('[Stats] watch classSummary triggered, rendering charts')
  renderClassChart()
  renderClassPieChart()
  renderClassTrendChart()
}, { flush: 'post' })

watch(examDetail, async (data) => {
  if (!data) return
  await nextTick()
  console.log('[Stats] watch examDetail triggered')
  if (data.by_type) renderTypeChart(data.by_type)
  if (data.by_difficulty) renderDiffChart(data.by_difficulty)
}, { flush: 'post' })

watch(studentRadar, async (data) => {
  if (!data) return
  await nextTick()
  renderStudentRadarChart()
}, { flush: 'post' })

function onDateChange() {
  if (activeTab.value === 'student') loadStudentOverview()
  else if (activeTab.value === 'class' && selectedClassId.value) loadClassSummary()
}
function clearDate() {
  startDate.value = ''
  endDate.value = ''
  onDateChange()
}

async function loadStudentOverview() {
  loadingStudent.value = true
  loadError.value = ''
  try {
    const params = {}
    if (startDate.value) params.start_date = startDate.value
    if (endDate.value) params.end_date = endDate.value
    const r = await api.get('/statistics/student/overview', { params })
    console.log('[Stats] student overview response:', r)
    if (r.success) {
      studentData.value = r.data
      console.log('[Stats] studentData set:', JSON.stringify(r.data).substring(0, 200))
      loadStudentRadar()
    } else {
      loadError.value = 'API返回失败: ' + (r.message || JSON.stringify(r))
    }
  } catch (e) {
    console.error('加载学生概况失败:', e)
    loadError.value = '请求失败: ' + (e.message || JSON.stringify(e))
  }
  finally { loadingStudent.value = false }
}

async function fetchClassList() {
  try {
    const r = await api.get('/classes')
    if (r.success) classList.value = r.data?.items || r.data
  } catch (e) { console.error('加载班级列表失败:', e); tip('班级列表加载失败，请稍后重试') }
}

async function loadClassSummary() {
  if (!selectedClassId.value) return
  loadingClass.value = true
  try {
    const params = {}
    if (startDate.value) params.start_date = startDate.value
    if (endDate.value) params.end_date = endDate.value
    const r = await api.get(`/statistics/class/${selectedClassId.value}/summary`, { params })
    console.log('[Stats] class summary response:', r)
    if (r.success) {
      classSummary.value = r.data
      console.log('[Stats] classSummary set:', 'students=', r.data.total_students, 'exams=', r.data.exam_count)
    }
  } catch (e) { console.error('加载班级概况失败:', e); tip('班级概况加载失败，请稍后重试') }
  finally { loadingClass.value = false }
}

function initChart(dom, options) {
  return new Promise(resolve => {
    let retries = 0
    const tryInit = () => {
      if (!dom || !dom.isConnected) {
        if (retries++ < 100) setTimeout(tryInit, 50)
        else resolve(null)
        return
      }
      try {
        const chart = echarts.init(dom)
        chart.setOption(options)
        resolve(chart)
      } catch (e) {
        console.error('[Stats] echarts init error:', e)
        resolve(null)
      }
    }
    requestAnimationFrame(() => {
      // 额外延迟确保布局完成
      setTimeout(tryInit, 30)
    })
  })
}

async function renderStudentChart() {
  console.log('[Stats] renderStudentChart called, ref:', !!studentChartRef.value, 'dist:', studentData.value?.distribution)
  if (!studentChartRef.value || !studentData.value?.distribution) return
  if (studentChart) studentChart.dispose()
  const dist = studentData.value.distribution
  studentChart = await initChart(studentChartRef.value, {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: Object.keys(dist) },
    yAxis: { type: 'value', name: '人数' },
    series: [{
      type: 'bar', data: Object.values(dist),
      itemStyle: { color: '#3b82f6' }, barWidth: '50%',
      label: { show: true, position: 'top', formatter: '{c}' }
    }]
  })
}

async function renderClassChart() {
  if (!classChartRef.value || !classSummary.value?.distribution) return
  if (classChart) classChart.dispose()
  const dist = classSummary.value.distribution
  classChart = await initChart(classChartRef.value, {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: Object.keys(dist) },
    yAxis: { type: 'value', name: '人数' },
    series: [{
      type: 'bar', data: Object.values(dist),
      itemStyle: { color: '#8b5cf6' }, barWidth: '50%',
      label: { show: true, position: 'top', formatter: '{c}' }
    }]
  })
}

async function renderStudentPieChart() {
  if (!studentPieRef.value || !studentData.value?.distribution) return
  if (studentPieChart) studentPieChart.dispose()
  const dist = studentData.value.distribution
  const pieData = Object.entries(dist).map(([k, v]) => ({ name: k + '分', value: v }))
  studentPieChart = await initChart(studentPieRef.value, {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie', radius: ['40%', '70%'],
      itemStyle: { borderRadius: 6 },
      data: pieData,
      label: { formatter: '{b}\n{d}%' }
    }]
  })
}

async function renderStudentTrendChart() {
  if (!studentTrendRef.value || !studentData.value?.recent_exams?.length) return
  if (studentTrendChart) studentTrendChart.dispose()
  const exams = [...studentData.value.recent_exams].reverse()
  const labels = exams.map(e => e.exam_title || '考试' + e.exam_id)
  const scores = exams.map(e => e.total_score ?? 0)
  studentTrendChart = await initChart(studentTrendRef.value, {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', name: '分数' },
    series: [{
      type: 'line', data: scores,
      smooth: true, lineStyle: { color: '#3b82f6', width: 2 },
      itemStyle: { color: '#3b82f6' },
      areaStyle: { color: 'rgba(59,130,246,0.1)' }
    }]
  })
}

async function renderClassPieChart() {
  if (!classPieRef.value || !classSummary.value?.distribution) return
  if (classPieChart) classPieChart.dispose()
  const dist = classSummary.value.distribution
  const pieData = Object.entries(dist).map(([k, v]) => ({ name: k + '分', value: v }))
  classPieChart = await initChart(classPieRef.value, {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie', radius: ['40%', '70%'],
      itemStyle: { borderRadius: 6 },
      data: pieData,
      label: { formatter: '{b}\n{d}%' }
    }]
  })
}

async function renderClassTrendChart() {
  if (!classTrendRef.value || !classSummary.value?.by_exam?.length) return
  if (classTrendChart) classTrendChart.dispose()
  const exams = [...classSummary.value.by_exam].reverse()
  const labels = exams.map(e => e.title)
  const scores = exams.map(e => e.avg_score ? Math.round(e.avg_score * 10) / 10 : 0)
  classTrendChart = await initChart(classTrendRef.value, {
    tooltip: { trigger: 'axis', formatter: '{b}: {c}分' },
    xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', name: '平均分' },
    series: [{
      type: 'line', data: scores,
      smooth: true, lineStyle: { color: '#8b5cf6', width: 2 },
      itemStyle: { color: '#8b5cf6' },
      areaStyle: { color: 'rgba(139,92,246,0.1)' }
    }]
  })
}

async function loadExamDetail(eid) {
  examDetail.value = null
  try {
    const r = await api.get(`/statistics/student/exam/${eid}`)
    if (r.success) {
      examDetail.value = r.data
    }
  } catch (e) { console.error('加载考试分析失败:', e); tip('考试分析加载失败，请稍后重试') }
}

async function renderTypeChart(byType) {
  if (!typeChartRef.value) return
  if (typeChart) typeChart.dispose()
  const labels = Object.keys(byType)
  const rates = labels.map(k => Math.round(byType[k].rate * 100))
  typeChart = await initChart(typeChartRef.value, {
    tooltip: { trigger: 'axis', formatter: '{b}: {c}%' },
    xAxis: { type: 'category', data: labels.map(k => TYPE_NAMES[k]) },
    yAxis: { type: 'value', name: '得分率(%)', max: 100 },
    series: [{
      type: 'bar', data: rates,
      itemStyle: { color: '#10b981' }, barWidth: '40%'
    }]
  })
}

async function renderDiffChart(byDiff) {
  if (!diffChartRef.value) return
  if (diffChart) diffChart.dispose()
  const labels = Object.keys(byDiff)
  const rates = labels.map(k => Math.round(byDiff[k].rate * 100))
  diffChart = await initChart(diffChartRef.value, {
    tooltip: { trigger: 'axis', formatter: '{b}: {c}%' },
    xAxis: { type: 'category', data: labels.map(k => DIFF_NAMES[k]) },
    yAxis: { type: 'value', name: '得分率(%)', max: 100 },
    series: [{
      type: 'bar', data: rates,
      itemStyle: { color: '#f59e0b' }, barWidth: '40%'
    }]
  })
}

const TYPE_NAMES = { choice: '选择', judge: '判断', fill: '填空', subjective: '主观' }
const DIFF_NAMES = { low: '低', medium: '中', high: '高' }
function typeLabelShort(t) { return TYPE_NAMES[t] || t }
function formatDate(d) {
  if (!d) return '-'
  return new Date(d).toLocaleString('zh-CN', { hour12: false })
}

async function loadClassExamDetail(eid) {
  if (!selectedClassId.value || loadingExamDetail.value) return
  loadingExamDetail.value = true
  classExamDetail.value = null
  classWeakPoints.value = null
  try {
    const r = await api.get(`/statistics/class/${selectedClassId.value}/exam/${eid}`)
    if (r.success) { classExamDetail.value = r.data; loadClassWeakPoints(eid) }
  } catch (e) { console.error('加载题目正确率失败:', e); tip('题目正确率加载失败，请稍后重试') }
  finally { loadingExamDetail.value = false }
}

async function loadStudentRadar() {
  try {
    const r = await api.get('/statistics/student/radar')
    if (r.success) studentRadar.value = r.data
  } catch (e) { console.error('加载掌握度失败:', e); tip('掌握度加载失败，请稍后重试') }
}

async function loadClassWeakPoints(eid) {
  try {
    const r = await api.get(`/statistics/class/${selectedClassId.value}/weak-points/${eid}`)
    if (r.success) classWeakPoints.value = r.data
  } catch (e) { console.error('加载薄弱点失败:', e); tip('薄弱点加载失败，请稍后重试') }
}

const ACCURACY_COLORS = [
  { threshold: 0, color: '#ef4444' },
  { threshold: 40, color: '#f59e0b' },
  { threshold: 60, color: '#84cc16' },
  { threshold: 80, color: '#10b981' }
]
function accuracyColor(rate) {
  let c = ACCURACY_COLORS[0].color
  for (const t of ACCURACY_COLORS) {
    if (rate >= t.threshold) c = t.color
  }
  return c
}

function catBg(cat) {
  const m = { '基础': '#dbeafe', '核心': '#ede9fe', '进阶': '#d1fae5', '数据结构': '#cffafe', '数据科学': '#fef3c7' }
  return m[cat] || '#f1f5f9'
}

async function renderStudentRadarChart() {
  if (!studentRadarRef.value || !studentRadar.value?.radar?.length) return
  if (studentRadarChart) studentRadarChart.dispose()
  const d = studentRadar.value.radar
  const max = Math.max(...d.map(x => x.accuracy))
  studentRadarChart = await initChart(studentRadarRef.value, {
    tooltip: { trigger: 'item' },
    radar: {
      center: ['50%', '55%'],
      radius: '65%',
      indicator: d.map(x => ({ name: x.category, max: 100 }))
    },
    series: [{
      type: 'radar',
      data: [{ value: d.map(x => x.accuracy), name: '掌握度', areaStyle: { color: 'rgba(59,130,246,0.15)' } }],
      itemStyle: { color: '#3b82f6' },
      lineStyle: { color: '#3b82f6', width: 2 }
    }]
  })
}
</script>

<style scoped>
.page-container { max-width: 1000px; margin: 0 auto; padding: 32px 24px; }
.page-top { margin-bottom: 20px; }
.page-top h1 { font-size: 19px; margin: 0; }
.page-subtitle { font-size: 11px; color: var(--text-secondary); margin: 4px 0 0; }

.tab-bar { display: flex; gap: 4px; margin-bottom: 20px; background: #f1f5f9; padding: 4px; border-radius: 8px; width: fit-content; }
.tab-btn {
  padding: 8px 20px; border: none; background: transparent; border-radius: 6px;
  font-size: 11px; cursor: pointer; color: var(--text-secondary); font-weight: 500;
}
.tab-btn.active { background: #fff; color: #1e293b; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }

.filter-row { margin-bottom: 16px; }

.loading-text { text-align: center; padding: 40px; color: var(--text-secondary); }
.empty-msg { text-align: center; padding: 40px; color: var(--text-light); }

.stats-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 24px; }
@media (max-width: 900px) { .stats-grid { grid-template-columns: repeat(3, 1fr); } }
.stat-box { text-align: center; padding: 24px; }
.stat-number { font-size: 32px; font-weight: 700; color: #1e293b; }
.stat-number.green { color: #10b981; }
.stat-number.blue { color: #3b82f6; }
.stat-number.red { color: #ef4444; }
.stat-label { font-size: 11px; color: var(--text-secondary); margin-top: 4px; }

.chart-card { padding: 20px; margin-bottom: 20px; }
.chart-card h3 { font-size: 13px; margin: 0 0 12px; }
.chart { height: 300px; }

.data-table {
  width: 100%; border-collapse: collapse; background: #fff;
  border-radius: 8px; overflow: hidden;
}
.data-table th, .data-table td {
  padding: 10px 14px; text-align: left; font-size: 11px; border-bottom: 1px solid #f1f5f9;
}
.data-table th { background: #f8fafc; font-weight: 600; color: var(--text-secondary); font-size: 11px; }
.data-table tr:last-child td { border-bottom: none; }

.input { padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 11px; box-sizing: border-box; }
.input-sm { width: auto; min-width: 200px; }

.date-filter { display: flex; gap: 8px; align-items: center; margin-bottom: 16px; }
.date-label { font-size: 11px; color: var(--text-secondary); white-space: nowrap; }
.date-sep { font-size: 11px; color: var(--text-secondary); }
.chart-row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.chart-half { height: 280px; }
@media (max-width: 700px) { .chart-row-2 { grid-template-columns: 1fr; } }

.radar-list { padding: 12px 0; display: flex; flex-direction: column; gap: 8px; }
.radar-row { display: flex; align-items: center; gap: 8px; }
.radar-cat { font-size: 11px; color: var(--text-secondary); width: 60px; flex-shrink: 0; text-align: right; }
.radar-bar-bg { flex: 1; height: 8px; background: #f1f5f9; border-radius: 4px; overflow: hidden; }
.radar-bar-fill { height: 100%; border-radius: 4px; transition: width 0.6s ease; min-width: 2px; }
.radar-val { font-size: 11px; font-weight: 600; color: var(--text-primary); width: 40px; flex-shrink: 0; }

</style>
