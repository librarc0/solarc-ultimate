<script setup lang="ts">
/**
 * LDWLineTab — 分 Line 操作 Tab
 * 支持三类：game(外战 O/D), internal(内战 A/B 多轮), training(训练 多 Line)
 * schedule 模式：实时 API 持久化
 * match 模式：本地状态，确认时一次性提交
 */
import { ref, computed, toRef } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import {
  type WizardPlayer,
  type WizardMatchType,
  type WizardMode,
  type LocalLine,
  type ScheduleLineRead,
  type AttendanceStatus,
  normalizeAttendance,
  getPlayerLabel,
} from '@/composables/useLineDivisionWizard'
import type { ScheduleLineDivisionRead } from '@/api/schedule'

// ─── Props ────────────────────────────────────────────────────────────────────
const props = defineProps<{
  allPlayers: WizardPlayer[]
  attendingIds: number[]
  attendanceMap: Record<number, AttendanceStatus>
  matchType: WizardMatchType
  mode: WizardMode
  // schedule mode
  division: ScheduleLineDivisionRead | null
  currentRound: number
  totalRounds: number
  activeLineId: number | null
  loadingDivision: boolean
  // match mode
  localLines: LocalLine[]
  localRounds: number
  currentLocalRound: number
  dLineCount: 1 | 2
  maxLineSize: number
  // templates
  templates: Array<{ id: number; event_type: string; template_name: string; line_count: number; updated_at: string }>
  supportsTemplates: boolean
  loadingTemplates: boolean
}>()

const emit = defineEmits<{
  (e: 'update:activeLineId', id: number | null): void
  (e: 'update:currentRound', r: number): void
  (e: 'update:currentLocalRound', r: number): void
  (e: 'update:dLineCount', v: 1 | 2): void
  (e: 'update:maxLineSize', v: number): void
  (e: 'initDivision', rounds: number): void
  (e: 'addRound'): void
  (e: 'deleteRound'): void
  (e: 'addLine', name: string, type: 'o_line' | 'd_line' | 'line'): void
  (e: 'deleteLine', lineId: number | string): void
  (e: 'togglePlayer', lineId: number | string, playerId: number): void
  (e: 'addLocalLine'): void
  (e: 'removeLocalLine', key: string): void
  (e: 'addLocalRound'): void
  (e: 'autoAssign', method: 'auto_balanced' | 'auto_strong_to_weak', numLines: number): void
  (e: 'smartAnalyze'): void
  (e: 'saveTemplate', name: string): void
  (e: 'applyTemplate', id: number): void
}>()

// ─── 状态 ─────────────────────────────────────────────────────────────────────
const keyword = ref('')
const showAutoPanel = ref(false)
// match 模式下本地记录当前激活的 line key（schedule 模式用 props.activeLineId）
const localActiveLineKey = ref<string | null>(null)
const showSaveTemplatePopup = ref(false)
const showLoadTemplatePopup = ref(false)
const autoMethod = ref<'auto_balanced' | 'auto_strong_to_weak'>('auto_balanced')
const autoNumLines = ref(2)
const templateNameInput = ref('')

// ─── 计算属性 ─────────────────────────────────────────────────────────────────
const isScheduleMode = computed(() => props.mode === 'schedule')

/** 当前展示的 lines（schedule 模式 vs match 模式） */
const displayLines = computed(() => {
  if (isScheduleMode.value) {
    const round = props.currentRound
    return (props.division?.lines ?? []).filter(l => l.round_number === round)
  } else {
    const round = props.matchType === 'internal' ? props.currentLocalRound : 1
    return props.localLines.filter(l => l.round_number === round)
  }
})

/** 当前活跃 line */
const currentActiveLine = computed(() => {
  if (isScheduleMode.value) {
    return displayLines.value.find(l => (l as any).id === props.activeLineId) ?? displayLines.value[0] ?? null
  }
  // match 模式：用 localActiveLineKey 定位，找不到时回退到第一条并自动更新 key
  if (localActiveLineKey.value) {
    const found = displayLines.value.find(l => (l as LocalLine).key === localActiveLineKey.value)
    if (found) return found
  }
  const first = displayLines.value[0] ?? null
  if (first) localActiveLineKey.value = (first as LocalLine).key
  return first
})

