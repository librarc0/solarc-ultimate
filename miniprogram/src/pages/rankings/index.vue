<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onPullDownRefresh, onReachBottom } from '@dcloudio/uni-app'
import api from '@/api/request'
import type {
  ExternalTeamDetail,
  ExternalTeamForMatch,
  ExternalTeamListItem,
  RankingItem,
  RankingResponse,
  SeasonOut,
  TeamRankingListResponse,
} from '@/api/types'
import FullWebLink from '@/components/FullWebLink.vue'
import StateBlock from '@/components/StateBlock.vue'

type RankingMode = 'team' | 'league'
type LeagueTab = 'list' | 'compare'
type TeamTab = 'composite' | 'progress' | 'chemistry' | 'stats' | 'match_info'
type CompareTarget = 'A' | 'B'

interface ChemistryItem {
  rank: number
  player_a_id: number
  player_b_id: number
  player_a_name: string | null
  player_b_name: string | null
  player_a_jersey: number | null
  player_b_jersey: number | null
  chemistry_score: number
  co_matches: number
  co_wins: number
  combo_count: number
}

interface ChemistryResponse {
  items: ChemistryItem[]
  page: number
  page_size: number
}

const PAGE_SIZE = 20
const sortOptions = [
  { label: '均分', value: 'avg_score' },
  { label: '总积分', value: 'total_score' },
  { label: '参赛', value: 'tournament_count' },
  { label: '胜率', value: 'win_rate' },
]
const provinceOptions = [
  { label: '全部地区', code: null },
  { label: '上海', code: 'CN-SH' },
  { label: '北京', code: 'CN-BJ' },
  { label: '广东', code: 'CN-GD' },
  { label: '浙江', code: 'CN-ZJ' },
  { label: '江苏', code: 'CN-JS' },
  { label: '四川', code: 'CN-SC' },
  { label: '湖北', code: 'CN-HB' },
  { label: '湖南', code: 'CN-HN' },
  { label: '福建', code: 'CN-FJ' },
  { label: '山东', code: 'CN-SD' },
  { label: '陕西', code: 'CN-SN' },
  { label: '河南', code: 'CN-HA' },
  { label: '辽宁', code: 'CN-LN' },
  { label: '天津', code: 'CN-TJ' },
  { label: '重庆', code: 'CN-CQ' },
  { label: '云南', code: 'CN-YN' },
  { label: '广西', code: 'CN-GX' },
  { label: '安徽', code: 'CN-AH' },
  { label: '江西', code: 'CN-JX' },
]
const provinceNameMap: Record<string, string> = {
  'CN-SH': '上海',
  'CN-BJ': '北京',
  'CN-GD': '广东',
  'CN-ZJ': '浙江',
  'CN-JS': '江苏',
  'CN-SC': '四川',
  'CN-HB': '湖北',
  'CN-HN': '湖南',
  'CN-FJ': '福建',
  'CN-SD': '山东',
  'CN-SN': '陕西',
  'CN-HA': '河南',
  'CN-LN': '辽宁',
  'CN-TJ': '天津',
  'CN-CQ': '重庆',
  'CN-YN': '云南',
  'CN-GX': '广西',
  'CN-AH': '安徽',
  'CN-JX': '江西',
}

const teamTabs = [
  { label: '综合', value: 'composite' },
  { label: '进步', value: 'progress' },
  { label: '默契', value: 'chemistry' },
  { label: '数据', value: 'stats' },
  { label: '比赛', value: 'match_info' },
] as const
const statsSorts = [
  { label: '得分', value: 'goals' },
  { label: '助攻', value: 'assists' },
  { label: '防守', value: 'defense' },
  { label: '失误', value: 'turnovers' },
] as const
const matchSorts = [
  { label: '净胜', value: 'net_wins' },
  { label: '正负值', value: 'plus_minus' },
] as const

const seasons = ref<SeasonOut[]>([])
const selectedSeasonId = ref<number | null>(null)
const search = ref('')
const leagueItems = ref<ExternalTeamListItem[]>([])
const teamItems = ref<RankingItem[]>([])
const chemItems = ref<ChemistryItem[]>([])
const mode = ref<RankingMode>('team')
const leagueTab = ref<LeagueTab>('list')
const teamTab = ref<TeamTab>('composite')
const statsSort = ref<(typeof statsSorts)[number]['value']>('goals')
const matchInfoSort = ref<(typeof matchSorts)[number]['value']>('net_wins')
const sortBy = ref('avg_score')
const provinceFilter = ref<string | null>(null)
const leaguePage = ref(1)
const total = ref(0)
const loading = ref(true)
const loadingMore = ref(false)
const error = ref('')
const expandedTeam = ref('')
const detailMap = ref<Record<string, ExternalTeamDetail>>({})
const detailLoading = ref<Record<string, boolean>>({})

const compareA = ref('')
const compareB = ref('')
const compareSeasonA = ref<number | null>(null)
const compareSeasonB = ref<number | null>(null)
const compareLoading = ref(false)
const compareError = ref('')
const compareData = ref<ExternalTeamDetail[]>([])
const pickerTarget = ref<CompareTarget>('A')
const pickerSearch = ref('')
const pickerTeams = ref<ExternalTeamForMatch[]>([])
const pickerLoading = ref(false)
const showPicker = ref(false)

