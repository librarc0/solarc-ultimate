<template>
  <div class="match-list-page" @touchstart.passive="onTouchStart" @touchend.passive="onTouchEnd">
    <van-nav-bar title="比赛记录" />
    <van-tabs v-model:active="activeTab" sticky swipeable>
      <van-tab title="未完成" name="draft">
        <van-pull-refresh v-model="refreshingDraft" @refresh="() => loadMatches('draft', true)">
          <van-list
            v-model:loading="loadingDraft"
            :finished="finishedDraft"
            finished-text="没有更多了"
            @load="() => loadMatches('draft')"
          >
            <van-cell
              v-for="m in draftMatches"
              :key="m.id"
              :title="`${m.match_type === 'internal' ? '内战' : '外战'} · ${formatDate(m.match_date)}`"
              :label="buildDraftLabel(m)"
            >
              <template #right-icon>
                <van-space>
                  <van-button
                    v-if="m.match_type === 'external'"
                    size="mini"
                    plain
                    type="primary"
                    @click.stop="goSpiritScore(m.id)"
                  >
                    {{ m.spirit_scored ? '查看精神评分' : '录入精神评分' }}
                  </van-button>
                  <van-button v-if="canContinueDraft(m)" size="mini" type="primary" @click.stop="continueLive(m.id)">继续录入</van-button>
                  <van-button
                    v-if="canTakeoverDraft(m)"
                    size="mini"
                    plain
                    type="warning"
                    @click.stop="takeoverDraft(m.id)"
                  >接管录入</van-button>
                  <van-button v-if="canAbandonDraft(m)" size="mini" type="danger" plain @click.stop="abandonDraft(m.id)">放弃</van-button>
                </van-space>
              </template>
            </van-cell>
          </van-list>
        </van-pull-refresh>
      </van-tab>

      <!-- 待审批（仅管理员可见） -->
      <van-tab v-if="isAdmin" title="待审批" name="pending_approval">
        <van-pull-refresh v-model="refreshingPending" @refresh="() => loadMatches('pending_approval', true)">
          <van-list
            v-model:loading="loadingPending"
            :finished="finishedPending"
            finished-text="没有更多了"
            @load="() => loadMatches('pending_approval')"
          >
            <van-cell
              v-for="m in pendingMatches"
              :key="m.id"
              :title="`${m.match_type === 'internal' ? '内战' : '外战'} · ${formatDate(m.match_date)}`"
              :label="buildMatchLabel(m)"
              @click="openDetail(m.id)"
            >
              <template #right-icon>
                <van-space v-if="isAdmin">
                  <van-button
                    v-if="m.match_type === 'external'"
                    size="mini"
                    plain
                    type="primary"
                    @click.stop="goSpiritScore(m.id)"
                  >
                    {{ m.spirit_scored ? '查看精神评分' : '录入精神评分' }}
                  </van-button>
                  <van-button size="mini" plain icon="eye-o" @click.stop="openDetail(m.id)">详情</van-button>
                  <van-button size="mini" type="success" @click.stop="approveMatch(m.id)">审批</van-button>
                  <van-button size="mini" type="danger" plain @click.stop="rejectMatch(m.id)">拒绝</van-button>
                  <van-button size="mini" plain @click.stop="deleteMatch(m.id)">删除</van-button>
                </van-space>
              </template>
            </van-cell>
          </van-list>
        </van-pull-refresh>
      </van-tab>

      <!-- 已完成 -->
      <van-tab title="已完成" name="approved">
        <van-pull-refresh v-model="refreshingApproved" @refresh="() => loadMatches('approved', true)">
          <van-list
            v-model:loading="loadingApproved"
            :finished="finishedApproved"
            finished-text="没有更多了"
            @load="() => loadMatches('approved')"
          >
            <van-cell
              v-for="m in approvedMatches"
              :key="m.id"
              :title="`${m.match_type === 'internal' ? '内战' : '外战'} · ${formatDate(m.match_date)}`"
              :label="buildMatchLabel(m)"
              is-link
              :to="`/matches/${m.id}`"
            >
              <template #right-icon>
                <div class="cell-right" v-if="isAdmin">
                  <van-button
                    v-if="m.match_type === 'external'"
                    size="mini"
                    plain
                    type="primary"
                    @click.stop="goSpiritScore(m.id)"
                    style="margin-right:8px"
                  >
                    {{ m.spirit_scored ? '查看精神评分' : '补录精神评分' }}
                  </van-button>
                  <van-button size="mini" type="danger" plain @click.stop="deleteMatch(m.id)" style="margin-right:8px">删除</van-button>
                  <van-tag type="success">已结算</van-tag>
                </div>
                <div v-else class="cell-right">
                  <van-button
                    v-if="m.match_type === 'external'"
                    size="mini"
                    plain
                    type="primary"
                    @click.stop="goSpiritScore(m.id)"
                    style="margin-right:8px"
                  >
                    {{ m.spirit_scored ? '查看精神评分' : '补录精神评分' }}
                  </van-button>
                  <van-tag type="success">已结算</van-tag>
                </div>
              </template>
            </van-cell>
          </van-list>
        </van-pull-refresh>
      </van-tab>
    </van-tabs>

    <!-- 比赛详情抽屉（待审批查看用） -->
    <van-popup
      v-model:show="showDetail"
      position="bottom"
      round
      :style="{ maxHeight: '80vh', overflowY: 'auto' }"
    >
      <div v-if="detailLoading" style="padding: 40px; text-align: center">
        <van-loading type="spinner" />
      </div>
      <template v-else-if="detailData">
        <div style="padding: 16px 16px 0; font-size: 16px; font-weight: 600">比赛详情</div>
        <van-cell-group inset title="基本信息" style="margin-top: 8px">
          <van-cell title="类型" :value="detailData.match_type === 'internal' ? '内战' : '外战'" />
          <van-cell title="日期" :value="formatDate(detailData.match_date)" />
          <van-cell title="比分" :value="`${detailData.team_a_score} : ${detailData.team_b_score}`" />
          <van-cell title="数据级别" :value="`Level ${detailData.data_level}`" />
          <van-cell title="提交人" :value="detailData.created_by_name" />
          <van-cell v-if="detailData.notes" title="备注" :value="detailData.notes" />
        </van-cell-group>

        <!-- 队A / 我方 -->
        <van-cell-group inset :title="detailData.match_type === 'internal' ? '队A' : '我方队员'" style="margin-top: 8px">
          <van-cell
            v-for="p in teamAParticipants(detailData.participants)"
            :key="p.player_id"
            :title="p.player_name"
            :label="statLabel(p, detailData.data_level)"
          />
        </van-cell-group>

        <!-- 队B（仅内战） -->
        <van-cell-group v-if="detailData.match_type === 'internal'" inset title="队B" style="margin-top: 8px">
          <van-cell
            v-for="p in teamBParticipants(detailData.participants)"
            :key="p.player_id"
            :title="p.player_name"
            :label="statLabel(p, detailData.data_level)"
          />
        </van-cell-group>

        <div style="padding: 12px 16px 24px; display: flex; gap: 8px">
          <van-button round block type="success" @click="approveMatch(detailData.id); showDetail = false">审批通过</van-button>
          <van-button round block type="danger" plain @click="rejectMatch(detailData.id); showDetail = false">拒绝</van-button>
        </div>
      </template>
    </van-popup>

    <!-- Bottom nav -->
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
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const isAdmin = auth.isAdmin
const currentUserId = computed(() => auth.user?.id ?? null)
const router = useRouter()

