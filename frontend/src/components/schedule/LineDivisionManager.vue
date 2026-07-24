<script setup lang="ts">
/**
 * LineDivisionManager — 日程分 line 管理（简化版）
 * 显示当前分 line 摘要，通过 LineDivisionWizard（schedule 模式）进行管理
 */
import { ref, computed, watch, onMounted } from 'vue'
import scheduleApi, { type ScheduleEvent, type ScheduleLineDivisionRead } from '@/api/schedule'
import LineDivisionWizard from '@/components/lineup/LineDivisionWizard.vue'

interface Props {
  event: ScheduleEvent
}
const props = defineProps<Props>()

// ─── 状态 ─────────────────────────────────────────────────────────────────────
const showWizard = ref(false)
const division = ref<ScheduleLineDivisionRead | null>(null)
const loading = ref(false)

const matchType = computed(() => {
  const et = props.event.event_type
  if (et === 'game') return 'game' as const
  if (et === 'internal') return 'internal' as const
  return 'training' as const
})

// ─── 分line摘要计算 ────────────────────────────────────────────────────────────
const divisionSummary = computed(() => {
  if (!division.value?.lines.length) return []
  const byRound: Record<number, typeof division.value.lines> = {}
  division.value.lines.forEach(l => {
    if (!byRound[l.round_number]) byRound[l.round_number] = []
    byRound[l.round_number]!.push(l)
  })
  return Object.entries(byRound).map(([round, lines]) => ({
    round: Number(round),
    lines: lines.map(l => ({
      id: l.id,
      name: l.line_name,
      count: l.players.length,
    })),
  })).sort((a, b) => a.round - b.round)
})

const totalPlayers = computed(() => {
  if (!division.value?.lines) return 0
  const ids = new Set<number>()
  division.value.lines.forEach(l => l.players.forEach(p => ids.add(p.player_id)))
  return ids.size
})

// ─── 加载分line数据 ────────────────────────────────────────────────────────────
async function loadDivision() {
  loading.value = true
  try {
    division.value = await scheduleApi.getDivision(props.event.id)
  } catch {
    division.value = null
  } finally {
    loading.value = false
  }
}

function onWizardClosed() {
  loadDivision()
}

watch(() => props.event.id, () => {
  loadDivision()
}, { immediate: true })

onMounted(() => {
  loadDivision()
})
</script>

<template>
  <div class="ldm-wrapper">
    <van-loading v-if="loading" type="spinner" vertical style="padding: 32px 0" />
    <template v-else>
      <!-- 已配置分line：显示摘要 -->
      <template v-if="division && division.lines.length > 0">
        <div class="ldm-summary-header">
          <div class="ldm-summary-header__left">
            <div class="ldm-summary-header__title">分 Line 配置</div>
            <div class="ldm-summary-header__meta">
              共 {{ totalPlayers }} 人 · {{ division.total_rounds }} 轮
            </div>
          </div>
          <van-button size="small" type="primary" @click="showWizard = true">管理分 Line</van-button>
        </div>

        <!-- 分组摘要 -->
        <div
          v-for="roundInfo in divisionSummary"
          :key="roundInfo.round"
          class="ldm-round"
        >
          <div v-if="division && division.total_rounds > 1" class="ldm-round__label">
            第 {{ roundInfo.round }} 轮
          </div>
          <div class="ldm-lines-row">
            <div
              v-for="line in roundInfo.lines"
              :key="line.id"
              class="ldm-line-chip"
            >
              <span class="ldm-line-chip__name">{{ line.name }}</span>
              <span class="ldm-line-chip__count">{{ line.count }}人</span>
            </div>
          </div>
        </div>
      </template>

      <!-- 未配置分line：引导创建 -->
      <template v-else>
        <van-empty description="暂无分 line 配置" image="default" style="padding: 32px 0" />
        <div style="margin: 0 16px 16px">
          <van-button round block type="primary" @click="showWizard = true">
            开始配置分 Line
          </van-button>
        </div>
      </template>
    </template>

    <!-- 分 Line 向导（schedule 模式） -->
    <LineDivisionWizard
      :visible="showWizard"
      :match-type="matchType"
      :event-id="event.id"
      mode="schedule"
      @update:visible="val => { showWizard = val; if (!val) onWizardClosed() }"
    />
  </div>
</template>

<style scoped>
.ldm-wrapper {
  padding: 12px 16px;
}

.ldm-summary-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.ldm-summary-header__title {
  color: #e2e8f0;
  font-weight: 700;
  font-size: 14px;
}

.ldm-summary-header__meta {
  color: #94a3b8;
  font-size: 12px;
  margin-top: 2px;
}

.ldm-round {
  margin-bottom: 10px;
}

.ldm-round__label {
  color: #7fb3d3;
  font-size: 12px;
  margin-bottom: 6px;
  font-weight: 600;
}

.ldm-lines-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ldm-line-chip {
  background: #0f2035;
  border: 1px solid #1e3a5f;
  border-radius: 10px;
  padding: 6px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.ldm-line-chip__name {
  color: #60a5fa;
  font-size: 12px;
  font-weight: 600;
}

.ldm-line-chip__count {
  color: #94a3b8;
  font-size: 11px;
}
</style>