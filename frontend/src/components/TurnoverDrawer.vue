<template>
  <!-- 失误录入底部抽屉：选择失误球员（按队分组） -->
  <van-action-sheet
    v-model:show="visible"
    title="失误录入"
    @cancel="handleCancel"
  >
    <div class="turnover-drawer">

      <!-- 失误方（分队显示） -->
      <div class="turnover-drawer__section">
        <div class="turnover-drawer__label">
          失误球员 <span class="required">*</span>
          <span v-if="possession" class="hint-text">
            （{{ possession === 'A' ? teamALabel : teamBLabel }} 持盘进攻中）
          </span>
        </div>

        <!-- 队A -->
        <div class="turnover-drawer__team-group">
          <div class="turnover-drawer__team-title"
            :class="{ 'turnover-drawer__team-title--attacker': possession === 'A' }">
            {{ teamALabel }}
            <span v-if="possession === 'A'" class="attacker-badge">进攻方</span>
          </div>
          <div class="turnover-drawer__players">
            <div
              v-for="p in teamAPlayers"
              :key="`tov-a-${p.id}`"
              class="turnover-drawer__chip"
              :class="{ 'turnover-drawer__chip--active': selectedPlayer === p.id }"
              @click="selectedPlayer = p.id"
            >
              {{ p.display_name || p.username }}
            </div>
          </div>
        </div>

        <!-- 队B -->
        <div class="turnover-drawer__team-group" style="margin-top: 10px">
          <div class="turnover-drawer__team-title"
            :class="{ 'turnover-drawer__team-title--attacker': possession === 'B' }">
            {{ teamBLabel }}
            <span v-if="possession === 'B'" class="attacker-badge">进攻方</span>
          </div>
          <div class="turnover-drawer__players">
            <div
              v-for="p in teamBPlayers"
              :key="`tov-b-${p.id}`"
              class="turnover-drawer__chip"
              :class="{ 'turnover-drawer__chip--active': selectedPlayer === p.id }"
              @click="selectedPlayer = p.id"
            >
              {{ p.display_name || p.username }}
            </div>
          </div>
        </div>
      </div>

      <!-- 确认按钮 -->
      <div class="turnover-drawer__actions">
        <van-button
          round
          block
          type="warning"
          :disabled="selectedPlayer === null"
          @click="handleConfirm"
        >
          确认失误
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
  teamALabel: string
  teamBLabel: string
  teamAPlayers: Player[]
  teamBPlayers: Player[]
  possession: 'A' | 'B' | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'confirm', playerId: number): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const selectedPlayer = ref<number | null>(null)

function handleConfirm() {
  if (selectedPlayer.value === null) return
  emit('confirm', selectedPlayer.value)
  reset()
  visible.value = false
}

function handleCancel() {
  reset()
  visible.value = false
}

function reset() {
  selectedPlayer.value = null
}
</script>

<style scoped>
.turnover-drawer {
  padding: 16px 16px calc(16px + env(safe-area-inset-bottom));
}

.turnover-drawer__section {
  margin-bottom: 16px;
}

.turnover-drawer__label {
  font-size: 14px;
  font-weight: 600;
  color: #323233;
  margin-bottom: 10px;
}

.hint-text {
  font-size: 12px;
  font-weight: normal;
  color: #ff976a;
  margin-left: 4px;
}

.required {
  color: #ee0a24;
}

.turnover-drawer__team-group {
  margin-bottom: 4px;
}

.turnover-drawer__team-title {
  font-size: 12px;
  font-weight: 600;
  color: #969799;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.turnover-drawer__team-title--attacker {
  color: #ff976a;
}

.attacker-badge {
  background: #ff976a;
  color: #fff;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
}

.turnover-drawer__players {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.turnover-drawer__chip {
  padding: 6px 14px;
  border-radius: 20px;
  background: #f7f8fa;
  border: 1px solid #ebedf0;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  color: #323233;
}

.turnover-drawer__chip--active {
  background: #ff976a;
  border-color: #ff976a;
  color: #fff;
  font-weight: 600;
}

.turnover-drawer__actions {
  margin-top: 20px;
}
</style>
