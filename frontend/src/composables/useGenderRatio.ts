import { computed, ref } from 'vue'

export type GenderRatio = 'A' | 'B'

export function useGenderRatio() {
  const useGender = ref(false)
  const abbaFirstRatio = ref<GenderRatio>('A')
  const abbaPhase = ref(0)

  const currentGenderRatio = computed<GenderRatio>(() => {
    const cycle = abbaFirstRatio.value === 'A'
      ? (['A', 'B', 'B', 'A'] as const) // ABBA
      : (['B', 'A', 'A', 'B'] as const) // BAAB
    return cycle[abbaPhase.value] ?? cycle[0]
  })

  function advancePoint() {
    if (!useGender.value) return
    abbaPhase.value = (abbaPhase.value + 1) % 4
  }

  function switchForSecondHalf() {
    if (!useGender.value) return
    // 下半场翻转序列（ABBA↔BAAB），并从新序列起点开始
    abbaFirstRatio.value = abbaFirstRatio.value === 'A' ? 'B' : 'A'
    abbaPhase.value = 0
  }

  return {
    useGender,
    abbaFirstRatio,
    abbaPhase,
    currentGenderRatio,
    advancePoint,
    switchForSecondHalf,
  }
}

