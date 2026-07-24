<template>
  <div class="docs-learn-page">
    <van-nav-bar title="规则与Drill学习" left-arrow @click-left="router.back()" />
    <van-tabs v-model:active="activeTab">
      <van-tab title="飞盘规则">
        <div class="doc-note">感谢 Maxima 的规则翻译支持。</div>
        <div class="doc-toolbar">
          <van-button size="small" plain type="primary" :loading="loadingRules" @click="openDoc('rules')">打开 PDF</van-button>
          <span class="cache-tip">{{ rulesCacheStatus }}</span>
        </div>
        <!-- 移动端不支持内嵌PDF，显示友好提示 -->
        <template v-if="isMobile">
          <div class="mobile-pdf-hint">
            <van-icon name="description" size="48" color="#1677ff" />
            <p class="hint-title">中英文对照 WFDF 飞盘规则手册</p>
            <p class="hint-sub">移动端浏览器不支持直接预览 PDF</p>
            <van-button type="primary" block style="margin-top: 12px" @click="openDoc('rules')">
              点击打开 PDF
            </van-button>
            <p class="hint-tip">将在系统 PDF 阅读器或浏览器中打开</p>
          </div>
        </template>
        <template v-else>
          <object class="doc-frame" :data="rulesPreviewUrl" type="application/pdf">
            <div class="doc-fallback">
              当前环境无法直接预览 PDF，请点击上方按钮打开。
            </div>
          </object>
        </template>
      </van-tab>
      <van-tab title="Skills & Drills">
        <div class="doc-toolbar">
          <van-button size="small" plain type="primary" :loading="loadingDrills" @click="openDoc('drills')">打开 PDF</van-button>
          <span class="cache-tip">{{ drillsCacheStatus }}</span>
        </div>
        <template v-if="isMobile">
          <div class="mobile-pdf-hint">
            <van-icon name="description" size="48" color="#1677ff" />
            <p class="hint-title">USAU Skills & Drills 训练手册</p>
            <p class="hint-sub">移动端浏览器不支持直接预览 PDF</p>
            <van-button type="primary" block style="margin-top: 12px" @click="openDoc('drills')">
              点击打开 PDF
            </van-button>
            <p class="hint-tip">将在系统 PDF 阅读器或浏览器中打开</p>
          </div>
        </template>
        <template v-else>
          <object class="doc-frame" :data="drillsPreviewUrl" type="application/pdf">
            <div class="doc-fallback">
              当前环境无法直接预览 PDF，请点击上方按钮打开。
            </div>
          </object>
        </template>
      </van-tab>
    </van-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const router = useRouter()
const route = useRoute()
const activeTab = ref(0)

// 移动端检测：iOS/Android 不支持 <object> 嵌入 PDF
const isMobile = computed(() => {
  const ua = navigator.userAgent
  return /Android|iPhone|iPod|iPad/i.test(ua) || window.innerWidth < 768
})

const DOC_CACHE_NAME = 'docs-pdf-cache-v1'
const rulesUrl = '/docs-files/中英文对照-2025-2028-WFDF-Rules-of-Ultimate-ver1.0.pdf'
const drillsUrl = '/docs-files/USAU_SkillsDrills.pdf'

const rulesPreviewUrl = ref(rulesUrl)
const drillsPreviewUrl = ref(drillsUrl)
const loadingRules = ref(false)
const loadingDrills = ref(false)
const rulesCacheStatus = ref('首次打开会缓存到本地')
const drillsCacheStatus = ref('首次打开会缓存到本地')
const objectUrls: string[] = []

function rememberObjectUrl(url: string) {
  objectUrls.push(url)
  return url
}

async function loadCachedPdf(sourceUrl: string): Promise<{ url: string; fromCache: boolean }> {
  if (!('caches' in window)) {
    return { url: sourceUrl, fromCache: false }
  }

  const cache = await caches.open(DOC_CACHE_NAME)
  let response = await cache.match(sourceUrl)
  let fromCache = true
  if (!response) {
    fromCache = false
    response = await fetch(sourceUrl, { credentials: 'same-origin' })
    if (response.ok) {
      await cache.put(sourceUrl, response.clone())
    }
  }

  if (!response.ok) {
    throw new Error('pdf load failed')
  }
  const blob = await response.blob()
  return { url: rememberObjectUrl(URL.createObjectURL(blob)), fromCache }
}

async function ensurePreview(which: 'rules' | 'drills') {
  if (which === 'rules') {
    loadingRules.value = true
    try {
      const loaded = await loadCachedPdf(rulesUrl)
      rulesPreviewUrl.value = loaded.url
      rulesCacheStatus.value = loaded.fromCache ? '已从本地缓存读取' : '已缓存到本地，下次秒开'
    } catch {
      rulesPreviewUrl.value = rulesUrl
      rulesCacheStatus.value = '缓存失败，已回退在线读取'
    } finally {
      loadingRules.value = false
    }
    return
  }

  loadingDrills.value = true
  try {
    const loaded = await loadCachedPdf(drillsUrl)
    drillsPreviewUrl.value = loaded.url
    drillsCacheStatus.value = loaded.fromCache ? '已从本地缓存读取' : '已缓存到本地，下次秒开'
  } catch {
    drillsPreviewUrl.value = drillsUrl
    drillsCacheStatus.value = '缓存失败，已回退在线读取'
  } finally {
    loadingDrills.value = false
  }
}

function openDoc(which: 'rules' | 'drills') {
  // 移动端直接用原始 URL 打开，避免 iOS Safari 不支持 blob URL in window.open
  const directUrl = which === 'rules' ? rulesUrl : drillsUrl
  const previewUrl = which === 'rules' ? rulesPreviewUrl.value : drillsPreviewUrl.value
  // 若预览 URL 是 blob URL 且在移动端，退回原始 URL
  const target = (isMobile.value && previewUrl.startsWith('blob:')) ? directUrl : previewUrl
  window.open(target, '_blank', 'noopener,noreferrer')
}

onMounted(() => {
  if (route.query.doc === 'drills') activeTab.value = 1
  void ensurePreview(activeTab.value === 1 ? 'drills' : 'rules')
  // 空闲时预取另一份文档，减少后续打开等待
  setTimeout(() => {
    void ensurePreview(activeTab.value === 1 ? 'rules' : 'drills')
  }, 600)
})

watch(activeTab, (value) => {
  void ensurePreview(value === 1 ? 'drills' : 'rules')
})

onBeforeUnmount(() => {
  for (const url of objectUrls) {
    URL.revokeObjectURL(url)
  }
})
</script>

<style scoped>
.docs-learn-page { min-height: 100vh; background: #f7f8fa; }
.doc-note { padding: 10px 12px; color: #64748b; font-size: 12px; }
.doc-toolbar { padding: 0 12px 8px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.cache-tip { color: #475569; font-size: 12px; }
.doc-frame {
  width: 100%;
  height: calc(100vh - 140px);
  border: none;
  background: #fff;
}
.doc-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #64748b;
  font-size: 14px;
  padding: 24px;
  text-align: center;
}
.mobile-pdf-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px 32px;
  text-align: center;
}
.hint-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 16px 0 6px;
}
.hint-sub {
  font-size: 13px;
  color: #888;
  margin: 0 0 4px;
}
.hint-tip {
  font-size: 12px;
  color: #aaa;
  margin-top: 10px;
}
</style>
