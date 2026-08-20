import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '../views/HomePage.vue'

const routes = [
  { path: '/', name: 'home', component: HomePage },
  { path: '/graph', name: 'graph', component: () => import('../views/GraphPage.vue') },
  { path: '/graph/:nodeId', name: 'graphNode', component: () => import('../views/GraphPage.vue') },
  { path: '/knowledge', name: 'knowledge', component: () => import('../views/KnowledgeList.vue') },
  { path: '/knowledge/:id', name: 'knowledgeDetail', component: () => import('../views/KnowledgeDetail.vue') },
  { path: '/login', name: 'login', component: () => import('../views/LoginPage.vue') },
  { path: '/stats', name: 'stats', component: () => import('../views/StatsPage.vue') },
  { path: '/graph-management', name: 'graphManagement', component: () => import('../views/GraphManagement.vue') },
  { path: '/overview', name: 'overview', component: () => import('../views/OverviewPage.vue') },
  { path: '/users', name: 'users', component: () => import('../views/UserManagement.vue') },
  { path: '/logs', name: 'logs', component: () => import('../views/LogPage.vue') },
  { path: '/questions', name: 'questions', component: () => import('../views/QuestionBank.vue') },
  { path: '/class-tasks', name: 'classTasks', component: () => import('../views/ClassTasks.vue') },
  { path: '/classes', name: 'classes', component: () => import('../views/ClassList.vue') },
  { path: '/classes/:id', name: 'classDetail', component: () => import('../views/ClassDetail.vue') },
  { path: '/exams', name: 'exams', component: () => import('../views/ExamCenter.vue') },
  { path: '/exams/edit', name: 'examEdit', component: () => import('../views/ExamEdit.vue') },
  { path: '/exams/:eid/doing', name: 'examDoing', component: () => import('../views/ExamDoing.vue') },
  { path: '/exams/:eid/review', name: 'examReview', component: () => import('../views/ExamReview.vue') },
  { path: '/exams/:eid/result', name: 'examResult', component: () => import('../views/ExamResult.vue') },
  { path: '/statistics', name: 'statistics', component: () => import('../views/StatisticsPage.vue') },
  { path: '/learning-path', name: 'learningPath', component: () => import('../views/LearningPath.vue') },
  { path: '/resources', name: 'resources', component: () => import('../views/ResourceManage.vue') },
  { path: '/llm-settings', name: 'llmSettings', component: () => import('../views/LLMSettings.vue') },
  { path: '/audit-log', name: 'auditLog', component: () => import('../views/AuditLog.vue') },
  { path: '/ai-practice', name: 'aiPractice', component: () => import('../views/AIPractice.vue') },
  { path: '/practice', name: 'practice', component: () => import('../views/PracticeCenter.vue') },
  { path: '/practice/history', name: 'practiceHistory', component: () => import('../views/PracticeHistory.vue') },
  { path: '/practice/:qid', name: 'practiceDoing', component: () => import('../views/PracticeDoing.vue') },
  { path: '/code-solution/:id', name: 'codeSolution', component: () => import('../views/CodeSolution.vue') },
  { path: '/user/:id', name: 'userProfile', component: () => import('../views/UserProfile.vue') },
  { path: '/notifications', name: 'notifications', component: () => import('../views/NotificationCenter.vue') },
  { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('../views/NotFound.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.hash) return { el: to.hash, behavior: 'smooth' }
    return { top: 0 }
  }
})

router.beforeEach(async (to, from, next) => {
  const publicPages = ['/login']

  // 静态导入会导致循环依赖，改用动态导入
  const { authStore: as } = await import('../stores/auth.js')

  // 首次验证：调用 /auth/me 检查登录态
  if (!as.isLoggedIn) {
    const ok = await as.fetchMe()
    if (!ok && !publicPages.includes(to.path)) {
      next('/login')
      return
    }
    if (ok && to.path === '/login') {
      next('/')
      return
    }
  }

  // 统一权限源：按路径所需角色校验（单一来源，见 src/config/permissions.js）
  const { pageRequiresRole } = await import('../config/permissions.js')
  const required = pageRequiresRole(to.path)
  if (required === 'dev' && !as.isDev) {
    next('/')
    return
  }
  if (required === 'admin' && !as.isAdmin) {
    next('/')
    return
  }

  next()
})

export default router
