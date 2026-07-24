<script setup lang="ts">
/**
 * LineDivisionWizard — 统一分 line 向导（全屏 Popup）
 *
 * Props:
 *   visible      : v-model控制显隐
 *   matchType    : 'game' | 'internal' | 'training'
 *   eventId      : 关联日程事件 ID（schedule 模式）
 *   mode         : 'schedule' | 'match'（默认 match）
 *   initialAttendingIds : 初始出勤人员 ID 列表
 *
 * Emits:
 *   update:visible
 *   confirm(result: LineDivisionResult)
 */
import { ref, computed, onMounted, watch } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import {
  useLineDivisionWizard,
  type WizardMatchType,
  type WizardMode,
  type LineDivisionResult,
} from '@/composables/useLineDivisionWizard'
import LDWAttendanceTab from './LDWAttendanceTab.vue'
import LDWLineTab from './LDWLineTab.vue'
import LDWAnalysisTab from './LDWAnalysisTab.vue'

// ─── Props & Emits ────────────────────────────────────────────────────────────
const props = withDefaults(defineProps<{
  visible: boolean
  matchType: WizardMatchType
  eventId?: number
  /** 仅用于加载出勤信息（match 模式下关联了日程可传此字段） */
  attendanceEventId?: number
  mode?: WizardMode
  initialAttendingIds?: number[]
}>(), {
  mode: 'match',
  initialAttendingIds: () => [],
})

const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void
  (e: 'confirm', result: LineDivisionResult): void
}>()

// ─── 核心 Composable ──────────────────────────────────────────────────────────
const wizard = useLineDivisionWizard({
  matchType: props.matchType,
  eventId: props.eventId,
  attendanceEventId: props.attendanceEventId,
  mode: props.mode,
  initialAttendingIds: props.initialAttendingIds,
})

// ─── Tab 配置 ─────────────────────────────────────────────────────────────────
const TAB_ORDER: Array<{ key: typeof wizard.activeTab.value; label: string; icon: string }> = [
  { key: 'attendance', label: '出勤选择', icon: 'friends-o' },
  { key: 'line',       label: '分Line',   icon: 'flag-o'     },
  { key: 'analysis',   label: '分析报告', icon: 'bar-chart-o' },
  { key: 'confirm',    label: '确认',     icon: 'passed'      },
]

const activeTabIndex = computed(() => TAB_ORDER.findIndex(t => t.key === wizard.activeTab.value))

function goToTab(key: typeof wizard.activeTab.value) {
  wizard.activeTab.value = key
}

// ─── 确认 ─────────────────────────────────────────────────────────────────────
function handleConfirm() {
  const result = wizard.buildResult()
  // 基础校验
  if (props.matchType === 'game') {
    if (!result.oLineIds.length && !result.dLine1Ids.length) {
      showToast('请先分配 O line 和 D line 球员')
      return
    }
  } else if (props.matchType === 'internal') {
    if (!result.teamAIds.length || !result.teamBIds.length) {
      showToast('内战需要分配队A和队B')
      return
    }
    const overlap = result.teamAIds.filter(id => result.teamBIds.includes(id))
    if (overlap.length > 0) {
      showToast(`有 ${overlap.length} 名球员同时出现在两队，请调整`)
      return
    }
  }
  emit('confirm', result)
  emit('update:visible', false)
}

async function handleClose() {
  if (props.mode === 'match') {
    try {
      await showConfirmDialog({ title: '退出分 line 向导', message: '当前配置不会被保存，确认退出？' })
    } catch { return }
  }
  emit('update:visible', false)
}

// ─── 事件转发 ─────────────────────────────────────────────────────────────────
// Attendance Tab events
function onUpdateAttendingIds(ids: number[]) {
  wizard.attendingIds.value = ids
}
function onSelectByStatus(statuses: ('yes' | 'leave' | 'sdl' | 'not_submitted')[]) {
  wizard.selectAttendingByStatus(statuses)
}

