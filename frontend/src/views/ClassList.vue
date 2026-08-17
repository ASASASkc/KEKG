<template>
  <div class="page-container">
    <div class="page-top">
      <div>
        <h1>班级管理</h1>
        <p class="page-subtitle" v-if="authStore.isAdmin">管理您的教学班级</p>
        <p class="page-subtitle" v-else>我的班级</p>
      </div>
      <div class="top-actions">
        <button v-if="authStore.isAdmin" class="btn btn-primary" @click="openCreate">+ 新建班级</button>
      </div>
    </div>

    <div v-if="!authStore.isAdmin" class="join-section">
      <div class="join-controls">
        <input v-model="joinCode" class="input" placeholder="输入6位班级码加入班级" maxlength="6" style="width:220px" />
        <button class="btn btn-primary" @click="doJoin" :disabled="joining">{{ joining ? '加入中...' : '加入班级' }}</button>
      </div>
      <p v-if="joinMsg" class="feedback-msg" :class="joinOk ? 'msg-ok' : 'msg-err'">{{ joinMsg }}</p>
    </div>

    <UiLoading v-if="loading" />

    <UiEmpty v-else-if="classes.length === 0"><template>{{ authStore.isAdmin ? '暂未创建班级，点击"新建班级"开始' : '暂未加入任何班级，请通过班级码加入' }}</template></UiEmpty>

    <div v-else class="class-grid">
      <div v-for="c in classes" :key="c.id" class="card class-card" @click="goDetail(c.id)" style="cursor:pointer">
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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { authStore } from '../stores/auth'

const router = useRouter()
const classes = ref([])
const loading = ref(true)
const showForm = ref(false)
const saving = ref(false)
const form = ref({ name: '', description: '' })
const formError = ref('')
const joinCode = ref('')
const joining = ref(false)
const joinMsg = ref('')
const joinOk = ref(true)

onMounted(fetchClasses)

async function fetchClasses() {
  loading.value = true
  try {
    const r = await api.get('/classes')
    if (r.success) classes.value = r.data?.items || r.data
  } catch (e) { console.error(e) }
  finally { loading.value = false }
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

function formatDate(d) {
  if (!d) return '-'
  return d.slice(0, 10)
}
</script>

<style scoped>
.page-container { max-width: 900px; margin: 0 auto; padding: 32px 24px; }
.page-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-top h1 { font-size: 19px; margin: 0; }
.page-subtitle { font-size: 11px; color: var(--text-secondary); margin: 4px 0 0; }
.top-actions { display: flex; gap: 8px; }

.join-section {
  background: #f0f9ff; border: 1px solid #bae6fd;
  border-radius: 8px; padding: 14px 18px; margin-bottom: 20px;
}
.join-controls { display: flex; gap: 8px; align-items: center; }
.feedback-msg { font-size: 11px; margin-top: 6px; }
.msg-ok { color: #16a34a; }
.msg-err { color: #dc2626; }

.loading-text { text-align: center; padding: 40px; color: var(--text-secondary); }
.empty-msg { text-align: center; padding: 40px; color: var(--text-light); font-size: 12px; }

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

.btn { padding: 8px 16px; font-size: 11px; border-radius: 6px; cursor: pointer; border: 1px solid transparent; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover { background: #2563eb; }
.btn-ghost { border-color: #cbd5e1; background: #fff; color: #334155; }
.btn-ghost:hover { background: #f1f5f9; }
.input { padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 11px; box-sizing: border-box; }
.input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.1); }
textarea.input { resize: vertical; }
</style>
