<template>
  <div class="setup-page">
    <div class="logo-area">
      <h2>☀️ Solarc Ultimate</h2>
      <p>欢迎！请加入或创建你的队伍</p>
    </div>

    <!-- 已申请等待审核 -->
    <template v-if="isPending">
      <van-notice-bar
        left-icon="info-o"
        :text="auth.user?.role === 'owner'
          ? '你创建的队伍申请正在等待超级管理员审批，请联系超级管理员处理，审批通过后即可使用'
          : '你的入队申请正在审核中，请联系队伍管理员审批'"
        color="#1989fa"
        background="#ecf9ff"
        style="margin-bottom: 16px"
      />
      <van-cell-group inset>
        <van-cell title="账号" :value="auth.user?.username" />
        <van-cell title="申请状态" value="待审核" value-class="pending-text" />
      </van-cell-group>
      <div style="margin: 20px 16px 0">
        <van-button plain block @click="handleCancelApply">取消申请并退出队伍</van-button>
      </div>
    </template>

    <!-- 未加入任何队伍 -->
    <template v-else>
      <van-tabs v-model:active="activeTab" animated>
        <!-- 创建队伍 -->
        <van-tab title="创建新队伍">
          <div class="tab-content">
            <van-form @submit="handleCreate">
              <van-cell-group inset>
                <van-field
                  v-model="teamName"
                  label="队伍名称"
                  placeholder="2-50个字符"
                  :rules="[{ required: true, message: '请填写队伍名称' }]"
                />
                <!-- 队徽上传 -->
                <van-field label="队徽（可选）" :border="false">
                  <template #input>
                    <van-uploader
                      :after-read="onLogoSelected"
                      accept="image/*"
                      :preview-image="false"
                      :max-count="1"
                    >
                      <div class="logo-upload-btn">
                        <img v-if="logoPreview" :src="logoPreview" class="logo-preview" />
                        <template v-else>
                          <van-icon name="photo-o" size="24" color="#aaa" />
                          <span style="font-size:12px;color:#aaa;margin-top:4px">点击上传</span>
                        </template>
                      </div>
                    </van-uploader>
                  </template>
                </van-field>
              </van-cell-group>
              <div style="margin: 16px">
                <van-button round block type="primary" native-type="submit" :loading="creating">
                  创建队伍（成为主理人）
                </van-button>
              </div>
            </van-form>
          </div>
        </van-tab>

        <!-- 申请加入 -->
        <van-tab title="申请加入队伍">
          <div class="tab-content">
            <van-pull-refresh v-model="refreshing" @refresh="loadTeams">
              <van-list :loading="loading" finished-text="已加载全部">
                <van-empty
                  v-if="!loading && teams.length === 0"
                  description="暂无可加入的队伍"
                />
                <van-cell
                  v-for="team in teams"
                  :key="team.id"
                  :title="team.name"
                  :label="`${team.member_count} 名活跃成员`"
                >
                  <template #right-icon>
                    <van-button
                      size="small"
                      type="primary"
                      plain
                      :loading="joiningId === team.id"
                      @click="handleJoin(team.id, team.name)"
                    >
                      申请
                    </van-button>
                  </template>
                </van-cell>
              </van-list>
            </van-pull-refresh>
          </div>
        </van-tab>
      </van-tabs>
    </template>

    <div class="bottom-actions">
      <van-button plain size="small" @click="handleLogout">退出登录</van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const activeTab = ref(0)
const teamName = ref('')
const creating = ref(false)
const loading = ref(false)
const refreshing = ref(false)
const joiningId = ref<number | null>(null)
const teams = ref<{ id: number; name: string; member_count: number }[]>([])
const logoFile = ref<File | null>(null)
const logoPreview = ref<string | null>(null)

function onLogoSelected(file: any) {
  const raw: File = file.file
  logoFile.value = raw
  logoPreview.value = URL.createObjectURL(raw)
}

const isPending = computed(() => auth.isPending)

onMounted(() => {
  // 已经有队伍则直接跳走
  if (auth.hasTeam && !auth.isPending) {
    router.replace('/rankings')
    return
  }
  loadTeams()
})

async function loadTeams() {
  loading.value = true
  refreshing.value = false
  try {
    const res = await api.get('/team/available')
    teams.value = res.data
  } catch {
    showToast('获取队伍列表失败')
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  creating.value = true
  try {
    const res = await api.post('/team/create', { team_name: teamName.value })
    // 若选择了队徽则上传
    if (logoFile.value) {
      const fd = new FormData()
      fd.append('file', logoFile.value)
      await api.post('/team/logo', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    }
    await auth.fetchMe()
    if (res.data?.pending) {
      showToast('申请已提交，等待超级管理员审批')
    } else {
      showToast('队伍创建成功！')
      router.replace('/rankings')
    }
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '创建失败')
  } finally {
    creating.value = false
  }
}

async function handleJoin(teamId: number, teamDisplayName: string) {
  joiningId.value = teamId
  try {
    await api.post('/team/apply', { team_id: teamId })
    await auth.fetchMe()
    showToast(`已申请加入 "${teamDisplayName}"，等待审核`)
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '申请失败')
  } finally {
    joiningId.value = null
  }
}

async function handleCancelApply() {
  await showConfirmDialog({ title: '确认取消申请？', message: '取消后需重新申请' })
  try {
    await api.delete('/team/leave')
    await auth.fetchMe()
  } catch (e: any) {
    showToast(e.response?.data?.detail ?? '操作失败')
  }
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.setup-page {
  padding-bottom: 80px;
}
.logo-area {
  text-align: center;
  padding: 32px 16px 16px;
}
.logo-area h2 { margin: 0 0 8px; font-size: 24px; }
.logo-area p { color: #888; margin: 0; }
.tab-content {
  padding-top: 12px;
}
.pending-text {
  color: #ff976a;
}
.logo-upload-btn {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  border: 1.5px dashed #ddd;
  background: #fafafa;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  overflow: hidden;
}
.logo-preview {
  width: 64px;
  height: 64px;
  object-fit: cover;
  border-radius: 8px;
}
.bottom-actions {
  position: fixed;
  bottom: 20px;
  left: 0;
  right: 0;
  text-align: center;
}
</style>
