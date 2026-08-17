<template>
  <div class="page-container profile-page">
    <div v-if="loading" class="loading">加载中...</div>
    <template v-else-if="profile">
      <!-- 用户信息卡片 -->
      <div class="profile-header">
        <div class="avatar-placeholder">{{ profile.user.username.charAt(0).toUpperCase() }}</div>
        <div class="profile-info">
          <h1 class="profile-name">{{ profile.user.username }}</h1>
          <div class="profile-meta">
            <span class="meta-item" v-if="profile.user.is_dev">开发者</span>
            <span class="meta-item" v-else-if="profile.user.role === 'admin'">教师</span>
            <span class="meta-item" v-else>学生</span>
            <span class="meta-item">注册于 {{ formatDate(profile.user.created_at) }}</span>
            <span class="meta-item" v-if="isStudentView">活跃 {{ profile.stats.active_days }} 天</span>
          </div>
        </div>
      </div>

      <!-- 教师教学概览（不含个人学习数据） -->
      <template v-if="isTeacherView">
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-value">{{ profile.teaching?.class_count }}</div>
            <div class="stat-label">我管理的班级</div>
            <div class="stat-sub">班级总数</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ profile.teaching?.student_total }}</div>
            <div class="stat-label">班级学生总数</div>
            <div class="stat-sub">去重统计</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ profile.teaching?.exam_count }}</div>
            <div class="stat-label">布置考试数</div>
            <div class="stat-sub">考试与作业</div>
          </div>
        </div>

        <!-- 工作台快捷操作 -->
        <div class="card">
          <h2 class="section-title">教学工作台</h2>
          <div class="work-actions">
            <router-link to="/classes" class="work-item">班级管理</router-link>
            <router-link to="/exams/edit" class="work-item">布置考试</router-link>
            <router-link to="/questions" class="work-item">题库管理</router-link>
            <router-link to="/resources" class="work-item">学习资源</router-link>
            <router-link to="/statistics" class="work-item">成绩统计</router-link>
            <router-link to="/graph-management" class="work-item">图谱管理</router-link>
          </div>
        </div>

        <!-- 待办概览 -->
        <div class="work-todos">
          <div class="work-todo todo-main">
            <div class="todo-value">{{ profile.teaching?.pending_review_count }}</div>
            <div class="todo-label">待批改提交</div>
            <div class="todo-sub">学生已交卷待评分</div>
          </div>
          <div class="work-todo todo-deep">
            <div class="todo-value">{{ profile.teaching?.draft_exam_count }}</div>
            <div class="todo-label">草稿试卷</div>
            <div class="todo-sub">已生成未发布</div>
          </div>
        </div>

        <!-- 最近布置的考试 -->
        <div class="card">
          <h2 class="section-title" style="display:flex;align-items:center;justify-content:space-between;">
            <span>最近布置的考试</span>
            <router-link to="/exams" class="btn-text">全部考试 →</router-link>
          </h2>
          <div v-if="profile.teaching?.recent_exams.length" class="exam-list">
            <router-link v-for="e in profile.teaching?.recent_exams" :key="e.id" :to="`/exams/${e.id}/review`" class="exam-item">
              <div class="exam-title">{{ e.title }}</div>
              <div class="exam-meta">
                <span class="exam-class">{{ e.class_name }}</span>
                <span class="exam-status" :class="'st-' + e.status">{{ examStatusText(e.status) }}</span>
                <span class="exam-date">{{ formatDate(e.created_at) }}</span>
              </div>
            </router-link>
          </div>
          <div v-else class="empty">还没有布置过考试</div>
        </div>

        <!-- 班级管理概览 -->
        <div class="card">
          <h2 class="section-title" style="display:flex;align-items:center;justify-content:space-between;">
            <span>班级管理概览</span>
            <router-link to="/classes" class="btn-text">进入班级管理 →</router-link>
          </h2>
          <div v-if="profile.teaching?.classes.length" class="class-grid">
            <div v-for="c in profile.teaching?.classes" :key="c.id" class="class-item">
              <div class="class-item-head">
                <span class="class-name">{{ c.name }}</span>
                <span class="class-code">{{ c.class_code }}</span>
              </div>
              <div class="class-item-meta">
                <span class="class-students">{{ c.student_count }} 名学生</span>
                <span class="class-date">创建于 {{ formatDate(c.created_at) }}</span>
              </div>
            </div>
          </div>
          <div v-else class="empty">尚未创建班级</div>
        </div>
      </template>

      <!-- 开发者系统概览 -->
      <template v-else-if="isDevView">
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-value">{{ profile.system.user_count }}</div>
            <div class="stat-label">用户总数</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ profile.system.teacher_count }}</div>
            <div class="stat-label">教师账号</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ profile.system.question_count }}</div>
            <div class="stat-label">题库题目</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ profile.system.class_count }}</div>
            <div class="stat-label">班级总数</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ profile.system.exam_count }}</div>
            <div class="stat-label">考试总数</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ profile.system.kp_count }}</div>
            <div class="stat-label">图谱知识点</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ profile.system.log_count }}</div>
            <div class="stat-label">操作日志</div>
          </div>
        </div>
      </template>

      <!-- 学生学习数据 -->
      <template v-else>
      <!-- 数据总览 -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">{{ profile.stats.exam.total }}</div>
          <div class="stat-label">考试次数</div>
          <div class="stat-sub">通过 {{ profile.stats.exam.passed }} 次</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ profile.stats.practice.total }}</div>
          <div class="stat-label">AI练习</div>
          <div class="stat-sub">平均 {{ profile.stats.practice.avg_score }} 分</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ profile.stats.code.total }}</div>
          <div class="stat-label">代码练习</div>
          <div class="stat-sub">平均 {{ profile.stats.code.avg_score }} 分</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ profile.stats.practice_redo.total }}</div>
          <div class="stat-label">独立刷题</div>
          <div class="stat-sub">正确 {{ profile.stats.practice_redo.correct }} 题 · {{ profile.stats.practice_redo.rate }}%</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ profile.stats.streak_days }}</div>
          <div class="stat-label">连续打卡</div>
          <div class="stat-sub">学习计划坚持天数</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ profile.stats.total_activities }}</div>
          <div class="stat-label">总活动次数</div>
          <div class="stat-sub">{{ profile.stats.active_days }} 天活跃</div>
        </div>
      </div>

      <!-- 成就徽章 -->
      <div class="card">
        <h2 class="section-title" style="display:flex;align-items:center;justify-content:space-between;">
          <span>成就徽章</span>
          <span style="font-size:12px;color:#94a3b8;font-weight:400;">当前连续打卡 {{ achievements.streak_days }} 天</span>
        </h2>
        <div class="badge-grid">
          <div v-for="b in achievements.items" :key="b.code" class="badge-item"
               :class="{ locked: !b.unlocked }"
               :title="b.description + (b.unlocked ? ' · 解锁于 ' + formatDate(b.unlocked_at) : ' · 未解锁')">
            <div class="badge-circle" :class="{ 'badge-circle-locked': !b.unlocked }">
              <span class="badge-icon">{{ b.icon }}</span>
            </div>
            <span class="badge-name">{{ b.name }}</span>
            <span class="badge-desc">{{ b.description }}</span>
          </div>
        </div>
      </div>

      <!-- 难度分布 -->
      <div class="card" v-if="profile.stats.difficulty_dist && profile.stats.difficulty_dist.length">
        <h2 class="section-title">独立刷题难度分布</h2>
        <div class="diff-list">
          <div v-for="d in profile.stats.difficulty_dist" :key="d.level" class="diff-item">
            <span class="diff-stars" :title="'难度等级 ' + d.level">{{ '★'.repeat(d.star) }}{{ '☆'.repeat(4 - d.star) }}</span>
            <span class="diff-count">{{ d.total }} 题</span>
            <div class="diff-bar"><div class="diff-bar-fill" :style="{ width: d.rate + '%' }"></div></div>
            <span class="diff-rate">{{ d.rate }}%</span>
          </div>
        </div>
      </div>

      <!-- 热力图网格 -->
      <div class="card">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
          <h2 class="section-title" style="margin:0;">学习热力图（近一年）</h2>
          <div class="heatmap-nav">
            <button class="hm-nav-btn" @click="shiftHeatmap(-90)" :disabled="hmLoading">← 前90天</button>
            <input type="date" class="hm-date-input" :value="heatmapEnd" @change="jumpHeatmap" :disabled="hmLoading" />
            <button class="hm-nav-btn" :disabled="hmLoading || isToday" @click="shiftHeatmap(90)">后90天 →</button>
            <button class="hm-nav-btn" @click="resetHeatmap" :disabled="hmLoading || isToday">回到今天</button>
          </div>
        </div>
        <div class="heatmap-grid">
          <div class="heatmap-container">
            <!-- 月份标签行 -->
            <div class="hm-month-row">
              <div class="hm-wday-spacer"></div>
              <div class="hm-month-labels">
                <span class="hm-month-label" v-for="m in monthLabels" :key="m.label"
                      :style="{ flex: m.span }">{{ m.label }}</span>
              </div>
            </div>
            <!-- 主体：星期标签 + 格子 -->
            <div class="hm-body">
              <div class="hm-wday-col">
                <span class="hm-wday" v-for="d in wdays" :key="d">{{ d }}</span>
              </div>
              <div class="heatmap-weeks">
                <div class="hm-week" v-for="(week, wi) in heatmapWeeks" :key="wi">
                  <div class="hm-day" v-for="day in week" :key="day.date"
                       :title="day.date + ': ' + day.count + '次学习'"
                       :style="{ background: getHeatColor(day.count) }"
                       @click="showDayDetail(day)">
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="heatmap-legend">
            <span>少</span>
            <span class="lg-block" style="background:#f1f5f9"></span>
            <span class="lg-block" style="background:#bbf7d0"></span>
            <span class="lg-block" style="background:#4ade80"></span>
            <span class="lg-block" style="background:#16a34a"></span>
            <span class="lg-block" style="background:#14532d"></span>
            <span>多</span>
          </div>
        </div>
      </div>

      <!-- 日期详情弹窗 -->
      <div class="modal-overlay" v-if="dayDetail.show" @click.self="dayDetail.show = false">
        <div class="day-detail-modal">
          <div class="ddm-header">
            <h3>{{ dayDetail.date }} 活动详情</h3>
            <button class="modal-close-btn" @click="dayDetail.show = false">×</button>
          </div>
          <div v-if="dayDetail.loading" class="ddm-loading">加载中...</div>
          <div v-else-if="dayDetail.items.length === 0" class="empty">当天无活动记录</div>
          <div v-else class="ddm-list">
            <template v-for="group in groupedDayItems" :key="group.type">
              <div class="ddm-group-header">
                <span class="ddm-type-badge" :class="'ddm-' + group.type">{{ typeLabel(group.type) }}</span>
                <span class="ddm-group-count">{{ group.items.length }} 条</span>
              </div>
              <div class="ddm-item" v-for="item in group.items" :key="item.id">
                <span class="ddm-detail">{{ item.detail || item.activity_subtype || '--' }}</span>
                <span class="ddm-score" v-if="item.score !== null && item.score !== undefined">{{ item.score }}分</span>
                <span class="ddm-kp" v-if="item.knowledge_points">{{ item.knowledge_points }}</span>
                <span class="ddm-time">{{ formatTime(item.created_at) }}</span>
                <span class="ddm-note" v-if="item.notes || item.review_comment" :title="item.notes || item.review_comment">📝 {{ item.notes || item.review_comment }}</span>
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- 赛道知识点掌握 -->
      <div class="card" v-if="profile.stats.track_mastery && profile.stats.track_mastery.length">
        <h2 class="section-title">知识点掌握情况（赛道）</h2>
        <div class="track-list">
          <div v-for="track in profile.stats.track_mastery" :key="track.track" class="track-item">
            <div class="track-header" @click="toggleTrack(track.track)">
              <div class="track-name">
                <span class="track-arrow" :class="{ open: openTracks[track.track] }">▸</span>
                <span class="track-label">{{ track.track }}</span>
                <span class="track-progress">{{ track.mastered_kp }}/{{ track.total_system_kp }}</span>
                <span class="track-pct">{{ track.total_system_kp > 0 ? Math.round(track.mastered_kp / track.total_system_kp * 100) : 0 }}%</span>
              </div>
              <div class="track-bar">
                <div class="track-bar-fill"
                     :style="{ width: (track.total_system_kp > 0 ? track.mastered_kp / track.total_system_kp * 100 : 0) + '%' }">
                </div>
              </div>
              <div class="track-detail">正确 {{ track.total_correct }}/{{ track.total_count }} 题</div>
            </div>
            <div class="track-sub" v-show="openTracks[track.track]">
              <div v-if="track.sub_points && track.sub_points.length" class="sub-grid">
                <div v-for="sp in track.sub_points" :key="sp.name" class="sub-kp"
                     :class="{ mastered: sp.mastered }">
                  <span class="sub-kp-dot" :style="{ background: sp.mastered ? '#16a34a' : '#e2e8f0' }"></span>
                  <span class="sub-kp-name">{{ sp.name }}</span>
                  <span class="sub-kp-stat">{{ sp.correct }}/{{ sp.total }}</span>
                </div>
              </div>
              <div v-else class="track-empty">暂无答题数据</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 错题本 -->
      <div class="card">
        <h2 class="section-title" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
          <span>错题本（{{ wrongBook.total }} 道）</span>
          <span v-if="wrongBookLoading" style="font-size:12px;color:#94a3b8;">加载中...</span>
          <button v-else-if="wrongBook.total > 0" class="btn-text" @click="wrongBookOpenAll = !wrongBookOpenAll">
            {{ wrongBookOpenAll ? '折叠全部' : '展开全部' }}
          </button>
        </h2>
        <div v-if="wrongBook.total === 0 && !wrongBookLoading" class="empty">暂无错题，继续保持！</div>
        <div v-else class="wrong-section">
          <div v-for="(items, kpName) in wrongBook.groups" :key="kpName" class="wrong-group">
            <div class="wrong-group-header" @click="toggleWrongGroup(kpName)">
              <span class="wrong-arrow" :class="{ open: openWrongGroups[kpName] }">▸</span>
              <span class="wrong-kp-name">{{ kpName }}</span>
              <span class="wrong-kp-count">{{ items.length }} 题</span>
            </div>
            <div v-if="openWrongGroups[kpName] || wrongBookOpenAll" class="wrong-items">
              <div v-for="item in items" :key="item.id" class="wrong-item">
                <div class="wrong-item-actions">
                  <button class="wrong-redo" @click.stop="openRedo(item)" title="重做此错题">重做</button>
                  <button class="wrong-delete" @click.stop="deleteWrongAnswer(item)" title="删除此错题">×</button>
                </div>
                <div class="wrong-q-title">
                  <span class="wrong-q-type" :class="'qtype-' + item.q_type">{{ typeLabelQ(item.q_type) }}</span>
                  <span>{{ item.q_title }}</span>
                </div>
                <div class="wrong-q-detail">
                  <span class="wrong-label">你的答案：</span>
                  <span class="wrong-ans">{{ item.student_answer || '（未作答）' }}</span>
                  <span class="wrong-label" style="margin-left:12px">正确答案：</span>
                  <span class="wrong-correct">{{ item.q_answer || '--' }}</span>
                  <span class="wrong-score">得分 {{ item.got_score || 0 }}/{{ item.max_score || 0 }}</span>
                </div>
                <div v-if="item.q_analysis" class="wrong-analysis">解析：{{ item.q_analysis }}</div>
                <div class="wrong-meta">来自考试：{{ item.exam_title }}</div>
              </div>
            </div>
          </div>
        </div>
        <UiPagination
          v-if="wrongBook.total > wrongPageSize"
          :page="wrongPage"
          :total="wrongBook.total"
          :page-size="wrongPageSize"
          @update:page="changeWrongPage"
        />
      </div>

      <!-- 最近活动 - 可点击展开 -->
      <div class="card">
        <h2 class="section-title">最近活动</h2>
        <div class="timeline" v-if="profile.stats.recent_activities.length">
          <div v-for="act in profile.stats.recent_activities" :key="act.id || act.created_at"
               class="timeline-item" @click="toggleActivity(act)">
            <div class="timeline-dot" :class="'dot-' + act.activity_type"></div>
            <div class="timeline-content">
              <span class="tl-detail">{{ act.detail || act.activity_subtype || act.activity_type }}</span>
              <span class="tl-time">{{ formatDateTime(act.created_at) }}</span>
            </div>
            <span class="tl-expand" :class="{ open: expandedAct === act.id || expandedAct === act.created_at }">▾</span>
          </div>
          <!-- 活动详情弹窗 -->
          <div v-if="expandedAct" class="activity-detail" @click.stop>
            <div class="ad-header">
              <span class="ad-type" :class="'ad-type-' + expandedActivity.activity_type">
                {{ typeLabel(expandedActivity.activity_type) }}
              </span>
              <button class="ad-close" @click="expandedAct = null">×</button>
            </div>
            <div class="ad-body">
              <div class="ad-row"><span class="ad-label">详情</span><span>{{ expandedActivity.detail || '-' }}</span></div>
              <div class="ad-row"><span class="ad-label">得分</span><span>{{ expandedActivity.score || '-' }}</span></div>
              <div class="ad-row"><span class="ad-label">知识点</span><span>{{ expandedActivity.knowledge_points || '-' }}</span></div>
              <div class="ad-row"><span class="ad-label">时间</span><span>{{ formatDateTime(expandedActivity.created_at) }}</span></div>
              <div class="ad-row"><span class="ad-label">子类型</span><span>{{ expandedActivity.activity_subtype || '-' }}</span></div>
            </div>
          </div>
        </div>
        <div v-else class="empty">暂无活动记录</div>
      </div>
      </template>
    </template>
    <div v-else class="empty">用户不存在</div>

    <!-- 错题重做弹窗 -->
    <div class="modal-overlay" v-if="redo.show" @click.self="closeRedo">
      <div class="redo-modal">
        <div class="redo-header">
          <h3>重做错题</h3>
          <button class="modal-close-btn" @click="closeRedo">×</button>
        </div>
        <div class="redo-body">
          <div class="redo-qtype" :class="'qtype-' + redo.item.q_type">{{ typeLabelQ(redo.item.q_type) }}</div>
          <div class="redo-title">{{ redo.item.q_title }}</div>

          <!-- 选择题 -->
          <div v-if="redo.item.q_type === 'choice'" class="redo-options">
            <label v-for="(opt, oi) in redo.options" :key="oi" class="redo-option"
                   :class="{ selected: redo.answer === opt.letter }">
              <input type="radio" :value="opt.letter" v-model="redo.answer" :disabled="redo.submitting" />
              <span class="redo-opt-letter">{{ opt.letter }}.</span>
              <span>{{ opt.text }}</span>
            </label>
          </div>

          <!-- 判断题 -->
          <div v-else-if="redo.item.q_type === 'judge'" class="redo-judge">
            <button class="redo-judge-btn" :class="{ selected: redo.answer === '对' }"
                    @click="redo.answer = '对'" :disabled="redo.submitting">对</button>
            <button class="redo-judge-btn" :class="{ selected: redo.answer === '错' }"
                    @click="redo.answer = '错'" :disabled="redo.submitting">错</button>
          </div>

          <!-- 填空/简答/编程 -->
          <div v-else class="redo-input">
            <textarea v-model="redo.answer" rows="3" placeholder="输入你的答案" :disabled="redo.submitting"></textarea>
          </div>

          <!-- 主观题自评 -->
          <div v-if="redo.needSelfAssess" class="redo-self">
            <p class="redo-self-tip">本题无法自动判题，请自评重做结果：</p>
            <div class="redo-self-btns">
              <button class="btn" @click="submitRedo(true)" :disabled="redo.submitting">我答对了</button>
              <button class="btn btn-danger" @click="submitRedo(false)" :disabled="redo.submitting">我答错了</button>
            </div>
          </div>

          <button v-else-if="!redo.result" class="redo-submit" @click="submitRedo()"
                  :disabled="redo.submitting || !redo.answer">
            {{ redo.submitting ? '提交中...' : '提交答案' }}
          </button>

          <!-- 判题结果 -->
          <div v-if="redo.result" class="redo-result" :class="redo.result.correct ? 'res-ok' : 'res-fail'">
            <div class="res-badge">{{ redo.result.correct ? '回答正确' : '回答错误' }}</div>
            <div class="res-row"><span class="res-label">正确答案：</span><span class="res-answer">{{ redo.item.q_answer }}</span></div>
            <div v-if="redo.item.q_analysis" class="res-analysis">解析：{{ redo.item.q_analysis }}</div>
            <div class="res-actions">
              <button v-if="!redo.result.correct" class="btn" @click="resetRedo">再试一次</button>
              <button class="btn btn-primary" @click="closeRedo">完成</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import { useFeedback } from '../composables/useFeedback'

