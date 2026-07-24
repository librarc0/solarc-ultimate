<script setup lang="ts">
import { ref, computed } from 'vue'
import { showToast } from 'vant'
import scheduleApi, { type ScheduleEvent } from '@/api/schedule'

interface Props {
  event: ScheduleEvent
  onClose: () => void
  onUpdated: () => void
}

const props = defineProps<Props>()

const summary = ref<any>(null)
const loadingSummary = ref(false)
const activeTab = ref('yes')

async function loadSummary() {
  loadingSummary.value = true
  try {
    summary.value = await scheduleApi.getAttendanceSummary(props.event.id)
  } catch {
    showToast('加载出勤数据失败')
  } finally {
    loadingSummary.value = false
  }
}

async function sendRemind() {
  try {
    await scheduleApi.remindEvent(props.event.id)
    showToast('催促通知已发送 ✓')
  } catch {
    showToast('发送失败')
  }
}

const groups = computed<Record<string, { player_id: number; player_name: string; display_name?: string }[]>>(() => ({
  yes: summary.value?.yes ?? [],
  leave: [...(summary.value?.leave ?? []), ...(summary.value?.no ?? [])],
  sdl: summary.value?.sdl ?? [],
  not_submitted: summary.value?.not_submitted ?? [],
}))

const tabLabels: Record<string, string> = {
  yes: '✅ 出勤',
  leave: '🏃 请假',
  sdl: '🎉 场边',
  not_submitted: '⏳ 未填',
}

loadSummary()
</script>

<template>
  <div class="attendance-panel">
    <div class="panel-header">
      <span class="panel-title">出勤情况 — {{ event.title }}</span>
      <van-button round size="small" plain type="warning" class="ios-remind-btn" @click="sendRemind">催促未填</van-button>
    </div>

    <van-loading v-if="loadingSummary" type="spinner" vertical style="padding: 24px 0" />
    <template v-else-if="summary">
      <van-tabs v-model:active="activeTab" class="attendance-tabs">
        <van-tab v-for="(label, key) in tabLabels" :key="key" :name="key" :title="`${label} (${(groups[key] ?? []).length})`">
          <div v-if="(groups[key] ?? []).length === 0" class="empty-tip">暂无</div>
          <div v-else class="player-chips">
            <span
              v-for="p in (groups[key] ?? [])"
              :key="p.player_id"
              class="player-chip"
            >
              {{ p.display_name || p.player_name }}
            </span>
          </div>
        </van-tab>
      </van-tabs>
    </template>
  </div>
</template>

<style scoped>
.attendance-panel { padding: 12px; }
.panel-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.panel-title { font-size: 15px; font-weight: 600; color: #e0e0e0; }
:deep(.attendance-panel .van-button) {
  font-weight: 600;
  border-radius: 12px;
  box-shadow: none;
  backdrop-filter: blur(10px);
}
.ios-remind-btn {
  background: rgba(255, 159, 10, .14) !important;
  color: #ffe0a3 !important;
  border: 1px solid rgba(255, 159, 10, .28) !important;
}
:deep(.attendance-tabs .van-tabs__wrap) {
  background: #0f2035 !important;
  border: 1px solid #244160;
  border-radius: 12px;
  overflow: hidden;
}
:deep(.attendance-tabs .van-tabs__nav),
:deep(.attendance-tabs .van-tabs__nav--line) {
  background: #0f2035 !important;
}
:deep(.attendance-tabs .van-tab) {
  color: #bfdcff !important;
}
:deep(.attendance-tabs .van-tab--active) {
  color: #ffffff !important;
  font-weight: 700;
}
:deep(.attendance-tabs .van-tab__text) {
  color: inherit !important;
}
:deep(.attendance-tabs .van-tabs__line) {
  background: #60a5fa;
}
.player-chips { display: flex; flex-wrap: wrap; gap: 8px; padding: 12px; }
.player-chip {
  background: #1e3a5f; color: #90caf9; border-radius: 16px;
  padding: 4px 12px; font-size: 13px;
}
.empty-tip { color: #888; font-size: 13px; text-align: center; padding: 16px; }
</style>
