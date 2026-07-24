<template>
  <!-- 实况录入开赛配置页：比赛设置 → 传参给 MatchLiveView（FR-009/T011） -->
  <div class="live-setup-page">
    <van-nav-bar
      title="开赛配置"
      left-arrow
      @click-left="router.back()"
    />

    <!-- 阵容信息预览（来自 history.state.lineup） -->
    <div
      v-if="teamASet.length > 0"
      class="lineup-preview"
    >
      <div class="lineup-team">
        <span class="lineup-team__label">{{ matchType === 'external' ? '我方' : '队 A' }}</span>
        <span class="lineup-team__names">{{ teamANames }}</span>
      </div>
      <div
        v-if="teamBSet.length > 0"
        class="lineup-team lineup-team--b"
      >
        <span class="lineup-team__label">队 B</span>
        <span class="lineup-team__names">{{ teamBNames }}</span>
      </div>
    </div>
    <!-- 无阵容时提示 -->
    <van-notice-bar
      v-else
      wrapable
      :scrollable="false"
      left-icon="info-o"
      text="未检测到阵容信息，请先退回到阵容分配步骤完成 Line Division"
      style="margin: 8px 16px; border-radius: 8px;"
    />

    <!-- 基本配置字段 -->
    <van-cell-group
      inset
      title="比赛配置"
    >
      <van-field
        v-model="matchDate"
        label="比赛日期"
        readonly
        right-icon="calendar-o"
        @click="showDatePicker = true"
      />
      <!-- 内战/外战切换 -->
      <van-field
        name="match_type"
        label="比赛类型"
      >
        <template #input>
          <van-radio-group
            v-model="matchType"
            direction="horizontal"
          >
            <van-radio name="internal">
              🆚 内战
            </van-radio>
            <van-radio name="external">
              🌐 外战
            </van-radio>
          </van-radio-group>
        </template>
      </van-field>
      <!-- 备注（必填，FR-009） -->
      <van-field
        v-model="liveNotes"
        label="比赛备注"
        type="textarea"
        placeholder="必填，例：北京天气训练赛"
        :rows="2"
        autosize
        required
      />
    </van-cell-group>

    <!-- 性别比配置 -->
    <van-cell-group
      inset
      title="性别比设置"
    >
      <van-cell title="启用性别比模式">
        <template #right-icon>
          <van-switch
            v-model="useGender"
            size="24"
          />
        </template>
      </van-cell>
      <!-- 启用后展示第一分性别比选项 -->
      <template v-if="useGender">
        <van-field
          label="第一分性别比"
          label-width="80px"
        >
          <template #input>
            <van-radio-group
              v-model="abbaFirstRatio"
              direction="horizontal"
            >
              <van-radio name="A">
                A（4男3女）
              </van-radio>
              <van-radio name="B">
                B（3男4女）
              </van-radio>
            </van-radio-group>
          </template>
        </van-field>
        <van-cell
          label="循环模式预览"
          is-link
          disabled
        >
          <template #value>
            <span style="font-size: 12px; color: #888;">
              {{ abbaFirstRatio === 'A'
                ? 'ABBA：4男3女 → 3男4女 → 3男4女 → 4男3女'
                : 'BAAB：3男4女 → 4男3女 → 4男3女 → 3男4女' }}
            </span>
          </template>
        </van-cell>
      </template>
    </van-cell-group>

    <!-- 开赛进攻方（两个大按钮，必选） -->
    <div class="possession-section">
      <div class="possession-section__title">
        开赛进攻方 <span class="required">*</span>
      </div>
      <div class="possession-section__btns">
        <div
          class="possession-btn"
          :class="{ 'possession-btn--active': possession === 'A' }"
          @click="possession = 'A'"
        >
          {{ matchType === 'external' ? '🏃 我方进攻' : '🏃 队 A 进攻' }}
        </div>
        <div
          class="possession-btn"
          :class="{ 'possession-btn--active': possession === 'B' }"
          @click="possession = 'B'"
        >
          {{ matchType === 'external' ? '🏃 对方进攻' : '🏃 队 B 进攻' }}
        </div>
      </div>
    </div>

    <!-- 胜率预测卡（内战且双方阵容均非空时显示） -->
    <div
      v-if="matchType === 'internal' && teamASet.length > 0 && teamBSet.length > 0"
      class="predict-card"
    >
      <div class="predict-card__title">
        ⚖️ 胜率预测
      </div>
      <div
        v-if="predictionLoading"
        class="predict-card__loading"
      >
        <van-loading
          type="spinner"
          size="24"
          color="#1677ff"
        />
        <span>计算中…</span>
      </div>
      <template v-else-if="prediction">
        <!-- 胜率进度条 -->
        <div class="predict-bar">
          <div
            class="predict-bar__a"
            :style="{ flex: prediction.win_prob_a }"
          >
            {{ (prediction.win_prob_a * 100).toFixed(0) }}%
          </div>
          <div
            class="predict-bar__b"
            :style="{ flex: prediction.win_prob_b }"
          >
            {{ (prediction.win_prob_b * 100).toFixed(0) }}%
          </div>
        </div>
        <div class="predict-quality">
          比赛质量指数：{{ (prediction.match_quality * 100).toFixed(0) }} / 100
        </div>
      </template>
      <div
        v-else
        class="predict-card__empty"
      >
        暂无预测数据
      </div>
    </div>

    <!-- 开始比赛按钮 -->
    <div class="live-setup-page__actions">
      <van-button
        round
        block
        type="primary"
        size="large"
        @click="handleStart"
      >
        🏁 开始比赛
      </van-button>
    </div>

    <!-- 日期选择器弹窗 -->
    <van-popup
      v-model:show="showDatePicker"
      position="bottom"
    >
      <van-date-picker
        v-model="dateParts"
        title="选择日期"
        @confirm="onDateConfirm"
        @cancel="showDatePicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast } from 'vant'
