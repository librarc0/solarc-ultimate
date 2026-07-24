<template>
  <div class="match-input-page">
    <van-nav-bar
      :title="`录入比赛（${stepTitles[step - 1]}）`"
      left-arrow
      @click-left="handleBack"
    />

    <!-- 步骤条 -->
    <van-steps :active="step - 1" active-color="#1677ff" style="padding: 12px 0">
      <van-step>类型</van-step>
      <van-step>阵容</van-step>
      <van-step>统计</van-step>
      <van-step>确认</van-step>
    </van-steps>

    <!-- Step 1: 比赛基本信息 -->
    <template v-if="step === 1">
      <van-cell-group inset title="比赛基本信息">
        <van-field
          v-model="form.match_date"
          label="比赛日期"
          placeholder="YYYY-MM-DD"
          readonly
          @click="showDatePicker = true"
        />
        <van-field name="match_type" label="比赛类型">
          <template #input>
            <van-radio-group v-model="form.match_type" direction="horizontal">
              <van-radio name="internal">🆚 内战</van-radio>
              <van-radio name="external">🌍 外战</van-radio>
            </van-radio-group>
          </template>
        </van-field>
        <template v-if="form.match_type === 'external'">
          <van-field v-model="form.opponent_name" label="对方队名" placeholder="可选填写">
            <template #button>
              <van-button size="mini" type="primary" plain @click="openTeamPicker">📋 从排行榜选</van-button>
            </template>
          </van-field>
          <van-field label="对手强度">
            <template #input>
              <van-stepper v-model="form.opponent_strength" min="1" max="10" step="0.1" decimal-length="1" />
              <span style="margin-left: 8px; color: #888; font-size: 13px;">{{ strengthLabel }}</span>
            </template>
          </van-field>
        </template>
        <van-field label="统计详情">
          <template #input>
            <van-radio-group v-model="form.data_level" direction="vertical" style="gap:8px">
              <van-radio :name="1">📊 仅比分（基础）</van-radio>
              <van-radio :name="2">📋 进球 + 助攻（标准）</van-radio>
              <van-radio :name="3">🏆 完整统计（含防守 · 失误）</van-radio>
            </van-radio-group>
          </template>
        </van-field>
        <van-field
          v-model="form.notes"
          label="比赛备注"
          type="textarea"
          rows="2"
          required
          placeholder="必填：请说明比赛场景，如训练赛/友谊赛/联赛第X轮、时间地点等"
        />
        <van-collapse v-model="levelHelpOpen" style="margin: 0 16px 4px;">
          <van-collapse-item title="📖 统计详情说明" name="help">
            <div style="font-size:13px;color:#666;line-height:1.8">
              <div>📊 基础：记录比赛比分，适合仅知道结果的场景</div>
              <div>📋 标准：额外记录每人进球数、助攻数，可用于个人评分</div>
              <div>🏆 完整：再加防守盘、失误数，数据最完整，评分最精准</div>
              <div style="margin-top:6px;color:#94a3b8;font-size:12px">若填写字段不足，系统会自动按实际数据计算评分。</div>
            </div>
          </van-collapse-item>
        </van-collapse>
        <!-- 分组模式（仅内战） -->
        <template v-if="auth.isAdmin">
          <van-field name="schedule_event_id" label="关联日程">
            <template #input>
              <select v-if="linkableEvents.length" v-model.number="form.schedule_event_id" class="schedule-select">
                <option :value="0">不关联</option>
                <option v-for="event in linkableEvents" :key="event.id" :value="event.id">
                  {{ event.title }}（{{ event.start_date }}）
                </option>
              </select>
              <span v-else style="color:#888; font-size:13px">无可关联的已发布日程</span>
            </template>
          </van-field>
        </template>
      </van-cell-group>
      <div style="margin: 16px">
        <van-button round block type="primary" @click="goToStep2">下一步：选择阵容</van-button>
      </div>
    </template>

    <!-- Step 2: 分Line分配（通过Wizard） -->
    <template v-if="step === 2">
      <van-loading v-if="loadingPlayers" type="spinner" vertical style="padding: 40px 0" />
      <template v-else>
        <!-- 分line状态卡片 -->
        <van-cell-group v-if="wizardConfirmed" inset title="分Line确认状态" style="margin-bottom: 8px">
          <van-cell title="状态" value="✓ 已完成确认" />
          <template v-for="summary in lineDivisionSummary" :key="summary.name">
            <van-cell :title="summary.name" :label="`${summary.count}人：${summary.names}`" />
          </template>
          <van-cell>
            <template #title>
              <van-button size="small" type="primary" @click="showLineDivisionWizard = true">重新调整分Line</van-button>
            </template>
          </van-cell>
        </van-cell-group>

        <!-- 未confirm时的提示 -->
        <template v-if="!wizardConfirmed">
          <van-empty description="请先完成分Line配置" image="default" style="padding: 40px 0" />
          <div style="margin: 16px">
            <van-button round block type="primary" @click="showLineDivisionWizard = true">管理分Line</van-button>
          </div>
        </template>

        <!-- Step 2 导航按钮 -->
        <div v-if="wizardConfirmed" style="margin: 16px; display: flex; gap: 8px; flex-wrap: wrap">
          <van-button round block plain @click="step = 1">上一步</van-button>
          <van-button round block type="primary" @click="goToStep3">下一步：录入统计</van-button>
          <van-button round block plain icon="video-o" @click="goToLive" style="margin-top: 4px">
            进入实况录入
          </van-button>
        </div>
      </template>

      <!-- Line Division Wizard 弹窗 -->
      <LineDivisionWizard
        :visible="showLineDivisionWizard"
        :match-type="wizardMatchType"
        :attendance-event-id="form.schedule_event_id > 0 ? form.schedule_event_id : undefined"
        :initial-attending-ids="teamA.concat(teamB)"
        mode="match"
        @update:visible="showLineDivisionWizard = $event"
        @confirm="handleWizardConfirm"
      />
    </template>

    <!-- Step 3: 统计录入 （Level 1: 比分 / Level 2/3: 详细统计） -->
    <template v-if="step === 3">
      <!-- 实时比分卡 -->
      <div class="score-live-bar">
        <div class="score-live__side score-live__side--left">
          <span class="score-live__team-name">{{ form.match_type === 'external' ? '我方' : '队 A' }}</span>
          <span class="score-live__num">{{ computedScoreUs }}</span>
        </div>
        <span class="score-live__vs">VS</span>
        <div class="score-live__side score-live__side--right">
          <span class="score-live__num">{{ computedScoreThem }}</span>
          <span class="score-live__team-name">{{ form.match_type === 'external' ? '对方' : '队 B' }}</span>
        </div>
      </div>

      <!-- Level 1：直接输入比分 -->
      <template v-if="form.data_level === 1">
        <div class="score-input-card">
          <div class="score-input-card__title">录入比赛得分</div>
          <div class="score-input-row">
            <div class="score-input-col">
              <span class="score-input-label">{{ form.match_type === 'external' ? '我方' : '队 A' }}</span>
              <van-stepper v-model="form.score_us" min="0" button-size="36px" input-width="52px" />
            </div>
            <span class="score-input-dash">—</span>
            <div class="score-input-col">
              <span class="score-input-label">{{ form.match_type === 'internal' ? '队 B' : '对方' }}</span>
              <van-stepper v-model="form.score_them" min="0" button-size="36px" input-width="52px" />
            </div>
          </div>
        </div>
      </template>

      <!-- Level 2/3：逐人录入 -->
      <template v-else>
        <!-- 队 A -->
        <div class="stat-team-section">
          <div class="stat-team-header">
            <span class="stat-team-title">{{ form.match_type === 'external' ? '我方球员' : '队 A' }}</span>
            <div class="stat-team-totals">
              <span class="ttl-badge ttl-badge--G">{{ teamAStats.goals }}G</span>
              <span class="ttl-badge ttl-badge--A">{{ teamAStats.assists }}A</span>
              <span v-if="form.data_level >= 3" class="ttl-badge ttl-badge--D">{{ teamAStats.defense }}D</span>
              <span v-if="form.data_level >= 3" class="ttl-badge ttl-badge--T">{{ teamAStats.turnovers }}T</span>
            </div>
          </div>
          <div class="pstat-list">
            <div
              v-for="pid in teamA"
              :key="`pa-${pid}`"
              class="pstat-card"
              :class="{ 'pstat-card--filled': hasStats(pid) }"
            >
              <div class="pstat-card__head">
                <div class="pstat-identity">
                  <span class="pstat-name">{{ getPlayerName(pid) }}</span>
                  <span v-if="getPlayer(pid)?.jersey_number != null" class="pstat-jersey">#{{ getPlayer(pid)?.jersey_number }}</span>
                  <span v-if="getPlayer(pid)?.gender" class="pstat-gender" :class="getPlayer(pid)?.gender === 'M' ? 'pstat-gender--m' : 'pstat-gender--f'">{{ getPlayer(pid)?.gender === 'M' ? '♂' : '♀' }}</span>
                </div>
                <div class="pstat-badges">
                  <span v-if="ensureStats(pid).goals > 0" class="sum-chip sum-chip--G">{{ ensureStats(pid).goals }}G</span>
                  <span v-if="ensureStats(pid).assists > 0" class="sum-chip sum-chip--A">{{ ensureStats(pid).assists }}A</span>
                  <span v-if="form.data_level >= 3 && ensureStats(pid).defense > 0" class="sum-chip sum-chip--D">{{ ensureStats(pid).defense }}D</span>
                  <span v-if="form.data_level >= 3 && ensureStats(pid).turnovers > 0" class="sum-chip sum-chip--T">{{ ensureStats(pid).turnovers }}T</span>
                </div>
              </div>
              <div class="pstat-card__ctrls">
                <div class="pstat-ctrl-item">
                  <span class="pstat-ctrl-label">进球</span>
                  <van-stepper v-model="ensureStats(pid).goals" min="0" button-size="32px" />
                </div>
                <div class="pstat-ctrl-item">
                  <span class="pstat-ctrl-label">助攻</span>
                  <van-stepper v-model="ensureStats(pid).assists" min="0" button-size="32px" />
                </div>
                <template v-if="form.data_level >= 3">
                  <div class="pstat-ctrl-item">
                    <span class="pstat-ctrl-label">防守盘</span>
                    <van-stepper v-model="ensureStats(pid).defense" min="0" button-size="32px" />
                  </div>
                  <div class="pstat-ctrl-item">
                    <span class="pstat-ctrl-label">失误</span>
                    <van-stepper v-model="ensureStats(pid).turnovers" min="0" button-size="32px" />
                  </div>
                </template>
              </div>
            </div>
          </div>
        </div>

        <!-- 队 B（内战） -->
        <template v-if="form.match_type === 'internal'">
          <div class="stat-team-section">
            <div class="stat-team-header">
              <span class="stat-team-title stat-team-title--b">队 B</span>
              <div class="stat-team-totals">
                <span class="ttl-badge ttl-badge--G">{{ teamBStats.goals }}G</span>
                <span class="ttl-badge ttl-badge--A">{{ teamBStats.assists }}A</span>
                <span v-if="form.data_level >= 3" class="ttl-badge ttl-badge--D">{{ teamBStats.defense }}D</span>
                <span v-if="form.data_level >= 3" class="ttl-badge ttl-badge--T">{{ teamBStats.turnovers }}T</span>
              </div>
            </div>
            <div class="pstat-list">
              <div
                v-for="pid in teamB"
                :key="`pb-${pid}`"
                class="pstat-card pstat-card--b"
                :class="{ 'pstat-card--filled pstat-card--b-filled': hasStats(pid) }"
              >
                <div class="pstat-card__head">
                  <div class="pstat-identity">
                    <span class="pstat-name">{{ getPlayerName(pid) }}</span>
                    <span v-if="getPlayer(pid)?.jersey_number != null" class="pstat-jersey">#{{ getPlayer(pid)?.jersey_number }}</span>
                    <span v-if="getPlayer(pid)?.gender" class="pstat-gender" :class="getPlayer(pid)?.gender === 'M' ? 'pstat-gender--m' : 'pstat-gender--f'">{{ getPlayer(pid)?.gender === 'M' ? '♂' : '♀' }}</span>
                  </div>
                  <div class="pstat-badges">
                    <span v-if="ensureStats(pid).goals > 0" class="sum-chip sum-chip--G">{{ ensureStats(pid).goals }}G</span>
                    <span v-if="ensureStats(pid).assists > 0" class="sum-chip sum-chip--A">{{ ensureStats(pid).assists }}A</span>
                    <span v-if="form.data_level >= 3 && ensureStats(pid).defense > 0" class="sum-chip sum-chip--D">{{ ensureStats(pid).defense }}D</span>
                    <span v-if="form.data_level >= 3 && ensureStats(pid).turnovers > 0" class="sum-chip sum-chip--T">{{ ensureStats(pid).turnovers }}T</span>
                  </div>
                </div>
                <div class="pstat-card__ctrls">
                  <div class="pstat-ctrl-item">
                    <span class="pstat-ctrl-label">进球</span>
                    <van-stepper v-model="ensureStats(pid).goals" min="0" button-size="32px" />
                  </div>
                  <div class="pstat-ctrl-item">
                    <span class="pstat-ctrl-label">助攻</span>
                    <van-stepper v-model="ensureStats(pid).assists" min="0" button-size="32px" />
                  </div>
                  <template v-if="form.data_level >= 3">
                    <div class="pstat-ctrl-item">
                      <span class="pstat-ctrl-label">防守盘</span>
                      <van-stepper v-model="ensureStats(pid).defense" min="0" button-size="32px" />
                    </div>
                    <div class="pstat-ctrl-item">
                      <span class="pstat-ctrl-label">失误</span>
                      <van-stepper v-model="ensureStats(pid).turnovers" min="0" button-size="32px" />
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- 外战：录入对方总得分 -->
        <template v-if="form.match_type === 'external'">
          <div class="score-input-card score-input-card--them">
            <div class="score-input-card__title">对方总得分</div>
            <van-stepper v-model="form.score_them" min="0" button-size="36px" input-width="52px" />
          </div>
        </template>
      </template>

      <div class="step-nav">
        <van-button round block plain @click="step = 2">上一步</van-button>
        <van-button round block type="primary" @click="goToStep4">下一步：确认</van-button>
      </div>
    </template>

    <!-- Step 4: 确认提交 -->
    <template v-if="step === 4">
      <!-- 非管理员：审批提示 -->
      <van-notice-bar
        v-if="!auth.isAdmin"
        wrapable
        :scrollable="false"
        left-icon="info-o"
        text="比赛将提交给管理员审批，审批通过后才会计入评分系统"
        color="#ff976a"
        background="#fff7e6"
        style="margin: 8px 16px; border-radius: 8px;"
      />
      <van-cell-group inset title="比赛信息">
        <van-cell title="比赛日期" :value="form.match_date" />
        <van-cell title="类型" :value="form.match_type === 'internal' ? '内战' : '外战'" />
        <van-cell title="比分" :value="`${computedScoreUs} — ${computedScoreThem}`" />
        <van-cell v-if="form.match_type === 'external'" title="对手强度" :value="`${form.opponent_strength}/10`" />
        <van-cell title="统计详情" :value="{ 1: '基础数据（仅比分）', 2: '标准数据（进球 + 助攻）', 3: '完整数据（进球 + 助攻 + 防守 + 失误）' }[form.data_level]" />
        <van-cell title="比赛备注" :value="form.notes" />
      </van-cell-group>
      <van-cell-group inset title="阵容">
        <van-cell :title="form.match_type === 'external' ? '我方队员' : '队A'" :value="teamA.map(getPlayerName).join(', ')" />
        <van-cell v-if="form.match_type === 'internal'" title="队B" :value="teamB.map(getPlayerName).join(', ')" />
      </van-cell-group>
      <div style="margin: 16px; display: flex; gap: 8px">
        <van-button round block plain @click="step = 3">上一步</van-button>
        <van-button round block type="primary" :loading="submitting" @click="handleSubmit">
          提交比赛记录
        </van-button>
      </div>
    </template>

    <!-- 日期选择器 -->
    <van-popup v-model:show="showDatePicker" position="bottom">
      <van-date-picker
        v-model="dateParts"
        title="选择日期"
        @confirm="onDateConfirm"
        @cancel="showDatePicker = false"
      />
    </van-popup>

    <!-- 排行榜对手选取弹窗 -->
    <van-popup
      v-model:show="showTeamPicker"
      position="bottom"
      round
      style="height: 70vh; display: flex; flex-direction: column;"
    >
      <div style="padding: 12px 16px 0;">
        <van-search
          v-model="teamPickerSearch"
          placeholder="搜索队伍名称"
          shape="round"
          @update:model-value="onTeamSearch"
        />
        <!-- 赛季选择 -->
        <div v-if="pickerSeasons.length > 1" style="display: flex; align-items: center; gap: 8px; margin-top: 8px; padding-bottom: 8px; border-bottom: 1px solid #f0f0f0;">
          <span style="font-size: 13px; color: #666; flex-shrink: 0;">赛季：</span>
          <select v-model.number="pickerSeasonId" class="schedule-select" style="flex: 1;">
            <option :value="null">全部赛季</option>
            <option v-for="s in pickerSeasons" :key="s.id" :value="s.id">
              {{ s.name }}{{ s.is_active ? ' (当前)' : '' }}
            </option>
          </select>
        </div>
      </div>
      <van-list
        v-if="!teamPickerLoading"
        style="flex: 1; overflow-y: auto; padding-bottom: 16px;"
      >
        <van-cell
          v-for="team in filteredPickerTeams"
          :key="team.name"
          :title="team.name"
          :label="`排名 #${team.rank}　积分 ${team.total_score.toFixed(1)}`"
          is-link
          @click="selectTeamFromRanking(team)"
        />
        <van-empty v-if="filteredPickerTeams.length === 0" description="暂无队伍数据" />
      </van-list>
      <div v-else style="padding: 32px; text-align: center;">
        <van-loading type="spinner" />
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'
import scheduleApi, { type ScheduleEvent } from '@/api/schedule'
import LineDivisionWizard from '@/components/lineup/LineDivisionWizard.vue'
import type { LineDivisionResult } from '@/composables/useLineDivisionWizard'
import { fetchTeamsForMatch, fetchTeamStrengthV2, fetchSeasons, type ExternalTeamForMatch, type SeasonOut } from '@/api/publicRanking'

