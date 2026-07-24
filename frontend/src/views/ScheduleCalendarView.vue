<script setup lang="ts">
/**
 * ScheduleCalendarView — 管理员日程管理页面
 * 月历视图 + 事件列表 + 出勤管理 + 分 line 管理
 */
import { ref, computed, onMounted } from 'vue'
import { showToast, showConfirmDialog } from 'vant'
import { Lunar } from 'lunar-typescript'
import scheduleApi, { type ScheduleEvent, type LinePlayerInfo } from '@/api/schedule'
import ScheduleEventForm from '@/components/schedule/ScheduleEventForm.vue'
import AttendanceDetailPanel from '@/components/schedule/AttendanceDetailPanel.vue'
import LineDivisionManager from '@/components/schedule/LineDivisionManager.vue'
import api from '@/api'

type CalendarMode = 'month' | 'week' | 'agenda'

function formatDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function parseDate(dateStr: string) {
  return new Date(`${dateStr}T00:00:00`)
}

// ─── 月历 / 周历导航 ─────────────────────────────────────────────────────────
const today = new Date()
const todayStr = formatDate(today)
const calendarMode = ref<CalendarMode>('month')
const viewYear = ref(today.getFullYear())
const viewMonth = ref(today.getMonth() + 1)
const selectedDate = ref(todayStr)
const focusDate = ref(todayStr)

function syncViewFromDate(dateStr: string) {
  const d = parseDate(dateStr)
  viewYear.value = d.getFullYear()
  viewMonth.value = d.getMonth() + 1
}

const monthLabel = computed(() =>
  `${viewYear.value} 年 ${String(viewMonth.value).padStart(2, '0')} 月`
)

const calDays = computed(() => {
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

const weekDays = computed(() => {
  const anchor = parseDate(focusDate.value || selectedDate.value || todayStr)
  const start = new Date(anchor)
  start.setDate(anchor.getDate() - anchor.getDay())
  return Array.from({ length: 7 }, (_, index) => {
    const current = new Date(start)
    current.setDate(start.getDate() + index)
    return { day: current.getDate(), date: formatDate(current) }
  })
})

const displayDays = computed(() =>
  calendarMode.value === 'week' ? weekDays.value : calDays.value,
)

const displayLabel = computed(() => {
  if (calendarMode.value === 'month') return monthLabel.value
  if (calendarMode.value === 'agenda') return '未来日程表'
  const first = weekDays.value[0]
  const last = weekDays.value[weekDays.value.length - 1]
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
  focusDate.value = selectedDate.value || todayStr
  if (mode !== 'agenda') {
    syncViewFromDate(focusDate.value)
  }
  loadEvents()
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
const eventTypeColor: Record<string, string> = Object.fromEntries(eventLegendItems.map(item => [item.key, item.color]))

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

// ─── 事件数据 ────────────────────────────────────────────────────────────────
const events = ref<ScheduleEvent[]>([])
const loading = ref(false)
const eventsCache = new Map<string, ScheduleEvent[]>()

function eventsCacheKey(): string {
  if (calendarMode.value === 'agenda') return 'agenda'
  if (calendarMode.value === 'week') {
    const first = weekDays.value[0]
    return `week:${first?.date ?? todayStr}`
  }
  return `month:${viewYear.value}-${String(viewMonth.value).padStart(2, '0')}`
}

async function loadEvents(force = false) {
  const key = eventsCacheKey()
  if (!force && eventsCache.has(key)) {
    events.value = eventsCache.get(key)!
    return
  }
  loading.value = true
  let start = todayStr
  let end = todayStr

  if (calendarMode.value === 'agenda') {
    const endDate = new Date()
    endDate.setDate(endDate.getDate() + 365)
    start = todayStr
    end = formatDate(endDate)
  } else if (calendarMode.value === 'week') {
    const first = weekDays.value[0]
    const last = weekDays.value[weekDays.value.length - 1]
    start = first?.date ?? todayStr
    end = last?.date ?? todayStr
  } else {
    const y = viewYear.value
    const m = viewMonth.value
    start = `${y}-${String(m).padStart(2, '0')}-01`
    end = `${y}-${String(m).padStart(2, '0')}-${String(new Date(y, m, 0).getDate()).padStart(2, '0')}`
  }

  try {
    const result = await scheduleApi.getEvents({ start_date: start, end_date: end })
    events.value = result
    eventsCache.set(key, result)
  } catch {
    showToast('加载失败')
  } finally {
    loading.value = false
  }
}

function eventsForDate(date: string) {
  return events.value.filter(e => date && e.start_date <= date && e.end_date >= date)
}

function weekdayLabel(date: string) {
  const labels = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return labels[parseDate(date).getDay()] ?? ''
}

function lunarLabel(date: string) {
  if (!date) return ''
  try {
    const lunar = Lunar.fromDate(parseDate(date))
    const festival = lunar.getFestivals()?.[0]
    const label = (festival || lunar.getDayInChinese() || '').replace(/节$/u, '')
    return label.slice(0, 2)
  } catch {
    return ''
  }
}

const selectedDateDisplay = computed(() => {
  if (!selectedDate.value) return ''
  const lunar = lunarLabel(selectedDate.value)
  return lunar ? `${selectedDate.value} · ${lunar}` : selectedDate.value
})

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
    const publishedCount = items.filter(item => item.status === 'published').length
    const draftCount = items.length - publishedCount
    return {
      date,
      items,
      weekday: weekdayLabel(date),
      primaryType: primaryEventTypeForDate(date) ?? 'other',
      statusText: draftCount > 0 ? `已发布 ${publishedCount} · 草稿 ${draftCount}` : `已发布 ${publishedCount} 项`,
    }
  })
})

