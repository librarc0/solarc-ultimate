<template>
  <div class="ra-login-page">
    <div class="logo-area">
      <van-icon name="medal-o" size="48" color="#1677ff" />
      <div class="logo-title">排行榜管理后台</div>
      <div class="logo-sub">SDL Pool · SolArc-Ultimate</div>
    </div>

    <van-cell-group inset>
      <van-field
        v-model="username"
        label="管理员"
        placeholder="请输入用户名"
        left-icon="manager-o"
      />
      <van-field
        v-model="password"
        label="密码"
        type="password"
        placeholder="请输入密码"
        left-icon="lock-o"
        @keyup.enter="doLogin"
      />
    </van-cell-group>

    <div style="padding: 16px">
      <van-button
        type="primary"
        block
        :loading="loading"
        @click="doLogin"
      >登录</van-button>
    </div>

    <div class="back-link" @click="router.push({ name: 'public-rankings' })">
      ← 返回公开排行榜
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useRankingAdminStore } from '@/stores/rankingAdmin'

const router = useRouter()
const store = useRankingAdminStore()

const username = ref('')
const password = ref('')
const loading = ref(false)

async function doLogin() {
  if (!username.value || !password.value) {
    showToast('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await store.login(username.value, password.value)
    router.replace({ name: 'ranking-admin' })
  } catch {
    showToast('用户名或密码错误')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.ra-login-page {
  min-height: 100vh;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
  padding-top: 60px;
}
.logo-area {
  text-align: center;
  margin-bottom: 32px;
}
.logo-title { font-size: 20px; font-weight: 700; color: #1a1a1a; margin-top: 8px; }
.logo-sub { font-size: 13px; color: #888; margin-top: 4px; }
.back-link {
  text-align: center;
  color: #1677ff;
  font-size: 14px;
  margin-top: 16px;
  cursor: pointer;
}
</style>
