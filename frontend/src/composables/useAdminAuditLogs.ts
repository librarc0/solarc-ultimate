import { ref } from 'vue'
import { showToast } from 'vant'

import api from '@/api'

interface AuditLogItem {
  id: number
  team_id: number | null
  actor_username: string
  action: string
  target_type: string | null
  target_id: number | null
  detail: Record<string, unknown> | null
  created_at: string
}

interface TeamOption {
  text: string
  value: number | string
}

interface TeamAvailableItem {
  id: number
  name: string
}

interface AuditLogsResponse {
  items: AuditLogItem[]
  total_pages: number
}

export function useAdminAuditLogs() {
  const auditLogs = ref<AuditLogItem[]>([])
  const auditPage = ref(1)
  const auditTotalPages = ref(1)
  const loadingAuditLogs = ref(false)
  const auditFilterTeamId = ref(0)
  const auditFilterAction = ref('')
  const auditFilterDate = ref('')
  const showAuditDatePicker = ref(false)
  const today = new Date()
  const auditDateParts = ref([
    String(today.getFullYear()),
    String(today.getMonth() + 1).padStart(2, '0'),
    String(today.getDate()).padStart(2, '0'),
  ])
  const auditTeamOptions = ref<TeamOption[]>([{ text: '全部队伍', value: 0 }])
  const auditActionOptions: TeamOption[] = [
    { text: '全部操作', value: '' },
    { text: '账号注册', value: 'player_registered' },
    { text: '找回密码申请', value: 'player_password_reset_requested' },
    { text: '重置密码完成', value: 'player_password_reset_completed' },
    { text: '比赛审批', value: 'match_approved' },
    { text: '比赛拒绝', value: 'match_rejected' },
    { text: '比赛删除', value: 'match_deleted' },
    { text: '比赛编辑', value: 'match_edited' },
    { text: '队伍创建', value: 'team_created' },
    { text: '申请加入队伍', value: 'team_join_applied' },
    { text: '退出队伍', value: 'team_left' },
    { text: '队伍信息更新', value: 'team_info_updated' },
    { text: '队徽更新', value: 'team_logo_updated' },
    { text: '球员状态', value: 'player_status_updated' },
    { text: '球员角色', value: 'player_role_changed' },
    { text: '个人资料修改', value: 'player_profile_updated' },
    { text: '管理员编辑球员', value: 'player_profile_admin_updated' },
    { text: '邮箱修改', value: 'player_email_updated' },
    { text: '密码修改', value: 'player_password_changed' },
    { text: '头像更新', value: 'player_avatar_updated' },
    { text: '新增球员', value: 'player_created' },
    { text: '移出队伍', value: 'player_removed_from_team' },
    { text: '系数更新', value: 'settings_updated' },
    { text: '系数重置', value: 'settings_reset' },
    { text: '队伍通过', value: 'team_approved' },
    { text: '队伍拒绝', value: 'team_rejected' },
    { text: '重算评分', value: 'team_rerated' },
    { text: '发布公告', value: 'team_post_created' },
    { text: '删除公告', value: 'team_post_deleted' },
    { text: '超管广播公告', value: 'superadmin_notice_published' },
  ]

  const auditActionLabelMap: Record<string, string> = {
    player_registered: '账号注册',
    player_password_reset_requested: '找回密码申请',
    player_password_reset_completed: '重置密码完成',
    player_status_updated: '球员状态修改',
    player_role_changed: '球员角色修改',
    player_profile_updated: '个人资料修改',
    player_profile_admin_updated: '管理员编辑球员资料',
    player_email_updated: '邮箱修改',
    player_password_changed: '密码修改',
    player_avatar_updated: '头像更新',
    player_created: '新增球员',
    player_removed_from_team: '移出队伍',
    team_created: '队伍创建',
    team_join_applied: '申请加入队伍',
    team_left: '退出队伍',
    team_info_updated: '队伍信息更新',
    team_logo_updated: '队徽更新',
    team_approved: '队伍审批通过',
    team_rejected: '队伍审批拒绝',
    settings_updated: '算法参数更新',
    settings_reset: '算法参数重置',
    team_rerated: '历史评分重算',
    match_created: '比赛创建',
    match_submitted: '比赛提交审批',
    match_approved: '比赛审批通过',
    match_rejected: '比赛拒绝',
    match_edited: '比赛编辑重算',
    match_deleted: '比赛删除',
    team_post_created: '发布公告',
    team_post_deleted: '删除公告',
    superadmin_notice_published: '超管广播公告',
  }

  function getAuditActionLabel(action: string) {
    return auditActionLabelMap[action] ?? action
  }

  async function loadAuditTeamList() {
    try {
      const res = await api.get<TeamAvailableItem[]>('/team/available')
      auditTeamOptions.value = [
        { text: '全部队伍', value: 0 },
        ...res.data.map((t) => ({ text: t.name, value: t.id })),
      ]
    } catch {
      // Keep dropdown usable with default option.
    }
  }

  async function loadAuditLogs(page = 1) {
    loadingAuditLogs.value = true
    auditPage.value = page
    try {
      const params: Record<string, unknown> = { page, page_size: 50 }
      // team_id=null 时不往 URL 发送，但能阻止拦截器自动注入 viewing_team_id
      params.team_id = auditFilterTeamId.value || null
      if (auditFilterAction.value) params.action = auditFilterAction.value
      if (auditFilterDate.value) params.log_date = auditFilterDate.value
      const res = await api.get<AuditLogsResponse>('/audit-logs', { params })
      auditLogs.value = res.data.items
      auditTotalPages.value = res.data.total_pages
    } catch {
      showToast('加载日志失败')
    } finally {
      loadingAuditLogs.value = false
    }
  }

  function onAuditDateConfirm({ selectedValues }: { selectedValues: string[] }) {
    const [y, m, d] = selectedValues
    auditFilterDate.value = `${y}-${m}-${d}`
    showAuditDatePicker.value = false
  }

  function clearAuditDate() {
    auditFilterDate.value = ''
  }

  return {
    auditLogs,
    auditPage,
    auditTotalPages,
    loadingAuditLogs,
    auditFilterTeamId,
    auditFilterAction,
    auditFilterDate,
    showAuditDatePicker,
    auditDateParts,
    auditTeamOptions,
    auditActionOptions,
    getAuditActionLabel,
    loadAuditTeamList,
    loadAuditLogs,
    onAuditDateConfirm,
    clearAuditDate,
  }
}
