import { ref, watch, type Ref } from 'vue'
import { showToast } from 'vant'

import api from '@/api'

export interface DraftEventPayload {
  client_event_id: string
  seq: number
  event_type: 'goal' | 'defense' | 'turnover' | 'halftime'
  team_side: 'A' | 'B' | null
  player_id: number | null
  assist_player_id: number | null
  is_break: boolean
  elapsed_seconds: number
  payload: Record<string, unknown>
}

function getAccessToken(): string | null {
  return localStorage.getItem('access_token')
}

function uuidLike() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export function useLiveDraftSync(draftId: Ref<number | null>, nextSeq: Ref<number>) {
  const pendingQueue = ref<DraftEventPayload[]>([])
  let lockHeartbeatTimer: number | null = null
  let lockReleased = false

  watch(draftId, () => {
    lockReleased = false
  })

  function pendingKey() {
    return draftId.value ? `live_pending_${draftId.value}` : 'live_pending_unknown'
  }

  function persistPendingQueue() {
    localStorage.setItem(pendingKey(), JSON.stringify(pendingQueue.value))
  }

  function loadPendingQueue() {
    try {
      const raw = localStorage.getItem(pendingKey())
      pendingQueue.value = raw ? JSON.parse(raw) : []
    } catch {
      pendingQueue.value = []
    }
  }

  function clearPendingQueue() {
    localStorage.removeItem(pendingKey())
    pendingQueue.value = []
  }

  function clearLockHeartbeat() {
    if (lockHeartbeatTimer !== null) {
      window.clearInterval(lockHeartbeatTimer)
      lockHeartbeatTimer = null
    }
  }

  function startLockHeartbeat() {
    clearLockHeartbeat()
    if (!draftId.value) return
    lockHeartbeatTimer = window.setInterval(async () => {
      if (!draftId.value) return
      try {
        await api.post(`/matches/drafts/${draftId.value}/heartbeat`)
      } catch {
        // Retry on next interval.
      }
    }, 15000)
  }

  async function releaseDraftLock(options?: { silent?: boolean; bestEffort?: boolean }) {
    if (!draftId.value || lockReleased) return
    const id = draftId.value
    const url = `/matches/drafts/${id}/release`

    try {
      await api.post(url)
      lockReleased = true
      return
    } catch {
      const token = getAccessToken()
      const apiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api/v1'
      const target = `${apiBase}/matches/drafts/${id}/release`

      try {
        await fetch(target, {
          method: 'POST',
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
          keepalive: true,
        })
        lockReleased = true
        return
      } catch {
        if (!options?.bestEffort) {
          try {
            await new Promise((resolve) => setTimeout(resolve, 300))
            await api.post(url)
            lockReleased = true
            return
          } catch {
            if (!options?.silent) showToast('释放录入锁失败，请稍后重试')
          }
        }
      }
    }
  }

  async function syncPendingQueue() {
    if (!draftId.value || pendingQueue.value.length === 0) return
    const queue = [...pendingQueue.value]
    for (const evt of queue) {
      try {
        await api.post(`/matches/drafts/${draftId.value}/events`, evt)
        pendingQueue.value = pendingQueue.value.filter((x) => x.client_event_id !== evt.client_event_id)
        persistPendingQueue()
      } catch {
        break
      }
    }
  }

  async function pushEvent(payload: Omit<DraftEventPayload, 'client_event_id' | 'seq'>) {
    if (!draftId.value) return
    const event: DraftEventPayload = {
      client_event_id: uuidLike(),
      seq: nextSeq.value,
      ...payload,
    }
    nextSeq.value++
    pendingQueue.value.push(event)
    persistPendingQueue()
    await syncPendingQueue()
  }

  return {
    pendingQueue,
    loadPendingQueue,
    clearPendingQueue,
    clearLockHeartbeat,
    startLockHeartbeat,
    releaseDraftLock,
    syncPendingQueue,
    pushEvent,
  }
}
