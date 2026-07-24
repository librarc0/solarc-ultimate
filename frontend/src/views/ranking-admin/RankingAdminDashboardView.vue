<template>
  <div class="ra-dashboard">
    <van-nav-bar title="排行榜管理后台" right-text="退出" @click-right="doLogout" />

    <van-tabs v-model:active="activeTab" sticky color="#1677ff">
      <van-tab title="📤 上传数据" name="upload">
        <div class="tab-body">
          <van-cell-group inset style="margin-bottom: 0">
            <van-cell center title="从 JSON 自动建立/匹配赛季">
              <template #right-icon>
                <van-switch v-model="autoCreateSeason" size="20" />
              </template>
            </van-cell>
          </van-cell-group>
          <div v-if="autoCreateSeason" style="padding: 4px 16px 8px; color: #888; font-size: 12px">
            开启后将读取 JSON 文件中的赛季名称自动建立或匹配赛季，无需手动选择。
          </div>

          <div class="season-toolbar" v-if="!autoCreateSeason">
            <div class="season-toolbar-title">目标赛季</div>
            <template v-if="seasons.length">
              <van-cell :value="uploadSeasonLabel" is-link @click="showUploadSeasonSheet = true" />
            </template>
            <van-empty v-else description="请先创建赛季（或开启「自动建立赛季」）" image="search" />
          </div>

          <van-cell-group inset title="上传排行榜 JSON 文件">
            <van-field v-model="uploadNotes" label="备注" placeholder="可选：本次数据说明" />
          </van-cell-group>

          <div style="padding: 16px">
            <van-uploader
              v-model="fileList"
              :max-count="1"
              accept=".json"
              :after-read="onFileRead"
            >
              <van-button icon="plus" type="primary" style="width: 100%">
                选择 JSON 文件
              </van-button>
            </van-uploader>

            <van-button
              type="primary"
              block
              :loading="uploading"
              :disabled="!selectedFile || (!autoCreateSeason && !uploadSeasonId)"
              style="margin-top: 12px"
              @click="doUpload"
            >确认上传</van-button>
          </div>

          <van-notice-bar
            wrapable
            :scrollable="false"
            text="上传会只覆盖当前所选赛季的排行榜数据。系统最多保留每个赛季 10 条历史记录，可按赛季恢复。"
            style="margin: 0 16px"
          />
        </div>
      </van-tab>

      <van-tab title="📋 上传历史" name="batches">
        <div class="tab-body">
          <div class="season-toolbar">
            <div class="season-toolbar-title">筛选赛季</div>
            <van-cell :value="batchSeasonLabel" is-link @click="showBatchSeasonSheet = true" />
          </div>

          <van-pull-refresh v-model="batchRefreshing" @refresh="loadBatches">
            <template v-if="batches.length">
              <div v-for="b in batches" :key="b.id" class="batch-item">
                <div class="batch-info">
                  <div class="batch-date">{{ formatDate(b.uploaded_at) }}</div>
                  <div class="batch-meta">
                    <van-tag :type="b.source === 'api' ? 'warning' : 'primary'">
                      {{ b.source === 'api' ? 'API推送' : '手动上传' }}
                    </van-tag>
                    <span>{{ seasonLabelById(b.season_id) }}</span>
                    <span>{{ b.record_count }} 条记录</span>
                  </div>
                  <div v-if="b.notes" class="batch-notes">{{ b.notes }}</div>
                </div>
                <div class="batch-actions">
                  <van-button
                    size="small"
                    type="primary"
                    plain
                    :loading="restoringId === b.id"
                    @click="restoreBatch(b.id)"
                  >恢复</van-button>
                  <van-button
                    size="small"
                    type="danger"
                    plain
                    :loading="deletingId === b.id"
                    @click="deleteBatch(b.id)"
                  >删除</van-button>
                </div>
              </div>
            </template>
            <van-empty v-else description="暂无上传记录" />
          </van-pull-refresh>
        </div>
      </van-tab>

      <van-tab title="🔑 API Key" name="keys">
        <div class="tab-body">
          <van-cell-group inset title="新建 API Key">
            <van-field v-model="newKeyName" label="备注名" placeholder="例如：SDL Scorecard 平台" />
            <van-cell label="绑定赛季" :value="newKeySeasonLabel" is-link @click="showNewKeySeasonSheet = true" />
          </van-cell-group>
          <div style="padding: 16px">
            <van-button type="primary" block :loading="creatingKey" @click="doCreateKey">
              生成新 Key
            </van-button>
          </div>

          <van-notice-bar
            v-if="newKeyCreated"
            wrapable
            :scrollable="false"
            left-icon="info-o"
            color="#1677ff"
            background="#e8f0fe"
            :text="`新 Key（请立即保存，仅显示一次）：${newKeyCreated}`"
            style="margin: 0 16px 12px"
          />

          <van-cell-group inset title="已有 Key">
            <template v-if="apiKeys.length">
              <van-cell
                v-for="k in apiKeys"
                :key="k.id"
                :title="k.name"
                :label="`${k.key_prefix}***   ${k.is_active ? '有效' : '已吩销'}${k.season_name ? '  【' + k.season_name + '】' : '  【不限赛季】'}`"
              >
                <template #right-icon>
                  <van-button
                    v-if="k.is_active"
                    size="mini"
                    type="danger"
                    plain
                    @click="revokeKey(k.id)"
                  >吊销</van-button>
                </template>
              </van-cell>
            </template>
            <van-empty v-else description="暂无 API Key" />
          </van-cell-group>
        </div>
      </van-tab>

      <van-tab title="🏆 赛季管理" name="seasons">
        <div class="tab-body">
          <van-cell-group inset title="新建赛季">
            <van-field v-model="newSeasonName" label="赛季名称" placeholder="例如：春季赛" />
            <van-field
              v-model="newSeasonYear"
              label="年份"
              readonly
              placeholder="点击选择年份"
              @click="showYearPicker = true"
            />
            <van-field
              v-model="newSeasonStart"
              label="开始日期"
              readonly
              clearable
              placeholder="点击选择（可选）"
              @click="showStartPicker = true"
              @clear="newSeasonStart = ''"
            />
            <van-field
              v-model="newSeasonEnd"
              label="结束日期"
              readonly
              clearable
              placeholder="点击选择（可选）"
              @click="showEndPicker = true"
              @clear="newSeasonEnd = ''"
            />
            <van-field v-model="newSeasonDescription" label="说明" type="textarea" rows="2" autosize placeholder="可选：赛季备注" />
          </van-cell-group>

          <!-- 年份选择 Popup -->
          <van-popup v-model:show="showYearPicker" position="bottom" round>
            <van-date-picker
              :model-value="newSeasonYearArr"
              :columns-type="['year']"
              :min-date="new Date(2000, 0, 1)"
              :max-date="new Date(2040, 11, 31)"
              title="选择年份"
              @confirm="onYearPickerConfirm"
              @cancel="showYearPicker = false"
            />
          </van-popup>

          <!-- 开始日期 Popup -->
          <van-popup v-model:show="showStartPicker" position="bottom" round>
            <van-date-picker
              :model-value="newSeasonStartArr"
              :columns-type="['year', 'month', 'day']"
              :min-date="new Date(2000, 0, 1)"
              :max-date="new Date(2040, 11, 31)"
              title="选择开始日期"
              @confirm="onStartPickerConfirm"
              @cancel="showStartPicker = false"
            />
          </van-popup>

          <!-- 结束日期 Popup -->
          <van-popup v-model:show="showEndPicker" position="bottom" round>
            <van-date-picker
              :model-value="newSeasonEndArr"
              :columns-type="['year', 'month', 'day']"
              :min-date="new Date(2000, 0, 1)"
              :max-date="new Date(2040, 11, 31)"
              title="选择结束日期"
              @confirm="onEndPickerConfirm"
              @cancel="showEndPicker = false"
            />
          </van-popup>

          <div style="padding: 16px">
            <van-button type="primary" block :loading="creatingSeason" @click="doCreateSeason">
              创建赛季
            </van-button>
          </div>

          <div class="season-list-title">已有赛季</div>
          <template v-if="seasons.length">
            <div v-for="season in seasons" :key="season.id" class="season-item">
              <div class="season-main">
                <div class="season-name-row">
                  <span class="season-name">{{ formatSeasonLabel(season) }}</span>
                  <van-tag :type="season.is_active ? 'success' : 'default'">
                    {{ season.is_active ? '启用中' : '已停用' }}
                  </van-tag>
                </div>
                <div class="season-date">{{ formatSeasonRange(season) }}</div>
                <div v-if="season.description" class="season-description">{{ season.description }}</div>
              </div>
              <div class="season-actions">
                <van-switch
                  :model-value="season.is_active"
                  size="20px"
                  :loading="togglingSeasonId === season.id"
                  @update:model-value="toggleSeasonActive(season)"
                />
                <van-button
                  size="small"
                  type="danger"
                  plain
                  :loading="deletingSeasonId === season.id"
                  @click="removeSeason(season)"
                >删除</van-button>
              </div>
            </div>
          </template>
          <van-empty v-else description="暂无赛季" />
        </div>
      </van-tab>

      <van-tab title="📊 排名预览" name="preview">
        <div class="tab-body">
          <div class="season-toolbar">
            <div class="season-toolbar-title">预览赛季</div>
            <van-cell :value="previewSeasonLabel" is-link @click="showPreviewSeasonSheet = true" />
          </div>

          <div v-for="team in previewTeams" :key="team.id" class="preview-row">
            <div class="pr-rank">#{{ team.rank }}</div>
            <div class="pr-info">
              <div class="pr-name">{{ team.name }}</div>
              <div class="pr-meta">参赛 {{ team.tournament_count }} · 胜率 {{ (team.win_rate * 100).toFixed(1) }}%</div>
            </div>
            <div class="pr-score">{{ team.total_score.toFixed(1) }}</div>
          </div>
          <van-empty v-if="!previewTeams.length" description="暂无数据" />
        </div>
      </van-tab>
    </van-tabs>

    <!-- 赛季选择 Action Sheets -->
    <van-action-sheet
      v-model:show="showUploadSeasonSheet"
      title="选择目标赛季"
      :actions="adminSeasonSheetActions"
      cancel-text="取消"
      close-on-click-action
      @select="onUploadSeasonSheetSelect"
    />
    <van-action-sheet
      v-model:show="showBatchSeasonSheet"
      title="筛选赛季"
      :actions="batchSeasonSheetActions"
      cancel-text="取消"
      close-on-click-action
      @select="onBatchSeasonSheetSelect"
    />
    <van-action-sheet
      v-model:show="showPreviewSeasonSheet"
      title="选择预览赛季"
      :actions="adminSeasonSheetActions"
      cancel-text="取消"
      close-on-click-action
      @select="onPreviewSeasonSheetSelect"
    />
    <van-action-sheet
      v-model:show="showNewKeySeasonSheet"
      title="选择 Key 绑定赛季"
      :actions="newKeySeasonSheetActions"
      cancel-text="取消"
      close-on-click-action
      @select="onNewKeySeasonSheetSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { fetchTeamRankings, type ExternalTeamListItem, type SeasonOut } from '@/api/publicRanking'
