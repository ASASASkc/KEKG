<template>
  <div class="page-container">
    <h1 class="page-title">统计分析</h1>
    <p class="page-subtitle">知识图谱数据统计与分布</p>

    <UiLoading v-if="statsLoading" />

    <template v-else-if="stats">
      <div class="stats-grid">
        <div class="card stat-box">
          <div class="stat-value">{{ stats.node_count }}</div>
          <div class="stat-label">总节点数</div>
        </div>
        <div class="card stat-box">
          <div class="stat-value">{{ stats.relationship_count }}</div>
          <div class="stat-label">总关系数</div>
        </div>
      </div>

      <div class="chart-row">
        <div class="card chart-card">
          <h3>标签分布</h3>
          <div ref="labelChartRef" class="chart"></div>
        </div>
        <div class="card chart-card">
          <h3>关系类型分布</h3>
          <div ref="relChartRef" class="chart"></div>
        </div>
      </div>

      <div class="card" v-if="stats.centrality && stats.centrality.length">
        <h3>中心度分析 — 核心知识点 Top 20</h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>排名</th>
              <th>节点名称</th>
              <th>分类</th>
              <th>出度</th>
              <th>入度</th>
              <th>总度数</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(c, idx) in stats.centrality" :key="c.id">
              <td>{{ idx + 1 }}</td>
              <td>{{ c.name }}</td>
              <td>{{ c.category || '-' }}</td>
              <td>{{ c.outdegree }}</td>
              <td>{{ c.indegree }}</td>
              <td><strong>{{ c.total_degree }}</strong></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <div v-else class="empty">暂无统计数据</div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import api from '../api'
import { useFeedback } from '../composables/useFeedback'

const { tip } = useFeedback()

const stats = ref(null)
const statsLoading = ref(true)
const labelChartRef = ref(null)
const relChartRef = ref(null)
let labelChart, relChart

onMounted(async () => {
  window.addEventListener('resize', onResize)
  statsLoading.value = true
  try {
    const r = await api.get('/graph/statistics')
    if (r.success) stats.value = r.data
  } catch (e) {
    console.error('加载统计信息失败:', e)
    tip('统计数据加载失败，请稍后重试')
  } finally {
    statsLoading.value = false
  }
  await nextTick()
  renderCharts()
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  if (labelChart) { labelChart.dispose(); labelChart = null }
  if (relChart) { relChart.dispose(); relChart = null }
})

function onResize() {
  if (labelChart) labelChart.resize()
  if (relChart) relChart.resize()
}

function renderCharts() {
  const s = stats.value
  if (!s) return

  if (labelChartRef.value) {
    labelChart = echarts.init(labelChartRef.value)
    const labels = s.labels_distribution || {}
    labelChart.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie', radius: ['40%', '70%'],
        itemStyle: { borderRadius: 6 },
        data: Object.entries(labels).map(([k, v]) => ({ name: k, value: v }))
      }]
    })
  }

  if (relChartRef.value) {
    relChart = echarts.init(relChartRef.value)
    const types = s.relationship_types || {}
    relChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: Object.keys(types), axisLabel: { fontSize: 11 } },
      yAxis: { type: 'value' },
      series: [{
        type: 'bar', data: Object.values(types).map((v, i) => ({
          value: v,
          itemStyle: { color: ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#06b6d4', '#ef4444'][i % 6] }
        })),
        barWidth: '50%'
      }]
    })
  }
}
</script>

<style scoped>
.empty { text-align: center; padding: 60px 20px; color: var(--text-light); }
.stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 24px; }
.stat-box { text-align: center; padding: 32px; }
.stat-value { font-size: 42px; font-weight: 700; color: var(--accent-blue); }
.stat-label { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }
.chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.chart-card h3 { font-size: 14px; font-weight: 600; margin-bottom: 16px; }
.chart { height: 320px; }
.data-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 12px;
}
.data-table th, .data-table td {
  padding: 8px 12px;
  text-align: left;
  font-size: 11px;
  border-bottom: 1px solid #f1f5f9;
}
.data-table th {
  background: #f8fafc;
  font-weight: 600;
  color: var(--text-secondary);
  font-size: 11px;
}
.data-table tr:hover td {
  background: #f8fafc;
}

@media (max-width: 768px) {
  .chart-row, .stats-grid { grid-template-columns: 1fr; }
}
</style>