const seasonNames = computed(() => seasons.value.map(s => `${s.year} · ${s.name}`))
const selectedSeasonIndex = computed(() => Math.max(0, seasons.value.findIndex(s => s.id === selectedSeasonId.value)))
const sortNames = computed(() => sortOptions.map(item => item.label))
const selectedSortIndex = computed(() => Math.max(0, sortOptions.findIndex(item => item.value === sortBy.value)))
const provinceNames = computed(() => provinceOptions.map(item => item.label))
const selectedProvinceIndex = computed(() => Math.max(0, provinceOptions.findIndex(item => item.code === provinceFilter.value)))
const hasMore = computed(() => mode.value === 'league' && leagueTab.value === 'list' && leagueItems.value.length < total.value)
const compareSeasonAIndex = computed(() => Math.max(0, seasons.value.findIndex(s => s.id === compareSeasonA.value)))
const compareSeasonBIndex = computed(() => Math.max(0, seasons.value.findIndex(s => s.id === compareSeasonB.value)))
const pickerSeasonId = computed(() => pickerTarget.value === 'A' ? compareSeasonA.value : compareSeasonB.value)
const pickerTitle = computed(() => `选择队伍 ${pickerTarget.value} · ${seasonLabel(pickerSeasonId.value)}`)
const compareReady = computed(() => !!compareA.value && !!compareB.value && !!compareSeasonA.value && !!compareSeasonB.value)
const isTeamEmpty = computed(() => teamTab.value === 'chemistry' ? chemItems.value.length === 0 : teamItems.value.length === 0)

async function loadSeasons() {
  seasons.value = await api.get<SeasonOut[]>('/public/seasons')
  const active = seasons.value.find(s => s.is_active) ?? seasons.value[0]
  selectedSeasonId.value ??= active?.id ?? null
  compareSeasonA.value ??= active?.id ?? null
  compareSeasonB.value ??= active?.id ?? null
}

function teamSortBy() {
  if (teamTab.value === 'stats') return statsSort.value
  if (teamTab.value === 'match_info') return matchInfoSort.value
  return teamTab.value
}

async function loadTeamRankings() {
  if (teamTab.value === 'chemistry') {
    const res = await api.get<ChemistryResponse>('/rankings/chemistry', { params: { page: 1, page_size: 30 } })
    chemItems.value = res.items
    total.value = res.items.length
    return
  }
  const res = await api.get<RankingResponse>('/rankings', {
    params: { page: 1, page_size: 100, sort_by: teamSortBy() },
  })
  teamItems.value = res.items
  total.value = res.items.length
}

function resetLeagueList() {
  leaguePage.value = 1
  total.value = 0
  leagueItems.value = []
  expandedTeam.value = ''
  detailMap.value = {}
  detailLoading.value = {}
}

async function loadLeagueRankings(reset = false) {
  if (reset) resetLeagueList()
  if (!selectedSeasonId.value) {
    leagueItems.value = []
    total.value = 0
    return
  }
  const res = await api.get<TeamRankingListResponse>('/public/team-rankings', {
    params: {
      page: leaguePage.value,
      page_size: PAGE_SIZE,
      search: search.value.trim() || undefined,
      season_id: selectedSeasonId.value,
      sort_by: sortBy.value,
      order: 'desc',
      province_filter: provinceFilter.value || undefined,
    },
  })
  total.value = res.total
  leagueItems.value = leaguePage.value === 1 ? res.items : leagueItems.value.concat(res.items)
}

async function loadRankings(reset = false) {
  if (reset) {
    teamItems.value = []
    chemItems.value = []
    if (mode.value === 'league') resetLeagueList()
  }
  if (mode.value === 'league' && leagueTab.value !== 'list') return
  if (mode.value === 'league' && leaguePage.value > 1) loadingMore.value = true
  else loading.value = true
  error.value = ''
  try {
    if (mode.value === 'team') await loadTeamRankings()
    else await loadLeagueRankings(false)
  } catch (e) {
    error.value = (e as Error).message || '排行榜加载失败'
  } finally {
    loading.value = false
    loadingMore.value = false
    uni.stopPullDownRefresh()
  }
}

async function refreshAll() {
  try {
    if (mode.value === 'league') await loadSeasons()
    await loadRankings(true)
  } catch (e) {
    error.value = (e as Error).message || '排行榜加载失败'
    loading.value = false
    uni.stopPullDownRefresh()
  }
}

function onSeasonChange(e: { detail: { value: number } }) {
  selectedSeasonId.value = seasons.value[Number(e.detail.value)]?.id ?? null
  loadRankings(true)
}

function onSortChange(e: { detail: { value: number } }) {
  sortBy.value = sortOptions[Number(e.detail.value)]?.value ?? 'avg_score'
  loadRankings(true)
}

function onProvinceChange(e: { detail: { value: number } }) {
  provinceFilter.value = provinceOptions[Number(e.detail.value)]?.code ?? null
  loadRankings(true)
}

function onSearch() {
  loadRankings(true)
}

async function switchMode(next: RankingMode) {
  if (mode.value === next) return
  mode.value = next
  if (next === 'league' && seasons.value.length === 0) await loadSeasons()
  await loadRankings(true)
}

async function switchTeamTab(next: TeamTab) {
  if (teamTab.value === next) return
  teamTab.value = next
  await loadRankings(true)
}

async function switchLeagueTab(next: LeagueTab) {
  if (leagueTab.value === next) return
  leagueTab.value = next
  error.value = ''
  if (next === 'list' && leagueItems.value.length === 0) await loadRankings(true)
}

function changeStatsSort(next: (typeof statsSorts)[number]['value']) {
  if (statsSort.value === next) return
  statsSort.value = next
  loadRankings(true)
}

function changeMatchSort(next: (typeof matchSorts)[number]['value']) {
  if (matchInfoSort.value === next) return
  matchInfoSort.value = next
  loadRankings(true)
}

