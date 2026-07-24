<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onPullDownRefresh } from '@dcloudio/uni-app'
import api from '@/api/request'
import type { ScheduleEventListItem } from '@/api/types'
import FullWebLink from '@/components/FullWebLink.vue'
import StateBlock from '@/components/StateBlock.vue'

const loading = ref(true)
const error = ref('')
const events = ref<ScheduleEventListItem[]>([])
const activeRange = ref<'upcoming' | 'month'>('upcoming')

const filteredEvents = computed(() => events.value)

function pad(n: number) {
  return String(n).padStart(2, '0')
}

function toDateString(date: Date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function rangeOf() {
  const start = new Date()
  const end = new Date()
  if (activeRange.value === 'month') {
    start.setDate(1)
    end.setMonth(end.getMonth() + 1, 0)
  } else {
    start.setDate(start.getDate() - 7)
    end.setDate(end.getDate() + 60)
  }
  return { start_date: toDateString(start), end_date: toDateString(end) }
}

function typeLabel(type: string) {
  const map: Record<string, string> = {
    game: '外战',
    training: '训练',
    internal: '内战',
    other: '其他',
  }
  return map[type] ?? type
}

function dateLabel(event: ScheduleEventListItem) {
  if (event.start_date === event.end_date) return event.start_date.slice(5).replace('-', '/')
  return `${event.start_date.slice(5).replace('-', '/')} - ${event.end_date.slice(5).replace('-', '/')}`
}

function attendanceLabel(event: ScheduleEventListItem) {
  return `${event.yes_count} 到 / ${event.sdl_count} 待定 / ${event.leave_count} 请假`
}

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    events.value = await api.get<ScheduleEventListItem[]>('/schedule-events', { params: rangeOf() })
  } catch (e) {
    error.value = (e as Error).message || '日程加载失败'
  } finally {
    loading.value = false
    uni.stopPullDownRefresh()
  }
}

function changeRange(range: 'upcoming' | 'month') {
  activeRange.value = range
  loadData()
}

function goDetail(event: ScheduleEventListItem) {
  uni.navigateTo({ url: `/pages/schedule/detail?id=${event.id}` })
}

onMounted(loadData)
onPullDownRefresh(loadData)
</script>

<template>
  <view class="page">
    <view class="header">
      <text class="title">日程</text>
      <text class="subtitle">查看活动安排并提交本人出勤</text>
    </view>

    <FullWebLink path="/schedule" desc="创建日程、排阵和催填请在网页版完成。" />

    <view class="range-tabs">
      <button class="range-btn" :class="{ active: activeRange === 'upcoming' }" @tap="changeRange('upcoming')">近期</button>
      <button class="range-btn" :class="{ active: activeRange === 'month' }" @tap="changeRange('month')">本月</button>
    </view>

    <StateBlock v-if="loading" title="正在加载日程" loading />
    <StateBlock v-else-if="error" title="加载失败" :desc="error" action-text="重试" @retry="loadData" />
    <StateBlock v-else-if="filteredEvents.length === 0" title="暂无日程" desc="当前范围内没有已发布活动" />

    <view v-else class="event-list">
      <view v-for="event in filteredEvents" :key="event.id" class="event-card" @tap="goDetail(event)">
        <view class="event-top">
          <view>
            <text class="event-title">{{ event.title }}</text>
            <text class="event-meta">{{ dateLabel(event) }} · {{ typeLabel(event.event_type) }}</text>
          </view>
          <text class="status">{{ event.status === 'published' ? '已发布' : '草稿' }}</text>
        </view>
        <view class="attendance-bar">
          <view class="attendance-fill yes" :style="{ width: `${event.total_players ? (event.yes_count / event.total_players) * 100 : 0}%` }" />
        </view>
        <view class="event-bottom">
          <text>{{ attendanceLabel(event) }}</text>
          <text>{{ event.not_submitted_count }} 未填</text>
        </view>
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

.range-tabs {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14rpx;
  margin: 0 28rpx 22rpx;
}

.range-btn {
  height: 68rpx;
  line-height: 68rpx;
  padding: 0;
  border-radius: 14rpx;
  background: rgba(15, 23, 42, 0.82);
  border: 1rpx solid rgba(148, 163, 184, 0.16);
  color: #cbd5e1;
  font-size: 25rpx;
}

.range-btn.active {
  background: #0ea5e9;
  color: #fff;
}

.range-btn::after {
  border: none;
}

.event-list {
  margin: 0 28rpx;
}

.event-card {
  margin-bottom: 16rpx;
  padding: 24rpx;
  border: 1rpx solid rgba(148, 163, 184, 0.16);
  border-radius: 18rpx;
  background: rgba(15, 23, 42, 0.82);
}

.event-top,
.event-bottom {
  display: flex;
  justify-content: space-between;
  gap: 18rpx;
}

.event-title {
  display: block;
  color: #f8fafc;
  font-size: 30rpx;
  font-weight: 850;
}

.event-meta,
.event-bottom {
  color: #94a3b8;
  font-size: 23rpx;
}

.event-meta {
  display: block;
  margin-top: 8rpx;
}

.status {
  color: #38bdf8;
  font-size: 23rpx;
  white-space: nowrap;
}

.attendance-bar {
  height: 16rpx;
  margin: 20rpx 0 14rpx;
  border-radius: 10rpx;
  background: rgba(148, 163, 184, 0.2);
  overflow: hidden;
}

.attendance-fill {
  height: 100%;
  border-radius: 10rpx;
}

.attendance-fill.yes {
  background: linear-gradient(90deg, #22c55e, #0ea5e9);
}
</style>