interface Player { id: number; username: string; display_name: string | null; conservative_rating: number; gender: string | null; jersey_number: number | null }
interface StatEntry { goals: number; assists: number; defense: number; turnovers: number }

const router = useRouter()
const auth = useAuthStore()

// ─── 可关联日程列表（管理员加载）──────────────────────────────────────────────
const linkableEvents = ref<ScheduleEvent[]>([])
const step = ref(1)
const stepTitles = ['类型选择', '阵容分配', '统计录入', '确认提交']
const submitting = ref(false)
const loadingPlayers = ref(false)
const showDatePicker = ref(false)
const levelHelpOpen = ref<string[]>([])

const today = new Date()
const dateParts = ref([
  String(today.getFullYear()),
  String(today.getMonth() + 1).padStart(2, '0'),
  String(today.getDate()).padStart(2, '0'),
])

const form = reactive({
  match_date: today.toISOString().slice(0, 10),
  match_type: 'internal',
  opponent_name: '',
  opponent_strength: 5,
  opponent_external_team_id: null as number | null,
  opponent_calibrated_mu: null as number | null,
  opponent_calibrated_sigma: null as number | null,
  data_level: 1,
  score_us: 0,
  score_them: 0,
  notes: '',
  schedule_event_id: 0,  // 0 表示不关联
})

