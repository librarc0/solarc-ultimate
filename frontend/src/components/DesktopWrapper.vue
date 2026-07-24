<template>
  <!-- 移动端：直接 passthrough，不加任何包装 -->
  <slot v-if="!isDesktop" />

  <!-- 桌面/平板：自动适配宽屏布局（屏幕宽度 ≥ 768px 且非手机 UA） -->
  <div v-else class="desktop-root">

    <!-- 网页版宽屏布局 -->
    <div class="desktop-layout">
      <!-- 左侧导航栏 -->
      <nav class="desktop-nav">
        <div class="desktop-nav__brand">
          <span class="brand-icon">☀️</span>
          <span class="brand-name">Solarc Ultimate</span>
        </div>
        <ul class="desktop-nav__menu">
          <li
            v-for="item in navItems"
            :key="item.path"
            class="desktop-nav__item"
            :class="{ active: isActive(item.path) }"
            @click="goto(item.path)"
          >
            <span class="nav-icon">{{ item.icon }}</span>
            <span class="nav-label">{{ item.label }}</span>
          </li>
        </ul>
        <div class="desktop-nav__footer">
          <div v-if="auth.isLoggedIn" class="nav-user">
            <span class="nav-user__name">{{ auth.user?.display_name || auth.user?.username }}</span>
            <span class="nav-user__role">{{ roleLabel }}</span>
          </div>
        </div>
      </nav>

      <!-- 主内容区（隐藏移动端 tabbar，内部独立滚动） -->
      <main ref="mainRef" class="desktop-main">
        <slot />
      </main>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

// 设备检测：userAgent 识别手机（不含平板）
function isMobilePhone(): boolean {
  const ua = navigator.userAgent
  const isMobile = /Android|iPhone|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua)
  const isTablet = /iPad|Android(?!.*Mobile)/i.test(ua) ||
    (navigator.maxTouchPoints > 1 && /Macintosh/i.test(ua)) // iPad Safari 桌面模式
  return isMobile && !isTablet
}

// 屏幕宽度检测（响应横竖屏旋转）
const screenWidth = ref(window.innerWidth)

// 调试用：开发环境可在控制台执行 window.__epSetMobile(true/false) 来强制切换移动端视图
// 或使用 Chrome DevTools 设备模拟（推荐：Ctrl+Shift+M，选择手机型号后刷新页面）
const forceMobileOverride = ref(localStorage.getItem('_ep_force_mobile') === '1')

// ≥768px 且非手机 UA → 桌面/平板宽屏布局
const isDesktop = computed(() => !forceMobileOverride.value && screenWidth.value >= 768 && !isMobilePhone())

function onResize() {
  screenWidth.value = window.innerWidth
}
onMounted(() => {
  window.addEventListener('resize', onResize)
  localStorage.removeItem('view_mode') // 清除旧版遗留的手动模式标记

  // 开发环境下暴露调试切换方法到 window
  if (import.meta.env.DEV) {
    ;(window as any).__epSetMobile = (v: boolean) => {
      if (v) {
        localStorage.setItem('_ep_force_mobile', '1')
        forceMobileOverride.value = true
        console.log('[SolArc-Ultimate] 已切换到移动端视图，刷新页面以应用完整效果')
      } else {
        localStorage.removeItem('_ep_force_mobile')
        forceMobileOverride.value = false
        console.log('[SolArc-Ultimate] 已恢复桌面视图')
      }
    }
    if (forceMobileOverride.value) {
      console.log('[SolArc-Ultimate] 调试模式：当前强制显示移动端视图。执行 window.__epSetMobile(false) 可恢复')
    }
  }
})
onUnmounted(() => window.removeEventListener('resize', onResize))

// 主内容区 ref（用于路由切换时滚动复位）
const mainRef = ref<HTMLElement | null>(null)
watch(() => route.path, () => {
  mainRef.value?.scrollTo({ top: 0, behavior: 'instant' })
})

// 导航菜单
const navItems = computed(() => {
  const items = [
    { path: '/home',         icon: '🏠', label: '主页' },
    { path: '/rankings',     icon: '📊', label: '排行榜' },
    { path: '/matches/new',  icon: '➕', label: '新增比赛' },
    { path: '/matches/list', icon: '📋', label: '比赛记录' },
    { path: '/profile',      icon: '👤', label: '我的' },
  ]
  if (auth.isAdmin) {
    items.push({ path: '/team/manage', icon: '⚙️', label: '队伍管理' })
    items.push({ path: '/admin',       icon: '🛡️', label: '管理后台' })
  }
  return items
})

function isActive(path: string) {
  return route.path === path || route.path.startsWith(path + '/')
}

function goto(path: string) {
  router.push(path)
}

