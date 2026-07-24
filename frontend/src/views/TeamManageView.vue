<template>
  <div class="team-manage-page">
    <van-nav-bar title="队伍管理" left-arrow @click-left="$router.back()" />

    <van-loading v-if="loading" type="spinner" vertical style="padding: 60px 0" />

    <template v-else>
      <!-- 队伍信息 -->
      <van-cell-group inset title="队伍信息">
        <!-- 队伍头像 -->
        <van-cell title="队伍头像">
          <template #value>
            <div v-if="isOwner" style="display: flex; align-items: center; gap: 12px; justify-content: flex-end">
              <div class="team-logo-preview">
                <img v-if="teamLogoUrl" :src="teamLogoUrl" class="team-logo-img" />
                <div v-else class="team-logo-placeholder">🦅</div>
              </div>
              <van-uploader :after-read="handleLogoUpload" accept="image/*" :max-count="1" :preview-image="false">
                <van-button size="mini" plain type="primary" :loading="uploadingLogo">{{ teamLogoUrl ? '更换' : '上传' }}</van-button>
              </van-uploader>
            </div>
            <div v-else style="display: flex; align-items: center; justify-content: flex-end">
              <div class="team-logo-preview">
                <img v-if="teamLogoUrl" :src="teamLogoUrl" class="team-logo-img" />
                <div v-else class="team-logo-placeholder">🦅</div>
              </div>
            </div>
          </template>
        </van-cell>
        <template v-if="!editingName">
          <van-cell title="队名" :value="teamName">
            <template #right-icon v-if="isOwner">
              <van-icon name="edit" color="#1677ff" style="cursor:pointer" @click="startEditName" />
            </template>
          </van-cell>
        </template>
        <template v-else>
          <van-field
            v-model="newTeamName"
            label="新队名"
            :maxlength="50"
            show-word-limit
            clearable
          />
          <div style="margin: 8px 16px; display: flex; gap: 8px">
            <van-button size="small" @click="editingName = false">取消</van-button>
            <van-button size="small" type="primary" :loading="savingName" @click="saveTeamName">
              保存
            </van-button>
          </div>
        </template>
        <van-cell title="当前人数" :value="`${activeMembers.length} 名队员`" />
      </van-cell-group>

      <!-- 待审批入队申请 -->
      <van-cell-group v-if="pendingApplications.length > 0" inset title="待审批入队申请">
        <van-cell
          v-for="app in pendingApplications"
          :key="app.id"
          :title="app.player_username"
          :label="app.join_reason ? `申请理由：${app.join_reason}` : '无申请理由'"
          :value="suggestedMuInfo ? `建议 μ: ${suggestedMuInfo.suggested_mu.toFixed(1)}` : ''"
        >
          <template #right-icon>
            <van-space>
              <van-button size="mini" type="success" @click="openApproveDialog(app.id)">通过</van-button>
              <van-button size="mini" type="danger" plain @click="rejectApplication(app.id)">拒绝</van-button>
            </van-space>
          </template>
        </van-cell>
      </van-cell-group>
      <van-cell-group v-else inset>
        <van-cell title="待审批入队申请" value="暂无" />
      </van-cell-group>

      <!-- 队员列表 -->
      <van-cell-group inset>
        <template #title>
          <div style="display:flex; align-items:center; justify-content:space-between; padding-right:8px">
            <span>队员列表</span>
            <van-button size="mini" type="primary" icon="plus" @click="openCreateDialog">新增队员</van-button>
          </div>
        </template>
        <van-empty v-if="activeMembers.length === 0" description="暂无队员" />
        <van-cell
          v-for="p in activeMembers"
          :key="p.id"
          :label="`@${p.username}  ·  σ ${p.sigma?.toFixed(2) ?? '-'}  ·  ${roleLabel(p.role)}`"
        >
          <template #title>
            <span>{{ p.display_name || p.username }}</span>
            <span v-if="p.jersey_number != null" class="jersey-tag">#{{ p.jersey_number }}</span>
          </template>
          <template #right-icon v-if="isAdmin && p.id !== currentUserId">
            <van-space size="4">
              <!-- 角色变更（owner/superadmin 可操作） -->
              <template v-if="isOwner || isSuperAdmin">
                <van-button
                  v-if="p.role === 'member'"
                  size="mini"
                  plain
                  type="primary"
                  @click="setRole(p.id, 'admin')"
                >
                  设管理
                </van-button>
                <van-button
                  v-else-if="p.role === 'admin'"
                  size="mini"
                  plain
                  @click="setRole(p.id, 'member')"
                >
                  取消管理
                </van-button>
                <span v-else style="color:#64748b; font-size:12px; padding:2px 4px">主理人</span>
              </template>
              <!-- 编辑信息 -->
              <van-button size="mini" plain icon="edit" @click="openEditDialog(p)">编辑</van-button>
              <!-- 退队（不能移出主理人） -->
              <van-button
                v-if="p.role !== 'owner'"
                size="mini"
                plain
                type="danger"
                @click="removeFromTeam(p.id, p.display_name || p.username)"
              >
                退队
              </van-button>
            </van-space>
          </template>
        </van-cell>
      </van-cell-group>
    </template>

    <!-- 新增队员弹窗 -->
    <van-popup v-model:show="showCreateDialog" position="bottom" round :style="{ maxHeight: '90vh', overflowY: 'auto' }">
      <div style="padding: 16px 16px 0; font-size: 16px; font-weight: 600; color: #1a1a1a">新增队员</div>
      <van-cell-group inset style="margin-top: 8px">
        <van-field
          v-model="createForm.username"
          label="账户名"
          placeholder="3-30位字母/数字/下划线"
          clearable
          :rules="[{ validator: validateUsername, message: '账户名格式不正确' }]"
        />
        <van-field
          v-model="createForm.display_name"
          label="显示名称"
          placeholder="可选，默认同账户名"
          clearable
        />
        <van-field
          v-model="createForm.email"
          label="邮箱"
          placeholder="可选"
          type="email"
          clearable
        />
        <van-field label="性别">
          <template #input>
            <van-radio-group v-model="createForm.gender" direction="horizontal">
              <van-radio name="male">男</van-radio>
              <van-radio name="female">女</van-radio>
            </van-radio-group>
          </template>
        </van-field>
        <van-field
          v-model="createForm.password"
          label="初始密码"
          placeholder="至少 6 位"
          type="password"
          clearable
        />
        <van-field
          v-model="createForm.jersey_number"
          label="球衣号码"
          placeholder="可选，0-999"
          type="digit"
          clearable
        />
      </van-cell-group>
      <div style="margin: 12px 16px 24px; display:flex; gap:8px">
        <van-button round block @click="showCreateDialog = false">取消</van-button>
        <van-button round block type="primary" :loading="saving" @click="submitCreate">确认新增</van-button>
      </div>
    </van-popup>

    <!-- 编辑队员弹窗 -->
    <van-popup v-model:show="showEditDialog" position="bottom" round :style="{ maxHeight: '90vh', overflowY: 'auto' }">
      <div style="padding: 16px 16px 0; font-size: 16px; font-weight: 600; color: #1a1a1a">
        编辑 {{ editForm.display_name || editForm.username }}
      </div>
      <van-cell-group inset style="margin-top: 8px">
        <van-field
          v-model="editForm.display_name"
          label="显示名称"
          clearable
        />
        <van-field
          v-model="editForm.email"
          label="邮箱"
          type="email"
          placeholder="留空则清除"
          clearable
        />
        <van-field label="性别">
          <template #input>
            <van-radio-group v-model="editForm.gender" direction="horizontal">
              <van-radio name="">不设置</van-radio>
              <van-radio name="M">男</van-radio>
              <van-radio name="F">女</van-radio>
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
      <div style="margin: 12px 16px 24px; display:flex; gap:8px">
        <van-button round block @click="showEditDialog = false">取消</van-button>
        <van-button round block type="primary" :loading="saving" @click="submitEdit">保存修改</van-button>
      </div>
    </van-popup>

    <van-dialog
      v-model:show="showApproveDialog"
      title="审核通过 - 设置初始 μ"
      show-cancel-button
      @confirm="confirmApprove"
    >
      <div style="padding: 16px;">
        <div v-if="suggestedMuInfo" style="margin-bottom: 12px; color: #666; font-size: 13px; line-height: 1.5;">
          建议值：<strong>{{ suggestedMuInfo.suggested_mu.toFixed(1) }}</strong>
          <span>
            （有效样本 {{ suggestedMuInfo.sample_count }} 人
            <span v-if="suggestedMuInfo.used_default">，样本不足，回退默认值 {{ suggestedMuInfo.fallback_mu.toFixed(1) }}</span>
            ）
          </span>
        </div>
        <van-field
          v-model="initialMuInput"
          label="初始 μ"
          type="number"
          placeholder="留空则使用建议值"
        />
        <div style="margin-top: 8px; color: #999; font-size: 12px;">
          可接受范围：10.0 ~ 40.0
        </div>
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { showToast, showConfirmDialog } from 'vant'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const isAdmin = auth.isAdmin
const isOwner = auth.isOwner
const isSuperAdmin = auth.isSuperAdmin
const currentUserId = auth.user?.id

