import type { Ref } from 'vue'

import api from '@/api'
import type { LiveEvent } from '@/composables/useLiveEvents'

export interface LivePlayer {
  id: number
  username: string
  display_name: string | null
}

interface DraftEventLike {
  event_type: 'goal' | 'defense' | 'turnover' | 'halftime'
  team_side?: 'A' | 'B' | null
  player_id?: number | null
  assist_player_id?: number | null
  is_break?: boolean
  elapsed_seconds?: number
  payload?: {
    score_a?: number
    score_b?: number
  }
}

interface DraftLike {
  team_a_ids?: number[]
  team_b_ids?: number[]
  match_type: 'internal' | 'external'
  notes?: string
  team_a_score?: number
  team_b_score?: number
  duration_seconds?: number
  last_event_seq?: number
  snapshot?: {
    is_halftime?: boolean
  }
  events?: DraftEventLike[]
}

interface DraftRestoreContext {
  teamAIds: Ref<number[]>
  teamBIds: Ref<number[]>
  teamAPlayers: Ref<LivePlayer[]>
  teamBPlayers: Ref<LivePlayer[]>
  matchType: Ref<'internal' | 'external'>
  liveNotes: Ref<string>
  scoreA: Ref<number>
  scoreB: Ref<number>
  elapsedSeconds: Ref<number>
  nextSeq: Ref<number>
  isHalftime: Ref<boolean>
  events: Ref<LiveEvent[]>
  fetchPrediction: (aIds: number[], bIds: number[]) => Promise<void>
  startTimer: () => void
  loadPendingQueue: () => void
  syncPendingQueue: () => Promise<void>
  startLockHeartbeat: () => void
}

interface NewDraftInitContext {
  draftId: Ref<number | null>
  teamAIds: Ref<number[]>
  teamBIds: Ref<number[]>
  teamAPlayers: Ref<LivePlayer[]>
  teamBPlayers: Ref<LivePlayer[]>
  matchType: Ref<'internal' | 'external'>
  liveNotes: Ref<string>
  fetchPrediction: (aIds: number[], bIds: number[]) => Promise<void>
  loadPendingQueue: () => void
  startLockHeartbeat: () => void
}

interface DraftLockedDetail {
  code?: string
  locked_by?: string
}

interface RestoreResult {
  ok: boolean
  reason?: 'locked' | 'takeover_required' | 'error'
  lockedBy?: string
}

interface InitResult {
  ok: boolean
  reason?: 'missing_entry' | 'create_failed'
}

