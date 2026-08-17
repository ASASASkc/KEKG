<template>
  <div class="page-container">
    <div class="page-top">
      <div>
        <router-link to="/classes" class="back-link">&larr; 返回班级列表</router-link>
        <h1 v-if="cls">{{ cls.name }}</h1>
        <p class="page-subtitle">班级码：<code>{{ cls?.class_code }}</code> | {{ cls?.description || '暂无描述' }}</p>
      </div>
      <div class="top-actions" v-if="cls">
        <button v-if="authStore.isAdmin" class="btn btn-outline btn-sm" @click="openEdit">编辑班级</button>
        <button v-if="!authStore.isAdmin" class="btn btn-outline btn-sm btn-leave" @click="leaveClass">退出班级</button>
        <button v-if="authStore.isAdmin" class="btn btn-danger btn-sm" @click="confirmDelete">解散班级</button>
      </div>
    </div>

    <UiLoading v-if="loading" />

    <div v-else-if="errorMsg" class="empty-state">
      <p>{{ errorMsg }}</p>
      <router-link to="/classes" class="btn btn-primary" style="margin-top:12px;display:inline-block">返回班级列表</router-link>
    </div>

    <template v-else-if="cls">
      <!-- 学生列表 -->
      <div class="section">
        <h3>学生列表 ({{ students.length }})</h3>
        <table v-if="students.length" class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>用户名</th>
              <th>邮箱</th>
              <th>加入时间</th>
              <th v-if="authStore.isAdmin">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in students" :key="s.id">
              <td>{{ s.id }}</td>
              <td>{{ s.username }}</td>
              <td>{{ s.email || '-' }}</td>
              <td>{{ formatDate(s.joined_at) }}</td>
              <td v-if="authStore.isAdmin">
                <button class="btn btn-xs btn-danger-text" @click="removeStudent(s)">移除</button>
              </td>
            </tr>
          </tbody>
        </table>
        <UiEmpty v-else text="暂无学生" />
      </div>

      <!-- 班级公告 -->
      <div class="section">
        <div class="section-header">
          <h3>班级公告 ({{ announcements.length }})</h3>
          <button v-if="authStore.isAdmin" class="btn btn-sm btn-outline" @click="openAnnouncementForm">+ 发布公告</button>
        </div>
        <div v-if="announcements.length" class="announcement-list">
          <div v-for="a in announcements" :key="a.id" class="announcement-item" :class="{ pinned: a.is_pinned }">
            <div class="ann-header">
              <span class="ann-dot" v-if="a.is_pinned">📌</span>
              <strong class="ann-title">{{ a.title }}</strong>
              <span class="ann-time">{{ formatDate(a.created_at) }}</span>
              <button v-if="authStore.isAdmin" class="btn btn-xs btn-danger-text" @click="deleteAnnouncement(a.id)">删除</button>
            </div>
            <div class="ann-content" v-if="a.content">{{ a.content }}</div>
          </div>
        </div>
        <UiEmpty v-else text="暂无公告" />
      </div>

      <!-- 发布公告弹窗 -->
      <div v-if="showAnnForm" class="modal-mask" @click.self="showAnnForm = false">
        <div class="modal-card">
          <h4>发布公告</h4>
          <div class="form-group">
            <label>公告标题</label>
            <input v-model="annForm.title" class="input" placeholder="输入公告标题" />
          </div>
          <div class="form-group">
            <label>公告内容</label>
            <textarea v-model="annForm.content" class="input" rows="3" placeholder="公告内容（可选）"></textarea>
          </div>
          <div class="form-group">
            <label class="checkbox-label">
              <input type="checkbox" v-model="annForm.is_pinned" />
              <span>置顶公告</span>
            </label>
          </div>
          <div class="modal-actions">
            <button class="btn btn-ghost" @click="showAnnForm = false">取消</button>
            <button class="btn btn-primary" @click="doCreateAnnouncement" :disabled="saving">发布</button>
          </div>
        </div>
      </div>

      <!-- 考试列表 -->
      <div class="section">
        <h3>考试列表</h3>
        <div v-if="authStore.isAdmin" style="margin-bottom:12px">
          <router-link :to="`/exams/edit?class_id=${cls.id}`" class="btn btn-primary btn-sm">+ 新建考试</router-link>
        </div>
        <table v-if="exams.length" class="data-table">
          <thead>
            <tr>
              <th>标题</th>
              <th>状态</th>
              <th>时长</th>
              <th>时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="e in exams" :key="e.id">
              <td>{{ e.title }}</td>
              <td><span class="status-tag" :class="'status-' + e.status">{{ statusLabel(e.status) }}</span></td>
              <td>{{ e.duration_minutes }} 分钟</td>
              <td>{{ formatDate(e.start_time) }} ~ {{ formatDate(e.end_time) }}</td>
              <td class="action-cell">
                <router-link v-if="e.status === 'published' && !authStore.isAdmin" :to="`/exams/${e.id}/doing`" class="btn btn-xs btn-primary">去答题</router-link>
                <router-link v-if="authStore.isAdmin" :to="`/exams/${e.id}/review`" class="btn btn-xs btn-outline">阅卷</router-link>
                <router-link v-if="!authStore.isAdmin" :to="`/exams/${e.id}/result`" class="btn btn-xs btn-outline">成绩</router-link>
              </td>
            </tr>
          </tbody>
        </table>
        <UiEmpty v-else text="暂无考试" />
      </div>

      <!-- 学生分组 -->
      <div class="section" v-if="authStore.isAdmin">
        <div class="section-header">
          <h3>学生分组 ({{ groups.length }})</h3>
          <button class="btn btn-sm btn-outline" @click="openGroupForm">+ 创建分组</button>
        </div>
        <div v-if="groups.length" class="group-list">
          <div v-for="g in groups" :key="g.id" class="group-item">
            <div class="group-header" @click="toggleGroup(g.id)">
              <span class="group-arrow" :class="{ open: openGroups[g.id] }">▸</span>
              <span class="group-name">{{ g.name }}</span>
              <span class="group-count">{{ g.member_count || 0 }} 人</span>
              <button class="btn btn-xs btn-danger-text" @click.stop="deleteGroup(g.id)">删除</button>
            </div>
            <div v-if="openGroups[g.id]" class="group-members">
              <div v-if="groupMembers[g.id]?.length">
                <span v-for="m in groupMembers[g.id]" :key="m.id" class="member-tag">
                  {{ m.username }}
                  <button class="member-remove" @click="removeGroupMember(g.id, m.id)">×</button>
                </span>
              </div>
              <UiLoading v-else-if="groupLoading[g.id]" />
              <UiEmpty v-else text="暂无成员，从学生列表拖拽或手动添加" />
              <select class="input input-sm" @change="addGroupMember(g.id, $event)" style="margin-top:8px;width:auto">
                <option value="">添加学生...</option>
                <option v-for="s in unassignedStudents(g.id)" :key="s.id" :value="s.id">{{ s.username }}</option>
              </select>
            </div>
          </div>
        </div>
        <UiEmpty v-else text="暂无分组" />
      </div>

      <!-- 创建分组弹窗 -->
      <div v-if="showGroupForm" class="modal-mask" @click.self="showGroupForm = false">
        <div class="modal-card">
          <h4>创建分组</h4>
          <div class="form-group">
            <label>分组名称</label>
            <input v-model="groupForm.name" class="input" placeholder="如：第一小组" />
          </div>
          <div class="form-group">
            <label>描述</label>
            <input v-model="groupForm.description" class="input" placeholder="可选" />
          </div>
          <div class="modal-actions">
            <button class="btn btn-ghost" @click="showGroupForm = false">取消</button>
            <button class="btn btn-primary" @click="doCreateGroup" :disabled="saving">创建</button>
          </div>
        </div>
      </div>
    </template>

    <!-- 编辑班级弹窗 -->
    <div v-if="showEdit" class="modal-mask" @click.self="showEdit = false">
      <div class="modal-card">
        <h4>编辑班级</h4>
        <div class="form-group">
          <label>班级名称</label>
          <input v-model="editForm.name" class="input" />
        </div>
        <div class="form-group">
          <label>班级描述</label>
          <textarea v-model="editForm.description" class="input" rows="2"></textarea>
        </div>
        <div class="modal-actions">
          <button class="btn btn-ghost" @click="showEdit = false">取消</button>
          <button class="btn btn-primary" @click="doEdit" :disabled="saving">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { authStore } from '../stores/auth'