function openAgendaDate(date: string, items: ScheduleEvent[]) {
  selectedDate.value = date
  focusDate.value = date
  syncViewFromDate(date)
  selectedEventId.value = items[0]?.id ?? null
  activeTab.value = items[0]?.id ? 'attendance' : 'events'
}

// ─── 日期点击 → 事件列表 ────────────────────────────────────────────────────
const selectedDayEvents = computed(() => eventsForDate(selectedDate.value))

function clickDay(date: string) {
  selectedDate.value = date
  focusDate.value = date
  syncViewFromDate(date)
  selectedEventId.value = null
  activeTab.value = 'events'
}

// ─── 事件详情面板 ────────────────────────────────────────────────────────────
const selectedEventId = ref<number | null>(null)
const selectedEvent = computed(() =>
  events.value.find(e => e.id === selectedEventId.value) ?? null
)
const activeTab = ref<'events' | 'attendance' | 'lines'>('events')

// ─── 创建/编辑弹窗 ──────────────────────────────────────────────────────────
const showForm = ref(false)
const editingEvent = ref<ScheduleEvent | null>(null)
const formDefaultDate = ref(todayStr)
const reminding = ref(false)

function openCreate() {
  editingEvent.value = null
  formDefaultDate.value = selectedDate.value || focusDate.value || todayStr
  showForm.value = true
}
function openEdit(ev: ScheduleEvent) {
  editingEvent.value = ev
  formDefaultDate.value = ev.start_date
  showForm.value = true
}
function onEventSaved(ev: ScheduleEvent) {
  const wasEditing = !!editingEvent.value?.id
  selectedDate.value = ev.start_date
  focusDate.value = ev.start_date
  syncViewFromDate(ev.start_date)
  activeTab.value = 'events'
  selectedEventId.value = wasEditing ? ev.id : null
  loadEvents(true)
}

async function remindAllPending() {
  try {
    await showConfirmDialog({
      title: '一键催填',
      message: '将提醒所有未来已发布活动里尚未填报的队员，并在通知中聚合显示。是否继续？',
    })
    reminding.value = true
    const result = await scheduleApi.remindPendingEvents()
    showToast(result.message || `已提醒 ${result.reminded} 人`)
  } catch (e: any) {
    if (e?.response?.data?.detail) showToast(e.response.data.detail)
  } finally {
    reminding.value = false
  }
}

// ─── 发布 / 取消发布 ────────────────────────────────────────────────────────
async function togglePublish(ev: ScheduleEvent) {
  try {
    if (ev.status === 'published') {
      await showConfirmDialog({ title: '取消发布', message: '确认将此活动退回草稿状态？' })
      await scheduleApi.unpublishEvent(ev.id)
    } else {
      await scheduleApi.publishEvent(ev.id)
    }
    showToast(ev.status === 'published' ? '已退回草稿' : '已发布 ✓')
    loadEvents(true)
  } catch {}
}

