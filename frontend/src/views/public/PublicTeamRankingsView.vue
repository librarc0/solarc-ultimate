<template>
  <div class="public-rankings-page">
    <!-- Header -->
    <div class="page-header">
      <div class="header-row">
        <div class="header-title">
          <van-icon name="medal-o" size="22" color="#fff" />
          <span>飞盘联赛队伍排行榜</span>
        </div>
        <div class="header-actions">
          <van-button
            size="mini"
            plain
            class="header-btn"
            icon="home-o"
            @click="$router.push('/home')"
          >主应用</van-button>
          <van-button
            size="mini"
            plain
            class="header-btn"
            @click="$router.push('/ranking-admin/login')"
          >管理员</van-button>
        </div>
      </div>
    </div>

    <!-- 排行榜面板 -->
    <LeagueRankingsPanel :show-footer="true" :sticky-tabs="true" />
  </div>
</template>

<script setup lang="ts">
import LeagueRankingsPanel from '@/components/ranking/LeagueRankingsPanel.vue'
</script>

<style scoped>
.public-rankings-page {
  min-height: 100vh;
  background: #f0f2f5;
}

.page-header {
  background: linear-gradient(135deg, #1365d6 0%, #0958d9 100%);
  color: #fff;
  padding: 14px 16px 12px;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 700;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.header-btn {
  color: rgba(255, 255, 255, 0.85) !important;
  border-color: rgba(255, 255, 255, 0.4) !important;
  background: rgba(255, 255, 255, 0.12) !important;
  font-size: 12px !important;
}
</style>
