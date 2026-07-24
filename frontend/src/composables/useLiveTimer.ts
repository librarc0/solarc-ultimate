import { computed, onUnmounted, ref } from 'vue'

export function useLiveTimer() {
  const elapsedSeconds = ref(0)
  const timerPaused = ref(false)
  let timerInterval: ReturnType<typeof setInterval> | null = null

  const timerDisplay = computed(() => {
    const m = Math.floor(elapsedSeconds.value / 60).toString().padStart(2, '0')
    const s = (elapsedSeconds.value % 60).toString().padStart(2, '0')
    return `${m}:${s}`
  })

  function startTimer() {
    if (timerInterval) return
    timerInterval = setInterval(() => {
      if (!timerPaused.value) elapsedSeconds.value++
    }, 1000)
  }

  function stopTimer() {
    timerPaused.value = true
    if (timerInterval) {
      clearInterval(timerInterval)
      timerInterval = null
    }
  }

  function toggleTimer() {
    timerPaused.value = !timerPaused.value
  }

  onUnmounted(() => {
    if (timerInterval) clearInterval(timerInterval)
  })

  return {
    elapsedSeconds,
    timerPaused,
    timerDisplay,
    startTimer,
    stopTimer,
    toggleTimer,
  }
}

