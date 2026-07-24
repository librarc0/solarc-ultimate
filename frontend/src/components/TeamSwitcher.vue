<script setup lang="ts">
/**
 * T026 [US2]: 统一切队组件
 *
 * 适用场景：
 * - 普通多队伍用户：调用 auth.switchTeam() 真正切换激活 token（队伍上下文随之改变）
 * - 超级管理员：额外支持 setViewingTeam() 切换查看视角（不改变自身 player）
 *
 * Props：
 * - show: 控制底部弹窗 v-model
 */
import { ref, computed, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { showToast, showLoadingToast, closeToast } from 'vant'
import api from '@/api'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ (e: 'update:show', val: boolean): void; (e: 'switched'): void }>()

const auth = useAuthStore()

// 所有可用队伍列表（统一来源：auth.availableTeams）
// 超管额外加载全部队伍
const allTeams = ref<{ id: number; name: string; member_count?: number }[]>([])
const loadingAll = ref(false)
const loadError = ref('')

// 超管的全量队伍通过独立接口获取
async function loadAllTeamsForSuperAdmin(force = false) {
  if (!auth.isSuperAdmin) return
  if (!force && allTeams.value.length > 0) return
  loadingAll.value = true
  loadError.value = ''
  try {
    const res = await api.get('/team/available')
    allTeams.value = Array.isArray(res.data) ? res.data : []
  } catch {
    loadError.value = '队伍列表加载失败'
  } finally {
    loadingAll.value = false
  }
}

// 弹窗打开时加载数据
watch(() => props.show, async (opened) => {
  if (!opened) return
  if (auth.isSuperAdmin) {
    await loadAllTeamsForSuperAdmin()
  }
})

// 统一展示类型（无论来源如何规范化为 id/name/member_count）
interface DisplayTeam {
  id: number
  name: string
  member_count?: number
}

// 展示列表：超管显示全量列表，普通用户显示 auth.availableTeams（规范化字段）
const displayTeams = computed<DisplayTeam[]>(() => {
  if (auth.isSuperAdmin) {
    return allTeams.value.map(t => ({ id: t.id, name: t.name, member_count: t.member_count }))
  }
  return auth.availableTeams.map(t => ({
    id: t.team_id,
    name: t.team_name ?? `队伍 #${t.team_id}`,
    member_count: undefined,
  }))
})

// 当前激活队伍 ID（用于高亮选中项）
const activeTeamId = computed(() =>
  auth.isSuperAdmin
    ? (auth.viewingTeamId ?? auth.user?.team_id ?? null)
    : (auth.userContext?.active_player?.team_id ?? auth.user?.team_id ?? null)
)

async function handleSelectTeam(teamId: number | null) {
  emit('update:show', false)

  if (auth.isSuperAdmin) {
    // 超管：切换视角（不重新颁发 token）
    auth.setViewingTeam(teamId)
    emit('switched')
    return
  }

  if (teamId === null) return
  if (teamId === activeTeamId.value) return  // 已在当前队伍

  // 普通用户：真正切队（重新颁发 token + 刷新 context）
  const toast = showLoadingToast({ message: '切换中...', forbidClick: true })
  try {
    await auth.switchTeam(teamId)
    closeToast()
    showToast({ message: '已切换队伍', icon: 'success', duration: 1500 })
    emit('switched')
  } catch (err: any) {
    closeToast()
    showToast({ message: err?.response?.data?.detail ?? '切队失败，请重试', icon: 'fail' })
  }
}

// 超管可重置视角（查看全部）
function handleViewAll() {
  handleSelectTeam(null)
}
</script>

<template>
  <van-popup
    :show="show"
    position="bottom"
    round
    @update:show="emit('update:show', $event)"
  >
    <van-cell-group :title="auth.isSuperAdmin ? '切换查看队伍（超管）' : '切换队伍'">
      <!-- 超管专属：全局视角 -->
      <van-cell
        v-if="auth.isSuperAdmin"
        title="全部队伍（超管视角）"
        clickable
        @click="handleViewAll"
      >
        <template #right-icon>
          <van-icon v-if="!auth.viewingTeamId" name="success" color="#3b82f6" />
        </template>
      </van-cell>

      <!-- 加载状态 -->
      <div v-if="loadingAll" class="team-picker-status">
        <van-loading size="20" type="spinner" />
        <span>正在加载...</span>
      </div>
      <div v-else-if="loadError" class="team-picker-status team-picker-status--error">
        <span>{{ loadError }}</span>
        <van-button size="small" plain type="primary" @click="loadAllTeamsForSuperAdmin(true)">重试</van-button>
      </div>

      <!-- 队伍列表 -->
      <van-cell
        v-for="team in displayTeams"
        :key="team.id"
        :title="team.name"
        :label="team.member_count != null ? `${team.member_count} 成员` : ''"
        clickable
        @click="handleSelectTeam(team.id)"
      >
        <template #right-icon>
          <van-icon
            v-if="auth.isSuperAdmin ? auth.viewingTeamId === team.id : activeTeamId === team.id"
            name="success"
            color="#3b82f6"
          />
        </template>
      </van-cell>

      <!-- 无可用队伍提示 -->
      <div
        v-if="!loadingAll && !loadError && displayTeams.length === 0 && !auth.isSuperAdmin"
        class="team-picker-empty"
      >
        暂无其他可用队伍
      </div>
    </van-cell-group>
  </van-popup>
</template>

<style scoped>
.team-picker-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  color: #64748b;
  font-size: 13px;
}
.team-picker-status--error {
  color: #f87171;
}
.team-picker-empty {
  padding: 16px;
  text-align: center;
  color: #64748b;
  font-size: 13px;
}
</style>
