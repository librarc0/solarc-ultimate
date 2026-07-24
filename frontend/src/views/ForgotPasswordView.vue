<template>
  <div class="forgot-page">
    <van-nav-bar title="忘记密码" left-arrow @click-left="$router.push('/login')" />

    <div class="content">

      <!-- 多次失败：提示联系管理员 -->
      <template v-if="contactAdmin">
        <div class="notice-card danger">
          <van-icon name="warning" color="#ef4444" size="52" />
          <h2>请联系管理员</h2>
          <p class="desc">
            多次验证失败，无法继续自助重置。<br />
            请联系队伍管理员，由管理员协助重置密码。
          </p>
          <van-button round block type="primary" @click="$router.push('/login')">
            返回登录
          </van-button>
        </div>
      </template>

      <!-- 重置成功 -->
      <template v-else-if="step === 'done'">
        <div class="notice-card success">
          <van-icon name="checked" color="#10b981" size="52" />
          <h2>密码已重置</h2>
          <p class="desc">你的密码已成功更新，请使用新密码登录。</p>
          <van-button round block type="primary" @click="$router.push('/login')">
            前往登录
          </van-button>
        </div>
      </template>

      <!-- 步骤 1：验证身份 -->
      <template v-else-if="step === 'identity'">
        <div class="step-header">
          <div class="step-indicator">
            <span class="step-dot active">1</span>
            <span class="step-line"></span>
            <span class="step-dot">2</span>
            <span class="step-line"></span>
            <span class="step-dot">3</span>
          </div>
          <p class="step-label">第一步：验证身份</p>
        </div>
        <div class="card">
          <p class="hint">输入注册时的用户名和邮箱，系统将发送 6 位验证码到邮箱</p>
          <van-form @submit="submitIdentity">
            <van-cell-group inset>
              <van-field
                v-model="username"
                name="username"
                label="用户名"
                placeholder="请输入账号用户名"
                clearable
                :rules="[{ required: true, message: '请输入用户名' }]"
              />
              <van-field
                v-model="email"
                name="email"
                label="邮箱"
                type="email"
                placeholder="请输入注册邮箱"
                clearable
                :rules="[
                  { required: true, message: '请输入邮箱' },
                  { pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, message: '邮箱格式不正确' }
                ]"
              />
            </van-cell-group>
            <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>
            <div class="btn-wrap">
              <van-button round block type="primary" native-type="submit" :loading="loading" loading-text="发送中...">
                发送验证码
              </van-button>
              <van-button round block plain @click="$router.push('/login')">返回登录</van-button>
            </div>
          </van-form>
        </div>
      </template>

      <!-- 步骤 2：输入验证码 -->
      <template v-else-if="step === 'code'">
        <div class="step-header">
          <div class="step-indicator">
            <span class="step-dot done">✓</span>
            <span class="step-line done"></span>
            <span class="step-dot active">2</span>
            <span class="step-line"></span>
            <span class="step-dot">3</span>
          </div>
          <p class="step-label">第二步：输入验证码</p>
        </div>
        <div class="card">
          <p class="hint">验证码已发送至 <strong>{{ maskedEmail }}</strong>，请在 15 分钟内输入</p>
          <van-form @submit="submitCode">
            <van-cell-group inset>
              <van-field
                v-model="code"
                name="code"
                label="验证码"
                placeholder="请输入 6 位数字验证码"
                type="digit"
                maxlength="6"
                clearable
                :rules="[
                  { required: true, message: '请输入验证码' },
                  { pattern: /^\d{6}$/, message: '验证码为 6 位数字' }
                ]"
              />
            </van-cell-group>
            <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>
            <div class="btn-wrap">
              <van-button round block type="primary" native-type="submit" :loading="loading" loading-text="验证中...">
                验证
              </van-button>
              <van-button round block plain @click="backToIdentity">重新发送验证码</van-button>
            </div>
          </van-form>
        </div>
      </template>

      <!-- 步骤 3：设置新密码 -->
      <template v-else-if="step === 'password'">
        <div class="step-header">
          <div class="step-indicator">
            <span class="step-dot done">✓</span>
            <span class="step-line done"></span>
            <span class="step-dot done">✓</span>
            <span class="step-line done"></span>
            <span class="step-dot active">3</span>
          </div>
          <p class="step-label">第三步：设置新密码</p>
        </div>
        <div class="card">
          <p class="hint">验证成功！请设置你的新密码（至少 8 位）</p>
          <van-form @submit="submitPassword">
            <van-cell-group inset>
              <van-field
                v-model="newPassword"
                name="newPassword"
                type="password"
                label="新密码"
                placeholder="至少 8 位"
                :rules="[
                  { required: true, message: '请输入新密码' },
                  { validator: (v) => v.length >= 8, message: '密码至少 8 位' }
                ]"
              />
              <van-field
                v-model="confirmPassword"
                name="confirmPassword"
                type="password"
                label="确认密码"
                placeholder="再次输入新密码"
                :rules="[
                  { required: true, message: '请再次输入密码' },
                  { validator: checkConfirm, message: '两次密码不一致' }
                ]"
              />
            </van-cell-group>
            <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>
            <div class="btn-wrap">
              <van-button round block type="primary" native-type="submit" :loading="loading" loading-text="提交中...">
                确认重置密码
              </van-button>
            </div>
          </van-form>
        </div>
      </template>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import api from '@/api'