// ─── Line Division Wizard State ────────────────────────────────────────────
const showLineDivisionWizard = ref(false)
const wizardConfirmed = ref(false)
const lineDivisionSummary = ref<Array<{ name: string; count: number; names: string }>>([])
const wizardMatchType = computed((): 'game' | 'internal' => 
  form.match_type === 'external' ? 'game' : 'internal'
)

function handleWizardConfirm(result: LineDivisionResult) {
  wizardConfirmed.value = true

  if (result.matchType === 'game') {
    // 外战：所有参战球员（O + 全部 D line）合并为 teamA 供统计录入
    const allGamePlayers = [
      ...result.oLineIds,
      ...result.dLine1Ids,
      ...result.dLine2Ids,
    ].filter((id, idx, arr) => arr.indexOf(id) === idx) // 去重
    teamA.value = allGamePlayers.length > 0 ? allGamePlayers : result.attendingIds
    teamB.value = []

    // 分line摘要：按 line 分别展示
    lineDivisionSummary.value = []
    if (result.oLineIds.length) {
      lineDivisionSummary.value.push({
        name: 'O Line',
        count: result.oLineIds.length,
        names: result.oLineIds.map(pid => getPlayerName(pid)).join('、'),
      })
    }
    if (result.dLine1Ids.length) {
      lineDivisionSummary.value.push({
        name: result.dLine2Ids.length ? 'D Line 1' : 'D Line',
        count: result.dLine1Ids.length,
        names: result.dLine1Ids.map(pid => getPlayerName(pid)).join('、'),
      })
    }
    if (result.dLine2Ids.length) {
      lineDivisionSummary.value.push({
        name: 'D Line 2',
        count: result.dLine2Ids.length,
        names: result.dLine2Ids.map(pid => getPlayerName(pid)).join('、'),
      })
    }
    if (!lineDivisionSummary.value.length) {
      lineDivisionSummary.value = [{
        name: '全体参战',
        count: teamA.value.length,
        names: teamA.value.map(pid => getPlayerName(pid)).join('、'),
      }]
    }
  } else {
    // 内战
    teamA.value = result.teamAIds
    teamB.value = result.teamBIds
    lineDivisionSummary.value = [
      {
        name: '队A',
        count: teamA.value.length,
        names: teamA.value.map(pid => getPlayerName(pid)).join('、'),
      },
      {
        name: '队B',
        count: teamB.value.length,
        names: teamB.value.map(pid => getPlayerName(pid)).join('、'),
      },
    ]
  }

  showLineDivisionWizard.value = false
  showToast('分line确认成功，请继续下一步')
}

