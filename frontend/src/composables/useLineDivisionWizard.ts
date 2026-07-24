/**
 * useLineDivisionWizard
 * —— 统一分 line 向导核心逻辑
 *
 * 两种运行模式：
 *   schedule : 关联具体日程事件 (eventId)，每次操作实时调 API 持久化
 *   match    : 比赛录入时独立使用，本地维护状态，confirm 时通过 emit 返回结果
 */
import { ref, computed, watch, type Ref } from 'vue'
import { showToast } from 'vant'
import api from '@/api'
import scheduleApi, {
  type ScheduleLineDivisionRead,
  type ScheduleLineRead,
  type ScheduleLineTemplate,
  type SmartLineAnalyzeResponse,
  type AttendanceSummary,
} from '@/api/schedule'

// ─── 公共类型 ─────────────────────────────────────────────────────────────────

export type WizardMatchType = 'game' | 'internal' | 'training'
export type WizardMode = 'schedule' | 'match'
export type AttendanceStatus = 'yes' | 'leave' | 'sdl' | 'not_submitted'
export type WizardTab = 'attendance' | 'line' | 'analysis' | 'confirm'

// Re-export types from schedule API
export type { ScheduleLineRead }

export interface WizardPlayer {
  id: number
  username: string
  display_name: string | null
  conservative_rating: number
  gender: string | null
  jersey_number: number | null
  is_guest?: boolean
  // 累计比赛数据（来自 PlayerPublic）
  total_matches?: number
  total_goals?: number
  total_assists?: number
  total_plus_minus?: number
}

/** match 模式下的本地 line 结构 */
export interface LocalLine {
  key: string          // 唯一标识 (line_name 在同类型中唯一)
  line_name: string
  line_type: 'o_line' | 'd_line' | 'line'
  round_number: number
  order_index: number
  playerIds: number[]
}

/** 向导确认返回的结果 */
export interface LineDivisionResult {
  matchType: WizardMatchType
  attendingIds: number[]
  // game (外战)
  oLineIds: number[]
  dLine1Ids: number[]
  dLine2Ids: number[]
  // internal (内战)
  teamAIds: number[]
  teamBIds: number[]
  // training (训练) — 多条 line
  trainingLines: Array<{ name: string; playerIds: number[] }>
  // 分析结果（外战时可能有）
  analysisResult: SmartLineAnalyzeResponse | null
  // schedule 模式下的 divisionId
  divisionId?: number
}

/** 智能分组结果（内战） */
export interface AutoGroupResult {
  team_a_ids: number[]
  team_b_ids: number[]
  match_quality: number
  win_prob_a: number
}

// ─── 辅助工具 ─────────────────────────────────────────────────────────────────

export function normalizeAttendance(value?: string | null): AttendanceStatus {
  if (value === 'no') return 'leave'
  return value === 'yes' || value === 'leave' || value === 'sdl' || value === 'not_submitted'
    ? value
    : 'not_submitted'
}

export function getPlayerLabel(p: WizardPlayer): string {
  const jersey = p.jersey_number != null ? `#${p.jersey_number} ` : ''
  const gender = p.gender === 'M' ? '♂' : p.gender === 'F' ? '♀' : ''
  const name = p.display_name || p.username
  return gender ? `${jersey}${name} ${gender}` : `${jersey}${name}`
}

// ─── Composable 主体 ──────────────────────────────────────────────────────────

export interface UseLineDivisionWizardOptions {
  matchType: WizardMatchType
  eventId?: number
  /** 仅用于加载出勤信息，不用于持久化 Line（match 模式下关联了日程时使用） */
  attendanceEventId?: number
  mode: WizardMode
  initialAttendingIds?: number[]
}