async function toggleExpand(team: ExternalTeamListItem) {
  if (expandedTeam.value === team.name) {
    expandedTeam.value = ''
    return
  }
  expandedTeam.value = team.name
  if (detailMap.value[team.name]) return
  detailLoading.value = { ...detailLoading.value, [team.name]: true }
  try {
    const detail = await api.get<ExternalTeamDetail>(`/public/team-rankings/${encodeURIComponent(team.name)}`, {
      params: selectedSeasonId.value ? { season_id: selectedSeasonId.value } : {},
    })
    detailMap.value = { ...detailMap.value, [team.name]: detail }
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '赛事数据加载失败', icon: 'none' })
    expandedTeam.value = ''
  } finally {
    detailLoading.value = { ...detailLoading.value, [team.name]: false }
  }
}

function goDetail(team: ExternalTeamListItem) {
  const query = `team=${encodeURIComponent(team.name)}&season_id=${encodeURIComponent(String(selectedSeasonId.value ?? ''))}`
  uni.navigateTo({ url: `/pages/rankings/detail?${query}` })
}

function seasonLabel(seasonId?: number | null) {
  const season = seasons.value.find(item => item.id === seasonId)
  return season ? `${season.year} · ${season.name}` : '选择赛季'
}

function formatLocation(province: string | null, city: string | null) {
  const code = city || province
  if (!code) return ''
  return province ? (provinceNameMap[province] ?? province.replace('CN-', '')) : code
}

function formatPercent(rate: number) {
  const normalized = rate > 1 ? rate : rate * 100
  return `${normalized.toFixed(0)}%`
}

function formatRankChange(change?: number | null) {
  if (change == null) return ''
  if (change > 0) return `↑${change}`
  if (change < 0) return `↓${Math.abs(change)}`
  return '—'
}

function rankChangeClass(change?: number | null) {
  if (!change) return 'same'
  return change > 0 ? 'up' : 'down'
}

function signed(value: number) {
  return value > 0 ? `+${value}` : String(value)
}

function valueTone(value: number) {
  if (value > 0) return 'positive'
  if (value < 0) return 'negative'
  return ''
}

function levelLabel(level: string) {
  const map: Record<string, string> = { National: '全国', Provincial: '省级', Local: '本地' }
  return map[level] ?? level
}

function rankLabel(rank: number) {
  return rank >= 99 ? '待定' : `#${rank}`
}

function genderMark(player: RankingItem) {
  if (player.gender === 'M') return '♂'
  if (player.gender === 'F') return '♀'
  return ''
}

function playerName(player: RankingItem) {
  return player.display_name || `队员 #${player.player_id}`
}

function netWins(player: RankingItem) {
  return player.total_wins * 2 - player.total_matches
}

function mainScore(player: RankingItem) {
  if (teamTab.value === 'progress') {
    return player.progress_speed > 0 ? (player.progress_speed * 100).toFixed(1) : '场次不足'
  }
  return `${player.composite_score.toFixed(1)}`
}

function statMetricValue(player: RankingItem, key: string) {
  if (key === 'goals') return player.total_goals
  if (key === 'assists') return player.total_assists
  if (key === 'defense') return player.total_defenses
  return player.total_turnovers ?? 0
}

function resetCompareResult() {
  compareData.value = []
  compareError.value = ''
}

function onCompareSeasonChange(target: CompareTarget, e: { detail: { value: number } }) {
  const seasonId = seasons.value[Number(e.detail.value)]?.id ?? null
  if (target === 'A') {
    compareSeasonA.value = seasonId
    compareA.value = ''
  } else {
    compareSeasonB.value = seasonId
    compareB.value = ''
  }
  resetCompareResult()
}

async function openTeamPicker(target: CompareTarget) {
  pickerTarget.value = target
  pickerSearch.value = ''
  pickerTeams.value = []
  if (!pickerSeasonId.value) {
    uni.showToast({ title: '请先选择赛季', icon: 'none' })
    return
  }
  showPicker.value = true
  await loadPickerTeams()
}

async function loadPickerTeams() {
  if (!pickerSeasonId.value) return
  pickerLoading.value = true
  try {
    pickerTeams.value = await api.get<ExternalTeamForMatch[]>('/public/team-rankings/for-match', {
      params: { search: pickerSearch.value.trim() || undefined, season_id: pickerSeasonId.value },
    })
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '队伍加载失败', icon: 'none' })
  } finally {
    pickerLoading.value = false
  }
}

function selectPickerTeam(team: ExternalTeamForMatch) {
  if (pickerTarget.value === 'A') compareA.value = team.name
  else compareB.value = team.name
  showPicker.value = false
  resetCompareResult()
}

async function doCompare() {
  if (!compareReady.value) return
  compareLoading.value = true
  compareError.value = ''
  try {
    compareData.value = await api.get<ExternalTeamDetail[]>('/public/team-rankings/compare', {
      params: {
        teams: `${compareA.value},${compareB.value}`,
        season_ids: `${compareSeasonA.value ?? ''},${compareSeasonB.value ?? ''}`,
      },
    })
  } catch (e) {
    compareError.value = (e as Error).message || '获取对比数据失败'
  } finally {
    compareLoading.value = false
  }
}

function avgScored(team: ExternalTeamDetail) {
  return team.total_games > 0 ? team.points_scored / team.total_games : 0
}

function avgConceded(team: ExternalTeamDetail) {
  return team.total_games > 0 ? team.points_conceded / team.total_games : 0
}

