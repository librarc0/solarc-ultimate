<script setup lang="ts">
/**
 * PlayerScheduleCalendar — 球员主页日历/日程表小控件
 * 支持月历、周历、未来日程表 + 点击提交出勤
 */
import { ref, computed, onMounted } from 'vue'
import { Lunar } from 'lunar-typescript'
import scheduleApi, { type ScheduleEvent } from '@/api/schedule'
import AttendancePopup from './AttendancePopup.vue'

type CalendarMode = 'month' | 'week' | 'agenda'
const attendanceKeys = ['yes', 'leave', 'sdl'] as const

type AttendanceStatusKey = (typeof attendanceKeys)[number]

const statusMeta: Record<AttendanceStatusKey, { label: string; short: string; color: string }> = {
  yes: { label: '到场', short: '到', color: '#22c55e' },
  leave: { label: '请假', short: '假', color: '#f59e0b' },
  sdl: { label: 'SDL', short: 'SDL', color: '#8b5cf6' },
}

function formatDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function parseDate(dateStr: string) {
  return new Date(`${dateStr}T00:00:00`)
}

function isAttendanceStatus(value: string): value is AttendanceStatusKey {
  return attendanceKeys.includes(value as AttendanceStatusKey)
}

// ─── 当前月 / 周 ─────────────────────────────────────────────────────────────
const today = new Date()
const todayStr = formatDate(today)
const viewYear = ref(today.getFullYear())
const viewMonth = ref(today.getMonth() + 1)
const calendarMode = ref<CalendarMode>('month')
const focusDate = ref(todayStr)

function syncViewFromDate(dateStr: string) {
  const d = parseDate(dateStr)
  viewYear.value = d.getFullYear()
  viewMonth.value = d.getMonth() + 1
}

const monthLabel = computed(() =>
  `${viewYear.value} 年 ${String(viewMonth.value).padStart(2, '0')} 月`,
)

const days = computed(() => {
  if (calendarMode.value === 'week') {
    const anchor = parseDate(focusDate.value || todayStr)
    const start = new Date(anchor)
    start.setDate(anchor.getDate() - anchor.getDay())
    return Array.from({ length: 7 }, (_, index) => {
      const current = new Date(start)
      current.setDate(start.getDate() + index)
      return { day: current.getDate(), date: formatDate(current) }
    })
  }

  const y = viewYear.value
  const m = viewMonth.value
  const firstDay = new Date(y, m - 1, 1).getDay()
  const daysInMonth = new Date(y, m, 0).getDate()
  const cells: { day: number | null; date: string }[] = []
  for (let i = 0; i < firstDay; i++) cells.push({ day: null, date: '' })
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ day: d, date: `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}` })
  }
  return cells
})

const displayLabel = computed(() => {
  if (calendarMode.value === 'month') return monthLabel.value
  if (calendarMode.value === 'agenda') return '未来日程表'
  const first = days.value[0]
  const last = days.value[days.value.length - 1]
  return `${first?.date ?? todayStr} ~ ${last?.date ?? todayStr}`
})

function prevPeriod() {
  if (calendarMode.value === 'agenda') return
  if (calendarMode.value === 'month') {
    if (viewMonth.value === 1) { viewYear.value--; viewMonth.value = 12 }
    else viewMonth.value--
    focusDate.value = `${viewYear.value}-${String(viewMonth.value).padStart(2, '0')}-01`
  } else {
    const d = parseDate(focusDate.value)
    d.setDate(d.getDate() - 7)
    focusDate.value = formatDate(d)
    syncViewFromDate(focusDate.value)
  }
  loadEvents()
}

function nextPeriod() {
  if (calendarMode.value === 'agenda') return
  if (calendarMode.value === 'month') {
    if (viewMonth.value === 12) { viewYear.value++; viewMonth.value = 1 }
    else viewMonth.value++
    focusDate.value = `${viewYear.value}-${String(viewMonth.value).padStart(2, '0')}-01`
  } else {
    const d = parseDate(focusDate.value)
    d.setDate(d.getDate() + 7)
    focusDate.value = formatDate(d)
    syncViewFromDate(focusDate.value)
  }
  loadEvents()
}

function switchMode(mode: CalendarMode) {
  calendarMode.value = mode
  focusDate.value = focusDate.value || todayStr
  if (mode !== 'agenda') {
    syncViewFromDate(focusDate.value)
  }
  loadEvents()
}

function getLunar(day: number) {
  try {
    const l = Lunar.fromDate(new Date(viewYear.value, viewMonth.value - 1, day))
    const festivals = l.getFestivals()
    return festivals.length > 0 ? festivals[0] : l.getDayInChinese()
  } catch {
    return ''
  }
}

