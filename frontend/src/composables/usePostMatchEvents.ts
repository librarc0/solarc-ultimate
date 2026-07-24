/**
 * usePostMatchEvents.ts
 * 赛后录入：事件列表的状态管理（US2 事件驱动模式核心 Composable）
 *
 * 职责：
 * - 维护赛后事件列表（进球/防守/失误）
 * - 实时推导比分（scoreA/scoreB）
 * - 将事件聚合为球员统计（aggregatedStats）
 * - 将事件序列化为后端 EventCreate[] 格式（eventCreateList）
 * 底层评分逻辑（detect_data_level/apply_ratings）保持不变，本 Composable 不调用任何评分接口
 */

import { ref, computed } from 'vue'

// ——————————————————————————
// 类型定义（与 data-model.md 对齐）
// ——————————————————————————

/** 三种事件类型共有基础字段 */
interface BasePostMatchEvent {
  /** 前端临时 UUID，用于列表 key 和删除定位 */
  id: string
  type: 'goal' | 'defense' | 'turnover'
  /** 归属队伍（外战时 A=我方 B=对方） */
  team: 'A' | 'B'
  /** 第几分（0-based，动态生成，按添加顺序） */
  point_index: number
}

/** 进球事件 */
export interface PostGoalEvent extends BasePostMatchEvent {
  type: 'goal'
  scorer_id: number
  assist_id: number | null
  /** 是否是 break point（进球方原本是防守方） */
  is_break: boolean
}

/** 防守得盘事件 */
export interface PostDefenseEvent extends BasePostMatchEvent {
  type: 'defense'
  defender_id: number
  interceptor_id: number | null
}

/** 失误事件 */
export interface PostTurnoverEvent extends BasePostMatchEvent {
  type: 'turnover'
  player_id: number
}

export type PostMatchEvent = PostGoalEvent | PostDefenseEvent | PostTurnoverEvent

/** 球员统计汇总（与现有 MatchPlayerEntry 结构兼容） */
export interface StatEntry {
  goals: number
  assists: number
  defense: number
  turnovers: number
}

/** 后端 EventCreate 格式（与 backend/app/schemas/match.py 对齐） */
export interface EventCreate {
  event_type: string
  scorer_id?: number
  assist_id?: number
  is_break?: boolean
  defender_id?: number
  interceptor_id?: number
  turnover_by_id?: number
  team_label?: string
}

// ——————————————————————————
// 将单个内部事件转换为后端 EventCreate 格式
// ——————————————————————————
function toEventCreate(event: PostMatchEvent): EventCreate {
  if (event.type === 'goal') {
    return {
      event_type: 'goal',
      scorer_id: event.scorer_id,
      ...(event.assist_id != null ? { assist_id: event.assist_id } : {}),
      is_break: event.is_break,
      team_label: event.team,
    }
  }
  if (event.type === 'defense') {
    return {
      event_type: 'defense',
      defender_id: event.defender_id,
      ...(event.interceptor_id != null ? { interceptor_id: event.interceptor_id } : {}),
      team_label: event.team,
    }
  }
  // type === 'turnover'
  return {
    event_type: 'turnover',
    turnover_by_id: event.player_id,
    team_label: event.team,
  }
}

// ——————————————————————————
// 主 Composable
// ——————————————————————————

/**
 * 赛后事件列表状态管理
 * @param teamAPlayerIds - 队A球员 id 列表（外战时可为空数组）
 * @param teamBPlayerIds - 队B球员 id 列表（外战时为空数组）
 */
export function usePostMatchEvents(
  teamAPlayerIds: number[] = [],
  teamBPlayerIds: number[] = [],
) {
  /** 所有事件（进球/防守/失误混合，按添加顺序排列） */
  const events = ref<PostMatchEvent[]>([])

  // ——————————————————————————
  // 添加事件
  // ——————————————————————————

  /** 添加进球事件 */
  function addGoal(
    team: 'A' | 'B',
    scorer_id: number,
    assist_id: number | null = null,
    is_break = false,
  ): void {
    const event: PostGoalEvent = {
      id: crypto.randomUUID(),
      type: 'goal',
      team,
      point_index: events.value.length,
      scorer_id,
      assist_id,
      is_break,
    }
    events.value.push(event)
  }

  /** 添加防守得盘事件 */
  function addDefense(
    team: 'A' | 'B',
    defender_id: number,
    interceptor_id: number | null = null,
  ): void {
    const event: PostDefenseEvent = {
      id: crypto.randomUUID(),
      type: 'defense',
      team,
      point_index: events.value.length,
      defender_id,
      interceptor_id,
    }
    events.value.push(event)
  }

  /** 添加失误事件 */
  function addTurnover(team: 'A' | 'B', player_id: number): void {
    const event: PostTurnoverEvent = {
      id: crypto.randomUUID(),
      type: 'turnover',
      team,
      point_index: events.value.length,
      player_id,
    }
    events.value.push(event)
  }

  /** 通过 id 删除事件（对应 ✕ 按钮点击） */
  function removeEvent(id: string): void {
    events.value = events.value.filter((e) => e.id !== id)
  }

  /** 清空所有事件（切换模式时使用） */
  function clearEvents(): void {
    events.value = []
  }

  // ——————————————————————————
  // 派生计算属性
  // ——————————————————————————

  /** 队A得分：统计 type=goal 且 team='A' 的事件数 */
  const scoreA = computed(
    () => events.value.filter((e) => e.type === 'goal' && e.team === 'A').length,
  )

  /** 队B得分：统计 type=goal 且 team='B' 的事件数 */
  const scoreB = computed(
    () => events.value.filter((e) => e.type === 'goal' && e.team === 'B').length,
  )

  /**
   * 聚合统计：将事件列表聚合为球员维度的统计对象
   * key = player_id，value = StatEntry
   * 用于切换到汇总模式时预填数据
   */
  const aggregatedStats = computed<Record<number, StatEntry>>(() => {
    const allIds = [...teamAPlayerIds, ...teamBPlayerIds]
    // 先用空值初始化所有球员
    const stats: Record<number, StatEntry> = {}
    for (const id of allIds) {
      stats[id] = { goals: 0, assists: 0, defense: 0, turnovers: 0 }
    }

    for (const e of events.value) {
      if (e.type === 'goal') {
        if (stats[e.scorer_id]) stats[e.scorer_id]!.goals++
        else if (!allIds.length) {
          // 外战对方无 id，仅计分不做球员统计
        }
        if (e.assist_id != null && stats[e.assist_id]) {
          stats[e.assist_id]!.assists++
        }
      } else if (e.type === 'defense') {
        if (stats[e.defender_id]) stats[e.defender_id]!.defense++
        if (e.interceptor_id != null && stats[e.interceptor_id]) {
          stats[e.interceptor_id]!.defense++
        }
      } else if (e.type === 'turnover') {
        if (stats[e.player_id]) stats[e.player_id]!.turnovers++
      }
    }
    return stats
  })

  /**
   * 后端 EventCreate[] 序列化列表
   * 提交比赛时直接使用此数组
   */
  const eventCreateList = computed<EventCreate[]>(() =>
    events.value.map(toEventCreate),
  )

  return {
    events,
    addGoal,
    addDefense,
    addTurnover,
    removeEvent,
    clearEvents,
    scoreA,
    scoreB,
    aggregatedStats,
    eventCreateList,
  }
}