const { tip, ask } = useFeedback()

const route = useRoute()
const profile = ref(null)
const loading = ref(true)
const openTracks = reactive({})
const expandedAct = ref(null)
const expandedActivity = ref(null)
const heatmapEnd = ref('')
const hmLoading = ref(false)
const dayDetail = reactive({ show: false, date: '', items: [], loading: false })

// 角色视图：开发者 > 教师 > 学生（以数据字段存在性为准，避免接口异常时模板崩溃）
const isDevView = computed(() => !!profile.value?.system)
const isTeacherView = computed(() => !!profile.value?.teaching && !profile.value?.user?.is_dev)
const isStudentView = computed(() => profile.value && !profile.value?.system && !profile.value?.teaching)

// 错题本
const wrongBook = reactive({ items: [], groups: {}, total: 0 })
const wrongBookLoading = ref(false)
const openWrongGroups = reactive({})
const wrongBookOpenAll = ref(false)
const wrongPageSize = 20
const wrongPage = ref(1)

// 错题重做
const redo = reactive({ show: false, item: null, options: [], answer: '', result: null, submitting: false, needSelfAssess: false })

// 成就徽章
const achievements = reactive({ streak_days: 0, items: [] })

async function loadAchievements() {
  try {
    const uid = route.params.id
    const res = await api.get(`/users/${uid}/achievements`)
    if (res.success && res.data) {
      achievements.streak_days = res.data.streak_days || 0
      achievements.items = res.data.items || []
    }
  } catch (e) {
    console.error('加载徽章失败:', e)
  }
}

