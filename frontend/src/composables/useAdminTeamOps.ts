import { computed, ref } from 'vue'
import { showConfirmDialog, showToast } from 'vant'

import api from '@/api'

interface TeamItem {
  id: number
  name: string
  member_count: number
}

interface SettingsData {
  team_id: number
  team?: { id: number; name: string; member_count: number } | null
  alpha: number
  beta: number
  gamma: number
  defense_weight: number
  composite_ts_weight: number
  composite_perf_weight: number
  composite_attendance_weight: number
  perf_confidence_decay: number
  turnover_penalty: number
  turnover_sigma_factor: number
  break_bonus_per_goal: number
  winner_floor_factor: number
  external_impact_multiplier: number
  external_opp_mu_min: number
  external_opp_mu_max: number
  external_opp_sigma: number
  openskill_mu: number
  openskill_sigma: number
  openskill_beta: number
  openskill_tau: number
  openskill_kappa: number
  openskill_margin: number
  openskill_limit_sigma: boolean
  openskill_balance: boolean
  chemistry_win_weight: number
  chemistry_combo_weight: number
  weight_cap: number
  chemistry_decay_constant: number
  sigma_bonus_factor: number
  universal_point_bonus: number
  block_mu_bonus: number
  consecutive_turnover_threshold: number
  consecutive_turnover_multiplier: number
}

type NumericRangeRule = {
  min: number
  max: number
  integer?: boolean
}

const SETTINGS_RANGE_RULES: Record<string, NumericRangeRule> = {
  alpha: { min: 0.0, max: 2.0 },
  beta: { min: 0.0, max: 2.0 },
  gamma: { min: 0.0, max: 2.0 },
  defense_weight: { min: 0.0, max: 2.0 },
  composite_ts_weight: { min: 0.0, max: 1.0 },
  composite_perf_weight: { min: 0.0, max: 1.0 },
  composite_attendance_weight: { min: 0.0, max: 1.0 },
  perf_confidence_decay: { min: 1.0, max: 50.0 },
  turnover_penalty: { min: 0.0, max: 2.0 },
  turnover_sigma_factor: { min: 0.0, max: 2.0 },
  break_bonus_per_goal: { min: 0.0, max: 2.0 },
  winner_floor_factor: { min: 0.0, max: 1.0 },
  external_impact_multiplier: { min: 0.0, max: 3.0 },
  external_opp_mu_min: { min: 1.0, max: 50.0 },
  external_opp_mu_max: { min: 1.0, max: 100.0 },
  external_opp_sigma: { min: 1.0, max: 20.0 },
  openskill_mu: { min: 1.0, max: 60.0 },
  openskill_sigma: { min: 0.5, max: 20.0 },
  openskill_beta: { min: 0.1, max: 20.0 },
  openskill_tau: { min: 0.0, max: 5.0 },
  openskill_kappa: { min: 0.0, max: 0.1 },
  openskill_margin: { min: 0.0, max: 20.0 },
  chemistry_win_weight: { min: 0.0, max: 1.0 },
  chemistry_combo_weight: { min: 0.0, max: 1.0 },
  chemistry_decay_constant: { min: 1.0, max: 50.0 },
  sigma_bonus_factor: { min: 0.0, max: 1.0 },
  weight_cap: { min: 1.0, max: 5.0 },
  universal_point_bonus: { min: 0.0, max: 5.0 },
  block_mu_bonus: { min: 0.0, max: 2.0 },
  consecutive_turnover_threshold: { min: 1, max: 20, integer: true },
  consecutive_turnover_multiplier: { min: 1.0, max: 5.0 },
}

function getRangeText(field: string): string {
  const rule = SETTINGS_RANGE_RULES[field]
  if (!rule) return ''
  return `${rule.min}~${rule.max}${rule.integer ? '（整数）' : ''}`
}

function normalizeErrorMessage(err: any): string {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0]
    const field = Array.isArray(first?.loc) ? String(first.loc[first.loc.length - 1] ?? '') : ''
    const msg = String(first?.msg ?? '参数校验失败')
    const range = field ? getRangeText(field) : ''
    if (field && range) return `参数 ${field} 校验失败：${msg}（允许范围 ${range}）`
    if (field) return `参数 ${field} 校验失败：${msg}`
    return msg
  }
  return '保存失败'
}