export function useLineDivisionWizard(options: UseLineDivisionWizardOptions) {
  const { matchType, eventId, mode } = options
  const attendanceEventId = options.attendanceEventId ?? eventId

  // ── Tab 导航 ──────────────────────────────────────────────────────────────
  const activeTab = ref<WizardTab>('attendance')

  // ── 球员数据 ───────────────────────────────────────────────────────────────
  const allPlayers = ref<WizardPlayer[]>([])
  const loadingPlayers = ref(false)
  const attendingIds = ref<number[]>(options.initialAttendingIds ? [...options.initialAttendingIds] : [])
  const attendanceMap = ref<Record<number, AttendanceStatus>>({})

  async function fetchPlayers() {
    loadingPlayers.value = true
    try {
      const res = await api.get<WizardPlayer[]>('/players', { params: { status: 'active', page_size: 500 } })
      // 保留已添加的外援（is_guest），避免重新加载后被清除
      const guests = allPlayers.value.filter(p => p.is_guest)
      allPlayers.value = [...res.data, ...guests]
    } catch {
      showToast('加载球员列表失败')
    } finally {
      loadingPlayers.value = false
    }
  }

  async function loadAttendanceFromSchedule() {
    if (!attendanceEventId) return
    try {
      const summary: AttendanceSummary = await scheduleApi.getAttendanceSummary(attendanceEventId)
      const nextMap: Record<number, AttendanceStatus> = {}
      summary.yes.forEach(item => { nextMap[item.player_id] = 'yes' })
      summary.sdl.forEach(item => { nextMap[item.player_id] = 'sdl' })
      summary.leave.forEach(item => { nextMap[item.player_id] = 'leave' })
      ;(summary.no ?? []).forEach(item => { nextMap[item.player_id] = 'leave' })
      summary.not_submitted.forEach(item => { nextMap[item.player_id] = 'not_submitted' })
      attendanceMap.value = nextMap
      // 在 schedule 模式下，自动预选 yes/sdl 状态的球员作为出勤人员
      if (mode === 'schedule' && attendingIds.value.length === 0) {
        attendingIds.value = [
          ...summary.yes.map(p => p.player_id),
          ...summary.sdl.map(p => p.player_id),
        ]
      }
    } catch {
      attendanceMap.value = {}
    }
  }

  function toggleAttendance(playerId: number) {
    const idx = attendingIds.value.indexOf(playerId)
    if (idx >= 0) attendingIds.value.splice(idx, 1)
    else attendingIds.value.push(playerId)
  }

  function selectAttendingByStatus(statuses: AttendanceStatus[]) {
    const ids = allPlayers.value
      .filter(p => statuses.includes(attendanceMap.value[p.id] ?? 'not_submitted'))
      .map(p => p.id)
    attendingIds.value = Array.from(new Set([...attendingIds.value, ...ids]))
  }

  function clearAttending() {
    attendingIds.value = []
  }

  // ── 外援（临时 guest 球员）─────────────────────────────────────────────────
  let _nextGuestId = -1

  function addGuest(displayName: string, gender: 'M' | 'F' | '') {
    const regularPlayers = allPlayers.value.filter(p => !p.is_guest)
    const avgRating = regularPlayers.length > 0
      ? Math.round(regularPlayers.reduce((s, p) => s + p.conservative_rating, 0) / regularPlayers.length)
      : 25
    const guest: WizardPlayer = {
      id: _nextGuestId--,
      username: displayName,
      display_name: displayName,
      conservative_rating: avgRating,
      gender: gender || null,
      jersey_number: null,
      is_guest: true,
      total_matches: 0,
      total_goals: 0,
      total_assists: 0,
      total_plus_minus: 0,
    }
    allPlayers.value = [...allPlayers.value, guest]
    attendingIds.value = [...attendingIds.value, guest.id]
  }

  function removeGuest(guestId: number) {
    allPlayers.value = allPlayers.value.filter(p => p.id !== guestId)
    attendingIds.value = attendingIds.value.filter(id => id !== guestId)
    localLines.value.forEach(line => {
      line.playerIds = line.playerIds.filter(id => id !== guestId)
    })
  }

  // ── Schedule 模式：持久化 division ────────────────────────────────────────
  const division = ref<ScheduleLineDivisionRead | null>(null)
  const currentRound = ref(1)
  const activeLineId = ref<number | null>(null)
  const loadingDivision = ref(false)

  const currentLines = computed<ScheduleLineRead[]>(() =>
    (division.value?.lines ?? []).filter(l => l.round_number === currentRound.value)
  )
  const activeLine = computed<ScheduleLineRead | null>(() =>
    currentLines.value.find(l => l.id === activeLineId.value) ?? currentLines.value[0] ?? null
  )
  const totalRounds = computed(() => division.value?.total_rounds ?? 1)

  async function loadDivision() {
    if (!eventId) return
    loadingDivision.value = true
    try {
      division.value = await scheduleApi.getDivision(eventId)
      currentRound.value = 1
      activeLineId.value = division.value?.lines[0]?.id ?? null
    } catch {
      division.value = null
      activeLineId.value = null
    } finally {
      loadingDivision.value = false
    }
  }

  async function initDivision(totalRoundsInput = 1) {
    if (!eventId) return
    loadingDivision.value = true
    try {
      division.value = await scheduleApi.createOrResetDivision(eventId, {
        division_method: 'manual',
        total_rounds: totalRoundsInput,
      })
      currentRound.value = 1
      activeLineId.value = division.value.lines[0]?.id ?? null
      showToast('方案已初始化 ✓')
    } catch (e: any) {
      showToast(e?.response?.data?.detail ?? '初始化失败')
    } finally {
      loadingDivision.value = false
    }
  }

  async function addRound() {
    if (!eventId || !division.value) return
    const next = Math.min(totalRounds.value + 1, 10)
    loadingDivision.value = true
    try {
      division.value = await scheduleApi.updateDivision(eventId, { total_rounds: next })
      currentRound.value = next
    } catch (e: any) {
      showToast(e?.response?.data?.detail ?? '增加轮数失败')
    } finally {
      loadingDivision.value = false
    }
  }

  async function deleteRound() {
    if (!eventId || !division.value) return
    loadingDivision.value = true
    try {
      division.value = await scheduleApi.deleteRound(eventId, currentRound.value)
      currentRound.value = Math.min(currentRound.value, division.value.total_rounds)
    } catch (e: any) {
      showToast(e?.response?.data?.detail ?? '删除轮数失败')
    } finally {
      loadingDivision.value = false
    }
  }

  async function addLine(lineName: string, lineType: 'o_line' | 'd_line' | 'line') {
    if (!eventId || !division.value) return
    loadingDivision.value = true
    try {
      const line = await scheduleApi.createLine(eventId, {
        line_name: lineName,
        line_type: lineType,
        round_number: currentRound.value,
        order_index: currentLines.value.length,
      })
      division.value.lines.push(line)
      activeLineId.value = line.id
    } catch (e: any) {
      showToast(e?.response?.data?.detail ?? '添加失败')
    } finally {
      loadingDivision.value = false
    }
  }

  async function deleteLine(lineId: number) {
    if (!eventId || !division.value) return
    try {
      await scheduleApi.deleteLine(eventId, lineId)
      division.value.lines = division.value.lines.filter(l => l.id !== lineId)
      if (activeLineId.value === lineId) {
        activeLineId.value = currentLines.value[0]?.id ?? null
      }
    } catch (e: any) {
      showToast(e?.response?.data?.detail ?? '删除失败')
    }
  }

  async function togglePlayerInLine(lineId: number, playerId: number) {
    if (!eventId || !division.value) return
    const line = division.value.lines.find(l => l.id === lineId)
    if (!line) return
    const inLine = line.players.some(p => p.player_id === playerId)
    // 检查是否已在同轮其它 line
    if (!inLine) {
      const inOther = currentLines.value.some(l => l.id !== lineId && l.players.some(p => p.player_id === playerId))
      if (inOther) {
        showToast('该队员已在当前轮其他 Line，请先移除')
        return
      }
    }
    loadingDivision.value = true
    try {
      if (inLine) {
        await scheduleApi.removePlayerFromLine(eventId, lineId, playerId)
        line.players = line.players.filter(p => p.player_id !== playerId)
      } else {
        const updated = await scheduleApi.addPlayerToLine(eventId, lineId, playerId)
        line.players = updated.players
      }
    } catch (e: any) {
      showToast(e?.response?.data?.detail ?? '操作失败')
    } finally {
      loadingDivision.value = false
    }
  }

  async function scheduleAutoAssign(method: 'auto_balanced' | 'auto_strong_to_weak', numLines: number) {
    if (!eventId) return
    loadingDivision.value = true
    try {
      division.value = await scheduleApi.autoAssign(eventId, {
        method,
        num_lines: numLines,
        round_number: currentRound.value,
        player_ids: attendingIds.value.length > 0 ? attendingIds.value : undefined,
      })
      activeLineId.value = currentLines.value[0]?.id ?? null
      showToast('自动分配完成 ✓')
    } catch (e: any) {
      showToast(e?.response?.data?.detail ?? '自动分配失败')
    } finally {
      loadingDivision.value = false
    }
  }

  // ── Match 模式：本地 line 状态 ─────────────────────────────────────────────
  const localLines = ref<LocalLine[]>([])
  const localRounds = ref(1) // 内战轮次
  const currentLocalRound = ref(1)
  const dLineCount = ref<1 | 2>(1)
  const maxLineSize = ref(7)

  function rebuildDefaultLocalLines() {
    if (matchType === 'game') {
      localLines.value = [
        { key: 'o_line', line_name: 'O Line', line_type: 'o_line', round_number: 1, order_index: 0, playerIds: [] },
        { key: 'd_line_1', line_name: 'D Line', line_type: 'd_line', round_number: 1, order_index: 1, playerIds: [] },
      ]
    } else if (matchType === 'internal') {
      localLines.value = [
        { key: 'team_a_1', line_name: '队A', line_type: 'line', round_number: 1, order_index: 0, playerIds: [] },
        { key: 'team_b_1', line_name: '队B', line_type: 'line', round_number: 1, order_index: 1, playerIds: [] },
      ]
    } else {
      localLines.value = [
        { key: 'line_1', line_name: 'Line 1', line_type: 'line', round_number: 1, order_index: 0, playerIds: [] },
        { key: 'line_2', line_name: 'Line 2', line_type: 'line', round_number: 1, order_index: 1, playerIds: [] },
      ]
    }
  }

  function getLocalCurrentLines() {
    if (matchType === 'internal') {
      return localLines.value.filter(l => l.round_number === currentLocalRound.value)
    }
    return localLines.value
  }

  function togglePlayerInLocalLine(lineKey: string, playerId: number) {
    const line = localLines.value.find(l => l.key === lineKey)
    if (!line) return
    if (matchType !== 'training') {
      // 同轮不重复
      const roundLines = getLocalCurrentLines()
      const inOther = roundLines.some(l => l.key !== lineKey && l.playerIds.includes(playerId))
      if (inOther) {
        // 从其他 line 移过来
        roundLines.forEach(l => {
          if (l.key !== lineKey) l.playerIds = l.playerIds.filter(id => id !== playerId)
        })
      }
    }
    const idx = line.playerIds.indexOf(playerId)
    if (idx >= 0) line.playerIds.splice(idx, 1)
    else line.playerIds.push(playerId)
  }

  function addLocalLine() {
    const round = matchType === 'internal' ? currentLocalRound.value : 1
    const existingInRound = localLines.value.filter(l => l.round_number === round)
    const index = existingInRound.length
    const key = `line_r${round}_${index + 1}_${Date.now()}`
    const name = matchType === 'game'
      ? (index === 0 ? 'O Line' : `D Line ${index}`)
      : `Line ${index + 1}`
    const type = matchType === 'game'
      ? (index === 0 ? 'o_line' : 'd_line')
      : 'line'
    localLines.value.push({ key, line_name: name, line_type: type, round_number: round, order_index: index, playerIds: [] })
  }

  function removeLocalLine(lineKey: string) {
    localLines.value = localLines.value.filter(l => l.key !== lineKey)
  }

  function addLocalRound() {
    if (matchType !== 'internal') return
    const next = localRounds.value + 1
    if (next > 10) return
    localLines.value.push(
      { key: `team_a_${next}`, line_name: '队A', line_type: 'line', round_number: next, order_index: 0, playerIds: [] },
      { key: `team_b_${next}`, line_name: '队B', line_type: 'line', round_number: next, order_index: 1, playerIds: [] },
    )
    localRounds.value = next
    currentLocalRound.value = next
  }

  // 将 attendingIds 均匀分配到本地 lines
  function localAutoAssign(method: 'auto_balanced' | 'auto_strong_to_weak') {
    const round = matchType === 'internal' ? currentLocalRound.value : 1
    const linesInRound = localLines.value.filter(l => l.round_number === round)
    if (linesInRound.length < 2) {
      showToast('至少需要 2 条 Line 才能自动分配')
      return
    }
    if (attendingIds.value.length === 0) {
      showToast('请先选择出勤球员')
      return
    }
    // 清空当前轮
    linesInRound.forEach(l => { l.playerIds = [] })

    const sorted = [...attendingIds.value].sort((a, b) => {
      const pa = allPlayers.value.find(p => p.id === a)
      const pb = allPlayers.value.find(p => p.id === b)
      return (pb?.conservative_rating ?? 0) - (pa?.conservative_rating ?? 0)
    })

    if (method === 'auto_balanced') {
      // 蛇形分配：012...N N...10
      sorted.forEach((pid, i) => {
        const n = linesInRound.length
        const pos = Math.floor(i / n)
        const inRow = i % n
        const lineIdx = pos % 2 === 0 ? inRow : n - 1 - inRow
        const line = linesInRound[lineIdx % n]
        if (line) line.playerIds.push(pid)
      })
    } else {
      // 循环顺序分配
      sorted.forEach((pid, i) => {
        const line = linesInRound[i % linesInRound.length]
        if (line) line.playerIds.push(pid)
      })
    }
    showToast('自动分配完成 ✓')
  }

  // ── 模板（game / training 有模板；internal 无） ───────────────────────────
  const templates = ref<ScheduleLineTemplate[]>([])
  const loadingTemplates = ref(false)

  const supportsTemplates = matchType === 'game' || matchType === 'training'

  async function loadTemplates() {
    if (!supportsTemplates) { templates.value = []; return }
    loadingTemplates.value = true
    try {
      templates.value = await scheduleApi.listDivisionTemplates(matchType as 'game' | 'training')
    } catch {
      templates.value = []
    } finally {
      loadingTemplates.value = false
    }
  }

  async function saveTemplate(name: string) {
    if (!supportsTemplates || !eventId) return
    try {
      const saved = await scheduleApi.saveDivisionTemplate(eventId, name)
      showToast(`模板「${saved.template_name}」已保存 ✓`)
      await loadTemplates()
    } catch (e: any) {
      showToast(e?.response?.data?.detail ?? '保存模板失败')
    }
  }

  async function applyTemplate(templateId: number) {
    if (!supportsTemplates || !eventId) return
    loadingDivision.value = true
    try {
      division.value = await scheduleApi.applyDivisionTemplate(eventId, templateId)
      activeLineId.value = division.value?.lines[0]?.id ?? null
      showToast('已应用模板 ✓')
    } catch (e: any) {
      showToast(e?.response?.data?.detail ?? '应用模板失败')
    } finally {
      loadingDivision.value = false
    }
  }

  // ── 外战智能分 line 分析 ────────────────────────────────────────────────────
  const analysisResult = ref<SmartLineAnalyzeResponse | null>(null)
  const analysisLoading = ref(false)

  async function runSmartExternalAnalysis(applyToLines = false) {
    const ids = attendingIds.value.length > 0 ? attendingIds.value : allPlayers.value.map(p => p.id)
    if (ids.length < 7) {
      showToast('外战分析至少需要 7 名出勤球员')
      return
    }
    analysisLoading.value = true
    try {
      const res = await scheduleApi.analyzeSmartExternalLines({
        player_ids: ids,
        schedule_event_id: eventId,
        apply_to_match: applyToLines && !!eventId,
        max_line_size: maxLineSize.value,
        d_line_count: dLineCount.value,
      })
      analysisResult.value = res
      if (applyToLines && mode === 'match') {
        // 将分析结果应用到本地 lines
        localLines.value = []
        if (res.o_line) {
          localLines.value.push({
            key: 'o_line',
            line_name: res.o_line.line_name,
            line_type: 'o_line',
            round_number: 1,
            order_index: 0,
            playerIds: res.o_line.player_ids,
          })
        }
        res.d_lines.forEach((dl, i) => {
          localLines.value.push({
            key: `d_line_${i + 1}`,
            line_name: dl.line_name,
            line_type: 'd_line',
            round_number: 1,
            order_index: i + 1,
            playerIds: dl.player_ids,
          })
        })
        showToast('智能分配已应用到分 line 配置 ✓')
      } else if (applyToLines && mode === 'schedule') {
        // schedule 模式：API 已经写回，刷新 division
        await loadDivision()
        showToast('智能分配已同步回写到日程分 line ✓')
      } else {
        showToast('分析完成，请前往"分析报告"查看详情')
      }
    } catch (e: any) {
      showToast(e?.response?.data?.detail ?? '智能分析失败')
    } finally {
      analysisLoading.value = false
    }
  }

  // ── 内战智能分组 ─────────────────────────────────────────────────────────
  const autoGroupResult = ref<AutoGroupResult | null>(null)
  const autoGroupLoading = ref(false)

  async function runSmartGroup() {
    const ids = attendingIds.value.length > 0 ? attendingIds.value : allPlayers.value.map(p => p.id)
    if (ids.length < 2) {
      showToast('至少需要 2 名球员进行智能分组')
      return
    }
    autoGroupLoading.value = true
    try {
      const res = await api.post<AutoGroupResult>('/matches/auto_group', { player_ids: ids })
      autoGroupResult.value = res.data
      // 应用到本地 lines（第 1 轮）
      const round = matchType === 'internal' ? currentLocalRound.value : 1
      const teamA = localLines.value.find(l => l.round_number === round && l.order_index === 0)
      const teamB = localLines.value.find(l => l.round_number === round && l.order_index === 1)
      if (teamA && teamB) {
        teamA.playerIds = res.data.team_a_ids
        teamB.playerIds = res.data.team_b_ids
        showToast(`均衡度 ${(res.data.match_quality * 100).toFixed(1)}%，分组已应用 ✓`)
      }
    } catch {
      showToast('智能分组失败，请重试')
    } finally {
      autoGroupLoading.value = false
    }
  }

  // ── 基于当前手动分line生成本地分析报告 ──────────────────────────────────────
  async function buildLocalGameAnalysis() {
    const currentLines = localLines.value.filter(l => l.round_number === 1)
    if (!currentLines.some(l => l.playerIds.length > 0)) {
      showToast('请先在「分Line」Tab 中分配球员')
      return
    }
    analysisLoading.value = true
    try {
      const res = await scheduleApi.analyzeAssignedLines({
        lines: currentLines.map(l => ({
          line_name: l.line_name,
          line_type: l.line_type,
          player_ids: l.playerIds,
        })),
      })
      analysisResult.value = res
      showToast('已根据当前分line生成分析报告 ✓')
    } catch (e: any) {
      showToast(e?.response?.data?.detail ?? '分析生成失败，请重试')
    } finally {
      analysisLoading.value = false
    }
  }

  // ── 最终结果构建 ─────────────────────────────────────────────────────────
  function buildResult(): LineDivisionResult {
    const lines = mode === 'schedule'
      ? (division.value?.lines ?? []).map(l => ({ key: `s_${l.id}`, ...l, playerIds: l.players.map(p => p.player_id) }))
      : localLines.value

    let oLineIds: number[] = []
    let dLine1Ids: number[] = []
    let dLine2Ids: number[] = []
    let teamAIds: number[] = []
    let teamBIds: number[] = []
    const trainingLines: Array<{ name: string; playerIds: number[] }> = []
    const rounds: Array<{ round: number; teamAIds: number[]; teamBIds: number[] }> = []

    if (matchType === 'game') {
      const oLine = lines.find(l => l.line_type === 'o_line')
      const dLines = lines.filter(l => l.line_type === 'd_line')
      oLineIds = oLine?.playerIds ?? []
      dLine1Ids = dLines[0]?.playerIds ?? []
      dLine2Ids = dLines[1]?.playerIds ?? []
    } else if (matchType === 'internal') {
      const maxRound = mode === 'schedule' ? totalRounds.value : localRounds.value
      for (let r = 1; r <= maxRound; r++) {
        const roundLines = lines.filter(l => l.round_number === r)
        const a = roundLines.find(l => l.order_index === 0)
        const b = roundLines.find(l => l.order_index === 1)
        rounds.push({ round: r, teamAIds: a?.playerIds ?? [], teamBIds: b?.playerIds ?? [] })
      }
      // 第 1 轮作为默认
      teamAIds = rounds[0]?.teamAIds ?? []
      teamBIds = rounds[0]?.teamBIds ?? []
    } else {
      // training
      lines.forEach(l => trainingLines.push({ name: l.line_name, playerIds: l.playerIds }))
    }

    return {
      matchType,
      attendingIds: attendingIds.value,
      oLineIds,
      dLine1Ids,
      dLine2Ids,
      teamAIds,
      teamBIds,
      trainingLines,
      analysisResult: analysisResult.value,
      divisionId: mode === 'schedule' ? division.value?.id : undefined,
    }
  }

  // ── 初始化 ────────────────────────────────────────────────────────────────
  // 是否是首次初始化
  let _initialized = false

  async function init() {
    const isFirstInit = !_initialized
    _initialized = true

    await fetchPlayers()
    if (mode === 'schedule' && eventId) {
      await Promise.all([loadAttendanceFromSchedule(), loadDivision(), loadTemplates()])
    } else {
      // match 模式：只有首次初始时（或 localLines 内容全为空）才重建默认 localLines
      const hasExistingContent = localLines.value.some(l => l.playerIds.length > 0)
      if (isFirstInit || !hasExistingContent) {
        // 如果有关联日程，尝试从日程已保存的 division 恢复分line
        let loadedFromSchedule = false
        if (attendanceEventId) {
          await loadAttendanceFromSchedule()
          try {
            const divForMatch = await scheduleApi.getDivisionForMatch(attendanceEventId)
            // 解析 rounds，恢复 localLines
            const restoredLines: LocalLine[] = []
            let hasAnyPlayers = false
            Object.entries(divForMatch.rounds).forEach(([roundStr, lines]) => {
              const round = parseInt(roundStr)
              lines.forEach((l, idx) => {
                if (l.player_ids.length > 0) hasAnyPlayers = true
                restoredLines.push({
                  key: `${l.line_type}_${round}_${idx}`,
                  line_name: l.line_name,
                  line_type: l.line_type as 'o_line' | 'd_line' | 'line',
                  round_number: round,
                  order_index: idx,
                  playerIds: l.player_ids,
                })
              })
            })
            if (hasAnyPlayers && restoredLines.length > 0) {
              localLines.value = restoredLines
              // 同时把所有已分配队员设为出勤（如 attendingIds 为空）
              if (attendingIds.value.length === 0) {
                const allAssigned = Array.from(new Set(restoredLines.flatMap(l => l.playerIds)))
                attendingIds.value = allAssigned
              }
              loadedFromSchedule = true
            }
          } catch {
            // 日程没有保存分line，正常情况，忽略错误
          }
        }
        if (!loadedFromSchedule) {
          rebuildDefaultLocalLines()
          // match 模式无关联日程时没有 attendanceEventId，不需再次 load
        }
      } else {
        // 已有内容，仅刷新出勤标签（不清空 localLines）
        if (attendanceEventId) {
          await loadAttendanceFromSchedule()
        }
      }
    }
  }

  // 当出勤人员变化时，同步 dLineCount 的最小值
  watch(attendingIds, (ids) => {
    if (matchType === 'game' && ids.length < 1 + dLineCount.value) {
      dLineCount.value = 1
    }
  }, { deep: true })

  // 当切换 D line 条数时，重建默认 local lines
  watch(dLineCount, () => {
    if (mode === 'match' && matchType === 'game') {
      const oLine = localLines.value.find(l => l.line_type === 'o_line')
      const existingD = localLines.value.filter(l => l.line_type === 'd_line')
      const newDLines: LocalLine[] = Array.from({ length: dLineCount.value }, (_, i) => ({
        key: `d_line_${i + 1}`,
        line_name: dLineCount.value === 1 ? 'D Line' : `D Line ${i + 1}`,
        line_type: 'd_line' as const,
        round_number: 1,
        order_index: i + 1,
        playerIds: existingD[i]?.playerIds ?? [],
      }))
      localLines.value = [
        oLine ?? { key: 'o_line', line_name: 'O Line', line_type: 'o_line', round_number: 1, order_index: 0, playerIds: [] },
        ...newDLines,
      ]
    }
  })

  return {
    // tab
    activeTab,
    // players
    allPlayers,
    loadingPlayers,
    attendingIds,
    attendanceMap,
    fetchPlayers,
    loadAttendanceFromSchedule,
    toggleAttendance,
    selectAttendingByStatus,
    clearAttending,
    addGuest,
    removeGuest,
    // schedule mode
    division,
    currentRound,
    activeLineId,
    loadingDivision,
    currentLines,
    activeLine,
    totalRounds,
    loadDivision,
    initDivision,
    addRound,
    deleteRound,
    addLine,
    deleteLine,
    togglePlayerInLine,
    scheduleAutoAssign,
    // match mode (local)
    localLines,
    localRounds,
    currentLocalRound,
    dLineCount,
    maxLineSize,
    getLocalCurrentLines,
    togglePlayerInLocalLine,
    addLocalLine,
    removeLocalLine,
    addLocalRound,
    localAutoAssign,
    // templates
    templates,
    loadingTemplates,
    supportsTemplates,
    loadTemplates,
    saveTemplate,
    applyTemplate,
    // external analysis
    analysisResult,
    analysisLoading,
    runSmartExternalAnalysis,
    buildLocalGameAnalysis,
    // internal smart group
    autoGroupResult,
    autoGroupLoading,
    runSmartGroup,
    // result
    buildResult,
    // init
    init,
  }
}
