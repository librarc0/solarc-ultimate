<template>
  <!-- 汇总模式统计表格：点击格子 → 数字键盘录入 → 自动移焦下一格 -->
  <div class="match-stat-table">
    <!-- 展开/收起高级数据按钮（防守/失误列默认隐藏） -->
    <div
      v-if="canShowAdvanced"
      class="match-stat-table__toggle"
      @click="showAdvanced = !showAdvanced"
    >
      {{ showAdvanced ? '▲ 收起高级数据（防守/失误）' : '▼ 显示高级数据（防守/失误）' }}
    </div>

    <!-- 表格容器：移动端可水平滑动 -->
    <div class="match-stat-table__scroll">
      <table class="match-stat-table__table">
        <!-- 表头行 -->
        <thead>
          <tr>
            <th class="match-stat-table__th match-stat-table__th--name">
              球员
            </th>
            <th class="match-stat-table__th">
              G
            </th>
            <!-- 助攻列（默认显示，prop 可关闭） -->
            <th
              v-if="props.showAssists !== false"
              class="match-stat-table__th"
            >
              A
            </th>
            <!-- 防守列（需展开高级数据 + prop 允许才显示） -->
            <th
              v-if="showAdvanced && props.showDefense"
              class="match-stat-table__th"
            >
              D
            </th>
            <!-- 失误列（需展开高级数据 + prop 允许才显示） -->
            <th
              v-if="showAdvanced && props.showTurnovers"
              class="match-stat-table__th"
            >
              T
            </th>
          </tr>
        </thead>

        <tbody>
          <!-- 球员统计数据行 -->
          <tr
            v-for="player in players"
            :key="player.id"
            class="match-stat-table__row"
          >
            <!-- 球员名称列 -->
            <td class="match-stat-table__td match-stat-table__td--name">
              <span class="match-stat-table__pname">{{ player.display_name || player.username }}</span>
              <span
                v-if="player.jersey_number != null"
                class="match-stat-table__jersey"
              >#{{ player.jersey_number }}</span>
            </td>
            <!-- 进球格子 -->
            <td
              class="match-stat-table__td match-stat-table__td--num"
              :class="{ 'match-stat-table__td--active': isActive(player.id, 'goals') }"
              @click="activateCell(player.id, 'goals')"
            >
              {{ getStatValue(player.id, 'goals') || '—' }}
            </td>
            <!-- 助攻格子 -->
            <td
              v-if="props.showAssists !== false"
              class="match-stat-table__td match-stat-table__td--num"
              :class="{ 'match-stat-table__td--active': isActive(player.id, 'assists') }"
              @click="activateCell(player.id, 'assists')"
            >
              {{ getStatValue(player.id, 'assists') || '—' }}
            </td>
            <!-- 防守格子（高级数据） -->
            <td
              v-if="showAdvanced && props.showDefense"
              class="match-stat-table__td match-stat-table__td--num"
              :class="{ 'match-stat-table__td--active': isActive(player.id, 'defense') }"
              @click="activateCell(player.id, 'defense')"
            >
              {{ getStatValue(player.id, 'defense') || '—' }}
            </td>
            <!-- 失误格子（高级数据） -->
            <td
              v-if="showAdvanced && props.showTurnovers"
              class="match-stat-table__td match-stat-table__td--num"
              :class="{ 'match-stat-table__td--active': isActive(player.id, 'turnovers') }"
              @click="activateCell(player.id, 'turnovers')"
            >
              {{ getStatValue(player.id, 'turnovers') || '—' }}
            </td>
          </tr>

          <!-- 合计行 -->
          <tr class="match-stat-table__row match-stat-table__row--total">
            <td class="match-stat-table__td match-stat-table__td--name">
              合计
            </td>
            <td class="match-stat-table__td match-stat-table__td--num match-stat-table__td--total">
              {{ totalGoals }}
            </td>
            <td
              v-if="props.showAssists !== false"
              class="match-stat-table__td match-stat-table__td--num match-stat-table__td--total"
            >
              {{ totalAssists }}
            </td>
            <td
              v-if="showAdvanced && props.showDefense"
              class="match-stat-table__td match-stat-table__td--num match-stat-table__td--total"
            >
              {{ totalDefense }}
            </td>
            <td
              v-if="showAdvanced && props.showTurnovers"
              class="match-stat-table__td match-stat-table__td--num match-stat-table__td--total"
            >
              {{ totalTurnovers }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 数字键盘（底部弹出）；close-button-text="完成"，点完成自动移焦下一格 -->
    <van-number-keyboard
      v-model:show="showKeyboard"
      :value="inputBuffer"
      close-button-text="完成"
      @input="onKeyInput"
      @delete="onKeyDelete"
      @close="onKeyboardConfirm"
      @blur="onKeyboardBlur"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

/* ===== 类型定义 ===== */
interface Player {
  id: number
  username: string
  display_name: string | null
  jersey_number?: number | null
}

interface StatEntry {
  goals: number
  assists: number
  defense: number
  turnovers: number
}

/* ===== Props 定义 ===== */
const props = defineProps<{
  /** 当前球队球员列表 */
  players: Player[]
  /** 当前统计数据（player_id → StatEntry） */
  modelValue: Record<number, StatEntry>
  /** 是否显示助攻列（默认 true） */
  showAssists?: boolean
  /** 是否允许展开防守列 */
  showDefense?: boolean
  /** 是否允许展开失误列 */
  showTurnovers?: boolean
}>()

/* ===== Emits ===== */
const emit = defineEmits<{
  (e: 'update:modelValue', value: Record<number, StatEntry>): void
}>()

/* ===== 内部状态 ===== */
/** 当前激活（聚焦）的格子 */
const activeCell = ref<{ playerId: number; field: keyof StatEntry } | null>(null)
/** 高级数据列展开状态（防守/失误，默认折叠） */
const showAdvanced = ref(false)
/** 数字键盘显示状态 */
const showKeyboard = ref(false)
/** 键盘输入缓存（字符串形式） */
const inputBuffer = ref('')

/* ===== 辅助计算 ===== */
/** 是否需要展开按钮：子prop 允许任意一列时才显示 */
const canShowAdvanced = computed(() => !!props.showDefense || !!props.showTurnovers)

/** 当前激活列的遍历顺序（决定自动移焦方向） */
const visibleFields = computed((): (keyof StatEntry)[] => {
  const fields: (keyof StatEntry)[] = ['goals']
  if (props.showAssists !== false) fields.push('assists')
  if (showAdvanced.value && props.showDefense) fields.push('defense')
  if (showAdvanced.value && props.showTurnovers) fields.push('turnovers')
  return fields
})

/* ===== 统计读取 ===== */
function getStatValue(playerId: number, field: keyof StatEntry): number {
  return props.modelValue[playerId]?.[field] ?? 0
}

/** 判断格子是否处于激活状态 */
function isActive(playerId: number, field: keyof StatEntry): boolean {
  return activeCell.value?.playerId === playerId && activeCell.value?.field === field
}

/* ===== 合计行计算 ===== */
const totalGoals = computed(() =>
  props.players.reduce((s, p) => s + (props.modelValue[p.id]?.goals ?? 0), 0)
)
const totalAssists = computed(() =>
  props.players.reduce((s, p) => s + (props.modelValue[p.id]?.assists ?? 0), 0)
)
const totalDefense = computed(() =>
  props.players.reduce((s, p) => s + (props.modelValue[p.id]?.defense ?? 0), 0)
)
const totalTurnovers = computed(() =>
  props.players.reduce((s, p) => s + (props.modelValue[p.id]?.turnovers ?? 0), 0)
)

/* ===== 格子激活逻辑 ===== */
function activateCell(playerId: number, field: keyof StatEntry) {
  // 先保存当前格子的值再切换
  if (activeCell.value) commitCurrentCell()
  activeCell.value = { playerId, field }
  const cur = getStatValue(playerId, field)
  inputBuffer.value = cur > 0 ? String(cur) : ''
  showKeyboard.value = true
}

/* ===== 键盘事件处理 ===== */
/** 按下数字键（限制最大 3 位整数） */
function onKeyInput(key: string) {
  if (inputBuffer.value.length >= 3) return
  inputBuffer.value += key
}

/** 按下删除键 */
function onKeyDelete() {
  inputBuffer.value = inputBuffer.value.slice(0, -1)
}

/** 点击"完成"按钮：保存当前格子并自动移焦到下一格 */
function onKeyboardConfirm() {
  commitCurrentCell()
  const next = getNextCell()
  if (next) {
    // 切换到下一个格子，键盘保持打开
    activeCell.value = next
    const cur = getStatValue(next.playerId, next.field)
    inputBuffer.value = cur > 0 ? String(cur) : ''
    showKeyboard.value = true
  } else {
    // 所有格子遍历完毕，关闭键盘
    showKeyboard.value = false
    activeCell.value = null
  }
}

/** 点击键盘外部区域：保存并关闭 */
function onKeyboardBlur() {
  commitCurrentCell()
  showKeyboard.value = false
  activeCell.value = null
}

/* ===== 保存当前格子的值 ===== */
function commitCurrentCell() {
  if (!activeCell.value) return
  const { playerId, field } = activeCell.value
  const newValue = parseInt(inputBuffer.value, 10) || 0
  const newStats: Record<number, StatEntry> = { ...props.modelValue }
  newStats[playerId] = {
    ...(newStats[playerId] ?? { goals: 0, assists: 0, defense: 0, turnovers: 0 }),
    [field]: newValue,
  }
  emit('update:modelValue', newStats)
}

/* ===== 获取下一个格子的位置 ===== */
function getNextCell(): { playerId: number; field: keyof StatEntry } | null {
  if (!activeCell.value) return null
  const { playerId, field } = activeCell.value
  const fields = visibleFields.value
  const curFieldIdx = fields.indexOf(field)
  const curPlayerIdx = props.players.findIndex(p => p.id === playerId)

  // 尝试移到同球员的下一列
  if (curFieldIdx < fields.length - 1) {
    return { playerId, field: fields[curFieldIdx + 1]! }
  }
  // 已是最后一列，移到下一球员的第一列
  if (curPlayerIdx < props.players.length - 1) {
    return { playerId: props.players[curPlayerIdx + 1]!.id, field: fields[0]! }
  }
  // 最后一格
  return null
}
</script>

<style scoped>
/* 表格主容器 */
.match-stat-table {
  margin: 0 0 8px;
}

/* 展开/收起高级数据按钮 */
.match-stat-table__toggle {
  text-align: center;
  padding: 8px 0;
  font-size: 13px;
  color: #1677ff;
  cursor: pointer;
  user-select: none;
}

/* 可水平滑动的表格容器（移动端防止内容溢出） */
.match-stat-table__scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

/* 表格基本布局 */
.match-stat-table__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

/* 表头单元格 */
.match-stat-table__th {
  padding: 8px 6px;
  text-align: center;
  font-weight: 600;
  font-size: 12px;
  color: #666;
  background: #f7f8fa;
  border-bottom: 2px solid #eee;
  white-space: nowrap;
}

/* 球员名称表头（左对齐，固定宽度） */
.match-stat-table__th--name {
  text-align: left;
  min-width: 80px;
}

/* 数据行 */
.match-stat-table__row {
  border-bottom: 1px solid #f0f0f0;
  transition: background 0.1s;
}

.match-stat-table__row:active {
  background: #fafafa;
}

/* 合计行样式 */
.match-stat-table__row--total {
  background: #f7f8fa;
  border-top: 2px solid #eee;
}

/* 数据单元格 */
.match-stat-table__td {
  padding: 10px 6px;
  text-align: center;
  vertical-align: middle;
}

/* 球员名称单元格（左对齐） */
.match-stat-table__td--name {
  text-align: left;
  min-width: 80px;
}

/* 数字格子：可点击交互 */
.match-stat-table__td--num {
  min-width: 40px;
  cursor: pointer;
  border: 1.5px solid transparent;
  border-radius: 4px;
  color: #333;
  font-weight: 500;
  transition: border-color 0.15s, background 0.15s;
}

/* 格子激活状态：蓝色边框高亮 */
.match-stat-table__td--active {
  border-color: #1677ff !important;
  background: #e8f4ff;
  color: #1677ff;
}

/* 合计值加粗 */
.match-stat-table__td--total {
  font-weight: 700;
  color: #333;
}

/* 球员姓名 */
.match-stat-table__pname {
  font-size: 13px;
  color: #333;
}

/* 球衣号码 */
.match-stat-table__jersey {
  font-size: 11px;
  color: #999;
  margin-left: 4px;
}

/* ── 宽屏适配（≥768px） ────────────────────── */
@media (min-width: 768px) {
  /* 宽屏列宽展开显示完整标题 */
  .match-stat-table__th {
    padding: 10px 12px;
    font-size: 13px;
  }

  .match-stat-table__td {
    padding: 12px 10px;
  }

  .match-stat-table__td--num {
    min-width: 64px;
    font-size: 15px;
  }

  .match-stat-table__th--name,
  .match-stat-table__td--name {
    min-width: 120px;
  }
}
</style>
