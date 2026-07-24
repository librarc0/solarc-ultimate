<template>
  <div></div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// 旧的链接式重置已停用，统一跳转到验证码三步流程
onMounted(() => {
  router.replace('/forgot-password')
})
</script>