interface LiveEntryState {
  teamAIds?: number[]
  teamBIds?: number[]
  players?: LivePlayer[]
  matchType?: string
  notes?: string
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0')
  const s = (seconds % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

function rebuildEventsFromDraft(draftEvents: DraftEventLike[], players: LivePlayer[]): LiveEvent[] {
  const nameById = new Map<number, string>()
  for (const p of players) nameById.set(p.id, p.display_name || p.username)

  const rebuilt = draftEvents.map((e): LiveEvent => {
    const elapsed = formatElapsed(e.elapsed_seconds ?? 0)
    if (e.event_type === 'goal') {
      const scorer = e.player_id ? (nameById.get(e.player_id) || '未知') : '对方'
      const assist = e.assist_player_id ? ` (助攻: ${nameById.get(e.assist_player_id) || '未知'})` : ''
      return {
        event_type: 'goal' as const,
        team_side: e.team_side ?? 'B',
        label: `${scorer} 得分${assist}`,
        elapsed,
        player_id: e.player_id ?? undefined,
        assist_player_id: e.assist_player_id ?? undefined,
        is_break: !!e.is_break,
        score_a: e.payload?.score_a,
        score_b: e.payload?.score_b,
      }
    }
    if (e.event_type === 'defense') {
      const defender = e.player_id ? (nameById.get(e.player_id) || '未知') : '未知'
      return {
        event_type: 'defense' as const,
        team_side: (e.team_side ?? 'A') as 'A' | 'B',
        label: `🛡 ${defender} 防守`,
        elapsed,
        player_id: e.player_id ?? undefined,
      }
    }
    if (e.event_type === 'turnover') {
      const player = e.player_id ? (nameById.get(e.player_id) || '未知') : '未知'
      return {
        event_type: 'turnover' as const,
        team_side: (e.team_side ?? 'A') as 'A' | 'B',
        label: `⚡ ${player} 失误`,
        elapsed,
        player_id: e.player_id ?? undefined,
      }
    }
    return {
      event_type: 'halftime' as const,
      team_side: 'system',
      label: '⏱ 半场',
      elapsed,
    }
  })

  return rebuilt.reverse()
}

function parseEntryState(): LiveEntryState | null {
  const storedState = sessionStorage.getItem('live_match_state')
  let parsed: LiveEntryState | null = null

  if (storedState) {
    try {
      parsed = JSON.parse(storedState) as LiveEntryState
    } catch {
      parsed = null
    }
    sessionStorage.removeItem('live_match_state')
  }

  if (!parsed?.teamAIds) {
    const hs = history.state as LiveEntryState | null
    if (hs?.teamAIds && hs?.teamBIds && hs?.players) parsed = hs
  }

  return parsed
}

export function useLiveDraftBootstrap() {
  async function restoreFromDraft(draftId: number, ctx: DraftRestoreContext): Promise<RestoreResult> {
    try {
      ctx.loadPendingQueue()
      const [draftRes, playersRes] = await Promise.all([
        api.get(`/matches/drafts/${draftId}`),
        api.get('/players', { params: { status: 'active', page_size: 100 } }),
      ])
      const draft = draftRes.data as DraftLike
      const all = playersRes.data as LivePlayer[]

      ctx.teamAIds.value = draft.team_a_ids ?? []
      ctx.teamBIds.value = draft.team_b_ids ?? []
      ctx.teamAPlayers.value = all.filter((p) => ctx.teamAIds.value.includes(p.id))
      ctx.teamBPlayers.value = all.filter((p) => ctx.teamBIds.value.includes(p.id))
      ctx.matchType.value = draft.match_type
      ctx.liveNotes.value = draft.notes ?? ''
      ctx.scoreA.value = draft.team_a_score ?? 0
      ctx.scoreB.value = draft.team_b_score ?? 0
      ctx.elapsedSeconds.value = draft.duration_seconds ?? 0
      ctx.nextSeq.value = (draft.last_event_seq ?? 0) + 1
      ctx.isHalftime.value = !!draft.snapshot?.is_halftime
      ctx.events.value = rebuildEventsFromDraft(draft.events ?? [], all)

      await ctx.fetchPrediction(ctx.teamAIds.value, ctx.teamBIds.value)
      ctx.startTimer()
      await ctx.syncPendingQueue()
      ctx.startLockHeartbeat()

      return { ok: true }
    } catch (e: any) {
      const detail = e?.response?.data?.detail as DraftLockedDetail | undefined
      if (detail?.code === 'DRAFT_LOCKED') {
        return { ok: false, reason: 'locked', lockedBy: detail.locked_by }
      }
      if (detail?.code === 'DRAFT_TAKEOVER_REQUIRED') {
        return { ok: false, reason: 'takeover_required' }
      }
      return { ok: false, reason: 'error' }
    }
  }

  async function initNewDraft(ctx: NewDraftInitContext): Promise<InitResult> {
    const parsed = parseEntryState()

    if (!parsed?.teamAIds || !parsed?.teamBIds || !parsed?.players) {
      return { ok: false, reason: 'missing_entry' }
    }

    ctx.teamAIds.value = parsed.teamAIds
    ctx.teamBIds.value = parsed.teamBIds
    ctx.teamAPlayers.value = parsed.players.filter((p) => parsed.teamAIds!.includes(p.id))
    ctx.teamBPlayers.value = parsed.players.filter((p) => parsed.teamBIds!.includes(p.id))
    if (parsed.matchType) ctx.matchType.value = parsed.matchType as 'internal' | 'external'
    if (parsed.notes) ctx.liveNotes.value = parsed.notes

    try {
      const draftRes = await api.post('/matches/drafts', {
        match_date: new Date().toISOString().slice(0, 10),
        match_type: ctx.matchType.value,
        team_a_ids: ctx.teamAIds.value,
        team_b_ids: ctx.teamBIds.value,
        data_level: 3,
        notes: ctx.liveNotes.value.trim() || '实况录入',
      })
      ctx.draftId.value = draftRes.data.id
      ctx.loadPendingQueue()
      ctx.startLockHeartbeat()
    } catch {
      return { ok: false, reason: 'create_failed' }
    }

    await ctx.fetchPrediction(ctx.teamAIds.value, ctx.teamBIds.value)
    return { ok: true }
  }

  return {
    restoreFromDraft,
    initNewDraft,
  }
}
