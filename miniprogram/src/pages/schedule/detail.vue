<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onPullDownRefresh } from '@dcloudio/uni-app'
import api from '@/api/request'
import type { AttendanceRead, ScheduleEventRead } from '@/api/types'
import FullWebLink from '@/components/FullWebLink.vue'
import StateBlock from '@/components/StateBlock.vue'

const eventId = ref<number | null>(null)
const event = ref<ScheduleEventRead | null>(null)
const attendance = ref<AttendanceRead | null>(null)
const loading = ref(true)
const submitting = ref(false)
const error = ref('')
const webPath = computed(() => eventId.value ? `/schedule?event=${eventId.value}` : '/schedule')

const options = [
  { label: '到场', value: 'yes', desc: '确认参加本次活动' },
  { label: '待定', value: 'sdl', desc: '暂不确定，稍后更新' },
  { label: '请假', value: 'leave', desc: '无法参加本次活动' },
] as const

function typeLabel(type: string) {
  const map: Record<string, string> = {
    game: '外战',
    training: '训练',
    internal: '内战',
    other: '其他',
  }
  return map[type] ?? type
}

function statusLabel(status?: string) {
  if (status === 'yes') return '到场'
  if (status === 'sdl') return '待定'
  if (status === 'leave') return '请假'
  return '未填写'
}

async function loadData() {
  if (!eventId.value) return
  loading.value = true
  error.value = ''
  try {
    const [eventRes, attendanceRes] = await Promise.allSettled([
      api.get<ScheduleEventRead>(`/schedule-events/${eventId.value}`),
      api.get<AttendanceRead | null>(`/schedule-attendance/${eventId.value}/me`),
    ])
    if (eventRes.status === 'fulfilled') event.value = eventRes.value
    else throw eventRes.reason
    attendance.value = attendanceRes.status === 'fulfilled' ? attendanceRes.value : null
  } catch (e) {
    error.value = (e as Error).message || '日程详情加载失败'
  } finally {
    loading.value = false
    uni.stopPullDownRefresh()
  }
}

async function submitAttendance(status: 'yes' | 'sdl' | 'leave') {
  if (!eventId.value || submitting.value) return
  submitting.value = true
  try {
    attendance.value = await api.put<AttendanceRead>(`/schedule-attendance/${eventId.value}/me`, { status })
    uni.showToast({ title: '已提交', icon: 'success' })
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '提交失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

onLoad((options) => {
  const id = Number((options as Record<string, string>)?.id)
  eventId.value = Number.isFinite(id) ? id : null
  loadData()
})
onPullDownRefresh(loadData)
</script>

<template>
  <view class="page">
    <FullWebLink :path="webPath" desc="排阵、编辑日程和查看完整汇总请在网页版完成。" />
    <StateBlock v-if="loading" title="正在加载日程详情" loading />
    <StateBlock v-else-if="error" title="加载失败" :desc="error" action-text="重试" @retry="loadData" />

    <template v-else-if="event">
      <view class="event-card">
        <text class="type">{{ typeLabel(event.event_type) }}</text>
        <text class="title">{{ event.title }}</text>
        <text class="date">{{ event.start_date }}{{ event.end_date !== event.start_date ? ' 至 ' + event.end_date : '' }}</text>
        <text v-if="event.description" class="desc">{{ event.description }}</text>
      </view>

      <view class="section">
        <view class="section-head">
          <text class="section-title">我的出勤</text>
          <text class="current">{{ statusLabel(attendance?.status) }}</text>
        </view>
        <view class="option-list">
          <view
            v-for="item in options"
            :key="item.value"
            class="option"
            :class="{ active: attendance?.status === item.value }"
            @tap="submitAttendance(item.value)"
          >
            <view>
              <text class="option-title">{{ item.label }}</text>
              <text class="option-desc">{{ item.desc }}</text>
            </view>
            <text class="option-mark">{{ attendance?.status === item.value ? '已选' : '选择' }}</text>
          </view>
        </view>
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

.event-card,
.section {
  margin: 0 28rpx 24rpx;
  padding: 26rpx;
  border: 1rpx solid rgba(148, 163, 184, 0.16);
  border-radius: 18rpx;
  background: rgba(15, 23, 42, 0.82);
}

.type {
  color: #38bdf8;
  font-size: 24rpx;
  font-weight: 800;
}

.title {
  display: block;
  margin-top: 10rpx;
  color: #f8fafc;
  font-size: 40rpx;
  font-weight: 900;
}

.date,
.desc {
  display: block;
  margin-top: 12rpx;
  color: #94a3b8;
  font-size: 25rpx;
  line-height: 1.5;
}

.section-head,
.option {
  display: flex;
  justify-content: space-between;
  gap: 18rpx;
}

.section-title {
  color: #f8fafc;
  font-size: 30rpx;
  font-weight: 900;
}

.current {
  color: #fbbf24;
  font-size: 25rpx;
}

.option-list {
  margin-top: 18rpx;
}

.option {
  align-items: center;
  padding: 20rpx 0;
  border-top: 1rpx solid rgba(148, 163, 184, 0.12);
}

.option:first-child {
  border-top: 0;
}

.option.active .option-title {
  color: #fbbf24;
}

.option-title {
  display: block;
  color: #e5e7eb;
  font-size: 28rpx;
  font-weight: 800;
}

.option-desc {
  display: block;
  margin-top: 6rpx;
  color: #94a3b8;
  font-size: 23rpx;
}

.option-mark {
  color: #38bdf8;
  font-size: 24rpx;
  white-space: nowrap;
}
</style>
