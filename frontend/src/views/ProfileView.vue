<template>
  <div class="profile-page">
    <van-nav-bar title="个人信息" right-text="退出" @click-right="handleLogout" />
    <template v-if="profile">
      <!-- ─── HERO 区 ─── -->
      <div class="profile-hero">
        <div class="profile-hero__top">
          <van-uploader
            :after-read="handleAvatarUpload"
            accept="image/*"
            :max-count="1"
            :show-upload="true"
            :preview-image="false"
          >
            <div class="avatar-wrapper">
              <img v-if="profile.avatar_url" :src="profile.avatar_url" class="avatar-img" />
              <div v-else class="avatar-placeholder">
                <van-icon name="photo-o" size="32" color="#93c5fd" />
              </div>
              <div class="avatar-edit-badge">
                <van-icon name="edit" size="14" color="#fff" />
              </div>
            </div>
          </van-uploader>
          <div class="profile-hero__info">
            <div class="hero-name">{{ profile.display_name || profile.username }}</div>
            <div class="hero-meta">
              <van-tag :type="isAdmin ? 'warning' : 'primary'">{{ isAdmin ? '队伍管理员' : '队员' }}</van-tag>
              <span v-if="profile.jersey_number != null" class="hero-jersey">#{{ profile.jersey_number }}</span>
              <span v-if="profile.gender" :class="['hero-gender', profile.gender === 'M' ? 'gender-m' : 'gender-f']">
                {{ profile.gender === 'M' ? '♂' : '♀' }}
              </span>
            </div>
            <div v-if="compositeScore != null" class="hero-rating">
              <span class="hero-rating-val">{{ compositeScore.toFixed(1) }}</span>
              <span class="hero-rating-lbl">综合战力</span>
            </div>
          </div>
        </div>
        <div class="profile-hero__actions">
          <van-button size="small" plain round @click="openEdit">✎ 编辑资料</van-button>
          <van-button size="small" plain type="danger" round @click="showPwdPopup = true">修改密码</van-button>
        </div>
      </div>

      <!-- ─── 战绩统计 ─── -->
      <div class="stats-section">
        <p v-if="profile.total_matches < 5" class="stats-notice">📊 数据积累中（已参与 {{ profile.total_matches }} 场）</p>
        <div class="stats-row">
          <div class="stat-chip">
            <strong>{{ profile.total_matches }}</strong><span>场次</span>
          </div>
          <div class="stat-chip stat-chip--wins">
            <strong>{{ profile.total_wins }}</strong><span>胜场</span>
          </div>
          <div class="stat-chip stat-chip--goals">
            <strong>{{ profile.total_goals }}</strong><span>进球</span>
          </div>
          <div class="stat-chip stat-chip--assists">
            <strong>{{ profile.total_assists }}</strong><span>助攻</span>
          </div>
        </div>
      </div>

      <!-- ─── 我的排名 ─── -->
      <div v-if="myRanks" class="rank-section">
        <div class="section-title-row">
          我的排名
          <span class="section-subtitle">共 {{ myRanks.total }} 人参与</span>
        </div>
        <div class="rank-grid">
          <div
            v-for="r in myRankItems"
            :key="r.key"
            :class="['rank-item', selectedRankKey === r.key && 'rank-item--active']"
            @click="selectedRankKey = r.key"
          >
            <div class="rank-item__label">{{ r.label }}</div>
            <div class="rank-item__value">
              <template v-if="r.rank != null">第 <strong>{{ r.rank }}</strong> 名</template>
              <span v-else style="color:#bbb">— 未上榜</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ─── 功能入口 ─── -->
      <div class="feature-section">
        <div class="section-title-row">快捷功能</div>
        <div class="feature-grid">
          <div class="feature-btn" @click="router.push('/docs-learn?doc=rules')">
            <van-icon name="description" class="feature-btn__icon" />
            <span>飞盘规则</span>
          </div>
          <div class="feature-btn" @click="router.push('/docs-learn?doc=drills')">
            <van-icon name="guide-o" class="feature-btn__icon" />
            <span>技巧文档</span>
          </div>
          <div class="feature-btn" @click="showHelpPopup = true">
            <van-icon name="question-o" class="feature-btn__icon" />
            <span>使用手册</span>
          </div>
          <template v-if="isAdmin">
            <div class="feature-btn feature-btn--admin" @click="router.push('/admin')">
              <van-icon name="setting-o" class="feature-btn__icon" />
              <span>管理后台</span>
            </div>
            <div class="feature-btn feature-btn--admin" @click="openExportPopup">
              <van-icon name="down" class="feature-btn__icon" />
              <span>导出数据</span>
            </div>
          </template>
        </div>
      </div>

      <!-- ─── 我的队伍 (T033/T073 [US3]) ─── -->
      <van-cell-group inset title="我的队伍">
        <template v-if="auth.availableTeams.length > 0">
          <van-cell
            v-for="team in auth.availableTeams"
            :key="team.team_id"
            :title="team.team_name || '未知队伍'"
            :label="roleLabelMap[team.role] || team.role"
          >
            <template #right-icon>
              <div style="display:flex;align-items:center;gap:8px">
                <van-tag
                  v-if="isDefaultTeam(team.team_id)"
                  type="success"
                >默认</van-tag>
                <van-button
                  v-else
                  size="mini"
                  plain
                  type="primary"
                  :loading="settingDefaultTeam === team.team_id"
                  @click="handleSetDefaultTeam(team.team_id)"
                >设为默认</van-button>
              </div>
            </template>
          </van-cell>
        </template>
        <van-cell v-else title="暂无队伍" label="申请加入队伍后将在此显示" />
        <!-- 申请入队按钮 -->
        <van-cell
          title="申请加入新队伍"
          is-link
          @click="showApplyTeamPopup = true"
        >
          <template #icon>
            <van-icon name="add-o" style="margin-right:6px;font-size:18px;" />
          </template>
        </van-cell>
      </van-cell-group>

      <!-- ─── 基本信息 ─── -->
      <van-cell-group inset title="基本信息">
        <van-cell title="账户名" :value="profile.username" />
        <van-cell title="昵称（排行榜）" :value="profile.display_name || '-'" />
        <van-cell title="邮箱" :value="profile.email || '未设置'" />
        <van-cell title="性别" :value="profile.gender === 'M' ? '♂ 男' : profile.gender === 'F' ? '♀ 女' : '未设置'" />
        <van-cell title="球衣号码" :value="profile.jersey_number != null ? '#' + profile.jersey_number : '未设置'" />
      </van-cell-group>

      <!-- 管理员：榜单展示开关 -->
      <van-cell-group v-if="isAdmin" inset>
        <van-cell title="展示在排行榜" label="关闭后管理员不显示在任何榜单中">
          <template #right-icon>
            <van-switch
              :model-value="profile.show_in_rankings"
              size="20"
              @update:model-value="toggleShowInRankings"
            />
          </template>
        </van-cell>
      </van-cell-group>


    </template>
    <van-loading v-else type="spinner" vertical style="padding:60px 0;">加载中...</van-loading>

    <!-- 个人资料编辑弹窗 -->
    <van-popup v-model:show="showEditPopup" position="bottom" round style="padding: 16px 0 32px">
      <van-nav-bar title="编辑个人资料" left-text="取消" @click-left="showEditPopup = false" />
      <!-- T053 [US6]: 双层字段提示 -->
      <div style="padding: 8px 16px 0; font-size: 12px; color: #999; line-height: 1.6">
        <div>· <strong>用户名</strong>：全局唯一账号名，用于登录（修改后全部队伍同步）</div>
        <div>· <strong>昵称</strong>：当前队伍的显示名称，各队伍独立</div>
      </div>
      <van-cell-group inset style="margin-top: 12px">
        <!-- T053: user 层 - 全局用户名 -->
        <van-field
          v-model="editForm.username"
          label="用户名"
          placeholder="英文/数字/下划线，3-20 位（全局唯一）"
          clearable
        />
        <!-- T053: player 层 - 队伍昵称 -->
        <van-field
          v-model="editForm.display_name"
          label="昵称"
          placeholder="显示在榜单上（当前队伍）"
          clearable
        />
        <van-field
          v-model="editForm.email"
          label="邮箱"
          placeholder="用于找回密码"
          type="email"
          clearable
        />
        <van-field name="gender" label="性别">
          <template #input>
            <van-radio-group v-model="editForm.gender" direction="horizontal">
              <van-radio name="M">男</van-radio>
              <van-radio name="F">女</van-radio>
              <van-radio name="">不填写</van-radio>
            </van-radio-group>
          </template>
        </van-field>
        <van-field
          v-model="editForm.jersey_number"
          label="球衣号码"
          placeholder="可选，0-999"
          type="digit"
          clearable
        />
      </van-cell-group>
      <div style="margin: 16px">
        <van-button round block type="primary" :loading="saving" @click="saveProfile">保存修改</van-button>
      </div>
    </van-popup>

    <!-- 管理员数据导出弹窗 -->
    <van-popup v-model:show="showExportPopup" position="bottom" round style="padding: 16px 0 32px">
      <van-nav-bar title="导出数据" left-text="取消" @click-left="showExportPopup = false" />
      <van-cell-group inset style="margin-top: 12px">
        <van-field label="导出内容">
          <template #input>
            <div style="width: 100%">
              <div style="display: flex; justify-content: flex-end; margin-bottom: 8px">
                <van-button size="mini" plain type="primary" @click="toggleSelectAllExportOptions">
                  {{ isAllExportOptionsSelected ? '清空' : '全选' }}
                </van-button>
              </div>
              <van-checkbox-group v-model="selectedExportKeys" direction="vertical">
                <van-checkbox v-for="item in exportOptions" :key="item.value" :name="item.value">
                  {{ item.label }}
                </van-checkbox>
              </van-checkbox-group>
            </div>
          </template>
        </van-field>
        <van-field v-if="selectedExportKeys.includes('rankings')" label="排行榜类型">
          <template #input>
            <div style="width: 100%">
              <van-search v-model="rankingKeyword" placeholder="筛选排行榜类型" shape="round" />
              <div style="display: flex; justify-content: flex-end; margin: 8px 0">
                <van-button size="mini" plain type="primary" @click="toggleSelectAllRankingTypes">
                  {{ isAllFilteredRankingTypesSelected ? '清空筛选项' : '全选筛选项' }}
                </van-button>
              </div>
              <van-checkbox-group v-model="selectedRankingTypes" direction="vertical">
                <van-checkbox v-for="item in filteredRankingTypeOptions" :key="item.value" :name="item.value">
                  {{ item.label }}
                </van-checkbox>
              </van-checkbox-group>
            </div>
          </template>
        </van-field>
        <van-field v-if="selectedExportKeys.includes('schedule')" label="日程范围">
          <template #input>
            <div style="width: 100%; display: grid; gap: 8px;">
              <input v-model="scheduleExportRange.start_date" type="date" class="export-date-input" />
              <input v-model="scheduleExportRange.end_date" type="date" class="export-date-input" />
              <div style="font-size: 12px; color: #666">将导出所选时间范围内的日程、每位队员的出勤状态与分 Line 情况。</div>
            </div>
          </template>
        </van-field>
        <van-field v-if="selectedExportKeys.includes('player-stats')" label="选择队员">
          <template #input>
            <div style="width: 100%">
              <van-search v-model="playerKeyword" placeholder="按昵称或账户名筛选队员" shape="round" />
              <div style="display: flex; justify-content: flex-end; margin: 8px 0">
                <van-button size="mini" plain type="primary" @click="toggleSelectAllPlayers">
                  {{ isAllFilteredPlayersSelected ? '清空筛选项' : '全选筛选项' }}
                </van-button>
              </div>
              <van-checkbox-group v-model="selectedPlayerIds" direction="vertical">
                <van-checkbox v-for="item in filteredExportPlayers" :key="item.id" :name="item.id">
                  {{ item.display_name || item.username }}（{{ item.username }}）
                </van-checkbox>
              </van-checkbox-group>
            </div>
          </template>
        </van-field>
      </van-cell-group>
      <div style="margin: 16px">
        <div style="margin-bottom: 8px; color: #666; font-size: 12px">
          <div>导出预览：将生成 {{ exportPreview.totalFiles }} 份 CSV</div>
          <div v-if="exportPreview.details.length">{{ exportPreview.details.join('；') }}</div>
          <div v-if="!canExportNow" style="color: #d97706; margin-top: 4px">{{ exportInvalidReason }}</div>
        </div>
        <van-button round block type="primary" :loading="exporting" :disabled="!canExportNow" @click="confirmExport">
          确认导出
        </van-button>
      </div>
    </van-popup>

    <!-- 修改密码弹窗 -->
    <van-popup v-model:show="showPwdPopup" position="bottom" round style="padding: 16px 0 32px">
      <van-nav-bar title="修改密码" left-text="取消" @click-left="showPwdPopup = false" />
      <van-cell-group inset style="margin-top: 12px">
        <van-field
          v-model="pwdForm.old_password"
          label="原密码"
          placeholder="请输入当前密码"
          type="password"
          clearable
        />
        <van-field
          v-model="pwdForm.new_password"
          label="新密码"
          placeholder="至少 6 位"
          type="password"
          clearable
        />
        <van-field
          v-model="pwdForm.confirm_password"
          label="确认新密码"
          placeholder="再次输入新密码"
          type="password"
          clearable
        />
      </van-cell-group>
      <div style="margin: 16px">
        <van-button round block type="primary" :loading="savingPwd" @click="changePwd">确认修改</van-button>
      </div>
    </van-popup>

    <!-- 帮助手册弹窗 -->
    <van-popup v-model:show="showHelpPopup" position="bottom" round style="height: 85vh; display: flex; flex-direction: column">
      <van-nav-bar
        :title="isAdmin ? '管理员使用手册' : '队员使用手册'"
        left-text="关闭"
        @click-left="showHelpPopup = false"
      />
      <div v-if="helpLoading" style="display: flex; justify-content: center; padding: 40px">
        <van-loading type="spinner">加载中...</van-loading>
      </div>
      <div v-else-if="helpContent" class="help-content" v-html="helpContent" />
      <div v-else style="padding: 32px; text-align: center; color: #999">暂无内容</div>
    </van-popup>

    <!-- T073 [US3]: 申请加入新队伍弹窗 -->
    <van-popup v-model:show="showApplyTeamPopup" position="bottom" round style="padding: 16px 0 32px">
      <van-nav-bar title="申请加入新队伍" left-text="取消" @click-left="showApplyTeamPopup = false" />
      <van-cell-group inset style="margin-top: 12px">
        <van-field
          v-model="applyTeamName"
          label="队伍名称"
          placeholder="输入要加入的队伍名称"
          clearable
        />
        <van-field
          v-model="applyJoinReason"
          label="申请理由"
          placeholder="可选，最多 200 字"
          type="textarea"
          rows="2"
          clearable
          maxlength="200"
        />
      </van-cell-group>
      <div style="margin: 16px">
        <van-button
          round block type="primary"
          :loading="applyingTeam"
          :disabled="!applyTeamName.trim()"
          @click="handleApplyTeam"
        >提交申请</van-button>
      </div>
    </van-popup>

    <van-tabbar route>
      <van-tabbar-item replace to="/home" icon="home-o">主页</van-tabbar-item>
      <van-tabbar-item replace to="/rankings" icon="chart-trending-o">排行榜</van-tabbar-item>
      <van-tabbar-item icon="plus" @click="router.push('/matches/new')">
        <template #icon="{ active }">
          <div class="tab-plus" :class="{ active }">＋</div>
        </template>
        新建
      </van-tabbar-item>
      <van-tabbar-item replace to="/matches/list" icon="records-o">比赛</van-tabbar-item>
      <van-tabbar-item replace to="/profile" icon="user-o">我的</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const isAdmin = auth.isAdmin
