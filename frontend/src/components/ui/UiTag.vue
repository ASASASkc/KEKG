<template>
  <span class="ui-tag" :class="[`ui-tag-${type}`, { 'ui-tag-sm': size === 'sm' }]">
    <slot>{{ text }}</slot>
  </span>
</template>

<script setup>
defineProps({
  type: { type: String, default: 'neutral' }, // success | danger | warning | info | neutral
  size: { type: String, default: 'md' },      // sm | md
  text: { type: String, default: '' },
})
</script>

<style scoped>
.ui-tag {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 500;
  padding: 2px 10px;
  border-radius: 4px;
  line-height: 1.6;
}
.ui-tag-sm { font-size: 10px; padding: 1px 8px; }
.ui-tag-success { background: var(--color-success-bg); color: var(--color-success-text); }
.ui-tag-danger { background: var(--color-danger-bg); color: var(--color-danger-text); }
.ui-tag-warning { background: var(--color-warning-bg); color: var(--color-warning-text); }
.ui-tag-info { background: var(--color-info-bg); color: var(--color-info-text); }
.ui-tag-neutral { background: var(--color-neutral-bg); color: var(--color-neutral-text); }
</style>