import { useRankingAdminStore } from '@/stores/rankingAdmin'

const router = useRouter()
const store = useRankingAdminStore()

const activeTab = ref('upload')
const seasons = ref<SeasonOut[]>([])
const uploadSeasonId = ref<number | null>(null)
const batchSeasonId = ref<number>(0)
const previewSeasonId = ref<number | null>(null)

const seasonOptions = computed(() => (
  seasons.value.map((season) => ({ text: formatSeasonLabel(season), value: season.id }))
))

const batchSeasonOptions = computed(() => (
  [{ text: '全部赛季', value: 0 }, ...seasonOptions.value]
))

function formatSeasonLabel(season: SeasonOut) {
  return `${season.year} · ${season.name}`
}

function formatSeasonRange(season: SeasonOut) {
  const start = season.start_date || '未设置开始'
  const end = season.end_date || '未设置结束'
  return `${start} 至 ${end}`
}

function seasonLabelById(seasonId?: number | null) {
  if (!seasonId) return '未绑定赛季'
  const season = seasons.value.find((item) => item.id === seasonId)
  return season ? formatSeasonLabel(season) : `赛季 #${seasonId}`
}

async function loadSeasons() {
  seasons.value = await store.fetchSeasons()
  if (!seasons.value.length) {
    uploadSeasonId.value = null
    previewSeasonId.value = null
    return
  }

  const latestSeasonId = seasons.value[0]?.id
  if (!latestSeasonId) return
  if (!uploadSeasonId.value || !seasons.value.some((item) => item.id === uploadSeasonId.value)) {
    uploadSeasonId.value = latestSeasonId
  }
  if (!previewSeasonId.value || !seasons.value.some((item) => item.id === previewSeasonId.value)) {
    previewSeasonId.value = latestSeasonId
  }
}

