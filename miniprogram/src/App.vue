<script setup lang="ts">
import { onLaunch } from '@dcloudio/uni-app'

// 冷启动时若已有 token，直接进入原生轻量首页（跳过登录页）
onLaunch(() => {
  const token: string = uni.getStorageSync('access_token') || ''
  if (token) {
    uni.reLaunch({ url: '/pages/home/index' })
  }
})
</script>

<template></template>

<style>
page {
  background-color: #1a1a2e;
  color: #ffffff;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  box-sizing: border-box;
}
</style>
