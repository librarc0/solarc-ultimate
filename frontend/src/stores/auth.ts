import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api'

export interface UserInfo {
  id: number
  team_id: number | null
  username: string
  display_name: string
  role: 'owner' | 'admin' | 'member'
  status: 'active' | 'pending' | 'rejected'
  is_superadmin?: boolean
  gender?: string | null
}

// T019 [US1]: 用户上下文接口（/auth/me/context）
export interface TeamEntry {
  team_id: number
  team_name: string | null
  player_id: number
  role: string
  status: string
}

export interface ActivePlayerContext {
  player_id: number
  team_id: number
  role: string
  status: string
  display_name: string | null
  mu: number
  conservative_rating: number
}

export interface UserContextData {
  user_id: number
  username: string
  email: string | null
  is_superadmin: boolean
  default_team_id: number | null
  teams: TeamEntry[]
  active_player: ActivePlayerContext | null
}

export interface TeamSeasonItem {
  id: number
  year: number
  is_current: boolean
  member_count: number
}

function unwrapApiData<T>(raw: any): T {
  if (raw && typeof raw === 'object' && 'code' in raw && 'data' in raw) {
    return raw.data as T
  }
  return raw as T
}

const AUTH_STORAGE = sessionStorage

function cleanupLegacyAuthStorage() {
  // 迁移策略：认证态不再持久化到 localStorage，启动时清理历史遗留键
  localStorage.removeItem('access_token')
  localStorage.removeItem('user_role')
  localStorage.removeItem('team_id')
  localStorage.removeItem('viewing_team_id')
  localStorage.removeItem('team_count')
}

