<template>
  <header class="app-header">
    <div class="header-inner">
      <router-link to="/" class="logo">
        <span class="logo-icon">&#9671;</span>
        <span class="logo-text">KEKG</span>
      </router-link>
      <nav class="nav-links">
        <!-- 图谱浏览下拉 -->
        <div class="nav-dropdown" @mouseenter="showGraphMenu = true" @mouseleave="showGraphMenu = false">
          <router-link to="/graph" class="nav-link dropdown-trigger">图谱浏览</router-link>
          <div v-if="showGraphMenu" class="dropdown-menu">
            <router-link to="/graph" class="dropdown-item" @click="showGraphMenu = false">
              <span class="item-name">全部知识图谱</span>
              <span class="item-count">{{ totalNodes }} 节点</span>
            </router-link>
            <div class="dropdown-divider"></div>
            <router-link
              v-for="g in visibleGroups" :key="g.label"
              :to="`/graph?label=${encodeURIComponent(g.label)}`"
              class="dropdown-item"
              @click="showGraphMenu = false"
            >
              <span class="item-name">{{ getGroupDisplayName(g.label) }}</span>
              <span class="item-count">{{ g.node_count }} 节点</span>
            </router-link>
            <div class="dropdown-divider"></div>
            <router-link to="/stats" class="dropdown-item" @click="showGraphMenu = false">
              <span class="item-name">图谱数据统计</span>
              <span class="item-count">分析</span>
            </router-link>
          </div>
        </div>
        <router-link to="/knowledge" class="nav-link">知识点管理</router-link>
        <router-link to="/overview" class="nav-link">图谱概览</router-link>
        <router-link v-if="authStore.isAdmin" to="/graph-management" class="nav-link nav-admin">图谱管理</router-link>
        <router-link v-if="authStore.isAdmin" to="/statistics" class="nav-link nav-admin">成绩统计</router-link>
        <router-link v-else-if="authStore.isLoggedIn" to="/statistics" class="nav-link">我的统计</router-link>
        <router-link to="/class-tasks" class="nav-link">班级任务</router-link>
        <router-link v-if="!authStore.isAdmin" to="/learning-path" class="nav-link">学习路径</router-link>
        <router-link v-if="!authStore.isAdmin" to="/ai-practice" class="nav-link nav-practice">练习中心</router-link>

        <router-link v-if="authStore.isAdmin" to="/questions" class="nav-link nav-admin">题库管理</router-link>
        <router-link v-if="authStore.isAdmin" to="/resources" class="nav-link nav-admin">学习资源</router-link>
        <router-link v-if="authStore.isDev" to="/llm-settings" class="nav-link nav-admin">AI设置</router-link>
        <router-link v-if="authStore.isDev" to="/users" class="nav-link nav-admin">用户管理</router-link>
        <router-link v-if="authStore.isDev" to="/logs" class="nav-link nav-admin">操作日志</router-link>
      </nav>
      <button class="hamburger" :class="{ open: menuOpen }" @click="menuOpen = !menuOpen" aria-label="菜单">
        <span></span><span></span><span></span>
      </button>
      <div class="header-right">
        <span class="version-tag">v1.0.0</span>
        <template v-if="authStore.user">
          <router-link to="/notifications" class="notif-link" title="通知中心">
            <svg class="notif-bell" viewBox="0 0 24 24" width="20" height="20" fill="none"
                 stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
              <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
            </svg>
            <span v-if="unreadCount > 0" class="notif-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
          </router-link>
          <router-link :to="`/user/${authStore.user.id}`" class="user-info user-link">{{ authStore.user.username }}</router-link>
          <span v-if="authStore.isAdmin" class="role-badge">管理员</span>
          <button class="btn btn-sm btn-ghost" @click="doLogout">退出</button>
        </template>
        <router-link v-else to="/login" class="btn btn-sm btn-primary">登录</router-link>
      </div>
    </div>

    <!-- 移动端折叠菜单 -->
    <nav v-if="menuOpen" class="mobile-menu">
      <div class="mm-group">
        <button class="mm-link mm-toggle" type="button" @click="graphExpanded = !graphExpanded">
          <span>全部知识图谱</span>
          <span class="mm-arrow" :class="{ open: graphExpanded }">▾</span>
        </button>
        <transition name="mm-slide">
          <div v-show="graphExpanded" class="mm-sub-group">
            <router-link
              v-for="g in visibleGroups" :key="g.label"
              :to="`/graph?label=${encodeURIComponent(g.label)}`"
              class="mm-link mm-sub"
              @click="menuOpen = false"
            >
              {{ getGroupDisplayName(g.label) }}
            </router-link>
            <router-link to="/stats" class="mm-link mm-sub" @click="menuOpen = false">图谱数据统计</router-link>
          </div>
        </transition>
      </div>
      <div class="mm-divider"></div>
      <router-link to="/knowledge" class="mm-link" @click="menuOpen = false">知识点管理</router-link>
      <router-link to="/overview" class="mm-link" @click="menuOpen = false">图谱概览</router-link>
      <router-link v-if="authStore.isAdmin" to="/graph-management" class="mm-link" @click="menuOpen = false">图谱管理</router-link>
      <router-link v-if="authStore.isAdmin" to="/statistics" class="mm-link" @click="menuOpen = false">成绩统计</router-link>
      <router-link v-else-if="authStore.isLoggedIn" to="/statistics" class="mm-link" @click="menuOpen = false">我的统计</router-link>
      <router-link to="/class-tasks" class="mm-link" @click="menuOpen = false">班级任务</router-link>
      <router-link v-if="!authStore.isAdmin" to="/learning-path" class="mm-link" @click="menuOpen = false">学习路径</router-link>
      <router-link v-if="!authStore.isAdmin" to="/ai-practice" class="mm-link" @click="menuOpen = false">练习中心</router-link>
      <router-link v-if="authStore.isAdmin" to="/questions" class="mm-link" @click="menuOpen = false">题库管理</router-link>
      <router-link v-if="authStore.isAdmin" to="/resources" class="mm-link" @click="menuOpen = false">学习资源</router-link>
      <router-link v-if="authStore.isDev" to="/llm-settings" class="mm-link" @click="menuOpen = false">AI设置</router-link>
      <router-link v-if="authStore.isDev" to="/users" class="mm-link" @click="menuOpen = false">用户管理</router-link>
      <router-link v-if="authStore.isDev" to="/logs" class="mm-link" @click="menuOpen = false">操作日志</router-link>
    </nav>
  </header>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { authStore } from '../stores/auth'
