<template>
  <button
    class="ui-btn"
    :class="[`ui-btn-${variant}`, `ui-btn-${size}`, { 'ui-btn-block': block, 'ui-btn-loading': loading }]"
    :disabled="disabled || loading"
    :type="nativeType"
    @click="handleClick"
  >
    <span v-if="loading" class="ui-btn-spinner" aria-hidden="true"></span>
    <slot>{{ text }}</slot>
  </button>
</template>

<script setup>
const props = defineProps({
  variant: { type: String, default: 'primary' },   // primary | secondary | danger | ghost | text
  size: { type: String, default: 'md' },           // sm | md | lg
  block: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  nativeType: { type: String, default: 'button' }, // button | submit
  text: { type: String, default: '' },
})

const emit = defineEmits(['click'])

function handleClick(e) {
  if (props.disabled || props.loading) return
  emit('click', e)
}
</script>

<style scoped>
.ui-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 20px;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  font-family: var(--font-family);
  cursor: pointer;
  transition: all 0.2s;
  line-height: 1.4;
  text-decoration: none;
}
.ui-btn:disabled { opacity: 0.55; cursor: not-allowed; transform: none !important; }
.ui-btn-block { width: 100%; }

/* 变体 */
.ui-btn-primary { background: var(--accent-blue); color: #fff; }
.ui-btn-primary:hover:not(:disabled) { background: var(--accent-blue-dark); transform: translateY(-1px); }
.ui-btn-secondary { background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border-color); }
.ui-btn-secondary:hover:not(:disabled) { background: var(--border-color); }
.ui-btn-danger { background: var(--color-danger); color: #fff; }
.ui-btn-danger:hover:not(:disabled) { background: #dc2626; }
.ui-btn-ghost { background: transparent; color: var(--text-secondary); border: 1px solid var(--border-color); }
.ui-btn-ghost:hover:not(:disabled) { background: var(--bg-secondary); color: var(--text-primary); }
.ui-btn-text { background: transparent; color: var(--accent-blue); padding: 4px 8px; }
.ui-btn-text:hover:not(:disabled) { background: var(--color-info-bg); }

/* 尺寸 */
.ui-btn-sm { padding: 6px 14px; font-size: 11px; }
.ui-btn-lg { padding: 14px 28px; font-size: 14px; }

/* 加载态 */
.ui-btn-spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: ui-btn-spin 0.7s linear infinite;
  flex-shrink: 0;
}
.ui-btn-secondary .ui-btn-spinner, .ui-btn-ghost .ui-btn-spinner, .ui-btn-text .ui-btn-spinner {
  border-color: rgba(100, 116, 139, 0.35);
  border-top-color: var(--text-secondary);
}
@keyframes ui-btn-spin { to { transform: rotate(360deg); } }
</style>
