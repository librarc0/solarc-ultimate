<template>
  <div class="register-page">
    <van-nav-bar title="创建账号" left-arrow @click-left="$router.back()" />
    <van-form ref="formRef">
      <van-cell-group inset>
        <van-field
          v-model="form.username"
          name="username"
          label="用户名"
          placeholder="6-20位字母数字，用于登录"
          :rules="[{ required: true, message: '请填写用户名' }, { pattern: /^[a-zA-Z0-9]{6,20}$/, message: '必须为6-20位字母数字' }]"
        />
        <van-field
          v-model="form.email"
          name="email"
          label="邮箱"
          type="email"
          placeholder="用于找回密码（必填）"
          :rules="[{ required: true, message: '请填写邮箱' }]"
        />
        <van-field
          v-model="form.display_name"
          name="display_name"
          label="展示名称"
          placeholder="排行榜上显示的名字"
          :rules="[{ required: true, message: '请填写展示名称' }]"
        />
        <van-field
          v-model="form.password"
          type="password"
          name="password"
          label="密码"
          placeholder="至少8位"
          :rules="[{ required: true, message: '请填写密码' }, { validator: (v) => v.length >= 8, message: '密码至少8位' }]"
        />
        <van-field
          v-model="form.confirm_password"
          type="password"
          name="confirm_password"
          label="确认密码"
          placeholder="请再次输入密码"
          :rules="[
            { required: true, message: '请再次输入密码' },
            { validator: (v) => v === form.password, message: '两次输入的密码不一致' }
          ]"
        />
      </van-cell-group>
      <div style="margin: 16px">
        <van-button round block type="primary" :loading="loading" @click="handleRegister">
          注册
        </van-button>
      </div>
    </van-form>
    <div style="padding: 0 16px; color: #888; font-size: 13px; text-align: center;">
      注册后登录，再加入或创建你的队伍
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showNotify } from 'vant'
import api from '@/api'

const router = useRouter()
const loading = ref(false)
const formRef = ref()
const form = reactive({ username: '', email: '', display_name: '', password: '', confirm_password: '' })

async function handleRegister() {
  try {
    await formRef.value?.validate()
  } catch {
    return // 校验失败，不提交
  }
  loading.value = true
  try {
    if (form.password !== form.confirm_password) {
      showToast('两次输入的密码不一致')
      return
    }
    await api.post('/auth/register', { ...form })
    showNotify({ type: 'success', message: '注册成功！请用新账号登录', duration: 3000 })
    router.push('/login')
  } catch (e: any) {
    const msg = e.response?.data?.detail ?? '注册失败，请稍后重试'
    showNotify({ type: 'danger', message: msg, duration: 4000 })
  } finally {
    loading.value = false
  }
}
</script>