const profile = ref<any>(null)
const compositeScore = ref<number | null>(null)

// --- 个人排名 ---
const myRanks = ref<{ total: number; ranks: Record<string, number | null> } | null>(null)
const selectedRankKey = ref<string>('composite')
const myRankDefinitions = [
  { key: 'composite', label: '综合战力' },
  { key: 'progress', label: '进步速度' },
  { key: 'goals', label: '得分榜' },
  { key: 'assists', label: '助攻榜' },
  { key: 'plus_minus', label: '正负值' },
  { key: 'turnovers', label: '失误少' },
]
const myRankItems = computed(() =>
  myRankDefinitions.map(d => ({
    ...d,
    rank: myRanks.value?.ranks[d.key] ?? null,
  }))
)
const selectedRankLabel = computed(() =>
  myRankDefinitions.find(d => d.key === selectedRankKey.value)?.label ?? ''
)

// --- 帮助手册 ---
const showHelpPopup = ref(false)
const helpContent = ref<string>('')
const helpLoading = ref(false)

watch(showHelpPopup, async (shown) => {
  if (!shown || helpContent.value) return
  helpLoading.value = true
  try {
    const docType = isAdmin ? 'admin' : 'member'
    const res = await api.get<{ html: string }>(`/help-docs/${docType}`)
    helpContent.value = res.data.html
  } catch {
    helpContent.value = '<p style="color:#999;padding:16px;">手册内容暂时无法加载</p>'
  } finally {
    helpLoading.value = false
  }
})

