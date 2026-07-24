<script setup lang="ts">
/**
 * LDWAnalysisTab — 分析报告 Tab
 *
 * game  (外战)  : 7 维详细表格 + 两两默契 + 文字说明（来自 SmartLineAnalyzeResponse）
 *               ——【智能分析】与【手动调整后一键分析】使用完全相同的格式与算法
 * internal (内战) : 每队平均能力 + 整体强度 + 默契度汇总（调用 auto_group 结果 + 本地计算）
 * training (训练) : 各 line 球员基础能力值表格（conservative_rating）
 */
import { computed } from 'vue'
import type { WizardMatchType, WizardPlayer, LocalLine, AutoGroupResult } from '@/composables/useLineDivisionWizard'
import type { SmartLineAnalyzeResponse, SmartLinePlayer } from '@/api/schedule'

const props = defineProps<{
  matchType: WizardMatchType
  allPlayers: WizardPlayer[]
  attendingIds: number[]
  // game 模式
  analysisResult: SmartLineAnalyzeResponse | null
  analysisLoading: boolean
  // internal 模式
  localLines: LocalLine[]
  currentLocalRound: number
  autoGroupResult: AutoGroupResult | null
  // schedule 模式 internal/training 复用 localLines 存放
}>()

const emit = defineEmits<{
  (e: 'runAnalysis'): void
}>()

// 是否是本地（手动）分析 —— 只影响 rationale banner 文字，不影响表格格式
const isLocalAnalysis = computed(() => (props.analysisResult?.rationale as any)?.from_local === true)

// ─── 辅助 ─────────────────────────────────────────────────────────────────────
function playerById(pid: number) {
  return props.allPlayers.find(p => p.id === pid)
}
function playerLabel(pid: number) {
  const p = playerById(pid)
  if (!p) return `#${pid}`
  const jersey = p.jersey_number != null ? `#${p.jersey_number} ` : ''
  const gender = p.gender === 'M' ? '♂' : p.gender === 'F' ? '♀' : ''
  return `${jersey}${p.display_name || p.username}${gender ? ' ' + gender : ''}`
}

// ─── 游戏类型分析 ──────────────────────────────────────────────────────────────
const gameLines = computed(() => props.analysisResult?.lines ?? [])

function lineMCount(players: SmartLinePlayer[]) {
  return players.filter(p => playerById(p.player_id)?.gender === 'M').length
}
function lineFCount(players: SmartLinePlayer[]) {
  return players.filter(p => playerById(p.player_id)?.gender === 'F').length
}

// ─── 内战类型分析 ─────────────────────────────────────────────────────────────
const internalDisplayLines = computed(() => {
  const round = props.currentLocalRound
  return props.localLines.filter(l => l.round_number === round)
})

function lineStrength(playerIds: number[]): number {
  if (!playerIds.length) return 0
  const total = playerIds.reduce((s, pid) => s + (playerById(pid)?.conservative_rating ?? 0), 0)
  return total / playerIds.length
}

// ─── 训练类型分析 ─────────────────────────────────────────────────────────────
const trainingDisplayLines = computed(() => props.localLines)
</script>