// ─── 删除 ────────────────────────────────────────────────────────────────
async function deleteEvent(ev: ScheduleEvent) {
  try {
    await showConfirmDialog({ title: '删除活动', message: `确认删除「${ev.title}」？` })
    await scheduleApi.deleteEvent(ev.id)
    events.value = events.value.filter(e => e.id !== ev.id)
    selectedEventId.value = null
    showToast('已删除 ✓')
  } catch {}
}

// ─── 球队球员列表（供 LineDivisionManager 使用） ─────────────────────────────
const teamPlayers = ref<LinePlayerInfo[]>([])

async function loadTeamPlayers() {
  try {
    const res = await api.get('/players', { params: { status: 'active', page_size: 100 } })
    const list = res.data?.items ?? res.data ?? []
    teamPlayers.value = list.map((p: any) => ({
      player_id: p.id,
      player_name: p.username,
      display_name: p.display_name,
      conservative_rating: p.conservative_rating ?? 0,
      gender: p.gender ?? null,
      jersey_number: p.jersey_number ?? null,
    }))
  } catch {}
}

onMounted(() => {
  Promise.all([loadEvents(), loadTeamPlayers()])
})
</script>

<template>
  <div class="schedule-view">
    <van-nav-bar
      title="队伍日程管理"
      left-arrow
      @click-left="$router.back()"
    >
      <template #right>
        <van-icon name="plus" size="20" color="#90caf9" @click="openCreate" />
      </template>
    </van-nav-bar>

    <!-- 月历 / 周历 -->
    <div class="cal-card">
      <div class="cal-toolbar">
        <div class="cal-header">
          <van-icon name="arrow-left" @click="prevPeriod" class="nav-icon" />
          <span class="month-label">{{ displayLabel }}</span>
          <van-icon name="arrow" @click="nextPeriod" class="nav-icon" />
        </div>
        <div class="view-switch">
          <van-button round size="small" class="mode-btn" :type="calendarMode === 'month' ? 'primary' : 'default'" plain @click="switchMode('month')">月历</van-button>
          <van-button round size="small" class="mode-btn" :type="calendarMode === 'week' ? 'primary' : 'default'" plain @click="switchMode('week')">周历</van-button>
          <van-button round size="small" class="mode-btn" :type="calendarMode === 'agenda' ? 'primary' : 'default'" plain @click="switchMode('agenda')">日程表</van-button>
        </div>
      </div>
      <div class="range-hint">{{ calendarMode === 'month' ? '按月查看活动' : calendarMode === 'week' ? '按周查看并快速编辑活动' : '按列表浏览未来活动并直接进入出勤 / 分 Line' }}</div>
      <div class="event-legend">
        <span v-for="item in eventLegendItems" :key="item.key" class="event-legend__item">
          <i class="event-legend__swatch" :style="{ background: item.color }" />{{ item.label }}
        </span>
      </div>
      <div v-if="calendarMode !== 'agenda'" class="weekdays">
        <span v-for="d in ['日','一','二','三','四','五','六']" :key="d">{{ d }}</span>
      </div>
      <van-loading v-if="loading" size="18px" style="display:block;text-align:center;padding:8px" />
      <div v-else-if="calendarMode === 'agenda'" class="agenda-list">
        <div v-if="upcomingAgendaGroups.length === 0" class="empty-tip">暂无未来活动</div>
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
                <div class="agenda-day__status">{{ group.statusText }}</div>
              </div>
              <van-tag plain :color="eventTypeMeta[group.primaryType].color">{{ eventTypeMeta[group.primaryType].label }} · {{ group.items.length }} 项</van-tag>
            </div>
            <div class="agenda-day__events">
              <div v-for="item in group.items" :key="item.id" class="agenda-event-row">
                <i class="agenda-event-row__dot" :style="{ background: eventTypeColor[item.event_type] ?? '#456' }" />
                <span class="agenda-event-row__name">{{ item.title }}</span>
                <span class="agenda-event-row__meta">{{ item.status === 'published' ? '已发布' : '草稿' }}</span>
              </div>
            </div>
            <div class="agenda-day__cta">点按后可直接进入活动详情、出勤统计或分 Line</div>
          </div>
        </div>
      </div>
      <div v-else :class="['day-grid', { 'week-mode': calendarMode === 'week' }]">
        <div
          v-for="(cell, i) in displayDays"
          :key="`${calendarMode}-${cell.date}-${i}`"
          class="day-cell"
          :class="{
            today: cell.date === todayStr,
            selected: cell.date === selectedDate,
            has_event: cell.day && eventsForDate(cell.date).length > 0,
            empty: !cell.day,
          }"
          :style="cell.day ? dayCellStyle(cell.date) : undefined"
          @click="cell.day && clickDay(cell.date)"
        >
          <span v-if="cell.day" class="day-num">{{ cell.day }}</span>
          <span v-if="cell.day" class="day-lunar">{{ lunarLabel(cell.date) }}</span>
        </div>
      </div>
    </div>

    <!-- 底部面板 -->
    <div v-if="selectedDate" class="detail-panel">
      <div class="panel-head">
        <div class="panel-date">{{ selectedDateDisplay }}</div>
        <div class="panel-actions">
          <van-button size="mini" plain type="warning" class="ios-remind-btn" :loading="reminding" @click="remindAllPending">一键催填</van-button>
          <van-button size="mini" plain type="primary" @click="openCreate">+ 新建活动</van-button>
        </div>
      </div>

      <!-- 活动列表 -->
      <div v-if="activeTab === 'events' || !selectedEventId">
        <div v-if="selectedDayEvents.length === 0" class="empty-tip">当日无活动</div>
        <van-cell
          v-for="ev in selectedDayEvents"
          :key="ev.id"
          :title="ev.title"
          clickable
          @click="selectedEventId = ev.id; activeTab = 'attendance'"
        >
          <template #label>
            <div class="event-label-row">
              <van-tag
                :color="eventTypeColor[ev.event_type]"
                style="margin-right: 4px"
              >{{ { game:'外战', internal:'内战', training:'训练', other:'其他' }[ev.event_type] }}</van-tag>
              <van-tag
                :type="ev.status === 'published' ? 'success' : 'default'"
              >{{ ev.status === 'published' ? '已发布' : '草稿' }}</van-tag>
              <span class="event-date-range">{{ ev.start_date }}{{ ev.start_date !== ev.end_date ? ` ~ ${ev.end_date}` : '' }}</span>
            </div>
            <div class="attendance-summary-row">
              <span class="summary-chip summary-chip--neutral">已填{{ ev.attendance_count ?? 0 }}/{{ ev.total_players ?? 0 }}</span>
              <span class="summary-chip summary-chip--yes">出勤{{ ev.yes_count ?? 0 }}</span>
              <span class="summary-chip summary-chip--sdl">SDL{{ ev.sdl_count ?? 0 }}</span>
              <span class="summary-chip summary-chip--leave">请假{{ ev.leave_count ?? 0 }}</span>
              <span class="summary-chip summary-chip--neutral">未填{{ ev.not_submitted_count ?? 0 }}</span>
            </div>
            <div class="event-entry-actions">
              <van-button size="mini" plain type="primary" @click.stop="selectedEventId = ev.id; activeTab = 'attendance'">查看出勤</van-button>
              <van-button size="mini" plain type="success" @click.stop="selectedEventId = ev.id; activeTab = 'lines'">分 Line</van-button>
              <span class="event-entry-tip">从这里可直接进入统计或分组</span>
            </div>
          </template>
          <template #right-icon>
            <div class="event-right-actions">
              <van-button size="mini" plain @click.stop="openEdit(ev)">编辑</van-button>
              <van-button size="mini" plain :type="ev.status === 'published' ? 'warning' : 'primary'" @click.stop="togglePublish(ev)">
                {{ ev.status === 'published' ? '退回' : '发布' }}
              </van-button>
              <van-button size="mini" plain type="danger" @click.stop="deleteEvent(ev)">删</van-button>
            </div>
          </template>
        </van-cell>
        <div style="margin: 12px 16px">
          <van-button size="mini" plain type="primary" block @click="openCreate">+ 新增活动</van-button>
        </div>
      </div>

      <!-- 事件详情 tabs -->
      <template v-if="selectedEventId && selectedEvent">
        <div class="detail-tabs-header">
          <span @click="selectedEventId = null; activeTab = 'events'" class="back-link">← 返回列表</span>
          <span class="detail-title">{{ selectedEvent.title }}</span>
        </div>
        <van-tabs v-model:active="activeTab" class="detail-tabs">
          <van-tab name="attendance" title="出勤情况">
            <AttendanceDetailPanel
              :event="selectedEvent"
              :on-close="() => selectedEventId = null"
              :on-updated="() => loadEvents(true)"
            />
          </van-tab>
          <van-tab name="lines" title="分 Line">
            <LineDivisionManager
              :event="selectedEvent"
              :team-players="teamPlayers"
            />
          </van-tab>
        </van-tabs>
      </template>
    </div>

    <!-- 创建/编辑弹窗 -->
    <ScheduleEventForm
      v-model="showForm"
      :event="editingEvent"
      :default-date="formDefaultDate"
      @saved="onEventSaved"
    />
  </div>
