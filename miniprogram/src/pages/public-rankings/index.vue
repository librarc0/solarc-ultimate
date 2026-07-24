<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onPullDownRefresh, onReachBottom } from '@dcloudio/uni-app'
import api from '@/api/request'
import type { ExternalTeamDetail, ExternalTeamForMatch, ExternalTeamListItem, SeasonOut, TeamRankingListResponse } from '@/api/types'
import StateBlock from '@/components/StateBlock.vue'

type PublicTab = 'list' | 'compare'
type CompareTarget = 'A' | 'B'

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

const tab = ref<PublicTab>('list')
const seasons = ref<SeasonOut[]>([])
const selectedSeasonId = ref<number | null>(null)
const search = ref('')
const sortBy = ref('avg_score')
const provinceFilter = ref<string | null>(null)
const teams = ref<ExternalTeamListItem[]>([])
const page = ref(1)
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
const seasonIndex = computed(() => Math.max(0, seasons.value.findIndex(s => s.id === selectedSeasonId.value)))
const sortNames = computed(() => sortOptions.map(item => item.label))
const sortIndex = computed(() => Math.max(0, sortOptions.findIndex(item => item.value === sortBy.value)))
const provinceNames = computed(() => provinceOptions.map(item => item.label))
const provinceIndex = computed(() => Math.max(0, provinceOptions.findIndex(item => item.code === provinceFilter.value)))
const hasMore = computed(() => tab.value === 'list' && teams.value.length < total.value)
const compareSeasonAIndex = computed(() => Math.max(0, seasons.value.findIndex(s => s.id === compareSeasonA.value)))
const compareSeasonBIndex = computed(() => Math.max(0, seasons.value.findIndex(s => s.id === compareSeasonB.value)))
const pickerSeasonId = computed(() => pickerTarget.value === 'A' ? compareSeasonA.value : compareSeasonB.value)
const pickerTitle = computed(() => `选择队伍 ${pickerTarget.value} · ${seasonLabel(pickerSeasonId.value)}`)
const compareReady = computed(() => !!compareA.value && !!compareB.value && !!compareSeasonA.value && !!compareSeasonB.value)

async function loadSeasons() {
  seasons.value = await api.get<SeasonOut[]>('/public/seasons')
  const active = seasons.value.find(s => s.is_active) ?? seasons.value[0]
  selectedSeasonId.value ??= active?.id ?? null
  compareSeasonA.value ??= active?.id ?? null
  compareSeasonB.value ??= active?.id ?? null
}

function resetList() {
  page.value = 1
  total.value = 0
  teams.value = []
  expandedTeam.value = ''
  detailMap.value = {}
  detailLoading.value = {}
}

async function loadRankings(reset = false) {
  if (reset) resetList()
  if (!selectedSeasonId.value) return
  if (page.value === 1) loading.value = true
  else loadingMore.value = true
  error.value = ''
  try {
    const res = await api.get<TeamRankingListResponse>('/public/team-rankings', {
      params: {
        page: page.value,
        page_size: PAGE_SIZE,
        search: search.value.trim() || undefined,
        season_id: selectedSeasonId.value,
        sort_by: sortBy.value,
        order: 'desc',
        province_filter: provinceFilter.value || undefined,
      },
    })
    total.value = res.total
    teams.value = page.value === 1 ? res.items : teams.value.concat(res.items)
  } catch (e) {
    error.value = (e as Error).message || '联盟排行榜加载失败'
  } finally {
    loading.value = false
    loadingMore.value = false
    uni.stopPullDownRefresh()
  }
}

