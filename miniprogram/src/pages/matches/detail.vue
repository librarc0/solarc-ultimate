<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onPullDownRefresh } from '@dcloudio/uni-app'
import api from '@/api/request'
import type { MatchDetail, MatchEventItem } from '@/api/types'
import FullWebLink from '@/components/FullWebLink.vue'
import StateBlock from '@/components/StateBlock.vue'

const matchId = ref<number | null>(null)
const detail = ref<MatchDetail | null>(null)
const events = ref<MatchEventItem[]>([])
const loading = ref(true)
const error = ref('')
const webPath = computed(() => matchId.value ? `/matches/${matchId.value}` : '/matches/list')

function typeLabel(type: string) {
  return type === 'external' ? '外战' : '内战'
}

function sideName(side: string) {
  return side === 'A' ? 'A 队' : 'B 队'
}

function eventLabel(event: MatchEventItem) {
  const side = event.team_side ? `${event.team_side} 队` : ''
  const typeMap: Record<string, string> = {
    goal: '得分',
    assist: '助攻',
    defense: '防守',
    halftime: '半场',
    start: '开始',
    end: '结束',
  }
  return `${side} ${typeMap[event.event_type] ?? event.event_type}`.trim()
}

function playerTotal(side: string) {
  return detail.value?.participants.filter(p => p.team_side === side) ?? []
}

async function loadData() {
  if (!matchId.value) return
  loading.value = true
  error.value = ''
  try {
    const [detailRes, eventRes] = await Promise.allSettled([
      api.get<MatchDetail>(`/matches/${matchId.value}`),
      api.get<MatchEventItem[]>(`/matches/${matchId.value}/events`),
    ])
    if (detailRes.status === 'fulfilled') detail.value = detailRes.value
    else throw detailRes.reason
    events.value = eventRes.status === 'fulfilled' ? eventRes.value : []
  } catch (e) {
    error.value = (e as Error).message || '比赛详情加载失败'
  } finally {
    loading.value = false
    uni.stopPullDownRefresh()
  }
}

onLoad((options) => {
  const id = Number((options as Record<string, string>)?.id)
  matchId.value = Number.isFinite(id) ? id : null
  loadData()
})
onPullDownRefresh(loadData)
</script>

<template>
  <view class="page">
    <FullWebLink :path="webPath" desc="编辑比赛、审批、补录精神评分请在网页版完成。" />
    <StateBlock v-if="loading" title="正在加载比赛详情" loading />
    <StateBlock v-else-if="error" title="加载失败" :desc="error" action-text="重试" @retry="loadData" />

    <template v-else-if="detail">
      <view class="score-card">
        <text class="match-type">{{ typeLabel(detail.match_type) }} · {{ detail.match_date }}</text>
        <text class="score">{{ detail.team_a_score }} : {{ detail.team_b_score }}</text>
        <text class="meta">创建者：{{ detail.created_by_name }}</text>
        <text v-if="detail.notes" class="notes">{{ detail.notes }}</text>
      </view>

      <view class="section" v-for="side in ['A', 'B']" :key="side">
        <text class="section-title">{{ sideName(side) }}</text>
        <view v-for="player in playerTotal(side)" :key="player.player_id" class="player-row">
          <text class="player-name">{{ player.player_name }}{{ player.is_mvp ? ' MVP' : '' }}</text>
          <text class="player-stat">{{ player.goals ?? 0 }}球 {{ player.assists ?? 0 }}助 {{ player.defenses ?? 0 }}防</text>
        </view>
      </view>

      <view class="section">
        <text class="section-title">时间轴</text>
        <view v-if="events.length">
          <view v-for="event in events" :key="event.id" class="event-row">
            <text class="event-time">{{ event.elapsed_seconds == null ? '--' : Math.floor(event.elapsed_seconds / 60) + '\'' }}</text>
            <text class="event-text">{{ eventLabel(event) }}</text>
          </view>
        </view>
        <text v-else class="empty">暂无事件流</text>
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

.score-card,
.section {
  margin: 0 28rpx 24rpx;
  padding: 26rpx;
  border: 1rpx solid rgba(148, 163, 184, 0.16);
  border-radius: 18rpx;
  background: rgba(15, 23, 42, 0.82);
}

.match-type,
.meta,
.notes,
.empty {
  color: #94a3b8;
  font-size: 24rpx;
}

.match-type,
.score,
.meta,
.notes {
  display: block;
  text-align: center;
}

.score {
  margin: 20rpx 0;
  color: #fbbf24;
  font-size: 58rpx;
  font-weight: 900;
}

.notes {
  margin-top: 16rpx;
  line-height: 1.5;
}

.section-title {
  display: block;
  color: #f8fafc;
  font-size: 30rpx;
  font-weight: 900;
  margin-bottom: 16rpx;
}

.player-row,
.event-row {
  display: flex;
  justify-content: space-between;
  gap: 18rpx;
  padding: 16rpx 0;
  border-top: 1rpx solid rgba(148, 163, 184, 0.12);
}

.player-row:first-of-type,
.event-row:first-of-type {
  border-top: 0;
}

.player-name,
.event-text {
  color: #e5e7eb;
  font-size: 25rpx;
}

.player-stat,
.event-time {
  color: #38bdf8;
  font-size: 24rpx;
  white-space: nowrap;
}
</style>
