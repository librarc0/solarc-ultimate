import { ref } from 'vue'

export type TeamSide = 'A' | 'B'
export type EventType = 'goal' | 'defense' | 'turnover' | 'halftime' | 'system'

export interface PlayerLite {
  id: number
  username: string
  display_name: string | null
}

export interface LiveEvent {
  event_type: EventType
  team_side: TeamSide | 'system'
  label: string
  elapsed: string
  player_id?: number
  assist_player_id?: number | null
  is_break?: boolean
  score_a?: number
  score_b?: number
}

export function useLiveEvents() {
  const events = ref<LiveEvent[]>([])

  function addTurnover(args: { side: TeamSide; player: PlayerLite; elapsed: string }) {
    events.value.unshift({
      event_type: 'turnover',
      team_side: args.side,
      label: `⚡ ${args.player.display_name || args.player.username} 失误`,
      elapsed: args.elapsed,
      player_id: args.player.id,
    })
  }

  function addGoal(args: {
    side: TeamSide
    scorer: PlayerLite | null
    assist: PlayerLite | null
    isBreak: boolean
    elapsed: string
    scoreA: number
    scoreB: number
  }) {
    let label = `${args.scorer?.display_name || args.scorer?.username || '未知'} 得分`
    if (args.assist) label += ` (助攻: ${args.assist.display_name || args.assist.username})`
    events.value.unshift({
      event_type: 'goal',
      team_side: args.side,
      label,
      elapsed: args.elapsed,
      player_id: args.scorer?.id,
      assist_player_id: args.assist?.id ?? null,
      is_break: args.isBreak,
      score_a: args.scoreA,
      score_b: args.scoreB,
    })
  }

  function addExternalOpponentGoal(args: { elapsed: string }) {
    events.value.unshift({
      event_type: 'goal',
      team_side: 'B',
      label: '对方 得分',
      elapsed: args.elapsed,
      assist_player_id: null,
      is_break: false,
    })
  }

  function addDefense(args: {
    side: TeamSide
    defender: PlayerLite | null
    interceptor: PlayerLite | null
    elapsed: string
  }) {
    let label = `🛡 ${args.defender?.display_name || args.defender?.username || '未知'} 防守`
    if (args.interceptor) label += ` (拦截: ${args.interceptor.display_name || args.interceptor.username})`
    events.value.unshift({
      event_type: 'defense',
      team_side: args.side,
      label,
      elapsed: args.elapsed,
      player_id: args.defender?.id,
      assist_player_id: args.interceptor?.id ?? null,
    })
  }

  function addHalftime(args: { elapsed: string; scoreA: number; scoreB: number }) {
    events.value.unshift({
      event_type: 'halftime',
      team_side: 'system',
      label: `⏱ 半场（${args.scoreA} — ${args.scoreB}）`,
      elapsed: args.elapsed,
    })
  }

  return {
    events,
    addTurnover,
    addGoal,
    addExternalOpponentGoal,
    addDefense,
    addHalftime,
  }
}

