<template>
  <div class="live-page">
    <van-nav-bar
      title="比赛实况"
    >
      <template #left>
        <div class="nav-left-wrap">
          <van-icon name="arrow-left" size="18" style="cursor: pointer" @click="handleBack" />
          <span class="timer-display" :class="{ paused: timerPaused }">
            {{ timerDisplay }}
          </span>
        </div>
      </template>
      <template #right>
        <div class="nav-actions">
          <van-button size="small" plain type="primary" @click="saveAsDraft">保存待录入</van-button>
          <van-button size="small" plain type="danger" @click="abandonDraft">放弃</van-button>
        </div>
      </template>
    </van-nav-bar>

    <!-- 开赛前配置对话框 -->
    <van-dialog
      v-model:show="showSetupDialog"
      title="开赛配置"
      :show-cancel-button="false"
      confirm-button-text="开始比赛"
      @confirm="startMatch"
    >
      <div style="padding: 12px 16px">
        <van-cell-group inset>
          <van-field label="是否记录性别比">
            <template #input>
              <van-switch v-model="useGender" size="20" />
            </template>
          </van-field>
          <template v-if="useGender">
            <van-field label="第一分性别比">
              <template #input>
                <van-radio-group v-model="abbaFirstRatio" direction="horizontal">
                  <van-radio name="A">A（4男3女）</van-radio>
                  <van-radio name="B">B（3男4女）</van-radio>
                </van-radio-group>
              </template>
            </van-field>
            <van-field label=" ">
              <template #input>
                <span style="font-size:12px;color:#888">
                  循环模式：{{ abbaFirstRatio === 'A' ? '4男3女 → 3男4女 → 3男4女 → 4男3女（ABBA）' : '3男4女 → 4男3女 → 4男3女 → 3男4女（BAAB）' }}
                </span>
              </template>
            </van-field>
          </template>
          <van-field label="开赛进攻方">
            <template #input>
              <van-radio-group v-model="possession" direction="horizontal">
                <van-radio name="A">{{ matchType === 'external' ? '我方先进攻' : '队A先进攻' }}</van-radio>
                <van-radio name="B">{{ matchType === 'external' ? '对方先进攻' : '队B先进攻' }}</van-radio>
              </van-radio-group>
            </template>
          </van-field>
          <van-field
            v-model="liveNotes"
            type="textarea"
            rows="2"
            label="比赛备注"
            placeholder="可填写天气、场地、关键背景等"
          />
        </van-cell-group>

        <!-- 胜率预测区 -->
        <div v-if="prediction" class="predict-card">
          <div class="predict-card__title">⚡ 比赛预测</div>
          <div class="predict-card__bars">
            <div class="predict-bar predict-bar--a">
              <span class="predict-bar__label">{{ matchType === 'external' ? '我方' : '队 A' }}</span>
              <div class="predict-bar__track">
                <div class="predict-bar__fill predict-bar__fill--a" :style="{ width: (prediction.win_prob_a * 100).toFixed(1) + '%' }"></div>
              </div>
              <span class="predict-bar__pct">{{ (prediction.win_prob_a * 100).toFixed(1) }}%</span>
            </div>
            <div class="predict-bar predict-bar--b">
              <span class="predict-bar__label">{{ matchType === 'external' ? '对方' : '队 B' }}</span>
              <div class="predict-bar__track">
                <div class="predict-bar__fill predict-bar__fill--b" :style="{ width: (prediction.win_prob_b * 100).toFixed(1) + '%' }"></div>
              </div>
              <span class="predict-bar__pct">{{ (prediction.win_prob_b * 100).toFixed(1) }}%</span>
            </div>
          </div>
          <div class="predict-card__quality">
            均衡度 {{ (prediction.match_quality * 100).toFixed(1) }}%
          </div>
        </div>
        <div v-else-if="predictionLoading" style="text-align:center;padding:12px;color:#969799;font-size:13px">
          预测加载中…
        </div>
      </div>
    </van-dialog>

    <!-- 比分板 -->
    <div class="scoreboard">
      <div class="scoreboard__team scoreboard__team--a">
        <div class="scoreboard__name">
          {{ matchType === 'external' ? '我方' : '队 A' }}
          <span v-if="possession === 'A'" class="disc-icon" title="持盘方">&#x1F94F;</span>
        </div>
        <div class="scoreboard__score">{{ scoreA }}</div>
      </div>
      <div class="scoreboard__sep">—</div>
      <div class="scoreboard__team scoreboard__team--b">
        <div class="scoreboard__name">
          {{ matchType === 'external' ? '对方' : '队 B' }}
          <span v-if="possession === 'B'" class="disc-icon" title="持盘方">&#x1F94F;</span>
        </div>
        <div class="scoreboard__score">{{ scoreB }}</div>
      </div>
    </div>

    <div v-if="liveNotes.trim() || useGender" class="status-bar">
      <span v-if="liveNotes.trim()" class="status-bar__note">{{ liveNotes }}</span>
      <span v-if="liveNotes.trim() && useGender" class="status-bar__gap"></span>
      <span v-if="useGender" class="status-bar__gender">
        本分性别比：<strong>{{ currentGenderRatio === 'A' ? 'A（4男3女）' : 'B（3男4女）' }}</strong>
      </span>
    </div>

    <!-- 操作按钮行 — 主要得分按钮 --> 
    <div class="action-bar action-bar--main">
      <van-button
        block
        class="score-btn score-btn--a"
        @click="openGoalDrawer('A')"
      >
        <span class="score-btn__icon">⚽</span>
        <span class="score-btn__label">{{ matchType === 'external' ? '我方得分' : '队A 得分' }}</span>
      </van-button>
      <van-button
        block
        class="score-btn score-btn--b"
        @click="matchType === 'external' ? handleExternalGoal() : openGoalDrawer('B')"
      >
        <span class="score-btn__icon">⚽</span>
        <span class="score-btn__label">{{ matchType === 'external' ? '对方得分' : '队B 得分' }}</span>
      </van-button>
    </div>
    <!-- 盘权提示 -->
    <div v-if="possession" class="possession-hint" :class="`possession-hint--${possession}`">
      &#x1F94F;
      {{ matchType === 'external'
        ? (possession === 'A' ? '我方' : '对方')
        : ('队' + possession)
      }} 持盘进攻中
    </div>
    <!-- 次要操作行 -->
    <div class="action-bar action-bar--secondary">
      <van-button size="small" plain type="primary" @click="openDefenseDrawer">🛡 防守盘</van-button>
      <van-button size="small" plain type="warning" @click="openTurnoverPicker">⚡ 失误</van-button>
      <van-button
        size="small"
        :type="timerPaused ? 'primary' : 'default'"
        @click="toggleTimer"
      >
        {{ timerPaused ? '▶ 继续' : '⏸ 暂停' }}
      </van-button>
      <van-button size="small" type="warning" @click="handleHalftime">半场</van-button>
      <van-button size="small" type="danger" @click="handleEnd">结束</van-button>
    </div>

    <!-- 时间轴事件流 -->
    <div class="timeline">
      <div v-if="events.length === 0" class="timeline__empty">
        <van-empty description="暂无事件，开始录入比赛吧" />
      </div>
      <div v-else class="timeline__list">
        <template v-for="(evt, idx) in events" :key="idx">
          <!-- 得分分割线：每个 goal 之后显示（列表是新→旧，因此得分后内容在下方） -->
          <div
            v-if="evt.event_type === 'goal'"
            class="timeline__point-divider"
          >
            <span class="timeline__point-label">
              ――― {{ matchType === 'external' ? '我方' : '队' + evt.team_side }}
              <strong>{{ evt.score_a }}–{{ evt.score_b }}</strong> ―――
            </span>
          </div>
          <div
            class="timeline__item"
            :class="{
              'timeline__item--a': evt.team_side === 'A',
              'timeline__item--b': evt.team_side === 'B',
              'timeline__item--system': evt.event_type === 'halftime' || evt.event_type === 'system',
            }"
          >
            <!-- 半场/系统事件居中 -->
            <template v-if="evt.event_type === 'halftime' || evt.event_type === 'system'">
              <div class="timeline__system-event">
                <van-tag type="warning" size="large">{{ evt.label }}</van-tag>
              </div>
            </template>
            <!-- 队A 事件（左侧） -->
            <template v-else-if="evt.team_side === 'A'">
              <div class="timeline__bubble timeline__bubble--a">
                <div class="timeline__bubble-time">{{ evt.elapsed }}</div>
                <div class="timeline__bubble-label">
                  {{ evt.label }}
                  <span v-if="evt.is_break" class="break-badge">⚡ BREAK</span>
                </div>
              </div>
              <div class="timeline__dot timeline__dot--a"></div>
              <div class="timeline__spacer"></div>
            </template>
            <!-- 队B 事件（右侧） -->
            <template v-else>
              <div class="timeline__spacer"></div>
              <div class="timeline__dot timeline__dot--b"></div>
              <div class="timeline__bubble timeline__bubble--b">
                <div class="timeline__bubble-time">{{ evt.elapsed }}</div>
                <div class="timeline__bubble-label">
                  {{ evt.label }}
                  <span v-if="evt.is_break" class="break-badge">⚡ BREAK</span>
                </div>
              </div>
            </template>
          </div>
        </template>
      </div>
    </div>

    <!-- 得分录入抽屉 -->
    <GoalDrawer
      v-model="showGoalDrawer"
      :team-label="activeTeam"
      :players="activeTeam === 'A' ? teamAPlayers : teamBPlayers"
      :possession-side="possession"
      @confirm="handleGoalConfirm"
    />

    <!-- 防守盘录入抽屉 -->
    <DefenseDrawer
      v-model="showDefenseDrawer"
      :team-a-label="matchType === 'external' ? '我方' : '队 A'"
      :team-b-label="matchType === 'external' ? '对方' : '队 B'"
      :team-a-players="teamAPlayers"
      :team-b-players="teamBPlayers"
      :possession="possession"
      @confirm="handleDefenseConfirm"
    />

    <!-- 失误录入抽屉 -->
    <TurnoverDrawer
      v-model="showTurnoverPicker"
      :team-a-label="matchType === 'external' ? '我方' : '队 A'"
      :team-b-label="matchType === 'external' ? '对方' : '队 B'"
      :team-a-players="teamAPlayers"
      :team-b-players="teamBPlayers"
      :possession="possession"
      @confirm="handleTurnoverConfirm"
    />

    <!-- 半场确认 Dialog -->
    <van-dialog
      v-model:show="showHalftimeDialog"
      title="进入半场"
      show-cancel-button
      confirm-button-text="确认半场"
      @confirm="confirmHalftime"
    >
      <div class="halftime-dialog">
        <p>当前比分：{{ scoreA }} — {{ scoreB }}</p>
        <p>比赛时间：{{ timerDisplay }}</p>
        <template v-if="possession">
          <p style="color:#ff976a;margin-top:8px">
            &#9888; 下半场将由
            <strong>
              {{ matchType === 'external'
                ? (possession === 'A' ? '对方' : '我方')
                : ('队' + (possession === 'A' ? 'B' : 'A'))
              }}
            </strong>
            先进攻（BAAB 模式）
          </p>
        </template>
        <p v-else style="color:#ff976a;margin-top:8px">&#9888; 下半场进攻方将自动翻转（BAAB 模式）</p>
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import GoalDrawer from '@/components/GoalDrawer.vue'
import DefenseDrawer from '@/components/DefenseDrawer.vue'
import TurnoverDrawer from '@/components/TurnoverDrawer.vue'
import api from '@/api'
import { useMatchPrediction } from '@/composables/useMatchPrediction'
import { useLiveTimer } from '@/composables/useLiveTimer'
import { useGenderRatio } from '@/composables/useGenderRatio'
import { usePossession } from '@/composables/usePossession'
import { useLiveEvents, type PlayerLite } from '@/composables/useLiveEvents'
import { useLiveDraftSync, type DraftEventPayload } from '@/composables/useLiveDraftSync'
import { useLiveDraftBootstrap } from '@/composables/useLiveDraftBootstrap'
import { useLiveDraftPageGuards } from '@/composables/useLiveDraftPageGuards'