interface MemberInfo {
  id: number
  username: string
  display_name: string | null
  role: string
  status: string
  sigma?: number
  email?: string | null
  gender?: string | null
  jersey_number?: number | null
}

const loading = ref(true)
const saving = ref(false)
interface ApplicationItem {
  id: number
  player_id: number
  player_username: string
  team_id: number
  join_reason: string | null
  status: string
  created_at: string
}

const activeMembers = ref<MemberInfo[]>([])
const pendingApplications = ref<ApplicationItem[]>([])
const teamName = ref('')
const teamLogoUrl = ref<string | null>(null)
const uploadingLogo = ref(false)
const editingName = ref(false)
const newTeamName = ref('')
const savingName = ref(false)

// 新增队员弹窗
const showCreateDialog = ref(false)
const createForm = ref({ username: '', display_name: '', email: '', password: '', gender: '', jersey_number: '' })

// 编辑队员弹窗
const showEditDialog = ref(false)
const editingPlayerId = ref<number | null>(null)
const editForm = ref({ username: '', display_name: '', email: '', gender: '', jersey_number: '' })

const showApproveDialog = ref(false)
const approvingApplicationId = ref<number | null>(null)
const initialMuInput = ref('')
const suggestedMuInfo = ref<{
  suggested_mu: number
  sample_count: number
  used_default: boolean
  fallback_mu: number
} | null>(null)

