export const WEB_ORIGIN =
  (import.meta.env?.VITE_WEB_ORIGIN as string) ?? 'http://localhost:5173'

export function copyWebLink(path = '/') {
  const normalized = path.startsWith('/') ? path : `/${path}`
  const url = `${WEB_ORIGIN}${normalized}`
  uni.setClipboardData({
    data: url,
    success() {
      uni.showToast({ title: '已复制，请在浏览器打开', icon: 'none' })
    },
  })
}