function pointRatio(team: ExternalTeamDetail) {
  if (team.points_conceded > 0) return team.points_scored / team.points_conceded
  return team.points_scored > 0 ? 10 : 1
}

const compareRows = computed(() => {
  if (compareData.value.length !== 2) return []
  const a = compareData.value[0]
  const b = compareData.value[1]
  if (!a || !b) return []
  const netPerA = a.total_games > 0 ? a.net_points / a.total_games : 0
  const netPerB = b.total_games > 0 ? b.net_points / b.total_games : 0
  return [
    { label: '排名', a: -a.rank, b: -b.rank, aStr: `#${a.rank}`, bStr: `#${b.rank}` },
    { label: '综合积分', a: a.total_score, b: b.total_score, aStr: a.total_score.toFixed(2), bStr: b.total_score.toFixed(2) },
    { label: '赛季均分', a: a.avg_score, b: b.avg_score, aStr: a.avg_score.toFixed(2), bStr: b.avg_score.toFixed(2) },
    { label: '战绩', a: a.wins, b: b.wins, aStr: `${a.wins}/${a.draws}/${a.losses}`, bStr: `${b.wins}/${b.draws}/${b.losses}` },
    { label: '胜率', a: a.win_rate, b: b.win_rate, aStr: formatPercent(a.win_rate), bStr: formatPercent(b.win_rate) },
    { label: '场均得分', a: avgScored(a), b: avgScored(b), aStr: avgScored(a).toFixed(1), bStr: avgScored(b).toFixed(1) },
    { label: '场均失分', a: -avgConceded(a), b: -avgConceded(b), aStr: avgConceded(a).toFixed(1), bStr: avgConceded(b).toFixed(1) },
    { label: '净胜分/场', a: netPerA, b: netPerB, aStr: netPerA.toFixed(2), bStr: netPerB.toFixed(2) },
    { label: '得失分比', a: pointRatio(a), b: pointRatio(b), aStr: pointRatio(a).toFixed(2), bStr: pointRatio(b).toFixed(2) },
    { label: '净胜分计', a: a.net_points, b: b.net_points, aStr: String(a.net_points), bStr: String(b.net_points) },
    { label: '参赛次数', a: a.tournament_count, b: b.tournament_count, aStr: String(a.tournament_count), bStr: String(b.tournament_count) },
  ]
})

const compareBars = computed(() => {
  if (compareData.value.length !== 2) return []
  const a = compareData.value[0]
  const b = compareData.value[1]
  if (!a || !b) return []
  return [
    { label: '综合积分', a: a.total_score, b: b.total_score },
    { label: '赛季均分', a: a.avg_score, b: b.avg_score },
    { label: '竞争力', a: a.win_rate > 1 ? a.win_rate : a.win_rate * 100, b: b.win_rate > 1 ? b.win_rate : b.win_rate * 100 },
    { label: '场均得分', a: avgScored(a), b: avgScored(b) },
    { label: '得失分比', a: pointRatio(a), b: pointRatio(b) },
    { label: '赛事经验', a: a.tournament_count, b: b.tournament_count },
  ].map(row => {
    const max = Math.max(row.a, row.b, 1)
    return {
      ...row,
      aWidth: `${Math.max(6, (row.a / max) * 100)}%`,
      bWidth: `${Math.max(6, (row.b / max) * 100)}%`,
      aStr: row.a.toFixed(row.a >= 10 ? 0 : 1),
      bStr: row.b.toFixed(row.b >= 10 ? 0 : 1),
    }
  })
})

function betterClass(row: { a: number; b: number }, side: CompareTarget) {
  if (row.a === row.b) return ''
  return side === 'A' ? (row.a > row.b ? 'better-a' : '') : (row.b > row.a ? 'better-b' : '')
}

onMounted(refreshAll)
onPullDownRefresh(refreshAll)
onReachBottom(() => {
  if (loading.value || loadingMore.value || !hasMore.value) return
  leaguePage.value += 1
  loadRankings()
})
</script>