</template>

<style scoped>
.schedule-view { min-height: 100vh; background: #050f1c; }
.cal-card {
  background: #0d1b2a; margin: 12px 16px;
  border-radius: 12px; padding: 12px;
}
.cal-toolbar {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  margin-bottom: 8px;
}
.cal-header {
  display: flex; align-items: center; justify-content: space-between; flex: 1;
}
.view-switch { display: flex; gap: 6px; flex-wrap: wrap; }
.mode-btn { min-width: 62px; }
.range-hint { font-size: 12px; color: #b8d4f0; margin-bottom: 8px; }
.event-legend { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.event-legend__item { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: #dbeafe; }
.event-legend__swatch { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
.month-label { font-size: 16px; font-weight: 600; color: #f8fbff; }
.nav-icon { color: #90caf9; cursor: pointer; font-size: 18px; padding: 4px; }
.weekdays {
  display: grid; grid-template-columns: repeat(7, 1fr);
  text-align: center; font-size: 11px; color: #546e7a; margin-bottom: 4px;
}
.day-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
.day-grid.week-mode .day-cell { min-height: 58px; }
.day-cell {
  min-height: 44px;
  padding: 3px 2px;
  border-radius: 6px;
  text-align: center;
  cursor: pointer;
  position: relative;
  transition: all .12s;
}
.day-cell.today { box-shadow: inset 0 0 0 2px #60a5fa; }
.day-cell.selected {
  background: linear-gradient(180deg, rgba(10, 132, 255, .22), rgba(10, 132, 255, .12)) !important;
  box-shadow: inset 0 0 0 2px #7dc1ff, 0 0 0 1px rgba(125, 193, 255, .28);
}
.day-cell.selected .day-num {
  color: #ffffff;
  text-shadow: 0 0 10px rgba(125, 193, 255, .3);
}
.day-cell.selected .day-lunar {
  color: #dff0ff;
}
.day-cell.has_event { background: #0f2035; }
.day-cell.empty { pointer-events: none; }
.day-num { display: block; font-size: 13px; color: #e0e0e0; font-weight: 700; line-height: 1.35; }
.day-lunar { display: block; font-size: 10px; color: #8fb3d9; line-height: 1.1; letter-spacing: .5px; }
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
.agenda-day__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.agenda-day__date { color: #f8fbff; font-weight: 700; font-size: 13px; }
.agenda-day__status { color: #93c5fd; font-size: 12px; margin-top: 2px; }
.agenda-day__events { display: grid; gap: 4px; }
.agenda-event-row {
  display: grid; grid-template-columns: 8px 1fr auto; align-items: center; gap: 8px; color: #eef6ff; font-size: 13px; padding: 4px 0;
  border-bottom: 1px dashed rgba(148, 163, 184, .2);
}
.agenda-event-row:last-child { border-bottom: none; }
.agenda-event-row__dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.agenda-event-row__name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.agenda-event-row__meta { color: #9ec5ef; font-size: 11px; }
.agenda-day__cta { margin-top: 8px; color: #b7d2ee; font-size: 11px; }

.detail-panel {
  background: #102238; margin: 0 16px 16px; border-radius: 12px; padding: 12px; border: 1px solid #284a6d;
}
.panel-head {
  display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; flex-wrap: wrap;
}
.panel-date { font-size: 14px; color: #dbeafe; font-weight: 700; }
.panel-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.event-right-actions { display: flex; align-items: center; gap: 4px; margin-left: 8px; }
.empty-tip { color: #9ec5ef; font-size: 13px; text-align: center; padding: 16px 0; }

:deep(.schedule-view .van-button) {
  font-weight: 600;
  border-radius: 12px;
  transition: all .18s ease;
  box-shadow: none;
  backdrop-filter: blur(10px);
}
:deep(.schedule-view .van-button--plain.van-button--default) {
  background: rgba(255, 255, 255, .08);
  color: #eef6ff;
  border-color: rgba(255, 255, 255, .08);
}
:deep(.schedule-view .van-button--plain.van-button--primary) {
  background: rgba(10, 132, 255, .16);
  color: #d9ebff;
  border-color: rgba(10, 132, 255, .24);
}
:deep(.schedule-view .van-button--plain.van-button--success) {
  background: rgba(48, 209, 88, .15);
  color: #c9f7d7;
  border-color: rgba(48, 209, 88, .22);
}
:deep(.schedule-view .van-button--plain.van-button--warning) {
  background: rgba(255, 159, 10, .16);
  color: #fde3b3;
  border-color: rgba(255, 159, 10, .24);
}
.ios-remind-btn {
  background: rgba(255, 159, 10, .14) !important;
  color: #ffe0a3 !important;
  border: 1px solid rgba(255, 159, 10, .28) !important;
  backdrop-filter: blur(10px);
}
:deep(.schedule-view .van-button--plain.van-button--danger) {
  background: rgba(255, 69, 58, .15);
  color: #ffd2cf;
  border-color: rgba(255, 69, 58, .22);
}
:deep(.schedule-view .van-button--primary) {
  background: #0a84ff;
  border-color: #0a84ff;
  color: #fff;
}
:deep(.schedule-view .van-button--success) {
  background: #30d158;
  border-color: #30d158;
  color: #06280f;
}
:deep(.schedule-view .van-button--warning) {
  background: #ff9f0a;
  border-color: #ff9f0a;
  color: #201000;
}
:deep(.schedule-view .van-button--danger) {
  background: #ff453a;
  border-color: #ff453a;
  color: #fff;
}
.event-label-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.event-date-range { font-size: 12px; color: #eaf3ff; font-weight: 600; }
.attendance-summary-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 4px;
  margin-top: 6px;
}
.event-entry-actions {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 8px;
}
.event-entry-tip { color: #8fb3d9; font-size: 11px; }
.summary-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  padding: 2px 3px;
  border-radius: 999px;
  font-size: 8px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  background: rgba(255, 255, 255, .06);
  color: #eef6ff;
  border: none;
}
.summary-chip::before {
  content: '';
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: currentColor;
  opacity: .72;
  margin-right: 3px;
  flex: 0 0 auto;
}
.summary-chip--yes { background: rgba(48, 209, 88, .14); color: #bdf5cd; }
.summary-chip--sdl { background: rgba(191, 90, 242, .14); color: #e5cbff; }
.summary-chip--leave { background: rgba(255, 159, 10, .16); color: #fde0a3; }
.summary-chip--neutral { background: rgba(148, 163, 184, .14); color: #e7f0fb; }

:deep(.van-cell) {
  background: #13263c;
  color: #eef6ff;
  margin-bottom: 8px;
  border-radius: 10px;
}
:deep(.van-cell__title) { color: #f8fbff; font-weight: 700; }
:deep(.van-cell__label) { color: #dbeafe; }

.detail-tabs-header {
  display: flex; align-items: center; gap: 12px; margin-bottom: 8px; padding: 0 4px;
}
:deep(.detail-tabs .van-tabs__wrap) {
  background: #0f2035 !important;
  border: 1px solid #244160;
  border-radius: 12px;
  margin-bottom: 8px;
}
:deep(.detail-tabs .van-tabs__nav),
:deep(.detail-tabs .van-tabs__nav--line) {
  background: #0f2035 !important;
}
:deep(.detail-tabs .van-tab) {
  color: #c7def7 !important;
}
:deep(.detail-tabs .van-tab--active) {
  color: #ffffff !important;
  font-weight: 700;
}
:deep(.detail-tabs .van-tab__text) {
  color: inherit !important;
}
:deep(.detail-tabs .van-tabs__line) {
  background: #60a5fa;
}
.back-link { color: #90caf9; font-size: 13px; cursor: pointer; }
.detail-title { font-size: 15px; font-weight: 600; color: #e0e0e0; }

@media (max-width: 768px) {
  .attendance-summary-row {
    gap: 2px;
  }

  .summary-chip {
    font-size: 7px;
    padding: 2px 2px;
  }

  .summary-chip::before {
    width: 3px;
    height: 3px;
    margin-right: 2px;
  }

  .event-right-actions {
    margin-left: 0;
    flex-wrap: wrap;
    justify-content: flex-end;
  }
}
</style>
