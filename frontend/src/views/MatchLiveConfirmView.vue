<template>
  <div class="live-confirm-page">
    <van-nav-bar title="确认实况结果" left-arrow @click-left="$router.back()" />

    <!-- 比分展示 -->
    <div class="score-display">
      <div class="score-team score-team--a">
        <div class="score-name">{{ matchType === 'external' ? '我方' : '队 A' }}</div>
        <div class="score-num">{{ scoreA }}</div>
      </div>
      <div class="score-sep">—</div>
      <div class="score-team score-team--b">
        <div class="score-num">{{ scoreB }}</div>
        <div class="score-name">{{ matchType === 'external' ? '对方' : '队 B' }}</div>
      </div>
    </div>

    <!-- 比赛信息 -->
    <van-cell-group inset title="比赛信息">
      <van-field v-model="matchDate" label="比赛日期" readonly @click="showDatePicker = true" />
      <van-field name="match_type" label="比赛类型">
        <template #input>
          <van-radio-group v-model="matchType" direction="horizontal">
            <van-radio name="internal">🆚 内战</van-radio>
            <van-radio name="external">🌍 外战</van-radio>
          </van-radio-group>
        </template>
      </van-field>
      <template v-if="matchType === 'external'">
        <van-field v-model="opponentName" label="对方队名" placeholder="可选填写" />
        <van-field label="对手强度">
          <template #input>
            <van-stepper v-model="opponentStrength" min="1" max="10" />
          </template>
        </van-field>
      </template>
      <van-field v-model="notes" label="备注" required placeholder="必填：请说明比赛场景" />
    </van-cell-group>

    <!-- 统计汇总（从事件自动计算） -->
    <van-cell-group inset :title="matchType === 'external' ? '我方球员统计' : '队A 统计（实况自动汇总）'">
      <van-cell
        v-for="p in teamAPlayers"
        :key="p.id"
        :title="p.display_name || p.username"
      >
        <template #label>
          <div class="stat-chips">
            <template v-if="playerStats.get(p.id)">
              <span v-if="(playerStats.get(p.id)?.goals ?? 0) > 0" class="stat-chip stat-chip--G">{{ playerStats.get(p.id)?.goals }}G</span>
              <span v-if="(playerStats.get(p.id)?.assists ?? 0) > 0" class="stat-chip stat-chip--A">{{ playerStats.get(p.id)?.assists }}A</span>
              <span v-if="(playerStats.get(p.id)?.defense ?? 0) > 0" class="stat-chip stat-chip--D">{{ playerStats.get(p.id)?.defense }}D</span>
              <span v-if="(playerStats.get(p.id)?.turnovers ?? 0) > 0" class="stat-chip stat-chip--T">{{ playerStats.get(p.id)?.turnovers }}T</span>
              <span v-if="(playerStats.get(p.id)?.goals ?? 0) === 0 && (playerStats.get(p.id)?.assists ?? 0) === 0 && (playerStats.get(p.id)?.defense ?? 0) === 0 && (playerStats.get(p.id)?.turnovers ?? 0) === 0" style="color:#c8c9cc;font-size:12px">无数据</span>
            </template>
            <span v-else style="color:#c8c9cc;font-size:12px">无数据</span>
          </div>
        </template>
      </van-cell>
    </van-cell-group>
    <van-cell-group v-if="matchType === 'internal'" inset title="队B 统计（实况自动汇总）">
      <van-cell
        v-for="p in teamBPlayers"
        :key="p.id"
        :title="p.display_name || p.username"
      >
        <template #label>
          <div class="stat-chips">
            <template v-if="playerStats.get(p.id)">
              <span v-if="(playerStats.get(p.id)?.goals ?? 0) > 0" class="stat-chip stat-chip--G">{{ playerStats.get(p.id)?.goals }}G</span>
              <span v-if="(playerStats.get(p.id)?.assists ?? 0) > 0" class="stat-chip stat-chip--A">{{ playerStats.get(p.id)?.assists }}A</span>
              <span v-if="(playerStats.get(p.id)?.defense ?? 0) > 0" class="stat-chip stat-chip--D">{{ playerStats.get(p.id)?.defense }}D</span>
              <span v-if="(playerStats.get(p.id)?.turnovers ?? 0) > 0" class="stat-chip stat-chip--T">{{ playerStats.get(p.id)?.turnovers }}T</span>
              <span v-if="(playerStats.get(p.id)?.goals ?? 0) === 0 && (playerStats.get(p.id)?.assists ?? 0) === 0 && (playerStats.get(p.id)?.defense ?? 0) === 0 && (playerStats.get(p.id)?.turnovers ?? 0) === 0" style="color:#c8c9cc;font-size:12px">无数据</span>
            </template>
            <span v-else style="color:#c8c9cc;font-size:12px">无数据</span>
          </div>
        </template>
      </van-cell>
    </van-cell-group>

    <!-- 实况记录预览 -->
    <van-cell-group inset :title="`比赛记录（共 ${allEvents.length} 条）`" v-if="allEvents.length > 0">
      <van-cell
        v-for="(evt, i) in previewEvents"
        :key="i"
        :title="evt.label"
        :label="evt.elapsed"
      />
      <van-cell v-if="allEvents.length > 5" :title="`... 还有 ${allEvents.length - 5} 条记录`" />
    </van-cell-group>

    <div style="margin: 16px; display: flex; flex-direction: column; gap: 8px">
      <van-button round block type="primary" :loading="submitting" @click="handleSubmit">
        提交保存比赛记录
      </van-button>
      <van-button round block plain @click="$router.back()">
        返回继续录入
      </van-button>
    </div>

    <van-popup v-model:show="showDatePicker" position="bottom">
      <van-date-picker
        v-model="dateParts"
        title="选择日期"
        @confirm="onDateConfirm"
        @cancel="showDatePicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import api from '@/api'

