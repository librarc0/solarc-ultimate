<template>
  <!-- 玩家战力卡片：头像/名称/保守评分/排名/μ/σ -->
  <div class="player-card" :class="{ 'player-card--compact': compact }">
    <div class="player-card__rank" v-if="rank">#{{ rank }}</div>
    <van-image
      class="player-card__avatar"
      round
      :src="avatarUrl"
      width="48"
      height="48"
      fit="cover"
    >
      <template #error>
        <div class="player-card__avatar-fallback">{{ initials }}</div>
      </template>
    </van-image>
    <div class="player-card__info">
      <div class="player-card__name">{{ displayName }}</div>
      <div class="player-card__meta" v-if="!compact">
        <span>μ {{ mu.toFixed(2) }}</span>
        <span>σ {{ sigma.toFixed(2) }}</span>
        <span>{{ totalMatches }}场</span>
      </div>
    </div>
    <div class="player-card__rating">
      <div class="player-card__score">{{ conservativeRating.toFixed(1) }}</div>
      <div class="player-card__label">保守评分</div>
    </div>
    <van-tag v-if="isNew" type="warning" class="player-card__tag">新人</van-tag>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  displayName: string
  mu: number
  sigma: number
  conservativeRating: number
  totalMatches: number
  rank?: number
  avatarUrl?: string
  compact?: boolean
}>(), {
  compact: false,
})

const isNew = computed(() => props.totalMatches < 5)

const initials = computed(() => {
  const name = props.displayName || '?'
  return name.slice(0, 1).toUpperCase()
})
</script>

<style scoped>
.player-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
  position: relative;
}

.player-card--compact {
  padding: 8px 12px;
  gap: 8px;
}

.player-card__rank {
  width: 32px;
  text-align: center;
  font-size: 14px;
  font-weight: 700;
  color: #1677ff;
  flex-shrink: 0;
}

.player-card__avatar {
  flex-shrink: 0;
}

.player-card__avatar-fallback {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, #1677ff, #0958d9);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 700;
  border-radius: 50%;
}

.player-card__info {
  flex: 1;
  min-width: 0;
}

.player-card__name {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a1a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.player-card__meta {
  display: flex;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
  color: #888;
}

.player-card__rating {
  text-align: right;
  flex-shrink: 0;
}

.player-card__score {
  font-size: 22px;
  font-weight: 700;
  color: #1677ff;
}

.player-card__label {
  font-size: 11px;
  color: #aaa;
}

.player-card__tag {
  position: absolute;
  top: 8px;
  right: 8px;
}
</style>
