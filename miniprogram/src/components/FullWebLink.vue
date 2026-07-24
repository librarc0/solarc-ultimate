<script setup lang="ts">
import { copyWebLink } from '@/utils/webLink'

const props = withDefaults(defineProps<{
  title?: string
  desc?: string
  path?: string
  compact?: boolean
}>(), {
  title: '完整功能',
  desc: '微信小程序暂不能直接打开完整网页，请复制网址后在微信聊天或浏览器中打开。',
  path: '/',
  compact: true,
})
</script>

<template>
  <view class="web-link-card" :class="{ compact: props.compact }">
    <view class="web-link-copy">
      <text class="web-link-title">{{ props.title }}</text>
      <text class="web-link-desc">{{ props.desc }}</text>
    </view>
    <button class="web-link-btn" @tap="copyWebLink(props.path)">复制网址</button>
  </view>
</template>

<style scoped>
.web-link-card {
  display: flex;
  align-items: center;
  gap: 18rpx;
  margin: 0 28rpx 18rpx;
  padding: 18rpx 20rpx;
  border: 1rpx solid rgba(125, 211, 252, 0.22);
  border-radius: 14rpx;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.16), rgba(245, 158, 11, 0.08));
}

.web-link-copy {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.web-link-title {
  color: #e0f2fe;
  font-size: 26rpx;
  font-weight: 700;
}

.web-link-desc {
  color: rgba(203, 213, 225, 0.72);
  font-size: 21rpx;
  line-height: 1.45;
}

.web-link-btn {
  width: 132rpx;
  height: 58rpx;
  line-height: 58rpx;
  padding: 0;
  border-radius: 12rpx;
  border: 0;
  background: #0ea5e9;
  color: #fff;
  font-size: 23rpx;
}

.web-link-btn::after {
  border: none;
}
</style>
