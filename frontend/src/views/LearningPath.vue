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
          <p v-else class="form-hint" style="margin-top:8px">暂无学习趋势数据</p>
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
      <div class="card empty-card" v-else>
        <p>暂无薄弱知识点，继续保持！</p>
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
      <div class="card empty-card" v-else>
        <p>暂无领域偏好推送数据</p>
      </div>
    </template>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import api from '../api'
import * as echarts from 'echarts'
import { useFeedback } from '../composables/useFeedback'

const { tip, ask } = useFeedback()

const loading = ref(true)
const error = ref('')
const assessment = ref(null)
const path = ref(null)
const trackRecs = ref(null)
const trendRef = ref(null)
let trendChart = null

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
  window.addEventListener('resize', onResize)
  await loadData()
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  if (trendChart) { trendChart.dispose(); trendChart = null }
})

function onResize() {
  if (trendChart) trendChart.resize()
}

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
  } catch (e) {
    if (retry) {
      await new Promise(r => setTimeout(r, 500))
      return loadData(false)
    }
    error.value = e?.message || e?.data?.message || '网络请求失败'
    console.error('加载学习路径失败:', e)
    tip('学习路径加载失败，请稍后重试')
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

</style>
