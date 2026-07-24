<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/api/request'

const auth = useAuthStore()

// bind_token 由登录页通过 URL 参数传入
const bindToken = ref('')
onMounted(() => {
  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1] as unknown as { options: Record<string, string> }
  bindToken.value = decodeURIComponent(currentPage.options?.bind_token ?? '')
  if (!bindToken.value) {
    uni.showToast({ title: '参数错误，请重新登录', icon: 'none' })
    setTimeout(() => uni.reLaunch({ url: '/pages/login/index' }), 1500)
  }
})

// ─────────── 绑定已有账号 ────────
const existUsername = ref('')
const existPassword = ref('')
const bindLoading = ref(false)
const bindError = ref('')

async function handleBindExisting() {
  bindError.value = ''
  if (!existUsername.value.trim() || !existPassword.value.trim()) {
    bindError.value = '请输入账号和密码'
    return
  }
  bindLoading.value = true
  try {
    const res = await api.post<{ access_token: string; role: string; display_name: string }>(
      '/auth/wx-bind-existing',
      {
        bind_token: bindToken.value,
        username: existUsername.value.trim(),
        password: existPassword.value,
      },
    )
    auth.setTokenFromBind(res.access_token, res.role)
    await auth.fetchMe()
    goHome()
  } catch (e: unknown) {
    bindError.value = (e as Error).message || '绑定失败'
  } finally {
    bindLoading.value = false
  }
}


function goHome() {
  uni.reLaunch({ url: '/pages/home/index' })
}
</script>

<template>
  <view class="container">
    <view class="header">
      <text class="logo">🦅</text>
      <text class="title">绑定账号</text>
      <text class="subtitle">请输入你在系统里的用户名（或邮箱）和密码，完成微信绑定</text>
    </view>

    <!-- 绑定已有账号 -->
    <view class="form">
      <view class="input-group">
        <input
          v-model="existUsername"
          class="input"
          placeholder="系统用户名 / 邮箱"
          placeholder-class="placeholder"
          :disabled="bindLoading"
        />
      </view>
      <view class="input-group">
        <input
          v-model="existPassword"
          class="input"
          type="password"
          placeholder="原密码"
          placeholder-class="placeholder"
          :disabled="bindLoading"
        />
      </view>
      <view v-if="bindError" class="error-text">{{ bindError }}</view>
      <button class="btn btn-primary" :loading="bindLoading" :disabled="bindLoading" @tap="handleBindExisting">
        确认绑定
      </button>
    </view>
  </view>
</template>

<style scoped>
.container {
  min-height: 100vh;
  background: linear-gradient(160deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80rpx 60rpx 40rpx;
}

.header {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 60rpx;
}

.logo { font-size: 80rpx; margin-bottom: 16rpx; }
.title { font-size: 48rpx; font-weight: 700; color: #e8b86d; }
.subtitle { font-size: 26rpx; color: #8899aa; margin-top: 12rpx; text-align: center; }

/* 表单 */
.form { width: 100%; }

.input-group { margin-bottom: 28rpx; }

.input {
  width: 100%;
  height: 96rpx;
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 16rpx;
  padding: 0 32rpx;
  color: #ffffff;
  font-size: 32rpx;
}

.placeholder { color: #556677; }

.error-text {
  color: #ff6b6b;
  font-size: 26rpx;
  margin-bottom: 20rpx;
  text-align: center;
}

.btn {
  width: 100%;
  height: 96rpx;
  border-radius: 16rpx;
  font-size: 34rpx;
  font-weight: 600;
  border: none;
}

.btn-primary {
  background: linear-gradient(90deg, #e8b86d, #d4a453);
  color: #1a1a2e;
}
</style>
