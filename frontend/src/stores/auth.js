import { reactive } from 'vue'

function safeParseJSON(str, fallback = null) {
  try { return JSON.parse(str) } catch { return fallback }
}

export const authStore = reactive({
  user: safeParseJSON(localStorage.getItem('kekg_user') || 'null'),

  get isLoggedIn() {
    return !!this.user
  },

  get isAdmin() {
    return this.user?.role === 'admin'
  },

  get isDev() {
    return this.user?.is_dev === 1 || this.user?.is_dev === true
  },

  setUser(user) {
    this.user = user
    if (user) {
      localStorage.setItem('kekg_user', JSON.stringify(user))
    } else {
      localStorage.removeItem('kekg_user')
    }
  },

  async fetchMe() {
    try {
      const api = (await import('../api/index.js')).default
      const r = await api.get('/auth/me')
      if (r.success) {
        this.setUser(r.data)
        return true
      }
    } catch { /* token 无效即未登录 */ }
    this.setUser(null)
    return false
  },

  async logout() {
    try {
      const api = (await import('../api/index.js')).default
      await api.post('/auth/logout')
    } catch { /* 忽略 */ }
    this.setUser(null)
  }
})
