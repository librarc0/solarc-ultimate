import axios from 'axios'

type ApiEnvelope<T = any> = { code: number; data: T; message?: string }

const api = axios.create({
  // 使用相对路径，通过 Vite 开发代理转发到后端（避免 CORS 问题）
  // 生产环境通过 VITE_API_BASE_URL 环境变量覆盖
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  timeout: 20000,
})

function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// Attach JWT token + superadmin team_id to every request
api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // 超级管理员：将选中的 viewing_team_id 附加到所有请求（跳过 auth 接口）
  // 注意：不覆盖调用方已显式传入的 team_id（如超管在各队系数页面查看指定队伍时）
  const viewingTeamId = sessionStorage.getItem('viewing_team_id') || localStorage.getItem('viewing_team_id')
  if (viewingTeamId && config.url && !config.url.includes('/auth/')) {
    if (config.params?.team_id === undefined) {
      config.params = { ...(config.params || {}), team_id: Number(viewingTeamId) }
    }
  }
  return config
})

// Handle 401 globally — clear token and redirect to login
// 登录接口本身返回 401 时不做跳转，让调用方的 catch 显示错误提示
api.interceptors.response.use(
  (res) => {
    // 兼容两种响应格式：
    // 1) 旧格式：直接返回 data（后端 return {...} / response_model）
    // 2) 新格式（章程要求）：{ code, data, message }
    const payload = res.data as any
    if (payload && typeof payload === 'object' && 'code' in payload && 'data' in payload) {
      const env = payload as ApiEnvelope
      if (env.code !== 0) {
        return Promise.reject(new Error(env.message || 'API error'))
      }
      res.data = env.data
    }
    return res
  },
  async (err) => {
    const config = err.config as (typeof err.config & { __retried?: boolean }) | undefined
    const method = (config?.method || 'get').toLowerCase()
    const status = err.response?.status
    const isRetriableStatus = [502, 503, 504, 522, 524].includes(status)
    const shouldRetry =
      !!config &&
      !config.__retried &&
      method === 'get' &&
      (err.code === 'ECONNABORTED' || !err.response || isRetriableStatus)

    if (shouldRetry) {
      config.__retried = true
      await sleep(400)
      return api(config)
    }

    if (err.response?.status === 401 && !err.config?.url?.includes('/auth/login')) {
      sessionStorage.removeItem('access_token')
      sessionStorage.removeItem('user_role')
      sessionStorage.removeItem('team_id')
      sessionStorage.removeItem('viewing_team_id')
      sessionStorage.removeItem('team_count')
      localStorage.removeItem('access_token')
      localStorage.removeItem('user_role')
      localStorage.removeItem('team_id')
      localStorage.removeItem('viewing_team_id')
      localStorage.removeItem('team_count')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

export default api