interface Player {
  id: number
  username: string
  display_name: string | null
}

const route = useRoute()
const router = useRouter()

// Props：从路由 state 或 query 获取队伍信息
const teamAIds = ref<number[]>([])
const teamBIds = ref<number[]>([])
const teamAPlayers = ref<Player[]>([])
const teamBPlayers = ref<Player[]>([])
const allPlayers = computed(() => [...teamAPlayers.value, ...teamBPlayers.value])

const scoreA = ref(0)
const scoreB = ref(0)
const isHalftime = ref(false)
const draftId = ref<number | null>(null)
const nextSeq = ref(1)
const {
  pendingQueue,
  loadPendingQueue,
  clearPendingQueue,
  clearLockHeartbeat,
  startLockHeartbeat,
  releaseDraftLock,
  syncPendingQueue,
  pushEvent,
} = useLiveDraftSync(draftId, nextSeq)
const { restoreFromDraft, initNewDraft } = useLiveDraftBootstrap()
useLiveDraftPageGuards({ pendingQueue, clearLockHeartbeat, releaseDraftLock })

const { prediction, predictionLoading, fetchPrediction } = useMatchPrediction()

// 开赛前配置
const showSetupDialog = ref(false)
const matchType = ref<'internal' | 'external'>('internal')
const liveNotes = ref('')

