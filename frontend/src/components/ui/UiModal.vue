<template>
  <Teleport to="body">
    <Transition name="ui-modal-fade">
      <div v-if="modelValue" class="ui-modal-mask" @click.self="onMaskClick">
        <div class="ui-modal" :style="widthStyle" role="dialog" aria-modal="true">
          <div class="ui-modal-header">
            <slot name="title"><h3 class="ui-modal-title">{{ title }}</h3></slot>
            <button class="ui-modal-close" @click="close" aria-label="关闭">&times;</button>
          </div>
          <div class="ui-modal-body"><slot /></div>
          <div v-if="showFooter" class="ui-modal-footer">
            <slot name="footer">
              <UiButton variant="secondary" size="sm" @click="close">取消</UiButton>
              <UiButton variant="primary" size="sm" :loading="confirmLoading" @click="confirm">确定</UiButton>
            </slot>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import UiButton from './UiButton.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  width: { type: String, default: '480px' },
  maskClosable: { type: Boolean, default: true },
  showFooter: { type: Boolean, default: true },
  confirmLoading: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const widthStyle = { width: props.width, maxWidth: '92vw' }

function close() {
  emit('update:modelValue', false)
  emit('cancel')
}
function onMaskClick() {
  if (props.maskClosable) close()
}
function confirm() {
  emit('confirm')
}
</script>

<style scoped>
.ui-modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
}
.ui-modal {
  background: var(--bg-primary);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  padding: 24px;
}
.ui-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.ui-modal-title { font-size: 15px; font-weight: 600; margin: 0; }
.ui-modal-close {
  border: none;
  background: transparent;
  font-size: 21px;
  line-height: 1;
  color: var(--text-light);
  cursor: pointer;
  padding: 0 4px;
}
.ui-modal-close:hover { color: var(--text-primary); }
.ui-modal-body { font-size: 12px; color: var(--text-primary); max-height: 65vh; overflow-y: auto; }
.ui-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}

.ui-modal-fade-enter-active, .ui-modal-fade-leave-active { transition: opacity 0.2s ease; }
.ui-modal-fade-enter-active .ui-modal, .ui-modal-fade-leave-active .ui-modal { transition: transform 0.2s ease; }
.ui-modal-fade-enter-from, .ui-modal-fade-leave-to { opacity: 0; }
.ui-modal-fade-enter-from .ui-modal, .ui-modal-fade-leave-to .ui-modal { transform: scale(0.95); }
</style>
