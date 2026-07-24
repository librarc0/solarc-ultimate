import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: () => {
        const auth = useAuthStore()
        return auth.isLoggedIn ? '/home' : '/login'
      },
    },
    // 微信小程序 web-view 自动登录入口（无需守卫）
    {
      path: '/auto-login',
      name: 'auto-login',
      component: () => import('@/views/AutoLoginView.vue'),
    },
    // 公开排行榜（无需登录）
    {
      path: '/public/rankings',
      name: 'public-rankings',
      component: () => import('@/views/public/PublicTeamRankingsView.vue'),
    },
    {
      path: '/public/rankings/:teamName',
      name: 'public-team-detail',
      component: () => import('@/views/public/PublicTeamDetailView.vue'),
    },
    // 排行榜管理员（独立体系）
    {
      path: '/ranking-admin/login',
      name: 'ranking-admin-login',
      component: () => import('@/views/ranking-admin/RankingAdminLoginView.vue'),
    },
    {
      path: '/ranking-admin',
      name: 'ranking-admin',
      component: () => import('@/views/ranking-admin/RankingAdminDashboardView.vue'),
      meta: { requiresRankingAdmin: true },
    },
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
    { path: '/register', name: 'register', component: () => import('@/views/RegisterView.vue') },
    { path: '/setup-team', name: 'setup-team', component: () => import('@/views/SetupTeamView.vue'), meta: { requiresAuth: true } },
    { path: '/forgot-password', name: 'forgot-password', component: () => import('@/views/ForgotPasswordView.vue') },
    { path: '/reset-password', name: 'reset-password', component: () => import('@/views/ResetPasswordView.vue') },
    { path: '/home', name: 'home', component: () => import('@/views/HomeView.vue'), meta: { requiresAuth: true } },
    { path: '/rankings', name: 'rankings', component: () => import('@/views/RankingsView.vue'), meta: { requiresAuth: true } },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('@/views/ProfileView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/matches/live',
      name: 'match-live',
      component: () => import('@/views/MatchLiveView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/matches/live/confirm',
      name: 'match-live-confirm',
      component: () => import('@/views/MatchLiveConfirmView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/match/input',
      name: 'match-mode-select',
      component: () => import('@/views/MatchModeSelectView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/matches/new',
      name: 'match-new',
      component: () => import('@/views/MatchInputView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/matches/list',
      name: 'match-list',
      component: () => import('@/views/MatchListView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/matches/edit/:id',
      name: 'match-edit',
      component: () => import('@/views/MatchEditView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/views/AdminView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/matches/:id',
      name: 'match-detail',
      component: () => import('@/views/MatchDetailView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/matches/:id/spirit-score',
      name: 'match-spirit-score',
      component: () => import('@/views/MatchSpiritScoreView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/team',
      name: 'team',
      component: () => import('@/views/TeamView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/team/manage',
      name: 'team-manage',
      component: () => import('@/views/TeamManageView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/team/membership',
      name: 'team-membership',
      component: () => import('@/views/TeamMembershipView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/schedule',
      name: 'schedule',
      component: () => import('@/views/ScheduleCalendarView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/docs-learn',
      name: 'docs-learn',
      component: () => import('@/views/DocsLearnView.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()

  // 排行榜管理员路由守卫（独立 token）
  if (to.meta.requiresRankingAdmin) {
    const rankingToken = localStorage.getItem('ranking_admin_token')
    if (!rankingToken) return { name: 'ranking-admin-login' }
  }

  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { name: 'login' }
  }
  if (to.meta.requiresAdmin && !auth.isAdmin) return { name: 'home' }
  // T020 [US1]: 已登录但无队伍 → 导航到 setup-team（白名单页无需队伍）
  const noTeamWhitelist = [
    'login', 'register', 'setup-team', 'forgot-password', 'reset-password',
    'public-rankings', 'public-team-detail',
    'ranking-admin-login', 'ranking-admin',
    'auto-login',  // 自动登录入口需在获取 token 后才能跳转，不能提前拦截
  ]
  if (auth.isLoggedIn && !auth.hasTeam && to.name && !noTeamWhitelist.includes(to.name as string)) {
    return { name: 'setup-team' }
  }
})

export default router

