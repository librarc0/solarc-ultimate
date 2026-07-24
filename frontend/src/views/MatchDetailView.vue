<template>
  <div class="match-detail-page">
    <van-nav-bar
      title="比赛详情"
      left-arrow
      @click-left="$router.back()"
    />

    <van-loading v-if="loading" class="page-loading" type="spinner" />

    <template v-else-if="match">
      <!-- 比分卡片 -->
      <van-cell-group inset class="score-card">
        <div class="score-row">
          <div class="team-score">
            <span class="score-num">{{ match.team_a_score }}</span>
            <span class="team-label">我方</span>
          </div>
          <div class="vs-divider">VS</div>
          <div class="team-score">
            <span class="score-num">{{ match.team_b_score }}</span>
            <span class="team-label">对方</span>
          </div>
        </div>
        <div class="match-meta">
          <van-tag :type="statusType">{{ statusLabel }}</van-tag>
          <span class="meta-text">{{ formatDate(match.match_date) }}</span>
          <span class="meta-text">Level {{ match.data_level }}</span>
        </div>
        <div v-if="match.created_by_name" class="notes-text" style="margin-top:4px">提交者：{{ match.created_by_name }}</div>
        <div v-if="match.notes" class="notes-text">备注：{{ match.notes }}</div>
      </van-cell-group>

      <!-- 球员统计 -->
      <template v-if="match.participants && match.participants.length">
        <van-divider content-position="left">A 队球员</van-divider>
        <van-cell-group inset>
          <van-cell
            v-for="p in teamA"
            :key="p.player_id"
            :title="playerName(p.player_id)"
            :label="statsLabel(p)"
          >
            <template #right-icon>
              <van-tag v-if="p.is_mvp" type="warning">MVP</van-tag>
            </template>
          </van-cell>
        </van-cell-group>

        <van-divider content-position="left">B 队球员</van-divider>
        <van-cell-group inset>
          <van-cell
            v-for="p in teamB"
            :key="p.player_id"
            :title="playerName(p.player_id)"
            :label="statsLabel(p)"
          >
            <template #right-icon>
              <van-tag v-if="p.is_mvp" type="warning">MVP</van-tag>
            </template>
          </van-cell>
        </van-cell-group>
      </template>

      <!-- 实况时间轴 -->
      <template v-if="events.length > 0">
        <van-divider content-position="left">比赛实况</van-divider>
        <div class="events-list">
          <div
            v-for="e in events"
            :key="e.id"
            class="event-row"
            :class="{
              'event-row--a': e.team_side === 'A',
              'event-row--b': e.team_side === 'B',
              'event-row--sys': !e.team_side || e.event_type === 'halftime',
            }"
          >
            <span class="event-time">{{ secondsToTime(e.elapsed_seconds) }}</span>
            <span class="event-body">{{ eventLabel(e) }}</span>
          </div>
        </div>
      </template>

      <div class="bottom-spacer"></div>
    </template>

    <van-empty v-else description="比赛不存在" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { showToast } from 'vant'
import api from '@/api'

const route = useRoute()
const matchId = Number(route.params.id)
const loading = ref(true)

interface Participant {
  player_id: number
  player_name?: string
  team_side: 'A' | 'B'
  goals: number | null
  assists: number | null
  defenses: number | null
  turnovers: number | null
  plus_minus: number | null
  is_mvp: boolean
  mu_before?: number
  mu_after?: number
}

interface MatchDetail {
  id: number
  match_type: string
  match_date: string
  team_a_score: number
  team_b_score: number
  status: string
  data_level: number
  notes: string | null
  created_by_id?: number
  created_by_name?: string
  participants: Participant[]
}

const match = ref<MatchDetail | null>(null)
// player name cache
const playerNames = ref<Record<number, string>>({})

const teamA = computed(() => match.value?.participants.filter(p => p.team_side === 'A') ?? [])
const teamB = computed(() => match.value?.participants.filter(p => p.team_side === 'B') ?? [])

const statusType = computed(() => {
  const s = match.value?.status
  if (s === 'approved') return 'success'
  if (s === 'rejected') return 'danger'
  return 'warning'
})
const statusLabel = computed(() => {
  const s = match.value?.status
  if (s === 'approved') return '已通过'
  if (s === 'rejected') return '已拒绝'
  if (s === 'pending_approval') return '待审批'
  return s ?? ''
})

function formatDate(d: string) {
  if (!d) return ''
  const str = /[Z+]/.test(d) ? d : d + 'Z'
  return new Date(str).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  })
}

function playerName(id: number) {
  return playerNames.value[id] ?? `Player #${id}`
}

