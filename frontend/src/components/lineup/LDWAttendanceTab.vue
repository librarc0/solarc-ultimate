<script setup lang="ts">
/**
 * LDWAttendanceTab — 出勤选人 Tab
 * 显示全量球员，支持按出勤状态过滤和搜索，用户可手动勾选参与本次活动的球员
 */
import { ref, computed } from 'vue'
import { showToast } from 'vant'
import {
  type WizardPlayer,
  type AttendanceStatus,
  type WizardMatchType,
  normalizeAttendance,
  getPlayerLabel,
} from '@/composables/useLineDivisionWizard'

const props = defineProps<{
  allPlayers: WizardPlayer[]
  attendingIds: number[]
  attendanceMap: Record<number, AttendanceStatus>
  matchType: WizardMatchType
  loadingPlayers: boolean
}>()

const emit = defineEmits<{
  (e: 'update:attendingIds', ids: number[]): void
  (e: 'selectByStatus', statuses: AttendanceStatus[]): void
  (e: 'clearAll'): void
  (e: 'addGuest', name: string, gender: 'M' | 'F' | ''): void
  (e: 'removeGuest', id: number): void
}>()

const guestName = ref('')
const guestGender = ref<'M' | 'F' | 'N'>('M')

const guestPlayers = computed(() => props.allPlayers.filter(p => p.is_guest))

function doAddGuest() {
  const name = guestName.value.trim()
  if (!name) { showToast('请输入外援姓名'); return }
  const gender = guestGender.value === 'N' ? '' : guestGender.value
  emit('addGuest', name, gender as 'M' | 'F' | '')
  guestName.value = ''}

const keyword = ref('')
const statusFilter = ref<'all' | AttendanceStatus>('all')

const statusMeta: Record<AttendanceStatus, { label: string; color: string }> = {
  yes: { label: '已到', color: '#22c55e' },
  sdl: { label: 'SDL', color: '#8b5cf6' },
  leave: { label: '请假', color: '#f59e0b' },
  not_submitted: { label: '未填', color: '#64748b' },
}

const statusOrder: Record<AttendanceStatus, number> = {
  yes: 0, sdl: 1, leave: 2, not_submitted: 3,
}

const filterOptions = [
  { key: 'all' as const, label: '全部' },
  { key: 'yes' as const, label: '已到' },
  { key: 'sdl' as const, label: 'SDL' },
  { key: 'leave' as const, label: '请假' },
  { key: 'not_submitted' as const, label: '未填' },
]

const filteredPlayers = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return props.allPlayers
    .map(p => ({ ...p, _status: normalizeAttendance(props.attendanceMap[p.id]) }))
    .filter(p => {
      const matchKw = !kw || `${p.display_name ?? ''} ${p.username}`.toLowerCase().includes(kw)
      const matchStatus = statusFilter.value === 'all' || p._status === statusFilter.value
      return matchKw && matchStatus
    })
    .sort((a, b) => {
      const od = statusOrder[a._status] - statusOrder[b._status]
      if (od !== 0) return od
      return (b.conservative_rating ?? 0) - (a.conservative_rating ?? 0)
    })
})

const attendingSet = computed(() => new Set(props.attendingIds))

function toggle(playerId: number) {
  const next = [...props.attendingIds]
  const idx = next.indexOf(playerId)
  if (idx >= 0) next.splice(idx, 1)
  else next.push(playerId)
  emit('update:attendingIds', next)
}

function selectFiltered() {
  const filtered = filteredPlayers.value.map(p => p.id)
  const merged = Array.from(new Set([...props.attendingIds, ...filtered]))
  emit('update:attendingIds', merged)
}

function selectYesOnly() {
  emit('selectByStatus', ['yes'])
}

function selectPresent() {
  emit('selectByStatus', ['yes', 'sdl'])
}
</script>