const { elapsedSeconds, timerPaused, timerDisplay, startTimer, stopTimer, toggleTimer } = useLiveTimer()
const { useGender, abbaFirstRatio, abbaPhase, currentGenderRatio, advancePoint, switchForSecondHalf } = useGenderRatio()
const { possession, transferOnTurnover, transferAfterGoal, transferOnDefenseSuccess, flipForSecondHalf } = usePossession()
const { events, addTurnover, addGoal, addExternalOpponentGoal, addDefense, addHalftime } = useLiveEvents()

function startMatch() {
  if (!liveNotes.value.trim()) {
    showToast('请先填写比赛备注再开始比赛')
    showSetupDialog.value = true
    return
  }
  startTimer()
}

// 抽屉
const showGoalDrawer = ref(false)
const showDefenseDrawer = ref(false)
const showTurnoverPicker = ref(false)
const activeTeam = ref<'A' | 'B'>('A')

function openGoalDrawer(team: 'A' | 'B') {
  activeTeam.value = team
  showGoalDrawer.value = true
}

function openDefenseDrawer() {
  showDefenseDrawer.value = true
}

function openTurnoverPicker() {
  showTurnoverPicker.value = true
}

function handleTurnoverConfirm(playerId: number) {
  const player = allPlayers.value.find(p => p.id === playerId)
  if (!player) return
  const side = teamAIds.value.includes(player.id) ? 'A' : 'B'
  transferOnTurnover(side)
  addTurnover({ side, player: player as PlayerLite, elapsed: timerDisplay.value })
  void pushEvent({
    event_type: 'turnover',
    team_side: side,
    player_id: player.id,
    assist_player_id: null,
    is_break: false,
    elapsed_seconds: elapsedSeconds.value,
    payload: { score_a: scoreA.value, score_b: scoreB.value },
  })
}

