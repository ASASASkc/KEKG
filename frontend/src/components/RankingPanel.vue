<template>
  <div class="ranking-panel">
    <div class="rp-header">
      <h3>班级排行榜</h3>
      <span v-if="items.length" class="rp-count">{{ items.length }} 人已提交</span>
    </div>
    <div v-if="loading" class="rp-loading">加载中...</div>
    <div v-else-if="items.length === 0" class="rp-empty">暂无提交数据</div>
    <table v-else class="rp-table">
      <thead>
        <tr>
          <th class="col-rank">名次</th>
          <th>学生</th>
          <th class="col-score">得分</th>
          <th class="col-time">用时</th>
          <th class="col-status">状态</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in items" :key="row.student_id" :class="'rank-' + row.rank">
          <td class="col-rank">
            <span class="rank-badge" :class="['rb-' + row.rank]">{{ row.rank }}</span>
          </td>
          <td class="rp-username">{{ row.username }}</td>
          <td class="col-score rp-score">{{ row.total_score ?? '-' }}</td>
          <td class="col-time">{{ formatDuration(row.duration_sec) }}</td>
          <td class="col-status">
            <span class="rp-status" :class="row.status === 'reviewed' ? 'st-reviewed' : 'st-submitted'">
              {{ row.status === 'reviewed' ? '已批阅' : '已提交' }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const props = defineProps({
  eid: { type: [Number, String], required: true },
})

const items = ref([])
const loading = ref(true)

function formatDuration(sec) {
  if (sec === null || sec === undefined) return '-'
  sec = Number(sec)
  if (sec <= 0) return '0s'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h > 0) return `${h}h${m}m`
  if (m > 0) return `${m}m${s}s`
  return `${s}s`
}

onMounted(async () => {
  try {
    const res = await api.get(`/exams/${props.eid}/ranking`)
    if (res.success) items.value = res.data || []
  } catch (e) {
    console.error('加载排行榜失败:', e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.ranking-panel { background: #fff; border: 1px solid #e0e7ff; border-radius: 12px; padding: 20px 24px; }
.rp-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.rp-header h3 { font-size: 13px; font-weight: 600; margin: 0; color: #1e293b; }
.rp-count { font-size: 11px; color: #94a3b8; }
.rp-loading, .rp-empty { text-align: center; padding: 24px; color: #94a3b8; font-size: 11px; }
.rp-table { width: 100%; border-collapse: collapse; }
.rp-table th {
  text-align: left; font-size: 11px; color: #94a3b8; font-weight: 500;
  padding: 8px 10px; border-bottom: 1px solid #e2e8f0;
}
.rp-table td { padding: 10px; border-bottom: 1px solid #f1f5f9; font-size: 11px; }
.rp-table tr:last-child td { border-bottom: none; }
.col-rank { width: 64px; }
.col-score { width: 80px; }
.col-time { width: 90px; }
.col-status { width: 80px; }
.rank-badge {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 50%; font-size: 11px; font-weight: 700;
  background: #f1f5f9; color: #64748b;
}
.rb-1 { background: #fef3c7; color: #d97706; }
.rb-2 { background: #e2e8f0; color: #475569; }
.rb-3 { background: #fde8d8; color: #b45309; }
.rp-username { font-weight: 500; color: #1e293b; }
.rp-score { font-weight: 700; color: #3b82f6; }
.rp-status {
  font-size: 10px; padding: 2px 8px; border-radius: 10px;
}
.st-reviewed { background: #dcfce7; color: #16a34a; }
.st-submitted { background: #dbeafe; color: #2563eb; }
</style>
