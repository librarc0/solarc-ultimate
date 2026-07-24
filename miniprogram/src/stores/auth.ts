import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api/request'

const API_BASE_URL: string =
  (import.meta.env?.VITE_API_BASE_URL as string) ?? 'http://localhost:8000/api/v1'

export interface UserInfo {
  id: number
  team_id: number | null
  username: string
  display_name: string
  role: 'owner' | 'admin' | 'member'
  status: 'active' | 'pending' | 'rejected'
  is_superadmin?: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(uni.getStorageSync('access_token') || '')
  const user = ref<UserInfo | null>(null)
  const role = ref<string>(uni.getStorageSync('user_role') || '')

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => role.value === 'admin' || role.value === 'owner')
  const hasTeam = computed(() => !!(user.value?.team_id))

  function _persist(t: string, r: string) {
    uni.setStorageSync('access_token', t)
    uni.setStorageSync('user_role', r)
    token.value = t
    role.value = r
  }

  /** 用户名+密码登录 */
  async function login(username: string, password: string): Promise<void> {
    // FastAPI OAuth2 表单格式
    const formBody = `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`
    const res = await new Promise<{ access_token: string; role: string }>((resolve, reject) => {
      uni.request({
        url: `${API_BASE_URL}/auth/login`,
        method: 'POST',
        data: formBody,
        header: { 'Content-Type': 'application/x-www-form-urlencoded' },
        success(r) {
          if (r.statusCode >= 400) {
            const body = r.data as Record<string, unknown>
            reject(new Error((body?.detail as string) || '登录失败'))
            return
          }
          resolve(r.data as { access_token: string; role: string })
        },
        fail(e) { reject(new Error(e.errMsg)) },
      })
    })
    _persist(res.access_token, res.role)
    await fetchMe()
  }

  /**
   * 微信登录 — 调用 wx.login 取 code 后传给此函数
   * 返回 next_step："ok" 直接进入应用；"need_bind" 需引导绑定
   */
  async function wxLogin(code: string): Promise<{
    next_step: 'ok' | 'need_bind'
    bind_token?: string
  }> {
    const res = await api.post<{
      access_token: string
      role: string
      next_step: 'ok' | 'need_bind'
      bind_token?: string
    }>('/auth/wx-login', { code })

    if (res.next_step === 'ok') {
      _persist(res.access_token, res.role)
      await fetchMe()
    }
    return { next_step: res.next_step, bind_token: res.bind_token }
  }

  /** 微信新用户绑定已有密码账号后同步状态 */
  function setTokenFromBind(accessToken: string, userRole: string) {
    _persist(accessToken, userRole)
  }

  /** 同步用户详情 */
  async function fetchMe(): Promise<void> {
    const me = await api.get<UserInfo>('/auth/me')
    user.value = me
    role.value = me.role
    uni.setStorageSync('user_role', me.role)
  }

  function logout() {
    uni.removeStorageSync('access_token')
    uni.removeStorageSync('user_role')
    token.value = ''
    role.value = ''
    user.value = null
    uni.reLaunch({ url: '/pages/login/index' })
  }

  return { token, user, role, isLoggedIn, isAdmin, hasTeam, login, wxLogin, fetchMe, logout, setTokenFromBind }
})