// 半场
const showHalftimeDialog = ref(false)

function handleHalftime() {
  timerPaused.value = true
  showHalftimeDialog.value = true
}

function confirmHalftime() {
  isHalftime.value = true
  flipForSecondHalf()
  switchForSecondHalf()
  addHalftime({ elapsed: timerDisplay.value, scoreA: scoreA.value, scoreB: scoreB.value })
  void pushEvent({
    event_type: 'halftime',
    team_side: null,
    player_id: null,
    assist_player_id: null,
    is_break: false,
    elapsed_seconds: elapsedSeconds.value,
    payload: { score_a: scoreA.value, score_b: scoreB.value, is_halftime: true },
  })
  showToast('半场已记录，进攻方已翻转，性别比序列已切换')
}

// 得分确认
function handleGoalConfirm(scorerId: number, assistId: number | null, isBreak: boolean) {
  const team = activeTeam.value
  const player = team === 'A'
    ? teamAPlayers.value.find(p => p.id === scorerId)
    : teamBPlayers.value.find(p => p.id === scorerId)
  const assistPlayer = assistId != null
    ? allPlayers.value.find(p => p.id === assistId)
    : null

  if (team === 'A') scoreA.value++
  else scoreB.value++

  transferAfterGoal(team)
  advancePoint()
  addGoal({
    side: team,
    scorer: (player ?? null) as PlayerLite | null,
    assist: (assistPlayer ?? null) as PlayerLite | null,
    isBreak,
    elapsed: timerDisplay.value,
    scoreA: scoreA.value,
    scoreB: scoreB.value,
  })
  void pushEvent({
    event_type: 'goal',
    team_side: team,
    player_id: scorerId,
    assist_player_id: assistId,
    is_break: isBreak,
    elapsed_seconds: elapsedSeconds.value,
    payload: { score_a: scoreA.value, score_b: scoreB.value, possession_after: possession.value },
  })
}

