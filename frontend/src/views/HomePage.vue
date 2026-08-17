<template>
  <div class="home-page">
    <!-- Hero 区域 -->
    <section class="hero">
      <div class="hero-bg"></div>
      <div class="hero-content">
        <h1 class="hero-title">
          在可视化图谱中<br/><span class="accent">探索知识体系</span>
        </h1>
        <p class="hero-desc">
          输入一个知识点，我们为你构建相关知识点的图谱。
          探索、发现知识之间的关联，快速理解领域全貌。
        </p>
        <div class="hero-search">
          <div class="search-wrapper">
            <input
              v-model="searchKw"
              class="input input-lg search-input"
              placeholder="搜索知识点，例如：装饰器、面向对象、NumPy..."
              @input="onSearchInput"
              @keyup.enter="goSearch"
              @focus="kwLength >= 1 && showResults && (showResults = true)"
              @blur="onBlur"
            />
            <!-- 搜索建议下拉 -->
            <div v-if="showResults && searchResults.length" class="search-dropdown">
              <div
                v-for="item in searchResults"
                :key="item.id"
                class="search-dropdown-item"
                @mousedown.prevent="goResult(item)"
              >
                <span class="sr-name">{{ item.properties?.name }}</span>
                <span class="sr-cat">{{ item.properties?.category || '未分类' }}</span>
              </div>
            </div>
          </div>
          <button class="btn btn-lg btn-primary search-btn" @click="goSearch">
            探索图谱
          </button>
        </div>
        <div class="hero-stats" v-if="graphGroups.length">
          <div v-for="g in graphGroups" :key="g.label" class="stat-card"
            @click="enterGraph(g.label)">
            <span class="stat-num">{{ g.node_count }}</span>
            <span class="stat-label">{{ getGroupName(g.label) }}</span>
            <span class="stat-sub">{{ g.relationship_count }} 关系</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 功能卡片 -->
    <section class="features">
      <h2 class="section-title">核心功能</h2>
      <div class="feature-grid">
        <div class="card feature-card">
          <div class="feature-icon">&#9678;</div>
          <h3>图谱可视化</h3>
          <p>力导向图直观展示知识点关联，拖拽缩放自由探索</p>
        </div>
        <div class="card feature-card">
          <div class="feature-icon">&#9776;</div>
          <h3>知识点管理</h3>
          <p>支持知识点的增删改查，灵活构建知识体系</p>
        </div>
        <div class="card feature-card">
          <div class="feature-icon">&#9881;</div>
          <h3>统计分析</h3>
          <p>图谱数据分布一目了然，帮助把握知识结构</p>
        </div>
        <div class="card feature-card">
          <div class="feature-icon">&#9998;</div>
          <h3>在线考试</h3>
          <p>在线作答、自动判分，检验知识点掌握情况</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const router = useRouter()
const searchKw = ref('')
const searchResults = ref([])
const showResults = ref(false)
const graphGroups = ref([])
let searchTimer = null
let searchSeq = 0   // 请求序号，防止旧结果覆盖新结果

const kwLength = computed(() => searchKw.value.trim().length)

const GROUP_NAMES = {
  'KnowledgePoint': '系统知识图谱',
  'TextbookKnowledge': '教材知识图谱'
}

function getGroupName(label) {
  return GROUP_NAMES[label] || label
}

onMounted(async () => {
  try {
    const r = await api.get('/graph-groups')
    if (r.success) graphGroups.value = r.data
  } catch (e) { console.error('加载图谱分组失败:', e) }
})

function onSearchInput() {
  clearTimeout(searchTimer)
  const kw = searchKw.value.trim()
  if (kw.length < 1) {
    searchResults.value = []
    showResults.value = false
    return
  }
  searchTimer = setTimeout(async () => {
    const seq = ++searchSeq
    try {
      const r = await api.get(`/knowledge-points/search?keyword=${encodeURIComponent(kw)}`)
      if (seq !== searchSeq) return   // 丢弃过期请求
      if (r.success) {
        searchResults.value = (r.data || []).slice(0, 8)
        showResults.value = searchResults.value.length > 0
      }
    } catch (e) { /* ignore */ }
  }, 300)
}