import { useFeedback } from '../composables/useFeedback'

const router = useRouter()
const { tip } = useFeedback()
const graphGroups = ref([])
const showGraphMenu = ref(false)
const menuOpen = ref(false)
const graphExpanded = ref(false)
const unreadCount = ref(0)
let notifTimer = null

const GROUP_NAMES = {
  'KnowledgePoint': '系统知识图谱',
  'TextbookKnowledge': '教材知识图谱'
}

const visibleGroups = computed(() => graphGroups.value.filter(g => g.label !== 'Category'))
const totalNodes = computed(() => visibleGroups.value.reduce((s, g) => s + g.node_count, 0))

function getGroupDisplayName(label) {
  return GROUP_NAMES[label] || label
}

async function loadUnread() {
  if (!authStore.user) return
  try {
    const r = await api.get('/notifications/unread-count')
    if (r.success) unreadCount.value = r.data.count || 0
  } catch (e) { /* 忽略 */ }
}

onMounted(async () => {
  try {
    const r = await api.get('/graph-groups')
    if (r.success) graphGroups.value = r.data
  } catch (e) { console.error('加载拓展失败:', e); tip('拓展加载失败，请稍后重试') }
  loadUnread()
  notifTimer = setInterval(loadUnread, 30000)
})

onBeforeUnmount(() => {
  if (notifTimer) clearInterval(notifTimer)
})

async function doLogout() {
  await authStore.logout()
  router.push('/')
}
</script>

