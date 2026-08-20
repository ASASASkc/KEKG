<template>
  <div class="wrongbook-panel">
    <!-- 错题本头部 -->
    <div class="wb-head">
      <span class="wb-title">错题本（{{ wrongBook.total }} 道）</span>
      <span v-if="wrongBookLoading" class="wb-loading">加载中...</span>
      <button v-else-if="wrongBook.total > 0" class="btn-text" @click="wrongBookOpenAll = !wrongBookOpenAll">
        {{ wrongBookOpenAll ? '折叠全部' : '展开全部' }}
      </button>
    </div>

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
import { ref, reactive, onMounted } from 'vue'
import api from '../api'
import { useFeedback } from '../composables/useFeedback'
import { authStore } from '../stores/auth'

const { tip, ask } = useFeedback()

function currentUid() {
  return authStore.user?.id
}

// 错题本
const wrongBook = reactive({ items: [], groups: {}, total: 0 })
const wrongBookLoading = ref(false)
const openWrongGroups = reactive({})
const wrongBookOpenAll = ref(false)
const wrongPageSize = 20
const wrongPage = ref(1)

// 错题重做
const redo = reactive({ show: false, item: null, options: [], answer: '', result: null, submitting: false, needSelfAssess: false })

async function loadWrongBook() {
  const uid = currentUid()
  if (!uid) return
  wrongBookLoading.value = true
  try {
    const res = await api.get(`/users/${uid}/wrong-answers`, { params: { page: wrongPage.value, page_size: wrongPageSize } })
    if (res.success) {
      wrongBook.items = res.data.items || []
      wrongBook.groups = res.data.groups || {}
      wrongBook.total = res.data.total || 0
    }
  } catch (e) {
    console.error('加载错题本失败:', e)
    tip('错题本加载失败')
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
      const uid = currentUid()
      if (!uid) return
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
    const uid = currentUid()
    if (!uid) return
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

onMounted(() => {
  loadWrongBook()
})
</script>

<style scoped>
.wrongbook-panel {
  height: 100%;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 20px 24px;
  box-sizing: border-box;
}
.empty { text-align: center; padding: 60px 20px; color: #94a3b8; }
.wb-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.wb-title { font-size: 16px; font-weight: 600; color: #1e293b; }
.wb-loading { font-size: 12px; color: #94a3b8; }

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
.wrong-q-title { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 8px; padding-right: 80px; }
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

/* 弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 200; }
.modal-close-btn { margin-left: auto; background: none; border: none; font-size: 22px; cursor: pointer; color: #94a3b8; padding: 0 4px; line-height: 1; }

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
</style>
