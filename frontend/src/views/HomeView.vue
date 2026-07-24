<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'
import { APP_NAME, APP_COPYRIGHT } from '@/config/app'
import PlayerScheduleCalendar from '@/components/schedule/PlayerScheduleCalendar.vue'
import TeamSwitcher from '@/components/TeamSwitcher.vue'  // T027 [US2]

const auth = useAuthStore()
const router = useRouter()
const isAdmin = auth.isAdmin

interface ProfileData {
  id: number
  display_name: string | null
  username: string
  total_matches: number
  total_wins: number
  total_goals: number
  total_assists: number
  total_defenses: number
  total_plus_minus: number
  avatar_url?: string | null
  is_superadmin?: boolean
  jersey_number?: number | null
}

interface TeamInfo {
  id: number
  name: string
  member_count: number
  my_status: string
  logo_url?: string | null
}

interface MatchStatItem {
  match_id: number
  match_date: string
  goals: number
  assists: number
  defenses: number
  plus_minus: number
  is_winner: boolean
}

interface TeamPlayer {
  id: number
  conservative_rating: number
  mu: number
  sigma: number
  total_goals: number
  total_assists: number
  total_defenses: number
  total_plus_minus: number
  total_matches: number
  total_wins: number
  status: string
  show_in_rankings: boolean
}

interface PostItem {
  id: number
  author_id: number
  author_name: string
  content: string
  parent_id: number | null
  created_at: string
  replies: PostItem[]
}

interface AvailableTeam {
  id: number
  name: string
  member_count: number
}

const profile = ref<ProfileData | null>(null)
const teamInfo = ref<TeamInfo | null>(null)
const matchStats = ref<MatchStatItem[]>([])
const teamPlayers = ref<TeamPlayer[]>([])
const availableTeams = ref<AvailableTeam[]>([])
const compositeScoreMap = ref<Record<number, number>>({})
const loadingTeams = ref(false)
const loadingTeamsError = ref('')
const loading = ref(true)
const showTeamPicker = ref(false)
const showSeasonPicker = ref(false)
const AVAILABLE_TEAMS_CACHE_KEY = 'ep_available_teams_cache_v1'

function getCompositeScore(playerId?: number | null) {
  if (!playerId) return null
  const score = compositeScoreMap.value[playerId]
  return typeof score === 'number' ? score : null
}

const myCompositeScore = computed(() => getCompositeScore(profile.value?.id))

// ---- 赛季 ----
const seasonPickerActions = computed(() =>
  auth.teamSeasons.map(s => ({
    name: s.year + ' 赛季' + (s.is_current ? '（当前）' : ''),
    subname: s.member_count + ' 名队员',
    value: s.id,
    color: s.is_current ? '#3b82f6' : undefined,
  }))
)
const currentSeasonLabel = computed(() => {
  const s = auth.teamSeasons.find(s => s.id === auth.selectedSeasonId)
  if (!s) return '赛季'
  return s.year + ' 赛季' + (s.is_current ? '（当前）' : '（历史）')
})
const currentSeasonBadgeLabel = computed(() => {
  const s = auth.teamSeasons.find(s => s.id === auth.selectedSeasonId)
  if (!s) return '赛季'
  return s.is_current ? `${s.year}赛季` : `${s.year}赛季(历史)`
})

// ---- 留言板 ----
const posts = ref<PostItem[]>([])
const postsLoading = ref(false)
const posting = ref(false)
const newPostContent = ref('')
const replyTo = ref<{ id: number; name: string } | null>(null)
const POSTS_CACHE_KEY = 'ep_team_posts_cache_v1'

// ---- 通知 ----
const notifCount = ref(0)
const showNotifPopup = ref(false)
const notifItems = ref<{ type: string; title: string; body: string; hint: string; created_at: string }[]>([])
const notifLoading = ref(false)
const NOTIF_KEY = 'ep_notif_last_seen'

async function fetchNotifCount() {
  const since = localStorage.getItem(NOTIF_KEY) ?? ''
  try {
    const res = await api.get('/team/notifications/count', since ? { params: { since } } : {})
    notifCount.value = res.data.count ?? 0
  } catch { /* ignore */ }
}

async function openNotifPopup() {
  showNotifPopup.value = true
  notifLoading.value = true
  const since = localStorage.getItem(NOTIF_KEY) ?? ''
  try {
    const res = await api.get('/team/notifications', since ? { params: { since } } : {})
    notifItems.value = res.data.items ?? []
  } catch {
    notifItems.value = []
  } finally {
    notifLoading.value = false
  }
}

function markNotifRead() {
  localStorage.setItem(NOTIF_KEY, new Date().toISOString())
  notifCount.value = 0
  notifItems.value = []
}

function notifIcon(type: string) {
  if (type === 'reply') return 'comment-o'
  if (type === 'schedule') return 'calendar-o'
  if (type === 'announcement') return 'volume-o'
  if (type === 'approval') return 'todo-list-o'
  return 'bell'
}

function notifColor(type: string) {
  if (type === 'reply') return '#60a5fa'
  if (type === 'schedule') return '#22c55e'
  if (type === 'announcement') return '#f59e0b'
  if (type === 'approval') return '#a78bfa'
  return '#94a3b8'
}

