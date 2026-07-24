<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onPullDownRefresh } from '@dcloudio/uni-app'
import api from '@/api/request'
import type { MyRanksResponse, PlayerPublic, RankingResponse, TeamInfo } from '@/api/types'
import FullWebLink from '@/components/FullWebLink.vue'
import StateBlock from '@/components/StateBlock.vue'
import { useAuthStore } from '@/stores/auth'
import { copyWebLink } from '@/utils/webLink'

const auth = useAuthStore()
const loading = ref(true)
const error = ref('')
const profile = ref<PlayerPublic | null>(null)
const teamInfo = ref<TeamInfo | null>(null)
const myRanks = ref<MyRanksResponse | null>(null)
const compositeScore = ref<number | null>(null)

const displayName = computed(() => profile.value?.display_name || profile.value?.username || '队员')
const roleLabel = computed(() => {
  const role = profile.value?.role
  if (role === 'owner') return '队长'
  if (role === 'admin') return '管理员'
  return '队员'
})

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const [profileRes, teamRes, ranksRes, rankListRes] = await Promise.allSettled([
      api.get<PlayerPublic>('/players/me'),
      api.get<TeamInfo | null>('/team/my'),
      api.get<MyRanksResponse>('/rankings/my-ranks'),
      api.get<RankingResponse>('/rankings', { params: { page: 1, page_size: 100, sort_by: 'composite' } }),
    ])
    if (profileRes.status === 'fulfilled') profile.value = profileRes.value
    else throw profileRes.reason
    teamInfo.value = teamRes.status === 'fulfilled' ? teamRes.value : null
    myRanks.value = ranksRes.status === 'fulfilled' ? ranksRes.value : null
    if (rankListRes.status === 'fulfilled') {
      const row = rankListRes.value.items.find(item => item.player_id === profile.value?.id)
      compositeScore.value = row?.composite_score ?? null
    }
  } catch (e) {
    error.value = (e as Error).message || '个人资料加载失败'
  } finally {
    loading.value = false
    uni.stopPullDownRefresh()
  }
}

function logout() {
  uni.showModal({
    title: '退出登录',
    content: '确认退出当前账号？',
    success(res) {
      if (res.confirm) auth.logout()
    },
  })
}

function goDocs() {
  uni.navigateTo({ url: '/pages/docs/index' })
}

onMounted(loadData)
onPullDownRefresh(loadData)
</script>

<template>
  <view class="page">
    <view class="profile-head">
      <view class="avatar">{{ displayName.slice(0, 1) }}</view>
      <view class="profile-main">
        <text class="name">{{ displayName }}</text>
        <text class="sub">{{ roleLabel }} · {{ profile?.status || '--' }}</text>
      </view>
    </view>

    <FullWebLink path="/profile" desc="修改资料、头像、密码和申请队伍等完整功能请在网页版使用。" />

    <StateBlock v-if="loading" title="正在加载个人资料" loading />
    <StateBlock v-else-if="error" title="加载失败" :desc="error" action-text="重试" @retry="loadData" />

    <template v-else>
      <view class="section">
        <text class="section-title">基础信息</text>
        <view class="info-row"><text>用户名</text><text>{{ profile?.username || '--' }}</text></view>
        <view class="info-row"><text>队伍</text><text>{{ teamInfo?.name || '暂未加入' }}</text></view>
        <view class="info-row"><text>球衣号码</text><text>{{ profile?.jersey_number ?? '--' }}</text></view>
        <view class="info-row"><text>邮箱</text><text>{{ profile?.email || '--' }}</text></view>
      </view>

      <view class="stats-grid">
        <view class="stat"><text class="val">{{ compositeScore == null ? '--' : compositeScore.toFixed(1) }}</text><text class="lbl">综合战力</text></view>
        <view class="stat"><text class="val">{{ profile?.total_matches ?? 0 }}</text><text class="lbl">比赛</text></view>
        <view class="stat"><text class="val">{{ profile?.total_goals ?? 0 }}</text><text class="lbl">得分</text></view>
        <view class="stat"><text class="val">{{ profile?.total_assists ?? 0 }}</text><text class="lbl">助攻</text></view>
      </view>

      <view class="section" v-if="myRanks">
        <text class="section-title">队内排名</text>
        <view class="rank-row"><text>综合战力</text><text>{{ myRanks.ranks.composite ?? '--' }} / {{ myRanks.total }}</text></view>
        <view class="rank-row"><text>保守评分</text><text>{{ myRanks.ranks.conservative ?? '--' }} / {{ myRanks.total }}</text></view>
        <view class="rank-row"><text>得分榜</text><text>{{ myRanks.ranks.goals ?? '--' }} / {{ myRanks.total }}</text></view>
        <view class="rank-row"><text>助攻榜</text><text>{{ myRanks.ranks.assists ?? '--' }} / {{ myRanks.total }}</text></view>
      </view>

      <view class="section">
        <text class="section-title">快捷操作</text>
        <button class="action-btn" @tap="goDocs">规则与手册 PDF</button>
        <button class="action-btn" @tap="copyWebLink('/profile')">复制个人资料网页版</button>
        <button class="action-btn muted" @tap="copyWebLink('/')">复制完整功能入口</button>
        <button class="action-btn danger" @tap="logout">退出登录</button>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page {
  min-height: 100vh;
  padding: 34rpx 0;
  background: linear-gradient(180deg, #07111f 0%, #111827 100%);
}

.profile-head {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 28rpx 32rpx;
}

.avatar {
  width: 104rpx;
  height: 104rpx;
  border-radius: 28rpx;
  background: linear-gradient(135deg, #0ea5e9, #f59e0b);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 44rpx;
  font-weight: 900;
}

.profile-main {
  flex: 1;
  min-width: 0;
}

.name {
  display: block;
  color: #f8fafc;
  font-size: 42rpx;
  font-weight: 900;
}

.sub {
  display: block;
  margin-top: 8rpx;
  color: #94a3b8;
  font-size: 25rpx;
}

.section,
.stat {
  border: 1rpx solid rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.82);
  border-radius: 18rpx;
}

.section {
  margin: 0 28rpx 24rpx;
  padding: 24rpx;
}

.section-title {
  display: block;
  color: #f8fafc;
  font-size: 30rpx;
  font-weight: 900;
  margin-bottom: 16rpx;
}

.info-row,
.rank-row {
  display: flex;
  justify-content: space-between;
  gap: 20rpx;
  padding: 16rpx 0;
  border-top: 1rpx solid rgba(148, 163, 184, 0.12);
  color: #cbd5e1;
  font-size: 25rpx;
}

.info-row:first-of-type,
.rank-row:first-of-type {
  border-top: 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14rpx;
  margin: 0 28rpx 24rpx;
}

.stat {
  padding: 20rpx 8rpx;
  text-align: center;
}

.val {
  display: block;
  color: #e0f2fe;
  font-size: 30rpx;
  font-weight: 900;
}

.lbl {
  display: block;
  margin-top: 6rpx;
  color: #94a3b8;
  font-size: 20rpx;
}

.action-btn {
  width: 100%;
  height: 76rpx;
  line-height: 76rpx;
  margin-top: 14rpx;
  padding: 0;
  border-radius: 16rpx;
  background: #0ea5e9;
  color: #fff;
  font-size: 27rpx;
  font-weight: 800;
}

.action-btn.muted {
  background: rgba(148, 163, 184, 0.2);
  color: #e2e8f0;
}

.action-btn.danger {
  background: #ef4444;
}

.action-btn::after {
  border: none;
}
</style>