<template>
  <view class="page">
    <view class="header">
      <text class="title">排行榜</text>
      <text class="subtitle">{{ mode === 'team' ? '队内排行与数据统计' : '公开联盟队伍数据 · 筛选与对比' }}</text>
    </view>

    <FullWebLink path="/public/rankings" desc="录入比赛、管理队伍和修改资料，请访问网页版完整功能。" />

    <view class="seg-tabs">
      <button class="seg-btn" :class="{ active: mode === 'team' }" @tap="switchMode('team')">队伍排行榜</button>
      <button class="seg-btn" :class="{ active: mode === 'league' }" @tap="switchMode('league')">联盟排行榜</button>
    </view>

    <view v-if="mode === 'team'" class="sub-tabs scroll-row">
      <button
        v-for="tab in teamTabs"
        :key="tab.value"
        class="chip"
        :class="{ active: teamTab === tab.value }"
        @tap="switchTeamTab(tab.value)"
      >{{ tab.label }}</button>
    </view>

    <view v-if="mode === 'team' && teamTab === 'stats'" class="sub-tabs compact">
      <button
        v-for="item in statsSorts"
        :key="item.value"
        class="chip small"
        :class="{ active: statsSort === item.value }"
        @tap="changeStatsSort(item.value)"
      >{{ item.label }}</button>
    </view>

    <view v-if="mode === 'team' && teamTab === 'match_info'" class="sub-tabs compact">
      <button
        v-for="item in matchSorts"
        :key="item.value"
        class="chip small"
        :class="{ active: matchInfoSort === item.value }"
        @tap="changeMatchSort(item.value)"
      >{{ item.label }}</button>
    </view>

    <view v-if="mode === 'league'" class="seg-tabs slim">
      <button class="seg-btn" :class="{ active: leagueTab === 'list' }" @tap="switchLeagueTab('list')">总榜</button>
      <button class="seg-btn" :class="{ active: leagueTab === 'compare' }" @tap="switchLeagueTab('compare')">对比</button>
    </view>

    <template v-if="mode === 'league' && leagueTab === 'list'">
      <view class="toolbar">
        <view class="filter-grid">
          <picker :range="seasonNames" :value="selectedSeasonIndex" @change="onSeasonChange">
            <view class="picker-inner">{{ seasonNames[selectedSeasonIndex] || '选择赛季' }}</view>
          </picker>
          <picker :range="sortNames" :value="selectedSortIndex" @change="onSortChange">
            <view class="picker-inner">{{ sortNames[selectedSortIndex] || '排序' }}</view>
          </picker>
          <picker :range="provinceNames" :value="selectedProvinceIndex" @change="onProvinceChange">
            <view class="picker-inner" :class="{ active: provinceFilter }">{{ provinceNames[selectedProvinceIndex] || '地区' }}</view>
          </picker>
        </view>
        <view class="search-row">
          <input v-model="search" class="search-input" placeholder="搜索队伍名" placeholder-class="placeholder" @confirm="onSearch" />
          <button class="search-btn" @tap="onSearch">搜索</button>
        </view>
      </view>
    </template>

    <StateBlock v-if="loading && leagueTab !== 'compare'" title="正在加载排行榜" loading />
    <StateBlock v-else-if="error && leagueTab !== 'compare'" title="加载失败" :desc="error" action-text="重试" @retry="refreshAll" />
    <StateBlock v-else-if="mode === 'team' && isTeamEmpty" title="暂无队伍排行" desc="完成比赛后会显示排名和统计" />
    <StateBlock v-else-if="mode === 'league' && leagueTab === 'list' && leagueItems.length === 0" title="暂无队伍" desc="换个关键词、赛季或地区试试" />

    <view v-else-if="mode === 'team'" class="card-list">
      <template v-if="teamTab === 'chemistry'">
        <view v-for="item in chemItems" :key="`${item.player_a_id}-${item.player_b_id}`" class="rank-card">
          <view class="card-top">
            <text class="rank-pill">#{{ item.rank }}</text>
            <view class="card-name-wrap">
              <text class="card-name">{{ item.player_a_name || '?' }} & {{ item.player_b_name || '?' }}</text>
              <text class="card-sub">共场 {{ item.co_matches }} · 共赢 {{ item.co_wins }} · 连线 {{ item.combo_count }}</text>
            </view>
            <text class="main-score green">{{ item.chemistry_score.toFixed(2) }}</text>
          </view>
        </view>
      </template>

      <template v-else>
        <view v-for="player in teamItems" :key="player.player_id" class="rank-card">
          <view class="card-top">
            <text class="rank-pill">#{{ player.rank }}</text>
            <view class="card-name-wrap">
              <view class="name-line">
                <text v-if="genderMark(player)" class="gender">{{ genderMark(player) }}</text>
                <text class="card-name">{{ playerName(player) }}</text>
                <text v-if="player.jersey_number != null" class="jersey">#{{ player.jersey_number }}</text>
              </view>
              <text class="card-sub">
                {{ player.total_matches }}场 {{ player.total_wins }}胜 · {{ formatRankChange(player.rank_change) }}
              </text>
            </view>
            <text v-if="teamTab === 'composite' || teamTab === 'progress'" class="main-score">{{ mainScore(player) }}</text>
          </view>

          <view v-if="teamTab === 'composite' || teamTab === 'progress'" class="mini-grid">
            <view class="mini"><text>{{ player.total_goals }}</text><text>得分</text></view>
            <view class="mini"><text>{{ player.total_assists }}</text><text>助攻</text></view>
            <view class="mini"><text>{{ player.total_defenses }}</text><text>防守</text></view>
            <view class="mini"><text>{{ player.attendance_rate?.toFixed(0) ?? 0 }}%</text><text>出勤</text></view>
          </view>

          <view v-else-if="teamTab === 'stats'" class="mini-grid">
            <view
              v-for="item in statsSorts"
              :key="item.value"
              class="mini"
              :class="{ active: statsSort === item.value }"
            >
              <text>{{ statMetricValue(player, item.value) }}</text>
              <text>{{ item.label }}</text>
            </view>
          </view>

          <view v-else class="mini-grid five">
            <view class="mini"><text>{{ player.total_matches }}</text><text>场次</text></view>
            <view class="mini"><text>{{ player.total_wins }}</text><text>胜</text></view>
            <view class="mini"><text>{{ player.total_matches - player.total_wins }}</text><text>负</text></view>
            <view class="mini" :class="[matchInfoSort === 'net_wins' ? 'active' : '', valueTone(netWins(player))]"><text>{{ signed(netWins(player)) }}</text><text>净胜</text></view>
            <view class="mini" :class="[matchInfoSort === 'plus_minus' ? 'active' : '', valueTone(player.total_plus_minus)]"><text>{{ signed(player.total_plus_minus) }}</text><text>正负</text></view>
          </view>
        </view>
      </template>
    </view>

    <view v-else-if="mode === 'league' && leagueTab === 'list'" class="card-list">
      <view v-for="team in leagueItems" :key="team.id" class="league-card" @tap="toggleExpand(team)">
        <view class="card-top">
          <text class="rank-pill blue">#{{ team.rank }}</text>
          <view class="card-name-wrap">
            <view class="name-line">
              <text class="card-name">{{ team.name }}</text>
              <text v-if="team.province" class="location-tag">{{ formatLocation(team.province, team.city) }}</text>
            </view>
            <text class="card-sub">排名变化 {{ formatRankChange(team.rank_change) || '—' }}</text>
          </view>
          <text class="main-score amber">{{ team.total_score.toFixed(1) }}</text>
        </view>
        <view class="mini-grid">
          <view class="mini"><text>{{ team.tournament_count }}</text><text>参赛</text></view>
          <view class="mini"><text>{{ team.wins }}-{{ team.losses }}-{{ team.draws }}</text><text>胜负平</text></view>
          <view class="mini"><text>{{ formatPercent(team.win_rate) }}</text><text>胜率</text></view>
          <view class="mini" :class="valueTone(team.net_points)"><text>{{ signed(team.net_points) }}</text><text>净胜</text></view>
        </view>
        <view class="league-extra">
          <text>均分 {{ team.avg_score.toFixed(1) }}</text>
          <text>点击展开赛事记录</text>
        </view>

        <view v-if="expandedTeam === team.name" class="sub-section">
          <view class="sub-actions">
            <text>赛事记录</text>
            <button class="detail-btn" @tap.stop="goDetail(team)">详情页</button>
          </view>
          <StateBlock v-if="detailLoading[team.name]" title="正在加载赛事记录" loading />
          <view v-else-if="detailMap[team.name]?.tournament_records?.length">
            <view v-for="record in detailMap[team.name].tournament_records" :key="record.id" class="record-row">
              <view>
                <text class="record-name">{{ record.tournament_name }}</text>
                <text class="record-meta">{{ record.month }} · {{ levelLabel(record.level) }} · Pool {{ record.pool && record.pool !== 'NoPool' ? record.pool : '—' }}</text>
                <text class="record-meta">{{ record.wins }}-{{ record.losses }}-{{ record.draws }} · 胜率 {{ formatPercent(record.win_rate) }} · 净胜 {{ signed(record.points_scored - record.points_conceded) }}</text>
              </view>
              <view class="record-side">
                <text class="record-rank">{{ rankLabel(record.final_rank) }}</text>
                <text class="record-score">{{ record.computed_score.toFixed(2) }}</text>
              </view>
            </view>
          </view>
          <text v-else class="sub-empty">无赛事数据</text>
        </view>
      </view>
      <text class="load-hint">{{ loadingMore ? '加载中...' : hasMore ? '上拉加载更多' : '已到底' }}</text>
      <view class="credit-note">感谢 xhs：sdlpool的栗子 提供的数据</view>
    </view>

    <view v-else-if="mode === 'league' && leagueTab === 'compare'" class="compare-page">
      <view class="compare-card">
        <text class="compare-title">队伍 A</text>
        <picker :range="seasonNames" :value="compareSeasonAIndex" @change="onCompareSeasonChange('A', $event)">
          <view class="picker-inner">{{ seasonLabel(compareSeasonA) }}</view>
        </picker>
        <view class="search-row">
          <input v-model="compareA" class="search-input" placeholder="输入或选择队伍名" placeholder-class="placeholder" @input="resetCompareResult" />
          <button class="search-btn" @tap="openTeamPicker('A')">选择</button>
        </view>
      </view>

      <view class="vs">VS</view>

      <view class="compare-card">
        <text class="compare-title">队伍 B</text>
        <picker :range="seasonNames" :value="compareSeasonBIndex" @change="onCompareSeasonChange('B', $event)">
          <view class="picker-inner">{{ seasonLabel(compareSeasonB) }}</view>
        </picker>
        <view class="search-row">
          <input v-model="compareB" class="search-input" placeholder="输入或选择队伍名" placeholder-class="placeholder" @input="resetCompareResult" />
          <button class="search-btn" @tap="openTeamPicker('B')">选择</button>
        </view>
      </view>

      <button class="compare-btn" :disabled="!compareReady || compareLoading" @tap="doCompare">
        {{ compareLoading ? '对比中...' : '开始对比' }}
      </button>
      <StateBlock v-if="compareError" title="对比失败" :desc="compareError" action-text="重试" @retry="doCompare" />

      <view v-if="compareData.length === 2" class="compare-result">
        <view class="compare-legend">
          <text class="legend-a">{{ compareData[0].name }}（{{ seasonLabel(compareData[0].season_id) }}）</text>
          <text class="legend-b">{{ compareData[1].name }}（{{ seasonLabel(compareData[1].season_id) }}）</text>
        </view>

        <view class="bar-card">
          <text class="section-title">综合能力对比</text>
          <view v-for="bar in compareBars" :key="bar.label" class="bar-row">
            <text class="bar-label">{{ bar.label }}</text>
            <view class="bar-line"><view class="bar-fill a" :style="{ width: bar.aWidth }" /><text>{{ bar.aStr }}</text></view>
            <view class="bar-line"><view class="bar-fill b" :style="{ width: bar.bWidth }" /><text>{{ bar.bStr }}</text></view>
          </view>
        </view>

        <view class="compare-table-card">
          <view v-for="row in compareRows" :key="row.label" class="compare-row">
            <text class="metric">{{ row.label }}</text>
            <text class="metric-val" :class="betterClass(row, 'A')">{{ row.aStr }}</text>
            <text class="metric-val" :class="betterClass(row, 'B')">{{ row.bStr }}</text>
          </view>
        </view>
      </view>

      <view class="credit-note">感谢 xhs：sdlpool的栗子 提供的数据</view>

      <view v-if="showPicker" class="picker-mask" @tap="showPicker = false">
        <view class="picker-panel" @tap.stop>
          <view class="picker-head">
            <text>{{ pickerTitle }}</text>
            <button class="close-btn" @tap="showPicker = false">关闭</button>
          </view>
          <view class="search-row picker-search">
            <input v-model="pickerSearch" class="search-input" placeholder="搜索队伍" placeholder-class="placeholder" @confirm="loadPickerTeams" />
            <button class="search-btn" @tap="loadPickerTeams">搜索</button>
          </view>
          <StateBlock v-if="pickerLoading" title="正在加载队伍" loading />
          <scroll-view v-else scroll-y class="picker-list">
            <view v-for="team in pickerTeams" :key="team.name" class="picker-team" @tap="selectPickerTeam(team)">
              <text class="picker-team-name">{{ team.name }}</text>
              <text class="picker-team-meta">#{{ team.rank }} · {{ team.total_score.toFixed(1) }}分</text>
            </view>
            <text v-if="pickerTeams.length === 0" class="sub-empty">暂无队伍</text>
          </scroll-view>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 28rpx 0 48rpx;
  background: linear-gradient(180deg, #08111f 0%, #111827 100%);
}

