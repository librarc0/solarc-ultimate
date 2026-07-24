<template>
  <!-- 防守盘录入底部抽屉：选择成功防守的人 -->
  <van-action-sheet
    v-model:show="visible"
    title="防守盘录入"
    @cancel="handleCancel"
  >
    <div class="defense-drawer">

      <!-- 防守方（分队显示） -->
      <div class="defense-drawer__section">
        <div class="defense-drawer__label">
          成功防守者 <span class="required">*</span>
          <span v-if="possession" class="hint-text">
            （{{ possession === 'A' ? teamBLabel : teamALabel }} 防守中）
          </span>
        </div>

        <!-- 队A -->
        <div class="defense-drawer__team-group">
          <div class="defense-drawer__team-title"
            :class="{ 'defense-drawer__team-title--defender': possession === 'B' }">
            {{ teamALabel }}
            <span v-if="possession === 'B'" class="defender-badge">防守方</span>
          </div>
          <div class="defense-drawer__players">
            <div
              v-for="p in teamAPlayers"
              :key="`def-a-${p.id}`"
              class="defense-drawer__chip"
              :class="{ 'defense-drawer__chip--active': selectedDefender === p.id }"
              @click="selectedDefender = p.id"
            >
              {{ p.display_name || p.username }}
            </div>
          </div>
        </div>

        <!-- 队B -->
        <div class="defense-drawer__team-group" style="margin-top: 10px">
          <div class="defense-drawer__team-title"
            :class="{ 'defense-drawer__team-title--defender': possession === 'A' }">
            {{ teamBLabel }}
            <span v-if="possession === 'A'" class="defender-badge">防守方</span>
          </div>
          <div class="defense-drawer__players">
            <div
              v-for="p in teamBPlayers"
              :key="`def-b-${p.id}`"
              class="defense-drawer__chip"
              :class="{ 'defense-drawer__chip--active': selectedDefender === p.id }"
              @click="selectedDefender = p.id"
            >
              {{ p.display_name || p.username }}
            </div>
          </div>
        </div>
      </div>

      <!-- 确认按钮 -->
      <div class="defense-drawer__actions">
        <van-button
          round
          block
          type="primary"
          :disabled="selectedDefender === null"
          @click="handleConfirm"
        >
          确认防守
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
  (e: 'confirm', defender: number, interceptor: number | null): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const selectedDefender = ref<number | null>(null)

function handleConfirm() {
  if (selectedDefender.value === null) return
  emit('confirm', selectedDefender.value, null)
  reset()
  visible.value = false
}

function handleCancel() {
  reset()
  visible.value = false
}

function reset() {
  selectedDefender.value = null
}
</script>

<style scoped>
.defense-drawer {
  padding: 16px 16px calc(16px + env(safe-area-inset-bottom));
}

.defense-drawer__section {
  margin-bottom: 16px;
}

.defense-drawer__label {
  font-size: 14px;
  font-weight: 600;
  color: #323233;
  margin-bottom: 10px;
}

.hint-text {
  font-size: 12px;
  font-weight: normal;
  color: #07c160;
  margin-left: 4px;
}

.required {
  color: #ee0a24;
}

.defense-drawer__team-group {
  margin-bottom: 4px;
}

.defense-drawer__team-title {
  font-size: 12px;
  font-weight: 600;
  color: #969799;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.defense-drawer__team-title--defender {
  color: #1677ff;
}

.defender-badge {
  background: #1677ff;
  color: #fff;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
}

.defense-drawer__players {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.defense-drawer__chip {
  padding: 6px 14px;
  border-radius: 20px;
  background: #f7f8fa;
  border: 1px solid #ebedf0;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  color: #323233;
}

.defense-drawer__chip--active {
  background: #1677ff;
  border-color: #1677ff;
  color: #fff;
  font-weight: 600;
}

.defense-drawer__actions {
  margin-top: 20px;
}
</style>
