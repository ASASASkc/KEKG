<template>
  <div class="page-container">
    <div class="page-top">
      <div>
        <h1>任务中心</h1>
        <p class="page-subtitle" v-if="authStore.isAdmin">管理所有考试和作业</p>
        <p class="page-subtitle" v-else>我的考试和作业</p>
      </div>
      <router-link to="/exams/edit" class="btn btn-primary" v-if="authStore.isAdmin">+ 新建任务</router-link>
    </div>

    <UiLoading v-if="loading" />

    <UiEmpty v-else-if="exams.length === 0">
      <template v-if="authStore.isAdmin">
        暂无任务，点击"新建任务"开始组卷
      </template>
      <template v-else>
        <p>你还没有可参加的考试或作业。</p>
        <p class="empty-hint">考试/作业需要教师创建并在任务中心 <strong>「发布」</strong> 后才会在这里显示。</p>
        <router-link to="/class-tasks" class="btn btn-primary btn-sm" style="margin-top:12px;display:inline-block">前往加入班级</router-link>
      </template>
    </UiEmpty>

    <table v-else class="data-table">
      <thead>
        <tr>
          <th>标题</th>
          <th>类型</th>
          <th>班级</th>
          <th>状态</th>
          <th>时长</th>
          <th>时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="e in exams" :key="e.id">
          <td>{{ e.title }}</td>
          <td><span class="task-type-tag" :class="'task-type-' + (e.task_type || 'exam')">{{ e.task_type === 'homework' ? '作业' : '考试' }}</span></td>
          <td>{{ e.class_name || '-' }}</td>
          <td>
            <span class="status-tag" :class="statusClass(e)">{{ statusLabel(e) }}</span>
            <span v-if="!authStore.isAdmin && e.max_attempts" class="attempt-info" :class="{ 'attempt-full': (e.my_attempt_count || 0) >= e.max_attempts && !e.my_status }">
              {{ e.my_attempt_count || 0 }}/{{ e.max_attempts }} 次
            </span>
          </td>
          <td>{{ e.task_type === 'homework' ? '-' : (e.duration_minutes + ' 分钟') }}</td>
          <td>{{ formatDate(e.start_time) }} ~ {{ formatDate(e.end_time) }}</td>
          <td class="action-cell">
            <!-- 学生端（动态状态：scheduled 未开始 / active 进行中 / expired 已结束） -->
            <router-link v-if="!authStore.isAdmin && e.time_status === 'active' && !e.my_status && !attemptsExhausted(e)" :to="`/exams/${e.id}/doing`" class="btn btn-xs btn-primary">{{ e.task_type === 'homework' ? '去做作业' : '去答题' }}</router-link>
            <span v-if="!authStore.isAdmin && e.time_status === 'active' && attemptsExhausted(e) && !e.my_status" class="btn btn-xs" style="color:#999;cursor:default">次数已用完</span>
            <router-link v-if="!authStore.isAdmin && e.time_status === 'active' && e.my_status === 'in_progress'" :to="`/exams/${e.id}/doing`" class="btn btn-xs btn-warning">继续答题</router-link>
            <template v-if="!authStore.isAdmin && e.my_status === 'submitted'">
              <router-link :to="`/exams/${e.id}/result`" class="btn btn-xs btn-outline">查看成绩</router-link>
              <router-link v-if="e.time_status === 'active' && e.max_attempts && (e.my_attempt_count || 0) < e.max_attempts" :to="`/exams/${e.id}/doing`" class="btn btn-xs btn-primary">重新答题</router-link>
            </template>
            <span v-if="!authStore.isAdmin && (e.status === 'closed' || e.time_status === 'expired') && !e.my_status" class="btn btn-xs" style="color:#999;cursor:default">已结束</span>
            <!-- 教师端 -->
            <template v-if="authStore.isAdmin">
              <button v-if="e.status === 'draft'" class="btn btn-xs btn-primary" @click="doPublish(e.id)">发布</button>
              <button v-if="e.status === 'published'" class="btn btn-xs btn-warning" @click="doClose(e.id)">关闭</button>
              <router-link :to="`/exams/edit?edit=${e.id}`" class="btn btn-xs btn-outline">编辑</router-link>
              <router-link :to="`/exams/${e.id}/review`" class="btn btn-xs btn-outline">阅卷</router-link>
              <button class="btn btn-xs btn-danger-text" @click="doDelete(e.id)">删除</button>
            </template>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import { authStore } from '../stores/auth'
import { useFeedback } from '../composables/useFeedback'

const { tip, ask } = useFeedback()

const exams = ref([])
const loading = ref(true)

