<template>
  <div class="solution-page">
    <!-- 左侧题目 -->
    <div class="solution-left">
      <div class="back-row"><button class="btn-back" @click="$router.back()">&larr; 返回练习</button></div>
      <div class="problem-card">
        <div class="problem-header">
          <h2>{{ exercise.title }}</h2>
          <span class="diff-tag" :class="'diff-' + exercise.difficulty">
            {{ ['', '★', '★★', '★★★', '★★★★', '★★★★★'][exercise.difficulty] || '★' }}
          </span>
        </div>
        <div class="problem-desc">{{ exercise.description }}</div>
      </div>
    </div>

    <!-- 右侧答案 -->
    <div class="solution-right">
      <div class="solution-topbar">
        <div class="solution-tabs">
          <button class="sol-tab" :class="{ active: solutionTab === 'ai' }" @click="solutionTab = 'ai'">
            AI 标准答案
          </button>
          <button class="sol-tab" :class="{ active: solutionTab === 'user' }" @click="solutionTab = 'user'">
            他人题解 <span class="tab-count">{{ userAnswers.length }}</span>
          </button>
        </div>
      </div>

      <div class="solution-body">
        <!-- AI 答案 -->
        <div v-if="solutionTab === 'ai'" class="ai-solution">
          <div class="solution-meta">
            <span class="meta-badge ai-badge">AI 生成</span>
            <span class="meta-hint">以下为 DeepSeek 生成的标准答案，仅供参考</span>
          </div>
          <div v-if="aiLoading" class="loading-box">AI 正在生成答案...</div>
          <div v-else class="code-block">
            <div class="code-lines"><span v-for="n in aiLines" :key="n" class="code-ln">{{ n }}</span></div>
            <pre class="solution-code">{{ aiAnswer }}</pre>
          </div>
        </div>

        <!-- 用户答案 - 竖向列表 -->
        <div v-if="solutionTab === 'user'">
          <div v-if="userAnswers.length === 0" class="empty-solutions">
            暂无其他用户的题解
          </div>
          <div v-else class="user-solution-list">
            <div v-for="(a, i) in userAnswers" :key="i" class="user-card">
              <div class="user-card-header">
                <div class="user-card-avatar">{{ (a.username || '?')[0].toUpperCase() }}</div>
                <div class="user-card-info">
                  <div class="user-card-name">{{ a.username || '用户' + a.user_id }}</div>
                  <div class="user-card-time">{{ a.created_at || '' }}</div>
                </div>
                <span class="user-card-tag">#{{ i + 1 }}</span>
              </div>
              <div class="code-block user-card-code-block">
                <div class="code-lines"><span v-for="n in codeLines(a.code)" :key="n" class="code-ln">{{ n }}</span></div>
                <pre class="solution-code user-card-code">{{ a.code || '(无代码)' }}</pre>
              </div>
              <div v-if="a.explanation" class="user-card-exp">
                <div class="exp-label">题解说明</div>
                <p>{{ a.explanation }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import { useFeedback } from '../composables/useFeedback'

const route = useRoute()
const { tip } = useFeedback()
const exerciseId = Number(route.params.id)

const exercise = ref({ title: '', description: '', difficulty: 1 })
const solutionTab = ref('ai')
const aiAnswer = ref('')
const aiLoading = ref(false)
const userAnswers = ref([])

const aiLines = computed(() => Math.max(aiAnswer.value.split('\n').length, 8))
function codeLines(code) { return Math.max((code || '').split('\n').length, 8) }

onMounted(async () => {
  await loadExercise()
  await loadAnswersAndAI()
})

async function loadExercise() {
  try {
    const r = await api.get(`/code-exercises/${exerciseId}`)
    if (r.success) exercise.value = r.data
  } catch (e) { console.error('加载题目失败', e); tip('题目加载失败，请稍后重试') }
}

async function loadAnswersAndAI() {
  // 先加载已有答案（包含 AI 答案）
  aiLoading.value = true
  try {
    const r = await api.get(`/code-exercises/${exerciseId}/answers`)
    if (r.success) {
      const all = r.data || []
      userAnswers.value = all.filter(a => a.answer_type !== 'ai')
      const aiAns = all.find(a => a.answer_type === 'ai')
      if (aiAns) {
        // 已有 AI 答案，直接使用
        aiAnswer.value = aiAns.code
        aiLoading.value = false
        return
      }
    }
  } catch (e) { /* 继续尝试生成 */ }

  // 没有已有 AI 答案，调用 AI 生成
  try {
    const r = await api.post(`/code-exercises/${exerciseId}/ai-answer`)
    if (r.success) aiAnswer.value = r.data.code || r.data.answer || '(AI 未返回答案)'
  } catch (e) { aiAnswer.value = '(AI 生成失败)' }
  aiLoading.value = false
}
</script>

<style scoped>
.solution-page {
  display: flex; height: calc(100vh - 64px); background: #f8fafc;
}

/* 左侧题目 */
.solution-left {
  width: 40%; min-width: 360px; overflow-y: auto;
  border-right: 1px solid #e0e7ff; padding: 24px;
}
.back-row { margin-bottom: 16px; }
.btn-back {
  background: none; border: 1px solid #cbd5e1; color: #475569;
  padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 11px;
}
.btn-back:hover { border-color: #3b82f6; color: #3b82f6; }
.problem-card {
  background: #ffffff; border: 1px solid #e0e7ff; border-radius: 10px; padding: 24px;
}
.problem-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
.problem-header h2 { margin: 0; font-size: 16px; color: #1e40af; }
.diff-tag { padding: 2px 10px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.diff-1 { color: #10b981; background: #d1fae5; }
.diff-2 { color: #3b82f6; background: #dbeafe; }
.diff-3 { color: #f59e0b; background: #fef3c7; }
.diff-4 { color: #f97316; background: #ffedd5; }
.diff-5 { color: #ef4444; background: #fee2e2; }
.problem-desc { font-size: 12px; color: #475569; line-height: 1.8; white-space: pre-wrap; }

/* 右侧答案 */
.solution-right {
  flex: 1; display: flex; flex-direction: column; overflow: hidden;
}
.solution-topbar {
  padding: 16px 24px; border-bottom: 1px solid #e0e7ff;
  background: #ffffff; display: flex; justify-content: space-between;
  align-items: center; flex-wrap: wrap; gap: 8px;
}
.solution-tabs { display: flex; gap: 4px; }
.sol-tab {
  padding: 8px 18px; border: 1px solid #e0e7ff; background: #ffffff;
  color: #64748b; border-radius: 6px; cursor: pointer; font-size: 11px;
  font-weight: 500; transition: all 0.15s;
}
.sol-tab:hover { border-color: #3b82f6; color: #3b82f6; }
.sol-tab.active { background: #3b82f6; color: #fff; border-color: #3b82f6; }
.tab-count { font-size: 10px; opacity: 0.8; }

.solution-body { flex: 1; overflow-y: auto; padding: 24px; }
.solution-meta { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.meta-badge { padding: 3px 10px; border-radius: 4px; font-size: 10px; font-weight: 600; }
.ai-badge { background: #ede9fe; color: #7c3aed; }
.meta-hint { font-size: 11px; color: #94a3b8; }

/* 带行号的代码块 - 行号用绝对定位，代码用 padding-left 留空 */
.code-block {
  position: relative; border-radius: 8px; overflow: hidden;
  border: 1px solid #334155; background: #0f172a;
}
.code-lines {
  position: absolute; top: 0; left: 0; bottom: 0; width: 44px;
  background: #1a2332; color: #546e7a;
  font-family: 'Consolas', 'Monaco', monospace; font-size: 11px;
  line-height: 1.7; padding: 12px 0; text-align: right;
  overflow: hidden; user-select: none; pointer-events: none;
}
.code-ln { display: block; padding: 0 10px; }
.solution-code {
  background: #0f172a; color: #e2e8f0; padding: 12px 14px 12px 56px;
  font-size: 11px; line-height: 1.7; overflow-x: auto; margin: 0;
  white-space: pre-wrap; word-break: break-all;
  border-radius: 0; border: none; min-height: 60px;
}
.loading-box { text-align: center; padding: 60px 20px; color: #94a3b8; font-size: 12px; }
.empty-solutions { text-align: center; padding: 60px 20px; color: #94a3b8; font-size: 12px; }

/* 用户题解列表 */
.user-solution-list { display: flex; flex-direction: column; gap: 16px; }
.user-card { border: 1px solid #e0e7ff; border-radius: 10px; padding: 0; overflow: hidden; background: #fff; }
.user-card-header {
  display: flex; align-items: center; gap: 12px; padding: 14px 18px;
  border-bottom: 1px solid #f1f5f9;
}
.user-card-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  background: #3b82f6; color: #fff; display: flex; align-items: center;
  justify-content: center; font-size: 12px; font-weight: 700; flex-shrink: 0;
}
.user-card-info { flex: 1; min-width: 0; }
.user-card-name { font-size: 12px; font-weight: 600; color: #1e293b; }
.user-card-time { font-size: 11px; color: #94a3b8; margin-top: 2px; }
.user-card-tag { font-size: 10px; color: #94a3b8; font-weight: 600; }
.user-card-code-block {
  margin: 0; border-radius: 0; border: none; border-bottom: 1px solid #f1f5f9;
}
.user-card-code {
  max-height: 300px; overflow-y: auto;
  padding: 12px 14px 12px 56px;
}
.user-card-exp { padding: 14px 18px; border-top: 1px solid #f1f5f9; }
.exp-label { font-size: 11px; font-weight: 600; color: #3b82f6; margin-bottom: 6px; }
.user-card-exp p { font-size: 11px; color: #475569; line-height: 1.6; margin: 0; }
</style>