import { useMatchPrediction } from '@/composables/useMatchPrediction'

/* ===== 类型 ===== */
interface Player {
  id: number
  username: string
  display_name: string | null
  gender?: string | null
}

const router = useRouter()
const route = useRoute()

/* ===== 从 history.state.lineup 读取阵容（由 goToLiveSetup 传入） ===== */
const lineup = (history.state?.lineup ?? {}) as { teamA?: Player[]; teamB?: Player[] }
const teamASet = ref<Player[]>(lineup.teamA ?? [])
const teamBSet = ref<Player[]>(lineup.teamB ?? [])

/** 队员名称汇总字符串 */
const teamANames = computed(() =>
  teamASet.value.map(p => p.display_name || p.username).join('、')
)
const teamBNames = computed(() =>
  teamBSet.value.map(p => p.display_name || p.username).join('、')
)

/* ===== 配置字段 ===== */
/** 比赛类型：支持 query 参数 ?type=external 初始化（FR-009） */
const matchType = ref<'internal' | 'external'>(
  (route.query.type as string) === 'external' ? 'external' : 'internal'
)
const liveNotes = ref('')        // 比赛备注（必填）
const useGender = ref(false)     // 是否启用性别比模式
const abbaFirstRatio = ref<'A' | 'B'>('A')  // 第一分性别比
/** 开赛进攻方（必选，A 或 B） */
const possession = ref<'A' | 'B' | null>(null)

/* ===== 日期选择 ===== */
const today = new Date()
const matchDate = ref(today.toISOString().slice(0, 10))
const showDatePicker = ref(false)
const dateParts = ref([
  String(today.getFullYear()),
  String(today.getMonth() + 1).padStart(2, '0'),
  String(today.getDate()).padStart(2, '0'),
])

function onDateConfirm({ selectedValues }: { selectedValues: string[] }) {
  matchDate.value = selectedValues.join('-')
  showDatePicker.value = false
}

/* ===== 胜率预测 ===== */
const { prediction, predictionLoading, fetchPrediction } = useMatchPrediction()

