import { ref } from 'vue'

export type TeamSide = 'A' | 'B'

export function usePossession() {
  const possession = ref<TeamSide | null>(null)

  function transferOnTurnover(turnoverSide: TeamSide) {
    // 失误：盘权转移给另一方
    if (possession.value == null) return
    possession.value = turnoverSide === 'A' ? 'B' : 'A'
  }

  function transferAfterGoal(scoringSide: TeamSide) {
    // 飞盘规则：得分方下分变防守方，失分方下分变进攻方（与当前持盘方无关）
    if (possession.value == null) return
    possession.value = scoringSide === 'A' ? 'B' : 'A'
  }

  function transferOnDefenseSuccess(defenderSide: TeamSide) {
    // 防守成功：盘权归防守方
    if (possession.value == null) return
    possession.value = defenderSide
  }

  function flipForSecondHalf() {
    if (possession.value == null) return
    possession.value = possession.value === 'A' ? 'B' : 'A'
  }

  return {
    possession,
    transferOnTurnover,
    transferAfterGoal,
    transferOnDefenseSuccess,
    flipForSecondHalf,
  }
}