const availablePlayers = ref<Player[]>([])
const teamA = ref<number[]>([])
const teamB = ref<number[]>([])
const stats = reactive<Record<number, StatEntry>>({})

async function loadLinkableEvents() {
  if (!auth.isAdmin) return
  try {
    linkableEvents.value = await scheduleApi.getLinkableEvents(form.match_type as 'external' | 'internal')
  } catch {
    linkableEvents.value = []
  }
}

// 当 data_level >= 2 时，比分由得分汇总自动计算
const computedScoreUs = computed(() => {
  if (form.data_level >= 2) {
    return teamA.value.reduce((sum, pid) => sum + (stats[pid]?.goals ?? 0), 0)
  }
  return form.score_us
})
const computedScoreThem = computed(() => {
  if (form.data_level >= 2 && form.match_type === 'internal') {
    return teamB.value.reduce((sum, pid) => sum + (stats[pid]?.goals ?? 0), 0)
  }
  return form.score_them
})

// 队伍合计统计（用于 Step3 团队汇总行）
const teamAStats = computed(() => ({
  goals: teamA.value.reduce((s, pid) => s + (stats[pid]?.goals ?? 0), 0),
  assists: teamA.value.reduce((s, pid) => s + (stats[pid]?.assists ?? 0), 0),
  defense: teamA.value.reduce((s, pid) => s + (stats[pid]?.defense ?? 0), 0),
  turnovers: teamA.value.reduce((s, pid) => s + (stats[pid]?.turnovers ?? 0), 0),
}))
const teamBStats = computed(() => ({
  goals: teamB.value.reduce((s, pid) => s + (stats[pid]?.goals ?? 0), 0),
  assists: teamB.value.reduce((s, pid) => s + (stats[pid]?.assists ?? 0), 0),
  defense: teamB.value.reduce((s, pid) => s + (stats[pid]?.defense ?? 0), 0),
  turnovers: teamB.value.reduce((s, pid) => s + (stats[pid]?.turnovers ?? 0), 0),
}))

