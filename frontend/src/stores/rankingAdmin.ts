import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

const STORAGE_KEY = 'ranking_admin_token'
const baseURL = (import.meta.env.VITE_API_BASE_URL ?? '/api/v1') + '/ranking-admin'

const rankingAdminApi = axios.create({ baseURL, timeout: 10000 })

// 自动附加 token
rankingAdminApi.interceptors.request.use((config) => {
  const token = localStorage.getItem(STORAGE_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export interface SeasonForm {
  name: string
  year: number
  start_date?: string
  end_date?: string
  description?: string
}

export const useRankingAdminStore = defineStore('rankingAdmin', () => {
  const token = ref<string | null>(localStorage.getItem(STORAGE_KEY))

  const isLoggedIn = computed(() => !!token.value)

  async function login(username: string, password: string): Promise<void> {
    const form = new FormData()
    form.append('username', username)
    form.append('password', password)
    const res = await rankingAdminApi.post('/login', form)
    const t: string = res.data.access_token
    token.value = t
    localStorage.setItem(STORAGE_KEY, t)
  }

  function logout() {
    token.value = null
    localStorage.removeItem(STORAGE_KEY)
  }

  // ── 赛季 ──────────────────────────────────────────────────────

  async function fetchSeasons() {
    const res = await rankingAdminApi.get('/seasons')
    return res.data
  }

  async function createSeason(data: SeasonForm) {
    const res = await rankingAdminApi.post('/seasons', data)
    return res.data
  }

  async function updateSeason(seasonId: number, data: Partial<SeasonForm> & { is_active?: boolean }) {
    const res = await rankingAdminApi.patch(`/seasons/${seasonId}`, data)
    return res.data
  }

  async function deleteSeason(seasonId: number) {
    await rankingAdminApi.delete(`/seasons/${seasonId}`)
  }

  // ── 上传 ──────────────────────────────────────────────────────

  async function uploadFile(file: File, seasonId: number | null, notes?: string, autoCreateSeason = false) {
    const form = new FormData()
    form.append('file', file)
    if (seasonId !== null) form.append('season_id', String(seasonId))
    if (notes) form.append('notes', notes)
    form.append('auto_create_season', autoCreateSeason ? 'true' : 'false')
    const res = await rankingAdminApi.post('/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  }

  // ── 批次 ──────────────────────────────────────────────────────

  async function fetchBatches(seasonId?: number) {
    const res = await rankingAdminApi.get('/batches', {
      params: seasonId ? { season_id: seasonId } : {},
    })
    return res.data
  }

  async function deleteBatch(batchId: number) {
    await rankingAdminApi.delete(`/batches/${batchId}`)
  }

  async function restoreBatch(batchId: number) {
    const res = await rankingAdminApi.post(`/batches/${batchId}/restore`)
    return res.data
  }

  // ── API Key ──────────────────────────────────────────────────

  async function fetchApiKeys() {
    const res = await rankingAdminApi.get('/api-keys')
    return res.data
  }

  async function createApiKey(name: string, seasonId?: number) {
    const form = new FormData()
    form.append('name', name)
    if (seasonId) form.append('season_id', String(seasonId))
    const res = await rankingAdminApi.post('/api-keys', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  }

  async function revokeApiKey(keyId: number) {
    await rankingAdminApi.delete(`/api-keys/${keyId}`)
  }

  return {
    token,
    isLoggedIn,
    login,
    logout,
    fetchSeasons,
    createSeason,
    updateSeason,
    deleteSeason,
    uploadFile,
    fetchBatches,
    deleteBatch,
    restoreBatch,
    fetchApiKeys,
    createApiKey,
    revokeApiKey,
  }
})