// Line Tab events
function onAddLine(name: string, type: 'o_line' | 'd_line' | 'line') {
  if (wizard.division.value) wizard.addLine(name, type)
  else wizard.addLocalLine()
}
function onDeleteLine(lineId: number | string) {
  if (typeof lineId === 'number') wizard.deleteLine(lineId)
  else wizard.removeLocalLine(lineId)
}
function onTogglePlayer(lineId: number | string, playerId: number) {
  if (typeof lineId === 'number') wizard.togglePlayerInLine(lineId, playerId)
  else wizard.togglePlayerInLocalLine(lineId, playerId)
}
function onAutoAssign(method: 'auto_balanced' | 'auto_strong_to_weak', numLines: number) {
  if (props.mode === 'schedule' && wizard.division.value) {
    wizard.scheduleAutoAssign(method, numLines)
  } else {
    // 在match模式下，先确保有足够的line
    const existingLines = wizard.localLines.value.length
    
    // 添加缺失的line
    for (let i = existingLines; i < numLines; i++) {
      const lineName = props.matchType === 'game' 
        ? (i === 0 ? 'O Line' : `D Line ${i}`)
        : `Line ${i + 1}`
      const lineType = props.matchType === 'game'
        ? (i === 0 ? 'o_line' : 'd_line' as const)
        : 'line' as const
      wizard.addLine(lineName, lineType)
    }
    
    wizard.localAutoAssign(method)
  }
}
function onSmartAnalyze() {
  void (async () => {
    await wizard.runSmartExternalAnalysis(true)
    // 分析完成后自动跳转到分析报告 Tab
    wizard.activeTab.value = 'analysis'
  })()
}
function onInitDivision(rounds: number) {
  wizard.initDivision(rounds)
}

// Analysis Tab event
async function onRunAnalysis() {
  if (props.matchType === 'game') {
    // 一键分析始终基于当前分line配置，手动调整后也能实时刷新
    await wizard.buildLocalGameAnalysis()
  } else if (props.matchType === 'internal') {
    wizard.runSmartGroup()
  }
  // training: 无需调用 API，直接显示本地数据
}

// ─── 初始化 ───────────────────────────────────────────────────────────────────
onMounted(() => {
  wizard.init()
})

// 当向导重新打开时重新初始化
watch(() => props.visible, (v) => {
  if (v) wizard.init()
})

// 当 initialAttendingIds 变化时同步
watch(() => props.initialAttendingIds, (ids) => {
  if (ids && ids.length > 0 && wizard.attendingIds.value.length === 0) {
    wizard.attendingIds.value = [...ids]
  }
})

// 将 wizard.autoNumLines 放到内部（composable 里没有，需要在这里包一下）
const autoNumLinesLocal = ref(2)
const confirmAttendCollapsed = ref<string[]>([])

// ─── Confirm Tab 辅助 ─────────────────────────────────────────────────────────
function confirmPlayer(pid: number) {
  return wizard.allPlayers.value.find(p => p.id === pid)
}
function confirmPlayerLabel(pid: number): string {
  const p = confirmPlayer(pid)
  if (!p) return `#${pid}`
  const name = p.display_name || p.username
  return p.jersey_number != null ? `#${p.jersey_number} ${name}` : name
}
function genderSymbol(pid: number): string {
  const g = confirmPlayer(pid)?.gender
  return g === 'M' ? '♂' : g === 'F' ? '♀' : ''
}
function genderColorClass(pid: number): string {
  const g = confirmPlayer(pid)?.gender
  return g === 'M' ? 'gender-m' : g === 'F' ? 'gender-f' : ''
}
function confirmRating(pid: number): string {
  const r = confirmPlayer(pid)?.conservative_rating
  return r != null ? r.toFixed(0) : ''
}
function lineTypeLabel(type: string): string {
  if (type === 'o_line') return 'O Line'
  if (type === 'd_line') return 'D Line'
  return 'Line'
}
function lineTypeClass(type: string): string {
  if (type === 'o_line') return 'line-badge--o'
  if (type === 'd_line') return 'line-badge--d'
  return 'line-badge--n'
}
// 计算 line 的平均能力值
function lineAvgRating(playerIds: number[]): string {
  if (!playerIds.length) return '—'
  const sum = playerIds.reduce((s, pid) => {
    return s + (confirmPlayer(pid)?.conservative_rating ?? 0)
  }, 0)
  return (sum / playerIds.length).toFixed(1)
}
</script>