import { useFeedback } from '../composables/useFeedback'

const route = useRoute()
const router = useRouter()
const cid = computed(() => route.params.id)
const { tip, ask } = useFeedback()

const cls = ref(null)
const errorMsg = ref('')
const students = ref([])
const exams = ref([])
const loading = ref(true)
const saving = ref(false)
const showEdit = ref(false)
const editForm = ref({ name: '', description: '' })

// 公告
const announcements = ref([])
const showAnnForm = ref(false)
const annForm = ref({ title: '', content: '', is_pinned: false })

// 分组
const groups = ref([])
const showGroupForm = ref(false)
const groupForm = ref({ name: '', description: '' })
const openGroups = reactive({})
const groupMembers = reactive({})
const groupLoading = reactive({})

const STATUS_MAP = { draft: '草稿', published: '进行中', closed: '已关闭' }
function statusLabel(s) { return STATUS_MAP[s] || s }

onMounted(fetchData)

async function fetchData() {
  loading.value = true
  errorMsg.value = ''
  try {
    const r = await api.get(`/classes/${cid.value}`)
    if (r.success) {
      cls.value = r.data
      students.value = r.data.students || []
    } else {
      errorMsg.value = r.message || '班级不存在'
      return
    }
    const [r2, r3, r4] = await Promise.all([
      api.get('/exams', { params: { class_id: cid.value } }),
      api.get(`/classes/${cid.value}/announcements`),
      authStore.isAdmin ? api.get(`/classes/${cid.value}/groups`) : Promise.resolve(null)
    ])
    if (r2?.success) exams.value = r2.data?.items || r2.data
    if (r3?.success) announcements.value = r3.data || []
    if (r4?.success) groups.value = r4.data || []
  } catch (e) {
    errorMsg.value = e.message || '加载失败，请稍后重试'
    console.error('班级详情加载失败:', e)
  }
  finally { loading.value = false }
}

