<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import DesktopWrapper from '@/components/DesktopWrapper.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

// 页面刷新后 token 存在但内存状态为空，需要重新拉取用户信息和队伍上下文
onMounted(async () => {
  const needsUser = !auth.user
  const needsContext = !auth.userContext || auth.availableTeams.length === 0
  if (auth.isLoggedIn && (needsUser || needsContext)) {
    try {
      if (needsUser) {
        await auth.fetchMe()
      }
      if (needsContext) {
        await auth.fetchContext()
      }
    } catch {
      // token 失效 → 静默登出，路由守卫会跳转登录页
      auth.logout()
    }
  }
})
</script>

<template>
  <DesktopWrapper>
    <RouterView />
  </DesktopWrapper>
</template>

<style>
/* 鍏ㄥ眬閲嶇疆锛氱Щ鍔ㄧ浼樺厛锛?100% 楂樺害 */
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body, #app {
  height: 100%;
  width: 100%;
  background: #f7f8fa;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
</style>