const groupedDayItems = computed(() => {
  const groups = {}
  for (const item of dayDetail.items) {
    const t = item.activity_type || 'other'
    if (!groups[t]) groups[t] = []
    groups[t].push(item)
  }
  const order = ['exam', 'homework', 'practice', 'code', 'checkin', 'other']
  return order.filter(t => groups[t]).map(t => ({ type: t, items: groups[t] }))
})

const wdays = ['一', '二', '三', '四', '五', '六', '日']

const isToday = computed(() => {
  if (!heatmapEnd.value) return true
  const td = new Date()
  const dt = new Date(heatmapEnd.value)
  return td.toDateString() === dt.toDateString()
})

async function loadProfile(hmEnd) {
  const uid = route.params.id
  const params = {}
  if (hmEnd) params.heatmap_end = hmEnd
  const qs = hmEnd ? `?heatmap_end=${hmEnd}` : ''
  const res = await api.get(`/users/${uid}/profile${qs}`)
  if (res.success) {
    profile.value = res.data
    if (hmEnd) {
      heatmapEnd.value = hmEnd
    } else if (res.data.stats) {
      const days = res.data.stats.weekly_heatmap || []
      if (days.length > 0) {
        heatmapEnd.value = days[days.length - 1].date
      }
    }
  }
}

