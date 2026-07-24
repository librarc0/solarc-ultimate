import { onMounted, onUnmounted, type Ref } from 'vue'

import type { DraftEventPayload } from '@/composables/useLiveDraftSync'

interface GuardContext {
  pendingQueue: Ref<DraftEventPayload[]>
  clearLockHeartbeat: () => void
  releaseDraftLock: (options?: { silent?: boolean; bestEffort?: boolean }) => Promise<void>
}

export function useLiveDraftPageGuards(ctx: GuardContext) {
  function handleBeforeUnload(e: BeforeUnloadEvent) {
    if (ctx.pendingQueue.value.length > 0) {
      e.preventDefault()
      e.returnValue = ''
    }
    void ctx.releaseDraftLock({ silent: true, bestEffort: true })
  }

  function handleVisibilityChange() {
    if (document.visibilityState === 'hidden') {
      void ctx.releaseDraftLock({ silent: true, bestEffort: true })
    }
  }

  onMounted(() => {
    window.addEventListener('beforeunload', handleBeforeUnload)
    document.addEventListener('visibilitychange', handleVisibilityChange)
  })

  onUnmounted(() => {
    window.removeEventListener('beforeunload', handleBeforeUnload)
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    ctx.clearLockHeartbeat()
    void ctx.releaseDraftLock({ silent: true, bestEffort: true })
  })
}