type Step = 'identity' | 'code' | 'password' | 'done'

const MAX_FAILURES = 3

const step = ref<Step>('identity')
const contactAdmin = ref(false)

// 表单字段
const username = ref('')
const email = ref('')
const code = ref('')
const newPassword = ref('')
const confirmPassword = ref('')

// 状态
const loading = ref(false)
const errorMsg = ref('')
const confirmedToken = ref('')

// 各步骤失败计数
const identityFailures = ref(0)
const codeFailures = ref(0)
const passwordFailures = ref(0)

const maskedEmail = computed(() => {
  const e = email.value
  const at = e.indexOf('@')
  if (at <= 1) return e
  return e[0] + '****' + e.slice(at)
})

function checkConfirm(val: string) {
  return val === newPassword.value
}

function backToIdentity() {
  step.value = 'identity'
  code.value = ''
  errorMsg.value = ''
}

// 步骤一：验证用户名+邮箱
async function submitIdentity() {
  loading.value = true
  errorMsg.value = ''
  try {
    await api.post('/auth/forgot-password', {
      username: username.value,
      email: email.value,
    })
    identityFailures.value = 0
    step.value = 'code'
  } catch (e: any) {
    identityFailures.value++
    const detail: string = e.response?.data?.detail ?? '验证失败，请稍后重试'
    if (detail.includes('未配置邮件')) {
      contactAdmin.value = true
      return
    }
    errorMsg.value = detail
    if (identityFailures.value >= MAX_FAILURES) {
      contactAdmin.value = true
    }
  } finally {
    loading.value = false
  }
}

// 步骤二：验证 6 位验证码
async function submitCode() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await api.post('/auth/verify-reset-code', {
      email: email.value,
      code: code.value,
    })
    confirmedToken.value = res.data.confirmed_token
    codeFailures.value = 0
    step.value = 'password'
  } catch (e: any) {
    codeFailures.value++
    errorMsg.value = e.response?.data?.detail ?? '验证码错误，请重试'
    if (codeFailures.value >= MAX_FAILURES) {
      contactAdmin.value = true
    }
  } finally {
    loading.value = false
  }
}

// 步骤三：设置新密码
async function submitPassword() {
  loading.value = true
  errorMsg.value = ''
  try {
    await api.post('/auth/reset-password', {
      confirmed_token: confirmedToken.value,
      new_password: newPassword.value,
      confirm_password: confirmPassword.value,
    })
    passwordFailures.value = 0
    step.value = 'done'
  } catch (e: any) {
    passwordFailures.value++
    errorMsg.value = e.response?.data?.detail ?? '重置失败，请重试'
    if (passwordFailures.value >= MAX_FAILURES) {
      contactAdmin.value = true
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.forgot-page {
  min-height: 100dvh;
  background: #f3f6fb;
}

.content {
  padding: 20px 16px 48px;
}

/* 步骤指示器 */
.step-header {
  text-align: center;
  margin-bottom: 18px;
}

.step-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 10px;
}

.step-dot {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #e5e7eb;
  color: #9ca3af;
  font-size: 14px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.step-dot.active {
  background: #2563eb;
  color: #fff;
}

.step-dot.done {
  background: #10b981;
  color: #fff;
  font-size: 16px;
}

.step-line {
  width: 44px;
  height: 2px;
  background: #e5e7eb;
}

.step-line.done {
  background: #10b981;
}

.step-label {
  color: #374151;
  font-size: 15px;
  font-weight: 600;
  margin: 0;
}

/* 卡片 */
.card {
  background: #fff;
  border-radius: 14px;
  padding: 20px 0 16px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 4px 20px rgba(15, 23, 42, 0.06);
}

.hint {
  font-size: 13px;
  color: #6b7280;
  text-align: center;
  margin: 0 16px 16px;
  line-height: 1.6;
}

.btn-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 16px 4px;
}

.error-msg {
  color: #ef4444;
  font-size: 13px;
  margin: 8px 16px 0;
  background: #fef2f2;
  padding: 10px 12px;
  border-radius: 8px;
}

/* 通知卡片 */
.notice-card {
  background: #fff;
  border-radius: 14px;
  padding: 32px 20px;
  text-align: center;
  border: 1px solid #e5e7eb;
  box-shadow: 0 8px 26px rgba(15, 23, 42, 0.06);
}

.notice-card.danger {
  border-color: #fca5a5;
}

.notice-card.success {
  border-color: #6ee7b7;
}

.notice-card h2 {
  margin: 14px 0 10px;
  font-size: 20px;
  color: #111827;
}

.notice-card .desc {
  font-size: 14px;
  color: #4b5563;
  margin: 0 0 20px;
  line-height: 1.75;
}
</style>
