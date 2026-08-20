<template>
  <div class="page-container">
    <div class="page-top">
      <div>
        <h1>班级任务</h1>
        <p class="page-subtitle" v-if="authStore.isAdmin">管理教学班级与任务</p>
        <p class="page-subtitle" v-else>我的班级与任务</p>
      </div>
    </div>

    <!-- 区块1：我的班级 / 班级管理 -->
    <section class="block-section">
      <div class="block-header">
        <h2 class="block-title">{{ authStore.isAdmin ? '班级管理' : '我的班级' }}</h2>
        <button v-if="authStore.isAdmin" class="btn btn-primary" @click="openCreate">+ 新建班级</button>
      </div>

      <div v-if="!authStore.isAdmin" class="join-section">
        <div class="join-controls">
          <input v-model="joinCode" class="input" placeholder="输入6位班级码加入班级" maxlength="6" style="width:220px" />
          <button class="btn btn-primary" @click="doJoin" :disabled="joining">{{ joining ? '加入中...' : '加入班级' }}</button>
        </div>
        <p v-if="joinMsg" class="feedback-msg" :class="joinOk ? 'msg-ok' : 'msg-err'">{{ joinMsg }}</p>
      </div>

      <UiLoading v-if="classLoading" />

      <UiEmpty v-else-if="classes.length === 0"><template>{{ authStore.isAdmin ? '暂未创建班级，点击"新建班级"开始' : '暂未加入任何班级，请通过班级码加入' }}</template></UiEmpty>

      <div v-else class="class-grid">
        <div v-for="c in classPaged" :key="c.id" class="card class-card" @click="goDetail(c.id)" style="cursor:pointer">
          <div class="class-card-header">
            <h3>{{ c.name }}</h3>
            <span class="class-code">班级码：{{ c.class_code }}</span>
          </div>
          <p class="class-desc">{{ c.description || '暂无描述' }}</p>
          <div class="class-meta">
            <span>{{ c.student_count || 0 }} 名学生</span>
            <span>创建于 {{ formatDate(c.created_at) }}</span>
          </div>
        </div>
      </div>

      <UiPagination v-model:page="classPage" :total="classes.length" :page-size="classPageSize" />

      <!-- 创建班级弹窗 -->
      <div v-if="showForm" class="modal-mask" @click.self="showForm = false">
        <div class="modal-card">
          <h4>新建班级</h4>
          <div class="form-group">
            <label>班级名称 <span class="required">*</span></label>
            <input v-model="form.name" class="input" placeholder="如：2024级计算机1班" />
          </div>
          <div class="form-group">
            <label>班级描述</label>
            <textarea v-model="form.description" class="input" rows="2" placeholder="可选描述"></textarea>
          </div>
          <div v-if="formError" class="error-msg">{{ formError }}</div>
          <div class="modal-actions">
            <button class="btn btn-ghost" @click="showForm = false">取消</button>
            <button class="btn btn-primary" @click="doCreate" :disabled="saving">{{ saving ? '创建中...' : '创建' }}</button>
          </div>
        </div>
      </div>
    </section>

    <!-- 区块2：我的任务 / 任务管理 -->
    <section class="block-section">
      <div class="block-header">
        <h2 class="block-title">{{ authStore.isAdmin ? '任务管理' : '我的任务' }}</h2>
        <router-link to="/exams/edit" class="btn btn-primary" v-if="authStore.isAdmin">+ 新建任务</router-link>
      </div>

      <UiLoading v-if="examLoading" />

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
          <tr v-for="e in examPaged" :key="e.id">
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
            <td>{{ formatDateTime(e.start_time) }} ~ {{ formatDateTime(e.end_time) }}</td>
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

      <UiPagination v-model:page="examPage" :total="exams.length" :page-size="examPageSize" />
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { authStore } from '../stores/auth'
import { useFeedback } from '../composables/useFeedback'
import UiPagination from '../components/ui/UiPagination.vue'

const router = useRouter()
const { tip, ask } = useFeedback()

// ── 班级 ──
const classes = ref([])
const classLoading = ref(true)
const showForm = ref(false)
const saving = ref(false)
const form = ref({ name: '', description: '' })
const formError = ref('')
const joinCode = ref('')
const joining = ref(false)
const joinMsg = ref('')
const joinOk = ref(true)
const classPage = ref(1)
const classPageSize = 4
const classPaged = computed(() =>
  classes.value.slice((classPage.value - 1) * classPageSize, classPage.value * classPageSize)
)

// ── 任务 ──
const exams = ref([])
const examLoading = ref(true)
const examPage = ref(1)
const examPageSize = 10
const examPaged = computed(() =>
  exams.value.slice((examPage.value - 1) * examPageSize, examPage.value * examPageSize)
)

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
function attemptsExhausted(e) {
  if (!e.max_attempts) return false
  return (e.my_attempt_count || 0) >= e.max_attempts
}

// 两个区块并行加载
onMounted(() => {
  Promise.all([fetchClasses(), fetchExams()])
})