function openEdit() {
  editForm.value = { name: cls.value.name, description: cls.value.description || '' }
  showEdit.value = true
}

async function doEdit() {
  saving.value = true
  try {
    await api.put(`/classes/${cid.value}`, editForm.value)
    cls.value.name = editForm.value.name
    cls.value.description = editForm.value.description
    showEdit.value = false
  } catch (e) { tip(e.message || '更新失败') }
  finally { saving.value = false }
}

function confirmDelete() {
  ask('确定解散此班级？所有学生将被移除。', async () => {
    try {
      await api.delete(`/classes/${cid.value}`)
      router.push('/classes')
    } catch (e) { tip('解散失败') }
  })
}

function removeStudent(s) {
  ask(`确定移除学生 ${s.username}？`, async () => {
    try {
      await api.delete(`/classes/${cid.value}/students/${s.id}`)
      students.value = students.value.filter(st => st.id !== s.id)
    } catch (e) { tip('移除失败') }
  })
}

// ── 退出班级 ──
function leaveClass() {
  ask('确定退出该班级？', async () => {
    try {
      await api.post(`/classes/${cid.value}/leave`)
      router.push('/classes')
    } catch (e) { tip(e.message || '退出失败') }
  })
}

// ── 公告 ──
function openAnnouncementForm() {
  annForm.value = { title: '', content: '', is_pinned: false }
  showAnnForm.value = true
}
async function doCreateAnnouncement() {
  if (!annForm.value.title.trim()) return
  saving.value = true
  try {
    await api.post(`/classes/${cid.value}/announcements`, annForm.value)
    showAnnForm.value = false
    const r = await api.get(`/classes/${cid.value}/announcements`)
    if (r.success) announcements.value = r.data || []
  } catch (e) { tip(e.message || '发布失败') }
  finally { saving.value = false }
}
function deleteAnnouncement(aid) {
  ask('确定删除该公告？', async () => {
    try {
      await api.delete(`/classes/${cid.value}/announcements/${aid}`)
      announcements.value = announcements.value.filter(a => a.id !== aid)
    } catch (e) { tip('删除失败') }
  })
}

// ── 分组 ──
function openGroupForm() {
  groupForm.value = { name: '', description: '' }
  showGroupForm.value = true
}
async function doCreateGroup() {
  if (!groupForm.value.name.trim()) return
  saving.value = true
  try {
    await api.post(`/classes/${cid.value}/groups`, groupForm.value)
    showGroupForm.value = false
    const r = await api.get(`/classes/${cid.value}/groups`)
    if (r.success) groups.value = r.data || []
  } catch (e) { tip(e.message || '创建失败') }
  finally { saving.value = false }
}
function deleteGroup(gid) {
  ask('确定删除该分组？', async () => {
    try {
      await api.delete(`/classes/${cid.value}/groups/${gid}`)
      groups.value = groups.value.filter(g => g.id !== gid)
    } catch (e) { tip('删除失败') }
  })
}
async function toggleGroup(gid) {
  openGroups[gid] = !openGroups[gid]
  if (openGroups[gid] && !groupMembers[gid]) {
    groupLoading[gid] = true
    try {
      const r = await api.get(`/classes/${cid.value}/groups/${gid}/members`)
      if (r.success) groupMembers[gid] = r.data || []
    } catch (e) { console.error(e) }
    finally { groupLoading[gid] = false }
  }
}
function unassignedStudents(gid) {
  const members = groupMembers[gid] || []
  const memberIds = new Set(members.map(m => m.id))
  return students.value.filter(s => !memberIds.has(s.id))
}
async function addGroupMember(gid, event) {
  const sid = parseInt(event.target.value)
  if (!sid) return
  event.target.value = ''
  try {
    await api.post(`/classes/${cid.value}/groups/${gid}/members`, { student_id: sid })
    if (!groupMembers[gid]) groupMembers[gid] = []
    const student = students.value.find(s => s.id === sid)
    if (student) groupMembers[gid].push(student)
  } catch (e) { tip('添加失败') }
}
async function removeGroupMember(gid, mid) {
  try {
    await api.delete(`/classes/${cid.value}/groups/${gid}/members/${mid}`)
    groupMembers[gid] = (groupMembers[gid] || []).filter(m => m.id !== mid)
  } catch (e) { tip('移除失败') }
}

