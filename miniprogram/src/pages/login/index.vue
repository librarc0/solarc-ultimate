<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { copyWebLink } from '@/utils/webLink'

const auth = useAuthStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

// 若已有 token，直接跳过登录进入应用（App.vue onLaunch 已处理大多数情况，
// 此处作为保底：从绑定页 back 时也会触发）
onMounted(() => {
  const savedToken: string = uni.getStorageSync('access_token') || ''
  if (savedToken) {
    uni.reLaunch({ url: '/pages/home/index' })
  }
})

// ──────────────────────── 密码登录 ────────────────────────────

async function handlePasswordLogin() {
  error.value = ''
  if (!username.value.trim() || !password.value.trim()) {
    error.value = '请输入账号和密码'
    return
  }
  loading.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    goHome()
  } catch (e: unknown) {
    error.value = (e as Error).message || '登录失败，请检查账号密码'
  } finally {
    loading.value = false
  }
}

// ──────────────────────── 微信登录 ────────────────────────────

const wxLoading = ref(false)

function handleWxLogin() {
  wxLoading.value = true
  error.value = ''
  uni.login({
    success: async (res: UniApp.LoginRes) => {
      try {
        const result = await auth.wxLogin(res.code)
        if (result.next_step === 'ok') {
          goHome()
        } else {
          uni.navigateTo({
            url: `/pages/bind/index?bind_token=${encodeURIComponent(result.bind_token ?? '')}`,
          })
        }
      } catch (e: unknown) {
        error.value = (e as Error).message || '微信登录失败'
      } finally {
        wxLoading.value = false
      }
    },
    fail: () => {
      error.value = '获取微信登录凭证失败，请重试'
      wxLoading.value = false
    },
  })
}

// ──────────────────────── 跳原生首页 / 复制网页版 ─────────────────

function goHome() {
  uni.reLaunch({ url: '/pages/home/index' })
}

function goRegister() {
  copyWebLink('/register')
}

function goRankings() {
  uni.navigateTo({ url: '/pages/public-rankings/index' })
}
</script>

<template>
  <view class="login-page">
    <!-- 背景装饰层 -->
    <view class="bg-grid" />
    <view class="bg-orb bg-orb--left" />
    <view class="bg-orb bg-orb--right" />

    <!-- 浮动粒子（纯 CSS 动画模拟飞盘） -->
    <view class="particles-layer">
      <view class="disc disc-1" /><view class="disc disc-2" />
      <view class="disc disc-3" /><view class="disc disc-4" />
      <view class="disc disc-5" /><view class="disc disc-6" />
      <view class="disc disc-7" /><view class="disc disc-8" />
      <view class="disc disc-9" />
    </view>

    <!-- 登录卡片 -->
    <view class="login-card">
      <!-- Logo 区 -->
      <view class="logo-area">
        <view class="logo-ring">
          <view class="logo-ring-arc" />
          <image class="logo-img" src="/static/logo2.jpg" mode="aspectFit" />
        </view>
        <text class="title">SolArc-Ultimate</text>
        <text class="system-subtitle">飞盘队伍管理&战力评分系统</text>
      </view>

      <!-- 输入区 -->
      <view class="input-glass-wrap">
        <view class="input-row">
          <text class="input-icon">👤</text>
          <input
            v-model="username"
            class="input"
            placeholder="账号 / 用户名"
            placeholder-class="placeholder"
            :disabled="loading"
            @confirm="handlePasswordLogin"
          />
        </view>
        <view class="input-divider" />
        <view class="input-row">
          <text class="input-icon">🔒</text>
          <input
            v-model="password"
            class="input"
            type="password"
            placeholder="登录密码"
            placeholder-class="placeholder"
            :disabled="loading"
            @confirm="handlePasswordLogin"
          />
        </view>
      </view>

      <view v-if="error" class="error-text">{{ error }}</view>

      <!-- 主登录按钮 -->
      <button
        class="btn btn-primary"
        :loading="loading"
        :disabled="loading || wxLoading"
        @tap="handlePasswordLogin"
      >
        登&nbsp;&nbsp;录
      </button>

      <!-- 忘记密码 -->
      <view class="forgot-row">
        <text class="txt-link" @tap="copyWebLink('/forgot-password')">忘记密码 ›</text>
      </view>

      <!-- 分隔线 -->
      <view class="seg-divider" />

      <!-- 微信一键登录 -->
      <button
        class="btn btn-wechat"
        :loading="wxLoading"
        :disabled="loading || wxLoading"
        @tap="handleWxLogin"
      >
        微信一键登录
      </button>

      <!-- 注册 -->
      <button class="btn btn-outline" :disabled="loading || wxLoading" @tap="goRegister">
        注册 · 申请加入队伍
      </button>

      <!-- 排行榜入口 -->
      <button class="btn btn-rankings" @tap="goRankings">
        ◈ 联盟排行榜 · 无需登录
      </button>

      <!-- 版权 -->
      <view class="copyright">
        © <text class="copyright-arc">ARC</text> · All Rights Reserved.
      </view>
    </view>
  </view>