function hasStats(pid: number): boolean {
  const s = stats[pid]
  return !!s && (s.goals > 0 || s.assists > 0 || s.defense > 0 || s.turnovers > 0)
}

function getPlayer(pid: number): Player | undefined {
  return availablePlayers.value.find(x => x.id === pid)
}

const strengthLabel = computed(() => {
  const s = form.opponent_strength
  if (s <= 2) return '弱队'
  if (s <= 4) return '一般'
  if (s <= 6) return '相当'
  if (s <= 8) return '较强'
  return '强队'
})

// --- 排行榜对手选取 ---
const showTeamPicker = ref(false)
const teamPickerLoading = ref(false)
const teamPickerSearch = ref('')
const allPickerTeams = ref<ExternalTeamForMatch[]>([])
const pickerSeasons = ref<SeasonOut[]>([])
const pickerSeasonId = ref<number | null>(null)

const filteredPickerTeams = computed(() => {
  const q = teamPickerSearch.value.trim().toLowerCase()
  if (!q) return allPickerTeams.value
  return allPickerTeams.value.filter((t) => t.name.toLowerCase().includes(q))
})

async function loadPickerTeams() {
  teamPickerLoading.value = true
  try {
    allPickerTeams.value = await fetchTeamsForMatch(undefined, pickerSeasonId.value ?? undefined)
  } catch {
    showToast('加载排行榜失败')
  } finally {
    teamPickerLoading.value = false
  }
}

async function openTeamPicker() {
  showTeamPicker.value = true
  // 初次打开：加载赛季列表
  if (!pickerSeasons.value.length) {
    try {
      pickerSeasons.value = await fetchSeasons()
      // 默认不过滤赛季（全部赛季），便于用户自选
    } catch { /* 加载失败则只显示全部赛季选项 */ }
  }
  if (allPickerTeams.value.length === 0) {
    await loadPickerTeams()
  }
}

// 赛季切换时重新加载队伍
watch(pickerSeasonId, () => {
  allPickerTeams.value = []
  void loadPickerTeams()
})

function onTeamSearch(_val: string) {
  // filteredPickerTeams is a computed, no action needed
}

function selectTeamFromRanking(team: ExternalTeamForMatch) {
  form.opponent_name = team.name
  // 线性映射：1 + (score - min) / (max - min) * 9
  const scores = allPickerTeams.value.map((t) => t.total_score)
  const minScore = Math.min(...scores)
  const maxScore = Math.max(...scores)
  let strength: number
  if (maxScore === minScore) {
    strength = 5.0
  } else {
    strength = 1 + ((team.total_score - minScore) / (maxScore - minScore)) * 9
  }
  form.opponent_strength = Math.round(strength * 10) / 10
  showTeamPicker.value = false

  // v2 校准：异步获取 calibrated_mu/sigma
  const teamId = auth.user?.team_id
  if (teamId) {
    fetchTeamStrengthV2(team.name, teamId, pickerSeasonId.value ?? undefined)
      .then((v2) => {
        form.opponent_external_team_id = v2.team_id
        form.opponent_calibrated_mu = v2.calibrated_mu
        form.opponent_calibrated_sigma = v2.calibrated_sigma
        form.opponent_strength = Math.round(v2.strength * 10) / 10
      })
      .catch(() => {
        // v2 失败时保留已有的 strength 线性映射值
        form.opponent_external_team_id = null
        form.opponent_calibrated_mu = null
        form.opponent_calibrated_sigma = null
      })
  }
  showToast(`已选：${team.name}，强度 ${form.opponent_strength}`)
}
// --- end 排行榜对手选取 ---

function onDateConfirm({ selectedValues }: { selectedValues: string[] }) {
  const [y, m, d] = selectedValues
  form.match_date = `${y}-${m}-${d}`
  showDatePicker.value = false
}