interface MatchItem {
  id: number
  match_type: string
  match_date: string
  team_a_score: number
  team_b_score: number
  status: string
  data_level: number
  notes?: string | null
  created_by_id?: number | null
  created_by_name?: string | null
  duration_seconds?: number | null
  expires_at?: string | null
  countdown_seconds?: number | null
  lock_status?: 'unlocked' | 'locked_by_me' | 'locked_by_other' | 'lock_expired'
  lock_owner_id?: number | null
  lock_owner_name?: string | null
  lock_expires_in_seconds?: number | null
  lock_lease_seconds?: number | null
  spirit_scored?: boolean
  spirit_total_score?: number | null
}

function buildMatchLabel(match: MatchItem): string {
  const segments = [`${match.team_a_score} : ${match.team_b_score}`, `Level ${match.data_level}`]
  if (match.match_type === 'external') {
    segments.push(match.spirit_scored ? `精神分：${match.spirit_total_score ?? '-'}/20` : '精神分：未评分')
  }
  if (match.created_by_name) segments.push(`提交人：${match.created_by_name}`)
  const text = (match.notes ?? '').trim()
  if (!text) return segments.join(' · ')
  const summary = text.length > 18 ? `${text.slice(0, 18)}...` : text
  segments.push(`备注：${summary}`)
  return segments.join(' · ')
}

function goSpiritScore(id: number) {
  router.push({ name: 'match-spirit-score', params: { id: String(id) } })
}