const fileList = ref<any[]>([])
const selectedFile = ref<File | null>(null)
const uploadNotes = ref('')
const uploading = ref(false)
const autoCreateSeason = ref(false)

function onFileRead(file: { file?: File } | Array<{ file?: File }>) {
  const item = Array.isArray(file) ? file[0] : file
  selectedFile.value = item?.file ?? null
}

async function doUpload() {
  if (!selectedFile.value) {
    showToast('请先选择文件')
    return
  }
  if (!autoCreateSeason.value && !uploadSeasonId.value) {
    showToast('请先选择赛季，或开启「自动建立赛季」')
    return
  }

  uploading.value = true
  try {
    const result = await store.uploadFile(
      selectedFile.value,
      uploadSeasonId.value,
      uploadNotes.value || undefined,
      autoCreateSeason.value,
    )
    const seasonTip = result.season_name ? `（赛季：${result.season_name}）` : ''
    showToast(`✅ 上传成功，处理 ${result.teams_processed} 支队伍${seasonTip}`)
    fileList.value = []
    selectedFile.value = null
    uploadNotes.value = ''
    // 自动刷新：跳转到实际入库的赛季
    const effectiveSeasonId = result.season_id ?? uploadSeasonId.value
    batchSeasonId.value = effectiveSeasonId
    previewSeasonId.value = effectiveSeasonId
    await loadSeasons()
    await loadBatches()
    await loadPreview()
  } catch (error: any) {
    showToast(error?.response?.data?.detail || '上传失败，请检查文件格式')
  } finally {
    uploading.value = false
  }
}

