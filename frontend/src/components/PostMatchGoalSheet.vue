<template>
  <!-- 赛后事件录入底部弹层：支持进球、防守、失误三种类型 -->
  <van-action-sheet
    v-model:show="visible"
    :title="sheetTitle"
    @cancel="handleCancel"
    @closed="reset"
  >
    <div class="post-goal-sheet">
      <!-- 步骤指示器 -->
      <div class="post-goal-sheet__stepper">
        <span
          v-for="n in totalSteps"
          :key="n"
          class="post-goal-sheet__dot"
          :class="{ 'post-goal-sheet__dot--active': n === step }"
        ></span>
      </div>

      <!-- Step 1: 选择归属队（A / B） -->
      <template v-if="step === 1">
        <div class="post-goal-sheet__section">
          <div class="post-goal-sheet__label">
            归属队伍
          </div>
          <div class="post-goal-sheet__team-row">
            <!-- 队 A 选择按钮 -->
            <div
              class="post-goal-sheet__team-btn"
              :class="{ 'post-goal-sheet__team-btn--active': selectedTeam === 'A' }"
              @click="selectedTeam = 'A'"
            >
              {{ props.teamALabel }}
            </div>
            <!-- 队 B 选择按钮；外战时对方球员列表可能为空，但仍可记录比分 -->
            <div
              class="post-goal-sheet__team-btn"
              :class="{ 'post-goal-sheet__team-btn--active': selectedTeam === 'B' }"
              @click="selectedTeam = 'B'"
            >
              {{ props.teamBLabel }}
            </div>
          </div>
        </div>
      </template>

      <!-- Step 2: 选择主球员（得分者 / 防守者 / 失误者） -->
      <template v-else-if="step === 2">
        <div class="post-goal-sheet__section">
          <div class="post-goal-sheet__label">
            {{ mainPlayerLabel }} <span class="required">*</span>
          </div>
          <!-- 外战模式下对方队员列表为空时显示提示 -->
          <div
            v-if="currentTeamPlayers.length === 0"
            class="post-goal-sheet__empty"
          >
            对方球员未录入，该事件将仅计入队伍层面统计
          </div>
          <div
            v-else
            class="post-goal-sheet__players"
          >
            <div
              v-for="p in currentTeamPlayers"
              :key="`main-${p.id}`"
              class="post-goal-sheet__chip"
              :class="{ 'post-goal-sheet__chip--active': selectedMainPlayer === p.id }"
              @click="selectedMainPlayer = p.id"
            >
              {{ p.display_name || p.username }}
            </div>
          </div>
        </div>
      </template>

      <!-- Step 3: 进球→选助攻+BREAK；防守→选截球者（失误无此步） -->
      <template v-else-if="step === 3">
        <!-- 进球：助攻者 + BREAK 开关 -->
        <template v-if="eventType === 'goal'">
          <div class="post-goal-sheet__section">
            <div class="post-goal-sheet__label">
              助攻者 <span class="optional">（可选）</span>
            </div>
            <div class="post-goal-sheet__players">
              <!-- "无" 选项代表无助攻 -->
              <div
                class="post-goal-sheet__chip"
                :class="{ 'post-goal-sheet__chip--active': selectedSecondPlayer === null }"
                @click="selectedSecondPlayer = null"
              >
                无
              </div>
              <div
                v-for="p in secondaryPlayers"
                :key="`assist-${p.id}`"
                class="post-goal-sheet__chip"
                :class="{ 'post-goal-sheet__chip--active': selectedSecondPlayer === p.id }"
                @click="selectedSecondPlayer = p.id"
              >
                {{ p.display_name || p.username }}
              </div>
            </div>
          </div>

          <!-- BREAK 开关：防守得分还是进攻得分 -->
          <div class="post-goal-sheet__section">
            <div class="post-goal-sheet__label">
              得分类型
            </div>
            <div class="post-goal-sheet__break-row">
              <van-tag
                :type="isBreak ? 'danger' : 'success'"
                size="large"
              >
                {{ isBreak ? '🔥 Break（防守得分）' : '✅ Hold（进攻得分）' }}
              </van-tag>
              <van-switch
                v-model="isBreak"
                size="20"
              />
            </div>
          </div>
        </template>

        <!-- 防守：截球者（可选） -->
        <template v-else-if="eventType === 'defense'">
          <div class="post-goal-sheet__section">
            <div class="post-goal-sheet__label">
              截球者 <span class="optional">（可选）</span>
            </div>
            <div class="post-goal-sheet__players">
              <div
                class="post-goal-sheet__chip"
                :class="{ 'post-goal-sheet__chip--active': selectedSecondPlayer === null }"
                @click="selectedSecondPlayer = null"
              >
                无
              </div>
              <div
                v-for="p in secondaryPlayers"
                :key="`intercept-${p.id}`"
                class="post-goal-sheet__chip"
                :class="{ 'post-goal-sheet__chip--active': selectedSecondPlayer === p.id }"
                @click="selectedSecondPlayer = p.id"
              >
                {{ p.display_name || p.username }}
              </div>
            </div>
          </div>
        </template>
      </template>

      <!-- 操作按钮区（下一步 / 确认 / 上一步） -->
      <div class="post-goal-sheet__actions">
        <van-button
          round
          block
          type="primary"
          :disabled="!canProceed"
          @click="handleNext"
        >
          {{ isLastStep ? '确认' : '下一步' }}
        </van-button>
        <!-- 非第一步显示返回按钮 -->
        <van-button
          v-if="step > 1"
          round
          block
          plain
          style="margin-top: 8px"
          @click="step--"
        >
          上一步
        </van-button>
        <van-button
          round
          block
          plain
          style="margin-top: 8px"
          @click="handleCancel"
        >
          取消
        </van-button>
      </div>
    </div>
  </van-action-sheet>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

