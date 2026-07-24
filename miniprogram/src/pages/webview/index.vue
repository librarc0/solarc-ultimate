<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'

/**
 * WebView 包装页 — 承载所有业务页面
 *
 * URL 参数：
 *   token    登录页传入的 JWT（首次进入）
 *   redirect 目标路径，如 /home，传递给 Web 端 /auto-login
 */

const WEB_ORIGIN =
  (import.meta.env?.VITE_WEB_ORIGIN as string) ?? 'http://localhost:5173'

const webviewUrl = ref('')

onLoad((options) => {
  const token: string = decodeURIComponent((options as Record<string, string>)?.token ?? '')
  const redirect: string = decodeURIComponent((options as Record<string, string>)?.redirect ?? '/home')

  if (token) {
    // 携带 token 走自动登录入口
    webviewUrl.value = `${WEB_ORIGIN}/auto-login?token=${encodeURIComponent(token)}&redirect=${encodeURIComponent(redirect)}`
  } else {
    // 已有本地 token（重新打开小程序），直接跳目标页
    const savedToken: string = uni.getStorageSync('access_token') || ''
    if (savedToken) {
      webviewUrl.value = `${WEB_ORIGIN}/auto-login?token=${encodeURIComponent(savedToken)}&redirect=${encodeURIComponent(redirect)}`
    } else {
      uni.reLaunch({ url: '/pages/login/index' })
    }
  }
})

// 接收 Web 端 postMessage（用于退出登录等跨层通信）
function onWebviewMessage(e: { detail: { data: Array<Record<string, unknown>> } }) {
  const msgs = e.detail.data
  if (!Array.isArray(msgs)) return
  for (const msg of msgs) {
    if (msg.action === 'logout') {
      uni.removeStorageSync('access_token')
      uni.removeStorageSync('user_role')
      uni.reLaunch({ url: '/pages/login/index' })
    }
  }
}
</script>

<template>
  <view class="page">
    <web-view
      v-if="webviewUrl"
      :src="webviewUrl"
      @message="onWebviewMessage"
    />
    <!-- 加载中占位 -->
    <view v-else class="loading">
      <text class="loading-text">正在载入…</text>
    </view>
  </view>
</template>

<style scoped>
.page {
  width: 100%;
  height: 100vh;
  background: #1a1a2e;
}

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
}

.loading-text {
  color: #8899aa;
  font-size: 28rpx;
}
</style>
