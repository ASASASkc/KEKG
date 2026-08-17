<template>
  <div id="app-root">
    <AppHeader v-if="!hasError" />
    <main class="main-content">
      <div v-if="hasError" class="error-boundary">
        <h2>页面加载异常</h2>
        <p>{{ errorMessage }}</p>
        <button class="btn btn-primary" @click="reloadPage">刷新页面</button>
      </div>
      <router-view v-else :key="$route.fullPath" />
    </main>
    <AppFooter v-if="!hasError" />

    <!-- 全局提示 / 确认弹窗（M5-A useFeedback） -->
    <UiModal v-model="tipVisible" title="提示" :show-footer="false" @cancel="closeTip">
      <p style="margin:0">{{ tipMsg }}</p>
    </UiModal>
    <UiModal v-model="confirmVisible" title="确认操作" @cancel="closeConfirm" @confirm="doConfirm">
      <p style="margin:0">{{ confirmMsg }}</p>
    </UiModal>
  </div>
</template>

<script setup>
import { ref, onErrorCaptured } from 'vue'
import AppHeader from './components/AppHeader.vue'
import AppFooter from './components/AppFooter.vue'
import { useFeedback } from './composables/useFeedback'

const hasError = ref(false)
const errorMessage = ref('')

const { tipVisible, tipMsg, confirmVisible, confirmMsg, closeTip, closeConfirm, doConfirm } = useFeedback()

onErrorCaptured((err, instance, info) => {
  console.error('Vue error captured:', err, info)
  hasError.value = true
  errorMessage.value = err?.message || '未知错误'
  return false // 阻止错误继续冒泡
})

function reloadPage() {
  window.location.reload()
}
</script>

<style scoped>
#app-root {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: #f8fafc;
}
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.error-boundary {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 24px;
  text-align: center;
}
.error-boundary h2 { font-size: 18px; color: #dc2626; margin: 0 0 8px; }
.error-boundary p { font-size: 12px; color: var(--text-secondary); margin: 0 0 20px; }
.btn { padding: 8px 16px; font-size: 11px; border-radius: 6px; cursor: pointer; border: 1px solid transparent; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover { background: #2563eb; }
</style>