export const useAuthStore = defineStore('auth', () => {
  cleanupLegacyAuthStorage()

  const token = ref<string | null>(AUTH_STORAGE.getItem('access_token'))
  const user = ref<UserInfo | null>(null)
  const role = ref<string | null>(AUTH_STORAGE.getItem('user_role'))
  // 持久化 team_id，解决刷新后 hasTeam 为 false 的问题
  const _cachedTeamId = ref<number | null>(
    AUTH_STORAGE.getItem('team_id') ? Number(AUTH_STORAGE.getItem('team_id')) : null
  )
  // 持久化 is_superadmin 已移除（防止控制台修改 localStorage 伪造超管状态），改为仅内存缓存
  const _cachedIsSuperAdmin = ref<boolean>(false)

  // T019 [US1]: user 级上下文（/auth/me/context），含可用队伍列表
  const userContext = ref<UserContextData | null>(null)
  const availableTeams = ref<TeamEntry[]>([])
  // 持久化队伍数量以支持刷新后 hasTeam 判断（不含敏感信息）
  const _cachedTeamCount = ref<number>(
    AUTH_STORAGE.getItem('team_count') ? Number(AUTH_STORAGE.getItem('team_count')) : 0
  )

  // 超级管理员相关（不再写入 localStorage，防止云端伪造）
  const isSuperAdmin = computed(() => !!user.value?.is_superadmin || _cachedIsSuperAdmin.value)
  const viewingTeamId = ref<number | null>(
    AUTH_STORAGE.getItem('viewing_team_id') ? Number(AUTH_STORAGE.getItem('viewing_team_id')) : null
  )

  // 赛季状态
  const teamSeasons = ref<TeamSeasonItem[]>([])
  const selectedSeasonId = ref<number | null>(null)
  const isViewingCurrentSeason = computed(() => {
    if (selectedSeasonId.value === null) return true
    const s = teamSeasons.value.find(s => s.id === selectedSeasonId.value)
    return s?.is_current === true
  })

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => role.value === 'admin' || role.value === 'owner' || isSuperAdmin.value)
  const isOwner = computed(() => role.value === 'owner')
  // T019 [US1]: hasTeam 同时检查 userContext.teams 或持久化的队伍数量
  const hasTeam = computed(
    () =>
      isSuperAdmin.value ||
      (userContext.value ? userContext.value.teams.length > 0 : _cachedTeamCount.value > 0) ||
      !!(user.value?.team_id ?? _cachedTeamId.value)
  )
  const isPending = computed(() => user.value?.status === 'pending')

  function setViewingTeam(teamId: number | null) {
    viewingTeamId.value = teamId
    if (teamId !== null) {
      AUTH_STORAGE.setItem('viewing_team_id', String(teamId))
    } else {
      AUTH_STORAGE.removeItem('viewing_team_id')
    }
  }

  async function login(username: string, password: string) {
    const form = new FormData()
    form.append('username', username)
    form.append('password', password)
    const res = await api.post('/auth/login', form)
    const data = unwrapApiData<{ access_token: string; role: string }>(res.data)
    token.value = data.access_token
    role.value = data.role
    AUTH_STORAGE.setItem('access_token', token.value!)
    AUTH_STORAGE.setItem('user_role', role.value!)
    try {
      await fetchMe()
      // T019 [US1]: 登录后同步加载 user 级上下文（含可用队伍列表）
      await fetchContext()
    } catch {
      // fetchMe/fetchContext 失败时清理已写入的 token，避免状态不一致
      logout()
      throw new Error('登录成功但获取用户信息失败，请重试')
    }
  }

  // T019 [US1]: 加载 user 上下文（可用队伍集合）
  async function fetchContext() {
    const res = await api.get('/auth/me/context')
    const data = unwrapApiData<UserContextData>(res.data)
    userContext.value = data
    availableTeams.value = data.teams
    _cachedTeamCount.value = data.teams.length
    AUTH_STORAGE.setItem('team_count', String(data.teams.length))
  }

  // T019 [US1]: 切换队伍（发起 /auth/switch-team，更新 token 与上下文）
  async function switchTeam(teamId: number) {
    const res = await api.post('/auth/switch-team', { team_id: teamId })
    const data = unwrapApiData<{ access_token: string; role: string }>(res.data)
    token.value = data.access_token
    role.value = data.role
    AUTH_STORAGE.setItem('access_token', token.value!)
    AUTH_STORAGE.setItem('user_role', role.value!)
    // active player 变了，需重新拉取 player 信息与 context
    await fetchMe()
    await fetchContext()
  }

  // T034 [US3]: 设置默认队伍（调用 /auth/me/default-team，同步 userContext）
  async function setDefaultTeam(teamId: number | null) {
    await api.post('/auth/me/default-team', { team_id: teamId })
    if (userContext.value) {
      userContext.value = { ...userContext.value, default_team_id: teamId }
    }
  }

  // T047 [US5]: 退队并清理本地上下文（调用 leave 端点，刷新 context 使 teams 列表收敛）
  async function leaveTeam() {
    await api.delete('/team-membership/leave')
    // 退队后刷新 user 级上下文，使 availableTeams 自动收敛（服务端已清除 default_team_id）
    await fetchContext()
    // 同步更新 user.team_id（fetchMe 读取当前 active player）
    await fetchMe()
  }

  async function fetchMe() {
    const res = await api.get('/players/me')
    const data = unwrapApiData<UserInfo>(res.data)
    user.value = data
    // 同步角色缓存（team_id 可能为 null 时 role 也保持最新）
    if (data.role) {
      role.value = data.role
      AUTH_STORAGE.setItem('user_role', role.value!)
    }
    // 持久化 is_superadmin 已移除，只在内存中保留（防止控制台伪造持久化缓存）
    _cachedIsSuperAdmin.value = !!data.is_superadmin
    // 持久化 team_id
    if (data.team_id) {
      _cachedTeamId.value = data.team_id
      AUTH_STORAGE.setItem('team_id', String(data.team_id))
    } else {
      _cachedTeamId.value = null
      AUTH_STORAGE.removeItem('team_id')
    }
  }

  function logout() {
    token.value = null
    user.value = null
    role.value = null
    _cachedTeamId.value = null
    _cachedIsSuperAdmin.value = false
    viewingTeamId.value = null
    teamSeasons.value = []
    selectedSeasonId.value = null
    // T019 [US1]: 清理 user 上下文
    userContext.value = null
    availableTeams.value = []
    _cachedTeamCount.value = 0
    AUTH_STORAGE.removeItem('access_token')
    AUTH_STORAGE.removeItem('user_role')
    AUTH_STORAGE.removeItem('team_id')
    localStorage.removeItem('is_superadmin')  // 广播清除（對老版本缓存兼容）
    AUTH_STORAGE.removeItem('viewing_team_id')
    AUTH_STORAGE.removeItem('team_count')
    // 兼容清理旧版 localStorage 认证键
    cleanupLegacyAuthStorage()
  }

  async function loadTeamSeasons(teamId?: number) {
    const tid = teamId ?? user.value?.team_id ?? _cachedTeamId.value
    if (!tid) return
    // 当前后端未提供 /team/seasons，避免产生 404 噪音。
    // 赛季选择保留为可选功能，待后端恢复后再启用接口请求。
    teamSeasons.value = []
    selectedSeasonId.value = null
  }

  return { token, user, role, isLoggedIn, isAdmin, isOwner, hasTeam, isPending, isSuperAdmin, viewingTeamId, setViewingTeam, login, logout, fetchMe, fetchContext, switchTeam, setDefaultTeam, leaveTeam, userContext, availableTeams, teamSeasons, selectedSeasonId, isViewingCurrentSeason, loadTeamSeasons }
})

