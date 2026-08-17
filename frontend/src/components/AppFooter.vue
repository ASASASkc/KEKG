<template>
  <footer class="app-footer">
    <div class="footer-inner">
      <div class="footer-left">
        <span class="footer-brand">KEKG</span>
        <span class="footer-desc">知识图谱管理与可视化系统</span>
      </div>
      <div class="footer-right">
        <span>Powered by Python / Flask / Vue3 / ECharts</span>
      </div>
    </div>
  </footer>
</template>

<style scoped>
.app-footer {
  background: var(--bg-footer);
  padding: 20px 0;
  color: var(--text-light);
  font-size: 11px;
  margin-top: auto;
}
.footer-inner {
  max-width: 1300px;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.footer-left { display: flex; align-items: center; gap: 12px; }
.footer-brand { font-weight: 700; color: var(--text-white); font-size: 14px; }
</style>