// --- 编辑资料 ---
const showEditPopup = ref(false)
const saving = ref(false)
const editForm = reactive({ username: '', display_name: '', email: '', gender: '', jersey_number: '' })

function openEdit() {
  editForm.username = profile.value?.username ?? ''
  editForm.display_name = profile.value?.display_name ?? ''
  editForm.email = profile.value?.email ?? ''
  editForm.gender = profile.value?.gender ?? ''
  editForm.jersey_number = profile.value?.jersey_number != null ? String(profile.value.jersey_number) : ''
  showEditPopup.value = true
}

// T053 [US6]: 双层资料更新
async function saveProfile() {
  saving.value = true
  try {
    const userPayload: Record<string, any> = {}
    const playerPayload: Record<string, any> = {}

    // user 层: 全局用户名
    const uname = editForm.username.trim()
    if (uname && uname !== profile.value?.username) {
      if (!/^[a-zA-Z0-9_]{3,20}$/.test(uname)) {
        showToast('用户名只能含英文、数字、下划线，长度 3-20 位')
        return
      }
      userPayload.username = uname
    }

    // player 层: 当前队伍字段
    const dn = editForm.display_name.trim()
    if (dn !== (profile.value?.display_name ?? '')) {
      playerPayload.display_name = dn || null
    }
    playerPayload.email = editForm.email.trim() || null
    playerPayload.gender = editForm.gender || ''
    if (editForm.jersey_number.trim() !== '') {
      const n = parseInt(editForm.jersey_number)
      if (!isNaN(n) && n >= 0 && n <= 999) playerPayload.jersey_number = n
    } else {
      playerPayload.jersey_number = null
    }

    const body: Record<string, any> = {}
    if (Object.keys(userPayload).length > 0) body.user = userPayload
    body.player = playerPayload

    const res = await api.patch('/players/me/profile/dual', body)
    // 同步更新 profile 展示
    if (profile.value) {
      if (res.data.user_username) profile.value.username = res.data.user_username
      if (res.data.display_name !== undefined) profile.value.display_name = res.data.display_name
      if (res.data.email !== undefined) profile.value.email = res.data.email
      if (res.data.gender !== undefined) profile.value.gender = res.data.gender
      if (res.data.jersey_number !== undefined) profile.value.jersey_number = res.data.jersey_number
    }
    showEditPopup.value = false
    showToast({ message: '修改成功', type: 'success' })
    await auth.fetchMe()
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '修改失败')
  } finally {
    saving.value = false
  }
}