/** 当前轮已分配球员集合 */
const assignedIds = computed(() => {
  const ids = new Set<number>()
  displayLines.value.forEach((l) => {
    const players = isScheduleMode.value
      ? ((l as ScheduleLineRead).players ?? []).map((p: any) => p.player_id)
      : ((l as LocalLine).playerIds ?? [])
    players.forEach((id: number) => ids.add(id))
  })
  return ids
})

/** 参与本次的球员池（按出勤 + 评分排序） */
const attendingPlayers = computed(() => {
  const attending = new Set(props.attendingIds)
  const kw = keyword.value.trim().toLowerCase()
  return props.allPlayers
    .filter(p => attending.has(p.id))
    .filter(p => !kw || `${p.display_name ?? ''} ${p.username}`.toLowerCase().includes(kw))
    .sort((a, b) => (b.conservative_rating ?? 0) - (a.conservative_rating ?? 0))
})

function getLinePlayerIds(line: ScheduleLineRead | LocalLine): number[] {
  if (isScheduleMode.value) {
    return ((line as ScheduleLineRead).players ?? []).map((p: any) => p.player_id)
  }
  return (line as LocalLine).playerIds ?? []
}

function getLineId(line: ScheduleLineRead | LocalLine): number | string {
  return isScheduleMode.value ? (line as ScheduleLineRead).id : (line as LocalLine).key
}

function lineHasPlayer(line: ScheduleLineRead | LocalLine, pid: number): boolean {
  return getLinePlayerIds(line).includes(pid)
}

function inWhichLine(pid: number): string {
  const found = displayLines.value.find(l => lineHasPlayer(l, pid))
  if (!found) return ''
  return isScheduleMode.value ? (found as ScheduleLineRead).line_name : (found as LocalLine).line_name
}

function handleTogglePlayer(line: ScheduleLineRead | LocalLine, pid: number) {
  emit('togglePlayer', getLineId(line), pid)
}

function handlePoolClick(pid: number) {
  const activeLine = currentActiveLine.value
  if (!activeLine) {
    showToast('请先选择一条 Line')
    return
  }
  if (!lineHasPlayer(activeLine, pid) && assignedIds.value.has(pid)) {
    showToast(`该球员已在 ${inWhichLine(pid)}，点击该 Line 的球员卡可移除`)
    return
  }
  handleTogglePlayer(activeLine, pid)
}

// 初始化 schedule 模式方案
const initRoundsInput = ref(1)
const showInitPanel = ref(false)

async function confirmInit() {
  emit('initDivision', initRoundsInput.value)
  showInitPanel.value = false
}

async function confirmDeleteLine(line: ScheduleLineRead | LocalLine) {
  try {
    await showConfirmDialog({ title: '确认删除', message: `删除 Line「${isScheduleMode.value ? (line as ScheduleLineRead).line_name : (line as LocalLine).line_name}」？` })
    emit('deleteLine', getLineId(line))
  } catch { /* 取消 */ }
}

async function handleDeleteRound() {
  try {
    await showConfirmDialog({ title: '删除本轮', message: '确认删除此轮及其分组？' })
    emit('deleteRound')
  } catch { /* 取消 */ }
}

function autoAssignAndClose() {
  emit('autoAssign', autoMethod.value, autoNumLines.value)
  showAutoPanel.value = false
}

function doSaveTemplate() {
  const name = templateNameInput.value.trim()
  if (!name) { showToast('请输入模板名称'); return }
  emit('saveTemplate', name)
  templateNameInput.value = ''
  showSaveTemplatePopup.value = false
}