// ─── 事件加载 + 出勤状态加载 ─────────────────────────────────────────────────
const events = ref<ScheduleEvent[]>([])
const attendanceMap = ref<Record<number, string>>({})
const loading = ref(false)

async function loadEvents() {
  loading.value = true
  try {
    let start = todayStr
    let end = todayStr

    if (calendarMode.value === 'agenda') {
      const endDate = new Date()
      endDate.setDate(endDate.getDate() + 365)
      start = todayStr
      end = formatDate(endDate)
    } else if (calendarMode.value === 'week') {
      const first = days.value[0]
      const last = days.value[days.value.length - 1]
      start = first?.date ?? todayStr
      end = last?.date ?? todayStr
    } else {
      const y = viewYear.value
      const m = viewMonth.value
      start = `${y}-${String(m).padStart(2, '0')}-01`
      end = `${y}-${String(m).padStart(2, '0')}-${String(new Date(y, m, 0).getDate()).padStart(2, '0')}`
    }

    events.value = await scheduleApi.getEvents({ start_date: start, end_date: end })
    const attendances = await Promise.all(
      events.value.map(async (ev) => {
        try {
          const res = await scheduleApi.getMyAttendance(ev.id)
          return [ev.id, res?.status ?? ''] as const
        } catch {
          return [ev.id, ''] as const
        }
      }),
    )
    attendanceMap.value = Object.fromEntries(attendances)
  } catch {
    events.value = []
    attendanceMap.value = {}
  } finally {
    loading.value = false
  }
}

function eventsForDate(date: string): ScheduleEvent[] {
  if (!date) return []
  return events.value.filter(e => e.start_date <= date && e.end_date >= date)
}

function attendanceStatusesForDate(date: string): AttendanceStatusKey[] {
  const found = new Set<AttendanceStatusKey>()
  for (const ev of eventsForDate(date)) {
    const rawStatus = attendanceMap.value[ev.id] ?? ''
    const status = rawStatus === 'no' ? 'leave' : rawStatus
    if (isAttendanceStatus(status)) found.add(status)
  }
  return Array.from(found)
}

const eventTypeMeta = {
  training: { label: '训练', color: '#22c55e', tint: 'rgba(34, 197, 94, .18)' },
  game: { label: '外战', color: '#3b82f6', tint: 'rgba(59, 130, 246, .18)' },
  internal: { label: '内战', color: '#a855f7', tint: 'rgba(168, 85, 247, .18)' },
  other: { label: '其他', color: '#f59e0b', tint: 'rgba(245, 158, 11, .18)' },
} as const

const eventLegendItems = [
  { key: 'training', ...eventTypeMeta.training },
  { key: 'game', ...eventTypeMeta.game },
  { key: 'internal', ...eventTypeMeta.internal },
  { key: 'other', ...eventTypeMeta.other },
] as const

const eventTypeColor: Record<string, string> = Object.fromEntries(
  eventLegendItems.map(item => [item.key, item.color]),
)

function weekdayLabel(date: string) {
  const labels = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return labels[parseDate(date).getDay()] ?? ''
}

function primaryEventTypeForDate(date: string): keyof typeof eventTypeMeta | null {
  const dayEvents = eventsForDate(date)
  if (dayEvents.length === 0) return null
  const priority: Array<keyof typeof eventTypeMeta> = ['game', 'internal', 'training', 'other']
  const types = new Set(dayEvents.map(event => event.event_type))
  return priority.find(type => types.has(type)) ?? 'other'
}

function dayCellStyle(date: string) {
  const type = primaryEventTypeForDate(date)
  if (!type) return undefined
  return {
    background: eventTypeMeta[type].tint,
    boxShadow: `inset 0 0 0 1px ${eventTypeMeta[type].color}55`,
  }
}

const statusBadgeMeta: Record<AttendanceStatusKey | 'pending', { label: string; bg: string; textColor: string }> = {
  yes:     { label: '✓ 到场', bg: '#166534', textColor: '#bbf7d0' },
  leave:   { label: '✗ 请假', bg: '#78350f', textColor: '#fde68a' },
  sdl:     { label: '⚡ SDL', bg: '#4c1d95', textColor: '#ddd6fe' },
  pending: { label: '？未填写', bg: '#1e3a4f', textColor: '#94a3b8' },
}