function onBlur() {
  // 延迟隐藏，让 mousedown 先触发
  setTimeout(() => { showResults.value = false }, 200)
}

function goResult(item) {
  showResults.value = false
  searchResults.value = []
  router.push({ path: '/graph', query: { nodeId: item.id } })
}

function goSearch() {
  const kw = searchKw.value.trim()
  if (!kw) return
  showResults.value = false
  router.push({ path: '/graph', query: { search: kw } })
}

function enterGraph(label) {
  router.push({ path: '/graph', query: { label } })
}
</script>

<style scoped>
.home-page { flex: 1; }

.hero {
  position: relative;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
  padding: 80px 24px 64px;
  text-align: center;
  overflow: hidden;
}
.hero-bg {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at 50% 0%, rgba(59,130,246,0.15) 0%, transparent 60%);
}
.hero-content { position: relative; max-width: 720px; margin: 0 auto; }
.hero-title {
  font-size: 37px;
  font-weight: 700;
  color: var(--text-white);
  line-height: 1.25;
  margin-bottom: 16px;
}
.hero-title .accent { color: var(--accent-blue); }
.hero-desc {
  font-size: 14px;
  color: var(--text-light);
  margin-bottom: 36px;
  line-height: 1.7;
}
.hero-search {
  display: flex;
  gap: 12px;
  max-width: 560px;
  margin: 0 auto 36px;
}
.search-wrapper { flex: 1; position: relative; }
.search-input {
  width: 100%;
  box-sizing: border-box;
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.15);
  color: var(--text-white);
}
.search-input::placeholder { color: var(--text-light); }
.search-input:focus {
  border-color: var(--accent-blue);
  background: rgba(255, 255, 255, 0.12);
}
.search-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 4px;
  max-height: 260px;
  overflow-y: auto;
  background: #1e293b;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: var(--radius-md);
  box-shadow: 0 12px 32px rgba(0,0,0,0.35);
  z-index: 100;
}
.search-dropdown-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.12s;
}
.search-dropdown-item:hover { background: rgba(59,130,246,0.15); }
.sr-name { color: var(--text-white); }
.sr-cat {
  font-size: 10px;
  color: var(--text-light);
  background: rgba(255,255,255,0.08);
  padding: 2px 8px;
  border-radius: 10px;
}
.search-btn {
  flex-shrink: 0;
  background: var(--accent-blue);
  color: white;
}
.hero-stats {
  display: flex;
  gap: 24px;
  justify-content: center;
  flex-wrap: wrap;
}
.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 28px;
  border-radius: var(--radius-md);
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.08);
  cursor: pointer;
  transition: all 0.2s;
  min-width: 140px;
}
.stat-card:hover {
  background: rgba(255,255,255,0.12);
  border-color: rgba(59,130,246,0.3);
  transform: translateY(-2px);
}
.stat-num {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-white);
}
.stat-label {
  font-size: 12px;
  color: var(--accent-blue);
  margin-top: 4px;
  font-weight: 500;
}
.stat-sub {
  font-size: 11px;
  color: var(--text-light);
  margin-top: 4px;
}

/* Features */
.features {
  max-width: 1100px;
  margin: 0 auto;
  padding: 64px 24px;
}
.section-title {
  font-size: 23px;
  font-weight: 700;
  text-align: center;
  margin-bottom: 40px;
  color: var(--text-primary);
}
.feature-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
}
.feature-card {
  text-align: center;
  padding: 32px 20px;
  transition: transform 0.2s, box-shadow 0.2s;
}
.feature-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
}
.feature-icon { font-size: 28px; margin-bottom: 16px; color: var(--accent-blue); }
.feature-card h3 {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--text-primary);
}
.feature-card p {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}

@media (max-width: 768px) {
  .hero-title { font-size: 25px; }
  .hero-search { flex-direction: column; }
  .feature-grid { grid-template-columns: 1fr 1fr; }
}
</style>
