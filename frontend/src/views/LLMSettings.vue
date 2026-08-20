<template>
  <div class="llm-settings-page">
    <div class="page-header">
      <h2>AI 大模型配置</h2>
      <p class="desc">配置 DeepSeek 或其他兼容 API，用于 AI 出题、知识点补全等功能</p>
    </div>

    <div class="card">
      <h3>API 连接设置</h3>
      <div class="form-group">
        <label>API Key</label>
        <div class="input-row">
          <input
            v-model="form.api_key"
            type="password"
            :placeholder="maskedKey ? '已配置（' + maskedKey + '），留空不修改' : '请输入 API Key'"
            class="input"
          />
          <button class="btn btn-outline" type="button" @click="toggleShowKey">
            {{ showKey ? '隐藏' : '显示' }}
          </button>
        </div>
      </div>

      <div class="form-group">
        <label>API 地址</label>
        <input
          v-model="form.base_url"
          placeholder="https://api.deepseek.com"
          class="input"
        />
        <span class="hint">DeepSeek 默认地址，也可填其他兼容 OpenAI 格式的 API</span>
      </div>

      <div class="form-group">
        <label>模型名称</label>
        <input
          v-model="form.model"
          placeholder="deepseek-chat"
          class="input"
        />
        <span class="hint">如 deepseek-chat、gpt-4o-mini 等</span>
      </div>

      <div class="actions" v-if="authStore.isAdmin">
        <button class="btn btn-primary" @click="saveConfig" :disabled="saving">
          {{ saving ? '保存中...' : '保存配置' }}
        </button>
        <button class="btn btn-outline" @click="testConnection" :disabled="testing">
          {{ testing ? '测试中...' : '测试连接' }}
        </button>
      </div>

      <div v-if="testResult" class="test-result" :class="{ success: testResult.success, fail: !testResult.success }">
        {{ testResult.success ? '✓' : '✗' }} {{ testResult.message }}
      </div>
    </div>

    <div class="card" v-if="config.has_key && authStore.isAdmin">
      <h3>使用说明</h3>
      <ul>
        <li><strong>管理端 AI 出题</strong>：在考试管理页面选择知识点范围，AI 根据难度自动生成试卷</li>
        <li><strong>节点 AI 练习</strong>：在知识点详情页点击"AI 练习"，针对当前知识点即时出题</li>
        <li><strong>知识点补全</strong>：批量调用 AI 为知识点补全描述、语法案例和示例</li>
        <li><strong>费用说明</strong>：DeepSeek API 按 token 计费，1000 个知识点约 1 元</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api'
import { authStore } from '../stores/auth'
import { useFeedback } from '../composables/useFeedback'

const { tip, ask } = useFeedback()

const config = reactive({ api_key: '', api_key_masked: '', base_url: '', model: '', has_key: false })
const form = reactive({ api_key: '', base_url: '', model: '' })
const showKey = ref(false)
const saving = ref(false)
const testing = ref(false)
const testResult = ref(null)
const maskedKey = ref('')

function toggleShowKey() {
  showKey.value = !showKey.value
  const el = document.querySelector('input[type="password"]')
  if (el) el.type = showKey.value ? 'text' : 'password'
}

async function loadConfig() {
  try {
    const res = await api.get('/llm/config')
    if (res.data.success) {
      Object.assign(config, res.data.data)
      maskedKey.value = res.data.data.api_key_masked
      form.base_url = res.data.data.base_url
      form.model = res.data.data.model
    }
  } catch (e) {
    console.error('加载配置失败', e)
    tip('配置加载失败，请稍后重试')
  }
}

async function saveConfig() {
  if (!form.api_key && !config.has_key) {
    tip('请输入 API Key')
    return
  }
  saving.value = true
  testResult.value = null
  try {
    const res = await api.post('/llm/config', form)
    if (res.data.success) {
      Object.assign(config, res.data.data)
      maskedKey.value = res.data.data.api_key_masked
      form.api_key = ''
      tip('配置已保存')
    } else {
      tip(res.data.message)
    }
  } catch (e) {
    tip('保存失败: ' + (e.response?.data?.message || e.message))
  } finally {
    saving.value = false
  }
}

async function testConnection() {
  testing.value = true
  testResult.value = null
  try {
    const res = await api.post('/llm/test')
    testResult.value = res.data.data
  } catch (e) {
    testResult.value = { success: false, message: '请求失败' }
  } finally {
    testing.value = false
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.llm-settings-page { max-width: 640px; margin: 0 auto; padding: 24px; }
.page-header { margin-bottom: 24px; }
.page-header h2 { font-size: 19px; color: #fff; margin-bottom: 6px; }
.desc { color: #94a3b8; font-size: 12px; }
.card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 24px; margin-bottom: 20px; }
.card h3 { font-size: 14px; color: #e2e8f0; margin-bottom: 20px; }
.form-group { margin-bottom: 16px; }
.form-group label { display: block; color: #cbd5e1; font-size: 12px; margin-bottom: 6px; font-weight: 500; }
.input { width: 100%; padding: 10px 12px; background: #0f172a; border: 1px solid #334155; border-radius: 8px; color: #e2e8f0; font-size: 12px; }
.input:focus { outline: none; border-color: #3b82f6; }
.input-row { display: flex; gap: 8px; }
.input-row .input { flex: 1; }
.hint { display: block; color: #64748b; font-size: 11px; margin-top: 4px; }
.actions { display: flex; gap: 12px; margin-top: 20px; }
.btn { padding: 10px 20px; border-radius: 8px; font-size: 12px; cursor: pointer; border: none; font-weight: 500; }
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-outline { background: transparent; border: 1px solid #475569; color: #cbd5e1; }
.btn-outline:hover:not(:disabled) { border-color: #64748b; }
.test-result { margin-top: 16px; padding: 12px; border-radius: 8px; font-size: 12px; }
.test-result.success { background: rgba(16,185,129,0.15); color: #34d399; }
.test-result.fail { background: rgba(239,68,68,0.15); color: #f87171; }
.card ul { color: #94a3b8; font-size: 12px; line-height: 2; padding-left: 20px; }
.card ul strong { color: #cbd5e1; }
</style>