// 防守确认
// defender 是守守方（非持盘方），防守成功后盘权转移给守守方
function handleDefenseConfirm(defenderId: number, interceptorId: number | null) {
  const defender = allPlayers.value.find(p => p.id === defenderId)
  const interceptor = interceptorId != null ? allPlayers.value.find(p => p.id === interceptorId) : null
  const side = teamAIds.value.includes(defenderId) ? 'A' : 'B'

  transferOnDefenseSuccess(side)
  addDefense({
    side,
    defender: (defender ?? null) as PlayerLite | null,
    interceptor: (interceptor ?? null) as PlayerLite | null,
    elapsed: timerDisplay.value,
  })
  void pushEvent({
    event_type: 'defense',
    team_side: side,
    player_id: defenderId,
    assist_player_id: interceptorId,
    is_break: false,
    elapsed_seconds: elapsedSeconds.value,
    payload: { score_a: scoreA.value, score_b: scoreB.value, possession_after: possession.value },
  })
}

// 外战对方得分（不选球员，只记录分数和事件）
function handleExternalGoal() {
  scoreB.value++
  transferAfterGoal('B')
  advancePoint()
  addExternalOpponentGoal({ elapsed: timerDisplay.value })
  void pushEvent({
    event_type: 'goal',
    team_side: 'B',
    player_id: null,
    assist_player_id: null,
    is_break: false,
    elapsed_seconds: elapsedSeconds.value,
    payload: { score_a: scoreA.value, score_b: scoreB.value, possession_after: possession.value },
  })
}

async function saveAsDraft() {
  if (!draftId.value) return
  try {
    await syncPendingQueue()
    await api.post(`/matches/drafts/${draftId.value}/save`, {
      elapsed_seconds: elapsedSeconds.value,
      score_a: scoreA.value,
      score_b: scoreB.value,
      is_halftime: isHalftime.value,
      possession: possession.value,
    })
    showToast('已保存为待录入，可在比赛历史继续')
    router.push({ name: 'match-list' })
  } catch {
    showToast('保存失败，请稍后重试')
  }
}

async function abandonDraft() {
  if (!draftId.value) return
  try {
    await showConfirmDialog({
      title: '确认放弃比赛',
      message: '放弃后该实况草稿将被删除，且不会出现在比赛列表中。',
      confirmButtonText: '确认放弃',
      cancelButtonText: '取消',
    })
    await api.post(`/matches/drafts/${draftId.value}/abandon`)
    showToast('已放弃该比赛')
    router.push({ name: 'match-list' })
  } catch (e: any) {
    // 用户取消确认时不提示失败
    if (e && (e.message?.includes?.('cancel') || e.message?.includes?.('close'))) return
    showToast('放弃失败，请稍后重试')
  }
}

// 结束比赛并提交结算
async function handleEnd() {
  stopTimer()
  if (!draftId.value) return
  try {
    await syncPendingQueue()
    await api.post(`/matches/drafts/${draftId.value}/save`, {
      elapsed_seconds: elapsedSeconds.value,
      score_a: scoreA.value,
      score_b: scoreB.value,
      is_halftime: isHalftime.value,
      possession: possession.value,
    })
    await api.post(`/matches/drafts/${draftId.value}/finalize`, { notes: liveNotes.value.trim() })
    clearPendingQueue()
    showToast('比赛已结束并结算')
    if (matchType.value === 'external') {
      router.push({ name: 'match-spirit-score', params: { id: String(draftId.value) } })
    } else {
      router.push({ name: 'match-list' })
    }
  } catch {
    showToast('结束比赛失败，请重试')
  }
}

function handleBack() {
  stopTimer()
  clearLockHeartbeat()
  if (draftId.value) {
    void releaseDraftLock().finally(() => {
      router.back()
    })
    return
  }
  router.back()
}

