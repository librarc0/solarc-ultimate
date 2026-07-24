<script setup lang="ts">
/**
 * AttendancePopup — 球员出勤填写弹窗（按天同步）
 */
import { computed, ref, watch } from 'vue'
import { showToast } from 'vant'
import scheduleApi, { type ScheduleEvent } from '@/api/schedule'

interface Props {
  modelValue: boolean
  events: ScheduleEvent[]
  date?: string
}
const props = defineProps<Props>()
const emit = defineEmits<{ 'update:modelValue': [v: boolean]; submitted: [] }>()

const myStatus = ref<string>('')
const loading = ref(false)
const loadedStatuses = ref<string[]>([])

const primaryEvent = computed(() => props.events[0] ?? null)
const selectedDateText = computed(() => props.date || primaryEvent.value?.start_date || '')
const hasMixedStatus = computed(() => Array.from(new Set(loadedStatuses.value.filter(Boolean))).length > 1)

const statusOptions = [
  { label: '✅ 出勤', value: 'yes', color: '#4caf50', desc: '我会到场参加' },
  { label: '🏃 请假', value: 'leave', color: '#ff9800', desc: '本次不参加，已提前请假' },
  { label: '🎉 场边加油', value: 'sdl', color: '#9c27b0', desc: '不到场上，但会在场边支持' },
]

const eventTypeText: Record<string, string> = {
  game: '外战',
  internal: '内战',
  training: '训练',
  other: '其他',
}

watch([() => props.modelValue, () => props.events.map(event => event.id).join(',')], async ([isOpen]) => {
  if (!isOpen || props.events.length === 0) {
    loadedStatuses.value = []
    myStatus.value = ''
    return
  }
  try {
    const results = await Promise.all(
      props.events.map(async (event) => {
        try {
          const res = await scheduleApi.getMyAttendance(event.id)
          return res?.status === 'no' ? 'leave' : (res?.status ?? '')
        } catch {
          return ''
        }
      }),
    )
    loadedStatuses.value = results
    const unique = Array.from(new Set(results.filter(Boolean)))
    myStatus.value = unique.length === 1 ? (unique[0] ?? '') : ''
  } catch {
    loadedStatuses.value = []
    myStatus.value = ''
  }
}, { immediate: true })

async function submit(status: string) {
  if (props.events.length === 0) return
  loading.value = true
  try {
    await Promise.all(props.events.map(event => scheduleApi.submitMyAttendance(event.id, status)))
    loadedStatuses.value = props.events.map(() => status)
    myStatus.value = status
    const targetText = props.events.length > 1 ? `${selectedDateText.value} 出勤更新完毕` : `${primaryEvent.value?.title ?? '活动'} 出勤更新完毕`
    showToast(targetText)
    emit('submitted')
    emit('update:modelValue', false)
  } catch (e: any) {
    showToast(e?.response?.data?.detail ?? '提交失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <van-popup
    :show="modelValue"
    @update:show="emit('update:modelValue', $event)"
    position="bottom"
    round
    class="schedule-sheet-popup"
    :style="{ padding: '18px 16px 20px', maxHeight: '80vh', overflowY: 'auto' }"
  >
    <div v-if="primaryEvent">
      <div class="event-card">
        <div class="popup-title">{{ props.events.length > 1 ? `${selectedDateText} · 共 ${props.events.length} 个活动` : primaryEvent.title }}</div>
        <div class="popup-meta-row">
          <van-tag plain type="primary">{{ props.events.length > 1 ? '当天同步' : (eventTypeText[primaryEvent.event_type] ?? primaryEvent.event_type) }}</van-tag>
          <span class="popup-date">{{ selectedDateText }}</span>
        </div>
        <div v-if="props.events.length > 1" class="event-list">
          <div v-for="item in props.events" :key="item.id" class="event-list__item">
            • {{ item.title }} · {{ eventTypeText[item.event_type] ?? item.event_type }}
          </div>
        </div>
        <div v-else-if="primaryEvent.description" class="popup-desc">{{ primaryEvent.description }}</div>
      </div>

      <p class="popup-tip">请选择你的出勤状态（点击后会{{ props.events.length > 1 ? `同步更新当天全部 ${props.events.length} 个活动` : '立即保存到当前活动' }}）：</p>
      <div v-if="hasMixedStatus" class="sync-note">这一天已有不同状态，本次选择会统一覆盖。</div>

      <div class="status-grid">
        <div
          v-for="opt in statusOptions"
          :key="opt.value"
          class="status-btn"
          :class="{ active: myStatus === opt.value }"
          :style="myStatus === opt.value ? `border-color: ${opt.color}; color: ${opt.color}` : ''"
          @click="submit(opt.value)"
        >
          <div class="status-btn__label">{{ opt.label }}</div>
          <div class="status-btn__desc">{{ opt.desc }}</div>
        </div>
      </div>

      <div v-if="myStatus" class="current-status">
        当前状态：{{ statusOptions.find(o => o.value === myStatus)?.label ?? myStatus }}
      </div>
    </div>
  </van-popup>
</template>

<style scoped>
.event-card {
  background: #ffffff;
  border: 1px solid #d7e4f2;
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 12px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}
.popup-title { font-size: 16px; font-weight: 700; color: #102238; }
.popup-meta-row { display: flex; align-items: center; gap: 8px; margin-top: 6px; flex-wrap: wrap; }
.popup-date { font-size: 13px; color: #2563eb; }
.popup-desc { font-size: 12px; color: #5b7088; margin-top: 8px; line-height: 1.5; }
.event-list { margin-top: 8px; display: grid; gap: 4px; }
.event-list__item { font-size: 12px; color: #45627e; line-height: 1.5; }
.popup-tip { color: #35516d; font-size: 13px; margin: 12px 0 8px; }
.sync-note {
  margin-bottom: 8px; padding: 8px 10px; border-radius: 10px;
  background: rgba(30, 136, 229, .12); color: #93c5fd; font-size: 12px;
}
.status-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-top: 8px;
}
.status-btn {
  padding: 12px 10px;
  border: 1.5px solid #d7e4f2;
  border-radius: 12px;
  text-align: left;
  font-size: 14px;
  color: #35516d;
  cursor: pointer;
  transition: all .15s;
  background: #ffffff;
}
.status-btn.active { background: #edf5ff; font-weight: 700; box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.08); }
.status-btn__label { font-weight: 700; }
.status-btn__desc { margin-top: 4px; font-size: 11px; color: #6a8299; line-height: 1.4; }
.current-status { margin-top: 12px; font-size: 12px; color: #2563eb; text-align: center; }
:deep(.schedule-sheet-popup) {
  background: linear-gradient(180deg, #f8fbff 0%, #eef6ff 100%);
}
</style>
