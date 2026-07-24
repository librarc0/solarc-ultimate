<template>
  <!-- 得分录入底部抽屉：选得分者→选助攻者→确认 -->
  <van-action-sheet
    v-model:show="visible"
    :title="`${teamLabel} 得分录入`"
    @cancel="handleCancel"
  >
    <div class="goal-drawer">

      <!-- 进球者 -->
      <div class="goal-drawer__section">
        <div class="goal-drawer__label">得分者 <span class="required">*</span></div>
        <div class="goal-drawer__players">
          <div
            v-for="p in scorerPlayers"
            :key="`scorer-${p.id}`"
            class="goal-drawer__chip"
            :class="{ 'goal-drawer__chip--active': selectedScorer === p.id }"
            @click="selectScorer(p.id)"
          >
            {{ p.display_name || p.username }}
          </div>
        </div>
      </div>

      <!-- 助攻者（可选） -->
      <div class="goal-drawer__section" v-if="selectedScorer !== null">
        <div class="goal-drawer__label">助攻者 <span class="optional">（可选）</span></div>
        <div class="goal-drawer__players">
          <div
            class="goal-drawer__chip"
            :class="{ 'goal-drawer__chip--active': selectedAssist === null }"
            @click="selectedAssist = null"
          >
            无
          </div>
          <div
            v-for="p in assistPlayers"
            :key="`assist-${p.id}`"
            class="goal-drawer__chip"
            :class="{ 'goal-drawer__chip--active': selectedAssist === p.id }"
            @click="selectAssist(p.id)"
          >
            {{ p.display_name || p.username }}
          </div>
        </div>
      </div>

      <!-- 是否 Break（防守得分） -->
      <div class="goal-drawer__section" v-if="selectedScorer !== null && possessionSide !== null">
        <div class="goal-drawer__label">得分类型</div>
        <div style="display:flex;align-items:center;gap:12px">
          <van-tag :type="isBreak ? 'danger' : 'success'" size="large">{{ isBreak ? '🔥 Break（防守得分）' : '✅ Clean Hold（进攻得分）' }}</van-tag>
          <span style="font-size:12px;color:#888">自动检测，可手动切换</span>
          <van-switch v-model="isBreak" size="20" />
        </div>
      </div>

      <!-- 确认按钮 -->
      <div class="goal-drawer__actions">
        <van-button
          round
          block
          type="primary"
          :disabled="selectedScorer === null"
          @click="handleConfirm"
        >
          确认得分
        </van-button>
        <van-button round block plain @click="handleCancel" style="margin-top: 8px">
          取消
        </van-button>
      </div>
    </div>
  </van-action-sheet>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Player {
  id: number
  username: string
  display_name: string | null
}

const props = defineProps<{
  modelValue: boolean
  teamLabel: string
  players: Player[]
  possessionSide: 'A' | 'B' | null  // 当前进攻方，用于自动检测 break
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'confirm', scorer: number, assist: number | null, isBreak: boolean): void
}>()  

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const selectedScorer = ref<number | null>(null)
const selectedAssist = ref<number | null>(null)
const isBreak = ref(false)

const scorerPlayers = computed(() => props.players)
const assistPlayers = computed(() =>
  props.players.filter(p => p.id !== selectedScorer.value)
)

// Auto-detect break: if scoring team != possession team, it's a break
import { watch } from 'vue'
watch(selectedScorer, () => {
  if (props.possessionSide === null) { isBreak.value = false; return }
  // teamLabel is 'A' or 'B' (the scoring team)
  const scoringTeam = props.teamLabel
  isBreak.value = scoringTeam !== props.possessionSide
})

function selectScorer(id: number) {
  selectedScorer.value = id
  selectedAssist.value = null
}

function selectAssist(id: number) {
  selectedAssist.value = id
}

function handleConfirm() {
  if (selectedScorer.value === null) return
  emit('confirm', selectedScorer.value, selectedAssist.value, isBreak.value)
  reset()
  visible.value = false
}

function handleCancel() {
  reset()
  visible.value = false
}

function reset() {
  selectedScorer.value = null
  selectedAssist.value = null
  isBreak.value = false
}
</script>

<style scoped>
.goal-drawer {
  padding: 16px 16px env(safe-area-inset-bottom, 16px);
}

.goal-drawer__section {
  margin-bottom: 20px;
}

.goal-drawer__label {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 10px;
}

.goal-drawer__label .required {
  color: #ee0a24;
  margin-left: 2px;
}

.goal-drawer__label .optional {
  font-size: 12px;
  font-weight: 400;
  color: #888;
}

.goal-drawer__players {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.goal-drawer__chip {
  padding: 6px 14px;
  border-radius: 20px;
  border: 1.5px solid #ddd;
  font-size: 14px;
  color: #333;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}

.goal-drawer__chip--active {
  border-color: #1677ff;
  background: #e8f4ff;
  color: #1677ff;
  font-weight: 600;
}

.goal-drawer__actions {
  margin-top: 8px;
}
</style>
