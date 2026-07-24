<template>
  <div class="team-page">
    <van-nav-bar title="队伍" :right-text="isAdmin ? '管理' : ''" @click-right="isAdmin && $router.push('/team/manage')" />

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- 评论列表 -->
      <van-list
        v-model:loading="postsLoading"
        :finished="postsFinished"
        finished-text="没有更多了"
        @load="loadPosts"
      >
        <van-cell-group inset style="margin-top: 12px">
          <template v-for="post in posts" :key="post.id">
            <van-cell
              :title="post.author_name"
              :label="formatTime(post.created_at)"
            >
              <template #value>
                <div class="post-content">{{ post.content }}</div>
              </template>
              <template #right-icon>
                <div class="post-actions">
                  <van-icon
                    name="chat-o"
                    color="#1677ff"
                    style="cursor: pointer; margin-right: 8px"
                    @click.stop="startReply(post.id, post.author_name)"
                  />
                  <van-icon
                    v-if="canDelete(post)"
                    name="delete-o"
                    color="#f00"
                    style="cursor: pointer"
                    @click.stop="deletePost(post.id)"
                  />
                </div>
              </template>
            </van-cell>

            <!-- 回复列表 -->
            <van-cell
              v-for="reply in post.replies"
              :key="reply.id"
              class="reply-cell"
              :title="reply.author_name"
              :label="formatTime(reply.created_at)"
            >
              <template #value>
                <div class="post-content">{{ reply.content }}</div>
              </template>
              <template #right-icon>
                <van-icon
                  v-if="canDeleteReply(reply)"
                  name="delete-o"
                  color="#f00"
                  style="cursor: pointer"
                  @click.stop="deletePost(reply.id)"
                />
              </template>
            </van-cell>
          </template>
          <van-empty v-if="!postsLoading && posts.length === 0" description="暂无评论" />
        </van-cell-group>
      </van-list>
    </van-pull-refresh>

    <!-- 发布 / 回复输入框 -->
    <div class="post-input-bar">
      <div v-if="replyTo" class="reply-hint">
        回复 <strong>{{ replyTo.authorName }}</strong>
        <van-icon name="cross" style="margin-left: 4px; cursor: pointer" @click="cancelReply" />
      </div>
      <div class="post-input-row">
        <van-field
          v-model="newContent"
          :placeholder="replyTo ? '回复...' : '发表评论...'"
          :maxlength="2000"
          show-word-limit
          clearable
          class="post-field"
        />
        <van-button
          type="primary"
          size="small"
          :loading="posting"
          :disabled="!newContent.trim()"
          @click="submitPost"
        >
          {{ replyTo ? '回复' : '发布' }}
        </van-button>
      </div>
    </div>

    <!-- 底部导航 -->
    <van-tabbar route>
      <van-tabbar-item replace to="/home" icon="home-o">主页</van-tabbar-item>
      <van-tabbar-item replace to="/rankings" icon="chart-trending-o">排行榜</van-tabbar-item>
      <van-tabbar-item icon="plus" @click="$router.push('/matches/new')">
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
import { ref, onMounted } from 'vue'
import { showToast, showConfirmDialog } from 'vant'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const isAdmin = auth.isAdmin

interface Reply {
  id: number
  author_id: number
  author_name: string
  content: string
  parent_id: number
  created_at: string
}

interface Post {
  id: number
  author_id: number
  author_name: string
  content: string
  created_at: string
  replies: Reply[]
}

const posts = ref<Post[]>([])
const postsLoading = ref(false)
const postsFinished = ref(false)
const refreshing = ref(false)
let page = 1

const newContent = ref('')
const posting = ref(false)

// 回复状态
const replyTo = ref<{ postId: number; authorName: string } | null>(null)

function startReply(postId: number, authorName: string) {
  replyTo.value = { postId, authorName }
}

function cancelReply() {
  replyTo.value = null
  newContent.value = ''
}

function formatTime(dt: string) {
  const d = new Date(dt)
  return d.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function canDelete(post: Post) {
  return isAdmin || post.author_id === auth.user?.id
}

function canDeleteReply(reply: Reply) {
  return isAdmin || reply.author_id === auth.user?.id
}

async function loadPosts() {
  postsLoading.value = true
  try {
    const res = await api.get('/team/posts', { params: { page, page_size: 20 } })
    if (res.data.length < 20) postsFinished.value = true
    posts.value.push(...res.data)
    page++
  } catch {
    postsFinished.value = true
  } finally {
    postsLoading.value = false
    refreshing.value = false
  }
}

async function onRefresh() {
  page = 1
  posts.value = []
  postsFinished.value = false
  await loadPosts()
}

async function submitPost() {
  if (!newContent.value.trim()) return
  posting.value = true
  try {
    const payload: { content: string; parent_id?: number } = { content: newContent.value.trim() }
    if (replyTo.value) payload.parent_id = replyTo.value.postId

    const res = await api.post('/team/posts', payload)
    const data = res.data

    if (replyTo.value) {
      // 将回复插入对应顶层帖的 replies 数组
      const parent = posts.value.find(p => p.id === replyTo.value!.postId)
      if (parent) parent.replies.push(data)
      cancelReply()
    } else {
      posts.value.unshift({ ...data, replies: [] })
    }
    newContent.value = ''
    showToast('发布成功')
  } catch {
    showToast('发布失败')
  } finally {
    posting.value = false
  }
}

async function deletePost(id: number) {
  await showConfirmDialog({ title: '确认删除', message: '确定要删除这条内容吗？' })
  try {
    await api.delete(`/team/posts/${id}`)
    // 找并删除顶层帖或其回复
    const topIdx = posts.value.findIndex(p => p.id === id)
    if (topIdx >= 0) {
      posts.value.splice(topIdx, 1)
    } else {
      for (const post of posts.value) {
        const rIdx = post.replies.findIndex(r => r.id === id)
        if (rIdx >= 0) { post.replies.splice(rIdx, 1); break }
      }
    }
    showToast('已删除')
  } catch {
    showToast('删除失败')
  }
}

onMounted(loadPosts)
</script>

<style scoped>
.team-page {
  padding-bottom: calc(50px + env(safe-area-inset-bottom));
}
.tab-plus {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #3b82f6;
  color: #fff;
  font-size: 22px;
  line-height: 36px;
  text-align: center;
  font-weight: 700;
  margin: 0 auto;
  margin-bottom: -4px;
}
.tab-plus.active { background: #1d4ed8; }
.post-content {
  text-align: left;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  color: var(--van-text-color);
}
.post-actions {
  display: flex;
  align-items: center;
  margin-left: 8px;
}
.reply-cell {
  background: #f7f8fa;
  padding-left: 24px;
}
.post-input-bar {
  position: fixed;
  bottom: calc(50px + env(safe-area-inset-bottom));
  left: 0;
  right: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 12px;
  background: var(--van-background-2);
  border-top: 1px solid var(--van-border-color);
}
.reply-hint {
  font-size: 12px;
  color: #646566;
  padding: 0 4px;
}
.post-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.post-field {
  flex: 1;
}
</style>
