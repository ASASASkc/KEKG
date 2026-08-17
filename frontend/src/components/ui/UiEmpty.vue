<template>
  <div class="ui-empty">
    <div class="ui-empty-icon"><slot name="icon"><span class="ui-empty-emoji">{{ icon }}</span></slot></div>
    <p class="ui-empty-text">{{ text }}</p>
    <div v-if="$slots.default" class="ui-empty-actions"><slot /></div>
  </div>
</template>

<script setup>
defineProps({
  text: { type: String, default: '暂无数据' },
  icon: { type: String, default: '📭' },
})
</script>

<style scoped>
.ui-empty {
  text-align: center;
  padding: 40px 24px;
}
.ui-empty-icon { font-size: 35px; line-height: 1; margin-bottom: 12px; }
.ui-empty-emoji { display: inline-block; }
.ui-empty-text { font-size: 11px; color: var(--text-light); margin: 0; }
.ui-empty-actions { margin-top: 16px; }
</style>