.header {
  padding: 18rpx 28rpx;
}

.title {
  display: block;
  color: #f8fafc;
  font-size: 40rpx;
  font-weight: 900;
}

.subtitle {
  display: block;
  margin-top: 6rpx;
  color: #94a3b8;
  font-size: 23rpx;
}

.seg-tabs {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10rpx;
  margin: 0 28rpx 16rpx;
  padding: 8rpx;
  border-radius: 18rpx;
  background: rgba(15, 23, 42, 0.76);
  border: 1rpx solid rgba(148, 163, 184, 0.16);
}

.seg-tabs.slim {
  margin-top: -4rpx;
}

.seg-btn,
.chip {
  height: 58rpx;
  line-height: 58rpx;
  padding: 0;
  border-radius: 14rpx;
  background: transparent;
  color: #94a3b8;
  font-size: 24rpx;
  font-weight: 800;
}

.seg-btn.active,
.chip.active {
  background: #0ea5e9;
  color: #fff;
}

.seg-btn::after,
.chip::after,
.search-btn::after,
.compare-btn::after,
.detail-btn::after,
.close-btn::after {
  border: none;
}

.sub-tabs {
  margin: 0 28rpx 16rpx;
  display: flex;
  gap: 10rpx;
}

.scroll-row {
  overflow-x: auto;
  white-space: nowrap;
}