</template>

<style scoped>
/* ── 页面背景 ──────────────────────────────────────────── */
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40rpx 40rpx 60rpx;
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(ellipse 900rpx 600rpx at 10% 15%, rgba(14,165,233,0.22) 0%, transparent 55%),
    radial-gradient(ellipse 700rpx 500rpx at 90% 85%, rgba(29,78,216,0.18) 0%, transparent 55%),
    linear-gradient(135deg, #060c16 0%, #071425 40%, #040b18 100%);
}

/* 网格线 */
.bg-grid {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-image:
    linear-gradient(rgba(148,163,184,0.07) 1rpx, transparent 1rpx),
    linear-gradient(90deg, rgba(148,163,184,0.07) 1rpx, transparent 1rpx);
  background-size: 76rpx 76rpx;
  z-index: 0;
}

/* 光晕球 */
.bg-orb {
  position: fixed;
  border-radius: 50%;
  z-index: 0;
}
.bg-orb--left {
  width: 700rpx; height: 700rpx;
  top: -200rpx; left: -250rpx;
  background: radial-gradient(circle, rgba(14,165,233,0.14) 0%, transparent 70%);
}
.bg-orb--right {
  width: 600rpx; height: 600rpx;
  bottom: -150rpx; right: -200rpx;
  background: radial-gradient(circle, rgba(37,99,235,0.14) 0%, transparent 70%);
}

/* ── 飞盘粒子（纯 CSS，简化版） ─────────────────────────── */
.particles-layer {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  z-index: 0;
  pointer-events: none;
}

.disc {
  position: absolute;
  border-radius: 50%;
  border: 1.5rpx solid rgba(125,211,252,0.4);
  background: rgba(14,165,233,0.08);
}

.disc-1  { width:48rpx; height:48rpx; top:12%; left:8%;  animation: float1 7s ease-in-out infinite; }
.disc-2  { width:36rpx; height:36rpx; top:25%; left:82%; animation: float2 9s ease-in-out infinite 1s; }
.disc-3  { width:56rpx; height:56rpx; top:55%; left:6%;  animation: float3 8s ease-in-out infinite 0.5s; }
.disc-4  { width:30rpx; height:30rpx; top:70%; left:75%; animation: float1 11s ease-in-out infinite 2s; }
.disc-5  { width:44rpx; height:44rpx; top:40%; left:90%; animation: float2 6s ease-in-out infinite 1.5s; }
.disc-6  { width:28rpx; height:28rpx; top:85%; left:20%; animation: float3 10s ease-in-out infinite 0.8s; }
.disc-7  { width:52rpx; height:52rpx; top:8%;  left:55%; animation: float1 8.5s ease-in-out infinite 3s; }
.disc-8  { width:34rpx; height:34rpx; top:60%; left:45%; animation: float2 7.5s ease-in-out infinite 0.3s; }
.disc-9  { width:40rpx; height:40rpx; top:30%; left:30%; animation: float3 9.5s ease-in-out infinite 2.5s; }

@keyframes float1 {
  0%,100% { transform: translate(0, 0) rotate(0deg); opacity: 0.6; }
  33%     { transform: translate(28rpx, -40rpx) rotate(120deg); opacity: 1; }
  66%     { transform: translate(-20rpx, 30rpx) rotate(240deg); opacity: 0.7; }
}
@keyframes float2 {
  0%,100% { transform: translate(0, 0) rotate(0deg); opacity: 0.5; }
  40%     { transform: translate(-35rpx, 45rpx) rotate(-150deg); opacity: 0.9; }
  70%     { transform: translate(25rpx, -30rpx) rotate(-300deg); opacity: 0.6; }
}
@keyframes float3 {
  0%,100% { transform: translate(0, 0) rotate(0deg); opacity: 0.7; }
  50%     { transform: translate(40rpx, 50rpx) rotate(180deg); opacity: 1; }
}

/* ── 登录卡片 ────────────────────────────────────────────── */
.login-card {
  width: 100%;
  max-width: 680rpx;
  padding: 48rpx 40rpx 36rpx;
  border: 1rpx solid rgba(186,230,253,0.22);
  border-radius: 40rpx;
  background: linear-gradient(180deg, rgba(186,230,253,0.13) 0%, rgba(125,211,252,0.07) 100%);
  box-shadow:
    inset 0 1rpx 0 rgba(255,255,255,0.32),
    0 52rpx 100rpx rgba(8,18,36,0.5);
  position: relative;
  z-index: 2;
}

/* ── Logo 区 ─────────────────────────────────────────────── */
.logo-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 48rpx;
}

