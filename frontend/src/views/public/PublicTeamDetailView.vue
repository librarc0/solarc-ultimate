<template>
  <div class="team-detail-page">
    <van-nav-bar
      :title="teamName"
      left-arrow
      @click-left="router.push({ name: 'public-rankings', query: seasonId ? { season_id: String(seasonId) } : undefined })"
    />

    <template v-if="loading">
      <van-skeleton title :row="5" style="padding: 16px" />
    </template>

    <template v-else-if="team">
      <!-- 赛季标签 -->
      <div v-if="seasonInfo" class="season-badge-bar">
        <van-tag type="primary" size="medium">🏆 {{ seasonInfo.year }} · {{ seasonInfo.name }}</van-tag>
      </div>

      <!-- 基本信息卡片 -->
      <div class="info-card">
        <div class="rank-row">
          <div class="rank-num">
            <span class="label">当前排名</span>
            <span class="value">#{{ team.rank }}</span>
          </div>
          <div class="rank-change-badge" :class="changeClass">
            <template v-if="team.rank_change > 0">▲ {{ team.rank_change }} 上升</template>
            <template v-else-if="team.rank_change < 0">▼ {{ Math.abs(team.rank_change) }} 下降</template>
            <template v-else>— 持平</template>
          </div>
        </div>
        <div class="stats-grid">
          <div class="stat-item">
            <div class="stat-value">{{ team.total_score.toFixed(2) }}</div>
            <div class="stat-label">总积分</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">{{ team.avg_score.toFixed(2) }}</div>
            <div class="stat-label">均积分</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">{{ (team.win_rate * 100).toFixed(1) }}%</div>
            <div class="stat-label">胜率</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">{{ team.net_points }}</div>
            <div class="stat-label">净胜分</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">{{ team.wins }}/{{ team.losses }}/{{ team.draws }}</div>
            <div class="stat-label">胜/负/平</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">{{ team.tournament_count }}</div>
            <div class="stat-label">参赛次数</div>
          </div>
        </div>
      </div>

      <!-- 积分走势折线图 -->
      <div class="chart-card">
        <div class="chart-card-title">积分走势</div>
        <v-chart class="line-chart" :option="lineOption" autoresize />
      </div>

      <!-- 赛事历史 -->
      <div class="section-title">赛事历史记录</div>
      <div class="history-list">
        <div v-for="rec in team.tournament_records" :key="rec.id" class="history-item">
          <div class="hi-header">
            <div class="hi-name">{{ rec.tournament_name }}</div>
            <div class="hi-score">{{ rec.computed_score.toFixed(2) }} 分</div>
          </div>
          <div class="hi-meta">
            <van-tag :type="levelType(rec.level)">{{ levelLabel(rec.level) }}</van-tag>
            <span class="hi-month">{{ rec.month }}</span>
            <span>Pool {{ rec.pool }}</span>
            <span>第 {{ rec.final_rank }} 名</span>
          </div>
          <div class="hi-stats">
            <span>{{ rec.wins }}胜 {{ rec.losses }}负 {{ rec.draws }}平</span>
            <span class="sep">·</span>
            <span>胜率 {{ (rec.win_rate * 100).toFixed(1) }}%</span>
            <span class="sep">·</span>
            <span>得/失 {{ rec.points_scored }}/{{ rec.points_conceded }}</span>
          </div>
        </div>
        <van-empty v-if="!team.tournament_records.length" description="暂无赛事记录" />
      </div>
    </template>

    <van-empty v-else description="队伍不存在" />

    <!-- 底栏 -->
    <div class="footer-bar">
      <span class="credit">数据支持：<b>@xhs SDL Pool的栗子</b></span>
      <van-button size="mini" type="warning" icon="like-o" @click="showDonation = true">打赏</van-button>
    </div>
    <DonationDrawer v-model:show="showDonation" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TooltipComponent, GridComponent, LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import DonationDrawer from '@/components/ranking/DonationDrawer.vue'
import { fetchTeamDetail, fetchSeasons, type ExternalTeamDetail, type SeasonOut } from '@/api/publicRanking'

