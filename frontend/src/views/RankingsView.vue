<template>
  <div class="rankings-page" @touchstart.passive="onPageTouchStart" @touchend.passive="onPageTouchEnd">
    <van-nav-bar :title="topMode === 'league' ? '飞盘联赛排行榜' : '战力排行榜'">
      <template #right>
        <div class="mode-switch">
          <span
            class="mode-btn"
            :class="{ active: topMode === 'internal' }"
            @click="topMode = 'internal'"
          >队内榜</span>
          <span
            class="mode-btn"
            :class="{ active: topMode === 'league' }"
            @click="topMode = 'league'"
          >🌐 联盟</span>
        </div>
      </template>
    </van-nav-bar>

    <!-- 联盟排行榜面板 -->
    <template v-if="topMode === 'league'">
      <LeagueRankingsPanel :show-footer="false" :sticky-tabs="true" />
    </template>

    <template v-else>
    <!-- 6 个子 tab -->
    <van-tabs v-model:active="activeTab" sticky swipeable @change="onTabChange">
      <van-tab name="composite">
        <template #title>
          <span class="tab-tip-trigger"
            @mouseenter="openTabTip('composite', $event)"
            @mouseleave="closeTabTip"
            @touchstart.passive="scheduleTabTip('composite', $event)"
            @touchend.passive="clearTabTipTimer"
            @touchmove.passive="clearTabTipTimer"
          >综合战力榜</span>
        </template>
      </van-tab>
      <van-tab name="progress">
        <template #title>
          <span class="tab-tip-trigger"
            @mouseenter="openTabTip('progress', $event)"
            @mouseleave="closeTabTip"
            @touchstart.passive="scheduleTabTip('progress', $event)"
            @touchend.passive="clearTabTipTimer"
            @touchmove.passive="clearTabTipTimer"
          >进步榜</span>
        </template>
      </van-tab>
      <van-tab name="chemistry">
        <template #title>
          <span class="tab-tip-trigger"
            @mouseenter="openTabTip('chemistry', $event)"
            @mouseleave="closeTabTip"
            @touchstart.passive="scheduleTabTip('chemistry', $event)"
            @touchend.passive="clearTabTipTimer"
            @touchmove.passive="clearTabTipTimer"
          >默契榜</span>
        </template>
      </van-tab>
      <van-tab name="stats">
        <template #title>
          <span class="tab-tip-trigger"
            @mouseenter="openTabTip('stats', $event)"
            @mouseleave="closeTabTip"
            @touchstart.passive="scheduleTabTip('stats', $event)"
            @touchend.passive="clearTabTipTimer"
            @touchmove.passive="clearTabTipTimer"
          >数据统计</span>
        </template>
      </van-tab>
      <van-tab name="match_info">
        <template #title>
          <span class="tab-tip-trigger"
            @mouseenter="openTabTip('match_info', $event)"
            @mouseleave="closeTabTip"
            @touchstart.passive="scheduleTabTip('match_info', $event)"
            @touchend.passive="clearTabTipTimer"
            @touchmove.passive="clearTabTipTimer"
          >比赛信息</span>
        </template>
      </van-tab>
    </van-tabs>

    <!-- 超管未选队伍时的引导提示 -->
    <van-empty
      v-if="auth.isSuperAdmin && !auth.viewingTeamId"
      image="search"
      description="请先在首页选择要查看的队伍"
    />

    <!-- 综合 / 战力 / 稳定 榜（带排名、变化箭头的卡片列表） -->
    <van-pull-refresh
      v-else-if="activeTab === 'composite' || activeTab === 'progress'"
      v-model="refreshing"
      @refresh="onRefresh"
    >
      <van-list
        v-model:loading="loading"
        :finished="finished"
        :finished-text="!auth.isAdmin && rankings.length >= 16 ? '仅显示前 16 名，完整榜单请联系管理员' : '没有更多了'"
        @load="onLoad"
      >
        <van-cell v-for="item in rankings" :key="item.player_id">
          <template #title>
            <div class="rank-title-row">
              <span class="rank-num">{{ item.rank }}</span>
              <span class="rank-change" :class="rankChangeClass(item)">{{ rankChangeIcon(item) }}</span>
              <span class="gender gender--m" v-if="item.gender === 'M'">♂</span>
              <span class="gender gender--f" v-else-if="item.gender === 'F'">♀</span>
              <span>{{ item.display_name || '—' }}</span>
              <span v-if="item.jersey_number != null" class="jersey-tag">#{{ item.jersey_number }}</span>
            </div>
          </template>
          <template #label>{{ rankLabel(item) }}</template>
          <template #value>
            <div class="rank-value">
              <span class="rank-main">{{ rankMain(item) }}</span>
              <van-tag v-if="item.is_new" type="warning">新人</van-tag>
            </div>
          </template>
        </van-cell>
      </van-list>
    </van-pull-refresh>

    <!-- 默契度榜 -->
    <van-pull-refresh v-else-if="activeTab === 'chemistry'" v-model="chemRefreshing" @refresh="onChemRefresh">
      <van-list
        v-model:loading="chemLoading"
        :finished="chemFinished"
        finished-text="没有更多了"
        @load="onChemLoad"
      >
        <van-cell
          v-for="item in chemRankings"
          :key="`${item.player_a_id}-${item.player_b_id}`"
        >
          <template #title>
            <div class="chem-title-row">
              <span class="chem-rank">#{{ item.rank }}</span>
              <span class="chem-name-a">{{ item.player_a_name || '?' }}<span v-if="item.player_a_jersey != null" class="jersey-tag">&nbsp;#{{ item.player_a_jersey }}</span></span>
              <span class="chem-amp">&amp;</span>
              <span class="chem-name-b">{{ item.player_b_name || '?' }}<span v-if="item.player_b_jersey != null" class="jersey-tag">&nbsp;#{{ item.player_b_jersey }}</span></span>
            </div>
          </template>
          <template #label>共场次 {{ item.co_matches }} · 共赢 {{ item.co_wins }} · 连线 {{ item.combo_count }}</template>
          <template #value><span class="chem-score">{{ item.chemistry_score.toFixed(2) }}</span></template>
        </van-cell>
      </van-list>
    </van-pull-refresh>

    <!-- 数据统计（得分/助攻/防守/失误，可切换排序） -->
    <van-pull-refresh v-else-if="activeTab === 'stats'" v-model="refreshing" @refresh="onRefresh">
      <div class="sort-bar">
        <span class="sort-bar__label">排序：</span>
        <van-radio-group v-model="statsSort" direction="horizontal" @change="onStatsSortChange">
          <van-radio name="goals">得分</van-radio>
          <van-radio name="assists">助攻</van-radio>
          <van-radio name="defense">防守</van-radio>
          <van-radio name="turnovers">失误</van-radio>
        </van-radio-group>
      </div>
      <div class="stats-table">
        <div class="stats-header">
          <span class="col-name">球员</span>
          <span class="col-num" :class="{ 'col-active': statsSort === 'goals' }">得分</span>
          <span class="col-num" :class="{ 'col-active': statsSort === 'assists' }">助攻</span>
          <span class="col-num" :class="{ 'col-active': statsSort === 'defense' }">防守</span>
          <span class="col-num" :class="{ 'col-active': statsSort === 'turnovers' }">失误</span>
        </div>
        <van-list
          v-model:loading="loading"
          :finished="finished"
          finished-text="没有更多了"
          @load="onLoad"
        >
          <div v-for="item in rankings" :key="item.player_id" class="stats-row">
            <span class="col-name">
              <span class="gender gender--m" v-if="item.gender === 'M'">♂</span>
              <span class="gender gender--f" v-else-if="item.gender === 'F'">♀</span>
              {{ item.display_name || '—' }}
            </span>
            <span class="col-num" :class="{ 'col-active': statsSort === 'goals' }">{{ item.total_goals }}</span>
            <span class="col-num" :class="{ 'col-active': statsSort === 'assists' }">{{ item.total_assists }}</span>
            <span class="col-num" :class="{ 'col-active': statsSort === 'defense' }">{{ item.total_defenses }}</span>
            <span class="col-num" :class="{ 'col-active': statsSort === 'turnovers' }">{{ item.total_turnovers }}</span>
          </div>
        </van-list>
      </div>
    </van-pull-refresh>

    <!-- 比赛信息（场次/胜/负/正负值，可切换排序） -->
    <van-pull-refresh v-else-if="activeTab === 'match_info'" v-model="refreshing" @refresh="onRefresh">
      <div class="sort-bar">
        <span class="sort-bar__label">排序：</span>
        <van-radio-group v-model="matchInfoSort" direction="horizontal" @change="onMatchInfoSortChange">
          <van-radio name="net_wins">净胜场次</van-radio>
          <van-radio name="plus_minus">正负值</van-radio>
        </van-radio-group>
      </div>
      <div class="stats-table">
        <div class="stats-header">
          <span class="col-name">球员</span>
          <span class="col-num">场次</span>
          <span class="col-num">胜</span>
          <span class="col-num">负</span>
          <span class="col-num" :class="{ 'col-active': matchInfoSort === 'net_wins' }">净胜</span>
          <span class="col-num" :class="{ 'col-active': matchInfoSort === 'plus_minus' }">正负</span>
        </div>
        <van-list
          v-model:loading="loading"
          :finished="finished"
          finished-text="没有更多了"
          @load="onLoad"
        >
          <div v-for="item in rankings" :key="item.player_id" class="stats-row">
            <span class="col-name">
              <span class="gender gender--m" v-if="item.gender === 'M'">♂</span>
              <span class="gender gender--f" v-else-if="item.gender === 'F'">♀</span>
              {{ item.display_name || '—' }}
            </span>
            <span class="col-num">{{ item.total_matches }}</span>
            <span class="col-num">{{ item.total_wins }}</span>
            <span class="col-num">{{ item.total_matches - item.total_wins }}</span>
            <span class="col-num" :class="[{ 'col-active': matchInfoSort === 'net_wins' }, pmClass(item.total_wins * 2 - item.total_matches)]">
              {{ item.total_wins * 2 - item.total_matches > 0 ? '+' : '' }}{{ item.total_wins * 2 - item.total_matches }}
            </span>
            <span class="col-num" :class="[{ 'col-active': matchInfoSort === 'plus_minus' }, pmClass(item.total_plus_minus)]">
              {{ item.total_plus_minus > 0 ? '+' : '' }}{{ item.total_plus_minus }}
            </span>
          </div>
        </van-list>
      </div>
    </van-pull-refresh>

    </template><!-- end internal mode -->

    <!-- 底部导航 -->
    <!-- Tab 说明浮层 -->
    <Transition name="tab-tip">
      <div
        v-if="tabTip.visible"
        class="tab-tip-popup"
        :style="{ left: tabTip.x + 'px', top: tabTip.y + 'px' }"
      >{{ tabTip.text }}</div>
    </Transition>

    <van-tabbar route>
      <van-tabbar-item replace to="/home" icon="home-o">主页</van-tabbar-item>
      <van-tabbar-item replace to="/rankings" icon="chart-trending-o">排行榜</van-tabbar-item>
      <van-tabbar-item icon="plus" @click="router.push('/matches/new')">
        <template #icon="{ active }">
          <div class="tab-plus" :class="{ active }">＋</div>
        </template>
        新建
      </van-tabbar-item>
      <van-tabbar-item replace to="/matches/list" icon="records-o">比赛</van-tabbar-item>
      <van-tabbar-item replace to="/profile" icon="user-o">我的</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'