const roleLabel = computed(() => {
  if (auth.isSuperAdmin) return '超级管理员'
  if (auth.isOwner) return '主理人'
  if (auth.isAdmin) return '管理员'
  return '队员'
})
</script>

<style scoped>
/* ══════════════════════════════════════
   桌面/平板宽屏布局（自动适配，无手动切换）
══════════════════════════════════════ */
/* 根容器：占满视口高度，建立独立堆叠上下文，防止弹层定位偏移 */
.desktop-root {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100vh;
  background: #f0f2f5;
  overflow: hidden;
  box-sizing: border-box;
  isolation: isolate;
}

/* Flex 横向：左侧导航 + 右侧内容，各自独立滚动 */
.desktop-layout {
  display: flex;
  flex-direction: row;
  flex: 1;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

/* 左侧导航栏（响应式宽度，高度随父容器自动填满，内部分层滚动） */
.desktop-nav {
  width: 220px;
  min-width: 220px;
  flex-shrink: 0;
  background: #1a1f3c;
  display: flex;
  flex-direction: column;
  padding: 0;
  height: 100%;
  overflow: hidden;
  z-index: 100;
  box-shadow: 2px 0 16px rgba(0,0,0,0.2);
}

.desktop-nav__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 24px 20px 20px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

.brand-icon { font-size: 28px; }
.brand-name {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.5px;
}

.desktop-nav__menu {
  list-style: none;
  padding: 12px 0;
  flex: 1;
  overflow-y: auto;
  margin: 0;
}

.desktop-nav__item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 20px;
  cursor: pointer;
  color: rgba(255,255,255,0.65);
  font-size: 14px;
  transition: all 0.2s;
  border-left: 3px solid transparent;
}

.desktop-nav__item:hover {
  background: rgba(255,255,255,0.08);
  color: #fff;
}

.desktop-nav__item.active {
  background: rgba(22, 119, 255, 0.15);
  color: #60a5fa;
  border-left-color: #1677ff;
  font-weight: 600;
}

.nav-icon { font-size: 18px; min-width: 24px; text-align: center; }
.nav-label { flex: 1; }

.desktop-nav__footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(255,255,255,0.08);
  flex-shrink: 0;
}

.nav-user__name {
  display: block;
  font-size: 14px;
  color: #fff;
  font-weight: 600;
}

.nav-user__role {
  display: block;
  font-size: 12px;
  color: rgba(255,255,255,0.45);
  margin-top: 2px;
}

/* ── 主内容区（flex:1 自动填满剩余宽度，min-width:0 防溢出，内部独立滚动）── */
.desktop-main {
  flex: 1;
  min-width: 0;          /* 关键：防止 flex 子元素溢出 */
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  background: #f0f2f5;
  box-sizing: border-box;
}

/* ── Vant 组件适配：将移动端窄样式扩展为桌面宽度 ── */

/* 隐藏底部 tabbar（由左侧导航取代） */
.desktop-main :deep(.van-tabbar) {
  display: none !important;
}

/* 内容区页面容器：平板与桌面同统内边距，限制过宽屏最大宽度 */
.desktop-main :deep(.van-cell-group--inset) {
  margin-left: 32px !important;
  margin-right: 32px !important;
  border-radius: var(--r-lg, 16px);
  box-shadow: var(--sh-sm);
}

/* nav-bar 无额外边距（已移除手动切换按钮） */
.desktop-main :deep(.van-nav-bar) {
  padding-right: 0;
}

/* 内容区页面通用 padding-bottom（不需要给 tabbar 留空间）*/
.desktop-main :deep(.van-list) {
  padding-bottom: 32px;
}

/* 表单字段 label 宽度适当加宽 */
.desktop-main :deep(.van-field__label) {
  width: 110px;
}

/* card 列表全宽 + 圆角投影 */
.desktop-main :deep(.van-card) {
  width: 100%;
  box-sizing: border-box;
  border-radius: var(--r-md, 10px);
  box-shadow: var(--sh-sm);
}

/* 按钮区域不占满全宽（保持合理宽度）*/
.desktop-main :deep([style*="margin: 16px"]) {
  max-width: 600px;
}

/* tabs 下划线 + 标题全宽 */
.desktop-main :deep(.van-tabs__wrap) {
  border-radius: 0;
}

/* Vant 卡片 / 循环列表大円角 */
.desktop-main :deep(.van-swipe-cell),
.desktop-main :deep(.van-cell:last-child) {
  border-radius: 0 0 var(--r-md) var(--r-md);
}

/* ── 响应式侧栏宽度（Pad 竖屏 / 宽屏桌面）── */