async function fetchClasses() {
  classLoading.value = true
  try {
    const r = await api.get('/classes')
    if (r.success) { classes.value = r.data?.items || r.data; classPage.value = 1 }
  } catch (e) { console.error(e); tip('班级列表加载失败，请稍后重试') }
  finally { classLoading.value = false }
}

async function fetchExams() {
  examLoading.value = true
  try {
    const r = await api.get('/exams')
    if (r.success) { exams.value = r.data?.items || r.data; examPage.value = 1 }
  } catch (e) { console.error(e); tip('加载任务列表失败，请刷新重试') }
  finally { examLoading.value = false }
}

function openCreate() {
  form.value = { name: '', description: '' }
  formError.value = ''
  showForm.value = true
}

async function doCreate() {
  if (!form.value.name.trim()) { formError.value = '请输入班级名称'; return }
  formError.value = ''
  saving.value = true
  try {
    await api.post('/classes', form.value)
    showForm.value = false
    fetchClasses()
  } catch (e) { formError.value = e.message || '创建失败' }
  finally { saving.value = false }
}

async function doJoin() {
  const code = joinCode.value.trim()
  if (!code) { joinMsg.value = '请输入班级码'; joinOk.value = false; return }
  joining.value = true
  joinMsg.value = ''
  try {
    const r = await api.post('/classes/join', { class_code: code })
    if (r.success) {
      joinOk.value = true
      joinMsg.value = '加入成功！'
      joinCode.value = ''
      fetchClasses()
    }
  } catch (e) {
    joinOk.value = false
    joinMsg.value = e.message || '加入失败'
  }
  finally { joining.value = false }
}

function goDetail(id) {
  router.push(`/classes/${id}`)
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

// 班级：仅日期
function formatDate(d) {
  if (!d) return '-'
  return d.slice(0, 10)
}
// 任务：日期+时间
function formatDateTime(d) {
  if (!d) return '-'
  return d.slice(0, 16).replace('T', ' ')
}
</script>

<style scoped>
.page-container { max-width: 1000px; margin: 0 auto; padding: 32px 24px; }
.page-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-top h1 { font-size: 22px; margin: 0; }
.page-subtitle { font-size: 13px; color: var(--text-secondary); margin: 4px 0 0; }

/* 上下两栏区块 */
.block-section {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
  padding: 20px 24px; margin-bottom: 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.block-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.block-title { font-size: 16px; font-weight: 600; margin: 0; color: #1e293b; }

/* ── 班级 ── */
.join-section {
  background: #f0f9ff; border: 1px solid #bae6fd;
  border-radius: 8px; padding: 14px 18px; margin-bottom: 20px;
}
.join-controls { display: flex; gap: 8px; align-items: center; }
.feedback-msg { font-size: 11px; margin-top: 6px; }
.msg-ok { color: #16a34a; }
.msg-err { color: #dc2626; }

.class-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.class-card { padding: 20px; transition: box-shadow 0.2s; }
.class-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
.class-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.class-card-header h3 { margin: 0; font-size: 14px; }
.class-code { font-size: 10px; color: var(--accent-blue); background: #eff6ff; padding: 2px 8px; border-radius: 4px; font-family: monospace; }
.class-desc { font-size: 11px; color: var(--text-secondary); margin-bottom: 12px; }
.class-meta { display: flex; gap: 16px; font-size: 10px; color: var(--text-light); }

.modal-mask {
  position: fixed; inset: 0; background: rgba(0,0,0,0.35);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal-card {
  background: #fff; border-radius: 10px; padding: 24px; width: 420px;
  box-shadow: 0 8px 30px rgba(0,0,0,0.15);
}
.modal-card h4 { margin: 0 0 16px; font-size: 14px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 11px; font-weight: 500; margin-bottom: 4px; color: var(--text-secondary); }
.required { color: #dc2626; }
.error-msg { color: #dc2626; font-size: 11px; margin-bottom: 8px; }

/* ── 任务表格 ── */
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

.task-type-tag { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.task-type-exam { background: #dbeafe; color: #1e40af; }
.task-type-homework { background: #ede9fe; color: #6d28d9; }

/* ── 通用按钮/表单控件 ── */
.btn { padding: 8px 16px; font-size: 13px; border-radius: 6px; cursor: pointer; border: 1px solid transparent; text-decoration: none; display: inline-block; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover { background: #2563eb; }
.btn-outline { border-color: #cbd5e1; color: #334155; background: #fff; }
.btn-outline:hover { border-color: #3b82f6; color: #3b82f6; }
.btn-warning { background: #f59e0b; color: #fff; }
.btn-warning:hover { background: #d97706; }
.btn-xs { padding: 3px 10px; font-size: 11px; }
.btn-ghost { border-color: #cbd5e1; background: #fff; color: #334155; }
.btn-ghost:hover { background: #f1f5f9; }
.btn-danger-text { border: none; color: #dc2626; background: transparent; cursor: pointer; font-size: 11px; }
.btn-danger-text:hover { text-decoration: underline; }
.input { padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 11px; box-sizing: border-box; }
.input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.1); }
textarea.input { resize: vertical; }
</style>