<style scoped>
.app-header {
  background: var(--bg-header);
  height: 64px;
  display: flex;
  align-items: center;
  z-index: 100;
  position: sticky;
  top: 0;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.15);
}
.header-inner {
  max-width: 1300px;
  margin: 0 auto;
  width: 100%;
  display: flex;
  align-items: center;
  padding: 0 24px;
  gap: 32px;
}
.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-white);
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.logo-icon { color: var(--accent-blue); font-size: 26px; }
.nav-links { display: flex; gap: 4px; }
.nav-link {
  color: var(--text-light);
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
  text-decoration: none;
  cursor: pointer;
  white-space: nowrap;
  display: inline-block;
}
.nav-link:hover, .nav-link.router-link-active {
  color: var(--text-white);
  background: rgba(255, 255, 255, 0.08);
}
.header-right { margin-left: auto; display: flex; align-items: center; gap: 12px; }
.version-tag { font-size: 10px; color: #94a3b8; font-family: monospace; }
.notif-link { position: relative; display: flex; align-items: center; color: var(--text-light); text-decoration: none; padding: 6px; border-radius: 8px; transition: all 0.2s; }
.notif-link:hover { color: var(--text-white); background: rgba(255,255,255,0.08); }
.notif-bell { display: block; }
.notif-badge {
  position: absolute; top: 0; right: 0;
  min-width: 16px; height: 16px; padding: 0 4px; border-radius: 8px;
  background: #ef4444; color: #fff; font-size: 10px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  transform: translate(30%, -30%);
}
.user-info { color: var(--text-light); font-size: 14px; }
.user-link { text-decoration: none; transition: color 0.2s; }
.user-link:hover { color: var(--accent-blue); }
.role-badge {
  font-size: 11px; padding: 2px 8px; border-radius: 10px;
  background: rgba(16,185,129,0.2); color: #10b981;
  font-weight: 500;
}
.btn-ghost {
  color: var(--text-light);
  border: 1px solid rgba(255,255,255,0.15);
  background: transparent;
}
.btn-ghost:hover { border-color: rgba(255,255,255,0.3); color: var(--text-white); }

/* 下拉菜单 */
.nav-dropdown { position: relative; }
.dropdown-trigger { cursor: pointer; }
.dropdown-menu {
  position: absolute; top: 100%; left: 0;
  min-width: 220px; background: #1e293b;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: var(--radius-md); padding: 6px 0;
  box-shadow: 0 8px 24px rgba(0,0,0,0.3); z-index: 200;
}
.dropdown-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 16px; font-size: 13px; color: var(--text-light);
  transition: background 0.15s;
}
.dropdown-item:hover { background: rgba(255,255,255,0.08); color: var(--text-white); }
.dropdown-item.router-link-active { background: rgba(59,130,246,0.15); color: var(--accent-blue); }
.item-count { font-size: 11px; color: var(--accent-blue); }
.dropdown-divider { height: 1px; background: rgba(255,255,255,0.08); margin: 4px 0; }

/* ── 移动端汉堡折叠菜单（RA） ── */
.hamburger {
  display: none;
  flex-direction: column;
  justify-content: center;
  gap: 5px;
  width: 40px;
  height: 40px;
  padding: 8px;
  background: transparent;
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 8px;
  cursor: pointer;
}
.hamburger span {
  display: block;
  height: 2px;
  width: 100%;
  background: var(--text-light);
  border-radius: 2px;
  transition: all 0.25s;
}
.hamburger.open span:nth-child(1) { transform: translateY(7px) rotate(45deg); }
.hamburger.open span:nth-child(2) { opacity: 0; }
.hamburger.open span:nth-child(3) { transform: translateY(-7px) rotate(-45deg); }

.mobile-menu {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: #0f172a;
  border-top: 1px solid rgba(255,255,255,0.08);
  box-shadow: 0 12px 28px rgba(0,0,0,0.35);
  padding: 8px 12px 16px;
  max-height: calc(100vh - 64px);
  overflow-y: auto;
  z-index: 300;
}
.mm-link {
  display: block;
  padding: 11px 14px;
  font-size: 14px;
  color: var(--text-light);
  text-decoration: none;
  border-radius: 8px;
  transition: background 0.15s, color 0.15s;
}
.mm-link:hover, .mm-link.router-link-active {
  color: var(--text-white);
  background: rgba(255,255,255,0.08);
}
.mm-sub { padding-left: 26px; font-size: 13px; color: var(--text-secondary); }
.mm-divider { height: 1px; background: rgba(255,255,255,0.08); margin: 6px 0; }
/* 图谱分组收放 */
.mm-group { position: relative; }
.mm-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  background: none;
  border: none;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
}
.mm-arrow { font-size: 12px; color: var(--text-secondary); transition: transform 0.2s; }
.mm-arrow.open { transform: rotate(180deg); }
.mm-sub-group { overflow: hidden; }
.mm-slide-enter-active, .mm-slide-leave-active { transition: max-height 0.25s ease, opacity 0.2s ease; }
.mm-slide-enter-from, .mm-slide-leave-to { max-height: 0; opacity: 0; }
.mm-slide-enter-to, .mm-slide-leave-from { max-height: 500px; opacity: 1; }

@media (max-width: 960px) {
  .header-inner { padding: 0 16px; gap: 12px; }
  .nav-links { display: none; }
  .hamburger { display: flex; }
  .version-tag { display: none; }
  .header-right { gap: 8px; }
  .user-info { font-size: 13px; }
}
</style>