const batches = ref<any[]>([])
const batchRefreshing = ref(false)
const deletingId = ref<number | null>(null)
const restoringId = ref<number | null>(null)

async function loadBatches() {
  try {
    batches.value = await store.fetchBatches(batchSeasonId.value || undefined)
  } finally {
    batchRefreshing.value = false
  }
}

async function deleteBatch(id: number) {
  try {
    await showConfirmDialog({ title: '确认删除', message: '删除批次将重新计算该赛季排名，确认?', confirmButtonColor: '#ee0a24' })
    deletingId.value = id
    await store.deleteBatch(id)
    showToast('已删除')
    await loadBatches()
    await loadPreview()
  } catch {
  } finally {
    deletingId.value = null
  }
}

async function restoreBatch(id: number) {
  try {
    await showConfirmDialog({ title: '确认恢复', message: '将恢复该批次对应赛季的排行榜，确认?', confirmButtonColor: '#1677ff' })
    restoringId.value = id
    const result = await store.restoreBatch(id)
    showToast(`✅ 已恢复，处理 ${result.teams_processed} 支队伍`)
    await loadBatches()
    await loadPreview()
  } catch {
  } finally {
    restoringId.value = null
  }
}

function normalizeUtcInput(value: string): string {
  if (!value) return ''
  return /Z|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`
}

function formatDate(iso: string) {
  const normalized = normalizeUtcInput(iso)
  if (!normalized) return '-'
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return iso
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(date)
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '00'
  return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}:${get('second')} (北京时间)`
}

const apiKeys = ref<any[]>([])
const newKeyName = ref('')
const newKeySeasonId = ref<number | null>(null)
const creatingKey = ref(false)
const newKeyCreated = ref('')
const showNewKeySeasonSheet = ref(false)

