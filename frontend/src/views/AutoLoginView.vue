<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

/**
 * AutoLoginView — 微信小程序 web-view 自动登录入口
 *
 * 小程序登录后拼接 URL: /auto-login?token=xxx&redirect=/home
 * 本页读取 token → 写入 localStorage → 刷新 auth store → 跳转目标页
 *
 * 无 token 时静默跳转登录页。
 */
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

onMounted(async () => {
  const token = route.query.token as string | undefined
  const redirect = (route.query.redirect as string | undefined) || '/home'

  if (!token) {
    router.replace('/login')
    return
  }

  // 写入 localStorage（与 auth store 保持同步）
  localStorage.setItem('access_token', token)
  // 重新初始化 store state
  auth.token = token
  try {
    await auth.fetchMe()
  } catch {
    // token 无效则清理并跳登录
    localStorage.removeItem('access_token')
    auth.token = null
    router.replace('/login')
    return
  }

  router.replace(redirect)
})
</script>

<template>
  <!-- 白屏跳转，无 UI -->
  <div />
</template>
