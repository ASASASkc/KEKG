<template>
  <div class="page-container">
    <div class="page-top">
      <a href="javascript:void(0)" class="back-link" @click="backToBank">&larr; 返回题库</a>
      <h1>我的提交记录</h1>
      <p class="page-subtitle">历次刷题作答时间线，可回看答案与用时</p>
    </div>

    <UiLoading v-if="loading" />

    <template v-else>
      <div v-if="items.length" class="hist-list">
        <div v-for="h in items" :key="h.id" class="hist-item">
          <div class="hist-head">
            <span class="type-tag" :class="'type-' + h.q_type">{{ typeLabel(h.q_type) }}</span>
            <router-link :to="'/practice/' + h.question_id" class="hist-title" :title="h.question_title">
              {{ h.question_title }}
            </router-link>
            <span class="hist-badge" :class="h.is_correct === 1 ? 'badge-correct' : (h.is_correct === 0 ? 'badge-wrong' : 'badge-sub')">
              {{ h.is_correct === 1 ? '✓ 正确' : (h.is_correct === 0 ? '✗ 错误' : '已提交') }}
            </span>
          </div>
          <div class="hist-meta">
            <span>⏱ {{ fmtElapsed(h.elapsed_seconds) }}</span>
            <span>{{ fmtTime(h.created_at) }}</span>
          </div>
          <div class="hist-answer">
            <span class="hist-answer-label">我的答案：</span>
            <span class="hist-answer-text">{{ h.user_answer || '（未作答）' }}</span>
          </div>
        </div>
      </div>
      <UiEmpty v-else text="暂无提交记录，快去题库刷题吧" />

      <!-- 分页 -->
      <div class="pagination" v-if="totalPages > 1">
        <button class="btn btn-xs btn-outline" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <span class="page-info">{{ page }} / {{ totalPages }}</span>
        <button class="btn btn-xs btn-outline" :disabled="page >= totalPages" @click="goPage(page + 1)">下一页</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { useFeedback } from '../composables/useFeedback'

const router = useRouter()
const { tip } = useFeedback()

// 返回题库：优先回退到来源页，无历史则进入练习中心
function backToBank() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/ai-practice')
  }
}

const loading = ref(true)
const items = ref([])
const page = ref(1)
const pageSize = 20
const totalPages = ref(1)

const TYPE_MAP = { choice: '选择', judge: '判断', fill: '填空', subjective: '主观', code: '编程' }
function typeLabel(t) { return TYPE_MAP[t] || t }

function fmtElapsed(sec) {
  const s = Number(sec) || 0
  if (s < 60) return `${s} 秒`
  const m = Math.floor(s / 60)
  const r = s % 60
  return r ? `${m}分${r}秒` : `${m} 分钟`
}

function fmtTime(ts) {
  if (!ts) return ''
  return String(ts).replace('T', ' ').slice(0, 19)
}

onMounted(load)

async function load() {
  loading.value = true
  try {
    const r = await api.get('/practice/history', { params: { page: page.value, page_size: pageSize } })
    if (r.success) {
      items.value = r.data.items || []
      totalPages.value = r.data.total_pages || 1
    }
  } catch (e) { console.error(e); tip('练习记录加载失败，请稍后重试') }
  finally { loading.value = false }
}

function goPage(p) {
  page.value = p
  load()
}
</script>

<style scoped>
.page-container { max-width: 860px; margin: 0 auto; padding: 32px 24px; }
.page-top h1 { font-size: 22px; margin: 0 0 4px; }
.page-subtitle { font-size: 13px; color: var(--text-secondary); margin: 0 0 20px; }
.back-link { font-size: 13px; color: var(--accent-blue); text-decoration: none; display: inline-block; margin-bottom: 8px; }
.back-link:hover { text-decoration: underline; }

.hist-list { display: flex; flex-direction: column; gap: 10px; }
.hist-item {
  border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 16px;
  background: #fff; transition: border-color 0.15s;
}
.hist-item:hover { border-color: #93c5fd; }
.hist-head { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.hist-title {
  flex: 1; font-size: 14px; font-weight: 500; color: #1e293b;
  text-decoration: none; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.hist-title:hover { color: #3b82f6; text-decoration: underline; }
.hist-badge { font-size: 11px; padding: 2px 10px; border-radius: 4px; font-weight: 600; flex-shrink: 0; }
.badge-correct { background: #d1fae5; color: #065f46; }
.badge-wrong { background: #fee2e2; color: #991b1b; }
.badge-sub { background: #e0e7ff; color: #4338ca; }
.hist-meta { display: flex; gap: 16px; font-size: 12px; color: #94a3b8; margin-bottom: 6px; }
.hist-answer { font-size: 13px; color: #475569; display: flex; gap: 6px; }
.hist-answer-label { color: #94a3b8; flex-shrink: 0; }
.hist-answer-text { word-break: break-all; }

.type-tag { font-size: 11px; padding: 1px 7px; border-radius: 3px; font-weight: 500; flex-shrink: 0; }
.type-choice { background: #dbeafe; color: #1e40af; }
.type-judge { background: #d1fae5; color: #065f46; }
.type-fill { background: #fef3c7; color: #92400e; }
.type-subjective { background: #ede9fe; color: #5b21b6; }
.type-code { background: #fee2e2; color: #991b1b; }

.pagination { display: flex; align-items: center; justify-content: center; gap: 12px; margin-top: 20px; }
.page-info { font-size: 13px; color: var(--text-secondary); }
.btn { padding: 6px 14px; font-size: 12px; border-radius: 6px; cursor: pointer; border: 1px solid transparent; text-decoration: none; display: inline-block; }
.btn-outline { border-color: #cbd5e1; color: #334155; background: #fff; }
.btn-outline:hover { border-color: #3b82f6; color: #3b82f6; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