.chip {
  min-width: 112rpx;
  padding: 0 18rpx;
  border: 1rpx solid rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.76);
}

.chip.small {
  min-width: 96rpx;
  height: 52rpx;
  line-height: 52rpx;
  font-size: 22rpx;
}

.toolbar,
.compare-page {
  margin: 0 28rpx 20rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.filter-grid {
  display: grid;
  grid-template-columns: 1.25fr 0.85fr 0.9fr;
  gap: 10rpx;
}

.picker-inner,
.search-input,
.rank-card,
.league-card,
.compare-card,
.bar-card,
.compare-table-card {
  border: 1rpx solid rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.82);
}

.picker-inner {
  height: 62rpx;
  line-height: 62rpx;
  padding: 0 18rpx;
  border-radius: 14rpx;
  color: #e2e8f0;
  font-size: 23rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.picker-inner.active {
  color: #fbbf24;
  border-color: rgba(245, 158, 11, 0.32);
}

.search-row {
  display: flex;
  gap: 10rpx;
}

.search-input {
  flex: 1;
  height: 66rpx;
  border-radius: 14rpx;
  padding: 0 18rpx;
  color: #f8fafc;
  font-size: 24rpx;
}

.placeholder {
  color: #64748b;
}

.search-btn,
.compare-btn,
.detail-btn,
.close-btn {
  height: 66rpx;
  line-height: 66rpx;
  padding: 0;
  border-radius: 14rpx;
  color: #111827;
  background: #f59e0b;
  font-size: 24rpx;
  font-weight: 900;
}

.search-btn {
  width: 108rpx;
}

.card-list {
  margin: 0 28rpx;
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.rank-card,
.league-card,
.compare-card,
.bar-card,
.compare-table-card {
  padding: 20rpx;
  border-radius: 20rpx;
}

.card-top {
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.rank-pill {
  width: 62rpx;
  height: 52rpx;
  line-height: 52rpx;
  border-radius: 14rpx;
  background: #0ea5e9;
  color: #fff;
  text-align: center;
  font-size: 22rpx;
  font-weight: 900;
  flex-shrink: 0;
}

.rank-pill.blue {
  background: #2563eb;
}

.card-name-wrap {
  flex: 1;
  min-width: 0;
}

.name-line {
  display: flex;
  align-items: center;
  gap: 8rpx;
  min-width: 0;
}

.card-name {
  color: #f8fafc;
  font-size: 28rpx;
  font-weight: 900;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-sub {
  display: block;
  margin-top: 6rpx;
  color: #94a3b8;
  font-size: 21rpx;
}

.gender {
  color: #38bdf8;
  font-size: 23rpx;
  font-weight: 900;
}

.jersey,
.location-tag {
  padding: 2rpx 8rpx;
  border-radius: 8rpx;
  background: rgba(245, 158, 11, 0.12);
  color: #fbbf24;
  font-size: 20rpx;
  flex-shrink: 0;
}

.main-score {
  color: #fbbf24;
  font-size: 30rpx;
  font-weight: 900;
  flex-shrink: 0;
}

.main-score.green {
  color: #22c55e;
}

.main-score.amber {
  color: #f59e0b;
}

.mini-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10rpx;
  margin-top: 16rpx;
}

.mini-grid.five {
  grid-template-columns: repeat(5, 1fr);
}

.mini {
  padding: 12rpx 6rpx;
  border-radius: 14rpx;
  background: rgba(30, 41, 59, 0.72);
  text-align: center;
}

.mini.active {
  background: rgba(14, 165, 233, 0.22);
  border: 1rpx solid rgba(14, 165, 233, 0.34);
}

.mini text:first-child {
  display: block;
  color: #e0f2fe;
  font-size: 24rpx;
  font-weight: 900;
}

.mini text:last-child {
  display: block;
  margin-top: 4rpx;
  color: #94a3b8;
  font-size: 19rpx;
}

.positive text:first-child {
  color: #22c55e;
}

.negative text:first-child {
  color: #ef4444;
}

.league-extra {
  display: flex;
  justify-content: space-between;
  margin-top: 14rpx;
  color: #64748b;
  font-size: 21rpx;
}

.sub-section {
  margin-top: 18rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid rgba(148, 163, 184, 0.16);
}

.sub-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10rpx;
  color: #e2e8f0;
  font-size: 24rpx;
  font-weight: 900;
}

.detail-btn,
.close-btn {
  width: 112rpx;
  height: 52rpx;
  line-height: 52rpx;
  border-radius: 12rpx;
  font-size: 21rpx;
}

.record-row {
  display: flex;
  justify-content: space-between;
  gap: 16rpx;
  padding: 14rpx 0;
  border-top: 1rpx solid rgba(148, 163, 184, 0.12);
}

.record-name {
  display: block;
  color: #e5e7eb;
  font-size: 24rpx;
  font-weight: 800;
}

.record-meta,
.sub-empty {
  display: block;
  margin-top: 6rpx;
  color: #94a3b8;
  font-size: 21rpx;
}

.record-side {
  flex-shrink: 0;
  text-align: right;
}

.record-rank {
  display: block;
  color: #cbd5e1;
  font-size: 22rpx;
}

.record-score {
  display: block;
  margin-top: 8rpx;
  color: #38bdf8;
  font-size: 25rpx;
  font-weight: 900;
}

.load-hint,
.credit-note {
  display: block;
  text-align: center;
  color: #64748b;
  font-size: 22rpx;
}

.load-hint {
  padding: 18rpx 0 6rpx;
}

.credit-note {
  margin: 6rpx 0 12rpx;
  padding: 18rpx 20rpx;
  border-radius: 16rpx;
  background: rgba(245, 158, 11, 0.08);
  border: 1rpx solid rgba(245, 158, 11, 0.16);
  color: #fbbf24;
}

.compare-title,
.section-title {
  display: block;
  margin-bottom: 14rpx;
  color: #f8fafc;
  font-size: 27rpx;
  font-weight: 900;
}

.vs {
  text-align: center;
  color: #38bdf8;
  font-size: 30rpx;
  font-weight: 900;
}

.compare-btn {
  width: 100%;
  background: #0ea5e9;
  color: #fff;
}

.compare-btn[disabled] {
  opacity: 0.5;
}

.compare-legend {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  margin-bottom: 14rpx;
  color: #cbd5e1;
  font-size: 22rpx;
}

.legend-a {
  color: #93c5fd;
}

.legend-b {
  color: #fca5a5;
}

.bar-row {
  margin-top: 16rpx;
}

.bar-label {
  display: block;
  color: #cbd5e1;
  font-size: 22rpx;
  margin-bottom: 8rpx;
}

.bar-line {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin: 8rpx 0;
  color: #cbd5e1;
  font-size: 21rpx;
}

.bar-fill {
  height: 16rpx;
  border-radius: 999rpx;
}

.bar-fill.a {
  background: #3b82f6;
}

.bar-fill.b {
  background: #ef4444;
}

.compare-row {
  display: grid;
  grid-template-columns: 1.2fr 1fr 1fr;
  gap: 12rpx;
  padding: 14rpx 0;
  border-top: 1rpx solid rgba(148, 163, 184, 0.12);
  color: #cbd5e1;
  font-size: 22rpx;
}

.compare-row:first-child {
  border-top: none;
}

.metric {
  color: #94a3b8;
}

.metric-val {
  text-align: right;
}

.better-a {
  color: #60a5fa;
  font-weight: 900;
}

.better-b {
  color: #f87171;
  font-weight: 900;
}

.picker-mask {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  z-index: 20;
  background: rgba(2, 6, 23, 0.68);
  display: flex;
  align-items: flex-end;
}

.picker-panel {
  width: 100%;
  max-height: 76vh;
  padding: 24rpx 28rpx 42rpx;
  border-radius: 28rpx 28rpx 0 0;
  background: #0f172a;
  box-sizing: border-box;
}

.picker-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #f8fafc;
  font-size: 27rpx;
  font-weight: 900;
}

.picker-search {
  margin: 20rpx 0;
}

.picker-list {
  max-height: 52vh;
}

.picker-team {
  padding: 18rpx 0;
  border-top: 1rpx solid rgba(148, 163, 184, 0.16);
}

.picker-team-name {
  display: block;
  color: #f8fafc;
  font-size: 26rpx;
  font-weight: 800;
}

.picker-team-meta {
  display: block;
  margin-top: 6rpx;
  color: #94a3b8;
  font-size: 21rpx;
}
</style>