function formatTemplateTime(value: string) {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

const isGame = computed(() => props.matchType === 'game')
const isInternal = computed(() => props.matchType === 'internal')
const displayRounds = computed(() => isScheduleMode.value ? props.totalRounds : props.localRounds)
const displayCurrentRound = computed(() => isScheduleMode.value ? props.currentRound : props.currentLocalRound)
const canAddRound = computed(() => isInternal.value && displayRounds.value < 10)
const canDeleteRound = computed(() => isInternal.value && displayRounds.value > 1)

function handleActiveLineClick(lineId: number | string) {
  if (isScheduleMode.value) {
    emit('update:activeLineId', lineId as number)
  } else {
    localActiveLineKey.value = lineId as string
  }
}
</script>

<template>
  <div class="line-tab">
    <van-loading v-if="loadingDivision" type="spinner" vertical style="padding: 24px 0" />
    <template v-else>

      <!-- schedule 模式：无方案时显示初始化 -->
      <template v-if="isScheduleMode && !division">
        <div class="no-plan">
          <p class="empty-hint">暂无分 line 方案</p>
          <van-button size="small" type="primary" block @click="showInitPanel = true">🆕 初始化方案</van-button>
        </div>
        <!-- 初始化面板 -->
        <van-popup v-model:show="showInitPanel" position="bottom" round :style="{ maxHeight: '60vh' }">
          <div class="sheet-body">
            <div class="sheet-title">初始化分 line 方案</div>
            <van-cell-group inset>
              <van-field v-if="isInternal" label="轮数">
                <template #input>
                  <van-stepper v-model="initRoundsInput" :min="1" :max="10" integer />
                </template>
              </van-field>
            </van-cell-group>
            <van-button block type="primary" style="margin-top:12px" @click="confirmInit">确认初始化</van-button>
          </div>
        </van-popup>
      </template>

      <template v-else>
        <!-- 操作栏 -->
        <div class="action-row">
          <van-button size="mini" plain @click="$emit('addLine', isGame ? (displayLines.length === 0 ? 'O Line' : `D Line ${displayLines.length}`) : `Line ${displayLines.length + 1}`, isGame ? (displayLines.length === 0 ? 'o_line' : 'd_line') : 'line')">
            + 新增 Line
          </van-button>
          <van-button v-if="!isGame" size="mini" plain type="primary" @click="showAutoPanel = true">⚡ 自动分配</van-button>
          <van-button v-if="isGame" size="mini" type="primary" plain @click="$emit('smartAnalyze')">🔍 智能O/D分析</van-button>
        </div>

        <!-- 模板工具栏（game / training） -->
        <div v-if="supportsTemplates" class="template-toolbar">
          <div class="template-toolbar__info">
            <div class="template-toolbar__title">模板工具</div>
            <div class="template-toolbar__desc">可保存当前分 line 方案，最多 3 个</div>
          </div>
          <div class="template-toolbar__actions">
            <van-button size="mini" plain type="primary" @click="showSaveTemplatePopup = true">保存为模板</van-button>
            <van-button size="mini" plain @click="showLoadTemplatePopup = true">加载模板</van-button>
          </div>
        </div>

        <!-- 外战：D line 条数 / 每条上限 -->
        <template v-if="isGame && !isScheduleMode">
          <div class="game-config">
            <div class="config-item">
              <span class="config-label">D line 条数</span>
              <van-radio-group :model-value="dLineCount" direction="horizontal" @update:model-value="$emit('update:dLineCount', $event as 1|2)">
                <van-radio :name="1">1 条</van-radio>
                <van-radio :name="2">2 条</van-radio>
              </van-radio-group>
            </div>
            <div class="config-item">
              <span class="config-label">每条上限</span>
              <van-stepper :model-value="maxLineSize" :min="3" :max="20" integer @update:model-value="$emit('update:maxLineSize', $event as number)" />
            </div>
          </div>
        </template>

        <!-- 内战：轮次管理 -->
        <template v-if="isInternal">
          <div class="round-toolbar">
            <span class="round-info">共 <strong>{{ displayRounds }}</strong> 轮</span>
            <div style="display:flex; gap:6px">
              <van-button v-if="canAddRound" size="mini" plain type="primary" @click="$emit('addLocalRound')">+ 增加一轮</van-button>
              <van-button v-if="canDeleteRound" size="mini" plain type="danger" @click="handleDeleteRound">删除本轮</van-button>
            </div>
          </div>
          <van-tabs
            v-if="displayRounds > 1"
            :model-value="displayCurrentRound"
            type="card"
            style="margin-bottom: 8px"
            @update:model-value="isScheduleMode ? $emit('update:currentRound', $event as number) : $emit('update:currentLocalRound', $event as number)"
          >
            <van-tab v-for="r in displayRounds" :key="r" :name="r" :title="`第 ${r} 轮`" />
          </van-tabs>
        </template>

        <!-- Line 卡片列表 -->
        <div class="line-list">
          <div
            v-for="line in displayLines"
            :key="getLineId(line)"
            class="line-card"
            :class="{ active: isScheduleMode ? getLineId(line) === activeLineId : getLineId(line) === localActiveLineKey }"
            @click="handleActiveLineClick(getLineId(line))"
          >
            <div class="line-card__header">
              <div>
                <div class="line-name">
                  {{ isScheduleMode ? (line as any).line_name : (line as LocalLine).line_name }}
                </div>
                <div class="line-subtitle">点选球员池中的球员可快速增删</div>
              </div>
              <van-tag plain :type="(isScheduleMode ? (line as any).line_type : (line as LocalLine).line_type) === 'o_line' ? 'primary' : 'success'">
                {{ getLinePlayerIds(line).length }} 人
              </van-tag>
              <van-icon name="delete-o" color="#e53935" style="cursor:pointer; margin-left:auto" @click.stop="confirmDeleteLine(line)" />
            </div>

            <div v-if="getLinePlayerIds(line).length === 0" class="line-empty">暂无球员</div>
            <div v-else class="assigned-grid">
              <div
                v-for="pid in getLinePlayerIds(line)"
                :key="pid"
                class="assigned-chip"
                @click.stop="handleTogglePlayer(line, pid)"
              >
                <div class="chip-top">
                  <div class="chip-name">{{ getPlayerLabel(allPlayers.find(p => p.id === pid) ?? { id: pid, username: `#${pid}`, display_name: null, conservative_rating: 0, gender: null, jersey_number: null }) }}</div>
                  <span class="chip-rating">{{ (allPlayers.find(p => p.id === pid)?.conservative_rating ?? 0).toFixed(0) }}</span>
                </div>
                <div class="chip-stats" v-if="(allPlayers.find(p => p.id === pid)?.total_matches ?? 0) > 0">
                  居均 {{ ((allPlayers.find(p => p.id === pid)?.total_goals ?? 0) / (allPlayers.find(p => p.id === pid)?.total_matches ?? 1)).toFixed(1) }}进
                  {{ ((allPlayers.find(p => p.id === pid)?.total_assists ?? 0) / (allPlayers.find(p => p.id === pid)?.total_matches ?? 1)).toFixed(1) }}助
                </div>
                <span class="remove-hint">点按移除</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 球员池 -->
        <div class="pool-card">
          <div class="pool-card__title">
            球员池
            <span v-if="currentActiveLine" class="pool-card__target">
              → {{ isScheduleMode ? (currentActiveLine as any).line_name : (currentActiveLine as LocalLine).line_name }}
            </span>
          </div>
          <van-field v-model="keyword" clearable placeholder="搜索球员名" left-icon="search" />
          <div v-if="attendingIds.length === 0" class="line-empty">请先在「出勤选择」Tab 中选好球员</div>
          <div v-else-if="attendingPlayers.length === 0" class="line-empty">没有符合条件的球员</div>
          <div v-else class="pool-grid">
            <div
              v-for="p in attendingPlayers"
              :key="p.id"
              class="pool-player"
              :class="{
                active: currentActiveLine && lineHasPlayer(currentActiveLine, p.id),
                used: !currentActiveLine ? false : !lineHasPlayer(currentActiveLine, p.id) && assignedIds.has(p.id),
              }"
              @click="handlePoolClick(p.id)"
            >
              <div class="pool-player__top">
                <span class="pool-player__name">{{ getPlayerLabel(p) }}</span>
                <span class="rating-badge">{{ p.conservative_rating.toFixed(0) }}</span>
              </div>
              <div class="pool-player__meta">
                <span class="pool-player__status">
                  {{ assignedIds.has(p.id) ? `已在 ${inWhichLine(p.id)}` : '可加入' }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </template>

    <!-- ⚡ 自动分 line 面板 -->
    <van-popup v-model:show="showAutoPanel" position="bottom" round :style="{ maxHeight: '80vh', overflowY: 'auto' }">
      <div class="sheet-body">
        <div class="sheet-title">⚡ 自动分 line</div>
        <van-cell-group inset>
          <van-field label="Line 数量">
            <template #input>
              <van-stepper v-model="autoNumLines" :min="2" :max="8" integer />
            </template>
          </van-field>
          <van-field label="分配方式" name="method">
            <template #input>
              <van-radio-group v-model="autoMethod" direction="horizontal">
                <van-radio name="auto_balanced">均衡</van-radio>
                <van-radio name="auto_strong_to_weak">强到弱</van-radio>
              </van-radio-group>
            </template>
          </van-field>
        </van-cell-group>
        <!-- 快速加载模板 -->
        <div v-if="supportsTemplates && templates.length" class="template-quick">
          <div class="template-quick__title">快速加载已有模板</div>
          <div class="template-list">
            <button
              v-for="tpl in templates"
              :key="tpl.id"
              type="button"
              class="template-item"
              @click="$emit('applyTemplate', tpl.id); showAutoPanel = false"
            >
              <span class="template-item__name">{{ tpl.template_name }}</span>
              <span class="template-item__meta">{{ tpl.line_count }} 条 · {{ formatTemplateTime(tpl.updated_at) }}</span>
            </button>
          </div>
        </div>
        <van-button block type="primary" style="margin-top: 12px" @click="autoAssignAndClose">开始自动分配</van-button>
      </div>
    </van-popup>

    <!-- 保存模板 -->
    <van-popup v-model:show="showSaveTemplatePopup" position="bottom" round :style="{ maxHeight: '60vh' }">
      <div class="sheet-body">
        <div class="sheet-title">🗂️ 保存当前为模板</div>
        <div class="sheet-subtitle">每队最多保留 3 个模板</div>
        <van-cell-group inset>
          <van-field v-model="templateNameInput" label="模板名称" maxlength="50" placeholder="例：主力版 / 周三训练A" clearable />
        </van-cell-group>
        <van-button block type="primary" style="margin-top: 12px" @click="doSaveTemplate">保存模板</van-button>
      </div>
    </van-popup>

    <!-- 加载模板 -->
    <van-popup v-model:show="showLoadTemplatePopup" position="bottom" round :style="{ maxHeight: '80vh', overflowY: 'auto' }">
      <div class="sheet-body">
        <div class="sheet-title">📥 加载模板</div>
        <div v-if="loadingTemplates" class="empty-hint">加载中…</div>
        <div v-else-if="templates.length === 0" class="empty-hint">暂无模板，请先保存一个</div>
        <div v-else class="template-list">
          <button
            v-for="tpl in templates"
            :key="tpl.id"
            type="button"
            class="template-item"
            @click="$emit('applyTemplate', tpl.id); showLoadTemplatePopup = false"
          >
            <span class="template-item__name">{{ tpl.template_name }}</span>
            <span class="template-item__meta">{{ tpl.line_count }} 条 · {{ formatTemplateTime(tpl.updated_at) }}</span>
          </button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<style scoped>
.line-tab { padding: 0 0 16px; }
.no-plan { padding: 20px; text-align: center; }
.empty-hint { color: #6f8cab; font-size: 12px; text-align: center; padding: 16px 0; }
.action-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.game-config { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 10px; }
.config-item { display: flex; align-items: center; gap: 8px; }
.config-label { color: #b7d2ee; font-size: 12px; white-space: nowrap; }
.round-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px; flex-wrap: wrap; gap: 6px;
}
.round-info { color: #dbeafe; font-size: 12px; }
.template-toolbar {
  display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap;
  margin-bottom: 10px; padding: 8px 10px; border-radius: 10px;
  background: #102238; border: 1px solid #244160;
}
.template-toolbar__info { min-width: 0; }
.template-toolbar__title { color: #eaf3ff; font-size: 13px; font-weight: 700; }
.template-toolbar__desc { color: #9ec5ef; font-size: 11px; margin-top: 2px; }
.template-toolbar__actions { display: flex; gap: 6px; flex-wrap: wrap; }
.line-list { display: grid; gap: 10px; margin-bottom: 10px; }
.line-card {
  background: #0f2035; border: 1px solid #1e3a5f; border-radius: 12px; padding: 10px; transition: all .15s;
}
.line-card.active { border-color: #60a5fa; box-shadow: 0 0 0 1px rgba(96,165,250,.35); }
.line-card__header { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 8px; }
.line-name { font-weight: 600; color: #90caf9; font-size: 14px; }
.line-subtitle { color: #6f8cab; font-size: 11px; margin-top: 2px; }
.line-empty { color: #6f8cab; font-size: 12px; text-align: center; padding: 8px 0; }
.assigned-grid { display: flex; flex-wrap: wrap; gap: 6px; }
.assigned-chip {
  background: #152841; border: 1px solid #244160; border-radius: 8px; padding: 5px 8px; cursor: pointer;
  display: flex; flex-direction: column; gap: 2px;
}
.chip-top { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.chip-name { color: #e2e8f0; font-size: 12px; font-weight: 600; }
.chip-rating { font-size: 10px; color: #ffd54f; flex-shrink: 0; }
.chip-stats { color: #94a3b8; font-size: 10px; line-height: 1.2; }
.remove-hint { color: #7f95af; font-size: 10px; }
.pool-card {
  background: #0f2035; border: 1px solid #1e3a5f; border-radius: 12px; padding: 10px;
}
.pool-card__title { color: #e2e8f0; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
.pool-card__target { color: #60a5fa; font-size: 12px; }
.pool-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; margin-top: 8px; }
.pool-player {
  background: #152841; border: 1px solid #244160; border-radius: 10px; padding: 8px; cursor: pointer; transition: all .15s;
}
.pool-player.active { border-color: #22c55e; background: #0f3320; }
.pool-player.used { border-color: #f59e0b; background: rgba(245, 158, 11, .12); }
.pool-player__top { display: flex; justify-content: space-between; gap: 4px; align-items: center; }
.pool-player__name { color: #e2e8f0; font-size: 12px; font-weight: 600; }
.pool-player__meta { margin-top: 4px; }
.pool-player__status { color: #94a3b8; font-size: 10px; }
.rating-badge { font-size: 10px; color: #ffd54f; flex-shrink: 0; }
/* Sheet popups */
.sheet-body { padding: 18px 16px 20px; }
.sheet-title { font-size: 16px; font-weight: 700; color: #102238; margin-bottom: 6px; }
.sheet-subtitle { font-size: 12px; color: #5b7088; line-height: 1.5; margin-bottom: 12px; }
.template-quick { margin-top: 12px; padding: 10px 12px; border-radius: 12px; background: #f3f8ff; border: 1px solid #d6e6f8; }
.template-quick__title { color: #102238; font-weight: 600; font-size: 13px; margin-bottom: 8px; }
.template-list { display: grid; gap: 8px; }
.template-item {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  width: 100%; border: 1px solid #c9ddf5; background: #fff; border-radius: 10px;
  padding: 10px 12px; cursor: pointer; text-align: left; box-shadow: 0 4px 12px rgba(15,23,42,.06);
}
.template-item__name { color: #12304f; font-size: 13px; font-weight: 700; }
.template-item__meta { color: #6a8299; font-size: 11px; white-space: nowrap; }
:deep(.van-tabs__nav--card) { border: none !important; background: transparent !important; }
:deep(.van-tab--card) { background: #13263c !important; color: #c7def7 !important; border-radius: 8px; border: none !important; }
:deep(.van-tab--card.van-tab--active) { background: linear-gradient(135deg, #2563eb, #1d4ed8) !important; color: #fff !important; }
</style>
