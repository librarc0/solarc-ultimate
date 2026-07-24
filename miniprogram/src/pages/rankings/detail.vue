<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onPullDownRefresh } from '@dcloudio/uni-app'
import api from '@/api/request'
import type { ExternalTeamDetail } from '@/api/types'
import FullWebLink from '@/components/FullWebLink.vue'
import StateBlock from '@/components/StateBlock.vue'

const teamName = ref('')
const seasonId = ref<number | null>(null)
const detail = ref<ExternalTeamDetail | null>(null)
const loading = ref(true)
const error = ref('')
const webPath = computed(() => `/public/rankings/${encodeURIComponent(teamName.value)}`)

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    detail.value = await api.get<ExternalTeamDetail>(`/public/team-rankings/${encodeURIComponent(teamName.value)}`, {
      params: seasonId.value ? { season_id: seasonId.value } : {},
    })
  } catch (e) {
    error.value = (e as Error).message || '队伍详情加载失败'
  } finally {
    loading.value = false
    uni.stopPullDownRefresh()
  }
}

onLoad((options) => {
  const raw = (options as Record<string, string>)?.team ?? ''
  teamName.value = decodeURIComponent(raw)
  const sid = Number((options as Record<string, string>)?.season_id ?? '')
  seasonId.value = Number.isFinite(sid) && sid > 0 ? sid : null
  loadData()
})
onPullDownRefresh(loadData)
</script>

<template>
  <view class="page">
    <FullWebLink :path="webPath" desc="完整队伍对比和更多筛选请在网页版使用。" />
    <StateBlock v-if="loading" title="正在加载队伍详情" loading />
    <StateBlock v-else-if="error" title="加载失败" :desc="error" action-text="重试" @retry="loadData" />

    <template v-else-if="detail">
      <view class="summary">
        <text class="rank">#{{ detail.rank }}</text>
        <text class="name">{{ detail.name }}</text>
        <text class="score">{{ detail.total_score.toFixed(1) }} 分</text>
      </view>

      <view class="stats-grid">
        <view class="stat"><text class="val">{{ detail.wins }}</text><text class="lbl">胜</text></view>
        <view class="stat"><text class="val">{{ detail.losses }}</text><text class="lbl">负</text></view>
        <view class="stat"><text class="val">{{ detail.win_rate.toFixed(0) }}%</text><text class="lbl">胜率</text></view>
        <view class="stat"><text class="val">{{ detail.net_points }}</text><text class="lbl">净胜分</text></view>
      </view>

      <view class="section">
        <text class="section-title">赛事记录</text>
        <view v-if="detail.tournament_records.length">
          <view v-for="record in detail.tournament_records" :key="record.id" class="record">
            <view>
              <text class="record-name">{{ record.tournament_name }}</text>
              <text class="record-meta">{{ record.month }} · {{ record.level }} · 第 {{ record.final_rank }} 名</text>
            </view>
            <text class="record-score">{{ record.computed_score.toFixed(1) }}</text>
          </view>
        </view>
        <text v-else class="empty">暂无赛事记录</text>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 34rpx 0;
  background: linear-gradient(180deg, #07111f 0%, #111827 100%);
}

.summary,
.stats-grid,
.section {
  margin: 0 28rpx 24rpx;
}

.summary,
.section,
.stat {
  border: 1rpx solid rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.82);
  border-radius: 18rpx;
}

.summary {
  padding: 30rpx;
}

.rank {
  display: block;
  color: #38bdf8;
  font-size: 32rpx;
  font-weight: 900;
}

.name {
  display: block;
  margin-top: 10rpx;
  color: #f8fafc;
  font-size: 42rpx;
  font-weight: 900;
}

.score {
  display: block;
  margin-top: 10rpx;
  color: #fbbf24;
  font-size: 30rpx;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14rpx;
}

.stat {
  padding: 20rpx 8rpx;
  text-align: center;
}

.val {
  display: block;
  color: #e0f2fe;
  font-size: 30rpx;
  font-weight: 900;
}

.lbl,
.record-meta,
.empty {
  color: #94a3b8;
  font-size: 22rpx;
}

.section {
  padding: 24rpx;
}

.section-title {
  display: block;
  color: #f8fafc;
  font-size: 30rpx;
  font-weight: 900;
  margin-bottom: 16rpx;
}

.record {
  display: flex;
  justify-content: space-between;
  gap: 20rpx;
  padding: 18rpx 0;
  border-top: 1rpx solid rgba(148, 163, 184, 0.12);
}

.record:first-child {
  border-top: 0;
}

.record-name {
  display: block;
  color: #e5e7eb;
  font-size: 26rpx;
  font-weight: 700;
}

.record-meta {
  display: block;
  margin-top: 6rpx;
}

.record-score {
  color: #fbbf24;
  font-size: 28rpx;
  font-weight: 900;
}
</style>