async function refreshAll() {
  try {
    await loadSeasons()
    if (tab.value === 'list') await loadRankings(true)
  } catch (e) {
    error.value = (e as Error).message || '联盟排行榜加载失败'
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

function switchTab(next: PublicTab) {
  tab.value = next
  if (next === 'list' && teams.value.length === 0) loadRankings(true)
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

function betterClass(row: { a: number; b: number }, side: CompareTarget) {
  if (row.a === row.b) return ''
  return side === 'A' ? (row.a > row.b ? 'better-a' : '') : (row.b > row.a ? 'better-b' : '')
}

onMounted(refreshAll)
onPullDownRefresh(refreshAll)
onReachBottom(() => {
  if (loading.value || loadingMore.value || !hasMore.value) return
  page.value += 1
  loadRankings()
})
</script>

<template>
  <view class="page">
    <view class="header">
      <text class="title">联盟排行榜</text>
      <text class="subtitle">无需登录 · 公开队伍数据</text>
    </view>

    <view class="seg-tabs">
      <button class="seg-btn" :class="{ active: tab === 'list' }" @tap="switchTab('list')">总榜</button>
      <button class="seg-btn" :class="{ active: tab === 'compare' }" @tap="switchTab('compare')">对比</button>
    </view>

    <template v-if="tab === 'list'">
      <view class="toolbar">
        <view class="filter-grid">
          <picker :range="seasonNames" :value="seasonIndex" @change="onSeasonChange">
            <view class="picker-inner">{{ seasonNames[seasonIndex] || '选择赛季' }}</view>
          </picker>
          <picker :range="sortNames" :value="sortIndex" @change="onSortChange">
            <view class="picker-inner">{{ sortNames[sortIndex] || '排序' }}</view>
          </picker>
          <picker :range="provinceNames" :value="provinceIndex" @change="onProvinceChange">
            <view class="picker-inner" :class="{ active: provinceFilter }">{{ provinceNames[provinceIndex] || '地区' }}</view>
          </picker>
        </view>
        <view class="search-row">
          <input v-model="search" class="search-input" placeholder="搜索队伍名" placeholder-class="placeholder" @confirm="onSearch" />
          <button class="search-btn" @tap="onSearch">搜索</button>
        </view>
      </view>

      <StateBlock v-if="loading" title="正在加载联盟排行榜" loading />
      <StateBlock v-else-if="error" title="加载失败" :desc="error" action-text="重试" @retry="refreshAll" />
      <StateBlock v-else-if="teams.length === 0" title="暂无队伍" desc="换个关键词、赛季或地区试试" />

      <view v-else class="card-list">
        <view v-for="team in teams" :key="team.id" class="league-card" @tap="toggleExpand(team)">
          <view class="card-top">
            <text class="rank-pill">#{{ team.rank }}</text>
            <view class="card-name-wrap">
              <view class="name-line">
                <text class="card-name">{{ team.name }}</text>
                <text v-if="team.province" class="location-tag">{{ formatLocation(team.province, team.city) }}</text>
              </view>
              <text class="card-sub">排名变化 {{ formatRankChange(team.rank_change) || '—' }}</text>
            </view>
            <text class="main-score">{{ team.total_score.toFixed(1) }}</text>
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
    </template>

    <view v-else class="compare-page">
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

      <view v-if="compareData.length === 2" class="compare-table-card">
        <view class="compare-legend">
          <text class="legend-a">{{ compareData[0].name }}（{{ seasonLabel(compareData[0].season_id) }}）</text>
          <text class="legend-b">{{ compareData[1].name }}（{{ seasonLabel(compareData[1].season_id) }}）</text>
        </view>
        <view v-for="row in compareRows" :key="row.label" class="compare-row">
          <text class="metric">{{ row.label }}</text>
          <text class="metric-val" :class="betterClass(row, 'A')">{{ row.aStr }}</text>
          <text class="metric-val" :class="betterClass(row, 'B')">{{ row.bStr }}</text>
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
  font-size: 42rpx;
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

.seg-btn,
.search-btn,
.compare-btn,
.close-btn {
  height: 58rpx;
  line-height: 58rpx;
  padding: 0;
  border-radius: 14rpx;
  font-size: 24rpx;
  font-weight: 900;
}

.seg-btn {
  background: transparent;
  color: #94a3b8;
}

.seg-btn.active {
  background: #0ea5e9;
  color: #fff;
}

.seg-btn::after,
.search-btn::after,
.compare-btn::after,
.close-btn::after {
  border: none;
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
.league-card,
.compare-card,
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
.close-btn {
  width: 108rpx;
  height: 66rpx;
  line-height: 66rpx;
  background: #f59e0b;
  color: #111827;
}

.card-list {
  margin: 0 28rpx;
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.league-card,
.compare-card,
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
  background: #2563eb;
  color: #fff;
  text-align: center;
  font-size: 22rpx;
  font-weight: 900;
  flex-shrink: 0;
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

.location-tag {
  padding: 2rpx 8rpx;
  border-radius: 8rpx;
  background: rgba(245, 158, 11, 0.12);
  color: #fbbf24;
  font-size: 20rpx;
  flex-shrink: 0;
}

.main-score {
  color: #f59e0b;
  font-size: 30rpx;
  font-weight: 900;
  flex-shrink: 0;
}

.mini-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10rpx;
  margin-top: 16rpx;
}

.mini {
  padding: 12rpx 6rpx;
  border-radius: 14rpx;
  background: rgba(30, 41, 59, 0.72);
  text-align: center;
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

.compare-title {
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