function unwrapApiData<T>(raw: any): T {
  if (raw && typeof raw === 'object' && 'code' in raw && 'data' in raw) {
    return raw.data as T
  }
  return raw as T
}

function roleLabel(role: string) {
  if (role === 'owner') return '主理人'
  if (role === 'admin') return '管理员'
  return '队员'
}

function validateUsername(val: string) {
  return /^[a-zA-Z0-9_]{3,30}$/.test(val)
}

async function loadData() {
  loading.value = true
  try {
    const [teamRes, activeRes, pendingRes] = await Promise.all([
      api.get('/team/my'),
      api.get('/players', { params: { status: 'active', page_size: 100 } }),
      api.get('/team-membership/applications/pending'),
    ])
    teamName.value = teamRes.data?.name ?? ''
    teamLogoUrl.value = teamRes.data?.logo_url ?? null
    activeMembers.value = activeRes.data ?? []
    const pendingRaw = unwrapApiData<ApplicationItem[]>(pendingRes.data)
    pendingApplications.value = Array.isArray(pendingRaw) ? pendingRaw : []
    await loadSuggestedMu()
  } catch {
    showToast('加载失败')
  } finally {
    loading.value = false
  }
}

async function loadSuggestedMu() {
  try {
    const res = await api.get('/team-membership/applications/suggested-mu')
    suggestedMuInfo.value = unwrapApiData(res.data)
  } catch {
    suggestedMuInfo.value = null
  }
}

function openApproveDialog(appId: number) {
  approvingApplicationId.value = appId
  initialMuInput.value = ''
  showApproveDialog.value = true
}

function parseInitialMuInput() {
  const raw = initialMuInput.value.trim()
  if (!raw) return undefined
  const parsed = Number(raw)
  if (Number.isNaN(parsed) || parsed < 10 || parsed > 40) {
    showToast('初始 μ 须在 10.0 ~ 40.0 之间')
    return null
  }
  return parsed
}

async function confirmApprove() {
  if (!approvingApplicationId.value) return
  const parsed = parseInitialMuInput()
  if (parsed === null) return false
  await approveApplication(approvingApplicationId.value, parsed)
  showApproveDialog.value = false
  approvingApplicationId.value = null
  initialMuInput.value = ''
  return true
}

function startEditName() {
  newTeamName.value = teamName.value
  editingName.value = true
}

async function saveTeamName() {
  if (!newTeamName.value.trim()) return
  savingName.value = true
  try {
    await api.put('/team/info', { team_name: newTeamName.value.trim() })
    teamName.value = newTeamName.value.trim()
    editingName.value = false
    showToast('队名已更新')
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '更新失败')
  } finally {
    savingName.value = false
  }
}

async function handleLogoUpload(file: any) {
  const rawFile: File = file.file
  const formData = new FormData()
  formData.append('file', rawFile)
  uploadingLogo.value = true
  try {
    const res = await api.post('/team/logo', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    teamLogoUrl.value = res.data.logo_url
    showToast('队伍头像已更新')
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '上传失败')
  } finally {
    uploadingLogo.value = false
  }
}

async function approveApplication(appId: number, initialMu?: number) {
  try {
    const payload: Record<string, any> = { action: 'approve' }
    if (typeof initialMu === 'number') payload.initial_mu = initialMu
    const resp = await api.post(`/team-membership/applications/${appId}/review`, payload)
    const data = unwrapApiData<{ initial_mu?: number }>(resp.data)
    pendingApplications.value = pendingApplications.value.filter(x => x.id !== appId)
    if (typeof data.initial_mu === 'number') {
      showToast(`已通过申请，初始 μ = ${data.initial_mu.toFixed(1)}`)
    } else {
      showToast('已通过申请')
    }
    await loadData()
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '操作失败')
  }
}