function buildDraftLabel(match: MatchItem): string {
  const segments = [
    `${match.team_a_score} : ${match.team_b_score}`,
    `已录入 ${formatElapsed(match.duration_seconds ?? 0)}`,
  ]
  if (match.created_by_name) segments.push(`最近保存：${match.created_by_name}`)
  if (match.lock_status === 'locked_by_me') {
    segments.push('录入锁：你正在编辑')
  } else if (match.lock_status === 'locked_by_other') {
    const who = match.lock_owner_name ? `（${match.lock_owner_name}）` : ''
    const left = Math.max(0, match.lock_expires_in_seconds ?? 0)
    segments.push(`录入锁：他人编辑中${who}，${left}s 后可接管`)
  } else if (match.lock_status === 'lock_expired') {
    segments.push('录入锁：已过期，可接管')
  }
  segments.push(formatCountdown(match.countdown_seconds))
  return segments.join(' · ')
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function formatCountdown(seconds?: number | null): string {
  if (seconds == null) return '删除倒计时：--'
  if (seconds <= 0) return '删除倒计时：即将过期'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  return `删除倒计时：${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function formatDate(isoStr: string): string {
  if (!isoStr) return ''
  // 确保带时区标识，否则浏览器按本地时间解析（非 UTC）
  const str = /[Z+]/.test(isoStr) ? isoStr : isoStr + 'Z'
  const d = new Date(str)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function statLabel(p: any, dataLevel: number): string {
  if (dataLevel < 2) return ''
  const parts: string[] = []
  if (p.goals != null) parts.push(`得分 ${p.goals}`)
  if (dataLevel >= 2 && p.plus_minus != null) parts.push(`正负 ${p.plus_minus}`)
  if (dataLevel >= 3 && p.assists != null) parts.push(`助攻 ${p.assists}`)
  if (dataLevel >= 3 && p.turnovers != null && p.turnovers > 0) parts.push(`失误 ${p.turnovers}`)
  return parts.join('  ')
}

function teamAParticipants(participants: any[] = []): any[] {
  return participants.filter(p => p.team_side === 'A')
}

function teamBParticipants(participants: any[] = []): any[] {
  return participants.filter(p => p.team_side === 'B')
}

const activeTab = ref('pending_approval')
const touchStartX = ref(0)
const touchStartY = ref(0)

function tabOrder(): string[] {
  return isAdmin ? ['draft', 'pending_approval', 'approved'] : ['draft', 'approved']
}

function onTouchStart(e: TouchEvent) {
  const touch = e.changedTouches?.[0]
  if (!touch) return
  touchStartX.value = touch.clientX
  touchStartY.value = touch.clientY
}

function onTouchEnd(e: TouchEvent) {
  const touch = e.changedTouches?.[0]
  if (!touch) return
  const dx = touch.clientX - touchStartX.value
  const dy = touch.clientY - touchStartY.value
  if (Math.abs(dx) < 60 || Math.abs(dx) <= Math.abs(dy)) return

  const order = tabOrder()
  const current = order.indexOf(activeTab.value)
  if (current < 0) return

  if (dx < 0 && current < order.length - 1) {
    activeTab.value = order[current + 1] as string
  } else if (dx > 0 && current > 0) {
    activeTab.value = order[current - 1] as string
  }
}

// --- Draft tab state ---
const draftMatches = ref<MatchItem[]>([])
const loadingDraft = ref(false)
const finishedDraft = ref(false)
const refreshingDraft = ref(false)
let draftPage = 1

// --- Pending tab state ---
const pendingMatches = ref<MatchItem[]>([])
const loadingPending = ref(false)
const finishedPending = ref(false)
const refreshingPending = ref(false)
let pendingPage = 1

// --- Approved tab state ---
const approvedMatches = ref<MatchItem[]>([])
const loadingApproved = ref(false)
const finishedApproved = ref(false)
const refreshingApproved = ref(false)
let approvedPage = 1

// --- Match detail drawer ---
const showDetail = ref(false)
const detailLoading = ref(false)
const detailData = ref<any>(null)

async function openDetail(matchId: number) {
  showDetail.value = true
  detailLoading.value = true
  detailData.value = null
  try {
    const res = await api.get(`/matches/${matchId}`)
    detailData.value = res.data
  } catch {
    showToast('加载详情失败')
    showDetail.value = false
  } finally {
    detailLoading.value = false
  }
}

async function loadMatches(statusFilter: string, reset = false) {
  const isPending = statusFilter === 'pending_approval'
  const isDraft = statusFilter === 'draft'
  if (reset) {
    if (isDraft) {
      loadingDraft.value = true
      draftPage = 1
      finishedDraft.value = false
      draftMatches.value = []
    } else if (isPending) {
      loadingPending.value = true   // block van-list from triggering @load while resetting
      pendingPage = 1
      finishedPending.value = false
      pendingMatches.value = []
    } else {
      loadingApproved.value = true  // block van-list from triggering @load while resetting
      approvedPage = 1
      finishedApproved.value = false
      approvedMatches.value = []
    }
  }
  const page = isDraft ? draftPage : (isPending ? pendingPage : approvedPage)

  try {
    const res = await api.get('/matches', { params: { status: statusFilter, page, page_size: 20 } })
    const items: MatchItem[] = res.data
    if (isDraft) {
      draftMatches.value.push(...items)
      if (items.length < 20) finishedDraft.value = true
      draftPage++
      refreshingDraft.value = false
    } else if (isPending) {
      pendingMatches.value.push(...items)
      if (items.length < 20) finishedPending.value = true
      pendingPage++
      refreshingPending.value = false
    } else {
      approvedMatches.value.push(...items)
      if (items.length < 20) finishedApproved.value = true
      approvedPage++
      refreshingApproved.value = false
    }
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    showToast(typeof detail === 'string' ? detail : '加载比赛记录失败，请稍后重试')
    if (isDraft) refreshingDraft.value = false
    else if (isPending) refreshingPending.value = false
    else refreshingApproved.value = false
  } finally {
    if (isDraft) loadingDraft.value = false
    else if (isPending) loadingPending.value = false
    else loadingApproved.value = false
  }
}

function continueLive(id: number) {
  router.push({ name: 'match-live', query: { draft_id: String(id) } })
}

function isDraftOwnedByMe(match: MatchItem): boolean {
  return currentUserId.value != null && match.created_by_id === currentUserId.value
}

function canContinueDraft(match: MatchItem): boolean {
  if (isAdmin) return true
  if (match.lock_status === 'locked_by_me') return true
  return isDraftOwnedByMe(match)
}

function canTakeoverDraft(match: MatchItem): boolean {
  if (match.lock_status === 'locked_by_me') return false
  if (isAdmin) return true
  return !canContinueDraft(match)
}

function canAbandonDraft(match: MatchItem): boolean {
  if (isAdmin) return true
  return isDraftOwnedByMe(match)
}

async function abandonDraft(id: number) {
  try {
    await showConfirmDialog({ title: '确认放弃', message: '放弃后该未完成比赛将被移除' })
    await api.post(`/matches/drafts/${id}/abandon`)
    showToast('已放弃该比赛')
    loadMatches('draft', true)
  } catch {
    // user cancelled
  }
}

async function takeoverDraft(id: number) {
  try {
    await showConfirmDialog({ title: '确认接管', message: '接管后将由你继续录入，原录入锁将失效' })
    await api.post(`/matches/drafts/${id}/takeover`)
    showToast('已接管，可继续录入')
    continueLive(id)
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    if (detail?.code === 'DRAFT_LOCKED') {
      const who = detail?.locked_by ? `（${detail.locked_by}）` : ''
      showToast(`仍在录入中${who}`)
      await loadMatches('draft', true)
      return
    }
    // user cancel or network issue
  }
}

async function approveMatch(id: number) {
  try {
    await showConfirmDialog({ title: '确认审批', message: '审批后将立即结算评分' })
    await api.put(`/matches/${id}`, { action: 'approve' })
    showToast('审批成功')
    loadMatches('pending_approval', true)
  } catch {
    // user cancelled or network error
  }
}

async function rejectMatch(id: number) {
  try {
    await showConfirmDialog({ title: '确认拒绝', message: '拒绝后该比赛不会影响评分' })
    await api.put(`/matches/${id}`, { action: 'reject' })
    showToast('已拒绝')
    loadMatches('pending_approval', true)
  } catch {
    // user cancelled
  }
}

async function deleteMatch(id: number) {
  try {
    await showConfirmDialog({
      title: '确认删除',
      message: '删除后将回退该场比赛的评分影响，此操作不可撤销',
    })
    await api.delete(`/matches/${id}`)
    showToast('已删除，评分已回退')
    // 两个 tab 都刷新一下
    loadMatches('pending_approval', true)
    loadMatches('approved', true)
  } catch {
    // user cancelled
  }
}

onMounted(() => {
  activeTab.value = 'draft'
  loadingDraft.value = true
  loadMatches('draft', true)

  if (isAdmin) {
    loadingPending.value = true
    loadMatches('pending_approval', true)
  } else {
    loadingApproved.value = true
    loadMatches('approved', true)
  }
})
</script>

<style scoped>
.match-list-page {
  padding-bottom: 60px;
}
.cell-right {
  display: flex;
  align-items: center;
}
.tab-plus {
  width: 36px; height: 36px; border-radius: 50%;
  background: #3b82f6; color: #fff;
  font-size: 22px; line-height: 36px; text-align: center;
  font-weight: 700; margin: 0 auto; margin-bottom: -4px;
}
.tab-plus.active { background: #1d4ed8; }
</style>