async function toggleShowInRankings(val: boolean) {
  try {
    const res = await api.put('/players/me/profile', { show_in_rankings: val })
    profile.value = res.data
    showToast({ message: val ? '已展示在榜单' : '已从榜单隐藏', type: 'success' })
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '设置失败')
  }
}

// --- T033/T073 [US3]: 我的队伍 + 默认队伍 + 申请入队 ---
const roleLabelMap: Record<string, string> = {
  owner: '队长',
  admin: '管理员',
  member: '队员',
}

const settingDefaultTeam = ref<number | null>(null)

function isDefaultTeam(teamId: number): boolean {
  return auth.userContext?.default_team_id === teamId
}

async function handleSetDefaultTeam(teamId: number) {
  settingDefaultTeam.value = teamId
  try {
    await auth.setDefaultTeam(teamId)
    showToast({ message: '默认队伍已更新', type: 'success' })
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '设置失败')
  } finally {
    settingDefaultTeam.value = null
  }
}

const showApplyTeamPopup = ref(false)
const applyTeamName = ref('')
const applyJoinReason = ref('')
const applyingTeam = ref(false)

async function handleApplyTeam() {
  const teamName = applyTeamName.value.trim()
  if (!teamName) {
    showToast('请输入队伍名称')
    return
  }
  applyingTeam.value = true
  try {
    await api.post('/team-membership/applications', {
      team_name: teamName,
      join_reason: applyJoinReason.value.trim() || null,
    })
    showToast({ message: '申请已提交，等待管理员审核', type: 'success' })
    showApplyTeamPopup.value = false
    applyTeamName.value = ''
    applyJoinReason.value = ''
    // 刷新上下文（申请后队伍列表可能尚未更新，但 pending 状态已创建）
    await auth.fetchContext()
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '申请失败')
  } finally {
    applyingTeam.value = false
  }
}

