<template>
  <div class="spirit-page">
    <van-nav-bar title="飞盘精神评分" left-arrow @click-left="router.back()" />
    <van-steps :active="activeStep" style="padding: 10px 0">
      <van-step>规则</van-step>
      <van-step>接触</van-step>
      <van-step>公平</van-step>
      <van-step>态度</van-step>
      <van-step>沟通</van-step>
    </van-steps>

    <van-cell-group inset :title="currentDimension.title">
      <van-field label="分数">
        <template #input>
          <van-stepper v-model="currentState.score" min="0" max="4" />
        </template>
      </van-field>
      <van-field label="依据">
        <template #input>
          <van-checkbox-group v-model="currentState.reasons" direction="vertical">
            <van-checkbox v-for="reason in currentDimension.reasons" :key="reason" :name="reason">{{ reason }}</van-checkbox>
          </van-checkbox-group>
        </template>
      </van-field>
      <van-field v-model="currentState.note" label="补充说明" type="textarea" rows="2" placeholder="可选填写细节" />
    </van-cell-group>

    <van-cell-group inset title="总体备注" style="margin-top: 8px">
      <van-field v-model="note" type="textarea" rows="2" placeholder="可选：精神队长备注" />
    </van-cell-group>

    <div style="margin: 16px; display:flex; gap: 8px;">
      <van-button round block plain @click="prevStep" :disabled="activeStep === 0">上一步</van-button>
      <van-button round block type="primary" :loading="submitting" @click="nextOrSubmit">
        {{ activeStep === dimensions.length - 1 ? '提交评分' : '下一步' }}
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import api from '@/api'

const router = useRouter()
const route = useRoute()
const matchId = Number(route.params.id)
const activeStep = ref(0)
const note = ref('')
const submitting = ref(false)

const dimensions = [
  { key: 'rules', title: '① 对规则的认知和使用', reasons: ['对规则认知良好并遵守时限', '主动解释规则并帮助澄清', '出现无视规则或故意曲解'] },
  { key: 'contact', title: '② 犯规及身体接触', reasons: ['主动避免身体接触', '接触偶发且无争议', '重复犯规或存在危险动作'] },
  { key: 'fairness', title: '③ 公平竞争意识', reasons: ['愿意收回不合理示意', '尊重争议并接受讨论结果', '存在战术性拖延或不一致示意'] },
  { key: 'attitude', title: '④ 积极态度和自我控制', reasons: ['高压下仍保持礼貌与克制', '整体态度积极友好', '存在羞辱、挑衅或破坏行为'] },
  { key: 'communication', title: '⑤ 交流/沟通', reasons: ['沟通冷静高效并遵守时限', '能提供清晰证据与观点', '拒绝讨论或语言肢体攻击性强'] },
] as const
type SpiritKey = typeof dimensions[number]['key']

const formState = reactive<Record<SpiritKey, { score: number; reasons: string[]; note: string }>>({
  rules: { score: 2, reasons: [], note: '' },
  contact: { score: 2, reasons: [], note: '' },
  fairness: { score: 2, reasons: [], note: '' },
  attitude: { score: 2, reasons: [], note: '' },
  communication: { score: 2, reasons: [], note: '' },
})

const currentDimension = computed(() => dimensions[activeStep.value] ?? dimensions[0])
const currentState = computed(() => formState[currentDimension.value.key as SpiritKey])

function prevStep() {
  if (activeStep.value > 0) activeStep.value -= 1
}

async function nextOrSubmit() {
  if (activeStep.value < dimensions.length - 1) {
    activeStep.value += 1
    return
  }
  submitting.value = true
  try {
    await api.put(`/matches/${matchId}/spirit-score`, {
      rules: formState.rules,
      contact: formState.contact,
      fairness: formState.fairness,
      attitude: formState.attitude,
      communication: formState.communication,
      note: note.value || null,
    })
    showToast('精神评分已提交')
    router.push('/matches/list')
  } catch (e: any) {
    showToast(e?.response?.data?.detail ?? '提交失败')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  if (!matchId) {
    router.replace('/matches/list')
    return
  }
  try {
    const res = await api.get(`/matches/${matchId}/spirit-score`)
    if (res.data) {
      for (const key of ['rules', 'contact', 'fairness', 'attitude', 'communication'] as SpiritKey[]) {
        formState[key] = {
          score: res.data[key].score,
          reasons: [...(res.data[key].reasons || [])],
          note: res.data[key].note || '',
        }
      }
      note.value = res.data.note || ''
    }
  } catch {
    // 首次评分无数据时忽略
  }
})
</script>