import LeagueRankingsPanel from '@/components/ranking/LeagueRankingsPanel.vue'

const router = useRouter()
const auth = useAuthStore()

const topMode = ref<'internal' | 'league'>('internal')

type TabKey = 'composite' | 'progress' | 'chemistry' | 'stats' | 'match_info'

interface RankingItem {
  rank: number
  player_id: number
  display_name: string | null
  gender: string | null
  jersey_number: number | null
  rank_change: number | null
  conservative_rating: number
  mu: number
  sigma: number
  total_matches: number
  total_wins: number
  total_goals: number
  total_assists: number
  total_defenses: number
  total_plus_minus: number
  total_turnovers: number
  is_new: boolean
  composite_score: number
  attendance_rate: number
  progress_speed: number
}

interface ChemItem {
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

const activeTab = ref<TabKey>('composite')

// ── Tab 说明提示 ──
const TAB_TIPS: Record<string, string> = {
  composite: '综合实力排行。同时考虑胜率稳定性与进攻表现，打得越好、出勤越多，排名越靠前。',
  progress: '进步最快球员排行。近期成绩提升越明显、状态越稳越靠前。至少参加 6 场才能上榜。',
  chemistry: '最佳搭档榜。两人一起打的场次越多、配合赢的越多，默契值越高。',
  stats: '个人进攻数据榜。按得分、助攻、防守贡献或失误次数排序，看谁进攻端最给力。',
  match_info: '参赛记录榜。按胜场数、净胜场或正负值排序，看谁赢得最多。',
}
const tabTip = reactive({ visible: false, text: '', x: 0, y: 0 })
let tabTipTimer: ReturnType<typeof setTimeout> | null = null
let tabTipHideTimer: ReturnType<typeof setTimeout> | null = null

function openTabTip(name: string, e: MouseEvent) {
  if (tabTipHideTimer) { clearTimeout(tabTipHideTimer); tabTipHideTimer = null }
  const el = e.currentTarget as HTMLElement
  const rect = el.getBoundingClientRect()
  tabTip.text = TAB_TIPS[name] ?? ''
  tabTip.x = Math.max(8, Math.min(rect.left, window.innerWidth - 270))
  tabTip.y = rect.bottom + 6
  tabTip.visible = true
}

function closeTabTip() {
  tabTipHideTimer = setTimeout(() => { tabTip.visible = false }, 120)
}

function scheduleTabTip(name: string, e: TouchEvent) {
  clearTabTipTimer()
  const el = e.currentTarget as HTMLElement
  tabTipTimer = setTimeout(() => {
    const rect = el.getBoundingClientRect()
    tabTip.text = TAB_TIPS[name] ?? ''
    tabTip.x = Math.max(8, Math.min(rect.left, window.innerWidth - 270))
    tabTip.y = rect.bottom + 6
    tabTip.visible = true
    tabTipHideTimer = setTimeout(() => { tabTip.visible = false }, 3000)
  }, 500)
}

function clearTabTipTimer() {
  if (tabTipTimer) { clearTimeout(tabTipTimer); tabTipTimer = null }
}

// 战力/稳定/数据统计/比赛信息 共用状态
const rankings = ref<RankingItem[]>([])
const loading = ref(false)
const finished = ref(false)
const refreshing = ref(false)
let page = 1

// 默契度榜状态
const chemRankings = ref<ChemItem[]>([])
const chemLoading = ref(false)
const chemFinished = ref(false)
const chemRefreshing = ref(false)
let chemPage = 1

// 数据统计 / 比赛信息 子排序
const statsSort = ref<'goals' | 'assists' | 'defense' | 'turnovers'>('goals')
const matchInfoSort = ref<'net_wins' | 'plus_minus'>('net_wins')

const RANKINGS_CACHE_KEY = 'ep_rankings_cache_v1'
const CHEM_CACHE_KEY = 'ep_chemistry_cache_v1'


// ── 名次变化（由后端基于最新比赛日计算，前端直接使用）──
function rankChangeIcon(item: RankingItem): string {
  const d = item.rank_change
  if (d == null) return ''
  if (d > 0) return `↑${d}`
  if (d < 0) return `↓${Math.abs(d)}`
  return '—'
}

function rankChangeClass(item: RankingItem): string {
  const d = item.rank_change
  if (d == null || d === 0) return 'rank-change--same'
  return d > 0 ? 'rank-change--up' : 'rank-change--down'
}

// ── API 排序参数 ──
function getSortBy(): string {
  if (activeTab.value === 'stats') return statsSort.value
  if (activeTab.value === 'match_info') return matchInfoSort.value
  return activeTab.value
}

function rankingCacheKeyOf(sortBy: string) {
  const tid = auth.viewingTeamId ?? 0
  return `${RANKINGS_CACHE_KEY}:${tid}:${sortBy}`
}

function chemistryCacheKeyOf() {
  const tid = auth.viewingTeamId ?? 0
  return `${CHEM_CACHE_KEY}:${tid}`
}

function persistRankingsCache(sortBy: string, items: RankingItem[]) {
  try {
    localStorage.setItem(rankingCacheKeyOf(sortBy), JSON.stringify(items))
  } catch {
    // ignore
  }
}

function readRankingsCache(sortBy: string): RankingItem[] {
  try {
    const raw = localStorage.getItem(rankingCacheKeyOf(sortBy))
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function persistChemistryCache(items: ChemItem[]) {
  try {
    localStorage.setItem(chemistryCacheKeyOf(), JSON.stringify(items))
  } catch {
    // ignore
  }
}

function readChemistryCache(): ChemItem[] {
  try {
    const raw = localStorage.getItem(chemistryCacheKeyOf())
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

// ── 卡片列表辅助函数（综合/战力/稳定）──
function rankLabel(item: RankingItem): string {
  if (activeTab.value === 'composite') {
    const attendanceText = item.attendance_rate > 0 ? ` · 出勤${item.attendance_rate.toFixed(0)}%` : ''
    return `${item.total_matches}场 ${item.total_wins}胜 · 得分${item.total_goals} 助攻${item.total_assists} 防守${item.total_defenses}${attendanceText}`
  }
  if (activeTab.value === 'progress') {
    return `${item.total_matches}场 · 当前综合战力 ${item.composite_score.toFixed(2)}`
  }
  return `${item.total_matches}场 · ${item.total_wins}胜`
}

function rankMain(item: RankingItem): string {
  if (activeTab.value === 'composite') return `${item.composite_score.toFixed(2)} 分`
  if (activeTab.value === 'progress') {
    const s = item.progress_speed
    return s > 0 ? (s * 100).toFixed(1) : '场次不足'
  }
  return `—`
}

function pmClass(val: number): string {
  if (val > 0) return 'rank-main--positive'
  if (val < 0) return 'rank-main--negative'
  return ''
}

// ── 数据加载 ──
const memberPageSize = 16  // 普通成员只看前16名

async function onLoad() {
  // 超管未选队伍时不请求（避免 403 循环）
  if (auth.isSuperAdmin && !auth.viewingTeamId) {
    finished.value = true
    loading.value = false
    return
  }
  // 非管理员：已加载16个后不再分页
  if (!auth.isAdmin && rankings.value.length >= memberPageSize) {
    finished.value = true
    loading.value = false
    return
  }
  try {
    const sortBy = getSortBy()
    const pageSize = auth.isAdmin ? 20 : memberPageSize
    const params: Record<string, unknown> = { page, page_size: pageSize, sort_by: sortBy }
    const res = await api.get('/rankings', { params })
    const items: RankingItem[] = res.data.items
    if (refreshing.value) {
      rankings.value = items
      refreshing.value = false
    } else {
      rankings.value.push(...items)
    }
    // 非管理员：加载完第一页就停止，只展示前16名
    if (items.length < pageSize || (!auth.isAdmin && rankings.value.length >= memberPageSize)) {
      finished.value = true
    }
    if (page === 1 && items.length > 0) {
      persistRankingsCache(sortBy, items)
    }
    page++
  } catch (_err) {
    if (page === 1) {
      const cached = readRankingsCache(getSortBy())
      if (cached.length > 0) {
        rankings.value = cached
      }
    }
    // Stop auto-retry loop when backend returns an error.
    finished.value = true
  } finally {
    loading.value = false
  }
}

function resetRankings() {
  page = 1
  finished.value = false
  rankings.value = []
}

function onRefresh() {
  resetRankings()
  loading.value = true
  onLoad()
}

async function onChemLoad() {
  // 超管未选队伍时不请求
  if (auth.isSuperAdmin && !auth.viewingTeamId) {
    chemFinished.value = true
    chemLoading.value = false
    return
  }
  try {
    const res = await api.get('/rankings/chemistry', { params: { page: 1, page_size: 30 } })
    const items: ChemItem[] = res.data.items
    chemRankings.value = items
    if (items.length > 0) {
      persistChemistryCache(items)
    }
    chemRefreshing.value = false
    chemFinished.value = true  // 只展示前30组，不再分页
  } catch (_err) {
    const cached = readChemistryCache()
    if (cached.length > 0) {
      chemRankings.value = cached
    }
    // Stop auto-retry loop when backend returns an error.
    chemFinished.value = true
  } finally {
    chemLoading.value = false
  }
}

function onChemRefresh() {
  chemPage = 1
  chemFinished.value = false
  chemLoading.value = true
  onChemLoad()
}

function onTabChange() {
  if (activeTab.value === 'chemistry') {
    chemPage = 1
    chemFinished.value = false
    chemRankings.value = []
    chemLoading.value = true
    onChemLoad()
  } else {
    resetRankings()
    loading.value = true
    onLoad()
  }
}



function onStatsSortChange() {
  resetRankings()
  loading.value = true
  onLoad()
}

function onMatchInfoSortChange() {
  resetRankings()
  loading.value = true
  onLoad()
}

onMounted(() => {
  if (activeTab.value === 'chemistry') {
    chemLoading.value = true
    onChemLoad()
  } else {
    loading.value = true
    onLoad()
  }
})

// ── 手势滑动切换 Tab ──
const TAB_ORDER: TabKey[] = ['composite', 'progress', 'chemistry', 'stats', 'match_info']
let _swipeStartX = 0
let _swipeStartY = 0

function onPageTouchStart(e: TouchEvent) {
  if (topMode.value !== 'internal') return
  _swipeStartX = e.touches[0]!.clientX
  _swipeStartY = e.touches[0]!.clientY
}

function onPageTouchEnd(e: TouchEvent) {
  if (topMode.value !== 'internal') return
  const dx = e.changedTouches[0]!.clientX - _swipeStartX
  const dy = e.changedTouches[0]!.clientY - _swipeStartY
  // 仅响应水平方向明显的滑动（>50px 且水平分量 > 垂直分量）
  if (Math.abs(dx) < 50 || Math.abs(dx) < Math.abs(dy)) return
  const currentIdx = TAB_ORDER.indexOf(activeTab.value)
  if (dx < 0 && currentIdx < TAB_ORDER.length - 1) {
    // 向左滑 → 下一个 Tab
    activeTab.value = TAB_ORDER[currentIdx + 1]!
    onTabChange()
  } else if (dx > 0 && currentIdx > 0) {
    // 向右滑 → 上一个 Tab
    activeTab.value = TAB_ORDER[currentIdx - 1]!
    onTabChange()
  }
}
</script>

<style scoped>
.rankings-page {
  padding-bottom: 60px;
  min-height: 100vh;
  background: #f7f8fa;
}

/* 联盟/队内切换按钮 */
.mode-switch {
  display: flex;
  align-items: center;
  gap: 2px;
  background: rgba(0, 0, 0, 0.08);
  border-radius: 6px;
  padding: 2px;
}

.mode-btn {
  padding: 3px 10px;
  font-size: 12px;
  border-radius: 4px;
  color: #999;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.mode-btn.active {
  background: #1677ff;
  color: #fff;
  font-weight: 600;
}

.rank-title-row {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
}
.rank-num {
  font-weight: 700;
  min-width: 24px;
  color: #333;
}
.rank-change {
  font-size: 12px;
  font-weight: 600;
  min-width: 28px;
}
.rank-change--up { color: #ee0a24; }
.rank-change--down { color: #07c160; }
.rank-change--same { color: #aaa; }

.gender {
  font-size: 13px;
  font-weight: 700;
}
.gender--m { color: #1677ff; }
.gender--f { color: #ee0a24; }

.rank-value {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}
.rank-main {
  font-size: 15px;
  font-weight: 700;
  color: #1677ff;
}
.rank-main--positive { color: #ee0a24 !important; }
.rank-main--negative { color: #07c160 !important; }

/* ---- 球衣号码 ---- */
.jersey-tag {
  font-size: 11px;
  font-weight: 700;
  font-style: italic;
  color: #f59e0b;
  margin-left: 2px;
}

/* ---- 默契榜彩色名字 ---- */
.chem-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.chem-rank {
  font-size: 12px;
  color: #999;
  flex-shrink: 0;
}
.chem-name-a {
  font-weight: 700;
  color: #1677ff;
}
.chem-name-b {
  font-weight: 700;
  color: #f59e0b;
}
.chem-amp {
  color: #ccc;
  font-size: 12px;
}
.chem-score {
  font-weight: 700;
  color: #07c160;
  font-size: 16px;
}

/* 排序栏 */
.sort-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: #fff;
  border-bottom: 1px solid #ebedf0;
  flex-wrap: wrap;
}
.sort-bar__label {
  font-size: 13px;
  color: #646566;
  flex-shrink: 0;
}


/* 统计表格 */
.stats-table {
  background: #fff;
}
.stats-header {
  display: flex;
  align-items: center;
  padding: 8px 16px;
  background: #f7f8fa;
  border-bottom: 1px solid #ebedf0;
  font-size: 12px;
  color: #969799;
  font-weight: 600;
}
.stats-row {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #ebedf0;
  font-size: 14px;
}
.col-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #323233;
}
.col-num {
  width: 44px;
  text-align: right;
  color: #646566;
  flex-shrink: 0;
}
.col-active {
  color: #1677ff;
  font-weight: 700;
}

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

/* Tab 说明提示浮层 */
.tab-tip-trigger {
  display: inline-block;
}

.tab-tip-popup {
  position: fixed;
  z-index: 9999;
  background: rgba(18, 22, 34, 0.94);
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.65;
  padding: 8px 12px;
  border-radius: 8px;
  max-width: 260px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
  pointer-events: none;
  word-break: break-all;
}

.tab-tip-enter-active,
.tab-tip-leave-active {
  transition: opacity 0.15s ease;
}

.tab-tip-enter-from,
.tab-tip-leave-to {
  opacity: 0;
}
</style>