interface Player {
  id: number
  username: string
  display_name: string | null
}

interface LiveEvent {
  event_type: string
  team_side: string
  label: string
  elapsed: string
  player_id?: number
  assist_player_id?: number | null
  is_break?: boolean
}

interface ConfirmState {
  scoreA: number
  scoreB: number
  events: LiveEvent[]
  elapsedSeconds: number
  teamAIds: number[]
  teamBIds: number[]
  teamAPlayers: Player[]
  teamBPlayers: Player[]
  matchType?: string
  notes?: string
}

const router = useRouter()

// 读取实况数据
const raw = sessionStorage.getItem('live_confirm_state')
let state: ConfirmState | null = null
if (raw) {
  try { state = JSON.parse(raw) } catch { /* ignore */ }
}

if (!state) {
  showToast('无实况数据，请重新录入')
  router.replace({ name: 'match-new' })
}

const scoreA = ref(state?.scoreA ?? 0)
const scoreB = ref(state?.scoreB ?? 0)
const allEvents = ref<LiveEvent[]>(state?.events ?? [])
const teamAPlayers = ref<Player[]>(state?.teamAPlayers ?? [])
const teamBPlayers = ref<Player[]>(state?.teamBPlayers ?? [])
const teamAIds = ref<number[]>(state?.teamAIds ?? [])
const teamBIds = ref<number[]>(state?.teamBIds ?? [])

// 表单字段
const today = new Date()
const dateParts = ref([
  String(today.getFullYear()),
  String(today.getMonth() + 1).padStart(2, '0'),
  String(today.getDate()).padStart(2, '0'),
])
const matchDate = ref(today.toISOString().slice(0, 10))
const matchType = ref<'internal' | 'external'>(state?.matchType === 'external' ? 'external' : 'internal')
const opponentName = ref('')
const opponentStrength = ref(5)
const notes = ref(state?.notes ?? '')
const showDatePicker = ref(false)
const submitting = ref(false)

function onDateConfirm({ selectedValues }: { selectedValues: string[] }) {
  const [y, m, d] = selectedValues
  matchDate.value = `${y}-${m}-${d}`
  showDatePicker.value = false
}

