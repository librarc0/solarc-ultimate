<template>
  <div class="membership-page">
    <van-nav-bar title="入队申请审核" left-arrow @click-left="$router.back()" />

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <van-list
        v-model:loading="loading"
        :finished="finished"
        finished-text="没有更多申请了"
        @load="loadMore"
      >
        <van-empty v-if="!loading && applications.length === 0" description="暂无待审核申请" />

        <van-cell-group inset v-for="app in applications" :key="app.id" style="margin-bottom: 8px;">
          <van-cell
            :title="app.player_username"
            :label="app.join_reason ? `申请理由：${app.join_reason}` : '未填写申请理由'"
            :value="`μ 建议值: ${suggestedMu?.toFixed(1) ?? '-'}`"
          >
            <template #right-icon>
              <van-space>
                <van-button size="mini" type="success" @click="openApproveDialog(app)">通过</van-button>
                <van-button size="mini" type="danger" plain @click="handleReject(app.id)">拒绝</van-button>
              </van-space>
            </template>
          </van-cell>
        </van-cell-group>
      </van-list>
    </van-pull-refresh>

    <!-- T041 [US4]: 审核通过弹窗 - 支持设置初始 μ -->
    <van-dialog
      v-model:show="showApproveDialog"
      title="审核通过 - 设置初始 μ"
      show-cancel-button
      @confirm="handleApprove"
      :before-close="() => true"
    >
      <div style="padding: 16px;">
        <div v-if="suggestedMu !== null" style="margin-bottom: 12px; color: #888; font-size: 13px;">
          队伍平均 μ 建议值：<strong>{{ suggestedMu.toFixed(1) }}</strong>
          <span v-if="suggestedMuIsDefault">（样本不足，使用默认值）</span>
        </div>
        <van-field
          v-model="initialMuInput"
          label="初始 μ"
          type="number"
          placeholder="留空则使用建议值"
          :rules="[{ validator: validateMu, message: '初始 μ 须在 10.0 ~ 40.0 之间' }]"
        />
        <div style="margin-top: 8px; color: #aaa; font-size: 12px;">
          可接受范围：10.0 ~ 40.0
        </div>
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * TeamMembershipView — 管理员审核入队申请页面（US4 / T041）
 *
 * 功能：
 * - 列出当前队伍所有 pending 状态的 PlayerTeamMembership 申请
 * - 通过时弹窗允许管理员设置初始 μ 值（10-40），默认取队伍 openskill_mu
 * - 拒绝申请直接更新状态，无需额外参数
 */
import { ref, onMounted } from 'vue'
import { showToast } from 'vant'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'

interface MembershipApp {
  id: number
  player_id: number
  player_username: string
  team_id: number
  join_reason: string | null
  status: string
  created_at: string
}

const auth = useAuthStore()
const applications = ref<MembershipApp[]>([])
const loading = ref(false)
const finished = ref(false)
const refreshing = ref(false)
const page = ref(1)

// 建议 μ（从 /team/settings 获取）
const suggestedMu = ref<number | null>(null)
const suggestedMuIsDefault = ref(false)

// 审核弹窗状态
const showApproveDialog = ref(false)
const currentMembershipId = ref<number | null>(null)
const initialMuInput = ref('')

function validateMu(val: string) {
  if (!val) return true
  const n = parseFloat(val)
  return !isNaN(n) && n >= 10.0 && n <= 40.0
}

async function loadSuggestedMu() {
  try {
    const teamId = auth.user?.team_id ?? auth.viewingTeamId
    if (!teamId) return
    // 通过创建一个临时申请来获取建议值（或通过 settings 接口的 openskill_mu 近似）
    // 实际建议值由后端审核接口返回，这里先读 settings 获取 openskill_mu 作为参考
    const res = await api.get('/team/settings', { params: { team_id: teamId } })
    suggestedMu.value = res.data.openskill_mu ?? 25.0
    suggestedMuIsDefault.value = true
  } catch {
    suggestedMu.value = 25.0
  }
}

async function loadApplications(reset = false) {
  if (reset) {
    page.value = 1
    finished.value = false
    applications.value = []
  }
  try {
    const teamId = auth.user?.team_id ?? auth.viewingTeamId
    const params: Record<string, any> = { status: 'pending', page: page.value, page_size: 20 }
    if (teamId) params.team_id = teamId
    // 查询 PlayerTeamMembership pending 列表（使用 /team-membership/applications/pending 端点）
    const res = await api.get('/team-membership/applications/pending', { params })
    const items: MembershipApp[] = res.data?.data ?? []
    applications.value.push(...items)
    if (items.length < 20) finished.value = true
    page.value++
  } catch {
    finished.value = true
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function onRefresh() {
  await loadApplications(true)
}

async function loadMore() {
  await loadApplications()
}

function openApproveDialog(app: MembershipApp) {
  currentMembershipId.value = app.id
  initialMuInput.value = ''
  showApproveDialog.value = true
}

async function handleApprove() {
  if (!currentMembershipId.value) return
  const muVal = initialMuInput.value ? parseFloat(initialMuInput.value) : undefined
  if (muVal !== undefined && (muVal < 10 || muVal > 40)) {
    showToast('初始 μ 须在 10.0 ~ 40.0 之间')
    return
  }
  try {
    const body: Record<string, any> = { action: 'approve' }
    if (muVal !== undefined) body.initial_mu = muVal
    const resp = await api.post(`/team-membership/applications/${currentMembershipId.value}/review`, body)
    const data = resp.data.data
    showToast(`已批准，初始 μ = ${data.initial_mu?.toFixed(1) ?? '-'}`)
    showApproveDialog.value = false
    await loadApplications(true)
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '操作失败')
  }
}

async function handleReject(membershipId: number) {
  try {
    await api.post(`/team-membership/applications/${membershipId}/review`, { action: 'reject' })
    showToast('已拒绝申请')
    await loadApplications(true)
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '操作失败')
  }
}

onMounted(() => {
  loadSuggestedMu()
})
</script>

<style scoped>
.membership-page {
  padding-bottom: 80px;
}
</style>
