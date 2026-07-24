<script setup lang="ts">
withDefaults(defineProps<{
  title: string
  desc?: string
  actionText?: string
  loading?: boolean
}>(), {
  desc: '',
  actionText: '',
  loading: false,
})

const emit = defineEmits<{
  retry: []
}>()
</script>

<template>
  <view class="state">
    <view v-if="loading" class="spinner" />
    <text class="state-title">{{ title }}</text>
    <text v-if="desc" class="state-desc">{{ desc }}</text>
    <button v-if="actionText" class="state-action" @tap="emit('retry')">{{ actionText }}</button>
  </view>
</template>

<style scoped>
.state {
  margin: 24rpx 28rpx;
  padding: 42rpx 26rpx;
  border-radius: 18rpx;
  background: rgba(15, 23, 42, 0.78);
  border: 1rpx solid rgba(148, 163, 184, 0.16);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14rpx;
}

.state-title {
  color: #e2e8f0;
  font-size: 28rpx;
  font-weight: 700;
}

.state-desc {
  color: #94a3b8;
  font-size: 24rpx;
  text-align: center;
  line-height: 1.5;
}

.state-action {
  width: 168rpx;
  height: 62rpx;
  line-height: 62rpx;
  padding: 0;
  border-radius: 14rpx;
  background: #f59e0b;
  color: #111827;
  font-size: 25rpx;
  font-weight: 700;
}

.state-action::after {
  border: none;
}

.spinner {
  width: 38rpx;
  height: 38rpx;
  border-radius: 50%;
  border: 4rpx solid rgba(148, 163, 184, 0.26);
  border-top-color: #38bdf8;
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