const upcomingAgendaGroups = computed(() => {
  const groups = new Map<string, ScheduleEvent[]>()
  events.value
    .filter(event => event.end_date >= todayStr)
    .sort((a, b) => a.start_date.localeCompare(b.start_date) || a.id - b.id)
    .forEach((event) => {
      const key = event.start_date
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push(event)
    })

  return Array.from(groups.entries()).map(([date, items]) => {
    const rawStatuses = Array.from(new Set(items
      .map(item => attendanceMap.value[item.id] === 'no' ? 'leave' : attendanceMap.value[item.id])
      .filter(Boolean))) as AttendanceStatusKey[]

    const statusBadges: Array<{ label: string; bg: string; textColor: string }> =
      rawStatuses.length === 0
        ? [statusBadgeMeta.pending]
        : rawStatuses.map(s => statusBadgeMeta[s] ?? statusBadgeMeta.pending)

    return {
      date,
      items,
      statusBadges,
      weekday: weekdayLabel(date),
      primaryType: primaryEventTypeForDate(date) ?? 'other',
    }
  })
})

function openAgendaDate(date: string, items: ScheduleEvent[]) {
  focusDate.value = date
  selectedEvents.value = items
  showPopup.value = true
}

// ─── 出勤弹窗 ────────────────────────────────────────────────────────────────
const showPopup = ref(false)
const selectedEvents = ref<ScheduleEvent[]>([])

function clickDay(date: string) {
  const evs = eventsForDate(date)
  focusDate.value = date
  syncViewFromDate(date)
  if (evs.length === 0) return
  selectedEvents.value = evs
  showPopup.value = true
}

onMounted(loadEvents)
</script>

<template>
  <div class="player-cal">
    <div class="cal-header">
      <van-icon name="arrow-left" @click="prevPeriod" class="nav-icon" />
      <span class="month-label">{{ displayLabel }}</span>
      <van-icon name="arrow" @click="nextPeriod" class="nav-icon" />
    </div>

    <div class="view-switch">
      <van-button size="mini" :type="calendarMode === 'month' ? 'primary' : 'default'" plain @click="switchMode('month')">月历</van-button>
      <van-button size="mini" :type="calendarMode === 'week' ? 'primary' : 'default'" plain @click="switchMode('week')">周历</van-button>
      <van-button size="mini" :type="calendarMode === 'agenda' ? 'primary' : 'default'" plain @click="switchMode('agenda')">日程表</van-button>
    </div>

    <div v-if="calendarMode !== 'agenda'" class="event-legend">
      <span v-for="item in eventLegendItems" :key="item.key" class="event-legend__item">
        <i class="event-legend__swatch" :style="{ background: item.color }" />{{ item.label }}
      </span>
    </div>

    <div v-if="calendarMode !== 'agenda'" class="weekdays">
      <span v-for="d in ['日','一','二','三','四','五','六']" :key="d">{{ d }}</span>
    </div>

    <van-loading v-if="loading" type="spinner" size="20px" style="display:block;text-align:center;padding:12px" />
    <div v-else-if="calendarMode === 'agenda'" class="agenda-list">
      <div v-if="upcomingAgendaGroups.length === 0" class="empty-tip">暂无未来日程</div>
      <div
        v-for="group in upcomingAgendaGroups"
        :key="group.date"
        class="agenda-day"
        :style="{ borderColor: eventTypeMeta[group.primaryType].color }"
        @click="openAgendaDate(group.date, group.items)"
      >
        <div class="agenda-day__datebox" :style="{ background: eventTypeMeta[group.primaryType].tint }">
          <div class="agenda-day__date-num">{{ group.date.slice(8, 10) }}</div>
          <div class="agenda-day__date-week">{{ group.weekday }}</div>
        </div>
        <div class="agenda-day__body">
          <div class="agenda-day__head">
            <div>
              <div class="agenda-day__date">{{ group.date }}</div>
              <div class="agenda-status-badges">
                <span
                  v-for="(badge, idx) in group.statusBadges"
                  :key="idx"
                  class="agenda-status-badge"
                  :style="{ background: badge.bg, color: badge.textColor }"
                >{{ badge.label }}</span>
              </div>
            </div>
            <van-tag plain :color="eventTypeMeta[group.primaryType].color">{{ eventTypeMeta[group.primaryType].label }} · {{ group.items.length }} 项</van-tag>
          </div>
          <div class="agenda-day__events">
            <div
              v-for="item in group.items"
              :key="item.id"
              class="agenda-event-row"
            >
              <i class="agenda-event-row__dot" :style="{ background: eventTypeColor[item.event_type] ?? '#456' }" />
              <span class="agenda-event-row__name">{{ item.title }}</span>
            </div>
          </div>
          <div class="agenda-day__cta">点按后可一次填写当天全部活动出勤</div>
        </div>
      </div>
    </div>
    <div v-else class="day-grid" :class="{ 'week-mode': calendarMode === 'week' }">
      <div
        v-for="(cell, i) in days"
        :key="`${calendarMode}-${cell.date}-${i}`"
        class="day-cell"
        :class="{
          today: cell.date === todayStr,
          has_event: cell.day && eventsForDate(cell.date).length > 0,
          empty: !cell.day,
        }"
        :style="cell.day ? dayCellStyle(cell.date) : undefined"
        @click="cell.day && clickDay(cell.date)"
      >
        <span v-if="cell.day" class="day-num">{{ cell.day }}</span>
        <span v-if="cell.day" class="day-lunar">{{ getLunar(cell.day) }}</span>
        <div v-if="cell.day" class="status-badges">
          <span
            v-for="status in attendanceStatusesForDate(cell.date)"
            :key="`${cell.date}-${status}`"
            class="status-badge"
            :style="{ background: statusMeta[status].color }"
          >{{ statusMeta[status].short }}</span>
        </div>
      </div>
    </div>

    <AttendancePopup
      v-model="showPopup"
      :events="selectedEvents"
      :date="focusDate"
      @submitted="loadEvents"
    />
  </div>