// --- 修改密码 ---
const showPwdPopup = ref(false)
const savingPwd = ref(false)
const pwdForm = reactive({ old_password: '', new_password: '', confirm_password: '' })

// --- 数据导出 ---
const showExportPopup = ref(false)
const exporting = ref(false)
const selectedExportKeys = ref<string[]>([])
const selectedRankingTypes = ref<string[]>([])
const rankingKeyword = ref('')
const playerKeyword = ref('')
const selectedPlayerIds = ref<number[]>([])
const exportPlayers = ref<Array<{ id: number; username: string; display_name: string | null }>>([])
const loadingExportPlayers = ref(false)
const scheduleExportRange = reactive({ start_date: '', end_date: '' })

const exportOptions = computed(() => {
  const base = [
    { label: '队员名单', value: 'players' },
    { label: '排行榜', value: 'rankings' },
    { label: '比赛数据', value: 'matches' },
    { label: '日程 / 出勤情况', value: 'schedule' },
    { label: '个人数据集合', value: 'player-stats' },
  ]
  if (auth.isSuperAdmin) {
    base.push({ label: '队伍配置系数（超管）', value: 'team-settings' })
  }
  return base
})

const rankingTypeOptions = [
  { label: '综合战力榜', value: 'composite' },
  { label: '战力榜（保守评分）', value: 'conservative' },
  { label: 'Mu 排行', value: 'mu' },
  { label: 'Sigma 排行（越小越好）', value: 'sigma' },
  { label: '进球榜', value: 'goals' },
  { label: '助攻榜', value: 'assists' },
  { label: '正负值榜', value: 'plus_minus' },
  { label: '失误榜（越少越好）', value: 'turnovers' },
]

const isAllExportOptionsSelected = computed(() => selectedExportKeys.value.length === exportOptions.value.length)

const filteredRankingTypeOptions = computed(() => {
  const kw = rankingKeyword.value.trim().toLowerCase()
  if (!kw) return rankingTypeOptions
  return rankingTypeOptions.filter((item) => item.label.toLowerCase().includes(kw) || item.value.toLowerCase().includes(kw))
})

const isAllFilteredRankingTypesSelected = computed(() => {
  const values = filteredRankingTypeOptions.value.map((item) => item.value)
  if (!values.length) return false
  return values.every((value) => selectedRankingTypes.value.includes(value))
})

const filteredExportPlayers = computed(() => {
  const kw = playerKeyword.value.trim().toLowerCase()
  if (!kw) return exportPlayers.value
  return exportPlayers.value.filter((item) => {
    const displayName = (item.display_name || '').toLowerCase()
    const username = item.username.toLowerCase()
    return displayName.includes(kw) || username.includes(kw)
  })
})

const isAllFilteredPlayersSelected = computed(() => {
  const ids = filteredExportPlayers.value.map((item) => item.id)
  if (!ids.length) return false
  return ids.every((id) => selectedPlayerIds.value.includes(id))
})

const exportPreview = computed(() => {
  let totalFiles = 0
  const details: string[] = []

  if (selectedExportKeys.value.includes('players')) {
    totalFiles += 1
    details.push('队员名单 1 份')
  }
  if (selectedExportKeys.value.includes('matches')) {
    totalFiles += 1
    details.push('比赛数据 1 份')
  }
  if (selectedExportKeys.value.includes('schedule')) {
    totalFiles += 1
    details.push(`日程出勤 1 份（${scheduleExportRange.start_date || '未设置'} ~ ${scheduleExportRange.end_date || '未设置'}）`)
  }
  if (selectedExportKeys.value.includes('rankings')) {
    totalFiles += selectedRankingTypes.value.length
    details.push(`排行榜 ${selectedRankingTypes.value.length} 份`)
  }
  if (selectedExportKeys.value.includes('player-stats')) {
    totalFiles += selectedPlayerIds.value.length
    details.push(`队员完整数据 ${selectedPlayerIds.value.length} 份`)
  }

  return { totalFiles, details }
})