function formatDate(d) {
  if (!d) return '-'
  return d.slice(0, 16).replace('T', ' ')
}
</script>

<style scoped>
.page-container { max-width: 900px; margin: 0 auto; padding: 32px 24px; }
.page-top { margin-bottom: 24px; }
.back-link { font-size: 11px; color: var(--accent-blue); text-decoration: none; display: inline-block; margin-bottom: 8px; }
.back-link:hover { text-decoration: underline; }
.page-top h1 { font-size: 19px; margin: 0 0 4px; }
.page-subtitle { font-size: 11px; color: var(--text-secondary); margin: 0; }
.page-subtitle code { background: #f1f5f9; padding: 2px 6px; border-radius: 3px; font-size: 11px; }
.top-actions { display: flex; gap: 8px; margin-top: 12px; }

.section { margin-bottom: 28px; }
.section h3 { font-size: 14px; margin: 0 0 12px; }

.loading-text { text-align: center; padding: 40px; color: var(--text-secondary); }
.empty-msg { text-align: center; padding: 24px; color: var(--text-light); font-size: 11px; }
.empty-state { text-align: center; padding: 60px 24px; color: var(--text-secondary); font-size: 13px; }

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
.action-cell { display: flex; gap: 6px; }

.status-tag { font-size: 10px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.status-draft { background: #e2e8f0; color: #475569; }
.status-published { background: #d1fae5; color: #065f46; }
.status-closed { background: #fee2e2; color: #991b1b; }

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

.btn { padding: 8px 16px; font-size: 11px; border-radius: 6px; cursor: pointer; border: 1px solid transparent; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover { background: #2563eb; }
.btn-outline { border-color: #cbd5e1; color: #334155; background: #fff; }
.btn-outline:hover { border-color: #3b82f6; color: #3b82f6; }
.btn-ghost { border-color: #cbd5e1; background: #fff; color: #334155; }
.btn-ghost:hover { background: #f1f5f9; }
.btn-danger { background: #dc2626; color: #fff; }
.btn-danger:hover { background: #b91c1c; }
.btn-sm { padding: 6px 12px; font-size: 11px; }
.btn-xs { padding: 3px 10px; font-size: 10px; }
.btn-danger-text { border: none; color: #dc2626; background: transparent; cursor: pointer; font-size: 10px; }
.btn-danger-text:hover { text-decoration: underline; }
.input { padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 11px; width: 100%; box-sizing: border-box; }
.input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.1); }
textarea.input { resize: vertical; }

/* ── 公告 ── */
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.section-header h3 { margin: 0; }

.announcement-list { display: flex; flex-direction: column; gap: 8px; }
.announcement-item {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 14px;
}
.announcement-item.pinned { border-color: #fbbf24; background: #fffbeb; }
.ann-header { display: flex; align-items: center; gap: 8px; }
.ann-dot { font-size: 12px; }
.ann-title { font-size: 12px; color: #1e293b; }
.ann-time { font-size: 10px; color: var(--text-light); margin-left: auto; }
.ann-content { margin-top: 8px; font-size: 11px; color: var(--text-secondary); line-height: 1.5; }

.checkbox-label { display: flex; align-items: center; gap: 6px; font-size: 11px; cursor: pointer; }
.checkbox-label input[type="checkbox"] { margin: 0; }

/* ── 分组 ── */
.group-list { display: flex; flex-direction: column; gap: 6px; }
.group-item { border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
.group-header {
  display: flex; align-items: center; gap: 8px; padding: 10px 14px;
  background: #f8fafc; cursor: pointer; user-select: none;
}
.group-header:hover { background: #f1f5f9; }
.group-arrow { font-size: 11px; color: var(--text-light); transition: transform 0.2s; display: inline-block; }
.group-arrow.open { transform: rotate(90deg); }
.group-name { font-size: 12px; font-weight: 500; color: #1e293b; }
.group-count { font-size: 11px; color: var(--text-light); }
.group-members { padding: 10px 14px 14px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.member-tag {
  display: inline-flex; align-items: center; gap: 4px;
  background: #eff6ff; color: #1e40af; font-size: 11px;
  padding: 3px 8px; border-radius: 4px;
}
.member-remove { border: none; background: none; color: #ef4444; cursor: pointer; font-size: 12px; font-weight: bold; padding: 0 2px; line-height: 1; }
.member-remove:hover { color: #dc2626; }

.btn-leave { border-color: #fca5a5; color: #dc2626; }
.btn-leave:hover { border-color: #dc2626; background: #fef2f2; }
</style>