/* ===== 类型定义 ===== */
interface Player {
  id: number
  username: string
  display_name: string | null
}

/* ===== Props 定义 ===== */
const props = defineProps<{
  modelValue: boolean
  /** 当前录入事件类型：进球 / 防守 / 失误 */
  eventType: 'goal' | 'defense' | 'turnover'
  teamALabel: string        // 队 A 显示名称
  teamBLabel: string        // 队 B 显示名称
  teamAPlayers: Player[]    // 队 A 球员列表
  teamBPlayers: Player[]    // 队 B 球员列表（外战时可能为空）
}>()

/* ===== Emits 定义 ===== */
const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'confirm:goal', payload: {
    team: 'A' | 'B'
    scorer_id: number
    assist_id: number | null
    is_break: boolean
  }): void
  (e: 'confirm:defense', payload: {
    team: 'A' | 'B'
    defender_id: number
    interceptor_id: number | null
  }): void
  (e: 'confirm:turnover', payload: {
    team: 'A' | 'B'
    player_id: number
  }): void
}>()

/* ===== 内部状态 ===== */
const step = ref(1)                                    // 当前步骤 (1~3)
const selectedTeam = ref<'A' | 'B' | null>(null)      // 已选队伍
const selectedMainPlayer = ref<number | null>(null)    // 主球员 id
const selectedSecondPlayer = ref<number | null>(null)  // 次球员 id（助攻/截球）
const isBreak = ref(false)                             // BREAK 开关

/* ===== v-model 双向绑定 ===== */
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

/* ===== 弹层标题 ===== */
const sheetTitle = computed(() => {
  switch (props.eventType) {
    case 'goal':     return '进球录入'
    case 'defense':  return '防守录入'
    case 'turnover': return '失误录入'
    default:         return ''
  }
})

/* ===== 步骤总数：失误只有 2 步（选队→选球员→确认） ===== */
const totalSteps = computed(() => props.eventType === 'turnover' ? 2 : 3)

/* ===== 是否处于最后一步 ===== */
const isLastStep = computed(() => step.value === totalSteps.value)

/* ===== 主球员选项（依据所选队伍） ===== */
const currentTeamPlayers = computed(() => {
  if (selectedTeam.value === 'A') return props.teamAPlayers
  if (selectedTeam.value === 'B') return props.teamBPlayers
  return []
})

/* ===== 次球员选项（排除主球员自身） ===== */
const secondaryPlayers = computed(() =>
  currentTeamPlayers.value.filter(p => p.id !== selectedMainPlayer.value)
)

/* ===== Step 2 标签：依事件类型不同 ===== */
const mainPlayerLabel = computed(() => {
  switch (props.eventType) {
    case 'goal':     return '得分者'
    case 'defense':  return '防守者'
    case 'turnover': return '失误者'
    default:         return ''
  }
})

