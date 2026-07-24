<script setup lang="ts">
import { ref } from 'vue'
import { WEB_ORIGIN } from '@/utils/webLink'
import StateBlock from '@/components/StateBlock.vue'

const loadingDoc = ref('')
const error = ref('')

const docs = [
  {
    key: 'rules',
    title: 'WFDF 飞盘规则手册',
    desc: '中英文对照 2025-2028 规则 PDF',
    path: '/docs-files/中英文对照-2025-2028-WFDF-Rules-of-Ultimate-ver1.0.pdf',
  },
  {
    key: 'drills',
    title: 'Skills & Drills 训练手册',
    desc: 'USAU 技能与训练 PDF',
    path: '/docs-files/USAU_SkillsDrills.pdf',
  },
]

function openPdf(doc: typeof docs[number]) {
  loadingDoc.value = doc.key
  error.value = ''
  uni.downloadFile({
    url: `${WEB_ORIGIN}${doc.path}`,
    success(res) {
      if (res.statusCode !== 200) {
        error.value = `下载失败 (${res.statusCode})`
        return
      }
      uni.openDocument({
        filePath: res.tempFilePath,
        fileType: 'pdf',
        showMenu: true,
        fail(err) {
          error.value = err.errMsg || 'PDF 打开失败'
        },
      })
    },
    fail(err) {
      error.value = err.errMsg || 'PDF 下载失败'
    },
    complete() {
      loadingDoc.value = ''
    },
  })
}
</script>

<template>
  <view class="page">
    <view class="header">
      <text class="title">规则与手册</text>
      <text class="subtitle">PDF 会使用微信文档阅读器打开</text>
    </view>

    <StateBlock v-if="error" title="打开失败" :desc="error" action-text="重试" @retry="error = ''" />

    <view class="doc-list">
      <view v-for="doc in docs" :key="doc.key" class="doc-card" @tap="openPdf(doc)">
        <view>
          <text class="doc-title">{{ doc.title }}</text>
          <text class="doc-desc">{{ doc.desc }}</text>
        </view>
        <text class="doc-action">{{ loadingDoc === doc.key ? '打开中' : '打开' }}</text>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 34rpx 0;
  background: linear-gradient(180deg, #07111f 0%, #111827 100%);
}

.header {
  padding: 24rpx 32rpx;
}

.title {
  display: block;
  color: #f8fafc;
  font-size: 44rpx;
  font-weight: 900;
}

.subtitle {
  display: block;
  margin-top: 8rpx;
  color: #94a3b8;
  font-size: 25rpx;
}

.doc-list {
  margin: 0 28rpx;
}

.doc-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20rpx;
  margin-bottom: 16rpx;
  padding: 26rpx;
  border: 1rpx solid rgba(148, 163, 184, 0.16);
  border-radius: 18rpx;
  background: rgba(15, 23, 42, 0.82);
}

.doc-title {
  display: block;
  color: #f8fafc;
  font-size: 30rpx;
  font-weight: 850;
}

.doc-desc {
  display: block;
  margin-top: 8rpx;
  color: #94a3b8;
  font-size: 24rpx;
}

.doc-action {
  color: #38bdf8;
  font-size: 25rpx;
  white-space: nowrap;
}
</style>