function statsLabel(p: Participant) {
  const parts: string[] = []
  const dataLevel = match.value?.data_level ?? 1
  const isLiveMatch = events.value.length > 0

  if (p.goals != null) parts.push(`${p.goals}进球`)
  if (p.assists != null) parts.push(`${p.assists}助攻`)

  if (isLiveMatch) {
    // 实况比赛：从 events 统计防守/失误次数
    const defCount = events.value.filter(e => e.event_type === 'defense' && e.player_id === p.player_id).length
    if (defCount > 0) parts.push(`${defCount}防守`)
    const toCount = events.value.filter(e => e.event_type === 'turnover' && e.player_id === p.player_id).length
    if (toCount > 0) parts.push(`${toCount}失误`)
    if (p.plus_minus != null) parts.push(`+/- ${p.plus_minus}`)
  } else if (dataLevel >= 3) {
    // Level3 录入：defenses = 防守次数，plus_minus = 得分差
    if (p.defenses != null && p.defenses > 0) parts.push(`${p.defenses}防守`)
    if (p.turnovers != null && p.turnovers > 0) parts.push(`${p.turnovers}失误`)
    if (p.plus_minus != null) parts.push(`+/- ${p.plus_minus}`)
  } else {
    if (p.plus_minus != null) parts.push(`+/- ${p.plus_minus}`)
    if (p.turnovers != null && p.turnovers > 0) parts.push(`${p.turnovers}失误`)
  }

  if (p.mu_after != null && p.mu_before != null) {
    const deltaNum = p.mu_after - p.mu_before
    const delta = deltaNum.toFixed(2)
    parts.push(`Δμ ${deltaNum > 0 ? '+' : ''}${delta}`)
  }
  return parts.join(' · ')
}

async function loadMatch() {
  loading.value = true
  try {
    const res = await api.get(`/matches/${matchId}`)
    match.value = res.data
    if (res.data.participants?.length) {
      const nameMap: Record<number, string> = {}
      for (const p of res.data.participants as Participant[]) {
        nameMap[p.player_id] = p.player_name ?? `#${p.player_id}`
      }
      playerNames.value = nameMap
    }
    // load events
    try {
      const evRes = await api.get(`/matches/${matchId}/events`)
      events.value = evRes.data ?? []
    } catch { /* events optional */ }
  } catch {
    showToast('加载失败')
  } finally {
    loading.value = false
  }
}

// ─── Events helpers ────────────────────────────────────────────────────────
interface MatchEvent {
  id: number
  event_type: string
  team_side: string | null
  player_id: number | null
  assist_player_id: number | null
  elapsed_seconds: number | null
  is_break?: boolean
}
const events = ref<MatchEvent[]>([])

function secondsToTime(s: number | null): string {
  if (s == null) return ''
  const m = Math.floor(s / 60).toString().padStart(2, '0')
  const sec = (s % 60).toString().padStart(2, '0')
  return `${m}:${sec}`
}

function eventLabel(e: MatchEvent): string {
  const scorer = e.player_id ? playerName(e.player_id) : '?'
  const assist = e.assist_player_id ? playerName(e.assist_player_id) : null
  const side = e.team_side ? `[${e.team_side}队] ` : ''
  if (e.event_type === 'goal') {
    return `${side}${scorer} 得分${assist ? ` (助攻: ${assist})` : ''}${e.is_break ? ' ⚡ BREAK' : ''}`
  }
  if (e.event_type === 'defense') {
    return `${side}🛡 ${scorer} 防守${assist ? ` (拦截: ${assist})` : ''}`
  }
  if (e.event_type === 'halftime') return '⏱ 半场'
  if (e.event_type === 'start') return '▶ 比赛开始'
  if (e.event_type === 'end') return '🏁 比赛结束'
  return `${side}${e.event_type}`
}

onMounted(loadMatch)
</script>

<style scoped>
.page-loading {
  display: flex;
  justify-content: center;
  padding: 48px 0;
}
.score-card {
  margin: 12px 16px;
  padding: 16px;
}
.score-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 32px;
  padding: 16px 0;
}
.team-score {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.score-num {
  font-size: 48px;
  font-weight: 700;
  color: var(--van-text-color);
}
.team-label {
  font-size: 12px;
  color: var(--van-text-color-3);
}
.vs-divider {
  font-size: 18px;
  color: var(--van-text-color-2);
  font-weight: 600;
}
.match-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
  padding-bottom: 8px;
}
.meta-text {
  font-size: 12px;
  color: var(--van-text-color-3);
}
.notes-text {
  font-size: 12px;
  color: var(--van-text-color-2);
  padding-top: 4px;
}
.bottom-spacer {
  height: 32px;
}
.events-list {
  margin: 0 16px 12px;
  border-radius: 8px;
  overflow: hidden;
}
.event-row {
  display: flex;
  gap: 12px;
  padding: 8px 12px;
  font-size: 13px;
  border-bottom: 1px solid #1e293b;
  background: #0f172a;
}
.event-row--a { border-left: 3px solid #3b82f6; }
.event-row--b { border-left: 3px solid #f59e0b; }
.event-row--sys { border-left: 3px solid #64748b; justify-content: center; }
.event-time { color: #64748b; min-width: 36px; font-size: 11px; padding-top: 1px; }
.event-body { color: #e2e8f0; flex: 1; }
</style>
