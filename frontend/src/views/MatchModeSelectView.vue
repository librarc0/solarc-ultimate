<template>
  <!-- 录入模式选择入口页（FR-001，/match/input） -->
  <div class="mode-select-page">
    <van-nav-bar
      title="录入比赛"
      left-arrow
      @click-left="router.back()"
    />

    <div class="mode-select-content">
      <!-- 模式卡片区 -->
      <div class="mode-cards">
        <!-- 赛后录入卡片 -->
        <div
          class="mode-card"
          @click="goPostMatch"
        >
          <div class="mode-card__icon">
            📋
          </div>
          <div class="mode-card__body">
            <div class="mode-card__title">
              赛后录入
            </div>
            <div class="mode-card__desc">
              比赛已结束，补录比分与球员统计数据
            </div>
          </div>
          <van-icon
            name="arrow"
            class="mode-card__arrow"
          />
        </div>

        <!-- 实况录入卡片 -->
        <div
          class="mode-card mode-card--live"
          @click="goLive"
        >
          <div class="mode-card__icon">
            🔴
          </div>
          <div class="mode-card__body">
            <div class="mode-card__title">
              实况录入
            </div>
            <div class="mode-card__desc">
              比赛正在进行，分分实时记录得分和事件
            </div>
          </div>
          <van-icon
            name="arrow"
            class="mode-card__arrow"
          />
        </div>
      </div>

      <!-- 未完成草稿横幅（从后端查询，有草稿时显示） -->
      <template v-if="loadingDrafts">
        <van-skeleton
          title
          :rows="1"
          style="margin: 12px 0"
        />
      </template>
      <template v-else-if="activeDraft">
        <!-- 草稿恢复提示横幅 -->
        <div
          class="draft-banner"
          @click="resumeDraft"
        >
          <div class="draft-banner__info">
            <van-icon
              name="clock-o"
              class="draft-banner__icon"
            />
            <div>
              <div class="draft-banner__title">
                未完成草稿
              </div>
              <div class="draft-banner__meta">
                {{ activeDraft.match_date }}
                {{ activeDraft.match_type === 'internal' ? '内战' : '外战' }}
              </div>
            </div>
          </div>
          <div class="draft-banner__action">
            继续录入 <van-icon name="arrow" />
          </div>
        </div>
        <!-- 草稿球员已变更提示（spec 边界情况）-->
        <van-notice-bar
          v-if="draftRosterWarning"
          wrapable
          :scrollable="false"
          left-icon="warning-o"
          :text="draftRosterWarning"
          color="#ff976a"
          background="#fff7e6"
          style="margin: 0 0 8px; border-radius: 8px"
        />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'

const router = useRouter()

// ——————————————————————————
// 草稿检测（后端 /matches?status=draft，FR-002）
// ——————————————————————————

interface DraftMatch {
  id: number
  match_date: string
  match_type: string
  /** 草稿中参与球员的 id 列表（用于比对当前在队名单） */
  team_a_player_ids?: number[]
  team_b_player_ids?: number[]
}

const loadingDrafts = ref(true)
/** 当前用户最近一条未完成草稿 */
const activeDraft = ref<DraftMatch | null>(null)
/** 草稿阵容变更警告文本（若草稿球员已退队则提示） */
const draftRosterWarning = ref<string | null>(null)

async function loadActiveDraft() {
  try {
    const res = await api.get('/matches', { params: { status: 'draft', page_size: 5 } })
    const drafts: DraftMatch[] = res.data ?? []
    if (drafts.length > 0) {
      activeDraft.value = drafts[0]!
      // 检查草稿中球员是否仍在队（spec 边界情况：草稿恢复后阵容已变）
      await checkRosterValidity(drafts[0]!)
    }
  } catch {
    // 加载失败时静默处理，不影响主要功能
  } finally {
    loadingDrafts.value = false
  }
}

