import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true
})

// 上报前端错误到后台日志
function reportError(module, detail, errorType = '', traceback = '', endpoint = '') {
  try {
    // 用 navigator.sendBeacon 避免阻塞页面卸载
    const body = JSON.stringify({ module, detail, error_type: errorType, traceback, endpoint })
    if (navigator.sendBeacon) {
      navigator.sendBeacon('/api/v1/logs/error', new Blob([body], { type: 'application/json' }))
    } else {
      axios.post('/api/v1/logs/error', { module, detail, error_type: errorType, traceback, endpoint }).catch(() => {})
    }
  } catch (_) { /* 静默处理 */ }
}

// 全局 JS 错误捕获
window.addEventListener('error', (e) => {
  const trace = e.error ? e.error.stack || '' : ''
  reportError('frontend', `${e.filename}:${e.lineno}:${e.colno} ${e.message}`, 'JS Error', trace, window.location.pathname)
})
window.addEventListener('unhandledrejection', (e) => {
  const msg = e.reason ? (e.reason.message || String(e.reason)) : 'Unknown Promise rejection'
  const trace = e.reason && e.reason.stack ? e.reason.stack : ''
  reportError('frontend', msg, 'UnhandledRejection', trace, window.location.pathname)
})

// 请求拦截器
api.interceptors.request.use(
  config => {
    config._retryCount = config._retryCount || 0
    config._startTime = Date.now()
    return config
  },
  error => Promise.reject(error)
)

// 响应拦截器 — 统一错误处理 + 自动重试 + 错误上报
api.interceptors.response.use(
  response => response.data,
  async error => {
    const config = error.config
    const method = (config?.method || 'get').toLowerCase()
    // 仅对幂等 GET 请求自动重试 1 次；POST/PUT/DELETE 不自动重试，避免重复提交的副作用
    if (config && method === 'get' && config._retryCount < 1 &&
        (!error.response || [502, 503, 504].includes(error.response.status))) {
      config._retryCount++
      await new Promise(r => setTimeout(r, 800))
      return api(config)
    }
    if (error.response) {
      const { status, data } = error.response
      if (status === 401) {
        localStorage.removeItem('kekg_user')
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      }
      // 上报 5xx 错误
      if (status >= 500) {
        reportError('api', `[${status}] ${config?.url || ''}`, 'HTTPError', data?.message || '', config?.url || '')
      }
      return Promise.reject(data || { message: '请求失败' })
    }
    // 网络错误上报
    reportError('api', `Network Error: ${config?.url || ''}`, 'NetworkError', error.message || '', config?.url || '')
    return Promise.reject({ message: '网络错误，请检查连接' })
  }
)

export default api