onMounted(async () => {
  const draftIdFromQuery = Number(route.query.draft_id || 0)
  if (draftIdFromQuery > 0) {
    draftId.value = draftIdFromQuery
    const restored = await restoreFromDraft(draftIdFromQuery, {
      teamAIds,
      teamBIds,
      teamAPlayers,
      teamBPlayers,
      matchType,
      liveNotes,
      scoreA,
      scoreB,
      elapsedSeconds,
      nextSeq,
      isHalftime,
      events,
      fetchPrediction,
      startTimer,
      loadPendingQueue,
      syncPendingQueue,
      startLockHeartbeat,
    })
    if (restored.ok) return

    if (restored.reason === 'locked') {
      const locker = restored.lockedBy ? `（${restored.lockedBy}）` : ''
      showToast(`正在有人录入该比赛${locker}`)
    } else if (restored.reason === 'takeover_required') {
      showToast('该未完成比赛由其他队员创建，请先在列表中接管')
    } else {
      showToast('恢复未完成比赛失败')
    }
    router.replace({ name: 'match-list' })
    return
  }

  const initialized = await initNewDraft({
    draftId,
    teamAIds,
    teamBIds,
    teamAPlayers,
    teamBPlayers,
    matchType,
    liveNotes,
    fetchPrediction,
    loadPendingQueue,
    startLockHeartbeat,
  })
  if (!initialized.ok) {
    if (initialized.reason === 'create_failed') {
      showToast('创建草稿失败，请返回重试')
      router.replace({ name: 'match-list' })
      return
    }
    showToast('缺少开赛信息，请从新建比赛进入')
    router.replace({ name: 'match-new' })
    return
  }

  // 显示开赛配置对话框，用户确认后才启动计时器
  showSetupDialog.value = true
})

</script>

<style scoped>
.live-page {
  min-height: 100dvh;
  background: #f7f8fa;
  padding-bottom: calc(16px + env(safe-area-inset-bottom));
}

.timer-display {
  font-size: 15px;
  font-weight: 700;
  color: #1677ff;
  font-variant-numeric: tabular-nums;
}

.nav-left-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 96px;
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.timer-display.paused {
  color: #ee0a24;
}