const STATUS_MAP = { draft: '草稿', published: '进行中', closed: '已关闭', scheduled: '未开始', active: '进行中', expired: '已结束' }
function statusClass(e) {
  // 学生端：有个人提交状态时用 my_status 着色
  if (!authStore.isAdmin && e.my_status === 'submitted') return 'status-submitted'
  if (!authStore.isAdmin && e.my_status === 'in_progress') return 'status-in_progress'
  return 'status-' + (e.time_status || e.status || 'draft')
}
function statusLabel(e) {
  // 学生端：优先显示个人提交状态
  if (!authStore.isAdmin && e.my_status) {
    if (e.my_status === 'submitted') return '已完成'
    if (e.my_status === 'in_progress') return '答题中'
  }
  // 动态状态优先（已发布考试按时间：未开始/进行中/已结束）
  return STATUS_MAP[e.time_status || e.status] || e.status
}

onMounted(fetchExams)

async function fetchExams() {
  loading.value = true
  try {
    const r = await api.get('/exams')
    if (r.success) exams.value = r.data?.items || r.data
  } catch (e) { console.error(e); tip('加载考试列表失败，请刷新重试') }
  finally { loading.value = false }
}

function doPublish(id) {
  ask('确认发布此考试？发布后学生即可开始答题。', async () => {
    try {
      await api.put(`/exams/${id}/publish`)
      fetchExams()
    } catch (e) { tip('发布失败') }
  })
}

function doClose(id) {
  ask('确认关闭此考试？关闭后学生无法继续答题。', async () => {
    try {
      await api.put(`/exams/${id}/close`)
      fetchExams()
    } catch (e) { tip('关闭失败') }
  })
}

function doDelete(id) {
  ask('确认删除此考试？', async () => {
    try {
      await api.delete(`/exams/${id}`)
      exams.value = exams.value.filter(e => e.id !== id)
    } catch (e) { tip('删除失败') }
  })
}

function formatDate(d) {
  if (!d) return '-'
  return d.slice(0, 16).replace('T', ' ')
}

function attemptsExhausted(e) {
  if (!e.max_attempts) return false
  return (e.my_attempt_count || 0) >= e.max_attempts
}
</script>

<style scoped>
.page-container { max-width: 1000px; margin: 0 auto; padding: 32px 24px; }
.page-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-top h1 { font-size: 22px; margin: 0; }
.page-subtitle { font-size: 13px; color: var(--text-secondary); margin: 4px 0 0; }

.loading-text { text-align: center; padding: 40px; color: var(--text-secondary); }
.empty-msg { text-align: center; padding: 40px; color: var(--text-light); }
.empty-hint { font-size: 12px; margin: 4px 0 0; }

.data-table {
  width: 100%; border-collapse: collapse; background: #fff;
  border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.data-table th, .data-table td {
  padding: 10px 14px; text-align: left; font-size: 13px; border-bottom: 1px solid #f1f5f9;
}
.data-table th { background: #f8fafc; font-weight: 600; color: var(--text-secondary); font-size: 12px; }
.data-table tr:last-child td { border-bottom: none; }
.data-table tr:hover td { background: #f8fafc; }
.action-cell { display: flex; gap: 6px; flex-wrap: wrap; }

.status-tag { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.status-draft { background: #e2e8f0; color: #475569; }
.status-published { background: #d1fae5; color: #065f46; }
.status-closed { background: #fee2e2; color: #991b1b; }
.status-submitted { background: #dbeafe; color: #1e40af; }
.status-in_progress { background: #fef3c7; color: #92400e; }
.status-scheduled { background: #e0e7ff; color: #3730a3; }
.status-active { background: #d1fae5; color: #065f46; }
.status-expired { background: #e2e8f0; color: #64748b; }

.attempt-info {
  font-size: 11px; margin-left: 6px; padding: 1px 6px; border-radius: 3px;
  background: #f1f5f9; color: #64748b;
}
.attempt-full { background: #fee2e2; color: #991b1b; }

.btn { padding: 8px 16px; font-size: 13px; border-radius: 6px; cursor: pointer; border: 1px solid transparent; text-decoration: none; display: inline-block; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover { background: #2563eb; }
.btn-outline { border-color: #cbd5e1; color: #334155; background: #fff; }
.btn-outline:hover { border-color: #3b82f6; color: #3b82f6; }
.btn-warning { background: #f59e0b; color: #fff; }
.btn-warning:hover { background: #d97706; }
.btn-xs { padding: 3px 10px; font-size: 11px; }
.btn-danger-text { border: none; color: #dc2626; background: transparent; cursor: pointer; font-size: 11px; }
.btn-danger-text:hover { text-decoration: underline; }

.task-type-tag { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.task-type-exam { background: #dbeafe; color: #1e40af; }
.task-type-homework { background: #ede9fe; color: #6d28d9; }
</style>