<template>
  <van-popup
    :show="visible"
    position="bottom"
    round
    :style="{ height: '96vh', display: 'flex', flexDirection: 'column' }"
    @update:show="emit('update:visible', $event)"
  >
    <!-- 顶部导航栏 -->
    <div class="wizard-header">
      <div class="wizard-header__left">
        <van-icon name="cross" size="20" color="#93c5fd" @click="handleClose" />
      </div>
      <div class="wizard-header__title">
        {{ matchType === 'game' ? '外战' : matchType === 'internal' ? '内战' : '训练' }} 分 line 向导
      </div>
      <div class="wizard-header__right">
        <van-button
          v-if="wizard.activeTab.value === 'confirm'"
          size="small"
          type="primary"
          @click="handleConfirm"
        >确认应用</van-button>
        <span v-else style="width: 60px" />
      </div>
    </div>

    <!-- Tab 导航 -->
    <div class="wizard-tabs">
      <div
        v-for="tab in TAB_ORDER"
        :key="tab.key"
        class="wizard-tab"
        :class="{ active: wizard.activeTab.value === tab.key }"
        @click="goToTab(tab.key)"
      >
        <van-icon :name="tab.icon" size="16" />
        <span>{{ tab.label }}</span>
      </div>
    </div>

    <!-- Tab 内容区 -->
    <div class="wizard-body">

      <!-- Tab 0: 出勤选择 -->
      <LDWAttendanceTab
        v-show="wizard.activeTab.value === 'attendance'"
        :all-players="wizard.allPlayers.value"
        :attending-ids="wizard.attendingIds.value"
        :attendance-map="wizard.attendanceMap.value"
        :match-type="matchType"
        :loading-players="wizard.loadingPlayers.value"
        @update:attending-ids="onUpdateAttendingIds"
        @select-by-status="onSelectByStatus"
        @clear-all="wizard.clearAttending"
        @add-guest="wizard.addGuest"
        @remove-guest="wizard.removeGuest"
      />

      <!-- Tab 1: 分 Line -->
      <LDWLineTab
        v-show="wizard.activeTab.value === 'line'"
        :all-players="wizard.allPlayers.value"
        :attending-ids="wizard.attendingIds.value"
        :attendance-map="wizard.attendanceMap.value"
        :match-type="matchType"
        :mode="mode"
        :division="wizard.division.value"
        :current-round="wizard.currentRound.value"
        :total-rounds="wizard.totalRounds.value"
        :active-line-id="wizard.activeLineId.value"
        :loading-division="wizard.loadingDivision.value"
        :local-lines="wizard.localLines.value"
        :local-rounds="wizard.localRounds.value"
        :current-local-round="wizard.currentLocalRound.value"
        :d-line-count="wizard.dLineCount.value"
        :max-line-size="wizard.maxLineSize.value"
        :templates="wizard.templates.value"
        :supports-templates="wizard.supportsTemplates"
        :loading-templates="wizard.loadingTemplates.value"
        @update:active-line-id="wizard.activeLineId.value = $event"
        @update:current-round="wizard.currentRound.value = $event"
        @update:current-local-round="wizard.currentLocalRound.value = $event"
        @update:d-line-count="wizard.dLineCount.value = $event"
        @update:max-line-size="wizard.maxLineSize.value = $event"
        @init-division="onInitDivision"
        @add-round="wizard.addRound"
        @delete-round="wizard.deleteRound"
        @add-line="onAddLine"
        @delete-line="onDeleteLine"
        @toggle-player="onTogglePlayer"
        @add-local-line="wizard.addLocalLine"
        @remove-local-line="wizard.removeLocalLine"
        @add-local-round="wizard.addLocalRound"
        @auto-assign="onAutoAssign"
        @smart-analyze="onSmartAnalyze"
        @save-template="wizard.saveTemplate"
        @apply-template="wizard.applyTemplate"
      />

      <!-- Tab 2: 分析报告 -->
      <LDWAnalysisTab
        v-show="wizard.activeTab.value === 'analysis'"
        :match-type="matchType"
        :all-players="wizard.allPlayers.value"
        :attending-ids="wizard.attendingIds.value"
        :analysis-result="wizard.analysisResult.value"
        :analysis-loading="wizard.analysisLoading.value"
        :local-lines="wizard.localLines.value"
        :current-local-round="wizard.currentLocalRound.value"
        :auto-group-result="wizard.autoGroupResult.value"
        @run-analysis="onRunAnalysis"
      />

      <!-- Tab 3: 确认 -->
      <div v-show="wizard.activeTab.value === 'confirm'" class="confirm-tab">
        <!-- 顶部标题 banner -->
        <div class="confirm-banner">
          <div class="confirm-banner__icon">🏆</div>
          <div>
            <div class="confirm-banner__title">
              {{ matchType === 'game' ? '外战' : matchType === 'internal' ? '内战' : '训练' }} 分 Line 方案
            </div>
            <div class="confirm-banner__sub">出勤 {{ wizard.attendingIds.value.length }} 人 · 请确认无误后提交</div>
          </div>
        </div>

        <!-- Line 摘要（match 模式） -->
        <template v-if="mode === 'match'">
          <template v-if="matchType === 'game'">
            <div
              v-for="line in wizard.localLines.value"
              :key="line.key"
              class="confirm-line-card"
            >
              <!-- Line 标题行 -->
              <div class="confirm-line-header">
                <span :class="['line-badge', lineTypeClass(line.line_type)]">
                  {{ lineTypeLabel(line.line_type) }}
                </span>
                <span class="confirm-line-name">{{ line.line_name }}</span>
                <span class="confirm-line-meta">
                  {{ line.playerIds.length }} 人
                  <span v-if="line.playerIds.length" class="confirm-line-avg">· avg {{ lineAvgRating(line.playerIds) }}</span>
                </span>
              </div>
              <!-- 球员卡片网格 -->
              <div class="confirm-player-grid">
                <div v-for="pid in line.playerIds" :key="pid" :class="['confirm-player-card', genderColorClass(pid)]">
                  <span :class="['cpcard__gender', genderColorClass(pid)]">{{ genderSymbol(pid) }}</span>
                  <span class="cpcard__name">{{ confirmPlayerLabel(pid) }}</span>
                  <span v-if="confirmRating(pid)" class="cpcard__rating">{{ confirmRating(pid) }}</span>
                </div>
                <div v-if="!line.playerIds.length" class="confirm-empty-line">暂无球员</div>
              </div>
            </div>
          </template>
          <template v-else-if="matchType === 'internal'">
            <div
              v-for="line in wizard.localLines.value.filter(l => l.round_number === wizard.currentLocalRound.value)"
              :key="line.key"
              class="confirm-line-card"
            >
              <div class="confirm-line-header">
                <span class="line-badge line-badge--n">{{ line.line_name }}</span>
                <span class="confirm-line-meta">
                  {{ line.playerIds.length }} 人
                  <span v-if="line.playerIds.length" class="confirm-line-avg">· avg {{ lineAvgRating(line.playerIds) }}</span>
                </span>
              </div>
              <div class="confirm-player-grid">
                <div v-for="pid in line.playerIds" :key="pid" :class="['confirm-player-card', genderColorClass(pid)]">
                  <span :class="['cpcard__gender', genderColorClass(pid)]">{{ genderSymbol(pid) }}</span>
                  <span class="cpcard__name">{{ confirmPlayerLabel(pid) }}</span>
                  <span v-if="confirmRating(pid)" class="cpcard__rating">{{ confirmRating(pid) }}</span>
                </div>
                <div v-if="!line.playerIds.length" class="confirm-empty-line">暂无球员</div>
              </div>
            </div>
          </template>
        </template>

        <!-- schedule 模式 line 摘要 -->
        <template v-if="mode === 'schedule' && wizard.division.value">
          <div
            v-for="line in wizard.currentLines.value"
            :key="line.id"
            class="confirm-line-card"
          >
            <div class="confirm-line-header">
              <span :class="['line-badge', lineTypeClass(line.line_type)]">{{ lineTypeLabel(line.line_type) }}</span>
              <span class="confirm-line-name">{{ line.line_name }}</span>
              <span class="confirm-line-meta">
                {{ line.players.length }} 人
                <span v-if="line.players.length" class="confirm-line-avg">· avg {{ (line.players.reduce((s, p) => s + p.conservative_rating, 0) / line.players.length).toFixed(1) }}</span>
              </span>
            </div>
            <div class="confirm-player-grid">
              <div
                v-for="p in line.players"
                :key="p.player_id"
                :class="['confirm-player-card', p.gender === 'M' ? 'gender-m' : p.gender === 'F' ? 'gender-f' : '']"
              >
                <span
                  :class="['cpcard__gender', p.gender === 'M' ? 'gender-m' : p.gender === 'F' ? 'gender-f' : '']"
                >{{ p.gender === 'M' ? '♂' : p.gender === 'F' ? '♀' : '' }}</span>
                <span class="cpcard__name">
                  {{ p.jersey_number != null ? `#${p.jersey_number} ` : '' }}{{ p.display_name || p.player_name }}
                </span>
                <span class="cpcard__rating">{{ p.conservative_rating.toFixed(0) }}</span>
              </div>
            </div>
          </div>
        </template>

        <!-- 出勤总览（折叠展示） -->
        <van-collapse v-model="confirmAttendCollapsed" class="confirm-attend-collapse">
          <van-collapse-item name="attend" :title="`全部出勤球员（${wizard.attendingIds.value.length} 人）`">
            <div class="confirm-player-grid">
              <div
                v-for="pid in wizard.attendingIds.value"
                :key="pid"
                class="confirm-player-card"
              >
                <span :class="['cpcard__gender', genderColorClass(pid)]">{{ genderSymbol(pid) }}</span>
                <span class="cpcard__name">{{ confirmPlayerLabel(pid) }}</span>
              </div>
            </div>
          </van-collapse-item>
        </van-collapse>

        <div class="confirm-actions">
          <van-button block type="primary" @click="handleConfirm">✓ 确认应用</van-button>
          <van-button block plain style="margin-top: 8px" @click="goToTab('line')">← 返回调整</van-button>
        </div>
      </div>

    </div>
  </van-popup>