use([LineChart, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const route = useRoute()
const router = useRouter()
const teamName = route.params.teamName as string
const seasonId = Number(route.query.season_id)

const loading = ref(true)
const team = ref<ExternalTeamDetail | null>(null)
const seasonInfo = ref<SeasonOut | null>(null)
const showDonation = ref(false)

onMounted(async () => {
  try {
    const resolvedSeasonId = Number.isFinite(seasonId) && seasonId > 0 ? seasonId : undefined
    const [teamData, allSeasons] = await Promise.all([
      fetchTeamDetail(teamName, resolvedSeasonId),
      fetchSeasons(),
    ])
    team.value = teamData
    const sid = teamData?.season_id ?? resolvedSeasonId
    seasonInfo.value = allSeasons.find(s => s.id === sid) ?? null
  } finally {
    loading.value = false
  }
})

const changeClass = computed(() => {
  if (!team.value) return ''
  return team.value.rank_change > 0 ? 'up' : team.value.rank_change < 0 ? 'down' : 'same'
})

function levelLabel(level: string) {
  return { National: '全国', Provincial: '省级', Local: '本地' }[level] ?? level
}
function levelType(level: string): 'danger' | 'warning' | 'primary' {
  return ({ National: 'danger', Provincial: 'warning', Local: 'primary' } as any)[level] ?? 'primary'
}

const lineOption = computed(() => {
  if (!team.value?.tournament_records.length) return {}
  const sorted = [...team.value.tournament_records].sort((a, b) => a.month.localeCompare(b.month))
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 20, bottom: 40 },
    xAxis: {
      type: 'category',
      data: sorted.map(r => `${r.month}\n${r.tournament_name.slice(0, 6)}`),
      axisLabel: { fontSize: 10, interval: 0, rotate: 30 },
    },
    yAxis: { type: 'value', name: '积分' },
    series: [
      {
        name: '单次积分',
        type: 'line',
        data: sorted.map(r => r.computed_score),
        smooth: true,
        lineStyle: { color: '#1677ff', width: 2 },
        itemStyle: { color: '#1677ff' },
        areaStyle: { color: 'rgba(22,119,255,0.1)' },
      },
    ],
  }
})
</script>

<style scoped>
.team-detail-page {
  min-height: 100vh;
  background: #f5f7fa;
  padding-bottom: 56px;
}
.info-card {
  margin: 12px 16px;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.rank-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.rank-num .label { font-size: 12px; color: #888; margin-right: 6px; }
.rank-num .value { font-size: 24px; font-weight: 800; color: #1677ff; }
.rank-change-badge {
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 12px;
}
.rank-change-badge.up { background: #fff1f0; color: #f5222d; }
.rank-change-badge.down { background: #f6ffed; color: #52c41a; }
.rank-change-badge.same { background: #f0f0f0; color: #999; }
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.stat-item { text-align: center; }
.stat-value { font-size: 16px; font-weight: 700; color: #1a1a1a; }
.stat-label { font-size: 11px; color: #aaa; margin-top: 2px; }

.season-badge-bar {
  padding: 8px 16px 0;
}

.chart-card {
  margin: 0 16px 12px;
  background: #fff;
  border-radius: 12px;
  padding: 12px 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.chart-card-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  padding: 0 12px 8px;
}
.line-chart { height: 200px; width: 100%; }

.section-title {
  padding: 12px 16px 6px;
  font-size: 14px;
  font-weight: 600;
  color: #555;
}
.history-list { padding: 0 16px; }
.history-item {
  background: #fff;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 8px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.hi-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 6px;
}
.hi-name { font-size: 14px; font-weight: 600; color: #1a1a1a; flex: 1; }
.hi-score { font-size: 16px; font-weight: 700; color: #1677ff; flex-shrink: 0; }
.hi-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #888;
  margin-bottom: 6px;
}
.hi-month { color: #555; }
.hi-stats { font-size: 12px; color: #888; }
.sep { margin: 0 4px; }

.footer-bar {
  position: fixed;
  bottom: 0; left: 0; right: 0;
  background: #fff;
  border-top: 1px solid #eee;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  z-index: 100;
}
.credit { font-size: 12px; color: #888; }
.credit b { color: #1677ff; }
</style>