async function loadPlayers() {
  loadingPlayers.value = true
  try {
    const res = await api.get('/players', { params: { status: 'active', page_size: 100 } })
    availablePlayers.value = res.data
    // 初始化 stats
    for (const p of res.data as Player[]) {
      if (!stats[p.id]) stats[p.id] = { goals: 0, assists: 0, defense: 0, turnovers: 0 }
    }
  } catch {
    showToast('加载队员列表失败')
  } finally {
    loadingPlayers.value = false
  }
}

const DRAFT_KEY = 'match_input_draft'

// 自动保存草稿
watch(
  [step, teamA, teamB, () => JSON.stringify(form), () => JSON.stringify(stats)],
  () => {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({
      step: step.value,
      form: { ...form },
      teamA: teamA.value,
      teamB: teamB.value,
      stats: JSON.parse(JSON.stringify(stats)),
    }))
  },
  { deep: true }
)

watch(() => form.match_type, () => {
  form.schedule_event_id = 0
  wizardConfirmed.value = false
  lineDivisionSummary.value = []
  void loadLinkableEvents()
})

// 关联日程后自动填入比赛备注（仅在备注为空时填入）
watch(() => form.schedule_event_id, (newId) => {
  if (newId > 0 && !form.notes.trim()) {
    const event = linkableEvents.value.find(e => e.id === newId)
    if (event) {
      const typeLabel: Record<string, string> = { game: '外战', internal: '内战', training: '训练', other: '活动' }
      const label = typeLabel[event.event_type] ?? event.event_type
      let autoNote = `${label}：${event.title}（${event.start_date}`
      if (event.end_date && event.end_date !== event.start_date) {
        autoNote += ` ~ ${event.end_date}`
      }
      autoNote += '）'
      if (event.description?.trim()) {
        autoNote += `\n${event.description.trim()}`
      }
      form.notes = autoNote
    }
  }
})

onMounted(async () => {
  await loadPlayers()
  // 恢复草稿
  const saved = localStorage.getItem(DRAFT_KEY)
  if (saved) {
    try {
      const draft = JSON.parse(saved)
      step.value = draft.step ?? 1
      if (draft.form) Object.assign(form, draft.form)
      if (Array.isArray(draft.teamA)) teamA.value = draft.teamA
      if (Array.isArray(draft.teamB)) teamB.value = draft.teamB
      if (draft.stats) {
        for (const [k, v] of Object.entries<StatEntry>(draft.stats)) {
          stats[Number(k)] = v
        }
      }
    } catch { /* 解析失败则忽略 */ }
  }

  await loadLinkableEvents()
})

function getPlayerName(pid: number) {
  const p = availablePlayers.value.find(x => x.id === pid)
  return p ? (p.display_name || p.username) : `#${pid}`
}

function ensureStats(pid: number) {
  if (!stats[pid]) stats[pid] = { goals: 0, assists: 0, defense: 0, turnovers: 0 }
  return stats[pid]
}

function goToLive() {
  const needsWizard = form.match_type === 'internal' || form.match_type === 'external'
  
  if (needsWizard && !wizardConfirmed.value) {
    showToast('请先完成分line确认')
    return
  }
  
  if (teamA.value.length === 0 || (form.match_type === 'internal' && teamB.value.length === 0)) {
    showToast(form.match_type === 'internal' ? '请先分配队A和队B成员' : '请先分配队A成员')
    return
  }
  
  // 通过 sessionStorage 传递队伍数据（比 history.state 更可靠）
  sessionStorage.setItem('live_match_state', JSON.stringify({
    teamAIds: teamA.value,
    teamBIds: teamB.value,
    players: availablePlayers.value,
    matchType: form.match_type,
    notes: form.notes,
  }))
  router.push({ name: 'match-live' })
}

function goToStep4() {
  // 校验比分合理性
  const totalUs = computedScoreUs.value
  const totalThem = computedScoreThem.value
  if (totalUs === 0 && totalThem === 0) {
    showToast('请至少录入一方得分')
    return
  }
  // Level 2+：校验助攻数 ≤ 得分数，且不能助攻自己
  if (form.data_level >= 2) {
    const allIds = form.match_type === 'internal' ? [...teamA.value, ...teamB.value] : teamA.value
    const totalGoals = allIds.reduce((s, pid) => s + (stats[pid]?.goals ?? 0), 0)
    const totalAssists = allIds.reduce((s, pid) => s + (stats[pid]?.assists ?? 0), 0)
    if (totalAssists > totalGoals) {
      showToast(`助攻数（${totalAssists}）不能超过得分数（${totalGoals}）`)
      return
    }
    // 逐队校验：每个球员的助攻数不能超过本队其他人得分之和（不能自助）
    const validateTeamSelfAssist = (ids: number[]): boolean => {
      const teamGoals = ids.reduce((s, pid) => s + (stats[pid]?.goals ?? 0), 0)
      for (const pid of ids) {
        const playerGoals = stats[pid]?.goals ?? 0
        const playerAssists = stats[pid]?.assists ?? 0
        const maxPossibleAssists = teamGoals - playerGoals
        if (playerAssists > maxPossibleAssists) {
          const name = getPlayerName(pid)
          showToast(`${name} 的助攻数（${playerAssists}）不合法：本队其他队员共得 ${maxPossibleAssists} 分，不能助攻自己`)
          return false
        }
      }
      return true
    }
    if (!validateTeamSelfAssist(teamA.value)) return
    if (form.match_type === 'internal' && !validateTeamSelfAssist(teamB.value)) return
  }
  step.value = 4
}

function handleBack() {
  if (step.value > 1) step.value--
  else router.back()
}