/* ===== 下一步可用状态 ===== */
const canProceed = computed(() => {
  switch (step.value) {
    case 1: return selectedTeam.value !== null
    // 外战模式对方球员为空时也可继续（仅记录队伍层级）
    case 2: return selectedMainPlayer.value !== null || currentTeamPlayers.value.length === 0
    case 3: return true   // 次球员与选项均为可选
    default: return false
  }
})

/* ===== 下一步 / 确认 ===== */
function handleNext() {
  if (step.value < totalSteps.value) {
    step.value++
    // 切换步骤时清空次球员选择
    if (step.value === 3) selectedSecondPlayer.value = null
  } else {
    handleConfirm()
  }
}

/* ===== 提交并发射对应事件 ===== */
function handleConfirm() {
  const team = selectedTeam.value!

  if (props.eventType === 'goal') {
    emit('confirm:goal', {
      team,
      scorer_id: selectedMainPlayer.value!,
      assist_id: selectedSecondPlayer.value,
      is_break: isBreak.value,
    })
  } else if (props.eventType === 'defense') {
    emit('confirm:defense', {
      team,
      defender_id: selectedMainPlayer.value!,
      interceptor_id: selectedSecondPlayer.value,
    })
  } else {
    // 失误：仅记录球员（对方外战时 player_id 可能为 -1 占位，由父组件兜底处理）
    emit('confirm:turnover', {
      team,
      player_id: selectedMainPlayer.value ?? -1,
    })
  }

  reset()
  visible.value = false
}

/* ===== 取消 ===== */
function handleCancel() {
  reset()
  visible.value = false
}

/* ===== 重置所有内部状态 ===== */
function reset() {
  step.value = 1
  selectedTeam.value = null
  selectedMainPlayer.value = null
  selectedSecondPlayer.value = null
  isBreak.value = false
}
</script>

<style scoped>
/* 弹层主容器 */
.post-goal-sheet {
  padding: 12px 16px env(safe-area-inset-bottom, 16px);
}

/* 步骤指示圆点 */
.post-goal-sheet__stepper {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 16px;
}

.post-goal-sheet__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ddd;
  transition: background 0.2s;
}

.post-goal-sheet__dot--active {
  background: #1677ff;
}

/* 内容分区 */
.post-goal-sheet__section {
  margin-bottom: 20px;
}

/* 区块标签 */
.post-goal-sheet__label {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 10px;
}

.post-goal-sheet__label .required {
  color: #ee0a24;
  margin-left: 2px;
}

.post-goal-sheet__label .optional {
  font-size: 12px;
  font-weight: 400;
  color: #888;
}

/* 队伍选择行：两个大按钮水平并排 */
.post-goal-sheet__team-row {
  display: flex;
  gap: 12px;
}

.post-goal-sheet__team-btn {
  flex: 1;
  padding: 14px 0;
  border-radius: 10px;
  border: 2px solid #ddd;
  text-align: center;
  font-size: 15px;
  font-weight: 600;
  color: #555;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}

.post-goal-sheet__team-btn--active {
  border-color: #1677ff;
  background: #e8f4ff;
  color: #1677ff;
}

/* 球员 chip 网格容器 */
.post-goal-sheet__players {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* Chip 基础样式（与 .goal-drawer__chip 风格一致） */
.post-goal-sheet__chip {
  padding: 6px 14px;
  border-radius: 20px;
  border: 1.5px solid #ddd;
  font-size: 14px;
  color: #333;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
  touch-action: manipulation; /* 优化移动端点击响应 */
  min-height: 44px;           /* 满足触摸目标最小尺寸要求 */
  display: flex;
  align-items: center;
}

/* Chip 选中态 */
.post-goal-sheet__chip--active {
  border-color: #1677ff;
  background: #e8f4ff;
  color: #1677ff;
  font-weight: 600;
}

/* BREAK 开关行 */
.post-goal-sheet__break-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

/* 操作按钮区 */
.post-goal-sheet__actions {
  margin-top: 8px;
}

/* 外战对方球员为空时的提示文字 */
.post-goal-sheet__empty {
  font-size: 13px;
  color: #888;
  padding: 12px 0;
  text-align: center;
}

/* 宽屏：球员 chip 网格改为更宽布局 */
@media (min-width: 768px) {
  .post-goal-sheet {
    max-width: 560px;
    margin: 0 auto;
  }

  .post-goal-sheet__players {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    gap: 8px;
  }

  .post-goal-sheet__chip {
    justify-content: center;
  }
}
</style>
