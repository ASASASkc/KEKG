<template>
  <div class="page-container notfound-wrap">
    <div class="card notfound-card">
      <div class="notfound-code">404</div>
      <p class="notfound-text">页面不存在或已被移除</p>
      <router-link to="/" class="btn btn-primary">返回首页</router-link>
    </div>
  </div>
</template>

<style scoped>
.notfound-wrap {
  min-height: 70vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.notfound-card {
  text-align: center;
  padding: 48px 64px;
  max-width: 480px;
}
.notfound-code {
  font-size: 96px;
  font-weight: 700;
  line-height: 1;
  color: var(--accent-blue);
}
.notfound-text {
  margin: 16px 0 24px;
  font-size: 16px;
  color: var(--text-secondary);
}
</style>