<template>
  <div class="attendance-tab">
    <van-loading v-if="loadingPlayers" type="spinner" vertical style="padding: 32px 0" />
    <template v-else>
      <!-- 操作说明 -->
      <div class="tip-banner">
        <div class="tip-banner__title">选择本次出勤球员</div>
        <div class="tip-banner__desc">
          已勾选 <strong>{{ attendingIds.length }}</strong> 人参与本次分 line。
          <template v-if="Object.keys(attendanceMap).length > 0">
            绿色卡片为已确认出勤球员。
          </template>
        </div>
      </div>

      <!-- 快捷操作 -->
      <div class="action-row">
        <van-button size="small" type="success" plain @click="selectYesOnly">✓ 全选已到</van-button>
        <van-button size="small" type="primary" plain @click="selectPresent">选已到/SDL</van-button>
        <van-button size="small" plain type="primary" @click="selectFiltered">选当前全部</van-button>
        <van-button size="small" plain type="warning" @click="$emit('clearAll')">清空</van-button>
      </div>

      <!-- 搜索 + 状态筛选 -->
      <van-field
        v-model="keyword"
        clearable
        placeholder="搜索球员名 / 展示名"
        left-icon="search"
        class="search-field"
      />
      <div class="filter-row">
        <van-button
          v-for="opt in filterOptions"
          :key="opt.key"
          size="mini"
          :type="statusFilter === opt.key ? 'primary' : 'default'"
          plain
          @click="statusFilter = opt.key"
        >{{ opt.label }}</van-button>
      </div>

      <!-- 外援区域 -->
      <div class="guest-section">
        <div class="guest-section__title">外援 / 临时球员</div>
        <div class="guest-add-row">
          <van-field v-model="guestName" clearable placeholder="外援姓名" class="guest-name-field" />
          <van-radio-group v-model="guestGender" direction="horizontal" class="guest-gender">
            <van-radio name="M"><span style="color:#60a5fa">♂ 男</span></van-radio>
            <van-radio name="F"><span style="color:#f472b6">♀ 女</span></van-radio>
            <van-radio name="N">未知</van-radio>
          </van-radio-group>
          <van-button size="small" type="primary" @click="doAddGuest">+ 添加</van-button>
        </div>
        <div v-if="guestPlayers.length" class="guest-list">
          <div v-for="g in guestPlayers" :key="g.id" class="guest-chip">
            <span :style="{ color: g.gender === 'M' ? '#60a5fa' : g.gender === 'F' ? '#f472b6' : '#94a3b8' }">
              {{ g.gender === 'M' ? '♂' : g.gender === 'F' ? '♀' : '—' }}
            </span>
            <span class="guest-chip__name">{{ g.display_name }}</span>
            <van-icon name="cross" size="14" color="#e53935" @click="$emit('removeGuest', g.id)" />
          </div>
        </div>
      </div>

      <!-- 球员网格 -->
      <div v-if="filteredPlayers.length === 0" class="empty-hint">没有符合条件的球员</div>
      <div v-else class="pool-grid">
        <div
          v-for="p in filteredPlayers"
          :key="p.id"
          class="player-card"
          :class="{
            'player-card--selected': attendingSet.has(p.id),
            [`player-card--${p._status}`]: true,
          }"
          @click="toggle(p.id)"
        >
          <div class="player-card__top">
            <span class="player-card__name">{{ getPlayerLabel(p) }}</span>
            <span class="rating-badge">{{ p.conservative_rating.toFixed(0) }}</span>
          </div>
          <div class="player-card__meta">
            <span class="status-pill" :style="{ background: statusMeta[p._status].color }">
              {{ statusMeta[p._status].label }}
            </span>
            <van-icon :name="attendingSet.has(p.id) ? 'checked' : 'circle'" :color="attendingSet.has(p.id) ? '#22c55e' : '#64748b'" />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.attendance-tab { padding: 0 0 16px; }

.tip-banner {
  background: #11263d; border: 1px solid #244160; border-radius: 12px;
  padding: 10px 12px; margin-bottom: 10px;
}
.tip-banner__title { color: #eff6ff; font-weight: 700; font-size: 13px; }
.tip-banner__desc { color: #b7d2ee; font-size: 12px; margin-top: 4px; line-height: 1.5; }

.action-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.search-field { margin-bottom: 8px; }
.filter-row { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }

.pool-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
}

.player-card {
  background: #152841; border: 1px solid #244160; border-radius: 10px;
  padding: 8px 10px; cursor: pointer; transition: all .15s;
}
.player-card--selected { border-color: #22c55e; background: #0f3320; }
.player-card--yes { box-shadow: 0 0 0 1px rgba(34, 197, 94, .2); }
.player-card__top {
  display: flex; justify-content: space-between; align-items: center; gap: 6px;
}
.player-card__name { color: #e2e8f0; font-size: 12px; font-weight: 600; line-height: 1.4; }
.player-card__meta {
  display: flex; justify-content: space-between; align-items: center; margin-top: 6px;
}
.status-pill {
  display: inline-flex; align-items: center; padding: 1px 6px;
  border-radius: 999px; color: #fff; font-size: 10px;
}
.rating-badge { font-size: 10px; color: #ffd54f; }
.empty-hint { color: #6f8cab; font-size: 12px; text-align: center; padding: 24px 0; }

.guest-section {
  background: #0d1f35; border: 1px solid #244160; border-radius: 10px;
  padding: 10px; margin-bottom: 10px;
}
.guest-section__title { color: #93c5fd; font-size: 12px; font-weight: 700; margin-bottom: 8px; }
.guest-add-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.guest-name-field { flex: 1; min-width: 100px; }
.guest-gender { display: flex; gap: 8px; font-size: 12px; }
.guest-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.guest-chip {
  display: inline-flex; align-items: center; gap: 6px;
  background: #1e3a5f; border: 1px solid #3b5a8a; border-radius: 8px; padding: 4px 8px;
}
.guest-chip__name { color: #e2e8f0; font-size: 12px; }
</style>
