<template>
  <div class="ui-card" :class="{ 'ui-card-padless': !pad }">
    <div v-if="title || $slots.header" class="ui-card-header">
      <slot name="header">
        <h3 class="ui-card-title">{{ title }}</h3>
      </slot>
      <div v-if="$slots.extra" class="ui-card-extra"><slot name="extra" /></div>
    </div>
    <div class="ui-card-body"><slot /></div>
    <div v-if="$slots.footer" class="ui-card-footer"><slot name="footer" /></div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  pad: { type: Boolean, default: true },
})
</script>

<style scoped>
.ui-card {
  background: var(--bg-primary);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
  padding: 24px;
}
.ui-card-padless { padding: 0; }
.ui-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.ui-card-title { font-size: 14px; font-weight: 600; margin: 0; }
.ui-card-extra { flex-shrink: 0; }
.ui-card-footer {
  border-top: 1px solid var(--border-color);
  margin-top: 16px;
  padding-top: 16px;
}
</style>
