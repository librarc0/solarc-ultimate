<template>
  <van-popup
    v-model:show="visible"
    position="bottom"
    round
    class="donation-popup"
    @update:show="$emit('update:show', $event)"
  >
    <div class="donation-content">
      <div class="donation-header">
        <span class="donation-title">支持 SDL Pool 飞盘数据事业</span>
        <van-icon name="cross" class="close-btn" @click="$emit('update:show', false)" />
      </div>

      <p class="donation-desc">感谢你使用本平台！数据由 @xhs SDL Pool的栗子 提供支持。<br />若觉得有帮助，欢迎打赏鼓励 ❤️</p>

      <div class="qrcode-wrap">
        <img src="/afdian.jpg" alt="爱发电二维码" class="qrcode-img" />
        <p class="qrcode-hint">微信/支付宝扫码打赏</p>
      </div>

      <van-button
        type="primary"
        block
        round
        class="afdian-btn"
        @click="openAfdian"
      >
        前往爱发电支持
      </van-button>

      <p class="donation-id">afdian.net/a/solarc</p>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
}>()

const visible = computed({
  get: () => props.show,
  set: (val) => emit('update:show', val),
})

function openAfdian() {
  window.open('https://afdian.net/a/solarc', '_blank', 'noopener,noreferrer')
}
</script>

<style scoped>
.donation-popup {
  max-width: 480px;
  left: 50%;
  transform: translateX(-50%);
}

.donation-content {
  padding: 20px 20px 32px;
}

.donation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.donation-title {
  font-size: 16px;
  font-weight: 600;
  color: #323233;
}

.close-btn {
  font-size: 18px;
  color: #969799;
  cursor: pointer;
}

.donation-desc {
  font-size: 13px;
  color: #646566;
  line-height: 1.7;
  margin: 0 0 16px;
}

.qrcode-wrap {
  text-align: center;
  margin-bottom: 16px;
}

.qrcode-img {
  width: 160px;
  height: 160px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #ebedf0;
}

.qrcode-hint {
  font-size: 12px;
  color: #969799;
  margin-top: 6px;
}

.afdian-btn {
  margin-bottom: 8px;
}

.donation-id {
  text-align: center;
  font-size: 12px;
  color: #c8c9cc;
  margin: 0;
}
</style>
