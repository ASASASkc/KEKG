<template>
  <div ref="el" class="base-chart" :style="{ height }"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  // ECharts option（深度 watch，变化时自动刷新）
  option: { type: Object, default: () => ({}) },
  // 容器高度
  height: { type: String, default: '240px' }
})

const el = ref(null)
let chart = null
let resizeObserver = null

function render() {
  if (!el.value) return
  // rAF 确保浏览器完成布局后再初始化，规避容器 0 尺寸导致的"暂无数据"
  requestAnimationFrame(() => {
    if (!el.value) return
    if (!chart) chart = echarts.init(el.value)
    chart.setOption(props.option, true)
    chart.resize()
  })
}

function handleResize() {
  if (chart) chart.resize()
}

onMounted(() => {
  render()
  if (window.ResizeObserver) {
    resizeObserver = new ResizeObserver(handleResize)
    resizeObserver.observe(el.value)
  } else {
    window.addEventListener('resize', handleResize)
  }
})

watch(() => props.option, render, { deep: true })

onBeforeUnmount(() => {
  if (resizeObserver) resizeObserver.disconnect()
  else window.removeEventListener('resize', handleResize)
  if (chart) { chart.dispose(); chart = null }
})
</script>

<style scoped>
.base-chart { width: 100%; }
</style>