onMounted(async () => {
  try {
    loading.value = true
    await loadProfile()
    // 仅学生视图需要错题本/成就（教师、开发者不展示个人学习数据）
    if (isStudentView.value) {
      await loadWrongBook()
      await loadAchievements()
    }
  } catch (e) {
    console.error('加载用户信息失败:', e)
  } finally {
    loading.value = false
  }
})

const heatmapWeeks = computed(() => {
  if (!profile.value) return []
  const days = profile.value.stats.weekly_heatmap || []
  const weeks = []
  for (let i = 0; i < days.length; i += 7) {
    weeks.push(days.slice(i, i + 7))
  }
  return weeks
})

// 计算月份标签（按周跨度）
const monthLabels = computed(() => {
  if (!profile.value) return []
  const days = profile.value.stats.weekly_heatmap || []
  if (days.length === 0) return []
  const weeks = heatmapWeeks.value
  if (weeks.length === 0) return []
  const MONTHS = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月']
  const labels = []
  for (let wi = 0; wi < weeks.length; wi++) {
    const midDate = weeks[wi][Math.floor(weeks[wi].length / 2)]
    const m = midDate ? parseInt(midDate.date.split('-')[1]) - 1 : 0
    const label = MONTHS[m]
    if (labels.length === 0 || labels[labels.length - 1].label !== label) {
      labels.push({ label, span: 1 })
    } else {
      labels[labels.length - 1].span++
    }
  }
  return labels
})

async function shiftHeatmap(days) {
  hmLoading.value = true
  try {
    const days_list = profile.value.stats.weekly_heatmap || []
    if (days_list.length === 0) return
    const cur = new Date(days_list[days_list.length - 1].date)
    cur.setDate(cur.getDate() + days)
    const newEnd = cur.toISOString().split('T')[0]
    await loadProfile(newEnd)
  } catch (e) {
    console.error(e)
  } finally {
    hmLoading.value = false
  }
}

async function jumpHeatmap(e) {
  const val = e.target.value
  if (!val) return
  hmLoading.value = true
  try {
    await loadProfile(val)
  } catch (e2) {
    console.error(e2)
  } finally {
    hmLoading.value = false
  }
}

async function resetHeatmap() {
  hmLoading.value = true
  try {
    heatmapEnd.value = ''
    await loadProfile()
  } catch (e) {
    console.error(e)
  } finally {
    hmLoading.value = false
  }
}