.status-bar {
  padding: 8px 16px;
  background: linear-gradient(90deg, #f8fbff 0%, #eef8f1 100%);
  border-bottom: 1px solid rgba(22, 119, 255, 0.08);
  color: #334155;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.status-bar__note {
  white-space: normal;
}

.status-bar__gap {
  display: inline-block;
  width: 12px;
}

.status-bar__gender {
  color: #0f766e;
  font-size: 13px;
}

/* 比分板 */
.scoreboard {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 20px 16px 16px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.scoreboard__team {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.scoreboard__name {
  font-size: 14px;
  color: #646566;
}

.scoreboard__score {
  font-size: 48px;
  font-weight: 800;
  color: #323233;
  font-variant-numeric: tabular-nums;
}

.scoreboard__team--a .scoreboard__score { color: #1677ff; }
.scoreboard__team--b .scoreboard__score { color: #f97316; }

.scoreboard__name {
  font-size: 14px;
  color: #646566;
  display: flex;
  align-items: center;
  gap: 4px;
}

.disc-icon {
  font-size: 18px;
  animation: disc-spin 1.5s linear infinite;
  display: inline-block;
}

@keyframes disc-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 盘权横条提示 */
.possession-hint {
  text-align: center;
  font-size: 14px;
  font-weight: 700;
  padding: 6px 16px;
  letter-spacing: 0.5px;
  border-radius: 0;
}
.possession-hint--A {
  background: linear-gradient(90deg, #dbeafe, #eff6ff);
  color: #1d4ed8;
  border-left: 4px solid #1677ff;
}
.possession-hint--B {
  background: linear-gradient(90deg, #ffedd5, #fff7ed);
  color: #c2410c;
  border-right: 4px solid #f97316;
}

.scoreboard__sep {
  font-size: 32px;
  color: #c8c9cc;
}

/* 操作按钮行 */
.action-bar {
  display: flex;
  justify-content: center;
  gap: 8px;
  padding: 8px 12px 4px;
  flex-wrap: wrap;
}

/* 主得分按钮行 */
.action-bar--main {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  padding: 10px 12px 4px;
}

.score-btn {
  height: 52px;
  border-radius: 14px;
  font-size: 15px;
  font-weight: 700;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: none;
  gap: 2px;
}

.score-btn--a {
  background: linear-gradient(135deg, #1677ff, #2563eb);
  color: #fff;
  box-shadow: 0 4px 14px rgba(22, 119, 255, 0.35);
}

.score-btn--b {
  background: linear-gradient(135deg, #f97316, #ea580c);
  color: #fff;
  box-shadow: 0 4px 14px rgba(249, 115, 22, 0.35);
}

.score-btn__icon {
  font-size: 18px;
  line-height: 1;
}

.score-btn__label {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.action-bar--secondary {
  padding-top: 0;
  padding-bottom: 10px;
}

/* 时间轴 */
.timeline {
  padding: 8px 0 16px;
}

.timeline__empty {
  padding: 32px 0;
}

.timeline__list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 0 8px;
}

/* 每得一分后的分割线 */
.timeline__point-divider {
  display: flex;
  align-items: center;
  margin: 6px 0 2px;
  padding: 0 4px;
}
.timeline__point-label {
  flex: 1;
  text-align: center;
  font-size: 12px;
  color: #969799;
  position: relative;
}
.timeline__point-label::before,
.timeline__point-label::after {
  content: '';
  position: absolute;
  top: 50%;
  width: 20%;
  height: 1px;
  background: #ebedf0;
}
.timeline__point-label::before { left: 0; }
.timeline__point-label::after { right: 0; }

.timeline__item {
  display: flex;
  align-items: center;
  gap: 0;
  min-height: 40px;
}

.timeline__system-event {
  flex: 1;
  display: flex;
  justify-content: center;
  padding: 6px 0;
}

.timeline__spacer {
  flex: 1;
}

.timeline__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  margin: 0 4px;
}

.timeline__dot--a { background: #1677ff; }
.timeline__dot--b { background: #07c160; }

.timeline__bubble {
  flex: 1;
  padding: 6px 10px;
  border-radius: 10px;
  font-size: 13px;
}

.timeline__bubble--a {
  background: #e8f4ff;
  color: #1677ff;
  text-align: left;
}

.timeline__bubble--b {
  background: #e8fff2;
  color: #07c160;
  text-align: right;
}

.timeline__bubble-time {
  font-size: 11px;
  opacity: 0.7;
  font-variant-numeric: tabular-nums;
}

.break-badge {
  display: inline-block;
  margin-left: 5px;
  background: #ee0a24;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
  letter-spacing: 0.5px;
  vertical-align: middle;
}

/* 半场 dialog */
.halftime-dialog {
  padding: 16px 20px;
  font-size: 14px;
  color: #323233;
}

.halftime-dialog p {
  margin: 6px 0;
}

/* 性别比 + 进攻方信息条 */
.info-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 6px 16px;
  background: #f0f5ff;
  font-size: 13px;
  flex-wrap: wrap;
}

.info-bar__gender {
  color: #555;
}

.info-bar__possession {
  font-weight: 700;
  padding: 2px 10px;
  border-radius: 10px;
}

.live-note-bar {
  margin: 8px 16px 4px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #fff7e6;
  color: #8a6d3b;
  font-size: 13px;
  line-height: 1.5;
}

.possession--A {
  background: #dbeafe;
  color: #1677ff;
}

.possession--B {
  background: #dcfce7;
  color: #07c160;
}

/* 胜率预测卡 */
.predict-card {
  margin-top: 12px;
  padding: 10px 14px;
  background: #f0f8ff;
  border-radius: 8px;
  border: 1px solid #c3d9f5;
}

.predict-card__title {
  font-size: 13px;
  font-weight: 700;
  color: #1677ff;
  margin-bottom: 8px;
}

.predict-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.predict-bar__label {
  width: 44px;
  font-size: 12px;
  color: #646566;
  text-align: right;
  flex-shrink: 0;
}

.predict-bar__track {
  flex: 1;
  height: 8px;
  background: #e5e8ec;
  border-radius: 4px;
  overflow: hidden;
}

.predict-bar__fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
}

.predict-bar__fill--a { background: #1677ff; }
.predict-bar__fill--b { background: #07c160; }

.predict-bar__pct {
  width: 44px;
  font-size: 12px;
  font-weight: 700;
  color: #323233;
  flex-shrink: 0;
}

.predict-card__quality {
  text-align: center;
  font-size: 12px;
  color: #969799;
  margin-top: 4px;
}
</style>
