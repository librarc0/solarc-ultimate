import { ref } from 'vue'

import api from '@/api'

export interface PredictResult {
  win_prob_a: number
  win_prob_b: number
  match_quality: number
}

export function useMatchPrediction() {
  const prediction = ref<PredictResult | null>(null)
  const predictionLoading = ref(false)

  async function fetchPrediction(aIds: number[], bIds: number[]) {
    if (!aIds.length || !bIds.length) return
    predictionLoading.value = true
    try {
      const res = await api.post('/matches/predict', { team_a_ids: aIds, team_b_ids: bIds })
      prediction.value = res.data
    } catch {
      // Prediction failure should not block match flow.
    } finally {
      predictionLoading.value = false
    }
  }

  return {
    prediction,
    predictionLoading,
    fetchPrediction,
  }
}