function getHeatColor(count) {
  if (count === 0) return '#f1f5f9'
  if (count <= 1) return '#bbf7d0'
  if (count <= 3) return '#4ade80'
  if (count <= 6) return '#16a34a'
  return '#14532d'
}

function toggleTrack(name) { openTracks[name] = !openTracks[name] }

function toggleActivity(act) {
  if (expandedAct.value === (act.id || act.created_at)) {
    expandedAct.value = null
    expandedActivity.value = null
  } else {
    expandedAct.value = act.id || act.created_at
    expandedActivity.value = act
  }
}

function typeLabel(t) {
  const m = { exam: '考试', practice: 'AI练习', code: '代码练习', homework: '作业', checkin: '学习打卡' }
  return m[t] || t
}

async function showDayDetail(day) {
  dayDetail.date = day.date
  dayDetail.show = true
  if (day.count === 0) {
    dayDetail.items = []
    return
  }
  dayDetail.loading = true
  dayDetail.items = []
  try {
    const uid = route.params.id
    const res = await api.get(`/users/${uid}/day-activities?date=${day.date}`)
    if (res.success) {
      dayDetail.items = res.data || []
    }
  } catch (e) {
    console.error(e)
  } finally {
    dayDetail.loading = false
  }
}

async function loadWrongBook() {
  wrongBookLoading.value = true
  try {
    const uid = route.params.id
    const res = await api.get(`/users/${uid}/wrong-answers`, { params: { page: wrongPage.value, page_size: wrongPageSize } })
    if (res.success) {
      wrongBook.items = res.data.items || []
      wrongBook.groups = res.data.groups || {}
      wrongBook.total = res.data.total || 0
    }
  } catch (e) {
    console.error('加载错题本失败:', e)
  } finally {
    wrongBookLoading.value = false
  }
}

function changeWrongPage(p) {
  wrongPage.value = p
  loadWrongBook()
}

function toggleWrongGroup(kpName) {
  openWrongGroups[kpName] = !openWrongGroups[kpName]
}

function deleteWrongAnswer(item) {
  ask('确定删除该错题记录？', async () => {
    try {
      const uid = route.params.id
      const res = await api.delete(`/users/${uid}/wrong-answers/${item.id}`)
      if (res.success) {
        removeWrongItem(item.id)
        // 当前页删空时回退页码，重新加载以同步服务端总数，避免空页
        if (wrongBook.items.length === 0 && wrongPage.value > 1) {
          wrongPage.value -= 1
        }
        loadWrongBook()
      }
    } catch (e) {
      console.error('删除错题失败:', e)
      tip('删除失败')
    }
  })
}

function removeWrongItem(aid) {
  wrongBook.items = wrongBook.items.filter(i => i.id !== aid)
  // 重建分组
  const groups = {}
  for (const i of wrongBook.items) {
    const kp = i.knowledge_point_name || '未分类'
    if (!groups[kp]) groups[kp] = []
    groups[kp].push(i)
  }
  wrongBook.groups = groups
  wrongBook.total = wrongBook.items.length
}

function openRedo(item) {
  let options = []
  if (item.q_options && Array.isArray(item.q_options)) {
    options = item.q_options.map((opt, i) => {
      const letter = String.fromCharCode(65 + i)
      const text = String(opt).replace(/^[A-Da-d][.、．)]?\s*/, '')
      return { letter, text }
    })
  }
  redo.item = item
  redo.options = options
  redo.answer = ''
  redo.result = null
  redo.submitting = false
  redo.needSelfAssess = item.q_type === 'subjective' || item.q_type === 'code'
  redo.show = true
}

function closeRedo() { redo.show = false }

function resetRedo() {
  redo.answer = ''
  redo.result = null
}

function judgeRedo(item, answer) {
  const qtype = item.q_type
  if (qtype === 'subjective' || qtype === 'code') return null
  const u = (answer || '').trim()
  const c = (item.q_answer || '').trim()
  if (qtype === 'fill') {
    const norm = s => s.replace(/[\s，。；、,.!！?？()（）]/g, '').toLowerCase()
    return norm(u) === norm(c)
  }
  if (qtype === 'judge') {
    const pos = ['对', '√', '✓', 'true', 't', 'yes', 'y', '1', '正确', '是']
    const neg = ['错', '×', '✗', 'false', 'f', 'no', 'n', '0', '错误', '否']
    const nu = pos.includes(u.toLowerCase()) ? '对' : neg.includes(u.toLowerCase()) ? '错' : u
    const nc = pos.includes(c.toLowerCase()) ? '对' : neg.includes(c.toLowerCase()) ? '错' : c
    return nu === nc
  }
  // choice：取答案字母比较
  const letter = s => {
    const m = String(s).trim().match(/^([A-Da-d])/)
    return m ? m[1].toUpperCase() : String(s).trim().toUpperCase()
  }
  return letter(u) === letter(c)
}

async function submitRedo(selfAssess) {
  const item = redo.item
  let isCorrect
  if (typeof selfAssess === 'boolean') {
    isCorrect = selfAssess
  } else {
    isCorrect = judgeRedo(item, redo.answer)
    if (isCorrect === null) return // 主观题走自评
  }
  redo.submitting = true
  try {
    const uid = route.params.id
    const res = await api.post(`/users/${uid}/wrong-answers/${item.id}/redo`, { is_correct: isCorrect ? 1 : 0 })
    if (res.success) {
      redo.result = { correct: !!isCorrect }
      if (isCorrect) {
        removeWrongItem(item.id) // 重做正确 → 标记已掌握，从错题本移除
      }
    }
  } catch (e) {
    console.error('重做提交失败:', e)
    tip('提交失败，请重试')
  } finally {
    redo.submitting = false
  }
}

function typeLabelQ(t) {
  const m = { choice: '单选题', judge: '判断题', fill: '填空题', subjective: '简答题', code: '编程题' }
  return m[t] || t
}

