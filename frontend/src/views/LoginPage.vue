<template>
  <div class="login-page">
    <div class="card login-card">
      <div class="login-header">
        <span class="login-icon">&#9671;</span>
        <h2>{{ isRegister ? '注册' : '登录' }} KEKG</h2>
        <p>知识图谱管理与可视化系统</p>
      </div>

      <!-- 登录表单 -->
      <form v-if="!isRegister" @submit.prevent="doLogin" class="login-form">
        <input v-model="username" class="input" placeholder="用户名" required />
        <input v-model="password" class="input" type="password" placeholder="密码" required style="margin-top: 12px" />
        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
        <button type="submit" class="btn btn-primary login-btn" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>

      <!-- 注册表单 -->
      <form v-else @submit.prevent="doRegister" class="login-form">
        <input v-model="username" class="input" placeholder="用户名（2-50字符）" required />
        <input v-model="password" class="input" type="password" placeholder="密码（至少4位）" required style="margin-top: 12px" />
        <input v-model="email" class="input" placeholder="邮箱（选填）" style="margin-top: 12px" />
        <div class="invite-row" style="margin-top: 12px">
          <input v-model="inviteCode" class="input input-invite" type="text" placeholder="邀请码（选填，填入可注册管理员）" />
        </div>
        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
        <p v-if="successMsg" class="success-msg">{{ successMsg }}</p>
        <button type="submit" class="btn btn-primary login-btn" :disabled="loading">
          {{ loading ? '注册中...' : '注册' }}
        </button>
      </form>

      <p class="login-footer">
        <template v-if="!isRegister">
          首次使用？<a href="#" @click.prevent="switchToRegister">注册账号</a>
        </template>
        <template v-else>
          已有账号？<a href="#" @click.prevent="switchToLogin">返回登录</a>
        </template>
        <br />
        <span class="demo-account">测试账号: admin / admin123</span>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { authStore } from '../stores/auth'
import { useFeedback } from '../composables/useFeedback'

const { tip } = useFeedback()
const router = useRouter()
const username = ref('')
const password = ref('')
const email = ref('')
const inviteCode = ref('')
const isRegister = ref(false)
const loading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

function clearMessages() {
  errorMsg.value = ''
  successMsg.value = ''
}

function switchToRegister() { clearMessages(); isRegister.value = true }
function switchToLogin() { clearMessages(); isRegister.value = false }

async function doLogin() {
  if (!username.value || !password.value) return
  clearMessages()
  loading.value = true
  try {
    const r = await api.post('/auth/login', {
      username: username.value,
      password: password.value
    })
    if (r.success) {
      authStore.setUser(r.data.user)
      router.push('/')
    } else {
      errorMsg.value = r.message || '登录失败'
    }
  } catch (e) {
    errorMsg.value = '网络错误，请检查后端服务'
  } finally {
    loading.value = false
  }
}

async function doRegister() {
  const uname = username.value.trim()
  if (uname.length < 2 || uname.length > 50) { tip('用户名须为 2-50 个字符'); return }
  if (!password.value || password.value.length < 4) { tip('密码至少 4 位'); return }
  clearMessages()
  loading.value = true
  try {
    const r = await api.post('/auth/register', {
      username: username.value,
      password: password.value,
      email: email.value || `${username.value}@kekg.local`,
      invite_code: inviteCode.value
    })
    if (r.success) {
      successMsg.value = '注册成功！请登录'
      setTimeout(() => { switchToLogin() }, 1200)
    } else {
      errorMsg.value = r.message || '注册失败'
    }
  } catch (e) {
    errorMsg.value = '网络错误，请检查后端服务'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
  padding: 24px;
}
.login-card {
  width: 400px;
  padding: 40px;
  text-align: center;
}
.login-header { margin-bottom: 32px; }
.login-icon { font-size: 35px; color: var(--accent-blue); }
.login-header h2 { font-size: 21px; margin: 12px 0 4px; }
.login-header p { font-size: 12px; color: var(--text-secondary); }
.login-form { display: flex; flex-direction: column; gap: 0; }
.login-btn {
  width: 100%;
  margin-top: 20px;
  padding: 12px;
  font-size: 13px;
}
.login-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.error-msg {
  margin-top: 12px; font-size: 11px; color: #dc2626;
  background: #fef2f2; padding: 8px 12px; border-radius: 6px;
}
.success-msg {
  margin-top: 12px; font-size: 11px; color: #16a34a;
  background: #f0fdf4; padding: 8px 12px; border-radius: 6px;
}
.login-footer { margin-top: 24px; font-size: 12px; color: var(--text-secondary); line-height: 1.8; }
.login-footer a { color: var(--accent-blue); font-weight: 500; }
.demo-account { font-size: 11px; color: var(--text-light); background: #f1f5f9; padding: 4px 10px; border-radius: 4px; }
</style>
