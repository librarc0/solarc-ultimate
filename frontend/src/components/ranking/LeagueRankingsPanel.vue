<template>
  <div class="league-panel">
    <van-tabs v-model:active="activeTab" :sticky="stickyTabs" animated color="#1677ff">
      <van-tab title="📊 总榜" name="list">
        <div class="season-toolbar" v-if="seasons.length">
          <div class="select-row">
            <button class="select-pill" @click="showSeasonSheet = true">
              <van-icon name="flag-o" size="13" />
              <span>{{ currentSeasonLabel }}</span>
              <van-icon name="arrow-down" size="11" />
            </button>
            <button class="select-pill" @click="showSortSheet = true">
              <van-icon name="sort" size="13" />
              <span>{{ currentSortLabel }}</span>
              <van-icon name="arrow-down" size="11" />
            </button>
            <button class="select-pill" :class="{ 'filter-active': provinceFilter }" @click="showProvinceSheet = true">
              <van-icon name="location-o" size="13" />
              <span>{{ currentProvinceLabel }}</span>
              <van-icon name="arrow-down" size="11" />
            </button>
          </div>
        </div>

        <div class="toolbar">
          <van-search
            v-model="searchText"
            placeholder="搜索队伍名"
            shape="round"
            @search="doSearch"
            @clear="doSearch"
            style="flex: 1"
          />
        </div>

        <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
          <van-list
            v-model:loading="loading"
            :finished="finished"
            finished-text="— 已全部加载 —"
            @load="loadMore"
          >
            <div class="sc-table-header">
              <div class="sc-col-rank">排名</div>
              <div class="sc-col-name">队伍名称</div>
              <div class="sc-col-count">参赛</div>
              <div class="sc-col-wld">胜-负-平</div>
              <div class="sc-col-wr">胜率</div>
              <div class="sc-col-net">净胜分</div>
              <div class="sc-col-avg">均分</div>
              <div class="sc-col-score">总积分</div>
            </div>

            <div v-for="(team, index) in teams" :key="team.id" class="sc-team-block">
              <div class="sc-team-row" :class="{ expanded: expandedTeam === team.name }" @click="toggleExpand(team)">
                <div class="sc-col-rank">
                  <span v-if="index + 1 === 1" class="medal">🥇</span>
                  <span v-else-if="index + 1 === 2" class="medal">🥈</span>
                  <span v-else-if="index + 1 === 3" class="medal">🥉</span>
                  <span v-else class="rank-num">#{{ index + 1 }}</span>
                  <div class="rank-change">
                    <span v-if="team.rank_change > 0" class="up">▲{{ team.rank_change }}</span>
                    <span v-else-if="team.rank_change < 0" class="dn">▼{{ Math.abs(team.rank_change) }}</span>
                    <span v-else class="eq">—</span>
                  </div>
                </div>
                <div class="sc-col-name name-cell">
                  <div class="name-main">
                    <span class="team-name">{{ team.name }}</span>
                    <span v-if="team.province" class="location-tag">{{ formatLocation(team.province, team.city) }}</span>
                  </div>
                  <span class="detail-link" @click.stop="goDetail(team.name)">详情</span>
                </div>
                <div class="sc-col-count">{{ team.tournament_count }}</div>
                <div class="sc-col-wld">{{ team.wins }}-{{ team.losses }}-{{ team.draws }}</div>
                <div class="sc-col-wr">{{ (team.win_rate * 100).toFixed(0) }}%</div>
                <div class="sc-col-net" :class="netClass(team.net_points)">
                  {{ team.net_points > 0 ? '+' : '' }}{{ team.net_points }}
                </div>
                <div class="sc-col-avg">
                  <span class="avg-badge">{{ team.avg_score.toFixed(1) }}</span>
                </div>
                <div class="sc-col-score">
                  <span class="score-badge">{{ team.total_score.toFixed(1) }}</span>
                </div>
              </div>

              <div v-if="expandedTeam === team.name" class="sc-sub-section">
                <div v-if="detailLoading[team.name]" class="sub-loading">
                  <van-loading size="16" />
                </div>
                <template v-else-if="detailMap[team.name]">
                  <div class="sc-sub-header">
                    <div class="sub-col-name">赛事</div>
                    <div class="sub-col-level">级别</div>
                    <div class="sub-col-pool">Pool</div>
                    <div class="sub-col-rank">名次</div>
                    <div class="sub-col-wld">胜-负-平</div>
                    <div class="sub-col-wr">胜率</div>
                    <div class="sub-col-net">净胜分</div>
                    <div class="sub-col-score">积分</div>
                  </div>
                  <div v-for="rec in detailMap[team.name]?.tournament_records || []" :key="rec.id" class="sc-sub-row">
                    <div class="sub-col-name">
                      <span class="sub-tree">└</span>{{ rec.tournament_name }}
                    </div>
                    <div class="sub-col-level">
                      <span class="level-tag" :class="levelClass(rec.level)">{{ levelLabel(rec.level) }}</span>
                    </div>
                    <div class="sub-col-pool">
                      <span v-if="rec.pool && rec.pool !== 'NoPool'" class="pool-tag" :class="poolClass(rec.pool)">{{ rec.pool }}</span>
                      <span v-else class="pool-none">—</span>
                    </div>
                    <div class="sub-col-rank">{{ rec.final_rank >= 99 ? '待定' : '#' + rec.final_rank }}</div>
                    <div class="sub-col-wld">{{ rec.wins }}-{{ rec.losses }}-{{ rec.draws }}</div>
                    <div class="sub-col-wr">{{ (rec.win_rate * 100).toFixed(0) }}%</div>
                    <div class="sub-col-net" :class="netClass(rec.points_scored - rec.points_conceded)">
                      {{ rec.points_scored - rec.points_conceded > 0 ? '+' : '' }}{{ rec.points_scored - rec.points_conceded }}
                    </div>
                    <div class="sub-col-score">
                      <span class="sub-score">{{ rec.computed_score.toFixed(2) }}</span>
                    </div>
                  </div>
                </template>
                <div v-else class="sub-empty">无赛事数据</div>
              </div>
            </div>
          </van-list>
        </van-pull-refresh>
      </van-tab>

      <van-tab title="⚖️ 对比" name="compare">
        <div class="compare-area">
          <div class="compare-selects">
            <div class="select-block">
              <div class="select-label">队伍 A</div>
              <button class="select-pill full" @click="showCompareASheet = true">
                <van-icon name="flag-o" size="13" />
                <span>{{ compareSeasonALabel }}</span>
                <van-icon name="arrow-down" size="11" />
              </button>
              <van-field v-model="compareA" placeholder="输入队伍名" clearable>
                <template #button>
                  <van-button size="small" type="primary" @click="pickTeam('A')">选择</van-button>
                </template>
              </van-field>
            </div>

            <div class="vs-divider">VS</div>

            <div class="select-block">
              <div class="select-label">队伍 B</div>
              <button class="select-pill full" @click="showCompareBSheet = true">
                <van-icon name="flag-o" size="13" />
                <span>{{ compareSeasonBLabel }}</span>
                <van-icon name="arrow-down" size="11" />
              </button>
              <van-field v-model="compareB" placeholder="输入队伍名" clearable>
                <template #button>
                  <van-button size="small" type="primary" @click="pickTeam('B')">选择</van-button>
                </template>
              </van-field>
            </div>
          </div>

          <van-button
            type="primary"
            block
            style="margin: 12px 0"
            :disabled="!compareA || !compareB || !compareSeasonA || !compareSeasonB"
            :loading="compareLoading"
            @click="doCompare"
          >对比</van-button>

          <template v-if="compareData.length === 2">
            <div class="chart-title">综合能力对比</div>
            <v-chart class="radar-chart" :option="radarOption" autoresize />
            <div class="compare-table">
              <table>
                <thead>
                  <tr>
                    <th>指标</th>
                    <th :style="{ color: COMPARE_COLORS[0] }">{{ compareLegend[0] }}</th>
                    <th :style="{ color: COMPARE_COLORS[1] }">{{ compareLegend[1] }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in compareRows" :key="row.label">
                    <td>{{ row.label }}</td>
                    <td :class="row.a > row.b ? 'better-a' : ''">{{ row.aStr }}</td>
                    <td :class="row.b > row.a ? 'better-b' : ''">{{ row.bStr }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>
      </van-tab>
    </van-tabs>

    <div v-if="showFooter" class="footer-bar">
      <span class="credit">数据支持：<b>@xhs SDL Pool的栗子</b></span>
      <van-button size="mini" type="warning" icon="like-o" @click="showDonation = true">打赏支持</van-button>
    </div>

    <van-popup v-model:show="showTeamPicker" position="bottom" round style="height: 70%">
      <div class="picker-header">选择队伍 · {{ pickerSeasonLabel }}</div>
      <van-search v-model="pickerSearch" placeholder="搜索" @update:model-value="searchPickerTeams" />
      <van-list>
        <van-cell
          v-for="t in pickerTeams"
          :key="`${pickerTarget}-${t.name}`"
          :title="t.name"
          :label="`总积分 ${t.total_score.toFixed(1)}  排名 #${t.rank}`"
          @click="selectPickerTeam(t.name)"
        />
      </van-list>
    </van-popup>

    <van-action-sheet
      v-model:show="showSeasonSheet"
      title="选择赛季"
      :actions="seasonSheetActions"
      cancel-text="取消"
      close-on-click-action
      @select="onSeasonSheetSelect"
    />
    <van-action-sheet
      v-model:show="showSortSheet"
      title="选择排序方式"
      :actions="sortSheetActions"
      cancel-text="取消"
      close-on-click-action
      @select="onSortSheetSelect"
    />
    <van-action-sheet
      v-model:show="showProvinceSheet"
      title="按地区筛选"
      :actions="provinceSheetActions"
      cancel-text="取消"
      close-on-click-action
      @select="onProvinceSheetSelect"
      @cancel="onProvinceSheetCancel"
    />
    <van-action-sheet
      v-model:show="showCompareASheet"
      title="队伍 A · 选择赛季"
      :actions="compareASheetActions"
      cancel-text="取消"
      close-on-click-action
      @select="onCompareASheetSelect"
    />
    <van-action-sheet
      v-model:show="showCompareBSheet"
      title="队伍 B · 选择赛季"
      :actions="compareBSheetActions"
      cancel-text="取消"
      close-on-click-action
      @select="onCompareBSheetSelect"
    />
    <DonationDrawer v-model:show="showDonation" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { LegendComponent, RadarComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { showToast } from 'vant'
import DonationDrawer from '@/components/ranking/DonationDrawer.vue'
import {
  fetchSeasons,
  fetchTeamDetail,
  fetchTeamRankings,
  fetchTeamsCompare,
  fetchTeamsForMatch,
  type ExternalTeamDetail,
  type ExternalTeamForMatch,
  type ExternalTeamListItem,
  type SeasonOut,
} from '@/api/publicRanking'

use([RadarChart, TooltipComponent, LegendComponent, RadarComponent, CanvasRenderer])

const props = withDefaults(defineProps<{
  showFooter?: boolean
  stickyTabs?: boolean
}>(), {
  showFooter: true,
  stickyTabs: true,
})

const router = useRouter()

const activeTab = ref('list')
const seasons = ref<SeasonOut[]>([])
const currentSeasonId = ref<number | null>(null)
const searchText = ref('')
const sortBy = ref('avg_score')
const sortOptions = [
  { text: '按平均积分', value: 'avg_score' },
  { text: '按总积分', value: 'total_score' },
  { text: '按参赛次数', value: 'tournament_count' },
  { text: '按胜率', value: 'win_rate' },
]

// ─── 地区筛选 ───
const provinceFilter = ref<string | null>(null)
const PROVINCE_OPTIONS = [
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
  { label: '其他', code: 'OTHER' },
]

// 省份/城市代码转简短中文显示
const PROVINCE_CODE_MAP: Record<string, string> = {
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

function formatLocation(province: string | null, city: string | null): string {
  const code = city || province
  if (!code) return ''
  // 如果 city 和 province 一样（如 CN-SH），显示省名
  const raw = province ? (PROVINCE_CODE_MAP[province] ?? province.slice(3)) : ''
  // 若 city 是更细粒度的代码（如 CN-GD-GZ），只显示省名即可
  return raw
}

const seasonOptions = computed(() => (
  seasons.value.map((season) => ({ text: `${season.year} · ${season.name}`, value: season.id }))
))

function seasonLabelById(seasonId?: number | null) {
  if (!seasonId) return '默认赛季'
  const season = seasons.value.find((item) => item.id === seasonId)
  return season ? `${season.year} · ${season.name}` : `赛季 #${seasonId}`
}

async function loadSeasons() {
  seasons.value = await fetchSeasons()
  if (seasons.value.length) {
    const latestSeasonId = seasons.value[0]?.id
    if (!latestSeasonId) return
    currentSeasonId.value ??= latestSeasonId
    compareSeasonA.value ??= latestSeasonId
    compareSeasonB.value ??= latestSeasonId
  }
}

const teams = ref<ExternalTeamListItem[]>([])
const loading = ref(false)
const finished = ref(false)
const refreshing = ref(false)
const page = ref(1)
const PAGE_SIZE = 20

function resetListState() {
  teams.value = []
  page.value = 1
  finished.value = false
}

function resetExpandedState() {
  expandedTeam.value = null
  detailMap.value = {}
  detailLoading.value = {}
}

async function loadMore() {
  if (!currentSeasonId.value) {
    finished.value = true
    loading.value = false
    refreshing.value = false
    return
  }

  loading.value = true
  try {
    const res = await fetchTeamRankings({
      season_id: currentSeasonId.value,
      search: searchText.value || undefined,
      sort_by: sortBy.value,
      order: 'desc',
      province_filter: provinceFilter.value && provinceFilter.value !== 'OTHER' ? provinceFilter.value : undefined,
      page: page.value,
      page_size: PAGE_SIZE,
    })
    teams.value.push(...res.items)
    page.value += 1
    if (teams.value.length >= res.total) finished.value = true
  } catch {
    finished.value = true
    showToast('加载排行榜失败')
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

function doSearch() {
  resetListState()
  resetExpandedState()
  void loadMore()
}

async function onRefresh() {
  resetListState()
  resetExpandedState()
  await loadMore()
}

function onSeasonChange() {
  doSearch()
}

const expandedTeam = ref<string | null>(null)
const detailMap = ref<Record<string, ExternalTeamDetail>>({})
const detailLoading = ref<Record<string, boolean>>({})

async function toggleExpand(team: ExternalTeamListItem) {
  if (expandedTeam.value === team.name) {
    expandedTeam.value = null
    return
  }

  expandedTeam.value = team.name
  if (detailMap.value[team.name]) return
  detailLoading.value[team.name] = true
  try {
    const detail = await fetchTeamDetail(team.name, currentSeasonId.value || undefined)
    detailMap.value[team.name] = detail
  } catch {
    showToast('加载赛事数据失败')
    expandedTeam.value = null
  } finally {
    detailLoading.value[team.name] = false
  }
}

function goDetail(name: string) {
  router.push({
    name: 'public-team-detail',
    params: { teamName: name },
    query: currentSeasonId.value ? { season_id: String(currentSeasonId.value) } : undefined,
  })
}

function netClass(n: number) {
  if (n > 0) return 'net-positive'
  if (n < 0) return 'net-negative'
  return ''
}

function levelLabel(level: string) {
  const map: Record<string, string> = { National: '全国', Provincial: '省级', Local: '本地' }
  return map[level] ?? level
}

function levelClass(level: string) {
  const map: Record<string, string> = { National: 'level-national', Provincial: 'level-provincial', Local: 'level-local' }
  return map[level] ?? ''
}

function poolClass(pool: string) {
  const map: Record<string, string> = { A: 'pool-a', B: 'pool-b', C: 'pool-c' }
  return map[pool] ?? ''
}

const compareA = ref('')
const compareB = ref('')
const compareSeasonA = ref<number | null>(null)
const compareSeasonB = ref<number | null>(null)
const compareLoading = ref(false)
const compareData = ref<ExternalTeamDetail[]>([])
const showTeamPicker = ref(false)
const pickerSearch = ref('')
const pickerTarget = ref<'A' | 'B'>('A')
const pickerTeams = ref<ExternalTeamForMatch[]>([])
const showDonation = ref(false)

// Action-sheet 选择器（替代 van-dropdown-menu，解决移动端 z-index 问题）
const showSeasonSheet = ref(false)
const showSortSheet = ref(false)
const showProvinceSheet = ref(false)
const showCompareASheet = ref(false)
const showCompareBSheet = ref(false)

const seasonSheetActions = computed(() =>
  seasons.value.map(s => ({
    name: `${s.year} · ${s.name}`,
    id: s.id,
    color: currentSeasonId.value === s.id ? '#1677ff' : undefined,
  }))
)
const sortSheetActions = sortOptions.map(o => ({ name: o.text, key: o.value }))
const provinceSheetActions = computed(() =>
  PROVINCE_OPTIONS.map(p => ({
    name: p.label,
    code: p.code,
    color: provinceFilter.value === p.code ? '#1677ff' : undefined,
  }))
)
const currentSeasonLabel = computed(() => {
  const s = seasons.value.find(s => s.id === currentSeasonId.value)
  return s ? `${s.year} · ${s.name}` : '选择赛季'
})
const currentSortLabel = computed(() => sortOptions.find(o => o.value === sortBy.value)?.text ?? '按平均积分')
const currentProvinceLabel = computed(() => {
  if (!provinceFilter.value) return '全部地区'
  return PROVINCE_OPTIONS.find(p => p.code === provinceFilter.value)?.label ?? provinceFilter.value
})
const compareSeasonALabel = computed(() => {
  const s = seasons.value.find(s => s.id === compareSeasonA.value)
  return s ? `${s.year} · ${s.name}` : '选择赛季'
})
const compareSeasonBLabel = computed(() => {
  const s = seasons.value.find(s => s.id === compareSeasonB.value)
  return s ? `${s.year} · ${s.name}` : '选择赛季'
})

// 对比专用 sheet actions（按照各自选中赛季高亮，避免 color:undefined 导致文字不可见）
const compareASheetActions = computed(() =>
  seasons.value.map(s => ({
    name: `${s.year} · ${s.name}`,
    id: s.id,
    color: s.id === compareSeasonA.value ? '#1677ff' : '#323233',
  }))
)
const compareBSheetActions = computed(() =>
  seasons.value.map(s => ({
    name: `${s.year} · ${s.name}`,
    id: s.id,
    color: s.id === compareSeasonB.value ? '#1677ff' : '#323233',
  }))
)

function onSeasonSheetSelect(action: any) {
  currentSeasonId.value = action.id
  onSeasonChange()
}
function onSortSheetSelect(action: any) {
  sortBy.value = action.key
  doSearch()
}
function onProvinceSheetSelect(action: any) {
  provinceFilter.value = action.code
  doSearch()
}
function onProvinceSheetCancel() {
  // 取消不清空筛选
}
function onCompareASheetSelect(action: any) {
  compareSeasonA.value = action.id
  onCompareSeasonChange('A')
}
function onCompareBSheetSelect(action: any) {
  compareSeasonB.value = action.id
  onCompareSeasonChange('B')
}

const pickerSeasonId = computed(() => (
  pickerTarget.value === 'A' ? compareSeasonA.value : compareSeasonB.value
))

const pickerSeasonLabel = computed(() => seasonLabelById(pickerSeasonId.value))

function onCompareSeasonChange(target: 'A' | 'B') {
  compareData.value = []
  if (target === 'A') {
    compareA.value = ''
  } else {
    compareB.value = ''
  }
}

async function pickTeam(target: 'A' | 'B') {
  pickerTarget.value = target
  pickerSearch.value = ''
  const seasonId = target === 'A' ? compareSeasonA.value : compareSeasonB.value
  if (!seasonId) {
    showToast('请先选择赛季')
    return
  }
  pickerTeams.value = await fetchTeamsForMatch(undefined, seasonId)
  showTeamPicker.value = true
}

async function searchPickerTeams(val: string) {
  if (!pickerSeasonId.value) return
  pickerTeams.value = await fetchTeamsForMatch(val || undefined, pickerSeasonId.value)
}

function selectPickerTeam(name: string) {
  compareData.value = []
  if (pickerTarget.value === 'A') compareA.value = name
  else compareB.value = name
  showTeamPicker.value = false
}

async function doCompare() {
  if (!compareA.value || !compareB.value || !compareSeasonA.value || !compareSeasonB.value) return
  compareLoading.value = true
  try {
    compareData.value = await fetchTeamsCompare(
      [compareA.value, compareB.value],
      [compareSeasonA.value, compareSeasonB.value],
    )
  } catch {
    showToast('获取对比数据失败')
  } finally {
    compareLoading.value = false
  }
}

const COMPARE_COLORS = ['#5470c6', '#ee6666']

const compareLegend = computed(() => compareData.value.map((item) => `${item.name} (${seasonLabelById(item.season_id)})`))

const radarOption = computed(() => {
  if (compareData.value.length !== 2) return {}
  const a = compareData.value[0]
  const b = compareData.value[1]
  if (!a || !b) return {}
  const avgScoredA = a.total_games > 0 ? a.points_scored / a.total_games : 0
  const avgScoredB = b.total_games > 0 ? b.points_scored / b.total_games : 0
  const ratioA = a.points_conceded > 0 ? a.points_scored / a.points_conceded : (a.points_scored > 0 ? 10 : 1)
  const ratioB = b.points_conceded > 0 ? b.points_scored / b.points_conceded : (b.points_scored > 0 ? 10 : 1)
  const legend = compareLegend.value
  return {
    color: COMPARE_COLORS,
    tooltip: { trigger: 'item' },
    legend: { data: legend, bottom: 0, textStyle: { color: '#555' } },
    radar: {
      indicator: [
        { name: '综合积分', max: Math.max(a.total_score, b.total_score) * 1.15 || 1 },
        { name: '赛季均分', max: Math.max(a.avg_score, b.avg_score) * 1.2 || 1 },
        { name: '竞争力 %', max: 100 },
        { name: '场均得分', max: Math.max(avgScoredA, avgScoredB) * 1.2 || 1 },
        { name: '得失分比', max: Math.max(ratioA, ratioB) * 1.2 || 1 },
        { name: '赛事经验', max: Math.max(a.tournament_count, b.tournament_count) * 1.2 || 1 },
      ],
      radius: '65%',
      nameGap: 6,
    },
    series: [{
      type: 'radar',
      data: [
        {
          name: legend[0],
          value: [a.total_score, a.avg_score, a.win_rate * 100, avgScoredA, ratioA, a.tournament_count],
          lineStyle: { color: COMPARE_COLORS[0] },
          itemStyle: { color: COMPARE_COLORS[0] },
          areaStyle: { color: COMPARE_COLORS[0], opacity: 0.12 },
        },
        {
          name: legend[1],
          value: [b.total_score, b.avg_score, b.win_rate * 100, avgScoredB, ratioB, b.tournament_count],
          lineStyle: { color: COMPARE_COLORS[1] },
          itemStyle: { color: COMPARE_COLORS[1] },
          areaStyle: { color: COMPARE_COLORS[1], opacity: 0.12 },
        },
      ],
    }],
  }
})

const compareRows = computed(() => {
  if (compareData.value.length !== 2) return []
  const a = compareData.value[0]
  const b = compareData.value[1]
  if (!a || !b) return []
  const avgScoredA = a.total_games > 0 ? a.points_scored / a.total_games : 0
  const avgScoredB = b.total_games > 0 ? b.points_scored / b.total_games : 0
  const avgConcededA = a.total_games > 0 ? a.points_conceded / a.total_games : 0
  const avgConcededB = b.total_games > 0 ? b.points_conceded / b.total_games : 0
  const netPpmA = a.total_games > 0 ? a.net_points / a.total_games : 0
  const netPpmB = b.total_games > 0 ? b.net_points / b.total_games : 0
  const ratioA = a.points_conceded > 0 ? a.points_scored / a.points_conceded : (a.points_scored > 0 ? 10 : 1)
  const ratioB = b.points_conceded > 0 ? b.points_scored / b.points_conceded : (b.points_scored > 0 ? 10 : 1)
  return [
    { label: '排名', a: -a.rank, b: -b.rank, aStr: `#${a.rank}`, bStr: `#${b.rank}` },
    { label: '综合积分', a: a.total_score, b: b.total_score, aStr: a.total_score.toFixed(2), bStr: b.total_score.toFixed(2) },
    { label: '赛季均分', a: a.avg_score, b: b.avg_score, aStr: a.avg_score.toFixed(2), bStr: b.avg_score.toFixed(2) },
    { label: '战绩 (胜/平/负)', a: a.wins, b: b.wins, aStr: `${a.wins}/${a.draws}/${a.losses}`, bStr: `${b.wins}/${b.draws}/${b.losses}` },
    { label: '竞争力 (胜率)', a: a.win_rate, b: b.win_rate, aStr: `${(a.win_rate * 100).toFixed(1)}%`, bStr: `${(b.win_rate * 100).toFixed(1)}%` },
    { label: '场均得分', a: avgScoredA, b: avgScoredB, aStr: avgScoredA.toFixed(1), bStr: avgScoredB.toFixed(1) },
    { label: '场均失分', a: -avgConcededA, b: -avgConcededB, aStr: avgConcededA.toFixed(1), bStr: avgConcededB.toFixed(1) },
    { label: '净胜分/场', a: netPpmA, b: netPpmB, aStr: netPpmA.toFixed(2), bStr: netPpmB.toFixed(2) },
    { label: '得失分比', a: ratioA, b: ratioB, aStr: ratioA.toFixed(2), bStr: ratioB.toFixed(2) },
    { label: '净胜分计', a: a.net_points, b: b.net_points, aStr: String(a.net_points), bStr: String(b.net_points) },
    { label: '参赛次数', a: a.tournament_count, b: b.tournament_count, aStr: String(a.tournament_count), bStr: String(b.tournament_count) },
  ]
})

onMounted(async () => {
  await loadSeasons()
  doSearch()
})
</script>

<style scoped>
.league-panel {
  background: #f0f2f5;
  padding-bottom: 56px;
}

.season-toolbar {
  background: #fff;
  padding: 0;
}

.select-row {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
}

.select-pill {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  padding: 6px 8px;
  background: #f0f5ff;
  border: 1px solid #c5d8ff;
  border-radius: 20px;
  font-size: 12px;
  color: #1677ff;
  font-weight: 600;
  cursor: pointer;
  min-width: 0;
  overflow: hidden;
}

.select-pill span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  flex: 1;
}

.select-pill.full {
  width: 100%;
  margin-bottom: 8px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  background: #fff;
  padding: 0 4px;
}

.sc-table-header {
  display: flex;
  align-items: center;
  background: #1a2332;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  padding: 8px 12px;
  letter-spacing: 0.2px;
}

.sc-team-block {
  border-bottom: 2px solid #e8edf3;
}

.sc-team-row {
  display: flex;
  align-items: center;
  background: #fff;
  padding: 10px 12px;
  cursor: pointer;
  transition: background 0.15s;
  border-left: 3px solid transparent;
}

.sc-team-row:active,
.sc-team-row.expanded {
  background: #f0f5ff;
  border-left-color: #1677ff;
}

.sc-sub-section {
  background: #f7f9fc;
  overflow-x: auto;
}

.sc-sub-header {
  display: flex;
  align-items: center;
  background: #eef1f5;
  color: #666;
  font-size: 10px;
  font-weight: 700;
  padding: 6px 12px 6px 24px;
  letter-spacing: 0.2px;
}

.sc-sub-row {
  display: flex;
  align-items: center;
  padding: 7px 12px 7px 24px;
  border-bottom: 1px solid #eef1f5;
  background: #fff;
  font-size: 12px;
  color: #555;
}

.sc-sub-row:last-child {
  border-bottom: none;
}

.sub-loading {
  padding: 16px;
  text-align: center;
}

.sub-empty {
  padding: 12px 16px;
  font-size: 12px;
  color: #aaa;
  text-align: center;
}

.sc-col-rank { width: 44px; flex-shrink: 0; text-align: center; }
.sc-col-name { flex: 1; min-width: 0; overflow: hidden; }
.sc-col-count { width: 28px; flex-shrink: 0; text-align: center; font-size: 11px; color: #333; }
.sc-col-wld { width: 52px; flex-shrink: 0; text-align: center; font-size: 11px; color: #333; }
.sc-col-wr { width: 36px; flex-shrink: 0; text-align: center; font-size: 11px; color: #333; }
.sc-col-net { width: 36px; flex-shrink: 0; text-align: center; font-size: 11px; color: #333; }
.sc-col-avg { width: 42px; flex-shrink: 0; text-align: center; }
.sc-col-score { width: 48px; flex-shrink: 0; text-align: center; }

/* 深色表头内所有列强制白字 */
.sc-table-header .sc-col-count,
.sc-table-header .sc-col-wld,
.sc-table-header .sc-col-wr,
.sc-table-header .sc-col-net,
.sc-table-header .sc-col-rank,
.sc-table-header .sc-col-name,
.sc-table-header .sc-col-avg,
.sc-table-header .sc-col-score { color: #fff; }

.sub-col-name { flex: 1; min-width: 120px; color: #444; }
.sub-col-level { width: 44px; flex-shrink: 0; text-align: center; }
.sub-col-pool { width: 36px; flex-shrink: 0; text-align: center; }
.sub-col-rank { width: 36px; flex-shrink: 0; text-align: center; }
.sub-col-wld { width: 56px; flex-shrink: 0; text-align: center; }
.sub-col-wr { width: 40px; flex-shrink: 0; text-align: center; }
.sub-col-net { width: 40px; flex-shrink: 0; text-align: center; }
.sub-col-score { width: 52px; flex-shrink: 0; text-align: center; }

.medal { font-size: 18px; line-height: 1; }
.rank-num { font-size: 13px; font-weight: 700; color: #666; }
.rank-change { font-size: 10px; margin-top: 1px; line-height: 1; }
.rank-change .up { color: #f5222d; font-weight: 700; }
.rank-change .dn { color: #52c41a; font-weight: 700; }
.rank-change .eq { color: #ccc; }

.name-cell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  min-width: 0;
  overflow: hidden;
}

.name-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
  gap: 2px;
}

.team-name {
  font-size: 13px;
  font-weight: 600;
  color: #1a1a1a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.location-tag {
  font-size: 10px;
  color: #8c8c8c;
  background: #f5f5f5;
  padding: 0 4px;
  border-radius: 3px;
  display: inline-block;
  width: fit-content;
}

.detail-link {
  font-size: 11px;
  color: #1677ff;
  flex-shrink: 0;
  padding: 2px 6px;
  border: 1px solid #1677ff22;
  border-radius: 4px;
  background: #f0f5ff;
}

.score-badge {
  display: inline-block;
  background: #1677ff;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  padding: 3px 4px;
  border-radius: 6px;
  min-width: 38px;
  text-align: center;
}

.avg-badge {
  display: inline-block;
  background: #52c41a;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 4px;
  border-radius: 6px;
  min-width: 34px;
  text-align: center;
}

.filter-active {
  background: #fff2e8 !important;
  border-color: #fa8c16 !important;
  color: #fa8c16 !important;
}

.sub-score {
  color: #1677ff;
  font-weight: 700;
  font-size: 12px;
}

.net-positive { color: #52c41a; font-weight: 700; }
.net-negative { color: #f5222d; font-weight: 700; }

.level-tag {
  display: inline-block;
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 3px;
  border: 1px solid currentColor;
}

.level-national { color: #d48806; background: #fffbe6; }
.level-provincial { color: #096dd9; background: #e6f7ff; }
.level-local { color: #389e0d; background: #f6ffed; }

.pool-tag {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 3px;
}

.pool-a { background: #fff1f0; color: #cf1322; }
.pool-b { background: #fff7e6; color: #d46b08; }
.pool-c { background: #e6fffb; color: #08979c; }
.pool-none { color: #ccc; font-size: 11px; }
.sub-tree { color: #aaa; margin-right: 4px; }

.compare-area { padding: 12px 16px; }

.compare-selects {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.select-block {
  background: #fff;
  border-radius: 12px;
  padding: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}

.select-label {
  font-size: 12px;
  color: #888;
  margin-bottom: 8px;
}

.vs-divider {
  text-align: center;
  font-size: 16px;
  font-weight: 700;
  color: #1677ff;
}

.chart-title {
  text-align: center;
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 16px 0 8px;
}

.radar-chart {
  height: 320px;
  width: 100%;
}

.compare-table {
  overflow-x: auto;
  margin-top: 12px;
}

.compare-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.compare-table th,
.compare-table td {
  padding: 8px 12px;
  text-align: center;
  border-bottom: 1px solid #eee;
  color: #1a1a1a;
}

.compare-table th {
  background: #f5f7fa;
  font-weight: 600;
  color: #555;
}

.compare-table .better-a {
  color: #5470c6;
  font-weight: 700;
}

.compare-table .better-b {
  color: #ee6666;
  font-weight: 700;
}

.picker-header {
  padding: 16px;
  font-size: 16px;
  font-weight: 600;
  text-align: center;
  border-bottom: 1px solid #eee;
}

.footer-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #fff;
  border-top: 1px solid #eee;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  z-index: 100;
}

.credit { font-size: 12px; color: #888; }
.credit b { color: #1677ff; }
</style>