// 从事件流计算球员统计
const playerStats = computed(() => {
  const map = new Map<number, { goals: number; assists: number; defense: number; turnovers: number }>()
  const get = (id: number) => {
    if (!map.has(id)) map.set(id, { goals: 0, assists: 0, defense: 0, turnovers: 0 })
    return map.get(id)!
  }
  for (const evt of allEvents.value) {
    if (evt.event_type === 'goal' && evt.player_id) {
      get(evt.player_id).goals++
      if (evt.assist_player_id != null) get(evt.assist_player_id).assists++
    } else if (evt.event_type === 'defense' && evt.player_id) {
      get(evt.player_id).defense++
    } else if (evt.event_type === 'turnover' && evt.player_id) {
      get(evt.player_id).turnovers++
    }
  }
  return map
})

function statsLabel(playerId: number): string {
  const s = playerStats.value.get(playerId)
  if (!s) return '无数据'
  const parts: string[] = []
  if (s.goals > 0) parts.push(`${s.goals}进球`)
  if (s.assists > 0) parts.push(`${s.assists}助攻`)
  if (s.defense > 0) parts.push(`${s.defense}防守`)
  if (s.turnovers > 0) parts.push(`${s.turnovers}失误`)
  return parts.join(' · ') || '无数据'
}

const previewEvents = computed(() => allEvents.value.slice(-5).reverse())

function parseElapsed(str: string): number {
  const parts = str.split(':')
  if (parts.length < 2) return 0
  return (parseInt(parts[0] ?? '0') * 60) + parseInt(parts[1] ?? '0')
}

async function handleSubmit() {
  if (!notes.value.trim()) {
    showToast('请填写比赛备注')
    return
  }
  submitting.value = true
  try {
    const buildTeamEntry = (ids: number[]) =>
      ids.map(pid => {
        const s = playerStats.value.get(pid)
        return {
          player_id: pid,
          goals: s?.goals ?? 0,
          assists: s?.assists ?? 0,
          plus_minus: s?.defense ?? 0,
          turnovers: s?.turnovers ?? 0,
        }
      })

    const eventsPayload = allEvents.value
      .filter(e => ['goal', 'defense', 'halftime', 'turnover'].includes(e.event_type))
      .map(e => ({
        event_type: e.event_type,
        team_side: (e.team_side && e.team_side !== 'system') ? e.team_side : null,
        player_id: e.player_id ?? null,
        assist_player_id: e.assist_player_id ?? null,
        is_break: e.is_break ?? false,
        elapsed_seconds: parseElapsed(e.elapsed),
      }))

    const payload: Record<string, unknown> = {
      match_date: matchDate.value,
      match_type: matchType.value,
      score_us: scoreA.value,
      score_them: scoreB.value,
      data_level: 3,
      team_a: buildTeamEntry(teamAIds.value),
      team_b: buildTeamEntry(teamBIds.value),
      events: eventsPayload,
      notes: notes.value.trim(),
    }

    if (matchType.value === 'external') {
      payload.opponent_strength = opponentStrength.value
      payload.opponent_name = opponentName.value || undefined
    }

    await api.post('/matches', payload)
    sessionStorage.removeItem('live_confirm_state')
    showToast({ message: '录入成功，评分已更新', type: 'success' })
    router.push('/home')
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '提交失败，请检查数据')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.live-confirm-page {
  padding-bottom: 40px;
  min-height: 100vh;
  background: #f7f8fa;
}

.score-display {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
  background: linear-gradient(135deg, #0f172a, #1e3a5f);
  color: #fff;
  gap: 32px;
}

.score-team {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.score-team--a .score-num { color: #60a5fa; }
.score-team--b .score-num { color: #fb923c; }

.score-name {
  font-size: 14px;
  color: #93c5fd;
  margin-bottom: 4px;
}

.score-num {
  font-size: 56px;
  font-weight: 700;
  color: #fff;
}

.score-sep {
  font-size: 32px;
  color: #64748b;
}

/* 统计 chip 标签 */
.stat-chips {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 2px;
}

.stat-chip {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 99px;
  line-height: 1.5;
}

.stat-chip--G { background: #dbeafe; color: #1d4ed8; }
.stat-chip--A { background: #d1fae5; color: #059669; }
.stat-chip--D { background: #fef3c7; color: #92400e; }
.stat-chip--T { background: #fee2e2; color: #b91c1c; }
</style>