.logo-ring {
  width: 176rpx;
  height: 176rpx;
  border-radius: 50%;
  border: 2rpx solid rgba(186,230,253,0.3);
  background: linear-gradient(180deg, rgba(191,219,254,0.2) 0%, rgba(147,197,253,0.08) 100%);
  box-shadow:
    inset 0 2rpx 0 rgba(255,255,255,0.42),
    0 20rpx 56rpx rgba(14,165,233,0.22);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  margin-bottom: 24rpx;
  animation: pulseRing 4.5s ease-in-out infinite;
}

.logo-ring-arc {
  position: absolute;
  top: -6rpx; left: -6rpx; right: -6rpx; bottom: -6rpx;
  border-radius: 50%;
  border: 3rpx solid transparent;
  border-top-color: rgba(125,211,252,0.9);
  border-right-color: rgba(14,165,233,0.5);
  animation: spinArc 5s linear infinite;
}

.logo-img {
  width: 136rpx;
  height: 136rpx;
  border-radius: 28rpx;
}

.title {
  font-size: 52rpx;
  font-weight: 900;
  color: #e0f2fe;
  letter-spacing: 4rpx;
  text-shadow: 0 0 36rpx rgba(14,165,233,0.5);
}

.system-subtitle {
  font-size: 22rpx;
  color: rgba(186,230,253,0.7);
  letter-spacing: 3rpx;
  margin-top: 10rpx;
}

/* ── 输入框 ──────────────────────────────────────────────── */
.input-glass-wrap {
  border: 1rpx solid rgba(186,230,253,0.22);
  border-radius: 28rpx;
  background: linear-gradient(180deg, rgba(186,230,253,0.14) 0%, rgba(125,211,252,0.08) 100%);
  box-shadow:
    inset 0 2rpx 0 rgba(255,255,255,0.38),
    inset 0 -32rpx 56rpx rgba(30,41,59,0.2);
  overflow: hidden;
  margin-bottom: 24rpx;
}

.input-row {
  display: flex;
  align-items: center;
  padding: 0 28rpx;
  height: 100rpx;
}

.input-icon {
  font-size: 34rpx;
  margin-right: 18rpx;
  opacity: 0.6;
}

.input {
  flex: 1;
  height: 100rpx;
  color: #e5efff;
  font-size: 30rpx;
  background: transparent;
}

.placeholder {
  color: rgba(186,230,253,0.35);
}

.input-divider {
  height: 1rpx;
  margin: 0 28rpx;
  background: rgba(186,230,253,0.2);
}

.error-text {
  color: #f87171;
  font-size: 26rpx;
  margin-bottom: 20rpx;
  text-align: center;
}

/* ── 按钮 ────────────────────────────────────────────────── */
.btn {
  width: 100%;
  height: 96rpx;
  border-radius: 20rpx;
  font-size: 32rpx;
  font-weight: 600;
  border: none;
  margin-bottom: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.btn::after { border: none; }

.btn-primary {
  background: linear-gradient(135deg, #0ea5e9 0%, #1d4ed8 100%);
  color: #ffffff;
  font-size: 36rpx;
  letter-spacing: 6rpx;
  box-shadow: 0 12rpx 32rpx rgba(14,165,233,0.35);
  margin-bottom: 0;
}

.forgot-row {
  display: flex;
  justify-content: flex-end;
  margin: 14rpx 0 24rpx;
}

.txt-link {
  color: rgba(125,211,252,0.7);
  font-size: 26rpx;
}

.seg-divider {
  height: 1rpx;
  background: rgba(186,230,253,0.18);
  margin: 8rpx 0 28rpx;
}

.btn-wechat {
  background: #07c160;
  color: #ffffff;
  letter-spacing: 2rpx;
}

.btn-outline {
  background: transparent;
  border: 1rpx solid rgba(186,230,253,0.32);
  color: rgba(186,230,253,0.75);
  letter-spacing: 2rpx;
}

.btn-rankings {
  background: transparent;
  border: 1rpx solid rgba(125,211,252,0.25);
  color: rgba(125,211,252,0.6);
  font-size: 27rpx;
  height: 80rpx;
  letter-spacing: 2rpx;
}

/* ── 版权 ────────────────────────────────────────────────── */
.copyright {
  text-align: center;
  color: rgba(186,230,253,0.3);
  font-size: 22rpx;
  margin-top: 20rpx;
  letter-spacing: 2rpx;
}

.copyright-arc {
  color: rgba(125,211,252,0.6);
  font-weight: 700;
}

/* ── 动画 ────────────────────────────────────────────────── */
@keyframes pulseRing {
  0%,100% { box-shadow: inset 0 2rpx 0 rgba(255,255,255,0.42), 0 20rpx 56rpx rgba(14,165,233,0.22); }
  50%     { box-shadow: inset 0 2rpx 0 rgba(255,255,255,0.42), 0 20rpx 72rpx rgba(14,165,233,0.4); }
}

@keyframes spinArc {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
</style>
