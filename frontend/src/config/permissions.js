// 统一权限配置源
// 路由守卫（router/index.js）与导航显隐均以此为唯一依据，避免口径不一致。
// 注意：/statistics 对学生开放个人统计、管理员可见班级统计，故不属于 adminOnly。

// 访问控制：各角色专属路由
export const routeAccess = {
  // 开发者专属
  dev: ['/users', '/logs', '/llm-settings', '/audit-log'],
  // 管理员专属
  admin: ['/graph-management', '/questions', '/resources'],
}

/**
 * 返回某路径所需的最低角色：'dev' | 'admin' | 'any'（登录即可）
 */
export function pageRequiresRole(path) {
  if (routeAccess.dev.includes(path)) return 'dev'
  if (routeAccess.admin.includes(path)) return 'admin'
  // 管理员专属（路径模式）：试卷编辑 / 阅卷页面
  if (path === '/exams/edit') return 'admin'
  if (/^\/exams\/\d+\/review$/.test(path)) return 'admin'
  return 'any'
}

/**
 * 判断当前用户是否有权访问某路径
 * @param {object|null} user authStore.user
 * @param {string} path 目标路由路径
 */
export function canAccess(user, path) {
  if (!user) return false
  const required = pageRequiresRole(path)
  if (required === 'any') return true
  const isAdmin = user.role === 'admin'
  const isDev = user.is_dev === 1 || user.is_dev === true
  if (required === 'admin') return isAdmin
  if (required === 'dev') return isDev
  return true
}