// ---- 留言板函数 ----
function formatTime(dt: string) {
  const d = new Date(dt)
  return d.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function canDelete(post: PostItem) {
  return isAdmin || profile.value?.id === post.author_id
}

function startReply(id: number, name: string) { replyTo.value = { id, name } }
function cancelReply() { replyTo.value = null }

function postsCacheKeyOf() {
  const tid = auth.viewingTeamId ?? teamInfo.value?.id ?? auth.user?.team_id ?? 0
  return `${POSTS_CACHE_KEY}:${tid}`
}

function persistPostsCache(items: PostItem[]) {
  try {
    localStorage.setItem(postsCacheKeyOf(), JSON.stringify(items))
  } catch {
    // ignore
  }
}

function readPostsCache(): PostItem[] {
  try {
    const raw = localStorage.getItem(postsCacheKeyOf())
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

async function loadPosts() {
  postsLoading.value = true
  try {
    const res = await api.get('/team/posts', { params: { page_size: 10 } })
    posts.value = res.data
    if (posts.value.length > 0) {
      persistPostsCache(posts.value)
    }
  } catch {
    const cached = readPostsCache()
    if (cached.length > 0) {
      posts.value = cached
    }
  } finally {
    postsLoading.value = false
  }
}

async function submitPost() {
  if (!newPostContent.value.trim()) return
  posting.value = true
  try {
    const res = await api.post('/team/posts', {
      content: newPostContent.value.trim(),
      parent_id: replyTo.value?.id ?? null,
    })
    newPostContent.value = ''
    if (res.data.parent_id == null) {
      posts.value.unshift({ ...res.data, replies: [] })
    } else {
      const parent = posts.value.find(p => p.id === res.data.parent_id)
      if (parent) parent.replies.push(res.data)
    }
    replyTo.value = null
  } catch { /* ignore */ } finally {
    posting.value = false
  }
}

async function deletePost(id: number) {
  try {
    await api.delete(`/team/posts/${id}`)
    const topIdx = posts.value.findIndex(p => p.id === id)
    if (topIdx >= 0) {
      posts.value.splice(topIdx, 1)
    } else {
      for (const post of posts.value) {
        const rIdx = post.replies.findIndex(r => r.id === id)
        if (rIdx >= 0) { post.replies.splice(rIdx, 1); break }
      }
    }
  } catch { /* ignore */ }
}

// ---- 雷达图 ----
const svgSize = 200
const cx = svgSize / 2
const cy = svgSize / 2
const maxR = 75
const axes = ['综合战力', '得分', '助攻', '胜率', '防守']
const axisAngles = axes.map((_, i) => -Math.PI / 2 + (i * 2 * Math.PI) / 5)
const showTeamAvg = ref(true)

// 按每场均值归一，使个人数据有意义（不受总场次影响）
function normalizePersonal(p: ProfileData): number[] {
  const m = Math.max(1, p.total_matches)
  const composite = getCompositeScore(p.id) ?? 50
  const winRateNorm = p.total_matches > 0 ? p.total_wins / p.total_matches : 0
  return [
    Math.min(1, Math.max(0, composite / 100)),
    Math.min(1, Math.max(0, p.total_goals   / m / 2.0)),
    Math.min(1, Math.max(0, p.total_assists  / m / 1.5)),
    Math.min(1, Math.max(0, winRateNorm)),
    Math.min(1, Math.max(0, (p.total_defenses / m + 3) / 6.0)),
  ]
}

function normalizeTeamPlayer(p: TeamPlayer): number[] {
  const m = Math.max(1, p.total_matches)
  const composite = getCompositeScore(p.id) ?? 50
  const winRateNorm = p.total_matches > 0 ? p.total_wins / p.total_matches : 0
  return [
    Math.min(1, Math.max(0, composite / 100)),
    Math.min(1, Math.max(0, p.total_goals   / m / 2.0)),
    Math.min(1, Math.max(0, p.total_assists  / m / 1.5)),
    Math.min(1, Math.max(0, winRateNorm)),
    Math.min(1, Math.max(0, (p.total_defenses / m + 3) / 6.0)),
  ]
}

const scores = computed<number[]>(() => {
  if (!profile.value) return [0, 0, 0, 0, 0]
  return normalizePersonal(profile.value)
})

const teamAvgScores = computed<number[]>(() => {
  const active = teamPlayers.value.filter(p => p.status === 'active' && p.show_in_rankings)
  if (!active.length) return [0, 0, 0, 0, 0]
  const sums: number[] = [0, 0, 0, 0, 0]
  for (const p of active) {
    const ns = normalizeTeamPlayer(p)
    for (let i = 0; i < 5; i++) sums[i] = (sums[i] ?? 0) + (ns[i] ?? 0)
  }
  return sums.map(s => s / active.length)
})

// 雷达图底部数值展示
const radarDisplayValues = computed(() => {
  if (!profile.value) return axes.map(() => '--')
  const p = profile.value
  const m = Math.max(1, p.total_matches)
  const composite = getCompositeScore(p.id)
  const winRatePct = p.total_matches > 0 ? (p.total_wins / p.total_matches) * 100 : 0
  return [
    composite != null ? composite.toFixed(1) : '--',
    (p.total_goals   / m).toFixed(2) + '/场',
    (p.total_assists  / m).toFixed(2) + '/场',
    winRatePct.toFixed(0) + '%',
    (p.total_defenses / m).toFixed(2) + '/场',
  ]
})
function polarToXY(angle: number, r: number) {
  return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) }
}

const outerPath = computed(() =>
  axisAngles.map((a, i) => {
    const { x, y } = polarToXY(a, maxR)
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ') + ' Z'
)

const innerPath50 = computed(() =>
  axisAngles.map((a, i) => {
    const { x, y } = polarToXY(a, maxR * 0.5)
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ') + ' Z'
)

const dataPath = computed(() =>
  axisAngles.map((a, i) => {
    const r = (scores.value[i] ?? 0) * maxR
    const { x, y } = polarToXY(a, r)
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ') + ' Z'
)

const labelPositions = computed(() =>
  axisAngles.map((a, i) => {
    const { x, y } = polarToXY(a, maxR + 18)
    return { x, y, label: axes[i] }
  })
)

const teamAvgPath = computed(() =>
  axisAngles.map((a, i) => {
    const r = (teamAvgScores.value[i] ?? 0) * maxR
    const { x, y } = polarToXY(a, r)
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ') + ' Z'
)

// ---- 个人数据统计图（多指标切换） ----
type ChartTab = 'rating' | 'goals' | 'assists' | 'defense'
const chartTab = ref<ChartTab>('rating')

const CHART_W = 320
const CHART_H = 110

const chartSeries = computed<number[]>(() => {
  const compositeFromMatch = (s: MatchStatItem) => {
    const base = 50
    const perf = s.goals * 3 + s.assists * 2 + s.defenses * 1 + s.plus_minus * 0.5
    const resultBonus = s.is_winner ? 2 : -1
    return Math.max(0, Math.min(100, base + perf + resultBonus))
  }
  switch (chartTab.value) {
    case 'rating':  return [...matchStats.value].reverse().map(compositeFromMatch)
    case 'goals':   return [...matchStats.value].reverse().map(s => s.goals)
    case 'assists': return [...matchStats.value].reverse().map(s => s.assists)
    case 'defense': return [...matchStats.value].reverse().map(s => s.defenses)
    default: return []
  }
})

const chartPoints = computed<{ x: number; y: number; val: number }[]>(() => {
  const data = chartSeries.value
  if (data.length < 2) return []
  const minV = Math.min(...data)
  const maxV = Math.max(...data)
  const range = maxV - minV || 1
  return data.map((v, i) => ({
    x: 20 + (i / (data.length - 1)) * (CHART_W - 40),
    y: 20 + (1 - (v - minV) / range) * (CHART_H - 30),
    val: v,
  }))
})

const chartColor = computed(() => {
  switch (chartTab.value) {
    case 'rating':  return '#3b82f6'
    case 'goals':   return '#f59e0b'
    case 'assists': return '#10b981'
    case 'defense': return '#a855f7'
    default: return '#3b82f6'
  }
})

// 贝塞尔平滑曲线
const chartPathD = computed(() => {
  const pts = chartPoints.value
  if (!pts.length) return ''
  let d = `M${pts[0]!.x.toFixed(1)},${pts[0]!.y.toFixed(1)}`
  for (let i = 1; i < pts.length; i++) {
    const prev = pts[i - 1]!
    const curr = pts[i]!
    const cpx = (curr.x - prev.x) * 0.35
    d += ` C${(prev.x + cpx).toFixed(1)},${prev.y.toFixed(1)} ${(curr.x - cpx).toFixed(1)},${curr.y.toFixed(1)} ${curr.x.toFixed(1)},${curr.y.toFixed(1)}`
  }
  return d
})

const chartFillD = computed(() => {
  if (!chartPoints.value.length) return ''
  const pts = chartPoints.value
  const last = pts[pts.length - 1]!
  const first = pts[0]!
  return `${chartPathD.value} L${last.x.toFixed(1)},${CHART_H} L${first.x.toFixed(1)},${CHART_H} Z`
})

const hasChartData = computed(() => chartSeries.value.length >= 2)

const chartLatest = computed(() => {
  const s = chartSeries.value
  return s.length ? s[s.length - 1]! : null
})
const chartAvg = computed(() => {
  const s = chartSeries.value
  if (!s.length) return null
  return Math.round((s.reduce((a, b) => a + b, 0) / s.length) * 10) / 10
})
const chartChange = computed(() => {
  const s = chartSeries.value
  if (s.length < 2) return null
  return Math.round(((s[s.length - 1]! - s[s.length - 2]!) * 10)) / 10
})
const chartLabel = computed(() => {
  switch (chartTab.value) {
    case 'rating':  return { unit: ' 分', dec: 1 }
    case 'goals':   return { unit: ' 球', dec: 0 }
    case 'assists': return { unit: ' 次', dec: 0 }
    case 'defense': return { unit: '',    dec: 0 }
    default:        return { unit: '',    dec: 1 }
  }
})

// ---- 队伍切换按钮显示名称 ----
const currentViewingTeamName = computed(() => {
  if (auth.isSuperAdmin) {
    const tid = auth.viewingTeamId
    if (!tid) return '全部队伍'
    return availableTeams.value.find(t => t.id === tid)?.name ?? `队伍 #${tid}`
  }
  // 普通多队成员：显示当前所在队伍名称
  if (auth.availableTeams.length > 1) {
    const tid = auth.user?.team_id
    if (!tid) return '切换队伍'
    return auth.availableTeams.find(t => t.team_id === tid)?.team_name ?? `队伍 #${tid}`
  }
  return null
})

function readCachedAvailableTeams() {
  try {
    const raw = localStorage.getItem(AVAILABLE_TEAMS_CACHE_KEY)
    if (!raw) return
    const cached = JSON.parse(raw)
    if (Array.isArray(cached) && cached.length > 0) {
      availableTeams.value = cached
    }
  } catch {
    // ignore
  }
}

function persistAvailableTeams(teams: AvailableTeam[]) {
  try {
    localStorage.setItem(AVAILABLE_TEAMS_CACHE_KEY, JSON.stringify(teams))
  } catch {
    // ignore
  }
}

function delay(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function loadAvailableTeams(force = false) {
  if (!auth.isSuperAdmin) return
  if (!force && availableTeams.value.length > 0) return

  loadingTeams.value = true
  loadingTeamsError.value = ''

  try {
    for (let i = 0; i < 3; i++) {
      try {
        const res = await api.get('/team/available', { timeout: 20000 })
        availableTeams.value = Array.isArray(res.data) ? res.data : []
        if (availableTeams.value.length > 0) {
          persistAvailableTeams(availableTeams.value)
        }
        return
      } catch {
        if (i < 2) {
          await delay(400 * (i + 1))
        }
      }
    }

    readCachedAvailableTeams()
    if (availableTeams.value.length > 0) {
      loadingTeamsError.value = '网络波动，已展示上次缓存队伍列表'
    } else {
      loadingTeamsError.value = '队伍列表加载失败，请重试'
    }
  } finally {
    loadingTeams.value = false
  }
}

function onSelectTeam(team: AvailableTeam | null) {
  auth.setViewingTeam(team ? team.id : null)
  showTeamPicker.value = false
  loadData()
}

// T027 [US2]: TeamSwitcher 切队成功后刷新页面数据
function onTeamSwitched() {
  loadData()
  loadPosts()
  auth.loadTeamSeasons().catch(() => {})
}

// 打开选择器时确保队伍列表已加载（防止 loadData 失败或竞态导致空列表）
watch(showTeamPicker, async (opened) => {
  if (!opened) return
  if (availableTeams.value.length === 0 || loadingTeamsError.value) {
    await loadAvailableTeams(true)
  }
})

async function loadData() {
  loading.value = true
  try {
    // 使用 allSettled 防止单个请求失败导致整页数据丢失
    const [profileRes, teamRes, statsRes, playersRes] = await Promise.allSettled([
      api.get('/players/me'),
      api.get('/team/my'),
      api.get('/players/me/match_stats', { params: { limit: 20 } }),
      api.get('/players', { params: { page_size: 100 } }),
    ])
    if (profileRes.status === 'fulfilled') profile.value = profileRes.value.data
    if (teamRes.status === 'fulfilled') teamInfo.value = teamRes.value.data
    if (statsRes.status === 'fulfilled') matchStats.value = statsRes.value.data
    if (playersRes.status === 'fulfilled') teamPlayers.value = playersRes.value.data

    // 独立加载综合战力映射，失败不影响首页主体
    // 注：后端 page_size 最大限制 100，超出会返回 422
    try {
      const rankRes = await api.get('/rankings', {
        params: { page: 1, page_size: 100, sort_by: 'composite' },
      })
      const rows = Array.isArray(rankRes.data?.items) ? rankRes.data.items : []
      const scoreMap: Record<number, number> = {}
      for (const row of rows) {
        if (typeof row?.player_id === 'number' && typeof row?.composite_score === 'number') {
          scoreMap[row.player_id] = row.composite_score
        }
      }
      compositeScoreMap.value = scoreMap
    } catch {
      // ignore
    }

    // 加载赛季列表
    await auth.loadTeamSeasons().catch(() => {})
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (auth.isSuperAdmin) {
    readCachedAvailableTeams()
    // 后台静默预加载最新队伍列表（即使有缓存也强制刷新，避免超管看到旧列表）
    loadAvailableTeams(true)
  }
  await Promise.all([loadData(), loadPosts(), fetchNotifCount()])
  setInterval(fetchNotifCount, 2 * 60 * 1000)
})

function goNewMatch() {
  router.push('/match/input')
}

const winRate = computed(() => {
  if (!profile.value || profile.value.total_matches === 0) return '-'
  return (profile.value.total_wins / profile.value.total_matches * 100).toFixed(0) + '%'
})
</script>

<template>
  <div class="home-page">
    <!-- 顶栏 -->
    <van-nav-bar :title="APP_NAME">
      <template #right>
        <div class="nav-right">
          <div class="notif-bell" @click="openNotifPopup">
            <van-icon name="bell" size="20" :color="notifCount > 0 ? '#f59e0b' : '#64748b'" />
            <span v-if="notifCount > 0" class="notif-badge">{{ notifCount > 99 ? '99+' : notifCount }}</span>
          </div>
          <span v-if="auth.isSuperAdmin || auth.availableTeams.length > 1" class="team-switch-btn" @click.stop="showTeamPicker = true">
            {{ currentViewingTeamName }} ▾
          </span>
        </div>
      </template>
    </van-nav-bar>

    <van-loading v-if="loading" type="spinner" vertical style="padding: 60px 0; color:#3b82f6" />
    <template v-else>

      <van-notice-bar
        v-if="auth.isPending"
        left-icon="warning-o"
        :text="auth.user?.role === 'owner'
          ? '当前账号处于待审批状态，请联系超级管理员审批队伍申请'
          : '当前账号处于待审批状态，请联系队伍管理员审批入队申请'"
        color="#ad6800"
        background="#fff7e6"
        style="margin: 8px 12px 0"
      />

      <!-- 队伍 Banner -->
      <div class="team-banner" v-if="teamInfo">
        <div class="team-banner__bg" :style="teamInfo.logo_url ? `background-image:url(${teamInfo.logo_url})` : ''" />
        <div class="team-banner__content">
          <div class="team-logo-wrap">
            <img v-if="teamInfo.logo_url" :src="teamInfo.logo_url" class="team-logo" />
            <div v-else class="team-logo-placeholder">🦅</div>
          </div>
          <div class="team-info-right">
            <div class="team-name-row">
              <span class="team-name">{{ teamInfo.name }}</span>
              <span
                v-if="auth.teamSeasons.length > 0"
                class="nav-season-badge"
                :class="{ 'nav-season-badge--history': !auth.isViewingCurrentSeason }"
                @click.stop="showSeasonPicker = true"
              >{{ currentSeasonBadgeLabel }} ▾</span>
            </div>
            <div class="team-meta">{{ teamInfo.member_count }} 名队员</div>
            <div v-if="isAdmin" class="team-actions">
              <van-button size="mini" color="#3b82f6" @click="router.push('/team/manage')">队伍管理</van-button>
              <van-button size="mini" plain color="#8b5cf6" @click="router.push('/schedule')">日程管理</van-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 历史赛季只读横幅（在 Banner 下方） -->
      <div v-if="auth.teamSeasons.length > 0 && !auth.isViewingCurrentSeason" class="season-readonly-banner">
        📂 正在查看 {{ currentSeasonLabel }}（历史，只读）
      </div>
      <van-action-sheet
        v-model:show="showSeasonPicker"
        :actions="seasonPickerActions"
        title="选择赛季"
        @select="(a: any) => { auth.selectedSeasonId = a.value; showSeasonPicker = false }"
        cancel-text="取消"
      />

      <!-- 个人卡片 -->
      <div class="player-card" v-if="profile">
        <div class="player-card__left">
          <div class="player-avatar">
            <img v-if="profile.avatar_url" :src="profile.avatar_url" class="avatar-img" />
            <span v-else class="avatar-placeholder">{{ (profile.display_name || profile.username).charAt(0).toUpperCase() }}</span>
          </div>
          <div class="player-info">
            <div class="player-name">
              {{ profile.display_name || profile.username }}
              <span v-if="profile.jersey_number != null" class="jersey-badge">#{{ profile.jersey_number }}</span>
            </div>
            <van-tag :type="profile.total_matches < 5 ? 'warning' : 'primary'">
              {{ profile.total_matches < 5 ? '新人' : '活跃队员' }}
            </van-tag>
          </div>
        </div>
        <div class="player-card__right">
          <div class="rating-big">{{ myCompositeScore != null ? myCompositeScore.toFixed(1) : '--' }}</div>
        </div>
      </div>

      <!-- 日程日历（球员查看出勤）-->
      <PlayerScheduleCalendar />

      <!-- 快捷统计行 -->
      <div class="quick-stats" v-if="profile">
        <div class="qs-item">
          <div class="qs-val">{{ profile.total_matches }}</div>
          <div class="qs-lbl">总场次</div>
        </div>
        <div class="qs-item">
          <div class="qs-val">{{ profile.total_wins }}</div>
          <div class="qs-lbl">胜场</div>
        </div>
        <div class="qs-item">
          <div class="qs-val">{{ winRate }}</div>
          <div class="qs-lbl">胜率</div>
        </div>
        <div class="qs-item">
          <div class="qs-val">{{ profile.total_goals }}</div>
          <div class="qs-lbl">得分</div>
        </div>
        <div class="qs-item">
          <div class="qs-val">{{ profile.total_assists }}</div>
          <div class="qs-lbl">助攻</div>
        </div>
        <div class="qs-item">
          <div class="qs-val">{{ profile.total_defenses }}</div>
          <div class="qs-lbl">防守</div>
        </div>
      </div>

      <!-- 个人数据统计 -->
      <div class="section-card">
        <div class="section-title-row">
          <span class="section-title">📊 个人数据统计</span>
          <div class="chart-tabs">
            <button :class="['chart-tab', { active: chartTab === 'rating'  }]" @click="chartTab = 'rating'">战力</button>
            <button :class="['chart-tab', { active: chartTab === 'goals'   }]" @click="chartTab = 'goals'">得分</button>
            <button :class="['chart-tab', { active: chartTab === 'assists' }]" @click="chartTab = 'assists'">助攻</button>
            <button :class="['chart-tab', { active: chartTab === 'defense' }]" @click="chartTab = 'defense'">防守</button>
          </div>
        </div>
        <template v-if="hasChartData">
          <!-- 摘要数字 -->
          <div class="chart-stats-row">
            <div class="chart-stat">
              <div class="cs-label">最新</div>
              <div class="cs-value" :style="{ color: chartColor }">
                {{ chartLatest != null ? (chartLabel.dec === 0 ? Math.round(chartLatest) : chartLatest.toFixed(1)) : '--' }}{{ chartLabel.unit }}
              </div>
            </div>
            <div class="chart-divider" />
            <div class="chart-stat">
              <div class="cs-label">均值</div>
              <div class="cs-value">
                {{ chartAvg != null ? (chartLabel.dec === 0 ? Math.round(chartAvg) : chartAvg.toFixed(1)) : '--' }}{{ chartLabel.unit }}
              </div>
            </div>
            <div class="chart-divider" />
            <div class="chart-stat">
              <div class="cs-label">较上场</div>
              <div class="cs-value" :class="chartChange != null && chartChange > 0 ? 'cs-up' : chartChange != null && chartChange < 0 ? 'cs-dn' : ''">
                {{ chartChange != null ? (chartChange > 0 ? '+' : '') + (chartLabel.dec === 0 ? Math.round(chartChange) : chartChange.toFixed(1)) : '--' }}
              </div>
            </div>
          </div>
          <!-- 曲线图 -->
          <svg :viewBox="`0 0 ${CHART_W} ${CHART_H}`" class="trend-svg" style="overflow:visible">
            <defs>
              <linearGradient :id="`cg-${chartTab}`" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   :stop-color="chartColor" stop-opacity="0.28" />
                <stop offset="100%" :stop-color="chartColor" stop-opacity="0.02" />
              </linearGradient>
            </defs>
            <!-- 参考格线 -->
            <line v-for="g in [0.33, 0.67]" :key="g"
              :x1="16" :y1="20 + (1 - g) * (CHART_H - 30)"
              :x2="CHART_W - 16" :y2="20 + (1 - g) * (CHART_H - 30)"
              stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"
            />
            <path :d="chartFillD" :fill="`url(#cg-${chartTab})`" />
            <path :d="chartPathD" fill="none" :stroke="chartColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
            <!-- 全部数据点（小圆点） -->
            <circle v-for="(pt, i) in chartPoints" :key="i"
              :cx="pt.x" :cy="pt.y" r="2.5" :fill="chartColor" opacity="0.5"
            />
            <!-- 最后一个点高亮 -->
            <circle :cx="chartPoints[chartPoints.length-1]!.x" :cy="chartPoints[chartPoints.length-1]!.y"
              r="6" fill="#0f172a" :stroke="chartColor" stroke-width="2.5" />
            <circle :cx="chartPoints[chartPoints.length-1]!.x" :cy="chartPoints[chartPoints.length-1]!.y"
              r="2.5" :fill="chartColor" />
            <!-- 最新值文本 -->
            <text
              :x="chartPoints[chartPoints.length-1]!.x"
              :y="chartPoints[chartPoints.length-1]!.y - 13"
              text-anchor="middle" font-size="10" :fill="chartColor" font-weight="700"
            >{{ chartLatest != null ? (chartLabel.dec === 0 ? Math.round(chartLatest) : chartLatest.toFixed(1)) : '' }}</text>
          </svg>
          <div class="trend-labels">
            <span>← {{ chartSeries.length }} 场前</span>
            <span>最近一场 →</span>
          </div>
        </template>
        <p v-else class="no-data-hint">多打几场比赛后将显示趋势图</p>
      </div>

      <!-- 雷达图 -->
      <div class="section-card" v-if="profile">
        <div class="section-title-row">
          <span class="section-title">🕸 能力面板</span>
          <label class="avg-toggle">
            <input type="checkbox" v-model="showTeamAvg" />
            队伍均值
          </label>
        </div>
        <div class="radar-wrap">
          <svg :width="svgSize" :height="svgSize" viewBox="0 0 200 200">
            <path :d="outerPath" fill="none" stroke="#334155" stroke-width="1" />
            <path :d="innerPath50" fill="none" stroke="#334155" stroke-width="0.8" stroke-dasharray="3,3" />
            <line
              v-for="(a, i) in axisAngles" :key="`axis-${i}`"
              :x1="cx" :y1="cy"
              :x2="polarToXY(a, maxR).x" :y2="polarToXY(a, maxR).y"
              stroke="#475569" stroke-width="0.8"
            />
            <!-- 队伍均值（橙色虚线） -->
            <path
              v-if="showTeamAvg && teamPlayers.length > 0"
              :d="teamAvgPath"
              fill="rgba(251,146,60,0.15)"
              stroke="#fb923c"
              stroke-width="1.5"
              stroke-dasharray="4,3"
            />
            <!-- 个人数据（蓝色实线） -->
            <path :d="dataPath" fill="rgba(59,130,246,0.25)" stroke="#3b82f6" stroke-width="2" />
            <circle
              v-for="(a, i) in axisAngles" :key="`dot-${i}`"
              :cx="polarToXY(a, (scores[i] ?? 0) * maxR).x"
              :cy="polarToXY(a, (scores[i] ?? 0) * maxR).y"
              r="3" fill="#3b82f6"
            />
            <!-- 顶点数值标注（蓝色小字贴近数据点） -->
            <text
              v-for="(a, i) in axisAngles" :key="`val-${i}`"
              :x="polarToXY(a, (scores[i] ?? 0) * maxR + 10).x"
              :y="polarToXY(a, (scores[i] ?? 0) * maxR + 10).y"
              text-anchor="middle" dominant-baseline="middle"
              font-size="9" fill="#60a5fa" font-weight="600"
            >{{ radarDisplayValues[i] }}</text>
            <text
              v-for="lp in labelPositions" :key="lp.label"
              :x="lp.x" :y="lp.y"
              text-anchor="middle" dominant-baseline="middle"
              font-size="11" fill="#94a3b8"
            >{{ lp.label }}</text>
          </svg>
        </div>
        <div class="radar-legend">
          <span class="legend-self">● 个人</span>
          <span v-if="showTeamAvg" class="legend-avg">- - 队伍均值</span>
        </div>
        <!-- 个人各项数值 -->
        <div class="radar-values">
          <div v-for="(v, i) in radarDisplayValues" :key="axes[i]" class="rv-item">
            <div class="rv-axis">{{ axes[i] }}</div>
            <div class="rv-val">{{ v }}</div>
          </div>
        </div>
      </div>

      <!-- 队伍留言板 -->
      <div class="section-card" v-if="teamInfo">
        <div class="section-title-row">
          <span class="section-title">💬 队伍留言板</span>
          <van-loading v-if="postsLoading" size="14" color="#3b82f6" />
        </div>
        <!-- 帖子列表 -->
        <div class="post-list">
          <div v-if="posts.length === 0 && !postsLoading" class="no-data-hint">暂无留言，快来说点什么吧～</div>
          <template v-for="post in posts" :key="post.id">
            <div class="post-item">
              <div class="post-header">
                <span class="post-author">{{ post.author_name }}</span>
                <span class="post-time">{{ formatTime(post.created_at) }}</span>
                <div class="post-actions">
                  <van-icon name="chat-o" size="14" color="#60a5fa" style="cursor:pointer" @click.stop="startReply(post.id, post.author_name)" />
                  <van-icon v-if="canDelete(post)" name="delete-o" size="14" color="#f87171" style="cursor:pointer;margin-left:8px" @click.stop="deletePost(post.id)" />
                </div>
              </div>
              <div class="post-content">{{ post.content }}</div>
              <!-- 回复列表 -->
              <div v-if="post.replies.length > 0" class="reply-list">
                <div v-for="reply in post.replies" :key="reply.id" class="reply-item">
                  <div class="reply-header">
                    <span class="reply-author">{{ reply.author_name }}</span>
                    <span class="post-time">{{ formatTime(reply.created_at) }}</span>
                    <van-icon v-if="canDelete(reply)" name="delete-o" size="12" color="#f87171" style="cursor:pointer;margin-left:6px" @click.stop="deletePost(reply.id)" />
                  </div>
                  <div class="reply-content">{{ reply.content }}</div>
                </div>
              </div>
            </div>
          </template>
        </div>
        <!-- 输入框 -->
        <div class="post-input-area">
          <div v-if="replyTo" class="reply-to-hint">
            回复 @{{ replyTo.name }}
            <van-icon name="cross" size="12" style="cursor:pointer;margin-left:4px;vertical-align:middle" @click="cancelReply" />
          </div>
          <div class="post-input-row">
            <van-field
              v-model="newPostContent"
              :placeholder="replyTo ? '回复...' : '说点什么...'"
              :maxlength="500"
              clearable
              class="post-field"
            />
            <van-button type="primary" size="small" :loading="posting" :disabled="!newPostContent.trim()" @click="submitPost">
              {{ replyTo ? '回复' : '发送' }}
            </van-button>
          </div>
        </div>
      </div>

    </template>

    <!-- 通知弹窗 -->
    <van-popup v-model:show="showNotifPopup" position="bottom" round :style="{ maxHeight: '70vh', overflowY: 'auto' }">
      <div class="notif-header">
        <span class="notif-title">🔔 通知</span>
        <van-button size="mini" plain type="primary" @click="markNotifRead">全部已读</van-button>
      </div>
      <van-loading v-if="notifLoading" type="spinner" vertical style="padding:24px" color="#3b82f6" />
      <template v-else>
        <div v-if="notifItems.length === 0" class="notif-empty">暂无新通知</div>
        <div v-for="(n, i) in notifItems" :key="i" class="notif-item">
          <van-icon
            :name="notifIcon(n.type)"
            :color="notifColor(n.type)"
            size="20"
            style="flex-shrink:0"
          />
          <div class="notif-content">
            <div class="notif-item-title">{{ n.title }}</div>
            <div class="notif-item-body">{{ n.body }}</div>
            <div v-if="n.hint" class="notif-item-hint">{{ n.hint }}</div>
            <div class="notif-item-time">{{ formatTime(n.created_at) }}</div>
          </div>
        </div>
      </template>
    </van-popup>

    <!-- T027 [US2]: 统一切队组件（普通多队伍用户 + 超级管理员） -->
    <TeamSwitcher v-model:show="showTeamPicker" @switched="onTeamSwitched" />

    <!-- 底部导航 -->
    <van-tabbar route>
      <van-tabbar-item replace to="/home" icon="home-o">主页</van-tabbar-item>
      <van-tabbar-item replace to="/rankings" icon="chart-trending-o">排行榜</van-tabbar-item>
      <van-tabbar-item icon="plus" @click="goNewMatch">
        <template #icon="{ active }">
          <div class="tab-plus" :class="{ active }">＋</div>
        </template>
        新建
      </van-tabbar-item>
      <van-tabbar-item replace to="/matches/list" icon="records-o">比赛</van-tabbar-item>
      <van-tabbar-item replace to="/profile" icon="user-o">我的</van-tabbar-item>
    </van-tabbar>

    <!-- 版权信息 -->
    <div class="copyright-footer">
      <div>{{ APP_COPYRIGHT }}</div>
      <a
        class="icp-link"
        href="https://beian.miit.gov.cn/"
        target="_blank"
        rel="noopener noreferrer"
      >
        沪ICP备2026021594号-2
      </a>
    </div>
  </div>
</template>

<style scoped>
.home-page {
  min-height: 100vh;
  background: #0f172a;
  padding-bottom: 70px;
}

.copyright-footer {
  text-align: center;
  padding: 6px 0 8px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.25);
  letter-spacing: 0.5px;
}

.icp-link {
  display: inline-block;
  margin-top: 4px;
  color: rgba(255, 255, 255, 0.34);
  text-decoration: none;
  -webkit-tap-highlight-color: transparent;
}

.icp-link:active {
  color: rgba(255, 255, 255, 0.62);
}

.team-switch-btn {
  font-size: 13px;
  color: #60a5fa;
  cursor: pointer;
  padding: 4px 8px;
}

.team-picker-status {
  padding: 14px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #64748b;
  font-size: 13px;
}

.team-picker-status--error {
  color: #b45309;
}

/* ---- 队伍 Banner 赛季徽章 ---- */
.team-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.nav-season-badge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  background: #1e3a5f;
  color: #60a5fa;
  border: 1px solid #2563eb44;
  cursor: pointer;
  white-space: nowrap;
}
.nav-season-badge--history {
  background: #422006;
  color: #fbbf24;
  border-color: #d9770644;
}
.season-readonly-banner {
  margin: 4px 16px 0;
  background: #422006;
  color: #fbbf24;
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 6px;
}
/* ---- 队伍 Banner ---- */
.team-banner {
  position: relative;
  margin: 12px 16px 8px;
  border-radius: 16px;
  overflow: hidden;
  background: linear-gradient(135deg, #1e3a5f, #1e40af);
  min-height: 100px;
}

.team-banner__bg {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  opacity: 0.15;
}

.team-banner__content {
  position: relative;
  display: flex;
  align-items: center;
  padding: 16px;
  gap: 16px;
}

.team-logo-wrap { flex-shrink: 0; }

.team-logo {
  width: 64px;
  height: 64px;
  border-radius: 12px;
  object-fit: cover;
  border: 2px solid rgba(255,255,255,0.3);
}

.team-logo-placeholder {
  width: 64px;
  height: 64px;
  border-radius: 12px;
  background: rgba(255,255,255,0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  border: 2px solid rgba(255,255,255,0.2);
}

.team-name {
  font-size: 20px;
  font-weight: 700;
  color: #fff;
}

.team-meta {
  font-size: 13px;
  color: #93c5fd;
  margin-bottom: 8px;
}

.team-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* ---- 个人卡片 ---- */
.player-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0 16px 8px;
  padding: 14px 16px;
  background: #1e293b;
  border-radius: 12px;
}

.player-card__left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.player-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  overflow: hidden;
  background: #334155;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar-img { width: 100%; height: 100%; object-fit: cover; }

.avatar-placeholder {
  font-size: 20px;
  font-weight: 700;
  color: #60a5fa;
}

.player-name {
  font-size: 16px;
  font-weight: 600;
  color: #f1f5f9;
  margin-bottom: 4px;
}

.player-card__right { text-align: right; }

.rating-big {
  font-size: 28px;
  font-weight: 700;
  color: #60a5fa;
  line-height: 1;
}

.rating-label { font-size: 11px; color: #64748b; margin-top: 2px; }
/* ---- 球衣号码徽章 ---- */
.jersey-badge {
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  font-style: italic;
  color: #f59e0b;
  margin-left: 6px;
  letter-spacing: 0.5px;
}

/* ---- 通知弹窗 ---- */
.notif-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 10px;
  border-bottom: 1px solid #f0f0f0;
}
.notif-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a1a;
}
.notif-empty {
  text-align: center;
  color: #999;
  font-size: 13px;
  padding: 32px 0;
}
.notif-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid #f5f5f5;
}
.notif-content { flex: 1; }
.notif-item-title {
  font-size: 13px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 2px;
}
.notif-item-body {
  font-size: 12px;
  color: #555;
  line-height: 1.4;
}
.notif-item-hint {
  font-size: 11px;
  color: #999;
  margin-top: 2px;
}
.notif-item-time {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 6px;
}

/* ---- 快捷统计 ---- */
.quick-stats {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  margin: 0 16px 8px;
  background: #1e293b;
  border-radius: 12px;
  padding: 12px 4px;
}

.qs-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.qs-val { font-size: 16px; font-weight: 700; color: #f1f5f9; }
.qs-lbl { font-size: 10px; color: #64748b; margin-top: 2px; }

/* ---- 通用卡片 ---- */
.section-card {
  margin: 0 16px 8px;
  background: #1e293b;
  border-radius: 12px;
  padding: 14px;
}

.section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #94a3b8;
}

/* ---- 多指标统计图 tab ---- */
.chart-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}
.chart-tab {
  flex: 1;
  padding: 4px 0;
  border-radius: 6px;
  border: 1px solid #334155;
  background: transparent;
  color: #64748b;
  font-size: 12px;
  cursor: pointer;
}
.chart-tab.active {
  background: #1677ff;
  border-color: #1677ff;
  color: #fff;
}

/* ---- 队伍均值 toggle ---- */
.avg-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #fb923c;
  cursor: pointer;
}
.avg-toggle input[type="checkbox"] {
  width: 14px;
  height: 14px;
  accent-color: #fb923c;
}

/* ---- 雷达图图例 ---- */
.radar-legend {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-top: 6px;
  font-size: 11px;
}
.legend-self { color: #3b82f6; }
.legend-avg  { color: #fb923c; }

/* ---- 趋势图 ---- */
.trend-svg {
  display: block;
  width: 100%;
  height: auto;
  max-width: 320px;
  margin: 0 auto;
}

.trend-labels {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #475569;
  margin-top: 4px;
  padding: 0 20px;
}

.no-data-hint {
  text-align: center;
  color: #475569;
  font-size: 13px;
  padding: 10px 0;
}

/* ---- 雷达图 ---- */
.radar-wrap {
  display: flex;
  justify-content: center;
}

/* ---- tabbar ---- */
.tab-plus {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #3b82f6;
  color: #fff;
  font-size: 22px;
  line-height: 36px;
  text-align: center;
  font-weight: 700;
  margin: 0 auto;
  margin-bottom: -4px;
}

.tab-plus.active { background: #1d4ed8; }

/* ---- 通知铃铛 ---- */
.nav-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.notif-bell {
  position: relative;
  cursor: pointer;
  padding: 4px 6px;
  display: flex;
  align-items: center;
}
.notif-badge {
  position: absolute;
  top: 0;
  right: 0;
  background: #ef4444;
  color: #fff;
  font-size: 9px;
  font-weight: 700;
  min-width: 16px;
  height: 16px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 3px;
  line-height: 1;
}

/* ---- 统计摘要行 ---- */
.chart-stats-row {
  display: flex;
  align-items: center;
  background: #0f172a;
  border-radius: 10px;
  padding: 10px 6px;
  margin-bottom: 12px;
}
.chart-stat {
  flex: 1;
  text-align: center;
}
.cs-label {
  font-size: 10px;
  color: #475569;
  margin-bottom: 3px;
}
.cs-value {
  font-size: 18px;
  font-weight: 700;
  color: #f1f5f9;
  line-height: 1.2;
}
.cs-up { color: #22c55e !important; }
.cs-dn { color: #f87171 !important; }
.chart-divider {
  width: 1px;
  height: 32px;
  background: #1e3a5f;
  flex-shrink: 0;
}

/* ---- 雷达图数值展示 ---- */
.radar-values {
  display: flex;
  justify-content: space-around;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #1e3a5f;
}
.rv-item {
  text-align: center;
}
.rv-axis {
  font-size: 10px;
  color: #475569;
  margin-bottom: 2px;
}
.rv-val {
  font-size: 11px;
  font-weight: 600;
  color: #60a5fa;
}

/* ---- 留言板 ---- */
.post-list {
  margin-bottom: 12px;
}
.post-item {
  padding: 10px 0;
  border-bottom: 1px solid #1e3a5f;
}
.post-item:last-child { border-bottom: none; }
.post-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.post-author {
  font-size: 12px;
  font-weight: 600;
  color: #60a5fa;
}
.post-time {
  font-size: 10px;
  color: #475569;
  flex: 1;
}
.post-actions {
  display: flex;
  align-items: center;
}
.post-content {
  font-size: 13px;
  color: #cbd5e1;
  line-height: 1.5;
}
.reply-list {
  margin-top: 8px;
  padding-left: 12px;
  border-left: 2px solid #1e3a5f;
}
.reply-item {
  padding: 6px 0;
}
.reply-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 2px;
}
.reply-author {
  font-size: 11px;
  font-weight: 600;
  color: #fb923c;
}
.reply-content {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.4;
}
.post-input-area {
  border-top: 1px solid #1e3a5f;
  padding-top: 10px;
}
.reply-to-hint {
  font-size: 11px;
  color: #fb923c;
  margin-bottom: 6px;
}
.post-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.post-field {
  flex: 1;
  background: #0f172a !important;
  border-radius: 8px;
  padding: 0;
}
</style>