const exportInvalidReason = computed(() => {
  if (!selectedExportKeys.value.length) return '请先选择至少一个导出内容'
  if (selectedExportKeys.value.includes('rankings') && !selectedRankingTypes.value.length) {
    return '已选择排行榜导出，请至少选择一个排行榜类型'
  }
  if (selectedExportKeys.value.includes('schedule')) {
    if (!scheduleExportRange.start_date || !scheduleExportRange.end_date) {
      return '已选择日程导出，请先设置开始和结束日期'
    }
    if (scheduleExportRange.end_date < scheduleExportRange.start_date) {
      return '日程导出结束日期不能早于开始日期'
    }
  }
  if (selectedExportKeys.value.includes('player-stats') && !selectedPlayerIds.value.length) {
    return '已选择队员数据导出，请至少选择一个队员'
  }
  return ''
})

const canExportNow = computed(() => !exportInvalidReason.value && exportPreview.value.totalFiles > 0)

async function loadExportPlayers() {
  if (loadingExportPlayers.value || exportPlayers.value.length) return
  loadingExportPlayers.value = true
  try {
    const all: Array<{ id: number; username: string; display_name: string | null }> = []
    const seen = new Set<number>()
    let page = 1
    while (true) {
      const res = await api.get('/players', { params: { page, page_size: 100 } })
      const items = Array.isArray(res.data) ? res.data : []
      for (const p of items) {
        if (typeof p?.id === 'number' && !seen.has(p.id)) {
          seen.add(p.id)
          all.push({ id: p.id, username: p.username, display_name: p.display_name ?? null })
        }
      }
      if (items.length < 100) break
      page += 1
    }
    all.sort((a, b) => (a.display_name || a.username).localeCompare(b.display_name || b.username, 'zh-CN'))
    exportPlayers.value = all
  } finally {
    loadingExportPlayers.value = false
  }
}

function toggleSelectAllExportOptions() {
  if (isAllExportOptionsSelected.value) {
    selectedExportKeys.value = []
    return
  }
  selectedExportKeys.value = exportOptions.value.map((item) => item.value)
}

function toggleSelectAllRankingTypes() {
  const values = filteredRankingTypeOptions.value.map((item) => item.value)
  if (!values.length) return
  if (isAllFilteredRankingTypesSelected.value) {
    selectedRankingTypes.value = selectedRankingTypes.value.filter((value) => !values.includes(value))
    return
  }
  selectedRankingTypes.value = Array.from(new Set([...selectedRankingTypes.value, ...values]))
}

function toggleSelectAllPlayers() {
  const ids = filteredExportPlayers.value.map((item) => item.id)
  if (!ids.length) return
  if (isAllFilteredPlayersSelected.value) {
    selectedPlayerIds.value = selectedPlayerIds.value.filter((id) => !ids.includes(id))
    return
  }
  selectedPlayerIds.value = Array.from(new Set([...selectedPlayerIds.value, ...ids]))
}