const newKeySeasonSheetActions = computed(() => [
  { name: '不限赛季（通用）', id: 0, color: !newKeySeasonId.value ? '#1677ff' : '#323233' },
  ...seasons.value.map(s => ({
    name: formatSeasonLabel(s),
    id: s.id,
    color: newKeySeasonId.value === s.id ? '#1677ff' : '#323233',
  })),
])
const newKeySeasonLabel = computed(() =>
  newKeySeasonId.value ? seasonLabelById(newKeySeasonId.value) : '不限赛季（通用）'
)
function onNewKeySeasonSheetSelect(action: any) {
  newKeySeasonId.value = action.id || null
  showNewKeySeasonSheet.value = false
}

async function loadApiKeys() {
  apiKeys.value = await store.fetchApiKeys()
}

async function doCreateKey() {
  if (!newKeyName.value.trim()) {
    showToast('请输入备注名')
    return
  }
  creatingKey.value = true
  try {
    const result = await store.createApiKey(newKeyName.value.trim(), newKeySeasonId.value ?? undefined)
    newKeyCreated.value = result.full_key
    newKeyName.value = ''
    newKeySeasonId.value = null
    await loadApiKeys()
  } catch {
    showToast('创建失败')
  } finally {
    creatingKey.value = false
  }
}

async function revokeKey(id: number) {
  try {
    await showConfirmDialog({ title: '确认吊销', message: '吊销后该 Key 将立即失效', confirmButtonColor: '#ee0a24' })
    await store.revokeApiKey(id)
    showToast('已吊销')
    await loadApiKeys()
  } catch {
  }
}

const newSeasonName = ref('')
const newSeasonYear = ref(String(new Date().getFullYear()))
const newSeasonYearArr = ref([String(new Date().getFullYear())])
const newSeasonStart = ref('')
const newSeasonStartArr = ref([String(new Date().getFullYear()), '01', '01'])
const newSeasonEnd = ref('')
const newSeasonEndArr = ref([String(new Date().getFullYear()), '12', '31'])
const newSeasonDescription = ref('')
const creatingSeason = ref(false)
const togglingSeasonId = ref<number | null>(null)
const deletingSeasonId = ref<number | null>(null)

const showYearPicker = ref(false)
const showStartPicker = ref(false)
const showEndPicker = ref(false)

function onYearPickerConfirm({ value }: { value: string[] }) {
  newSeasonYear.value = value[0] ?? newSeasonYear.value
  newSeasonYearArr.value = value
  showYearPicker.value = false
}

function onStartPickerConfirm({ value }: { value: string[] }) {
  newSeasonStart.value = `${value[0]}-${value[1]}-${value[2]}`
  newSeasonStartArr.value = value
  showStartPicker.value = false
}

function onEndPickerConfirm({ value }: { value: string[] }) {
  newSeasonEnd.value = `${value[0]}-${value[1]}-${value[2]}`
  newSeasonEndArr.value = value
  showEndPicker.value = false
}

async function doCreateSeason() {
  const name = newSeasonName.value.trim()
  const year = Number(newSeasonYear.value)

  if (!name) {
    showToast('请输入赛季名称')
    return
  }
  if (!Number.isInteger(year) || year < 2000) {
    showToast('请输入正确的年份')
    return
  }

  creatingSeason.value = true
  try {
    const season = await store.createSeason({
      name,
      year,
      start_date: newSeasonStart.value || undefined,
      end_date: newSeasonEnd.value || undefined,
      description: newSeasonDescription.value || undefined,
    })
    showToast(`已创建 ${formatSeasonLabel(season)}`)
    newSeasonName.value = ''
    newSeasonYear.value = String(year)
    newSeasonStart.value = ''
    newSeasonEnd.value = ''
    newSeasonDescription.value = ''
    await loadSeasons()
    uploadSeasonId.value = season.id
    previewSeasonId.value = season.id
    batchSeasonId.value = season.id
    await loadBatches()
    await loadPreview()
  } catch (error: any) {
    showToast(error?.response?.data?.detail || '创建赛季失败')
  } finally {
    creatingSeason.value = false
  }
}

async function toggleSeasonActive(season: SeasonOut) {
  togglingSeasonId.value = season.id
  try {
    await store.updateSeason(season.id, { is_active: !season.is_active })
    await loadSeasons()
  } catch (error: any) {
    showToast(error?.response?.data?.detail || '更新赛季状态失败')
  } finally {
    togglingSeasonId.value = null
  }
}

