<template>
  <div class="page-container">
    <div class="page-top">
      <h1>用户管理</h1>
      <div class="invite-section">
        <label class="invite-label">注册邀请码</label>
        <div class="invite-controls">
          <input
            v-model="inviteCodeInput"
            class="input input-sm"
            placeholder="设置邀请码（至少4位）"
            style="width: 240px"
          />
          <button class="btn btn-sm btn-primary" @click="saveInviteCode" :disabled="savingInvite">
            {{ savingInvite ? '保存中...' : '更新邀请码' }}
          </button>
        </div>
        <p v-if="inviteMsg" class="feedback-msg">{{ inviteMsg }}</p>
      </div>
    </div>

    <UiLoading v-if="loading" />

    <table v-else class="user-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>用户名</th>
          <th>邮箱</th>
          <th>角色</th>
          <th>注册时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.id" :class="{ 'row-current': u.id === currentUserId }">
          <td>{{ u.id }}</td>
          <td>
            {{ u.username }}
            <span v-if="u.id === currentUserId" class="tag-you">当前</span>
          </td>
          <td>{{ u.email }}</td>
          <td>
            <span class="role-tag" :class="u.role === 'admin' ? 'role-admin' : 'role-user'">
              {{ u.role === 'admin' ? '管理员' : '普通用户' }}
            </span>
          </td>
          <td>{{ formatDate(u.created_at) }}</td>
          <td class="action-cell">
            <button
              v-if="u.id !== currentUserId"
              class="btn btn-xs btn-outline"
              @click="toggleRole(u)"
              :disabled="acting === u.id"
            >
              {{ acting === u.id ? '...' : (u.role === 'admin' ? '降为普通' : '升为管理员') }}
            </button>
            <button
              v-if="u.id !== currentUserId"
              class="btn btn-xs btn-danger-text"
              @click="confirmDelete(u)"
              :disabled="acting === u.id"
            >
              删除
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <UiEmpty v-if="!loading && users.length === 0" text="暂无用户数据" />

    <!-- 删除确认弹窗 -->
    <div v-if="deleteTarget" class="modal-mask" @click.self="deleteTarget = null">
      <div class="modal-card">
        <h4>确认删除</h4>
        <p>确定要删除用户 <strong>{{ deleteTarget.username }}</strong> 吗？此操作不可撤销。</p>
        <div class="modal-actions">
          <button class="btn btn-sm btn-ghost" @click="deleteTarget = null">取消</button>
          <button class="btn btn-sm btn-danger" @click="doDelete" :disabled="acting">确认删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import api from '../api'
import { authStore } from '../stores/auth'
import { useFeedback } from '../composables/useFeedback'

const { tip, ask } = useFeedback()

const users = ref([])
const loading = ref(true)
const acting = ref(null)
const deleteTarget = ref(null)
const inviteCodeInput = ref('')
const savingInvite = ref(false)
const inviteMsg = ref('')

const currentUserId = computed(() => authStore.user?.id)

onMounted(async () => {
  await Promise.all([fetchUsers(), fetchInviteCode()])
})

async function fetchUsers() {
  loading.value = true
  try {
    const r = await api.get('/auth/users')
    if (r.success) users.value = r.data?.items || r.data
  } catch (e) {
    console.error('加载用户列表失败', e)
  } finally {
    loading.value = false
  }
}

async function fetchInviteCode() {
  try {
    const r = await api.get('/auth/invite-code')
    if (r.success) inviteCodeInput.value = r.data.invite_code
  } catch (e) { console.error('加载邀请码失败:', e); tip('邀请码加载失败，请稍后重试') }
}

async function saveInviteCode() {
  if ((inviteCodeInput.value || '').trim().length < 4) { tip('邀请码至少 4 位'); return }
  savingInvite.value = true
  inviteMsg.value = ''
  try {
    const r = await api.put('/auth/invite-code', { invite_code: inviteCodeInput.value })
    inviteMsg.value = r.message || '已更新'
  } catch (e) {
    inviteMsg.value = '更新失败'
  } finally {
    savingInvite.value = false
    setTimeout(() => { inviteMsg.value = '' }, 2000)
  }
}