/* Pad 竖屏 / 小平板（768–1023px）：收窄侧栏，内容区边距收紧 */
@media (max-width: 1023px) {
  .desktop-nav {
    width: 180px;
    min-width: 180px;
  }
  .brand-name {
    font-size: 14px;
  }
  .desktop-nav__brand {
    padding: 20px 12px 16px;
  }
  .desktop-nav__item {
    padding: 11px 12px;
  }
  .desktop-main :deep(.van-cell-group--inset) {
    margin-left: 16px !important;
    margin-right: 16px !important;
  }
}

/* 宽屏桌面（≥1440px）：加宽侧栏，内容限宽 */
@media (min-width: 1440px) {
  .desktop-nav {
    width: 240px;
    min-width: 240px;
  }

  /* 内容区各块统一限宽 + 居中 */
  .desktop-main :deep(.van-cell-group--inset),
  .desktop-main :deep(.van-steps),
  .desktop-main :deep(.van-notice-bar),
  .desktop-main :deep(.score-bar) {
    max-width: 960px;
    margin-left: auto !important;
    margin-right: auto !important;
  }

  /* 按钮区域同样居中 */
  .desktop-main :deep([style*="margin: 16px"]) {
    max-width: 600px;
    margin-left: auto !important;
    margin-right: auto !important;
  }

  /* ProfileView 自定义区块限宽居中 */
  .desktop-main :deep(.profile-hero),
  .desktop-main :deep(.stats-section),
  .desktop-main :deep(.rank-section),
  .desktop-main :deep(.feature-section) {
    max-width: 960px;
    margin-left: auto !important;
    margin-right: auto !important;
    border-radius: 16px;
  }

  /* 页面级别的 notice-bar / 分组section等外层容器限宽 */
  .desktop-main :deep(.van-cell-group) {
    max-width: 960px;
    margin-left: auto !important;
    margin-right: auto !important;
  }
}

/* ══════════════════════════════════════
   PC/Pad 深层全局优化：消除移动端特定样式
══════════════════════════════════════ */

/* 全页面容器：消除为移动端 tabbar 预留的底部占位，消除 min-height 拉伸 */
.desktop-main :deep(.home-page),
.desktop-main :deep(.profile-page),
.desktop-main :deep(.match-input-page),
.desktop-main :deep(.match-list-page),
.desktop-main :deep(.rankings-page),
.desktop-main :deep(.admin-page),
.desktop-main :deep(.team-page),
.desktop-main :deep(.match-detail-page) {
  padding-bottom: 24px !important;
  min-height: unset !important;
}

/* 消除 main.css 里为移动端 tabbar 预留的 safe-area padding */
.desktop-main :deep(.rankings-page),
.desktop-main :deep(.profile-page),
.desktop-main :deep(.match-input-page),
.desktop-main :deep(.match-list-page) {
  padding-bottom: 24px !important;
}

/* Stepper 控件：桂面上增大点击区域，改善操作手感 */
.desktop-main :deep(.van-stepper__input) {
  width: 52px;
  font-size: 15px;
  height: 32px;
}
.desktop-main :deep(.van-stepper__minus),
.desktop-main :deep(.van-stepper__plus) {
  width: 32px;
  height: 32px;
  font-size: 18px;
}

/* 统计录入行：在宽屏下允许换行，防止控件溢出 */
.desktop-main :deep(.stat-row) {
  flex-wrap: wrap;
  row-gap: 8px;
}

/* 比分行：宽屏下显示美观 */
.desktop-main :deep(.score-row) {
  flex-wrap: wrap;
  gap: 16px;
}

/* 步骤条 Steps 增加内边距，长文字不拥挤 */
.desktop-main :deep(.van-steps) {
  padding: 16px 32px;
}

/* 列表条目在桌面上稍宽松 */
.desktop-main :deep(.van-cell) {
  padding-top: 14px;
  padding-bottom: 14px;
  line-height: 1.6;
}

/* nav-bar 标题字号 Pad/PC 稍大 */
.desktop-main :deep(.van-nav-bar__title) {
  font-size: 17px;
  font-weight: 600;
}

/* 搜索框 Pad/PC 冯圆角减小 */
.desktop-main :deep(.van-search) {
  border-radius: 8px;
}

/* 卡片圆角与投影基线 */
.desktop-main :deep(.van-cell-group--inset) {
  border-radius: var(--r-lg, 16px);
  box-shadow: var(--sh-sm);
}

/* HomeView 手动被定义的内容单元 */
.desktop-main :deep(.team-banner) {
  margin-left: 24px;
  margin-right: 24px;
  border-radius: 20px;
}
.desktop-main :deep(.player-card) {
  margin-left: 24px;
  margin-right: 24px;
  border-radius: 14px;
}
</style>
