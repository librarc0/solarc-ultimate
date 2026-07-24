/**
 * uni.request 封装 — 替代 axios，接口格式与 Web 版完全一致
 *
 * 后端返回格式：直接返回业务数据（FastAPI 标准 JSON），
 * 401 时自动清除 token 并跳转登录。
 */

interface RequestOptions {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  data?: unknown
  params?: Record<string, unknown>
}

// 默认指向本地后端；生产发布时通过 VITE_API_BASE_URL 覆盖。
const BASE_URL: string =
  (import.meta.env?.VITE_API_BASE_URL as string) ?? 'http://localhost:8000/api/v1'

export function request<T = unknown>(options: RequestOptions): Promise<T> {
  return new Promise((resolve, reject) => {
    const token: string = uni.getStorageSync('access_token') || ''

    let url = BASE_URL + options.url

    // 拼接 query 参数
    const params = { ...(options.params ?? {}) }
    if (Object.keys(params).length > 0) {
      const qs = Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null)
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join('&')
      if (qs) url += `?${qs}`
    }

    uni.request({
      url,
      method: (options.method ?? 'GET') as UniApp.RequestOptions['method'],
      data: options.data as Record<string, unknown>,
      header: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      success(res) {
        if (res.statusCode === 401) {
          uni.removeStorageSync('access_token')
          uni.reLaunch({ url: '/pages/login/index' })
          reject(new Error('未授权，请重新登录'))
          return
        }
        if (res.statusCode >= 400) {
          const body = res.data as Record<string, unknown>
          reject(new Error((body?.detail as string) || `请求失败 (${res.statusCode})`))
          return
        }
        resolve(res.data as T)
      },
      fail(err) {
        reject(new Error(err.errMsg || '网络请求失败'))
      },
    })
  })
}

/** 便捷方法，与 Web 版 axios 实例接口一致 */
export const api = {
  get<T>(url: string, config?: { params?: Record<string, unknown> }): Promise<T> {
    return request<T>({ url, method: 'GET', params: config?.params })
  },
  post<T>(url: string, data?: unknown): Promise<T> {
    return request<T>({ url, method: 'POST', data })
  },
  put<T>(url: string, data?: unknown): Promise<T> {
    return request<T>({ url, method: 'PUT', data })
  },
  patch<T>(url: string, data?: unknown): Promise<T> {
    return request<T>({ url, method: 'PATCH', data })
  },
  delete<T>(url: string): Promise<T> {
    return request<T>({ url, method: 'DELETE' })
  },
}

export default api
