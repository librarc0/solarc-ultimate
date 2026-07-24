<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { onPullDownRefresh, onReachBottom } from '@dcloudio/uni-app'
import api from '@/api/request'
import type { MatchListItem } from '@/api/types'
import FullWebLink from '@/components/FullWebLink.vue'
import StateBlock from '@/components/StateBlock.vue'

const filters = [
  { label: '全部', value: '' },
  { label: '已通过', value: 'approved' },
  { label: '待审批', value: 'pending_approval' },
  { label: '草稿', value: 'draft' },
]

const selectedStatus = ref('')
const matches = ref<MatchListItem[]>([])
const page = ref(1)
const pageSize = 20
const hasMore = ref(true)
const loading = ref(true)
const loadingMore = ref(false)
const error = ref('')

function statusLabel(status: string) {
  const map: Record<string, string> = {
    approved: '已通过',
    pending_approval: '待审批',
    rejected: '已拒绝',
    draft: '草稿',
  }
  return map[status] ?? status
}

function typeLabel(type: string) {
  return type === 'external' ? '外战' : '内战'
}

async function loadMatches(reset = false) {
  if (reset) {
    page.value = 1
    matches.value = []
    hasMore.value = true
  }
  if (page.value === 1) loading.value = true
  else loadingMore.value = true
  error.value = ''
  try {
    const list = await api.get<MatchListItem[]>('/matches', {
      params: {
        page: page.value,
        page_size: pageSize,
        status: selectedStatus.value || undefined,
      },
    })
    matches.value = page.value === 1 ? list : matches.value.concat(list)
    hasMore.value = list.length === pageSize
  } catch (e) {
    error.value = (e as Error).message || '比赛列表加载失败'
  } finally {
    loading.value = false
    loadingMore.value = false
    uni.stopPullDownRefresh()
  }
}

function changeFilter(value: string) {
  selectedStatus.value = value
  loadMatches(true)
}

function goDetail(match: MatchListItem) {
  uni.navigateTo({ url: `/pages/matches/detail?id=${match.id}` })
}

onMounted(() => loadMatches(true))
onPullDownRefresh(() => loadMatches(true))
onReachBottom(() => {
  if (loading.value || loadingMore.value || !hasMore.value) return
  page.value += 1
  loadMatches()
})
</script>

<template>
  <view class="page">
    <view class="header">
      <text class="title">比赛</text>
      <text class="subtitle">小程序提供查看，录入和编辑请使用网页版</text>
    </view>

    <FullWebLink path="/match/input" desc="新建比赛、直播录入、赛后编辑和审批请在网页版完成。" />

    <view class="filters">
      <button
        v-for="filter in filters"
        :key="filter.value"
        class="filter-btn"
        :class="{ active: selectedStatus === filter.value }"
        @tap="changeFilter(filter.value)"
      >
        {{ filter.label }}
      </button>
    </view>

    <StateBlock v-if="loading" title="正在加载比赛" loading />
    <StateBlock v-else-if="error" title="加载失败" :desc="error" action-text="重试" @retry="loadMatches(true)" />
    <StateBlock v-else-if="matches.length === 0" title="暂无比赛" desc="可以到网页版录入第一场比赛" />

    <view v-else class="match-list">
      <view v-for="match in matches" :key="match.id" class="match-card" @tap="goDetail(match)">
        <view class="match-top">
          <view>
            <text class="match-date">{{ match.match_date }}</text>
            <text class="match-meta">{{ typeLabel(match.match_type) }} · {{ statusLabel(match.status) }}</text>
          </view>
          <text class="score">{{ match.team_a_score }} : {{ match.team_b_score }}</text>
        </view>
        <view class="match-bottom">
          <text class="creator">{{ match.created_by_name || '未知创建者' }}</text>
          <text v-if="match.spirit_scored" class="spirit">精神分 {{ match.spirit_total_score }}</text>
          <text v-else class="spirit muted">未评分</text>
        </view>
        <text v-if="match.notes" class="notes">{{ match.notes }}</text>
      </view>
      <text class="load-hint">{{ loadingMore ? '加载中...' : hasMore ? '上拉加载更多' : '已到底' }}</text>
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

.filters {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12rpx;
  margin: 0 28rpx 22rpx;
}

.filter-btn {
  height: 66rpx;
  line-height: 66rpx;
  padding: 0;
  border-radius: 14rpx;
  background: rgba(15, 23, 42, 0.82);
  border: 1rpx solid rgba(148, 163, 184, 0.16);
  color: #cbd5e1;
  font-size: 24rpx;
}

.filter-btn.active {
  background: #0ea5e9;
  color: #fff;
}

.filter-btn::after {
  border: none;
}

.match-list {
  margin: 0 28rpx;
}

.match-card {
  margin-bottom: 16rpx;
  padding: 24rpx;
  border: 1rpx solid rgba(148, 163, 184, 0.16);
  border-radius: 18rpx;
  background: rgba(15, 23, 42, 0.82);
}

.match-top,
.match-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 18rpx;
}

.match-date {
  display: block;
  color: #f8fafc;
  font-size: 29rpx;
  font-weight: 800;
}

.match-meta,
.creator,
.notes,
.spirit.muted {
  color: #94a3b8;
}

.match-meta,
.creator,
.spirit {
  font-size: 22rpx;
}

.score {
  color: #fbbf24;
  font-size: 40rpx;
  font-weight: 900;
}

.match-bottom {
  margin-top: 16rpx;
}

.spirit {
  color: #38bdf8;
}

.notes {
  display: block;
  margin-top: 14rpx;
  padding-top: 14rpx;
  border-top: 1rpx solid rgba(148, 163, 184, 0.12);
  font-size: 24rpx;
  line-height: 1.5;
}

.load-hint {
  display: block;
  padding: 24rpx 0 10rpx;
  text-align: center;
  color: #64748b;
  font-size: 23rpx;
}
</style>