function validateSettingsPayload(payload: Record<string, number | boolean>): string | null {
  for (const [field, rule] of Object.entries(SETTINGS_RANGE_RULES)) {
    const value = payload[field]
    if (typeof value !== 'number' || Number.isNaN(value)) {
      return `参数 ${field} 必须是数字（允许范围 ${getRangeText(field)}）`
    }
    if (rule.integer && !Number.isInteger(value)) {
      return `参数 ${field} 必须是整数（允许范围 ${getRangeText(field)}）`
    }
    if (value < rule.min || value > rule.max) {
      return `参数 ${field} 超出范围：当前 ${value}，允许 ${getRangeText(field)}`
    }
  }

  if (typeof payload.external_opp_mu_min === 'number' && typeof payload.external_opp_mu_max === 'number') {
    if (payload.external_opp_mu_min > payload.external_opp_mu_max) {
      return '参数 external_opp_mu_min 不能大于 external_opp_mu_max'
    }
  }

  return null
}

function toBool(v: string): boolean {
  return String(v).trim().toLowerCase() === 'true'
}

export function useAdminTeamOps() {
  const pendingTeams = ref<
    Array<{
      id: number
      name: string
      created_at: string
      owner_username: string
      owner_display_name: string | null
    }>
  >([])
  const loadingTeams = ref(false)
  const finishedTeams = ref(false)
  const refreshingTeams = ref(false)

  const allTeams = ref<TeamItem[]>([])
  const loadingAllTeams = ref(false)
  const settingsTeamObject = ref<{ id: number; name: string; member_count: number } | null>(null)
  const showTeamSettingsPopup = ref(false)
  const editingTeam = ref<TeamItem | null>(null)
  const loadingTeamSettings = ref(false)
  const savingTeamSettings = ref(false)
  const resettingTeamSettings = ref(false)
  const reratingTeam = ref(false)
  const rerateProgress = ref(0)
  const rerateMessage = ref('')
  const broadcastScope = ref<'all' | 'targeted'>('all')
  const broadcastTeamIds = ref<number[]>([])
  const broadcastContent = ref('')
  const publishingBroadcast = ref(false)
  const editSettingsForm = ref({
    alpha: '',
    beta: '',
    gamma: '',
    defense_weight: '',
    composite_ts_weight: '',
    composite_perf_weight: '',
    composite_attendance_weight: '',
    perf_confidence_decay: '',
    turnover_penalty: '',
    turnover_sigma_factor: '',
    break_bonus_per_goal: '',
    winner_floor_factor: '',
    sigma_bonus_factor: '',
    universal_point_bonus: '',
    block_mu_bonus: '',
    consecutive_turnover_threshold: '',
    consecutive_turnover_multiplier: '',
    external_impact_multiplier: '',
    external_opp_mu_min: '',
    external_opp_mu_max: '',
    external_opp_sigma: '',
    openskill_mu: '',
    openskill_sigma: '',
    openskill_beta: '',
    openskill_tau: '',
    openskill_kappa: '',
    openskill_margin: '',
    openskill_limit_sigma: 'false',
    openskill_balance: 'false',
    chemistry_win_weight: '',
    chemistry_combo_weight: '',
    weight_cap: '',
    chemistry_decay_constant: '',
  })

  const invalidSettingMessages = computed(() => {
    const form = editSettingsForm.value
    const messages: string[] = []

    for (const [field, rule] of Object.entries(SETTINGS_RANGE_RULES)) {
      const raw = (form as Record<string, string>)[field]
      const value = Number(raw)
      if (!Number.isFinite(value)) {
        messages.push(`${field} 不是合法数字（允许 ${getRangeText(field)}）`)
        continue
      }
      if (rule.integer && !Number.isInteger(value)) {
        messages.push(`${field} 必须是整数（允许 ${getRangeText(field)}）`)
        continue
      }
      if (value < rule.min || value > rule.max) {
        messages.push(`${field}=${value} 超出范围（允许 ${getRangeText(field)}）`)
      }
    }

    const muMin = Number(form.external_opp_mu_min)
    const muMax = Number(form.external_opp_mu_max)
    if (Number.isFinite(muMin) && Number.isFinite(muMax) && muMin > muMax) {
      messages.push('external_opp_mu_min 不能大于 external_opp_mu_max')
    }

    return messages
  })

  async function loadPendingTeams(reset = false) {
    if (reset) {
      finishedTeams.value = false
      pendingTeams.value = []
    }
    try {
      const res = await api.get('/team/pending-teams')
      pendingTeams.value = res.data
      finishedTeams.value = true
    } finally {
      loadingTeams.value = false
      refreshingTeams.value = false
    }
  }

  async function approveTeam(id: number) {
    try {
      await api.post(`/team/${id}/approve`)
      showToast('队伍已批准')
      await loadPendingTeams(true)
      await loadAllTeams()
    } catch (e: any) {
      showToast(e?.response?.data?.detail ?? '操作失败')
    }
  }

  async function rejectTeam(id: number) {
    try {
      await api.post(`/team/${id}/reject`)
      showToast('已拒绝该队伍申请')
      await loadPendingTeams(true)
    } catch (e: any) {
      showToast(e?.response?.data?.detail ?? '操作失败')
    }
  }

  async function loadAllTeams() {
    loadingAllTeams.value = true
    try {
      const res = await api.get('/team/available')
      allTeams.value = res.data
    } finally {
      loadingAllTeams.value = false
    }
  }

  async function publishBroadcastNotice() {
    const content = broadcastContent.value.trim()
    if (!content) {
      showToast('请填写公告内容')
      return
    }
    if (broadcastScope.value === 'targeted' && broadcastTeamIds.value.length === 0) {
      showToast('请选择至少一支队伍')
      return
    }

    publishingBroadcast.value = true
    try {
      const res = await api.post('/team/superadmin/broadcast', {
        content,
        team_ids: broadcastScope.value === 'all' ? [] : broadcastTeamIds.value,
      })
      const count = Number(res.data?.team_count ?? 0)
      showToast(`公告已发布（${count} 支队伍）`)
      broadcastContent.value = ''
      broadcastTeamIds.value = []
    } catch (err: any) {
      showToast(err?.response?.data?.detail ?? '发布失败')
    } finally {
      publishingBroadcast.value = false
    }
  }

  async function openTeamSettings(team: TeamItem) {
    editingTeam.value = team
    settingsTeamObject.value = null
    showTeamSettingsPopup.value = true
    loadingTeamSettings.value = true
    try {
      const res = await api.get('/team/settings', { params: { team_id: team.id } })
      const d: SettingsData = res.data
      settingsTeamObject.value = d.team ?? { id: d.team_id, name: team.name, member_count: team.member_count }
      editSettingsForm.value = {
        alpha: String(d.alpha),
        beta: String(d.beta),
        gamma: String(d.gamma),
        defense_weight: String(d.defense_weight ?? '0.1'),
        composite_ts_weight: String(d.composite_ts_weight),
        composite_perf_weight: String(d.composite_perf_weight),
        composite_attendance_weight: String(d.composite_attendance_weight ?? '0.0'),
        perf_confidence_decay: String(d.perf_confidence_decay ?? '8.0'),
        turnover_penalty: String(d.turnover_penalty ?? '0.2'),
        turnover_sigma_factor: String(d.turnover_sigma_factor ?? '0.3'),
        break_bonus_per_goal: String(d.break_bonus_per_goal ?? '0.1'),
        winner_floor_factor: String(d.winner_floor_factor ?? '0.1'),
        external_impact_multiplier: String(d.external_impact_multiplier ?? '1.0'),
        external_opp_mu_min: String(d.external_opp_mu_min ?? '15.0'),
        external_opp_mu_max: String(d.external_opp_mu_max ?? '50.0'),
        external_opp_sigma: String(d.external_opp_sigma ?? '6.0'),
        openskill_mu: String(d.openskill_mu ?? '25.0'),
        openskill_sigma: String(d.openskill_sigma ?? '8.333'),
        openskill_beta: String(d.openskill_beta ?? '4.167'),
        openskill_tau: String(d.openskill_tau ?? '0.083333'),
        openskill_kappa: String(d.openskill_kappa ?? '0.0001'),
        openskill_margin: String(d.openskill_margin ?? '0.0'),
        openskill_limit_sigma: String(Boolean(d.openskill_limit_sigma)),
        openskill_balance: String(Boolean(d.openskill_balance)),
        chemistry_win_weight: String(d.chemistry_win_weight ?? '0.7'),
        chemistry_combo_weight: String(d.chemistry_combo_weight ?? '0.3'),
        weight_cap: String(d.weight_cap ?? '2.0'),
        chemistry_decay_constant: String(d.chemistry_decay_constant ?? '8.0'),
        sigma_bonus_factor: String(d.sigma_bonus_factor ?? '0.15'),
        universal_point_bonus: String(d.universal_point_bonus ?? '0.5'),
        block_mu_bonus: String(d.block_mu_bonus ?? '0.05'),
        consecutive_turnover_threshold: String(d.consecutive_turnover_threshold ?? '3'),
        consecutive_turnover_multiplier: String(d.consecutive_turnover_multiplier ?? '1.5'),
      }
    } catch {
      showToast('加载系数失败')
      showTeamSettingsPopup.value = false
    } finally {
      loadingTeamSettings.value = false
    }
  }

  async function saveTeamSettings() {
    if (!editingTeam.value) return
    await persistTeamSettings({ closePopup: true, showSuccessToast: true })
  }

  function buildSettingsPayload() {
    return {
      alpha: Number(editSettingsForm.value.alpha),
      beta: Number(editSettingsForm.value.beta),
      gamma: Number(editSettingsForm.value.gamma),
      defense_weight: Number(editSettingsForm.value.defense_weight),
      composite_ts_weight: Number(editSettingsForm.value.composite_ts_weight),
      composite_perf_weight: Number(editSettingsForm.value.composite_perf_weight),
      composite_attendance_weight: Number(editSettingsForm.value.composite_attendance_weight),
      perf_confidence_decay: Number(editSettingsForm.value.perf_confidence_decay),
      turnover_penalty: Number(editSettingsForm.value.turnover_penalty),
      turnover_sigma_factor: Number(editSettingsForm.value.turnover_sigma_factor),
      break_bonus_per_goal: Number(editSettingsForm.value.break_bonus_per_goal),
      winner_floor_factor: Number(editSettingsForm.value.winner_floor_factor),
      external_impact_multiplier: Number(editSettingsForm.value.external_impact_multiplier),
      external_opp_mu_min: Number(editSettingsForm.value.external_opp_mu_min),
      external_opp_mu_max: Number(editSettingsForm.value.external_opp_mu_max),
      external_opp_sigma: Number(editSettingsForm.value.external_opp_sigma),
      openskill_mu: Number(editSettingsForm.value.openskill_mu),
      openskill_sigma: Number(editSettingsForm.value.openskill_sigma),
      openskill_beta: Number(editSettingsForm.value.openskill_beta),
      openskill_tau: Number(editSettingsForm.value.openskill_tau),
      openskill_kappa: Number(editSettingsForm.value.openskill_kappa),
      openskill_margin: Number(editSettingsForm.value.openskill_margin),
      openskill_limit_sigma: toBool(editSettingsForm.value.openskill_limit_sigma),
      openskill_balance: toBool(editSettingsForm.value.openskill_balance),
      chemistry_win_weight: Number(editSettingsForm.value.chemistry_win_weight),
      chemistry_combo_weight: Number(editSettingsForm.value.chemistry_combo_weight),
      weight_cap: Number(editSettingsForm.value.weight_cap),
      chemistry_decay_constant: Number(editSettingsForm.value.chemistry_decay_constant),
      sigma_bonus_factor: Number(editSettingsForm.value.sigma_bonus_factor),
      universal_point_bonus: Number(editSettingsForm.value.universal_point_bonus),
      block_mu_bonus: Number(editSettingsForm.value.block_mu_bonus),
      consecutive_turnover_threshold: Number(editSettingsForm.value.consecutive_turnover_threshold),
      consecutive_turnover_multiplier: Number(editSettingsForm.value.consecutive_turnover_multiplier),
    }
  }

  async function persistTeamSettings(options?: { closePopup?: boolean; showSuccessToast?: boolean }): Promise<boolean> {
    if (!editingTeam.value) return false
    const payload = buildSettingsPayload()
    const validationError = validateSettingsPayload(payload)
    if (validationError) {
      showToast(validationError)
      return false
    }

    savingTeamSettings.value = true
    try {
      await api.put('/team/settings', payload, { params: { team_id: editingTeam.value.id } })
      if (options?.showSuccessToast) showToast('系数已保存')
      if (options?.closePopup) showTeamSettingsPopup.value = false
      return true
    } catch (err: any) {
      showToast(normalizeErrorMessage(err))
      return false
    } finally {
      savingTeamSettings.value = false
    }
  }

  async function resetTeamSettings() {
    if (!editingTeam.value) return
    try {
      await showConfirmDialog({
        title: '确认重置系数？',
        message: '将该队伍的所有算法系数恢复为系统默认值，不影响历史比赛数据。',
        confirmButtonText: '确认重置',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }

    resettingTeamSettings.value = true
    try {
      const res = await api.post('/team/settings/reset', null, { params: { team_id: editingTeam.value.id } })
      const d = res.data
      editSettingsForm.value = {
        alpha: String(d.alpha),
        beta: String(d.beta),
        gamma: String(d.gamma),
        defense_weight: String(d.defense_weight),
        composite_ts_weight: String(d.composite_ts_weight),
        composite_perf_weight: String(d.composite_perf_weight),
        composite_attendance_weight: String(d.composite_attendance_weight ?? '0.0'),
        perf_confidence_decay: String(d.perf_confidence_decay ?? '8.0'),
        turnover_penalty: String(d.turnover_penalty),
        turnover_sigma_factor: String(d.turnover_sigma_factor),
        break_bonus_per_goal: String(d.break_bonus_per_goal),
        winner_floor_factor: String(d.winner_floor_factor),
        external_impact_multiplier: String(d.external_impact_multiplier),
        external_opp_mu_min: String(d.external_opp_mu_min),
        external_opp_mu_max: String(d.external_opp_mu_max),
        external_opp_sigma: String(d.external_opp_sigma),
        openskill_mu: String(d.openskill_mu),
        openskill_sigma: String(d.openskill_sigma),
        openskill_beta: String(d.openskill_beta),
        openskill_tau: String(d.openskill_tau),
        openskill_kappa: String(d.openskill_kappa),
        openskill_margin: String(d.openskill_margin),
        openskill_limit_sigma: String(Boolean(d.openskill_limit_sigma)),
        openskill_balance: String(Boolean(d.openskill_balance)),
        chemistry_win_weight: String(d.chemistry_win_weight),
        chemistry_combo_weight: String(d.chemistry_combo_weight),
        weight_cap: String(d.weight_cap ?? '2.0'),
        chemistry_decay_constant: String(d.chemistry_decay_constant ?? '8.0'),
        sigma_bonus_factor: String(d.sigma_bonus_factor ?? '0.15'),
        universal_point_bonus: String(d.universal_point_bonus ?? '0.5'),
        block_mu_bonus: String(d.block_mu_bonus ?? '0.05'),
        consecutive_turnover_threshold: String(d.consecutive_turnover_threshold ?? '3'),
        consecutive_turnover_multiplier: String(d.consecutive_turnover_multiplier ?? '1.5'),
      }
      showToast('已重置为默认系数')
    } catch (err: any) {
      showToast(err?.response?.data?.detail ?? '重置失败')
    } finally {
      resettingTeamSettings.value = false
    }
  }

  async function rerateEditingTeam() {
    if (!editingTeam.value) return
    try {
      await showConfirmDialog({
        title: '确认重算历史？',
        message: '这会将该队所有球员的评分与累计统计重置为初始值，并按当前系数重放所有已审批比赛。此操作不可撤销，且可能需要几十秒。',
        confirmButtonText: '开始重算',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }

    const saved = await persistTeamSettings({ closePopup: false, showSuccessToast: false })
    if (!saved) return

    reratingTeam.value = true
    rerateProgress.value = 0
    rerateMessage.value = '连接中…'

    const baseURL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'
    const token = localStorage.getItem('access_token')
    const url = `${baseURL}/team/${editingTeam.value.id}/rerate-stream`

    try {
      const resp = await fetch(url, {
        headers: { Authorization: token ? `Bearer ${token}` : '' },
      })
      if (!resp.ok || !resp.body) {
        throw new Error(`HTTP ${resp.status}`)
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          try {
            const evt = JSON.parse(line.slice(5).trim())
            rerateProgress.value = evt.progress ?? rerateProgress.value
            rerateMessage.value = evt.message ?? rerateMessage.value
            if (evt.type === 'done') {
              showToast(`重算完成：重放 ${evt.matches_replayed} 场`)
              showTeamSettingsPopup.value = false
            } else if (evt.type === 'error') {
              showToast(evt.message ?? '重算失败')
            }
          } catch {
            // ignore malformed SSE lines
          }
        }
      }
    } catch (err: any) {
      showToast(err?.message ?? '重算失败，请检查后端连接')
    } finally {
      reratingTeam.value = false
      rerateProgress.value = 0
      rerateMessage.value = ''
    }
  }

  return {
    pendingTeams,
    loadingTeams,
    finishedTeams,
    refreshingTeams,
    loadPendingTeams,
    approveTeam,
    rejectTeam,
    allTeams,
    loadingAllTeams,
    settingsTeamObject,
    showTeamSettingsPopup,
    editingTeam,
    loadingTeamSettings,
    savingTeamSettings,
    resettingTeamSettings,
    reratingTeam,
    rerateProgress,
    rerateMessage,
    broadcastScope,
    broadcastTeamIds,
    broadcastContent,
    publishingBroadcast,
    editSettingsForm,
    invalidSettingMessages,
    loadAllTeams,
    publishBroadcastNotice,
    openTeamSettings,
    saveTeamSettings,
    resetTeamSettings,
    rerateEditingTeam,
    getRangeText,
  }
}
