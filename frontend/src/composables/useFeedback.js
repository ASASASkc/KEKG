// 全局反馈工具：tip 提示 / ask 确认
// 状态为模块级单例，App.vue 中挂载全局 Modal，各页面调用本函数弹出
import { ref } from 'vue'

const tipVisible = ref(false)
const tipMsg = ref('')
const confirmVisible = ref(false)
const confirmMsg = ref('')
const confirmAction = ref(null)

export function useFeedback() {
  function tip(msg) {
    tipMsg.value = msg
    tipVisible.value = true
  }

  function ask(msg, fn) {
    confirmMsg.value = msg
    confirmAction.value = fn
    confirmVisible.value = true
  }

  function closeTip() {
    tipVisible.value = false
  }

  function closeConfirm() {
    confirmVisible.value = false
    confirmAction.value = null
  }

  function doConfirm() {
    confirmVisible.value = false
    const fn = confirmAction.value
    confirmAction.value = null
    if (typeof fn === 'function') fn()
  }

  return {
    tipVisible, tipMsg, confirmVisible, confirmMsg,
    tip, ask, closeTip, closeConfirm, doConfirm,
  }
}