async function goToStep2() {
  if (!form.notes.trim()) {
    showToast('请在基本信息中填写比赛备注')
    return
  }
  step.value = 2
}

function goToStep3() {
  // 对于内战和外战，都需要先通过wizard确认分line
  const needsWizard = form.match_type === 'internal' || form.match_type === 'external'
  
  if (needsWizard && !wizardConfirmed.value) {
    showToast('请先完成分line确认')
    return
  }
  
  // 校验队伍非空（作为防守检查）
  if (teamA.value.length === 0 || (form.match_type === 'internal' && teamB.value.length === 0)) {
    showToast(form.match_type === 'internal' ? '请先分配队A和队B成员' : '请先分配队A成员')
    return
  }
  
  // 内战还需检查无重叠
  if (form.match_type === 'internal') {
    const overlap = teamA.value.filter(id => teamB.value.includes(id))
    if (overlap.length > 0) {
      showToast(`${overlap.map(getPlayerName).join(', ')} 同时出现在两队`)
      return
    }
  }
  
  step.value = 3
}

async function handleSubmit() {
  submitting.value = true
  try {
    const buildTeam = (ids: number[]) => ids.map(pid => ({
      player_id: pid,
      goals: form.data_level >= 2 ? (stats[pid]?.goals ?? 0) : undefined,
      assists: form.data_level >= 2 ? (stats[pid]?.assists ?? 0) : undefined,
      defenses: form.data_level >= 3 ? (stats[pid]?.defense ?? 0) : undefined,
      turnovers: form.data_level >= 3 ? (stats[pid]?.turnovers ?? 0) : undefined,
    }))

    const payload: Record<string, unknown> = {
      match_date: form.match_date,
      match_type: form.match_type,
      score_us: computedScoreUs.value,
      score_them: computedScoreThem.value,
      data_level: form.data_level,
      team_a: buildTeam(teamA.value),
      team_b: buildTeam(teamB.value),
      notes: form.notes.trim(),
    }

    if (form.match_type === 'external') {
      payload.opponent_strength = form.opponent_strength
      payload.opponent_name = form.opponent_name || undefined
      if (form.opponent_external_team_id) {
        payload.opponent_external_team_id = form.opponent_external_team_id
      }
      if (form.opponent_calibrated_mu != null) {
        payload.opponent_calibrated_mu = form.opponent_calibrated_mu
        payload.opponent_calibrated_sigma = form.opponent_calibrated_sigma
      }
      payload.team_b = []  // 外战不需要对方详细阵容
    }

    if (form.schedule_event_id > 0) {
      payload.schedule_event_id = form.schedule_event_id
    }

    await api.post('/matches', payload)
    localStorage.removeItem(DRAFT_KEY)  // 成功后清除草稿
    showToast({ message: auth.isAdmin ? '录入成功，评分已更新' : '比赛已提交，等待管理员审批', type: 'success' })
    router.push('/home')
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '录入失败，请检查数据')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.match-input-page {
  padding-bottom: env(safe-area-inset-bottom, 20px);
  min-height: 100vh;
  background: #f7f8fa;
}

.score-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 0;
}

.score-team {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.score-sep {
  font-size: 20px;
  font-weight: 700;
  color: #666;
}

.stat-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 6px;
}

/* ─── Step 3 升级版统计录入 ─────────────────────────── */
.score-live-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin: 10px 16px 14px;
  padding: 14px 20px;
  background: linear-gradient(135deg, #0f2035, #0c1c30);
  border: 1px solid #1e3a5f;
  border-radius: 18px;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.2);
}

.score-live__side {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.score-live__side--right {
  flex-direction: row-reverse;
}

.score-live__team-name {
  color: #6ea8d8;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.score-live__num {
  color: #e2f0ff;
  font-size: 40px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  min-width: 40px;
  text-align: center;
  line-height: 1;
  text-shadow: 0 0 18px rgba(96, 165, 250, 0.5);
}

.score-live__side--left .score-live__num {
  color: #60a5fa;
  text-shadow: 0 0 18px rgba(96, 165, 250, 0.6);
}

.score-live__side--right .score-live__num {
  color: #fb923c;
  text-shadow: 0 0 18px rgba(251, 146, 60, 0.5);
}

.score-live__vs {
  color: #2d5580;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 3px;
  flex-shrink: 0;
}

.score-input-card {
  margin: 0 16px 14px;
  background: #fff;
  border-radius: 16px;
  padding: 18px 16px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.07);
  text-align: center;
}

.score-input-card--them {
  margin-top: 4px;
}

.score-input-card__title {
  font-size: 13px;
  font-weight: 600;
  color: #555;
  margin-bottom: 16px;
}

.score-input-row {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 18px;
}

.score-input-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.score-input-label {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}

.score-input-dash {
  font-size: 22px;
  font-weight: 700;
  color: #ccc;
  padding-bottom: 4px;
}

.stat-team-section {
  margin: 0 16px 4px;
}

.stat-team-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 2px 8px;
}

.stat-team-title {
  font-size: 14px;
  font-weight: 700;
  color: #1a3560;
}

.stat-team-title--b {
  color: #7e1d5a;
}

.stat-team-totals {
  display: flex;
  gap: 5px;
}

.ttl-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 99px;
}