async function removeSeason(season: SeasonOut) {
  try {
    await showConfirmDialog({
      title: '确认删除赛季',
      message: `删除 ${formatSeasonLabel(season)} 会同时删除该赛季榜单和上传历史，确认?`,
      confirmButtonColor: '#ee0a24',
    })
    deletingSeasonId.value = season.id
    await store.deleteSeason(season.id)
    showToast('赛季已删除')
    await loadSeasons()
    await loadBatches()
    await loadPreview()
  } catch {
  } finally {
    deletingSeasonId.value = null
  }
}

const previewTeams = ref<ExternalTeamListItem[]>([])

// Action-sheet 选择器
 const showUploadSeasonSheet = ref(false)
const showBatchSeasonSheet = ref(false)
const showPreviewSeasonSheet = ref(false)

const adminSeasonSheetActions = computed(() =>
  seasons.value.map(s => ({ name: formatSeasonLabel(s), id: s.id }))
)
const batchSeasonSheetActions = computed(() => [
  { name: '全部赛季', id: 0 },
  ...seasons.value.map(s => ({ name: formatSeasonLabel(s), id: s.id })),
])
const uploadSeasonLabel = computed(() =>
  uploadSeasonId.value ? seasonLabelById(uploadSeasonId.value) : '请选择赛季'
)
const batchSeasonLabel = computed(() =>
  batchSeasonId.value ? seasonLabelById(batchSeasonId.value) : '全部赛季'
)
const previewSeasonLabel = computed(() =>
  previewSeasonId.value ? seasonLabelById(previewSeasonId.value) : '请选择赛季'
)

function onUploadSeasonSheetSelect(action: any) {
  uploadSeasonId.value = action.id || null
  showUploadSeasonSheet.value = false
}
function onBatchSeasonSheetSelect(action: any) {
  batchSeasonId.value = action.id
  showBatchSeasonSheet.value = false
  void loadBatches()
}
function onPreviewSeasonSheetSelect(action: any) {
  previewSeasonId.value = action.id || null
  showPreviewSeasonSheet.value = false
  void loadPreview()
}

async function loadPreview() {
  if (!previewSeasonId.value) {
    previewTeams.value = []
    return
  }
  const res = await fetchTeamRankings({ page: 1, page_size: 50, season_id: previewSeasonId.value })
  previewTeams.value = res.items
}

function doLogout() {
  store.logout()
  router.replace({ name: 'ranking-admin-login' })
}

onMounted(async () => {
  await loadSeasons()
  await Promise.all([
    loadBatches(),
    loadApiKeys(),
    loadPreview(),
  ])
})
</script>

<style scoped>
.ra-dashboard {
  min-height: 100vh;
  background: #f5f7fa;
}

.tab-body {
  padding-bottom: 20px;
}

.season-toolbar {
  margin: 12px 16px;
}

.season-toolbar-title {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #4a4a4a;
}

.batch-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  margin: 8px 16px;
  border-radius: 10px;
  padding: 12px 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}

.batch-info {
  flex: 1;
}

.batch-date {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 4px;
}

.batch-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #888;
}

.batch-notes {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.batch-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-left: 8px;
  flex-shrink: 0;
}

.season-list-title {
  margin: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  color: #4a4a4a;
}

.season-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  background: #fff;
  margin: 8px 16px;
  border-radius: 12px;
  padding: 14px 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}

.season-main {
  flex: 1;
}

.season-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.season-name {
  font-size: 15px;
  font-weight: 700;
  color: #1a1a1a;
}

.season-date {
  margin-top: 6px;
  font-size: 12px;
  color: #7a7a7a;
}

.season-description {
  margin-top: 6px;
  font-size: 12px;
  color: #555;
}

.season-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.preview-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
}

.pr-rank {
  width: 36px;
  font-size: 16px;
  font-weight: 800;
  color: #1677ff;
  text-align: center;
}

.pr-info {
  flex: 1;
}

.pr-name {
  font-size: 14px;
  font-weight: 600;
}

.pr-meta {
  font-size: 11px;
  color: #888;
}

.pr-score {
  font-size: 16px;
  font-weight: 700;
  color: #1677ff;
}
</style>