onMounted(() => {
  // 内战且双方球员均存在时，自动请求胜率预测
  if (
    matchType.value === 'internal' &&
    teamASet.value.length > 0 &&
    teamBSet.value.length > 0
  ) {
    void fetchPrediction(
      teamASet.value.map(p => p.id),
      teamBSet.value.map(p => p.id),
    )
  }
})

/* ===== 开始比赛（校验 + 路由跳转） ===== */
function handleStart() {
  // 备注必填校验（FR-009）
  if (!liveNotes.value.trim()) {
    showToast('请先填写比赛备注')
    return
  }
  // 进攻方必选校验
  if (!possession.value) {
    showToast('请选择开赛进攻方')
    return
  }
  // 跳转至实况录入，通过 history.state 传递配置和阵容数据
  router.push({
    name: 'match-live',
    state: {
      // 开赛配置
      matchType: matchType.value,
      useGender: useGender.value,
      abbaFirstRatio: abbaFirstRatio.value,
      possession: possession.value,
      liveNotes: liveNotes.value.trim(),
      // 阵容数据（供 initNewDraft 的 parseEntryState 读取）
      teamAIds: teamASet.value.map((p) => p.id),
      teamBIds: teamBSet.value.map((p) => p.id),
      players: [...teamASet.value, ...teamBSet.value],
      notes: liveNotes.value.trim(),
    },
  })
}
</script>

<style scoped>
/* 页面主容器：最大宽度 600px，居中布局 */
.live-setup-page {
  min-height: 100vh;
  background: #f7f8fa;
  padding-bottom: 80px;
}

/* 必填标记 */
.required {
  color: #ee0a24;
  margin-left: 2px;
}

/* ── 阵容预览区 ──────────────────────────────── */
.lineup-preview {
  margin: 8px 16px;
  padding: 12px 16px;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #eee;
}

.lineup-team {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 6px;
}

.lineup-team:last-child {
  margin-bottom: 0;
}

.lineup-team--b .lineup-team__label {
  color: #1890ff;
}

.lineup-team__label {
  font-size: 12px;
  font-weight: 700;
  color: #1677ff;
  flex-shrink: 0;
}

.lineup-team__names {
  font-size: 13px;
  color: #555;
  line-height: 1.5;
}

/* ── 开赛进攻方选择 ───────────────────────────── */
.possession-section {
  margin: 8px 16px;
  padding: 14px 16px;
  background: #fff;
  border-radius: 12px;
}

.possession-section__title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
}

.possession-section__btns {
  display: flex;
  gap: 12px;
}

/* 进攻方大按钮 */
.possession-btn {
  flex: 1;
  padding: 16px 0;
  border-radius: 10px;
  border: 2px solid #ddd;
  text-align: center;
  font-size: 15px;
  font-weight: 600;
  color: #555;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}

.possession-btn--active {
  border-color: #1677ff;
  background: #e8f4ff;
  color: #1677ff;
}

/* ── 胜率预测卡 ──────────────────────────────── */
.predict-card {
  margin: 8px 16px;
  padding: 14px 16px;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #eee;
}

.predict-card__title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
}

.predict-card__loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #999;
  font-size: 13px;
}

.predict-card__empty {
  font-size: 13px;
  color: #bbb;
  text-align: center;
  padding: 8px 0;
}

/* 胜率进度条 */
.predict-bar {
  display: flex;
  border-radius: 6px;
  overflow: hidden;
  height: 32px;
  margin-bottom: 8px;
}

.predict-bar__a {
  background: #1677ff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  transition: flex 0.3s;
}

.predict-bar__b {
  background: #ff4d4f;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  transition: flex 0.3s;
}

.predict-quality {
  font-size: 12px;
  color: #888;
  text-align: center;
}

/* ── 底部操作区 ──────────────────────────────── */
.live-setup-page__actions {
  padding: 16px;
}

/* ── 宽屏适配（≥768px） ──────────────────────── */
@media (min-width: 768px) {
  .live-setup-page {
    max-width: 600px;
    margin: 0 auto;
  }

  .possession-section__btns {
    gap: 20px;
  }

  .possession-btn {
    padding: 20px 0;
    font-size: 16px;
  }
}
</style>