.ttl-badge--G { background: #dbeafe; color: #1d4ed8; }
.ttl-badge--A { background: #d1fae5; color: #059669; }
.ttl-badge--D { background: #fef3c7; color: #92400e; }
.ttl-badge--T { background: #fee2e2; color: #b91c1c; }

.pstat-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.pstat-card {
  background: #fff;
  border-radius: 14px;
  padding: 12px 14px 14px;
  border: 1.5px solid #e5ecf5;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.pstat-card--b {
  border-color: #f3e8f5;
}

.pstat-card--filled {
  border-color: #93c5fd;
  box-shadow: 0 2px 10px rgba(59, 130, 246, 0.10);
}

.pstat-card--b-filled {
  border-color: #f9a8d4 !important;
  box-shadow: 0 2px 10px rgba(236, 72, 153, 0.10) !important;
}

.pstat-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.pstat-identity {
  display: flex;
  align-items: center;
  gap: 5px;
}

.pstat-name {
  font-size: 15px;
  font-weight: 700;
  color: #1a2942;
}

.pstat-jersey {
  font-size: 11px;
  color: #94a3b8;
}

.pstat-gender--m { color: #3b82f6; font-size: 14px; }
.pstat-gender--f { color: #ec4899; font-size: 14px; }

.pstat-badges {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.sum-chip {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 99px;
}

.sum-chip--G { background: #dbeafe; color: #1d4ed8; }
.sum-chip--A { background: #d1fae5; color: #059669; }
.sum-chip--D { background: #fef3c7; color: #92400e; }
.sum-chip--T { background: #fee2e2; color: #b91c1c; }

.pstat-card__ctrls {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 12px;
}

.pstat-ctrl-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #f8fafc;
  border-radius: 10px;
  padding: 8px 10px;
  gap: 6px;
}

.pstat-ctrl-label {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
  white-space: nowrap;
}

.step-nav {
  display: flex;
  gap: 8px;
  margin: 16px;
}

.schedule-select {
  width: 100%;
  min-height: 36px;
  border: 1px solid #d0d7de;
  border-radius: 8px;
  padding: 0 10px;
  background: #fff;
  color: #111827;
}

.player-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.jersey-tag {
  color: #666;
  font-size: 12px;
}

.gender {
  font-weight: 700;
  font-size: 13px;
}

.gender--m {
  color: #1677ff;
}

.gender--f {
  color: #e91e63;
}

.roster-layout {
  display: grid;
  gap: 12px;
  margin: 8px 16px 0;
}

.match-team-board {
  display: grid;
  gap: 10px;
}

.match-team-card {
  background: #0f2035;
  border: 1px solid #1e3a5f;
  border-radius: 12px;
  padding: 10px;
  transition: all .15s;
}

.match-team-card.active { border-color: #60a5fa; box-shadow: 0 0 0 1px rgba(96,165,250,.25); }
.match-team-card__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
.team-entry-hint { color: #6f8cab; font-size: 11px; margin-top: 2px; }
.pool-card {
  background: #0f2035;
  border: 1px solid #1e3a5f;
  border-radius: 12px;
  padding: 10px;
}
.pool-card__title { color: #e2e8f0; font-weight: 600; margin-bottom: 8px; }
.selection-summary { margin: 8px 0 10px; font-size: 12px; color: #475569; }
.selection-summary__text { line-height: 1.6; }
.line-empty { color: #6f8cab; font-size: 12px; text-align: center; padding: 10px 0; }
.assigned-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.assigned-chip {
  background: #152841; border: 1px solid #244160; border-radius: 10px; padding: 7px 9px; min-width: 130px; cursor: pointer;
}
.assigned-chip__name { color: #e2e8f0; font-size: 12px; font-weight: 600; }
.assigned-chip__meta { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 4px; }
.remove-hint { color: #7f95af; font-size: 10px; }
.pool-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 8px; }
.pool-player {
  background: #152841; border: 1px solid #244160; border-radius: 10px; padding: 8px; cursor: pointer; transition: all .15s;
}
.pool-player.active { border-color: #22c55e; background: #123324; }
.pool-player.used { border-color: #f59e0b; background: rgba(245, 158, 11, .12); box-shadow: 0 0 0 1px rgba(245, 158, 11, .2); }
.pool-player__top { display: flex; justify-content: space-between; gap: 6px; align-items: center; }
.pool-player__name { color: #e2e8f0; font-size: 12px; font-weight: 600; line-height: 1.4; }
.pool-player__meta { display: flex; justify-content: space-between; align-items: center; gap: 6px; margin-top: 6px; color: #94a3b8; font-size: 10px; }
.status-pill {
  display: inline-flex; align-items: center; justify-content: center; padding: 1px 6px; border-radius: 999px; color: #fff; font-size: 10px;
}
.status-pill--roster { background: #3b82f6; }
.rating-badge { font-size: 10px; color: #ffd54f; }

/* 实时比分条 */
.score-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  background: #1677ff;
  color: #fff;
  padding: 10px 16px;
  font-weight: 700;
}
.score-bar__team {
  display: flex;
  align-items: center;
  gap: 10px;
}
.score-bar__num {
  font-size: 28px;
  line-height: 1;
  min-width: 32px;
  text-align: center;
}
.score-bar__label {
  font-size: 13px;
  opacity: 0.85;
}
.score-bar__sep {
  font-size: 22px;
  opacity: 0.7;
}

/* ── Pad/PC 响应式优化 ── */
@media (min-width: 768px) {
  /* 球员选择池：更大的固定奶头尺寸 */
  .pool-grid {
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  }
  /* 阵容区域内边距加大 */
  .roster-layout {
    gap: 20px;
    margin: 8px 24px 0;
  }
  .match-team-card {
    padding: 14px 18px;
  }
  /* 比分栏限宽居中 */
  .score-bar {
    max-width: 640px;
    margin: 0 auto;
    border-radius: 12px;
  }
}

/* 桌面：双队并排展示，更直观 */
@media (min-width: 1024px) {
  .roster-layout {
    grid-template-columns: 1fr 1fr;
    margin: 8px 32px 0;
  }
  .pool-grid {
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  }
}
</style>