async function toggleRole(user) {
  acting.value = user.id
  const newRole = user.role === 'admin' ? 'user' : 'admin'
  try {
    const r = await api.put(`/auth/users/${user.id}/role`, { role: newRole })
    if (r.success) {
      user.role = newRole
    } else {
      tip(r.message)
    }
  } catch (e) {
    tip('操作失败')
  } finally {
    acting.value = null
  }
}

function confirmDelete(user) {
  deleteTarget.value = user
}

async function doDelete() {
  if (!deleteTarget.value) return
  acting.value = deleteTarget.value.id
  try {
    const r = await api.delete(`/auth/users/${deleteTarget.value.id}`)
    if (r.success) {
      users.value = users.value.filter(u => u.id !== deleteTarget.value.id)
      deleteTarget.value = null
    } else {
      tip(r.message)
    }
  } catch (e) {
    tip('删除失败')
  } finally {
    acting.value = null
  }
}

function formatDate(d) {
  if (!d) return '-'
  return d.slice(0, 19).replace('T', ' ')
}
</script>

<style scoped>
.page-container { max-width: 900px; margin: 0 auto; padding: 32px 24px; }
.page-top {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin-bottom: 24px; flex-wrap: wrap; gap: 16px;
}
.page-top h1 { font-size: 19px; margin: 0; }

.invite-section {
  background: #f8fafc; border: 1px solid #e2e8f0;
  border-radius: 8px; padding: 12px 16px;
}
.invite-label { font-size: 11px; color: var(--text-secondary); display: block; margin-bottom: 6px; }
.invite-controls { display: flex; gap: 8px; align-items: center; }
.feedback-msg { font-size: 11px; color: #16a34a; margin-top: 4px; }

.loading-text { text-align: center; color: var(--text-secondary); padding: 40px; }
.empty-msg { text-align: center; color: var(--text-light); padding: 40px; }

.user-table {
  width: 100%; border-collapse: collapse; background: #fff;
  border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.user-table th, .user-table td {
  padding: 12px 16px; text-align: left; font-size: 12px; border-bottom: 1px solid #f1f5f9;
}
.user-table th { background: #f8fafc; font-weight: 600; color: var(--text-secondary); font-size: 11px; }
.user-table tr:last-child td { border-bottom: none; }
.row-current td { background: #f0f9ff; }

.tag-you { font-size: 10px; background: #3b82f6; color: #fff; padding: 1px 6px; border-radius: 3px; margin-left: 6px; }

.role-tag { font-size: 11px; padding: 2px 10px; border-radius: 10px; font-weight: 500; }
.role-admin { background: #d1fae5; color: #065f46; }
.role-user { background: #e2e8f0; color: #475569; }

.action-cell { display: flex; gap: 8px; }

.btn-xs { padding: 4px 12px; font-size: 11px; border-radius: 4px; }
.btn-outline { border: 1px solid #cbd5e1; color: #334155; background: #fff; cursor: pointer; }
.btn-outline:hover { border-color: #3b82f6; color: #3b82f6; }
.btn-danger-text { border: none; color: #dc2626; background: transparent; cursor: pointer; font-size: 11px; }
.btn-danger-text:hover { text-decoration: underline; }
.btn-danger { background: #dc2626; color: #fff; border: none; cursor: pointer; }
.btn-danger:hover { background: #b91c1c; }

.modal-mask {
  position: fixed; inset: 0; background: rgba(0,0,0,0.35);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal-card {
  background: #fff; border-radius: 10px; padding: 24px; width: 360px;
  box-shadow: 0 8px 30px rgba(0,0,0,0.15);
}
.modal-card h4 { margin: 0 0 12px; font-size: 14px; }
.modal-card p { font-size: 12px; color: var(--text-secondary); margin: 0 0 20px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; }
.btn-sm { padding: 8px 16px; font-size: 11px; border-radius: 6px; cursor: pointer; }
.btn-ghost { border: 1px solid #cbd5e1; background: #fff; color: #334155; }
.btn-ghost:hover { background: #f1f5f9; }
.btn-primary { background: #3b82f6; color: #fff; border: none; }
.btn-primary:hover { background: #2563eb; }
.input-sm { padding: 6px 10px; font-size: 11px; }
</style>