async function openExportPopup() {
  selectedExportKeys.value = []
  selectedRankingTypes.value = ['conservative']
  selectedPlayerIds.value = []
  rankingKeyword.value = ''
  playerKeyword.value = ''
  const today = new Date()
  scheduleExportRange.end_date = today.toISOString().slice(0, 10)
  scheduleExportRange.start_date = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-01`
  await loadExportPlayers()
  showExportPopup.value = true
}

function getFilenameFromDisposition(disposition?: string, fallback = 'export.csv') {
  if (!disposition) return fallback
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1])
  const basicMatch = disposition.match(/filename=\"?([^\";]+)\"?/i)
  if (basicMatch?.[1]) return basicMatch[1]
  return fallback
}

async function downloadOneCsv(key: string, params: Record<string, string | number> = {}) {
  const url = `/exports/${key}`
  const query: Record<string, string | number> = { format: 'csv', ...params }
  const res = await api.get(url, { params: query, responseType: 'blob' })
  const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8-sig' })
  const disposition = (res.headers?.['content-disposition'] as string | undefined) ?? undefined
  const filename = getFilenameFromDisposition(disposition, `${key}.csv`)

  const objectUrl = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(objectUrl)
}

async function confirmExport() {
  if (!selectedExportKeys.value.length) {
    showToast('请至少选择一个导出内容')
    return
  }

  const tasks: Array<{ key: string; params?: Record<string, string | number> }> = []
  for (const key of selectedExportKeys.value) {
    if (key === 'rankings') {
      if (!selectedRankingTypes.value.length) {
        showToast('请选择至少一个排行榜类型')
        return
      }
      for (const rankingType of selectedRankingTypes.value) {
        tasks.push({ key, params: { ranking_type: rankingType } })
      }
      continue
    }

    if (key === 'schedule') {
      if (!scheduleExportRange.start_date || !scheduleExportRange.end_date) {
        showToast('请先选择日程导出时间范围')
        return
      }
      tasks.push({
        key,
        params: { start_date: scheduleExportRange.start_date, end_date: scheduleExportRange.end_date },
      })
      continue
    }

    if (key === 'player-stats') {
      if (!selectedPlayerIds.value.length) {
        showToast('请选择至少一个队员')
        return
      }
      for (const playerId of selectedPlayerIds.value) {
        tasks.push({ key, params: { player_id: playerId } })
      }
      continue
    }

    tasks.push({ key })
  }

  exporting.value = true
  try {
    for (const task of tasks) {
      await downloadOneCsv(task.key, task.params)
    }
    showExportPopup.value = false
    showToast({ message: `已导出 ${tasks.length} 份 CSV`, type: 'success' })
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '导出失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}

async function changePwd() {
  if (!pwdForm.old_password || !pwdForm.new_password) {
    showToast('请填写完整')
    return
  }
  if (pwdForm.new_password !== pwdForm.confirm_password) {
    showToast('两次密码不一致')
    return
  }
  if (pwdForm.new_password.length < 6) {
    showToast('密码至少 6 位')
    return
  }
  savingPwd.value = true
  try {
    await api.put('/players/me/password', {
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password,
    })
    showPwdPopup.value = false
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    pwdForm.confirm_password = ''
    showToast({ message: '密码已修改', type: 'success' })
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '修改失败')
  } finally {
    savingPwd.value = false
  }
}

onMounted(async () => {
  try {
    const [profileRes, ranksRes, rankingsRes] = await Promise.all([
      api.get('/players/me'),
      api.get('/rankings/my-ranks').catch(() => null),
      api.get('/rankings', { params: { page: 1, page_size: 100, sort_by: 'composite' } }).catch(() => null),
    ])
    profile.value = profileRes.data
    if (ranksRes) myRanks.value = ranksRes.data
    if (rankingsRes) {
      const rows = Array.isArray(rankingsRes.data?.items) ? rankingsRes.data.items : []
      const me = rows.find((r: any) => r.player_id === profile.value?.id)
      compositeScore.value = me ? me.composite_score : null
    }
  } catch {
    showToast('加载失败')
  }
})

async function handleAvatarUpload(file: any) {
  const rawFile: File = file.file
  const formData = new FormData()
  formData.append('file', rawFile)
  try {
    const res = await api.post('/players/me/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    profile.value.avatar_url = res.data.avatar_url
    showToast('头像已更新')
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '上传失败')
  }
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.profile-page { padding-bottom: 60px; }
.export-date-input {
  width: 100%;
  min-height: 36px;
  border: 1px solid #d0d7de;
  border-radius: 8px;
  padding: 0 10px;
  background: #fff;
  color: #111827;
  box-sizing: border-box;
}

/* ─── HERO ─── */
.profile-hero {
  background: linear-gradient(135deg, #1a3a60 0%, #0d1f35 100%);
  padding: 20px 16px 16px;
  margin-bottom: 10px;
}
.profile-hero__top {
  display: flex; align-items: center; gap: 14px; margin-bottom: 14px;
}
.avatar-wrapper {
  position: relative; width: 72px; height: 72px; cursor: pointer; flex-shrink: 0;
}
.avatar-img {
  width: 72px; height: 72px; border-radius: 50%; object-fit: cover; border: 2px solid #2d6abf;
}
.avatar-placeholder {
  width: 72px; height: 72px; border-radius: 50%;
  background: #0f2035; border: 2px dashed #2d6abf;
  display: flex; align-items: center; justify-content: center;
}
.avatar-edit-badge {
  position: absolute; bottom: 0; right: 0;
  width: 22px; height: 22px; border-radius: 50%; background: #1677ff;
  display: flex; align-items: center; justify-content: center;
}
.profile-hero__info { flex: 1; min-width: 0; }
.hero-name { color: #eff6ff; font-size: 18px; font-weight: 700; margin-bottom: 6px; }
.hero-meta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.hero-jersey { color: #93c5fd; font-size: 13px; font-weight: 600; }
.hero-gender { font-weight: 700; font-size: 15px; }
.hero-rating { display: flex; align-items: baseline; gap: 4px; }
.hero-rating-val { color: #fbbf24; font-size: 28px; font-weight: 700; line-height: 1; }
.hero-rating-lbl { color: #7f95af; font-size: 11px; }
.profile-hero__actions { display: flex; gap: 8px; flex-wrap: wrap; }
.gender-m { color: #60a5fa; }
.gender-f { color: #f472b6; }

/* ─── 战绩统计 ─── */
.stats-section { background: #fff; padding: 12px 16px; margin-bottom: 10px; }
.stats-notice { font-size: 12px; color: #f59e0b; margin: 0 0 8px; text-align: center; }
.stats-row { display: flex; gap: 8px; }
.stat-chip {
  flex: 1; background: #f7f8fa; border-radius: 12px;
  display: flex; flex-direction: column; align-items: center;
  padding: 10px 4px 8px; gap: 3px;
}
.stat-chip strong { font-size: 22px; font-weight: 700; color: #1a1a1a; line-height: 1.1; }
.stat-chip span { font-size: 11px; color: #888; }
.stat-chip--wins strong { color: #16a34a; }
.stat-chip--goals strong { color: #dc2626; }
.stat-chip--assists strong { color: #7c3aed; }

/* ─── 排名区 ─── */
.rank-section { background: #fff; margin-bottom: 10px; }
.section-title-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px 6px; font-size: 14px; font-weight: 600; color: #111;
}
.section-subtitle { font-size: 12px; color: #999; font-weight: 400; }
.rank-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  border-top: 1px solid #f0f0f0;
}
.rank-item {
  padding: 10px 12px; cursor: pointer;
  border-right: 1px solid #f0f0f0; border-bottom: 1px solid #f0f0f0;
  transition: background .15s;
}
.rank-item:nth-child(3n) { border-right: none; }
.rank-item--active { background: #eff6ff; }
.rank-item__label { font-size: 11px; color: #888; margin-bottom: 3px; }
.rank-item__value { font-size: 13px; color: #333; }
.rank-item__value strong { font-size: 18px; color: #1677ff; font-weight: 700; }

/* ─── 功能入口 ─── */
.feature-section { background: #fff; margin-bottom: 10px; }
.feature-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 10px; padding: 8px 16px 16px;
}
.feature-btn {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 14px 8px; background: #f7f8fa; border-radius: 12px;
  cursor: pointer; transition: background .15s; font-size: 12px; font-weight: 500; color: #333;
}
.feature-btn:active { background: #e8f0fe; }
.feature-btn__icon { font-size: 22px; color: #1677ff; }
.feature-btn--admin .feature-btn__icon { color: #f59e0b; }

/* tabbar */
.tab-plus {
  width: 36px; height: 36px; border-radius: 50%;
  background: #3b82f6; color: #fff;
  font-size: 22px; line-height: 36px; text-align: center;
  font-weight: 700; margin: 0 auto; margin-bottom: -4px;
}
.tab-plus.active { background: #1d4ed8; }

/* 手册弹窗 — 使用 :deep() 确保 v-html 内注入元素的样式在 scoped CSS 下也能生效 */
.help-content {
  flex: 1; overflow-y: auto; padding: 16px;
  font-size: 14px; line-height: 1.8;
  color: #1a1a1a !important; background: #ffffff !important;
}
.help-content :deep(h1),
.help-content :deep(h2),
.help-content :deep(h3) { color: #1677ff !important; margin: 16px 0 8px; font-weight: 700; }
.help-content :deep(p) { margin: 8px 0; color: #1a1a1a !important; }
.help-content :deep(ul),
.help-content :deep(ol) { padding-left: 20px; }
.help-content :deep(li) { margin: 4px 0; color: #1a1a1a !important; }
.help-content :deep(code) { background: #f0f4f8 !important; color: #c7254e !important; padding: 2px 6px; border-radius: 4px; font-family: monospace; }
.help-content :deep(pre) { background: #f0f4f8 !important; padding: 12px; border-radius: 8px; overflow-x: auto; }
.help-content :deep(pre) :deep(code) { background: none !important; color: #1a1a1a !important; padding: 0; }
.help-content :deep(strong) { color: #1a1a1a !important; font-weight: 700; }
.help-content :deep(em) { color: #555 !important; }
.help-content :deep(br) { display: block; margin: 4px 0; }

/* ── Pad/PC 响应式优化 ── */
@media (min-width: 768px) {
  .profile-hero {
    padding: 28px 32px 24px;
  }
  .stats-section {
    padding: 16px 28px;
  }
  .stats-row {
    gap: 16px;
  }
  .stat-chip {
    padding: 16px 8px 14px;
    border-radius: 16px;
  }
  .stat-chip strong {
    font-size: 26px;
  }
  /* 排名网格：移动端 3 列 → Pad/PC 6 列 */
  .rank-grid {
    grid-template-columns: repeat(6, 1fr);
  }
  .rank-item:nth-child(3n) {
    border-right: 1px solid #f0f0f0;
  }
  .rank-item:nth-child(6n) {
    border-right: none;
  }
  /* 功能入口：移动端 3 列 → Pad 4 列 */
  .feature-grid {
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    padding: 8px 24px 20px;
  }
  .feature-btn {
    padding: 18px 10px;
    font-size: 13px;
  }
  .feature-btn__icon {
    font-size: 26px;
  }
}

@media (min-width: 1024px) {
  .profile-hero {
    padding: 32px 40px 28px;
  }
  /* 宽屏 5 列 */
  .feature-grid {
    grid-template-columns: repeat(5, 1fr);
  }
  /* 头像稍大 */
  .avatar-wrapper,
  .avatar-img,
  .avatar-placeholder {
    width: 88px;
    height: 88px;
  }
  .hero-rating-val {
    font-size: 34px;
  }
}
</style>
