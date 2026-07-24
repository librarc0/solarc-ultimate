<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onPullDownRefresh } from '@dcloudio/uni-app'
import api from '@/api/request'
import type { MatchStatItem, PlayerPublic, PostItem, RankingResponse, TeamInfo } from '@/api/types'
import FullWebLink from '@/components/FullWebLink.vue'
import StateBlock from '@/components/StateBlock.vue'
import { WEB_ORIGIN } from '@/utils/webLink'

const loading = ref(true)
const error = ref('')
const profile = ref<PlayerPublic | null>(null)
const teamInfo = ref<TeamInfo | null>(null)
const matchStats = ref<MatchStatItem[]>([])
const posts = ref<PostItem[]>([])
const notifCount = ref(0)
const compositeScore = ref<number | null>(null)

const displayName = computed(() => profile.value?.display_name || profile.value?.username || '队员')
const teamLogoUrl = computed(() => {
  const url = teamInfo.value?.logo_url
  if (!url) return ''
  return url.startsWith('http') ? url : `${WEB_ORIGIN}${url}`
})
const teamInitial = computed(() => (teamInfo.value?.name || 'E').slice(0, 1))
const winRate = computed(() => {
  const p = profile.value
  if (!p || p.total_matches === 0) return '--'
  return `${Math.round((p.total_wins / p.total_matches) * 100)}%`
})
const latestStats = computed(() => matchStats.value.slice(0, 5))
const maxGoal = computed(() => Math.max(1, ...latestStats.value.map(item => item.goals + item.assists + item.defenses)))

function formatDate(date: string) {
  return date ? date.slice(5, 10).replace('-', '/') : '--'
}

async function loadData(showLoading = true) {
  if (showLoading) loading.value = true
  error.value = ''
  try {
    const [profileRes, teamRes, statsRes, postsRes, notifRes, rankRes] = await Promise.allSettled([
      api.get<PlayerPublic>('/players/me'),
      api.get<TeamInfo | null>('/team/my'),
      api.get<MatchStatItem[]>('/players/me/match_stats', { params: { limit: 20 } }),
      api.get<PostItem[]>('/team/posts', { params: { page_size: 5 } }),
      api.get<{ count: number }>('/team/notifications/count'),
      api.get<RankingResponse>('/rankings', { params: { page: 1, page_size: 100, sort_by: 'composite' } }),
    ])

    if (profileRes.status === 'fulfilled') profile.value = profileRes.value
    if (teamRes.status === 'fulfilled') teamInfo.value = teamRes.value
    if (statsRes.status === 'fulfilled') matchStats.value = statsRes.value
    if (postsRes.status === 'fulfilled') posts.value = postsRes.value
    if (notifRes.status === 'fulfilled') notifCount.value = notifRes.value.count ?? 0
    if (rankRes.status === 'fulfilled' && profile.value) {
      const row = rankRes.value.items.find(item => item.player_id === profile.value?.id)
      compositeScore.value = row?.composite_score ?? null
    }

    if (profileRes.status === 'rejected') {
      throw profileRes.reason
    }
  } catch (e) {
    error.value = (e as Error).message || '首页数据加载失败'
  } finally {
    loading.value = false
    uni.stopPullDownRefresh()
  }
}

function goMatches() {
  uni.switchTab({ url: '/pages/matches/index' })
}

onMounted(() => loadData())
onPullDownRefresh(() => loadData(false))
</script>

<template>
  <view class="page">
    <view class="hero">
      <view class="hero-copy">
        <text class="hero-title">{{ displayName }}</text>
        <text class="hero-sub">{{ teamInfo?.name || '暂未加入队伍' }}</text>
      </view>
      <view v-if="teamInfo" class="team-logo-stage">
        <view class="logo-halo" />
        <image v-if="teamLogoUrl" class="team-logo" :src="teamLogoUrl" mode="aspectFill" />
        <view v-else class="team-logo fallback">{{ teamInitial }}</view>
      </view>
      <view class="notice-badge">
        <text class="notice-num">{{ notifCount }}</text>
        <text class="notice-label">通知</text>
      </view>
    </view>

    <FullWebLink />

    <StateBlock v-if="loading" title="正在加载首页" loading />
    <StateBlock v-else-if="error" title="加载失败" :desc="error" action-text="重试" @retry="loadData()" />

    <template v-else>
      <view class="stats-grid">
        <view class="stat-cell">
          <text class="stat-value">{{ compositeScore == null ? '--' : compositeScore.toFixed(1) }}</text>
          <text class="stat-label">综合战力</text>
        </view>
        <view class="stat-cell">
          <text class="stat-value">{{ profile?.total_matches ?? 0 }}</text>
          <text class="stat-label">比赛</text>
        </view>
        <view class="stat-cell">
          <text class="stat-value">{{ winRate }}</text>
          <text class="stat-label">胜率</text>
        </view>
        <view class="stat-cell">
          <text class="stat-value">{{ profile?.total_goals ?? 0 }}</text>
          <text class="stat-label">得分</text>
        </view>
      </view>

      <view class="section">
        <view class="section-head">
          <text class="section-title">最近表现</text>
          <text class="section-action" @tap="goMatches">比赛列表</text>
        </view>
        <view v-if="latestStats.length" class="trend">
          <view v-for="item in latestStats" :key="item.match_id" class="trend-row">
            <text class="trend-date">{{ formatDate(item.match_date) }}</text>
            <view class="trend-bar-wrap">
              <view class="trend-bar" :style="{ width: `${Math.max(8, ((item.goals + item.assists + item.defenses) / maxGoal) * 100)}%` }" />
            </view>
            <text class="trend-score">{{ item.goals }}/{{ item.assists }}/{{ item.defenses }}</text>
          </view>
        </view>
        <text v-else class="empty-text">暂无近期比赛数据</text>
      </view>

      <view class="section" v-if="teamInfo">
        <view class="section-head">
          <text class="section-title">队伍概览</text>
          <text class="meta">{{ teamInfo.member_count }} 人</text>
        </view>
        <view class="team-card">
          <text class="team-name">{{ teamInfo.name }}</text>
          <text class="team-status">当前状态：{{ teamInfo.my_status }}</text>
        </view>
      </view>

      <view class="section">
        <view class="section-head">
          <text class="section-title">队伍留言</text>
          <text class="meta">前 {{ posts.length }} 条</text>
        </view>
        <view v-if="posts.length" class="post-list">
          <view v-for="post in posts" :key="post.id" class="post-item">
            <text class="post-author">{{ post.author_name }}</text>
            <text class="post-content">{{ post.content }}</text>
          </view>
        </view>
        <text v-else class="empty-text">暂无留言</text>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 34rpx 0 34rpx;
  background: linear-gradient(180deg, #07111f 0%, #101827 52%, #141414 100%);
}

.hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 30rpx 32rpx 24rpx;
}

.eyebrow,
.hero-sub,
.stat-label,
.meta,
.empty-text,
.team-status {
  color: #94a3b8;
}

.hero-copy {
  flex: 1;
  min-width: 0;
}

.hero-title {
  display: block;
  color: #f8fafc;
  font-size: 46rpx;
  font-weight: 800;
}

.hero-sub {
  display: block;
  margin-top: 8rpx;
  font-size: 25rpx;
}

.team-logo-stage {
  position: relative;
  width: 122rpx;
  height: 122rpx;
  margin-right: 14rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-halo {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: conic-gradient(from 140deg, #0ea5e9, #f59e0b, #22c55e, #0ea5e9);
  opacity: 0.85;
}

.team-logo {
  position: relative;
  z-index: 1;
  width: 104rpx;
  height: 104rpx;
  border-radius: 28rpx;
  border: 4rpx solid rgba(255, 255, 255, 0.18);
  background: #0f172a;
  overflow: hidden;
}

.team-logo.fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 42rpx;
  font-weight: 900;
}
.notice-badge {
  width: 112rpx;
  height: 112rpx;
  border-radius: 50%;
  background: #f59e0b;
  color: #111827;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.notice-num {
  font-size: 34rpx;
  font-weight: 900;
}

.notice-label {
  font-size: 20rpx;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14rpx;
  margin: 0 28rpx 24rpx;
}

.stat-cell,
.section {
  background: rgba(15, 23, 42, 0.82);
  border: 1rpx solid rgba(148, 163, 184, 0.14);
}

.stat-cell {
  border-radius: 16rpx;
  padding: 22rpx 8rpx;
  text-align: center;
}

.stat-value {
  display: block;
  color: #e0f2fe;
  font-size: 32rpx;
  font-weight: 800;
}

.stat-label {
  display: block;
  margin-top: 6rpx;
  font-size: 20rpx;
}

.section {
  margin: 0 28rpx 24rpx;
  padding: 24rpx;
  border-radius: 18rpx;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18rpx;
}

.section-title {
  color: #e5e7eb;
  font-size: 30rpx;
  font-weight: 800;
}

.section-action {
  color: #38bdf8;
  font-size: 24rpx;
}

.trend-row {
  display: grid;
  grid-template-columns: 70rpx 1fr 96rpx;
  align-items: center;
  gap: 14rpx;
  margin-bottom: 14rpx;
}

.trend-date,
.trend-score {
  color: #cbd5e1;
  font-size: 22rpx;
}

.trend-bar-wrap {
  height: 18rpx;
  border-radius: 10rpx;
  background: rgba(148, 163, 184, 0.2);
  overflow: hidden;
}

.trend-bar {
  height: 100%;
  border-radius: 10rpx;
  background: linear-gradient(90deg, #0ea5e9, #f59e0b);
}

.team-card {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.team-name {
  color: #f8fafc;
  font-size: 32rpx;
  font-weight: 800;
}

.post-item {
  padding: 16rpx 0;
  border-top: 1rpx solid rgba(148, 163, 184, 0.12);
}

.post-item:first-child {
  border-top: 0;
  padding-top: 0;
}

.post-author {
  display: block;
  color: #38bdf8;
  font-size: 23rpx;
  margin-bottom: 6rpx;
}

.post-content {
  display: block;
  color: #d1d5db;
  font-size: 25rpx;
  line-height: 1.5;
}
</style>
