// Copyright 2026 ARC. All Rights Reserved.
// EaglesPower — Frisbee Team Rating System
import './assets/main.css'
import 'vant/lib/index.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Vant from 'vant'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(Vant)

// 启动时若有 token，先从服务端恢复用户状态再挂载，保证路由守卫能正确处理
const authStore = useAuthStore()
const bootstrap = authStore.isLoggedIn
  ? Promise.all([
      authStore.fetchMe(),
      authStore.fetchContext(),
    ]).catch(() => authStore.logout())
  : Promise.resolve()

bootstrap.then(() => app.mount('#app'))