</template>

<style scoped>
.player-cal {
  background: #0d1b2a; border-radius: 12px;
  padding: 12px; margin: 12px 16px;
}
.cal-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px;
}
.month-label { font-size: 15px; font-weight: 600; color: #e0e0e0; }
.nav-icon { color: #90caf9; cursor: pointer; font-size: 18px; padding: 4px; }
.view-switch { display: flex; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }
.event-legend { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.event-legend__item { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: #dbeafe; }
.event-legend__swatch { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
.weekdays {
  display: grid; grid-template-columns: repeat(7, 1fr);
  text-align: center; font-size: 11px; color: #546e7a; margin-bottom: 4px;
}
.day-grid {
  display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px;
}
.day-grid.week-mode .day-cell {
  min-height: 58px;
}
.day-cell {
  min-height: 44px;
  padding: 3px 2px;
  border-radius: 6px;
  text-align: center;
  cursor: pointer;
  position: relative;
  transition: background .1s;
}
.day-cell.has_event { background: #0f2035; }
.day-cell.today { box-shadow: inset 0 0 0 2px #60a5fa; }
.day-cell.empty { pointer-events: none; }
.day-num { display: block; font-size: 13px; color: #e0e0e0; line-height: 1.4; }
.day-lunar { display: block; font-size: 9px; color: #a9bdd3; line-height: 1.2; overflow: hidden; white-space: nowrap; }
.status-badges {
  display: flex; justify-content: center; gap: 2px; flex-wrap: wrap; margin-top: 3px;
}
.status-badge {
  min-width: 12px; height: 12px; padding: 0 3px; border-radius: 999px;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 8px; color: #fff; line-height: 1;
}
.agenda-list { display: grid; gap: 8px; }
.agenda-day {
  display: grid; grid-template-columns: 64px 1fr; gap: 10px;
  background: #0f2035; border: 1px solid #244160; border-radius: 14px; padding: 10px; cursor: pointer;
}
.agenda-day__datebox {
  border-radius: 12px; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 72px;
  border: 1px solid rgba(255,255,255,.08);
}
.agenda-day__date-num { font-size: 20px; font-weight: 800; color: #f8fbff; line-height: 1; }
.agenda-day__date-week { margin-top: 6px; font-size: 11px; color: #dbeafe; }
.agenda-day__body { min-width: 0; }
.agenda-day__head {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 8px; flex-wrap: wrap;
}
.agenda-day__date { color: #f8fbff; font-weight: 700; font-size: 13px; }
.agenda-day__status { color: #93c5fd; font-size: 12px; margin-top: 2px; }
.agenda-day__events { display: grid; gap: 6px; }
.agenda-event-row {
  display: flex; align-items: center; gap: 8px; color: #eef6ff; font-size: 13px; padding: 4px 0;
  border-bottom: 1px dashed rgba(148, 163, 184, .2);
}
.agenda-event-row:last-child { border-bottom: none; }
.agenda-event-row__dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.agenda-event-row__name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.agenda-day__cta { margin-top: 8px; color: #b7d2ee; font-size: 11px; }
.empty-tip { color: #8fb3d9; text-align: center; padding: 12px 0; }

@media (max-width: 640px) {
  .agenda-day { grid-template-columns: 1fr; }
  .agenda-day__datebox { min-height: 64px; }
}
.agenda-status-badges {
  display: flex; gap: 5px; flex-wrap: wrap; margin-top: 4px;
}
.agenda-status-badge {
  display: inline-flex; align-items: center; justify-content: center;
  padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600;
  letter-spacing: 0.02em; line-height: 1.6;
}
</style>
