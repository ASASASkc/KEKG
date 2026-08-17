<template>
  <div class="ui-loading">
    <span class="ui-loading-spinner" aria-hidden="true"></span>
    <span v-if="text" class="ui-loading-text">{{ text }}</span>
    <slot />
  </div>
</template>

<script setup>
defineProps({
  text: { type: String, default: '加载中...' },
})
</script>

<style scoped>
.ui-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 32px 16px;
  color: var(--text-secondary);
  font-size: 11px;
}
.ui-loading-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border-color);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: ui-loading-spin 0.7s linear infinite;
  flex-shrink: 0;
}
@keyframes ui-loading-spin { to { transform: rotate(360deg); } }
</style>