async function rejectApplication(appId: number) {
  try {
    await showConfirmDialog({ title: '确认拒绝', message: '拒绝后该用户需重新申请' })
    await api.post(`/team-membership/applications/${appId}/review`, { action: 'reject' })
    pendingApplications.value = pendingApplications.value.filter(x => x.id !== appId)
    showToast('已拒绝')
  } catch { /* user cancelled or error */ }
}

async function setRole(playerId: number, role: 'admin' | 'member') {
  try {
    await api.patch(`/players/${playerId}/role`, { role })
    const p = activeMembers.value.find(x => x.id === playerId)
    if (p) p.role = role
    showToast(role === 'admin' ? '已设为管理员' : '已降为普通队员')
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '操作失败')
  }
}

// ─── 新增队员 ───────────────────────────────────────────────────────────────
function openCreateDialog() {
  createForm.value = { username: '', display_name: '', email: '', password: '', gender: '', jersey_number: '' }
  showCreateDialog.value = true
}

async function submitCreate() {
  if (!createForm.value.username.trim()) {
    showToast('账户名不能为空')
    return
  }
  if (!validateUsername(createForm.value.username)) {
    showToast('账户名只能包含字母、数字和下划线，3-30 位')
    return
  }
  if (createForm.value.password.length < 6) {
    showToast('密码至少 6 位')
    return
  }
  saving.value = true
  try {
    const payload: Record<string, string | number | null> = {
      username: createForm.value.username.trim(),
      password: createForm.value.password,
    }
    if (createForm.value.display_name.trim()) payload.display_name = createForm.value.display_name.trim()
    if (createForm.value.email.trim()) payload.email = createForm.value.email.trim()
    if (createForm.value.gender) payload.gender = createForm.value.gender
    if (createForm.value.jersey_number.trim()) {
      const n = parseInt(createForm.value.jersey_number)
      if (!isNaN(n) && n >= 0 && n <= 999) payload.jersey_number = n
    }
    const res = await api.post('/players/admin-create', payload)
    activeMembers.value.push(res.data)
    showCreateDialog.value = false
    showToast({ message: '队员已创建', type: 'success' })
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '创建失败')
  } finally {
    saving.value = false
  }
}

// ─── 编辑队员信息 ────────────────────────────────────────────────────────────
function openEditDialog(p: MemberInfo) {
  editingPlayerId.value = p.id
  editForm.value = {
    username: p.username,
    display_name: p.display_name ?? '',
    email: p.email ?? '',
    gender: p.gender ?? '',
    jersey_number: p.jersey_number != null ? String(p.jersey_number) : '',
  }
  showEditDialog.value = true
}

async function submitEdit() {
  if (!editingPlayerId.value) return
  saving.value = true
  try {
    const payload: Record<string, string | number | null> = {
      display_name: editForm.value.display_name || null,
      email: editForm.value.email || null,
      gender: editForm.value.gender || '',
      jersey_number: editForm.value.jersey_number.trim() ? parseInt(editForm.value.jersey_number) : null,
    }
    const res = await api.put(`/players/${editingPlayerId.value}/admin-edit`, payload)
    const idx = activeMembers.value.findIndex(x => x.id === editingPlayerId.value)
    if (idx >= 0) {
      activeMembers.value[idx] = { ...activeMembers.value[idx], ...res.data }
    }
    showEditDialog.value = false
    showToast({ message: '信息已更新', type: 'success' })
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '更新失败')
  } finally {
    saving.value = false
  }
}

// ─── 退队 ────────────────────────────────────────────────────────────────────
async function removeFromTeam(playerId: number, name: string) {
  try {
    await showConfirmDialog({
      title: '确认退队',
      message: `将 ${name} 移出队伍？该操作不删除账号，历史比赛数据保留，但不再参与排名。`,
    })
    await api.delete(`/players/${playerId}/from-team`)
    activeMembers.value = activeMembers.value.filter(x => x.id !== playerId)
    showToast({ message: `${name} 已移出队伍`, type: 'success' })
  } catch (e: any) {
    if (e.response) showToast(e.response?.data?.detail ?? '操作失败')
    // 用户取消则忽略
  }
}

onMounted(loadData)
</script>

<style scoped>
.team-manage-page {
  padding-bottom: 40px;
  min-height: 100vh;
  background: #f7f8fa;
}

.jersey-tag {
  display: inline-block;
  margin-left: 6px;
  font-size: 11px;
  font-style: italic;
  font-weight: 600;
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
  border-radius: 4px;
  padding: 0 4px;
}

.team-logo-preview {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f3f4f6;
  font-size: 20px;
}

.team-logo-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.team-logo-placeholder {
  font-size: 20px;
  line-height: 1;
}
</style>
