<template>
  <div class="match-edit-page">
    <van-nav-bar title="编辑比赛" left-arrow @click-left="router.back()" />

    <van-loading v-if="loading" type="spinner" class="loading-center" />

    <template v-else-if="match">
      <van-cell-group inset title="比赛信息">
        <van-cell title="类型" :value="match.match_type === 'internal' ? '内战' : '外战'" />
        <van-cell title="日期" :value="match.match_date?.slice(0, 10)" />
        <van-cell title="当前状态" :value="match.status" />
      </van-cell-group>

      <van-cell-group inset title="修改比分">
        <van-field
          v-model="form.scoreUs"
          label="我方得分"
          type="digit"
          placeholder="队 A 得分"
        />
        <van-field
          v-model="form.scoreThem"
          label="对方得分"
          type="digit"
          placeholder="队 B 得分"
        />
      </van-cell-group>

      <van-cell-group inset title="备注">
        <van-field
          v-model="form.notes"
          type="textarea"
          rows="2"
          autosize
          placeholder="修改原因（可选）"
        />
      </van-cell-group>

      <div style="margin: 16px">
        <van-button block type="primary" :loading="submitting" @click="submit">
          保存并重新结算评分
        </van-button>
      </div>

      <van-notice-bar
        wrapable
        :scrollable="false"
        text="保存后系统将回退原有评分并以新数据重新计算，此操作将追加管理员修正记录。"
        color="#ed6a0c"
        background="#fffbe8"
      />
    </template>

    <van-empty v-else description="比赛不存在或无权访问" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import api from '@/api'

const route = useRoute()
const router = useRouter()
const matchId = Number(route.params.id)

interface MatchDetail {
  id: number
  match_type: string
  match_date: string
  team_a_score: number
  team_b_score: number
  status: string
  data_level: number
  notes: string | null
}

const loading = ref(true)
const submitting = ref(false)
const match = ref<MatchDetail | null>(null)

const form = ref({
  scoreUs: '',
  scoreThem: '',
  notes: '',
})

onMounted(async () => {
  try {
    const res = await api.get(`/matches/${matchId}`)
    match.value = res.data
    form.value.scoreUs = String(res.data.team_a_score)
    form.value.scoreThem = String(res.data.team_b_score)
    form.value.notes = res.data.notes ?? ''
  } catch {
    match.value = null
  } finally {
    loading.value = false
  }
})

async function submit() {
  if (!form.value.scoreUs || !form.value.scoreThem) {
    showToast('请填写双方得分')
    return
  }
  submitting.value = true
  try {
    await api.put(`/matches/${matchId}`, {
      action: 'edit',
      score_us: Number(form.value.scoreUs),
      score_them: Number(form.value.scoreThem),
      notes: form.value.notes || undefined,
    })
    showToast('已保存，评分已重新结算')
    router.replace('/matches/list')
  } catch (err: any) {
    showToast(err?.response?.data?.detail ?? '保存失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.match-edit-page {
  padding-bottom: 20px;
}
.loading-center {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
</style>