</template>

<style scoped>
/* 整体结构 */
.wizard-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px 8px; border-bottom: 1px solid #1e3a5f; background: #0d1f35; flex-shrink: 0;
}
.wizard-header__left { width: 40px; cursor: pointer; }
.wizard-header__title { color: #eff6ff; font-weight: 700; font-size: 15px; }
.wizard-header__right { width: 60px; display: flex; justify-content: flex-end; }

.wizard-tabs {
  display: flex; background: #0f2035; border-bottom: 1px solid #1e3a5f; flex-shrink: 0;
}
.wizard-tab {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 3px; padding: 8px 4px; cursor: pointer;
  color: #6f8cab; font-size: 11px; transition: all .15s;
}
.wizard-tab.active {
  color: #60a5fa; border-bottom: 2px solid #60a5fa;
}

.wizard-body {
  flex: 1; overflow-y: auto; padding: 12px 16px;
  background: linear-gradient(180deg, #0b1a2b 0%, #0a1628 100%);
}

/* 确认 Tab */
.confirm-tab { padding-bottom: 16px; }

.confirm-banner {
  display: flex; align-items: center; gap: 12px;
  background: linear-gradient(135deg, #0f2a4a 0%, #1a3a60 100%);
  border: 1px solid #2d6abf; border-radius: 14px;
  padding: 14px 16px; margin-bottom: 14px;
}
.confirm-banner__icon { font-size: 28px; line-height: 1; }
.confirm-banner__title {
  color: #eff6ff; font-weight: 700; font-size: 15px; margin-bottom: 3px;
}
.confirm-banner__sub { color: #93c5fd; font-size: 12px; }

.confirm-line-card {
  background: #0f2035; border: 1px solid #1e3a5f; border-radius: 12px;
  padding: 10px 12px; margin-bottom: 10px;
}
.confirm-line-header {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 10px; padding-bottom: 8px;
  border-bottom: 1px solid #1e3a5f;
}
.line-badge {
  padding: 2px 10px; border-radius: 20px;
  font-size: 12px; font-weight: 700; letter-spacing: .5px; white-space: nowrap;
}
.line-badge--o { background: #1a3a60; color: #60a5fa; border: 1px solid #3b82f6; }
.line-badge--d { background: #14362a; color: #4ade80; border: 1px solid #22c55e; }
.line-badge--n { background: #2a1f4a; color: #c084fc; border: 1px solid #a855f7; }

.confirm-line-name { color: #e2e8f0; font-weight: 600; font-size: 13px; flex: 1; }
.confirm-line-meta { color: #6f8cab; font-size: 12px; white-space: nowrap; }
.confirm-line-avg { color: #ffd54f; }

.confirm-player-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
  gap: 7px;
}
.confirm-player-card {
  display: flex; align-items: center; gap: 5px;
  background: #152841; border: 1px solid #244160; border-radius: 10px;
  padding: 6px 8px; min-width: 0; overflow: hidden;
  transition: border-color .15s;
}
.confirm-player-card.gender-m { border-color: #1d4a7a; }
.confirm-player-card.gender-f { border-color: #6b2c5a; }

.cpcard__gender { font-size: 13px; font-weight: 700; flex-shrink: 0; }
.cpcard__name {
  color: #e2e8f0; font-size: 12px; font-weight: 600;
  flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.cpcard__rating {
  color: #ffd54f; font-size: 10px; font-weight: 700;
  background: rgba(255,213,79,.12); border-radius: 4px;
  padding: 1px 4px; flex-shrink: 0;
}

.gender-m { color: #60a5fa; }
.gender-f { color: #f472b6; }

.confirm-empty-line {
  color: #6f8cab; font-size: 12px; text-align: center;
  padding: 12px 0; grid-column: 1 / -1;
}

.confirm-attend-collapse {
  margin-bottom: 10px; border-radius: 12px; overflow: hidden;
}
:deep(.confirm-attend-collapse .van-collapse-item__content) {
  background: #0f2035; padding: 8px 12px;
}
:deep(.confirm-attend-collapse .van-cell) {
  background: #0f2035; color: #90caf9; font-size: 13px; font-weight: 600;
}
:deep(.confirm-attend-collapse .van-cell::after) { border-color: #1e3a5f; }

.confirm-actions { margin-top: 16px; }
/* 兼容旧的 confirm-chips / confirm-section（保留不破坏 schedule mode 旧路径） */
.confirm-section {
  background: #0f2035; border: 1px solid #1e3a5f; border-radius: 12px; padding: 10px; margin-bottom: 10px;
}
.confirm-section__title {
  color: #90caf9; font-weight: 600; font-size: 13px; margin-bottom: 8px; display: flex; align-items: center; gap: 8px;
}
.confirm-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.confirm-chip {
  background: #152841; border: 1px solid #244160; color: #e2e8f0;
  padding: 3px 8px; border-radius: 8px; font-size: 12px;
}
.empty-hint { color: #6f8cab; font-size: 12px; text-align: center; padding: 12px 0; }

/* van-popup 背景 */
:deep(.van-popup) {
  background: #0b1a2b !important;
}
</style>