function formatTime(t) {
  if (!t) return ''
  return new Date(t).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
function formatDate(d) {
  if (!d) return ''
  return d.split(' ')[0] || d.split('T')[0]
}
function examStatusText(s) {
  return { draft: '草稿', published: '进行中', closed: '已结束', deleted: '已删除' }[s] || s
}
function formatDateTime(d) {
  if (!d) return ''
  return d.replace('T', ' ').split('.')[0]
}
</script>

<style scoped>
.profile-page { max-width: 900px; margin: 0 auto; padding: 32px 24px; }
.loading, .empty { text-align: center; padding: 60px 20px; color: #94a3b8; }
.profile-header {
  display: flex; align-items: center; gap: 24px; padding: 32px;
  background: #ffffff; border-radius: 12px;
  border: 1px solid #e0e7ff; margin-bottom: 24px;
}
.avatar-placeholder {
  width: 80px; height: 80px; border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  display: flex; align-items: center; justify-content: center;
  font-size: 36px; color: #fff; font-weight: 700; flex-shrink: 0;
}
.profile-name { font-size: 28px; font-weight: 700; margin: 0 0 8px; color: #1e293b; }
.profile-meta { display: flex; gap: 12px; flex-wrap: wrap; }
.meta-item { font-size: 13px; color: #475569; background: #f1f5f9; padding: 4px 12px; border-radius: 12px; }

.stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
.stat-card {
  background: #ffffff; border: 1px solid #e0e7ff;
  border-radius: 12px; padding: 20px; text-align: center;
}
.stat-value { font-size: 32px; font-weight: 700; color: #3b82f6; }
.stat-label { font-size: 13px; color: #64748b; margin-top: 4px; }
.stat-sub { font-size: 11px; color: #94a3b8; margin-top: 4px; }

/* 成就徽章 */
.badge-grid { display: flex; gap: 16px; flex-wrap: wrap; }
.badge-item {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  width: 100px; padding: 16px 8px; border-radius: 12px;
  background: #fffbeb; border: 1px solid #fde68a;
}
.badge-item.locked { background: #f8fafc; border-color: #e2e8f0; }
.badge-circle {
  width: 56px; height: 56px; border-radius: 50%;
  background: radial-gradient(circle at 30% 25%, #fef3c7, #f59e0b);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 14px; font-weight: 700;
  box-shadow: 0 2px 8px rgba(245, 158, 11, 0.35);
}
.badge-circle-locked {
  background: #e2e8f0; color: #94a3b8; box-shadow: none;
}
.badge-name { font-size: 13px; font-weight: 600; color: #1e293b; }
.badge-item.locked .badge-name { color: #94a3b8; }
.badge-desc { font-size: 11px; color: #94a3b8; }

/* 难度分布 */
.diff-list { display: flex; flex-direction: column; gap: 10px; }
.diff-item { display: flex; align-items: center; gap: 12px; }
.diff-stars { font-size: 14px; color: #f59e0b; letter-spacing: 2px; width: 90px; flex-shrink: 0; }
.diff-count { font-size: 12px; color: #64748b; width: 50px; flex-shrink: 0; }
.diff-bar { flex: 1; height: 8px; background: #f1f5f9; border-radius: 4px; overflow: hidden; }
.diff-bar-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #10b981); border-radius: 4px; transition: width 0.5s; }
.diff-rate { font-size: 12px; color: #334155; font-weight: 600; width: 44px; text-align: right; flex-shrink: 0; }

.card {
  background: #ffffff; border: 1px solid #e0e7ff;
  border-radius: 12px; padding: 24px; margin-bottom: 24px;
}
.section-title { font-size: 16px; font-weight: 600; margin: 0 0 16px; color: #1e293b; }

/* 热力图网格 */
.heatmap-grid { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.heatmap-container { display: flex; flex-direction: column; }
.heatmap-weeks { display: flex; gap: 2px; }
.hm-week { display: flex; flex-direction: column; gap: 2px; }
.hm-day { width: 12px; height: 12px; border-radius: 2px; cursor: pointer; transition: transform 0.1s; }
.hm-day:hover { transform: scale(1.4); z-index: 1; }
.heatmap-legend { display: flex; align-items: center; gap: 4px; font-size: 11px; color: #94a3b8; }
.lg-block { width: 12px; height: 12px; border-radius: 2px; }
.hm-nav-btn {
  padding: 4px 10px; font-size: 12px; border: 1px solid #cbd5e1; border-radius: 4px;
  background: #fff; color: #475569; cursor: pointer; white-space: nowrap;
}
.hm-nav-btn:hover:not(:disabled) { background: #f1f5f9; border-color: #3b82f6; color: #3b82f6; }
.hm-nav-btn:disabled { opacity: 0.4; cursor: default; }
.hm-date-input {
  padding: 4px 8px; font-size: 12px; border: 1px solid #cbd5e1; border-radius: 4px;
  color: #334155; outline: none;
}
.hm-date-input:focus { border-color: #3b82f6; }
/* 月份标签 */
.hm-month-row { display: flex; height: 14px; margin-bottom: 4px; }
.hm-wday-spacer { width: 22px; flex-shrink: 0; }
.hm-month-labels { display: flex; flex: 1; }
.hm-month-label { flex: 1; font-size: 9px; color: #94a3b8; text-align: center; }
/* 主体：星期 + 格子 */
.hm-body { display: flex; }
.hm-wday-col { display: flex; flex-direction: column; gap: 2px; width: 22px; flex-shrink: 0; padding-top: 1px; }
.hm-wday { font-size: 9px; color: #94a3b8; height: 12px; line-height: 12px; text-align: right; padding-right: 4px; }

/* 日期详情弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 200; }
.modal-close-btn { margin-left: auto; background: none; border: none; font-size: 22px; cursor: pointer; color: #94a3b8; padding: 0 4px; line-height: 1; }
.day-detail-modal {
  background: #fff; border-radius: 12px; width: 480px; max-height: 80vh;
  display: flex; flex-direction: column; box-shadow: 0 8px 30px rgba(0,0,0,0.15);
}
.ddm-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid #e2e8f0;
}
.ddm-header h3 { font-size: 16px; color: #1e293b; margin: 0; }
.ddm-loading { padding: 32px; text-align: center; color: #94a3b8; }
.ddm-list { padding: 8px 0; overflow-y: auto; max-height: 60vh; }
.ddm-item {
  display: flex; align-items: center; gap: 10px; padding: 10px 20px;
  border-bottom: 1px solid #f1f5f9; font-size: 13px;
}
.ddm-item:last-child { border-bottom: none; }
/* 分组标题 */
.ddm-group-header {
  display: flex; align-items: center; gap: 8px; padding: 8px 20px;
  background: #f8fafc; border-bottom: 1px solid #e2e8f0; font-size: 12px;
}
.ddm-group-header:first-child { border-top: none; }
.ddm-type-badge {
  padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;
}
.ddm-group-count { color: #94a3b8; }
/* 备注 */
.ddm-note {
  font-size: 11px; color: #64748b; flex-shrink: 0; cursor: help;
  max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ddm-exam { background: #dbeafe; color: #2563eb; }
.ddm-practice { background: #dcfce7; color: #16a34a; }
.ddm-code { background: #fef3c7; color: #d97706; }
.ddm-homework { background: #f3e8ff; color: #9333ea; }
.ddm-checkin { background: #ccfbf1; color: #0d9488; }
.ddm-other { background: #f1f5f9; color: #64748b; }
.ddm-detail { flex: 1; color: #334155; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ddm-score { color: #3b82f6; font-weight: 600; font-size: 12px; flex-shrink: 0; }
.ddm-kp { color: #94a3b8; font-size: 11px; flex-shrink: 0; max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ddm-time { color: #94a3b8; font-size: 11px; flex-shrink: 0; }

/* 赛道掌握 */
.track-list { display: flex; flex-direction: column; gap: 8px; }
.track-item { border: 1px solid #e0e7ff; border-radius: 8px; overflow: hidden; }
.track-header {
  display: flex; align-items: center; gap: 16px; padding: 12px 16px;
  cursor: pointer; user-select: none; transition: background 0.15s;
}
.track-header:hover { background: #f8fafc; }
.track-name { display: flex; align-items: center; gap: 8px; width: 280px; flex-shrink: 0; }
.track-arrow { font-size: 12px; color: #94a3b8; transition: transform 0.2s; display: inline-block; }
.track-arrow.open { transform: rotate(90deg); }
.track-label { font-size: 14px; font-weight: 600; color: #1e293b; }
.track-progress { font-size: 12px; color: #3b82f6; font-weight: 600; }
.track-pct { font-size: 11px; color: #94a3b8; }
.track-bar { flex: 1; height: 8px; background: #f1f5f9; border-radius: 4px; overflow: hidden; }
.track-bar-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #10b981); border-radius: 4px; transition: width 0.5s; }
.track-detail { font-size: 12px; color: #94a3b8; width: 110px; text-align: right; flex-shrink: 0; }

.track-sub { padding: 0 16px 12px; }
.sub-grid { display: flex; flex-wrap: wrap; gap: 6px; }
.sub-kp {
  display: flex; align-items: center; gap: 4px;
  padding: 4px 10px; border-radius: 6px; font-size: 12px;
  background: #f8fafc; border: 1px solid #e0e7ff; color: #64748b;
}
.sub-kp.mastered { background: #f0fdf4; border-color: #bbf7d0; color: #166534; }
.sub-kp-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.sub-kp-name { max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sub-kp-stat { font-size: 10px; color: #94a3b8; }
.track-empty { font-size: 12px; color: #94a3b8; padding: 8px 0; }

/* 活动时间线 */
.timeline { display: flex; flex-direction: column; gap: 8px; position: relative; }
.timeline-item {
  display: flex; gap: 12px; align-items: center; padding: 8px 12px;
  border-radius: 8px; cursor: pointer; transition: background 0.15s;
}
.timeline-item:hover { background: #f8fafc; }
.timeline-dot {
  width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
}
.dot-exam { background: #ef4444; }
.dot-practice { background: #3b82f6; }
.dot-homework { background: #f59e0b; }
.dot-code { background: #10b981; }
.timeline-content { display: flex; flex-direction: column; gap: 2px; flex: 1; }
.tl-detail { font-size: 13px; color: #1e293b; }
.tl-time { font-size: 11px; color: #94a3b8; }
.tl-expand { font-size: 12px; color: #94a3b8; transition: transform 0.2s; }
.tl-expand.open { transform: rotate(180deg); }

/* 活动详情 */
.activity-detail {
  margin-top: 4px; padding: 16px; background: #f8fafc;
  border: 1px solid #e0e7ff; border-radius: 8px;
}
.ad-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.ad-type { padding: 3px 10px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.ad-type-exam { background: #fee2e2; color: #ef4444; }
.ad-type-practice { background: #dbeafe; color: #3b82f6; }
.ad-type-code { background: #d1fae5; color: #10b981; }
.ad-type-homework { background: #fef3c7; color: #f59e0b; }
.ad-close { background: none; border: none; font-size: 16px; color: #94a3b8; cursor: pointer; }
.ad-body { display: flex; flex-direction: column; gap: 8px; }
.ad-row { display: flex; gap: 12px; font-size: 13px; }
.ad-label { color: #94a3b8; width: 50px; flex-shrink: 0; }

.btn-text {
  background: none; border: none; color: #3b82f6; font-size: 12px; cursor: pointer; padding: 2px 6px;
}

/* 错题本 */
.wrong-section { display: flex; flex-direction: column; gap: 8px; }
.wrong-group { border: 1px solid #e0e7ff; border-radius: 8px; overflow: hidden; }
.wrong-group-header {
  display: flex; align-items: center; gap: 8px; padding: 10px 16px;
  cursor: pointer; background: #f8fafc; transition: background 0.15s; user-select: none;
}
.wrong-group-header:hover { background: #f1f5f9; }
.wrong-arrow { font-size: 12px; color: #94a3b8; transition: transform 0.2s; display: inline-block; }
.wrong-arrow.open { transform: rotate(90deg); }
.wrong-kp-name { font-size: 14px; font-weight: 600; color: #1e293b; }
.wrong-kp-count { font-size: 12px; color: #ef4444; margin-left: auto; }
.wrong-items { border-top: 1px solid #e0e7ff; }
.wrong-item { padding: 14px 16px; border-bottom: 1px solid #f1f5f9; position: relative; }
.wrong-item:last-child { border-bottom: none; }
.wrong-item-actions {
  position: absolute; top: 8px; right: 10px;
  display: flex; align-items: center; gap: 6px;
}
.wrong-redo {
  background: #eff6ff; border: 1px solid #bfdbfe; color: #2563eb;
  font-size: 11px; padding: 2px 8px; border-radius: 4px; cursor: pointer;
}
.wrong-redo:hover { background: #dbeafe; }
.wrong-delete {
  background: none; border: none; font-size: 16px; color: #94a3b8;
  cursor: pointer; line-height: 1; padding: 2px 4px; border-radius: 4px;
}
.wrong-delete:hover { color: #ef4444; background: #fef2f2; }
.wrong-q-title { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 8px; }
.wrong-q-type {
  padding: 1px 6px; border-radius: 4px; font-size: 11px; font-weight: 500; flex-shrink: 0;
  white-space: nowrap;
}
.qtype-choice { background: #dbeafe; color: #2563eb; }
.qtype-judge { background: #fef3c7; color: #d97706; }
.qtype-fill { background: #dcfce7; color: #16a34a; }
.qtype-subjective { background: #f3e8ff; color: #9333ea; }
.qtype-code { background: #fce7f3; color: #db2777; }
.wrong-q-detail { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; font-size: 13px; margin-bottom: 6px; }
.wrong-label { color: #94a3b8; font-size: 12px; flex-shrink: 0; }
.wrong-ans { color: #ef4444; font-weight: 500; }
.wrong-correct { color: #16a34a; font-weight: 600; }
.wrong-score { margin-left: auto; font-size: 12px; color: #64748b; flex-shrink: 0; }
.wrong-analysis {
  font-size: 12px; color: #475569; background: #fffbeb; border-left: 3px solid #f59e0b;
  padding: 6px 10px; border-radius: 0 4px 4px 0; margin-bottom: 6px; line-height: 1.5;
}
.wrong-meta { font-size: 11px; color: #94a3b8; }

/* 错题重做弹窗 */
.redo-modal {
  background: #fff; border-radius: 12px; width: 520px; max-height: 85vh;
  display: flex; flex-direction: column; box-shadow: 0 8px 30px rgba(0,0,0,0.15);
}
.redo-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid #e2e8f0;
}
.redo-header h3 { font-size: 16px; color: #1e293b; margin: 0; }
.redo-body { padding: 20px; overflow-y: auto; }
.redo-qtype { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; margin-bottom: 10px; }
.redo-title { font-size: 15px; color: #1e293b; font-weight: 500; margin-bottom: 16px; line-height: 1.6; }
.redo-options { display: flex; flex-direction: column; gap: 8px; }
.redo-option {
  display: flex; align-items: center; gap: 8px; padding: 10px 12px;
  border: 1px solid #e2e8f0; border-radius: 8px; cursor: pointer; font-size: 14px;
  transition: all 0.15s;
}
.redo-option:hover { border-color: #93c5fd; }
.redo-option.selected { border-color: #3b82f6; background: #eff6ff; }
.redo-opt-letter { font-weight: 700; color: #3b82f6; width: 18px; }
.redo-judge { display: flex; gap: 12px; }
.redo-judge-btn {
  flex: 1; padding: 12px; font-size: 16px; font-weight: 600;
  border: 1px solid #e2e8f0; border-radius: 8px; background: #fff; cursor: pointer;
}
.redo-judge-btn.selected { border-color: #3b82f6; background: #eff6ff; color: #2563eb; }
.redo-input textarea {
  width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 8px;
  font-size: 14px; font-family: inherit; resize: vertical; outline: none; box-sizing: border-box;
}
.redo-input textarea:focus { border-color: #3b82f6; }
.redo-submit {
  width: 100%; margin-top: 16px; padding: 10px; background: #3b82f6; color: #fff;
  border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer;
}
.redo-submit:hover:not(:disabled) { background: #2563eb; }
.redo-submit:disabled { opacity: 0.5; cursor: default; }
.redo-self { margin-top: 16px; }
.redo-self-tip { font-size: 13px; color: #64748b; margin: 0 0 10px; }
.redo-self-btns { display: flex; gap: 12px; }
.redo-result { margin-top: 16px; padding: 14px; border-radius: 8px; border: 1px solid; }
.res-ok { background: #f0fdf4; border-color: #bbf7d0; }
.res-fail { background: #fef2f2; border-color: #fecaca; }
.res-badge { font-size: 14px; font-weight: 700; margin-bottom: 8px; }
.res-ok .res-badge { color: #16a34a; }
.res-fail .res-badge { color: #dc2626; }
.res-row { font-size: 13px; margin-bottom: 6px; }
.res-label { color: #94a3b8; }
.res-answer { color: #16a34a; font-weight: 600; }
.res-analysis { font-size: 12px; color: #475569; background: #fff; border-radius: 6px; padding: 8px 10px; line-height: 1.5; margin-bottom: 12px; }
.res-actions { display: flex; justify-content: flex-end; gap: 10px; }

/* 教学工作台（统一靛蓝主调） */
.work-actions { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.work-item {
  display: flex; align-items: center; justify-content: center;
  padding: 18px 12px; border-radius: 10px; font-size: 14px; font-weight: 600;
  color: #4338ca; background: linear-gradient(135deg, #eef2ff, #e0e7ff);
  border: 1px solid #c7d2fe;
  transition: transform 0.15s, box-shadow 0.15s, background 0.15s;
}
.work-item:hover {
  transform: translateY(-2px);
  background: linear-gradient(135deg, #e0e7ff, #c7d2fe);
  box-shadow: 0 6px 16px rgba(79, 70, 229, 0.18);
  color: #3730a3;
}

.work-todos { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 16px; }
.work-todo { border-radius: 10px; padding: 14px 16px; color: #fff; }
.todo-value { font-size: 26px; font-weight: 700; line-height: 1.1; }
.todo-label { font-size: 13px; margin-top: 4px; font-weight: 600; }
.todo-sub { font-size: 12px; opacity: 0.85; margin-top: 2px; }
.todo-main { background: linear-gradient(135deg, #6366f1, #4f46e5); }
.todo-deep { background: linear-gradient(135deg, #4f46e5, #4338ca); }

.exam-list { display: flex; flex-direction: column; }
.exam-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 12px; border-radius: 8px; transition: background 0.15s;
}
.exam-item:hover { background: #f8fafc; }
.exam-title { font-size: 13px; font-weight: 600; color: #1e293b; }
.exam-meta { display: flex; align-items: center; gap: 10px; font-size: 12px; color: #64748b; }
.exam-class { color: #64748b; }
.exam-status { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.st-draft { background: #fffbeb; color: #b45309; }
.st-published { background: #ecfdf5; color: #047857; }
.st-closed { background: #f1f5f9; color: #64748b; }

/* 班级概览（教师视图） */
.class-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.class-item {
  border: 1px solid #e0e7ff; border-radius: 10px; padding: 14px 16px;
  background: #fff; transition: box-shadow 0.15s;
}
.class-item:hover { box-shadow: 0 2px 10px rgba(59,130,246,0.08); }
.class-item-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
.class-name { font-size: 14px; font-weight: 600; color: #1e293b; }
.class-code {
  font-size: 11px; color: #3b82f6; background: #eff6ff;
  padding: 2px 8px; border-radius: 4px; font-family: monospace;
}
.class-item-meta { display: flex; justify-content: space-between; font-size: 12px; color: #64748b; }
.class-students { color: #16a34a; font-weight: 600; }
.class-date { color: #94a3b8; }

@media (max-width: 768px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .track-header { flex-wrap: wrap; }
  .class-grid { grid-template-columns: 1fr; }
  .work-actions { grid-template-columns: repeat(2, 1fr); }
  .exam-item { flex-direction: column; align-items: flex-start; gap: 6px; }
}
</style>