<template>
  <div class="analysis-tab">

    <!-- ── 外战分析 ─────────────────────────────────────────────────────── -->
    <template v-if="matchType === 'game'">
      <div class="section-header">
        <div class="section-header__info">
          <div class="section-title">O/D line 智能分析报告</div>
          <div class="section-desc">综合球员近期数据、能力评分、两两默契，给出最优阵容建议</div>
        </div>
        <van-button size="small" type="primary" :loading="analysisLoading" @click="$emit('runAnalysis')">
          一键分析
        </van-button>
      </div>

      <div v-if="!analysisResult && !analysisLoading" class="empty-hint">
        点击「一键分析」生成分 line 报告（基于当前分line配置）
      </div>

      <div v-if="analysisResult" class="analysis-report">
        <!-- 分析依据说明 -->
        <div class="rationale-banner">
          <div class="rationale-banner__title">
            {{ isLocalAnalysis ? '📊 当前分line分析报告' : '📊 智能 O/D 分线分析报告' }}
          </div>
          <template v-if="isLocalAnalysis">
            <div class="rationale-banner__desc">基于当前手动分 Line 配置，使用与智能分析完全相同的算法计算各维度评分</div>
            <div class="rationale-weights">
              <div class="weight-label">综合评分权重：</div>
              <span class="weight-tag">能力 35%</span>
              <span class="weight-tag">默契 20%</span>
              <span class="weight-tag">进攻 15%</span>
              <span class="weight-tag">终结 15%</span>
              <span class="weight-tag">近期 15%</span>
            </div>
          </template>
          <template v-else>
            <div class="rationale-banner__body">
              <span>近期 {{ (analysisResult.rationale as any)?.recent_matches_window ?? 6 }} 场外战数据</span>
              <span>· O line 上限 {{ (analysisResult.rationale as any)?.o_line_size ?? '-' }} 人</span>
              <span>· D line × {{ (analysisResult.rationale as any)?.d_line_count ?? 1 }}</span>
            </div>
            <div v-if="(analysisResult.rationale as any)?.description" class="rationale-banner__desc">
              {{ (analysisResult.rationale as any).description }}
            </div>
            <div class="rationale-weights">
              <div class="weight-label">综合评分权重：</div>
              <span class="weight-tag">能力 35%</span>
              <span class="weight-tag">默契 20%</span>
              <span class="weight-tag">进攻 15%</span>
              <span class="weight-tag">终结 15%</span>
              <span class="weight-tag">近期 15%</span>
            </div>
          </template>
        </div>

        <!-- 每条 line 详情（智能分析 & 手动分析统一格式） -->
        <div v-for="line in gameLines" :key="line.line_name" class="line-report-card">
          <div class="line-report-card__header">
            <span class="line-report-name">{{ line.line_name }}</span>
            <span class="score-pill">综合 {{ line.total_score.toFixed(1) }}</span>
            <span class="chem-pill">默契 {{ line.chemistry_average.toFixed(2) }}</span>
            <van-tag :type="line.line_type === 'o_line' ? 'primary' : 'success'" plain>{{ line.players.length }} 人</van-tag>
          </div>
          <!-- 性别/人数摘要 -->
          <div class="line-summary-bar">
            <span class="lsb-item gender-m">♂ {{ lineMCount(line.players) }}</span>
            <span class="lsb-dot">·</span>
            <span class="lsb-item gender-f">♀ {{ lineFCount(line.players) }}</span>
            <span class="lsb-dot">·</span>
            <span class="lsb-item">{{ line.line_type === 'o_line' ? '进攻优先：得分+稳定+默契' : '防守优先：出盘+低失误+压迫' }}</span>
          </div>
          <!-- 球员详情表格（统一格式） -->
          <div class="table-wrap">
            <table class="metric-table">
              <thead>
                <tr>
                  <th>队员</th>
                  <th>角色</th>
                  <th>总分</th>
                  <th>能力</th>
                  <th>默契</th>
                  <th>进攻</th>
                  <th>终结</th>
                  <th>近期</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="row in line.players" :key="row.player_id">
                  <tr>
                    <td>{{ playerLabel(row.player_id) }}</td>
                    <td>
                      <span :class="['role-badge', row.role === 'handler' ? 'role-badge--handler' : 'role-badge--cutter']">
                        {{ row.role }}
                      </span>
                    </td>
                    <td class="score-cell">{{ row.total_score.toFixed(1) }}</td>
                    <td>{{ row.ability_score.toFixed(1) }}</td>
                    <td class="chem-cell">{{ row.chemistry_score.toFixed(1) }}</td>
                    <td>{{ row.offense_score.toFixed(1) }}</td>
                    <td>{{ row.scoring_score.toFixed(1) }}</td>
                    <td>{{ row.recent_form_score.toFixed(1) }}</td>
                  </tr>
                  <!-- 原始历史数据子行（role reason + 场次/进球/助攻/正负） -->
                  <tr v-if="(playerById(row.player_id)?.total_matches ?? 0) > 0" class="sub-row">
                    <td colspan="2" class="sub-row__reason">{{ row.reason }}</td>
                    <td colspan="6" class="sub-row__stats">
                      场次 {{ playerById(row.player_id)?.total_matches }}
                      · 进球 {{ playerById(row.player_id)?.total_goals }}
                      · 助攻 {{ playerById(row.player_id)?.total_assists }}
                      · 正负 {{ (playerById(row.player_id)?.total_plus_minus ?? 0) >= 0 ? '+' : '' }}{{ playerById(row.player_id)?.total_plus_minus }}
                    </td>
                  </tr>
                  <tr v-else class="sub-row">
                    <td colspan="8" class="sub-row__nodata">暂无外战历史数据</td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
          <!-- 两两默契组合 -->
          <div v-if="line.chemistry_pairs.length" class="chem-pairs">
            <div class="chem-pairs__title">🤝 重点默契组合</div>
            <div
              v-for="pair in line.chemistry_pairs.slice(0, 6)"
              :key="`${pair.player_a_id}-${pair.player_b_id}`"
              class="chem-pair-item"
            >
              {{ pair.summary }}
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ── 内战分析 ─────────────────────────────────────────────────────── -->
    <template v-else-if="matchType === 'internal'">
      <div class="section-header">
        <div class="section-header__info">
          <div class="section-title">内战队伍能力分析</div>
          <div class="section-desc">对比两队整体战力，辅助判断分组均衡度</div>
        </div>
        <van-button size="small" type="primary" :loading="analysisLoading" @click="$emit('runAnalysis')">
          智能均衡分组
        </van-button>
      </div>

      <!-- 自动分组均衡度 -->
      <template v-if="autoGroupResult">
        <div class="balance-card">
          <div class="balance-card__row">
            <span class="balance-label">均衡度</span>
            <van-progress
              :percentage="Math.round(autoGroupResult.match_quality * 100)"
              color="#22c55e"
              style="flex: 1; margin: 0 8px"
            />
            <span class="balance-value">{{ (autoGroupResult.match_quality * 100).toFixed(1) }}%</span>
          </div>
          <div class="balance-card__row">
            <span class="balance-label">队A胜率</span>
            <van-progress
              :percentage="Math.round(autoGroupResult.win_prob_a * 100)"
              color="#3b82f6"
              style="flex: 1; margin: 0 8px"
            />
            <span class="balance-value">{{ (autoGroupResult.win_prob_a * 100).toFixed(1) }}%</span>
          </div>
          <div class="balance-hint">均衡度越高 → 两队对抗强度越接近 → 比赛更激烈</div>
        </div>
      </template>

      <!-- 每条 line 强度表 -->
      <div v-if="internalDisplayLines.length" class="internal-table-wrap">
        <table class="metric-table">
          <thead>
            <tr>
              <th>队伍</th>
              <th>人数</th>
              <th>平均评分</th>
              <th>球员列表</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="line in internalDisplayLines" :key="line.key">
              <td>{{ line.line_name }}</td>
              <td>{{ line.playerIds.length }}</td>
              <td class="score-cell">{{ lineStrength(line.playerIds).toFixed(1) }}</td>
              <td class="players-cell">{{ line.playerIds.map(playerLabel).join('、') || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-hint">请先在「分Line」Tab 中分好队伍</div>
    </template>

    <!-- ── 训练分析 ─────────────────────────────────────────────────────── -->
    <template v-else>
      <div class="section-header">
        <div class="section-header__info">
          <div class="section-title">训练分组能力概览</div>
          <div class="section-desc">各组球员基础评分一览，供训练安排参考</div>
        </div>
      </div>

      <div v-if="trainingDisplayLines.length === 0" class="empty-hint">请先在「分Line」Tab 中配置各训练组</div>

      <div v-for="line in trainingDisplayLines" :key="line.key" class="training-line-card">
        <div class="training-line-card__title">
          {{ line.line_name }}
          <van-tag plain type="primary">{{ line.playerIds.length }} 人</van-tag>
          <span class="line-avg">均分 {{ lineStrength(line.playerIds).toFixed(1) }}</span>
        </div>
        <div v-if="line.playerIds.length === 0" class="empty-hint" style="padding:6px 0">暂无球员</div>
        <table v-else class="metric-table" style="margin-top:6px">
          <thead>
            <tr>
              <th>球员</th>
              <th>评分</th>
              <th>性别</th>
              <th>号码</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="pid in line.playerIds" :key="pid">
              <td>{{ playerLabel(pid) }}</td>
              <td class="score-cell">{{ (playerById(pid)?.conservative_rating ?? 0).toFixed(0) }}</td>
              <td>{{ playerById(pid)?.gender === 'M' ? '♂' : playerById(pid)?.gender === 'F' ? '♀' : '—' }}</td>
              <td>{{ playerById(pid)?.jersey_number != null ? `#${playerById(pid)!.jersey_number}` : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

  </div>
</template>

<style scoped>
.analysis-tab { padding: 0 0 16px; }
.empty-hint { color: #6f8cab; font-size: 12px; text-align: center; padding: 24px 0; }

.section-header {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 12px;
}
.section-header__info { flex: 1; min-width: 0; }
.section-title { color: #eff6ff; font-weight: 700; font-size: 14px; }
.section-desc { color: #b7d2ee; font-size: 12px; margin-top: 2px; }

.rationale-banner {
  background: #0d1f35; border: 1px solid #244160; border-radius: 12px; padding: 10px 12px; margin-bottom: 12px;
}
.rationale-banner__title { color: #93c5fd; font-weight: 700; font-size: 13px; margin-bottom: 4px; }
.rationale-banner__body { color: #b7d2ee; font-size: 12px; display: flex; gap: 8px; flex-wrap: wrap; }
.rationale-banner__desc { color: #94a3b8; font-size: 11px; margin-top: 6px; line-height: 1.5; }
.rationale-weights { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
.weight-label { color: #7f95af; font-size: 11px; }
.weight-tag {
  background: #1e3a5f; color: #93c5fd; font-size: 11px; padding: 2px 8px; border-radius: 999px;
}

.line-report-card {
  background: #0f2035; border: 1px solid #1e3a5f; border-radius: 12px; padding: 10px 12px; margin-bottom: 10px;
}
.line-report-card__header {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px;
}
.line-report-name { color: #90caf9; font-weight: 700; font-size: 14px; }
.score-pill {
  background: #1e3a5f; color: #fbbf24; padding: 2px 8px; border-radius: 999px; font-size: 11px;
}
.chem-pill {
  background: #1e3a5f; color: #a78bfa; padding: 2px 8px; border-radius: 999px; font-size: 11px;
}

.line-summary-bar {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  color: #7f95af; font-size: 11px; margin-bottom: 8px;
}
.lsb-item { }
.lsb-dot { color: #2d4a6b; }

.table-wrap { overflow-x: auto; }
.internal-table-wrap { overflow-x: auto; }
.metric-table {
  width: 100%; border-collapse: collapse; font-size: 12px;
}
.metric-table th {
  background: #0d1f35; color: #93c5fd; padding: 6px 8px; text-align: left;
  white-space: nowrap; font-weight: 600; border-bottom: 1px solid #244160;
}
.metric-table td {
  color: #e2e8f0; padding: 6px 8px; border-bottom: 1px solid #1a3050;
}
.metric-table tr:last-child td { border-bottom: none; }
.score-cell { color: #fbbf24; font-weight: 700; }
.chem-cell { color: #a78bfa; font-weight: 700; }
.players-cell { color: #b7d2ee; font-size: 11px; }

/* 原始数据子行 */
.sub-row td { background: #0a1929 !important; border-bottom: 2px solid #1e3a5f !important; padding: 3px 8px 5px; }
.sub-row__reason { color: #5a7a9a; font-size: 10px; font-style: italic; white-space: nowrap; }
.sub-row__stats { color: #4a7090; font-size: 10px; }
.sub-row__nodata { color: #3a5570; font-size: 10px; font-style: italic; }

.role-badge {
  display: inline-flex; align-items: center; padding: 1px 6px;
  border-radius: 999px; font-size: 10px; font-weight: 600;
}
.role-badge--handler { background: rgba(59, 130, 246, .2); color: #93c5fd; }
.role-badge--cutter { background: rgba(34, 197, 94, .2); color: #86efac; }

.chem-pairs { margin-top: 8px; }
.chem-pairs__title { color: #93c5fd; font-weight: 600; font-size: 12px; margin-bottom: 4px; }
.chem-pair-item { color: #b7d2ee; font-size: 11px; padding: 3px 0; border-bottom: 1px solid #1a3050; line-height: 1.5; }
.chem-pair-item:last-child { border-bottom: none; }

.balance-card {
  background: #0f2035; border: 1px solid #1e3a5f; border-radius: 12px; padding: 12px; margin-bottom: 12px;
}
.balance-card__row { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
.balance-label { color: #b7d2ee; font-size: 12px; white-space: nowrap; min-width: 52px; }
.balance-value { color: #fbbf24; font-size: 13px; font-weight: 700; min-width: 44px; text-align: right; }
.balance-hint { color: #6f8cab; font-size: 11px; margin-top: 6px; }

.training-line-card {
  background: #0f2035; border: 1px solid #1e3a5f; border-radius: 12px; padding: 10px 12px; margin-bottom: 10px;
}
.training-line-card__title {
  display: flex; align-items: center; gap: 8px; color: #90caf9; font-weight: 700; font-size: 13px; margin-bottom: 4px;
}
.line-avg { color: #fbbf24; font-size: 11px; margin-left: auto; }

.gender-m { color: #60a5fa; }
.gender-f { color: #f472b6; }
</style>
