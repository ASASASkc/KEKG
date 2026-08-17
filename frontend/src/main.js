import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './styles/global.css'
import UiButton from './components/ui/UiButton.vue'
import UiCard from './components/ui/UiCard.vue'
import UiModal from './components/ui/UiModal.vue'
import UiTag from './components/ui/UiTag.vue'
import UiEmpty from './components/ui/UiEmpty.vue'
import UiLoading from './components/ui/UiLoading.vue'
import UiPagination from './components/ui/UiPagination.vue'

const app = createApp(App)

// 全局注册基础 UI 组件（M5-A）
app.component('UiButton', UiButton)
app.component('UiCard', UiCard)
app.component('UiModal', UiModal)
app.component('UiTag', UiTag)
app.component('UiEmpty', UiEmpty)
app.component('UiLoading', UiLoading)
app.component('UiPagination', UiPagination)

app.use(router)
app.mount('#app')