/** 比对草稿阵容与当前在队球员，若有退队球员则给出提示 */
async function checkRosterValidity(draft: DraftMatch) {
  const allIds = [
    ...(draft.team_a_player_ids ?? []),
    ...(draft.team_b_player_ids ?? []),
  ]
  if (allIds.length === 0) return
  try {
    const res = await api.get('/players', { params: { status: 'active', page_size: 200 } })
    const activeIds = new Set<number>((res.data as { id: number }[]).map((p) => p.id))
    const leftIds = allIds.filter((id) => !activeIds.has(id))
    if (leftIds.length > 0) {
      draftRosterWarning.value = `草稿中有 ${leftIds.length} 名球员已退出队伍，恢复后将自动过滤无效球员`
    }
  } catch {
    // 检测失败时忽略，不阻止恢复
  }
}

onMounted(() => {
  void loadActiveDraft()
})

// ——————————————————————————
// 导航操作
// ——————————————————————————

/** 赛后录入：跳转 MatchInputView（正常流程） */
function goPostMatch() {
  router.push({ name: 'match-new' })
}

/**
 * 实况录入：跳转 MatchInputView mode=live
 * 路径：MatchInputView（Step 2 阵容）→ MatchLiveSetupView → MatchLiveView（FR-008）
 */
function goLive() {
  router.push({ name: 'match-new', query: { mode: 'live' } })
}

/** 恢复未完成草稿：跳转至 MatchLiveView 传入 draft_id */
function resumeDraft() {
  if (!activeDraft.value) return
  router.push({ name: 'match-live', query: { draft_id: String(activeDraft.value.id) } })
}
</script>

<style scoped>
/* 页面容器 */
.mode-select-page {
  min-height: 100vh;
  background: #f7f8fa;
  padding-bottom: env(safe-area-inset-bottom, 20px);
}

/* 内容区：max-width 居中（PC 兼容，FR 响应式） */
.mode-select-content {
  max-width: 600px;
  margin: 0 auto;
  padding: 20px 16px 0;
}

/* 模式卡片容器 */
.mode-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}

/* 单张大卡片——与 van-cell-group inset 保持一致的圆角风格 */
.mode-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 16px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  transition: box-shadow 0.15s ease;
  /* 最小触摸区域 ≥44px（章程 Principle II） */
  min-height: 80px;
}

.mode-card:active {
  box-shadow: 0 0 0 2px #1677ff40;
}

/* 实况录入卡片高亮边框 */
.mode-card--live {
  border: 1.5px solid #ff000022;
}

.mode-card__icon {
  font-size: 32px;
  flex-shrink: 0;
  width: 44px;
  text-align: center;
}

.mode-card__body {
  flex: 1;
}

.mode-card__title {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 4px;
}

.mode-card__desc {
  font-size: 13px;
  color: #888;
  line-height: 1.5;
}

.mode-card__arrow {
  color: #c8c9cc;
  font-size: 16px;
  flex-shrink: 0;
}

/* 草稿恢复横幅 */
.draft-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: #fff7e6;
  border: 1px solid #ffd591;
  border-radius: 12px;
  cursor: pointer;
  margin-bottom: 8px;
}

.draft-banner__info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.draft-banner__icon {
  font-size: 20px;
  color: #fa8c16;
  flex-shrink: 0;
}

.draft-banner__title {
  font-size: 14px;
  font-weight: 600;
  color: #fa8c16;
}

.draft-banner__meta {
  font-size: 12px;
  color: #a05800;
  margin-top: 2px;
}

.draft-banner__action {
  font-size: 13px;
  color: #fa8c16;
  font-weight: 600;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 2px;
}

/* PC 端适配（768px+） */
@media (min-width: 768px) {
  .mode-select-content {
    padding: 32px 24px 0;
  }

  .mode-card {
    padding: 24px 24px;
  }

  .mode-card__icon {
    font-size: 40px;
    width: 52px;
  }

  .mode-card__title {
    font-size: 18px;
  }

  .mode-card__desc {
    font-size: 14px;
  }
}
</style>
