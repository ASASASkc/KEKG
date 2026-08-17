<template>
  <div class="page-container notif-page">
    <div class="notif-header">
      <h1 class="page-title">通知中心</h1>
      <button v-if="items.length" class="btn btn-sm btn-secondary" @click="markAllRead">全部已读</button>
    </div>

    <UiLoading v-if="loading" />
    <UiEmpty v-else-if="items.length === 0" text="暂无通知" />
    <div v-else class="notif-list">
      <div v-for="n in items" :key="n.id" class="notif-item" :class="{ unread: !n.is_read }" @click="openNotif(n)">
        <div class="notif-icon" :class="'icon-' + n.type"></div>
        <div class="notif-main">
          <div class="notif-title-row">
            <span class="notif-badge" :class="'badge-' + n.type">{{ typeLabel(n.type) }}</span>
            <span class="notif-title" :class="{ strong: !n.is_read }">{{ n.title }}</span>
          </div>
          <div v-if="n.content" class="notif-content">{{ n.content }}</div>
          <div class="notif-time">{{ formatTime(n.created_at) }}</div>
        </div>
        <span v-if="!n.is_read" class="notif-dot"></span>
      </div>
    </div>

    <div v-if="totalPages > 1" class="pagination">
      <button class="btn btn-sm" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
      <span class="page-info">{{ page }} / {{ totalPages }}</span>
      <button class="btn btn-sm" :disabled="page >= totalPages" @click="goPage(page + 1)">下一页</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const router = useRouter()
const items = ref([])
const loading = ref(true)
const page = ref(1)
const totalPages = ref(1)

const TYPE_LABELS = {
  exam_publish: '考试发布',
  exam_result: '成绩发布',
  announcement: '班级公告',
  class_removed: '班级变动',
}

function typeLabel(t) {
  return TYPE_LABELS[t] || t
}

function formatTime(t) {
  if (!t) return ''
  return String(t).replace('T', ' ').slice(0, 16)
}

async function load() {
  loading.value = true
  try {
    const res = await api.get(`/notifications?page=${page.value}&page_size=15`)
    if (res.success) {
      items.value = res.data.items || []
      totalPages.value = res.data.total_pages || 1
    }
  } catch (e) {
    console.error('加载通知失败:', e)
  } finally {
    loading.value = false
  }
}

async function markAllRead() {
  try {
    await api.put('/notifications/read-all')
    items.value.forEach(n => { n.is_read = 1 })
  } catch (e) {
    console.error(e)
  }
}

async function openNotif(n) {
  if (!n.is_read) {
    try {
      await api.put(`/notifications/${n.id}/read`)
      n.is_read = 1
    } catch (e) { /* 忽略 */ }
  }
  // 关联跳转
  if (n.related_type === 'exam') {
    router.push('/exams')
  } else if (n.related_type === 'announcement' || n.related_type === 'class') {
    router.push('/classes')
  }
}

function goPage(p) {
  if (p < 1 || p > totalPages.value) return
  page.value = p
  load()
}

onMounted(load)
</script>

<style scoped>
.notif-page { max-width: 820px; margin: 0 auto; padding: 32px 24px; }
.page-title { font-size: 21px; font-weight: 700; margin: 0; color: #1e293b; }
.notif-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.loading, .empty { text-align: center; padding: 60px 20px; color: #94a3b8; }

.notif-list { display: flex; flex-direction: column; gap: 8px; }
.notif-item {
  display: flex; align-items: flex-start; gap: 14px;
  background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px;
  padding: 14px 16px; cursor: pointer; transition: all 0.15s; position: relative;
}
.notif-item:hover { border-color: #93c5fd; box-shadow: 0 2px 8px rgba(59,130,246,0.08); }
.notif-item.unread { background: #f8faff; border-color: #bfdbfe; }
.notif-icon {
  width: 34px; height: 34px; border-radius: 8px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700; color: #fff;
}
.icon-exam_publish { background: #3b82f6; }
.icon-exam_result { background: #10b981; }
.icon-announcement { background: #f59e0b; }
.icon-class_removed { background: #ef4444; }
.notif-main { flex: 1; min-width: 0; }
.notif-title-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.notif-badge {
  font-size: 10px; padding: 1px 8px; border-radius: 4px; font-weight: 600; flex-shrink: 0;
}
.badge-exam_publish { background: #dbeafe; color: #2563eb; }
.badge-exam_result { background: #d1fae5; color: #047857; }
.badge-announcement { background: #fef3c7; color: #b45309; }
.badge-class_removed { background: #fee2e2; color: #b91c1c; }
.notif-title { font-size: 12px; color: #334155; }
.notif-title.strong { font-weight: 600; color: #1e293b; }
.notif-content { font-size: 11px; color: #64748b; margin-bottom: 4px; line-height: 1.5; }
.notif-time { font-size: 10px; color: #94a3b8; }
.notif-dot {
  width: 8px; height: 8px; border-radius: 50%; background: #ef4444;
  flex-shrink: 0; margin-top: 6px;
}

.pagination { display: flex; align-items: center; justify-content: center; gap: 12px; margin-top: 20px; }
.page-info { font-size: 11px; color: #64748b; }
</style>
