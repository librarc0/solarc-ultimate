import { ref } from 'vue'
import { showToast } from 'vant'

import api from '@/api'

interface AuthLike {
  isSuperAdmin: boolean
  viewingTeamId: number | null
}

/** 统一的待审批条目，兼容两套系统 */
export interface PendingItem {
  /** 唯一 key（old: `player-{id}`，new: `membership-{id}`） */
  _key: string
  /** 显示名称 */
  username: string
  display_name: string | null
  created_at: string
  /** 加入申请时提供的理由（仅新系统有） */
  join_reason: string | null
  /** 区分：旧系统用 player.id 直接操作；新系统用 membership.id */
  _type: 'player' | 'membership'
  _id: number
}

export interface SuggestedMuInfo {
  team_id: number
  suggested_mu: number
  sample_count: number
  used_default: boolean
  fallback_mu: number
  manual_mu_min: number
  manual_mu_max: number
}

function unwrapApiData<T>(raw: any): T {
  if (raw && typeof raw === 'object' && 'code' in raw && 'data' in raw) {
    return raw.data as T
  }
  return raw as T
}

export function useAdminMembers(auth: AuthLike) {
  const pendingMembers = ref<PendingItem[]>([])
  const loadingMembers = ref(false)
  const finishedMembers = ref(false)
  const refreshingMembers = ref(false)

  async function loadPendingMembers(reset = false) {
    if (reset) {
      finishedMembers.value = false
      pendingMembers.value = []
    }

    if (auth.isSuperAdmin && !auth.viewingTeamId) {
      finishedMembers.value = true
      loadingMembers.value = false
      refreshingMembers.value = false
      return
    }

    try {
      const items: PendingItem[] = []

      // --- 新系统：PlayerTeamMembership 申请 ---
      const membershipParams: Record<string, any> = {}
      if (auth.isSuperAdmin && auth.viewingTeamId) membershipParams.team_id = auth.viewingTeamId
      try {
        const r = await api.get('/team-membership/applications/pending', { params: membershipParams })
        const list = unwrapApiData<any[]>(r.data)
        const normalized: any[] = Array.isArray(list) ? list : []
        for (const m of normalized) {
          items.push({
            _key: `membership-${m.id}`,
            username: m.player_username,
            display_name: null,
            created_at: m.created_at,
            join_reason: m.join_reason ?? null,
            _type: 'membership',
            _id: m.id,
          })
        }
      } catch { /* ignore if endpoint unavailable */ }

      // --- 旧系统：player.status=pending（首次注册加入流程） ---
      try {
        const params: Record<string, any> = { status: 'pending', page_size: 50 }
        if (auth.isSuperAdmin && auth.viewingTeamId) params.team_id = auth.viewingTeamId
        const r = await api.get('/players', { params })
        const list: any[] = Array.isArray(r.data) ? r.data : []
        for (const p of list) {
          // 避免与新系统重复（新系统的审批会把 player.status 置为 active，不会重叠）
          items.push({
            _key: `player-${p.id}`,
            username: p.username,
            display_name: p.display_name ?? null,
            created_at: p.created_at,
            join_reason: null,
            _type: 'player',
            _id: p.id,
          })
        }
      } catch { /* ignore */ }

      // 按时间倒序，最新在前
      items.sort((a, b) => (b.created_at > a.created_at ? 1 : -1))
      pendingMembers.value = items
      finishedMembers.value = true
    } finally {
      loadingMembers.value = false
      refreshingMembers.value = false
    }
  }

  async function loadSuggestedMuForReview() {
    const params: Record<string, any> = {}
    if (auth.isSuperAdmin && auth.viewingTeamId) {
      params.team_id = auth.viewingTeamId
    }
    const r = await api.get('/team-membership/applications/suggested-mu', { params })
    return unwrapApiData<SuggestedMuInfo>(r.data)
  }

  async function approvePlayer(item: PendingItem, initialMu?: number) {
    try {
      if (item._type === 'membership') {
        const payload: Record<string, any> = { action: 'approve' }
        if (typeof initialMu === 'number') payload.initial_mu = initialMu
        const resp = await api.post(`/team-membership/applications/${item._id}/review`, payload)
        const data = unwrapApiData<{ initial_mu?: number; suggested_mu?: number }>(resp.data)
        showToast(`已批准，初始 μ = ${Number(data.initial_mu ?? initialMu ?? 0).toFixed(1)}`)
      } else {
        await api.patch(`/players/${item._id}/status`, { status: 'active' })
        showToast('已批准')
      }
      await loadPendingMembers(true)
    } catch (e: any) {
      showToast(e.response?.data?.detail ?? '操作失败')
    }
  }

  async function rejectPlayer(item: PendingItem) {
    try {
      if (item._type === 'membership') {
        await api.post(`/team-membership/applications/${item._id}/review`, { action: 'reject' })
      } else {
        await api.patch(`/players/${item._id}/status`, { status: 'rejected' })
      }
      showToast('已拒绝')
      await loadPendingMembers(true)
    } catch (e: any) {
      showToast(e.response?.data?.detail ?? '操作失败')
    }
  }

  return {
    pendingMembers,
    loadingMembers,
    finishedMembers,
    refreshingMembers,
    loadPendingMembers,
    loadSuggestedMuForReview,
    approvePlayer,
    rejectPlayer,
  }
}

