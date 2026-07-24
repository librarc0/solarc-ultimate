<template>
  <div class="admin-page">
    <van-nav-bar title="管理后台" left-text="返回我的" left-arrow @click-left="goBackToProfile" />

    <van-tabs v-model:active="activeTab" sticky>
      <!-- 成员审批 -->
      <van-tab title="成员审批" name="members">
        <!-- 超管未选队伍时的提示 -->
        <van-empty
          v-if="auth.isSuperAdmin && !auth.viewingTeamId"
          description="请先在「各队系数」中选择一支队伍，再查看待审批成员"
          style="padding: 40px 0"
        />
        <van-pull-refresh v-else v-model="refreshingMembers" @refresh="loadPendingMembers(true)">
          <van-list
            v-model:loading="loadingMembers"
            :finished="finishedMembers"
            finished-text="没有更多了"
            @load="loadPendingMembers"
          >
            <van-empty v-if="finishedMembers && pendingMembers.length === 0" description="暂无待审批成员" />
            <van-cell
              v-for="p in pendingMembers"
              :key="p._key"
              :title="p.display_name || p.username"
              :label="`@${p.username}${p.join_reason ? '  理由：' + p.join_reason : ''}  申请于 ${formatBeijingDate(p.created_at)}`"
            >
              <template #right-icon>
                <van-space>
                  <van-button size="mini" type="success" @click.stop="openApproveDialog(p)">批准</van-button>
                  <van-button size="mini" type="danger" plain @click.stop="rejectPlayer(p)">拒绝</van-button>
                </van-space>
              </template>
            </van-cell>
          </van-list>
        </van-pull-refresh>
      </van-tab>

      <!-- 算法系数（仅超级管理员通过「各队系数」管理，普通角色不可见） -->
      <van-tab v-if="false" title="算法系数" name="settings">
        <van-loading v-if="loadingSettings" type="spinner" style="padding: 30px; text-align: center" />
        <template v-else-if="settings">
          <!-- 系数说明卡 -->
          <van-cell-group inset style="margin-bottom:0">
            <van-cell title="📊 系数说明" label="点击可展开" is-link @click="showCoeffHelp = !showCoeffHelp" />
            <template v-if="showCoeffHelp">
              <van-cell v-for="item in coeffDescriptions" :key="item.name"
                :title="item.name"
                :label="item.desc"
                style="font-size:12px"
              />
            </template>
          </van-cell-group>
          <van-cell-group inset title="个人贡献加权">
            <van-field v-model="settingsForm.alpha" label="alpha" type="number" placeholder="贡献调整幅度 0~2" />
            <van-field v-model="settingsForm.beta" label="beta" type="number" placeholder="进球权重 0~2" />
            <van-field v-model="settingsForm.gamma" label="gamma" type="number" placeholder="助攻权重 0~2" />
            <van-field v-model="settingsForm.defense_weight" label="defense_weight" type="number" placeholder="防守/正负值权重 0~2" />
          </van-cell-group>
          <van-cell-group inset title="综合评分混合" style="margin-top:8px">
            <van-field v-model="settingsForm.composite_ts_weight" label="composite_ts_weight" type="number" placeholder="OpenSkill占比 0~1" />
            <van-field v-model="settingsForm.composite_perf_weight" label="composite_perf_weight" type="number" placeholder="表现占比 0~1" />
            <van-field v-model="settingsForm.composite_attendance_weight" label="composite_attendance_weight" type="number" placeholder="出勤加成占比 0~1（建议 0.02~0.05）" />
            <van-field v-model="settingsForm.perf_confidence_decay" label="perf_confidence_decay" type="number" placeholder="表现分场次置信衰减 N（默认 8.0）" />
          </van-cell-group>
          <van-cell-group inset title="特殊奖惩" style="margin-top:8px">
            <van-field v-model="settingsForm.turnover_penalty" label="turnover_penalty" type="number" placeholder="失误惩罚 0~2" />
            <van-field v-model="settingsForm.turnover_sigma_factor" label="turnover_sigma_factor" type="number" placeholder="失误sigma惩罚系数 0~2" />
            <van-field v-model="settingsForm.break_bonus_per_goal" label="break_bonus_per_goal" type="number" placeholder="Break奖励 0~2" />
            <van-field v-model="settingsForm.winner_floor_factor" label="winner_floor_factor" type="number" placeholder="胜者保底因子 0~1" />
          </van-cell-group>
          <van-cell-group inset title="外战参数" style="margin-top:8px">
            <van-field v-model="settingsForm.external_impact_multiplier" label="外战影响力倍率" type="number" placeholder="默认 1.0" />
            <van-field v-model="settingsForm.external_opp_mu_min" label="虚拟对手最弱μ" type="number" placeholder="强度=1时 默认15" />
            <van-field v-model="settingsForm.external_opp_mu_max" label="虚拟对手最强μ" type="number" placeholder="强度=10时 默认50" />
            <van-field v-model="settingsForm.external_opp_sigma" label="虚拟对手σ" type="number" placeholder="默认 6.0" />
          </van-cell-group>
          <van-cell-group inset title="化学值公式" style="margin-top:8px">
            <van-field v-model="settingsForm.chemistry_win_weight" label="胜率权重" type="number" placeholder="默认 0.7" />
            <van-field v-model="settingsForm.chemistry_combo_weight" label="配合率权重" type="number" placeholder="默认 0.3" />
          </van-cell-group>
          <van-cell-group inset title="算法 v2 参数" style="margin-top:8px">
            <van-field v-model="settingsForm.weight_cap" label="weight_cap" type="number" placeholder="贡献权重上限（默认 2.0）" />
            <van-field v-model="settingsForm.chemistry_decay_constant" label="chemistry_decay_constant" type="number" placeholder="化学值置信衰减常数（默认 8.0）" />
          </van-cell-group>
          <div style="margin: 16px">
            <van-button block type="primary" :loading="savingSettings" @click="saveSettings">
              保存系数
            </van-button>
          </div>
          <van-notice-bar
            wrapable
            :scrollable="false"
            text="修改系数仅影响「下一场」比赛，不重算历史记录。"
            color="#1989fa"
            background="#ecf9ff"
          />
        </template>
      </van-tab>

      <!-- 仅超级管理员：待审批队伍 -->
      <van-tab v-if="auth.isSuperAdmin" title="待审批队伍" name="pending-teams">
        <van-pull-refresh v-model="refreshingTeams" @refresh="loadPendingTeams(true)">
          <van-list
            v-model:loading="loadingTeams"
            :finished="finishedTeams"
            finished-text="没有更多了"
            @load="loadPendingTeams"
          >
            <van-empty v-if="finishedTeams && pendingTeams.length === 0" description="暂无待审批队伍" />
            <van-cell
              v-for="t in pendingTeams"
              :key="t.id"
              :title="t.name"
              :label="`主理人：${t.owner_display_name || t.owner_username}  申请于 ${formatBeijingDate(t.created_at)}`"
            >
              <template #right-icon>
                <van-space>
                  <van-button size="mini" type="success" @click.stop="approveTeam(t.id)">批准</van-button>
                  <van-button size="mini" type="danger" plain @click.stop="rejectTeam(t.id)">拒绝</van-button>
                </van-space>
              </template>
            </van-cell>
          </van-list>
        </van-pull-refresh>
      </van-tab>

      <!-- 仅超级管理员：各队算法系数 -->
      <van-tab v-if="auth.isSuperAdmin" title="各队系数" name="all-settings">
        <van-loading v-if="loadingAllTeams" type="spinner" style="padding: 30px; text-align: center" />
        <template v-else>
          <van-cell-group inset style="margin-bottom:0">
            <van-cell title="📊 系数说明" label="点击可展开" is-link @click="showCoeffHelp2 = !showCoeffHelp2" />
            <template v-if="showCoeffHelp2">
              <van-cell v-for="item in coeffDescriptions" :key="item.name"
                :title="item.name"
                :label="item.desc"
                style="font-size:12px"
              />
            </template>
          </van-cell-group>
          <van-notice-bar
            wrapable
            :scrollable="false"
            text="可为每支队伍独立设置算法系数，修改后仅影响该队伍的下一场比赛。"
            color="#ff976a"
            background="#fff7e6"
            style="margin-bottom: 8px"
          />
          <van-cell
            v-for="team in allTeams"
            :key="team.id"
            :title="team.name"
            :label="`${team.member_count} 名成员`"
            is-link
            @click="openTeamSettings(team)"
          >
            <template #right-icon>
              <span style="color: #999; font-size: 12px; margin-right: 6px">点击配置</span>
              <van-icon name="arrow" />
            </template>
          </van-cell>
        </template>
      </van-tab>

      <van-tab v-if="auth.isSuperAdmin" title="公告发布" name="broadcast">
        <div style="padding: 12px 16px 6px">
          <van-notice-bar
            wrapable
            :scrollable="false"
            text="支持给全部队伍或定向队伍发布平台公告，发布后成员会在首页通知中收到提醒。"
            color="#1989fa"
            background="#ecf9ff"
          />
        </div>
        <van-cell-group inset title="发布设置">
          <van-field label="发送范围">
            <template #input>
              <van-radio-group v-model="broadcastScope" direction="horizontal">
                <van-radio name="all">全部队伍</van-radio>
                <van-radio name="targeted">定向队伍</van-radio>
              </van-radio-group>
            </template>
          </van-field>
          <van-field v-if="broadcastScope === 'targeted'" label="选择队伍">
            <template #input>
              <van-checkbox-group v-model="broadcastTeamIds" direction="vertical" style="width: 100%">
                <van-checkbox v-for="team in allTeams" :key="team.id" :name="team.id" shape="square" style="margin-bottom: 6px">
                  {{ team.name }}（{{ team.member_count }} 人）
                </van-checkbox>
              </van-checkbox-group>
            </template>
          </van-field>
          <van-field
            v-model="broadcastContent"
            type="textarea"
            rows="5"
            label="公告内容"
            placeholder="请输入公告内容（最多 2000 字）"
            maxlength="2000"
            show-word-limit
          />
        </van-cell-group>
        <div style="margin: 16px">
          <van-button block type="primary" :loading="publishingBroadcast" @click="publishBroadcastNotice">
            发布公告
          </van-button>
        </div>
      </van-tab>

      <!-- 操作日志 Tab（仅超管） -->
      <van-tab v-if="auth.isSuperAdmin" title="操作日志" name="audit-logs">
        <div style="padding: 12px 16px 4px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center">
          <van-dropdown-menu style="flex: 1">
            <van-dropdown-item v-model="auditFilterTeamId" :options="auditTeamOptions" />
          </van-dropdown-menu>
          <van-dropdown-menu style="flex: 1">
            <van-dropdown-item v-model="auditFilterAction" :options="auditActionOptions" />
          </van-dropdown-menu>
          <van-button size="small" plain @click="showAuditDatePicker = true">{{ auditFilterDate || '选择日期' }}</van-button>
          <van-button size="small" plain @click="clearAuditDate">清空日期</van-button>
          <van-button size="small" type="primary" @click="loadAuditLogs(1)">查询</van-button>
        </div>
        <van-loading v-if="loadingAuditLogs" type="spinner" style="padding: 30px; text-align: center" />
        <template v-else>
          <van-cell
            v-for="log in auditLogs"
            :key="log.id"
            :label="`${formatBeijingDateTime(log.created_at)} · ${log.actor_username}`"
          >
            <template #title>
              <span :class="`audit-action audit-action--${log.action.split('_')[0]}`">{{ getAuditActionLabel(log.action) }}</span>
              <span v-if="log.target_type" style="color: #999; font-size: 12px; margin-left: 6px">→ {{ log.target_type }} #{{ log.target_id }}</span>
              <span v-if="log.detail && log.detail['notes']" style="color: #f59e0b; font-size: 12px; margin-left: 8px">「{{ log.detail['notes'] }}」</span>
            </template>
            <template #value>
              <span v-if="log.detail" style="font-size: 11px; color: #999">{{ formatAuditDetail(log.detail) }}</span>
            </template>
          </van-cell>
          <van-empty v-if="auditLogs.length === 0" description="暂无日志" />
          <div v-if="auditTotalPages > 1" style="padding: 8px 16px; display: flex; justify-content: center; gap: 8px">
            <van-button size="small" :disabled="auditPage <= 1" @click="loadAuditLogs(auditPage - 1)">上一页</van-button>
            <span style="line-height: 32px; font-size: 12px; color: #999">{{ auditPage }} / {{ auditTotalPages }}</span>
            <van-button size="small" :disabled="auditPage >= auditTotalPages" @click="loadAuditLogs(auditPage + 1)">下一页</van-button>
          </div>
        </template>
      </van-tab>

      <!-- 赛季管理 -->
      <van-tab title="🗂️ 赛季" name="seasons">
        <div style="padding: 48px 16px 32px; display:flex; flex-direction:column; align-items:center; gap:14px">
          <van-icon name="clock-o" size="52" color="#c8c9cc" />
          <div style="font-size:16px; font-weight:600; color:#323233">赛季管理</div>
          <van-tag type="warning" size="large">🚧 开发中</van-tag>
          <div style="font-size:13px; color:#969799; text-align:center; max-width:280px; line-height:1.7">
            赛季管理功能正在开发中，敬请期待。<br>
            此功能将支持按赛季隔离评分历史、球员数据与进步榜排名。
          </div>
        </div>
      </van-tab>

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
    </van-tabs>

    <!-- 创建赛季多步骤弹窗 -->
    <van-popup v-model:show="showCreateSeasonWizard" position="bottom" round style="padding:16px 0 32px">
      <div style="padding: 0 16px">
        <div style="font-size:16px; font-weight:600; margin-bottom:16px; text-align:center">
          创建新赛季（步骤 {{ wizardStep }}/4）
        </div>

        <!-- Step 1: 年份滚动选择 -->
        <template v-if="wizardStep === 1">
          <p style="font-size:13px; color:#94a3b8; margin-bottom:8px; text-align:center">选择新赛季年份</p>
          <van-picker
            :columns="yearPickerColumns"
            :model-value="[String(wizardYear)]"
            @change="(picker: any, values: string[]) => { wizardYear = Number(values[0]) }"
            style="margin-bottom:12px; border-radius:8px; overflow:hidden"
            :show-toolbar="false"
            visible-option-num="5"
          />
          <van-button block type="primary" @click="wizardStep = 2">下一步</van-button>
        </template>

        <!-- Step 2: 是否同步评分 -->
        <template v-else-if="wizardStep === 2">
          <van-cell-group inset style="margin-bottom:12px">
            <van-cell title="同步当前评分到新赛季" label="开启：球员携带现有 mu/sigma 开始新赛季；关闭：重置为初始值">
              <template #right-icon>
                <van-switch v-model="wizardSyncRatings" />
              </template>
            </van-cell>
          </van-cell-group>
          <van-button block style="margin-bottom:8px" @click="wizardStep = 1">上一步</van-button>
          <van-button block type="primary" @click="wizardStep = 3">下一步</van-button>
        </template>

        <!-- Step 3: 选择新赛季成员 -->
        <template v-else-if="wizardStep === 3">
          <p style="font-size:13px; color:#94a3b8; margin-bottom:8px">
            选择加入新赛季的成员（当前活跃成员均已默认选中）
          </p>
          <van-checkbox-group v-model="wizardSelectedMemberIds" style="max-height:300px; overflow-y:auto; margin-bottom:12px">
            <van-cell
              v-for="m in wizardMembers" :key="m.id"
              :title="m.display_name || m.username"
              :label="`@${m.username}`"
              clickable
              @click="() => {
                const idx = wizardSelectedMemberIds.indexOf(m.id)
                if (idx >= 0) wizardSelectedMemberIds.splice(idx, 1)
                else wizardSelectedMemberIds.push(m.id)
              }"
            >
              <template #right-icon>
                <van-checkbox :name="m.id" @click.stop />
              </template>
            </van-cell>
          </van-checkbox-group>
          <van-button block style="margin-bottom:8px" @click="wizardStep = 2">上一步</van-button>
          <van-button block type="primary" @click="wizardStep = 4">下一步</van-button>
        </template>

        <!-- Step 4: 确认 -->
        <template v-else-if="wizardStep === 4">
          <van-cell-group inset style="margin-bottom:12px">
            <van-cell title="赛季年份" :value="`${wizardYear} 年`" />
            <van-cell title="评分同步" :value="wizardSyncRatings ? '是（携带现有评分）' : '否（重置为初始值）'" />
            <van-cell title="参与人数" :value="`${wizardSelectedMemberIds.length} 名队员`" />
          </van-cell-group>
          <van-notice-bar color="#f59e0b" background="#1a1a2e" wrapable :scrollable="false"
            text="创建后，旧赛季将变为历史只读，系统自动切换到新赛季。此操作不可撤销。" />
          <van-button block style="margin:12px 0 8px" @click="wizardStep = 3">上一步</van-button>
          <van-button block type="danger" :loading="wizardSubmitting" @click="submitCreateSeason">
            确认创建 {{ wizardYear }} 赛季
          </van-button>
        </template>
      </div>
    </van-popup>

    <van-popup v-model:show="showAuditDatePicker" position="bottom">
      <van-date-picker
        v-model="auditDateParts"
        title="选择日志日期"
        @confirm="onAuditDateConfirm"
        @cancel="showAuditDatePicker = false"
      />
    </van-popup>

    <!-- 队伍算法系数弹窗 -->
    <van-popup
      v-model:show="showTeamSettingsPopup"
      position="center"
      round
      :style="{ width: 'min(860px, 96vw)', maxHeight: '92vh', overflowY: 'auto' }"
    >
      <div class="popup-inner">
        <van-nav-bar
          :title="`${editingTeam?.name} · 算法系数`"
          left-text="取消"
          @click-left="showTeamSettingsPopup = false"
        />
        <van-loading v-if="loadingTeamSettings" type="spinner" style="padding: 30px; text-align: center" />
        <template v-else>
          <van-notice-bar
            v-if="settingsTeamObject"
            wrapable
            :scrollable="false"
            :text="`{ id: ${settingsTeamObject.id}, name: '${settingsTeamObject.name}', members: ${settingsTeamObject.member_count} }`"
            color="#1989fa"
            background="#ecf9ff"
            style="margin: 8px 12px"
          />
          <div class="popup-grid">
            <div class="param-group">
              <div class="param-group__title">个人贡献加权</div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.alpha }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('alpha')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.alpha" type="number" />
                  </div>
                  <div v-if="expandedFields.has('alpha')" class="coeff-desc">{{ coeffFieldDesc['alpha'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.beta }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('beta')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.beta" type="number" />
                  </div>
                  <div v-if="expandedFields.has('beta')" class="coeff-desc">{{ coeffFieldDesc['beta'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.gamma }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('gamma')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.gamma" type="number" />
                  </div>
                  <div v-if="expandedFields.has('gamma')" class="coeff-desc">{{ coeffFieldDesc['gamma'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.defense_weight }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('defense_weight')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.defense_weight" type="number" />
                  </div>
                  <div v-if="expandedFields.has('defense_weight')" class="coeff-desc">{{ coeffFieldDesc['defense_weight'] }}</div>
                </div>
            </div>
            <div class="param-group">
              <div class="param-group__title">综合评分混合</div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.composite_ts_weight }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('composite_ts_weight')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.composite_ts_weight" type="number" />
                  </div>
                  <div v-if="expandedFields.has('composite_ts_weight')" class="coeff-desc">{{ coeffFieldDesc['composite_ts_weight'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.composite_perf_weight }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('composite_perf_weight')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.composite_perf_weight" type="number" />
                  </div>
                  <div v-if="expandedFields.has('composite_perf_weight')" class="coeff-desc">{{ coeffFieldDesc['composite_perf_weight'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.composite_attendance_weight }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('composite_attendance_weight')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.composite_attendance_weight" type="number" />
                  </div>
                  <div v-if="expandedFields.has('composite_attendance_weight')" class="coeff-desc">{{ coeffFieldDesc['composite_attendance_weight'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.perf_confidence_decay }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('perf_confidence_decay')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.perf_confidence_decay" type="number" />
                  </div>
                  <div v-if="expandedFields.has('perf_confidence_decay')" class="coeff-desc">{{ coeffFieldDesc['perf_confidence_decay'] }}</div>
                </div>
            </div>
            <div class="param-group">
              <div class="param-group__title">失误惩罚 & 基础奖励</div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.turnover_penalty }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('turnover_penalty')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.turnover_penalty" type="number" />
                  </div>
                  <div v-if="expandedFields.has('turnover_penalty')" class="coeff-desc">{{ coeffFieldDesc['turnover_penalty'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.break_bonus_per_goal }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('break_bonus_per_goal')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.break_bonus_per_goal" type="number" />
                  </div>
                  <div v-if="expandedFields.has('break_bonus_per_goal')" class="coeff-desc">{{ coeffFieldDesc['break_bonus_per_goal'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.winner_floor_factor }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('winner_floor_factor')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.winner_floor_factor" type="number" />
                  </div>
                  <div v-if="expandedFields.has('winner_floor_factor')" class="coeff-desc">{{ coeffFieldDesc['winner_floor_factor'] }}</div>
                </div>
            </div>
            <div class="param-group">
              <div class="param-group__title">特殊飞盘事件奖励</div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.universal_point_bonus }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('universal_point_bonus')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.universal_point_bonus" type="number" />
                  </div>
                  <div v-if="expandedFields.has('universal_point_bonus')" class="coeff-desc">{{ coeffFieldDesc['universal_point_bonus'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.block_mu_bonus }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('block_mu_bonus')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.block_mu_bonus" type="number" />
                  </div>
                  <div v-if="expandedFields.has('block_mu_bonus')" class="coeff-desc">{{ coeffFieldDesc['block_mu_bonus'] }}</div>
                </div>
            </div>
            <div class="param-group">
              <div class="param-group__title">连续失误加重惩罚</div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.consecutive_turnover_threshold }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('consecutive_turnover_threshold')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.consecutive_turnover_threshold" type="number" />
                  </div>
                  <div v-if="expandedFields.has('consecutive_turnover_threshold')" class="coeff-desc">{{ coeffFieldDesc['consecutive_turnover_threshold'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.consecutive_turnover_multiplier }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('consecutive_turnover_multiplier')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.consecutive_turnover_multiplier" type="number" />
                  </div>
                  <div v-if="expandedFields.has('consecutive_turnover_multiplier')" class="coeff-desc">{{ coeffFieldDesc['consecutive_turnover_multiplier'] }}</div>
                </div>
            </div>
            <div class="param-group">
              <div class="param-group__title">外战参数</div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.external_impact_multiplier }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('external_impact_multiplier')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.external_impact_multiplier" type="number" />
                  </div>
                  <div v-if="expandedFields.has('external_impact_multiplier')" class="coeff-desc">{{ coeffFieldDesc['external_impact_multiplier'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.external_opp_mu_min }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('external_opp_mu_min')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.external_opp_mu_min" type="number" />
                  </div>
                  <div v-if="expandedFields.has('external_opp_mu_min')" class="coeff-desc">{{ coeffFieldDesc['external_opp_mu_min'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.external_opp_mu_max }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('external_opp_mu_max')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.external_opp_mu_max" type="number" />
                  </div>
                  <div v-if="expandedFields.has('external_opp_mu_max')" class="coeff-desc">{{ coeffFieldDesc['external_opp_mu_max'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.external_opp_sigma }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('external_opp_sigma')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.external_opp_sigma" type="number" />
                  </div>
                  <div v-if="expandedFields.has('external_opp_sigma')" class="coeff-desc">{{ coeffFieldDesc['external_opp_sigma'] }}</div>
                </div>
            </div>
            <div class="param-group">
              <div class="param-group__title">OpenSkill 模型参数</div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.openskill_mu }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('openskill_mu')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.openskill_mu" type="number" />
                  </div>
                  <div v-if="expandedFields.has('openskill_mu')" class="coeff-desc">{{ coeffFieldDesc['openskill_mu'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.openskill_sigma }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('openskill_sigma')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.openskill_sigma" type="number" />
                  </div>
                  <div v-if="expandedFields.has('openskill_sigma')" class="coeff-desc">{{ coeffFieldDesc['openskill_sigma'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.openskill_beta }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('openskill_beta')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.openskill_beta" type="number" />
                  </div>
                  <div v-if="expandedFields.has('openskill_beta')" class="coeff-desc">{{ coeffFieldDesc['openskill_beta'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.openskill_tau }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('openskill_tau')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.openskill_tau" type="number" />
                  </div>
                  <div v-if="expandedFields.has('openskill_tau')" class="coeff-desc">{{ coeffFieldDesc['openskill_tau'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.openskill_kappa }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('openskill_kappa')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.openskill_kappa" type="number" />
                  </div>
                  <div v-if="expandedFields.has('openskill_kappa')" class="coeff-desc">{{ coeffFieldDesc['openskill_kappa'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.openskill_margin }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('openskill_margin')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.openskill_margin" type="number" />
                  </div>
                  <div v-if="expandedFields.has('openskill_margin')" class="coeff-desc">{{ coeffFieldDesc['openskill_margin'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.openskill_limit_sigma }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('openskill_limit_sigma')">？</span>
                    <van-switch
                    :model-value="editSettingsForm.openskill_limit_sigma === 'true'"
                    @update:model-value="editSettingsForm.openskill_limit_sigma = $event ? 'true' : 'false'"
                    size="18px"
                  />
                  </div>
                  <div v-if="expandedFields.has('openskill_limit_sigma')" class="coeff-desc">{{ coeffFieldDesc['openskill_limit_sigma'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.openskill_balance }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('openskill_balance')">？</span>
                    <van-switch
                    :model-value="editSettingsForm.openskill_balance === 'true'"
                    @update:model-value="editSettingsForm.openskill_balance = $event ? 'true' : 'false'"
                    size="18px"
                  />
                  </div>
                  <div v-if="expandedFields.has('openskill_balance')" class="coeff-desc">{{ coeffFieldDesc['openskill_balance'] }}</div>
                </div>
            </div>
            <div class="param-group">
              <div class="param-group__title">化学值公式</div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.chemistry_win_weight }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('chemistry_win_weight')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.chemistry_win_weight" type="number" />
                  </div>
                  <div v-if="expandedFields.has('chemistry_win_weight')" class="coeff-desc">{{ coeffFieldDesc['chemistry_win_weight'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.chemistry_combo_weight }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('chemistry_combo_weight')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.chemistry_combo_weight" type="number" />
                  </div>
                  <div v-if="expandedFields.has('chemistry_combo_weight')" class="coeff-desc">{{ coeffFieldDesc['chemistry_combo_weight'] }}</div>
                </div>
            </div>
            <div class="param-group">
              <div class="param-group__title">算法 v2 参数</div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.weight_cap }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('weight_cap')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.weight_cap" type="number" />
                  </div>
                  <div v-if="expandedFields.has('weight_cap')" class="coeff-desc">{{ coeffFieldDesc['weight_cap'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key">{{ coeffLabel.chemistry_decay_constant }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('chemistry_decay_constant')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.chemistry_decay_constant" type="number" />
                  </div>
                  <div v-if="expandedFields.has('chemistry_decay_constant')" class="coeff-desc">{{ coeffFieldDesc['chemistry_decay_constant'] }}</div>
                </div>
            </div>
            <div class="param-group param-group--deprecated">
              <div class="param-group__title">⚠️ 已废弃（v2 不生效）</div>
              <div class="param-group__note">sigma 由 OpenSkill 贝叶斯管理，以下字段仅保留向后兼容，修改无效。</div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key" style="text-decoration:line-through;opacity:.55">{{ coeffLabel.sigma_bonus_factor }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('sigma_bonus_factor')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.sigma_bonus_factor" type="number" />
                  </div>
                  <div v-if="expandedFields.has('sigma_bonus_factor')" class="coeff-desc">{{ coeffFieldDesc['sigma_bonus_factor'] }}</div>
                </div>
                <div class="param-row">
                  <div class="param-name-line">
                    <span class="param-key" style="text-decoration:line-through;opacity:.55">{{ coeffLabel.turnover_sigma_factor }}</span>
                    <span class="help-btn" @click.stop="toggleFieldHelp('turnover_sigma_factor')">？</span>
                    <input class="param-value-input" v-model="editSettingsForm.turnover_sigma_factor" type="number" />
                  </div>
                  <div v-if="expandedFields.has('turnover_sigma_factor')" class="coeff-desc">{{ coeffFieldDesc['turnover_sigma_factor'] }}</div>
                </div>
            </div>
          </div>
          <div
            v-if="invalidSettingMessages.length"
            style="margin: 0 12px 8px; padding: 10px 12px; border: 1px solid #ffb8b8; background: #fff5f5; border-radius: 8px; color: #c53030; font-size: 12px; line-height: 1.5"
          >
            <div style="font-weight: 600; margin-bottom: 4px">
              发现 {{ invalidSettingMessages.length }} 项参数超出范围，已禁止重算：
            </div>
            <div v-for="msg in invalidSettingMessages.slice(0, 5)" :key="msg">- {{ msg }}</div>
            <div v-if="invalidSettingMessages.length > 5">… 另 {{ invalidSettingMessages.length - 5 }} 项</div>
          </div>
          <div class="popup-actions">
            <van-button block type="warning" plain :loading="resettingTeamSettings" @click="resetTeamSettings">重置为默认系数</van-button>
            <van-button block type="danger" plain :loading="savingTeamSettings || reratingTeam" :disabled="savingTeamSettings || reratingTeam || invalidSettingMessages.length > 0" @click="rerateEditingTeam">
              <template v-if="reratingTeam">{{ rerateMessage || '重算中…' }}（{{ rerateProgress }}%）</template>
              <template v-else-if="savingTeamSettings">保存中…</template>
              <template v-else-if="invalidSettingMessages.length > 0">请先修正越界参数</template>
              <template v-else>刷新（保存并按当前系数重算历史比赛）</template>
            </van-button>
            <van-progress v-if="reratingTeam" :percentage="rerateProgress" stroke-width="4" style="margin-top:4px" />
          </div>
        </template>
      </div>
    </van-popup>

    <!-- Bottom nav -->
    <van-tabbar route>
      <van-tabbar-item replace to="/rankings" icon="chart-trending-o">排行</van-tabbar-item>
      <van-tabbar-item replace to="/profile" icon="user-o">我的</van-tabbar-item>
      <van-tabbar-item replace to="/matches/new" icon="plus">录入</van-tabbar-item>
      <van-tabbar-item replace to="/matches/list" icon="records-o">比赛</van-tabbar-item>
      <van-tabbar-item replace to="/admin" icon="setting-o">管理</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { showToast } from 'vant'
import api from '@/api'
import { useAdminAuditLogs } from '@/composables/useAdminAuditLogs'
import { useAdminMembers, type PendingItem } from '@/composables/useAdminMembers'
import { useAdminTeamOps } from '@/composables/useAdminTeamOps'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const isOwner = auth.isOwner
const router = useRouter()

function normalizeUtcInput(value: string): string {
  if (!value) return ''
  return /Z|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`
}

function formatBeijingDate(value: string): string {
  const normalized = normalizeUtcInput(value)
  if (!normalized) return '-'
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date).replace(/\//g, '-')
}

function formatBeijingDateTime(value: string): string {
  const normalized = normalizeUtcInput(value)
  if (!normalized) return '-'
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return value
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
  const get = (type: string) => parts.find(p => p.type === type)?.value ?? '00'
  return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}:${get('second')} (北京时间)`
}

function goBackToProfile() {
  router.push('/profile')
}

const activeTab = ref('members')

// 切换到审计日志 Tab 时自动加载
watch(activeTab, (val) => {
  if (val === 'audit-logs' && auth.isSuperAdmin && auditLogs.value.length === 0) {
    loadAuditLogs(1)
  }
  if (val === 'seasons') {
    loadSeasons()
  }
})

// 系数说明
const showCoeffHelp = ref(false)
const showCoeffHelp2 = ref(false)
const showCoeffHelp3 = ref(false)
// per-field expandable help in the settings popup
const expandedFields = ref<Set<string>>(new Set())
function toggleFieldHelp(field: string) {
  const s = new Set(expandedFields.value)
  if (s.has(field)) { s.delete(field) } else { s.add(field) }
  expandedFields.value = s
}
// build a lookup map from coeffDescriptions for the popup

const coeffDescriptions = [
  // ── 个人贡献加权（对应算法参数 10.2）────────────────────────────────────
  {
    name: 'alpha — 贡献差异放大系数',
    desc: '控制高贡献者和低贡献者之间涨分差距的放大幅度。默认 0.3，范围 0~2。\n• alpha=0：贡献数据不影响涨分，纯看胜负\n• alpha=0.3（默认）：进5球 vs 0球有明显但温和的差距\n• alpha≥1.0：差距显著拉大，核心球员大幅领先\n队伍人数越多，梯度效果越明显（建议5人以上队伍使用）。',
  },
  {
    name: 'beta — 进球贡献权重',
    desc: '表现分计算中进球数的权重。默认 0.6，仅在 Level 2/3 比赛中生效。\n进球比助攻更难，因此默认 beta（0.6）高于 gamma（0.4）。\n• 想更重视射手型球员：上调 beta（如 0.8）\n• 想平衡进球与传球的价值：降低 beta 至 0.5，同时上调 gamma\n建议保持 beta/gamma ≈ 1.5 的比例（如 0.6/0.4、0.9/0.6）。',
  },
  {
    name: 'gamma — 助攻贡献权重',
    desc: '表现分计算中助攻数的权重。默认 0.4，仅在 Level 2/3 比赛中生效。\n• 队伍重视传球组织、战术组织者（handler）：上调至 0.5~0.6\n• 提高 gamma 会让传球型球员在综合榜中排名更靠前\n调整时建议同步调整 beta，保持两者比例合理。',
  },
  {
    name: 'defense_weight — 防守次数贡献权重',
    desc: '表现分计算中场均防守次数（总防守次数/总场次）的权重。默认 0.1，仅在 Level 3 比赛中生效。\n防守次数指录入的成功拦截、贴防到位等防守事件总次数。\n• 默认较小（0.1），防止防守数据不完整时影响公平性\n• 防守数据录入准确完整时可适当上调至 0.15~0.3，奖励积极防守球员\n⚠️ 此字段不是"正负值（+/-）"，仅用于统计防守事件次数。',
  },
  // ── 综合评分混合（对应算法参数 10.3）────────────────────────────────────
  {
    name: 'composite_ts_weight — OpenSkill 保守战力分权重',
    desc: '综合排行榜中"保守战力分"的占比。默认 0.85（85%）。\n保守战力分 = max(0，50 + μ - 3σ)，代表球员经过多场比赛沉淀的技术下限，是综合榜的核心锚。\n• 降低此值：让近期表现和出勤对排名产生更大影响\n• 提高此值：排名更依赖长期积累，短期波动影响更小\n通常不需要调整，除非需要弱化历史积分的主导作用。',
  },
  {
    name: 'composite_perf_weight — 近期表现分权重',
    desc: '综合排行榜中"近期赛事表现指数"（场均进球/助攻/防守/失误换算）的占比。默认 0.15（15%）。\n• 提高到 0.2~0.3：近期状态好的球员更容易超越历史积分高但近期参赛少的球员\n• 适合短赛季或希望排名反映近期状态的队伍\n注意：此分数受「表现分场次置信折扣」保护，场次太少的球员不会因几场高数据异常靠前。',
  },
  {
    name: 'composite_attendance_weight — 出勤加成权重',
    desc: '综合排行榜中训练+比赛出勤率的加成系数。默认 0（不启用）。\n• 建议从 0.02~0.05 开始试验，作为轻量出勤激励\n• 设置过高（如 0.2+）会让出勤主导排名，掩盖技术差距\n⚠️ 须出勤模块完整接入才能生效；若出勤未录入，所有人出勤率相同，此项无效果。',
  },
  // ── 特殊事件奖惩（对应算法参数 10.4）────────────────────────────────────
  {
    name: 'turnover_penalty — 失误 mu 惩罚/次',
    desc: '每次失误（Turnover）扣减的球员 mu 值。默认 0.2。\n例：单场 3 次失误 → 扣 0.6 mu（一场普通比赛涨分约 +2.0，失误成本约 30%）。\n• 觉得惩罚过重：降至 0.1\n• 想强力引导减少失误：升至 0.3~0.4\n配合「连续失误阈值」和「超阈值倍率」可实现"前几次宽容、后续加重"的分级惩罚。',
  },
  {
    name: 'break_bonus_per_goal — Break 进球 mu 奖励/次',
    desc: '每个 Break 进球（防守方发起进攻并得分，即"防反得分"）的额外 mu 奖励。默认 0.1。\nBreak 是飞盘中难度最高的得分方式，需在防守端发动进攻并完成连贯配合。\n• 重视攻防转换战术的队伍可调高至 0.2~0.3\n⚠️ 仅在比赛中录入了 is_break=true 事件时生效。',
  },
  {
    name: 'winner_floor_factor — 胜者最低涨分保底',
    desc: '⚠️ v2 已废弃（保留字段，不参与计算）。当前引擎使用 OpenSkill 原生 weights 分配贡献，不再额外应用“胜者保底”。\n修改该值不会改变实际评分结果，仅用于兼容旧数据结构。',
  },
  {
    name: 'universal_point_bonus — Universe Point mu 奖励',
    desc: 'Universe Point（UP，全场比赛最后一分，双方到达赛制终点后的决胜分）事件的额外 mu 奖励。默认 0.5。\nUP 是心理压力最大的时刻，奖励旨在表彰关键时刻稳定发挥的球员。\n0.5 约等于普通进球奖励的 2~3 倍，可按队伍对"关键时刻表现"的重视程度调整。\n⚠️ 仅在录入了 is_universe_point=true 的比赛事件时生效。',
  },
  {
    name: 'block_mu_bonus — Block 防守 mu 奖励/次',
    desc: '每次 Block（在防守端成功拦截对方传球或接球）奖励的 mu。默认 0.05。\n默认较小，防止激励冒险防守（冒险贴防容易造成判罚）。Block 数据录入准确完整时可适当调高至 0.1~0.2。\n⚠️ 仅在录入了 event_type="block" 的比赛事件时生效。',
  },
  {
    name: 'consecutive_turnover_threshold — 连续失误加重阈值',
    desc: '单场失误次数超过此阈值后，超出部分按加重倍率惩罚。默认 3（次）。\n• 第 1~threshold 次失误：正常按 turnover_penalty 扣分\n• 第 threshold+1 次起：每次按 penalty × multiplier 加重扣分\n设为较大值（≥10）相当于关闭加重机制，所有失误统一扣分。\n目的：区分"偶发失误"（宽容）和"习惯性失误"（加重惩罚）。',
  },
  {
    name: 'consecutive_turnover_multiplier — 超阈值失误倍率',
    desc: '失误次数超过阈值后，超出部分每次失误的惩罚倍率。默认 1.5（额外 +50% 惩罚）。\n例：threshold=3，multiplier=1.5，penalty=0.2\n  → 前3次各扣 0.2，第4次起改为每次扣 0.3（0.2 × 1.5）\n• 设为 1.0：不加重，与正常失误相同\n• 设为 2.0：超阈值部分惩罚翻倍',
  },
  // ── 外战参数（对应算法参数 10.5）────────────────────────────────────────
  {
    name: 'external_impact_multiplier — 外战评分影响倍率',
    desc: '外战（对阵其他队伍）比赛结果对 mu/sigma 更新幅度的全局缩放比例。默认 1.0（与内部训练赛相同权重）。\n• 认为外战结果可信度低（如对手信息不透明）：降至 0.5~0.7\n• 重视对外战绩，希望外战胜出奖励更多：调高至 1.2~1.5\n⚠️ 过高时一场外战大胜可能导致评分异常飙升，尤其对新建团队影响更大。',
  },
  {
    name: 'external_opp_mu_min — 虚拟对手最弱 mu（强度=1）',
    desc: '外战强度评级为"1"（最弱）时，系统用于计算的虚拟对手 mu 值。默认 15.0。\n15 代表明显弱于初始水平（新球员 mu=25）的对手。\n• 调高到 20：打"最弱"外战也需要付出更多才能涨分\n此值与 external_opp_mu_max 共同定义强度 1~10 的 mu 线性映射区间。',
  },
  {
    name: 'external_opp_mu_max — 虚拟对手最强 mu（强度=10）',
    desc: '外战强度评级为"10"（最强）时，系统用于计算的虚拟对手 mu 值。默认 50.0。\n50 约是新球员初始值（25）的两倍，赢这样的顶级对手有明显涨分激励。\n• 建议参考队内顶尖球员 mu 来设定合理上限\n• 上限过低：高强度外战与普通比赛奖励无区别',
  },
  {
    name: 'external_opp_sigma — 虚拟对手不确定度 sigma',
    desc: '手动输入强度的外战中，系统生成的虚拟对手水平不确定度。默认 6.0。\n• sigma 越小（如 4.0）：系统"更相信"对手水平稳定，比赛结果对评分影响更大\n• sigma 越大（如 8.0）：对手水平视为"不稳定"，比赛结果影响更温和\n⚠️ 通过联盟排行自动匹配真实对手时，sigma 根据对手实际参赛场次校准，此值仅用于手动输入强度的外战场景。',
  },
  // ── OpenSkill 模型参数（对应算法参数 10.1）───────────────────────────────
  {
    name: 'openskill_mu — 新球员初始均值 mu',
    desc: '新加入球员的起始技能估值 mu。默认 25.0，通常无需修改。\n• 修改此值只改变绝对数字刻度，不影响球员间的相对排名顺序\n⚠️ 修改后需对所有旧球员执行重新评分（rerate），否则新旧球员标准不统一，且会影响外战强度校准基准。',
  },
  {
    name: 'openskill_sigma — 新球员初始不确定度 sigma',
    desc: '新球员评分的初始不确定度。默认 8.333（≈ mu/3）。\nsigma 越高 → 系统越不确定新球员水平 → 前几场评分波动越大（涨或跌都更快）。\n• 提高到 10：新球员可快速拉开差距，连赢快速上升\n• 降低到 6：评分更稳定，但上升/下降速度也更慢\n通常保持默认，sigma 会随比赛场次自然收敛（约 8~15 场后趋于稳定）。',
  },
  {
    name: 'openskill_beta — 比赛随机噪声参数 beta',
    desc: '决定单场比赛结果中"运气因素"所占比重。默认 4.167（≈ sigma/2）。\n• beta 越大：系统认为比赛随机性强，每场对评分影响越小（不容易暴涨暴跌）\n• beta 越小：每场对评分影响越大，系统更"相信"比赛结果反映真实水平\n建议保持 beta ≈ sigma/2 的比例关系。',
  },
  {
    name: 'openskill_tau — 动态因子（防止评分僵化）',
    desc: '每场比赛后 sigma 的微小增长量，防止老球员 sigma 过度收窄后评分"僵化"。默认 0.083（≈ sigma/100）。\n• tau 越大：老球员评分越"活跃"，几场好成绩就能明显提升排名\n• tau=0：sigma 只减不增，资深球员评分越来越难以改变\n若感觉老球员排名长期凝固，可小幅上调至 0.1~0.15。',
  },
  {
    name: 'openskill_kappa — 数值稳定保护下限 kappa',
    desc: '防止内部计算中 sigma 趋近于 0 引发数学错误的保护下限值。默认 0.0001。\n极少需要调整。仅当出现评分异常（如排名出现 NaN 或极端值）时，可小幅上调至 0.001 排查问题。正常运营保持默认即可。',
  },
  {
    name: 'openskill_margin — 险胜/大胜分差门槛',
    desc: 'OpenSkill PlackettLuce 模型参数 margin（胜局分差容忍项），不是业务层“险胜阈值开关”。默认 0.0。\n该参数会直接影响模型更新敏感度，属于高影响参数：小幅调整也可能引发全榜显著变化（尤其在 rerate 后）。\n建议仅在赛季级评审后调整，并配合参数扫描回归验证。',
  },
  {
    name: 'openskill_limit_sigma — 限制 sigma 只降不增',
    desc: '开启后，球员 sigma 永远不会超过其初始值（openskill_sigma），确定性只增不减。默认 false（关闭）。\n设为 true 可防止偶发异常数据（如录入错误）导致 sigma 突然飙升。v2 已通过 tau 参数管理 sigma 生命周期，通常无需开启此保护，保持默认 false 即可。',
  },
  {
    name: 'openskill_balance — 队伍人数平衡（v2 强烈建议开启）',
    desc: '开启后，两队人数不等时（如 5v4 练习赛）自动缩放人数较少一方的评分影响幅度，保证人数差异不引起异常评分变动。默认 true。\n关闭后，人数不等的比赛结果可能导致 30~50% 额外的评分偏差。飞盘练习赛中非标准人数场次较常见，强烈建议保持开启。',
  },
  // ── 化学值参数（对应算法参数 10.6）──────────────────────────────────────
  {
    name: 'chemistry_win_weight — 化学值协同胜率权重',
    desc: '搭档化学值中"协同胜率超出预期"部分的计分占比。默认 0.7（70%）。\n协同胜率 = 两人同队时的实际胜率 - 基准预期胜率（0.5）。正值越大说明两人在一起时队伍表现越好。\n• 降低到 0.5（同时提高 chemistry_combo_weight）：让直接配合频次和胜率贡献并重\n• 偏重"一起赢"文化的队伍保持高值即可',
  },
  {
    name: 'chemistry_combo_weight — 化学值直接配合权重',
    desc: '搭档化学值中"直接进攻配合率"（进球+助攻组合次数/共同比赛场次）的计分占比。默认 0.3（30%）。\n提高此权重奖励频繁直接连线的搭档（如固定handler-cutter配对），适合重视战术配合文化的队伍。',
  },
  // ── 算法 v2 贡献权重────────────────────────────────────────────────────
  {
    name: 'weight_cap — 贡献权重上限（v2 新增）',
    desc: '个人贡献分映射到 OpenSkill 内部计算时的权重上限。默认 2.0，范围 1.0~5.0。\n防止贡献差距过大（如 1 人进了 10 球、队友均 0 球）时出现极端评分跳变。\n• 设为 1.0：所有人权重相同，等同于禁用贡献差异（与 alpha=0 效果类似）\n• 5人队伍推荐 2.0~3.0；设置过高边际效果递减',
  },
  {
    name: 'chemistry_decay_constant — 化学值置信衰减常数（v2 新增）',
    desc: '化学值置信度随共同比赛场次"趋于可信"的速度。默认 8.0。\n公式：置信度 = 1 - exp(-共同场次/decay)。\n场次→置信度参考（decay=8）：1场→12%，4场→39%，8场→63%，16场→87%，24场→95%。\n• 值越小：少量场次即达高置信（化学值更敏感，适合短赛季）\n• 值越大：需更多场次验证（化学值更保守稳定，适合长期联盟）',
  },
  {
    name: 'perf_confidence_decay — 表现分场次置信折扣系数',
    desc: '控制综合战力中"表现分"置信度随参赛场次增加"趋于可信"的速度。默认 8.0，范围 1~50。\n公式：表现分 = 50 + (1 - exp(-场次/N)) × (原始表现分 - 50)\n场次越少，表现分越接近基准 50 → 防止场次过少的球员因短期高数据异常排名靠前。\n场次→置信度参考（N=8）：1场→12%，3场→31%，5场→46%，8场→63%，11场→75%，20场→92%。\n• N 越小：少量场次就能充分体现（场次少的队伍适用）\n• N 越大：需更多场次积累才能全量反映（排名更稳定）',
  },
  // ── 已废弃参数（v2 保留字段，不参与计算）──────────────────────────────
  {
    name: '⚠️ sigma_bonus_factor【v2 已废弃，修改不生效】',
    desc: 'v1 中用于在高贡献球员更新后额外缩小其 sigma，加速评分收敛。v2 起废弃，sigma 完全由 OpenSkill 自动管理。字段仍存在于数据库但不参与任何计算，修改无效果。保持默认值 0.15 即可。',
  },
  {
    name: '⚠️ turnover_sigma_factor【v2 已废弃，修改不生效】',
    desc: 'v1 中用于让有失误的球员 sigma 增大，使其评分变得不确定。v2 起废弃。原因：sigma 代表"评分成熟度"，不应被失误行为人为干扰。字段仍存在于数据库但不参与任何计算，修改无效果。保持默认值 0.3 即可。',
  },
]

// field-key → description text for the popup tooltips
const coeffFieldDesc: Record<string, string> = {
  alpha: coeffDescriptions[0]!.desc,
  beta: coeffDescriptions[1]!.desc,
  gamma: coeffDescriptions[2]!.desc,
  defense_weight: coeffDescriptions[3]!.desc,
  composite_ts_weight: coeffDescriptions[4]!.desc,
  composite_perf_weight: coeffDescriptions[5]!.desc,
  composite_attendance_weight: coeffDescriptions[6]!.desc,
  turnover_penalty: coeffDescriptions[7]!.desc,
  break_bonus_per_goal: coeffDescriptions[8]!.desc,
  winner_floor_factor: coeffDescriptions[9]!.desc,
  universal_point_bonus: coeffDescriptions[10]!.desc,
  block_mu_bonus: coeffDescriptions[11]!.desc,
  consecutive_turnover_threshold: coeffDescriptions[12]!.desc,
  consecutive_turnover_multiplier: coeffDescriptions[13]!.desc,
  external_impact_multiplier: coeffDescriptions[14]!.desc,
  external_opp_mu_min: coeffDescriptions[15]!.desc,
  external_opp_mu_max: coeffDescriptions[16]!.desc,
  external_opp_sigma: coeffDescriptions[17]!.desc,
  openskill_mu: coeffDescriptions[18]!.desc,
  openskill_sigma: coeffDescriptions[19]!.desc,
  openskill_beta: coeffDescriptions[20]!.desc,
  openskill_tau: coeffDescriptions[21]!.desc,
  openskill_kappa: coeffDescriptions[22]!.desc,
  openskill_margin: coeffDescriptions[23]!.desc,
  openskill_limit_sigma: coeffDescriptions[24]!.desc,
  openskill_balance: coeffDescriptions[25]!.desc,
  chemistry_win_weight: coeffDescriptions[26]!.desc,
  chemistry_combo_weight: coeffDescriptions[27]!.desc,
  weight_cap: coeffDescriptions[28]!.desc,
  chemistry_decay_constant: coeffDescriptions[29]!.desc,
  perf_confidence_decay: coeffDescriptions[30]!.desc,
  sigma_bonus_factor: coeffDescriptions[31]!.desc,
  turnover_sigma_factor: coeffDescriptions[32]!.desc,
}

const coeffLabel: Record<string, string> = {
  alpha: 'alpha（贡献差异放大系数，范围 0~2）',
  beta: 'beta（进球贡献权重，范围 0~2）',
  gamma: 'gamma（助攻贡献权重，范围 0~2）',
  defense_weight: 'defense_weight（防守次数贡献权重，范围 0~2）',
  composite_ts_weight: 'composite_ts_weight（保守战力分权重，范围 0~1）',
  composite_perf_weight: 'composite_perf_weight（近期表现分权重，范围 0~1）',
  composite_attendance_weight: 'composite_attendance_weight（出勤加成权重，范围 0~1）',
  perf_confidence_decay: 'perf_confidence_decay（表现分场次置信折扣，范围 1~50）',
  turnover_penalty: 'turnover_penalty（失误惩罚，范围 0~2）',
  break_bonus_per_goal: 'break_bonus_per_goal（Break 进球奖励，范围 0~2）',
  winner_floor_factor: 'winner_floor_factor（胜者保底系数，范围 0~1）',
  universal_point_bonus: 'universal_point_bonus（宇宙分奖励，范围 0~5）',
  block_mu_bonus: 'block_mu_bonus（Block 奖励，范围 0~2）',
  consecutive_turnover_threshold: 'consecutive_turnover_threshold（连续失误阈值，范围 1~20）',
  consecutive_turnover_multiplier: 'consecutive_turnover_multiplier（超阈值失误倍率，范围 1~5）',
  external_impact_multiplier: 'external_impact_multiplier（外战影响倍率，范围 0~3）',
  external_opp_mu_min: 'external_opp_mu_min（外战最弱对手 mu，范围 1~50）',
  external_opp_mu_max: 'external_opp_mu_max（外战最强对手 mu，范围 1~100）',
  external_opp_sigma: 'external_opp_sigma（外战对手 sigma，范围 1~20）',
  openskill_mu: 'openskill_mu（新球员初始 mu，范围 1~60）',
  openskill_sigma: 'openskill_sigma（新球员初始 sigma，范围 0.5~20）',
  openskill_beta: 'openskill_beta（比赛噪声 beta，范围 0.1~20）',
  openskill_tau: 'openskill_tau（动态因子 tau，范围 0~5）',
  openskill_kappa: 'openskill_kappa（数值稳定下限，范围 0~0.1）',
  openskill_margin: 'openskill_margin（险胜分差门槛，范围 0~20）',
  openskill_limit_sigma: 'openskill_limit_sigma（限制 sigma 只降不增）',
  openskill_balance: 'openskill_balance（人数平衡开关）',
  chemistry_win_weight: 'chemistry_win_weight（化学值胜率权重，范围 0~1）',
  chemistry_combo_weight: 'chemistry_combo_weight（化学值配合权重，范围 0~1）',
  weight_cap: 'weight_cap（贡献权重上限，范围 1~5）',
  chemistry_decay_constant: 'chemistry_decay_constant（化学值置信衰减常数，范围 1~50）',
  sigma_bonus_factor: 'sigma_bonus_factor（已废弃，范围 0~1）',
  turnover_sigma_factor: 'turnover_sigma_factor（已废弃，范围 0~2）',
}

const {
  pendingMembers,
  loadingMembers,
  finishedMembers,
  refreshingMembers,
  loadPendingMembers,
  loadSuggestedMuForReview,
  approvePlayer,
  rejectPlayer,
} = useAdminMembers(auth)

const showApproveDialog = ref(false)
const approvingItem = ref<PendingItem | null>(null)
const initialMuInput = ref('')
const suggestedMuInfo = ref<{
  suggested_mu: number
  sample_count: number
  used_default: boolean
  fallback_mu: number
} | null>(null)

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

async function openApproveDialog(item: PendingItem) {
  approvingItem.value = item
  initialMuInput.value = ''
  suggestedMuInfo.value = null
  if (item._type === 'membership') {
    try {
      suggestedMuInfo.value = await loadSuggestedMuForReview()
    } catch {
      suggestedMuInfo.value = null
    }
  }
  showApproveDialog.value = true
}

async function confirmApprove() {
  if (!approvingItem.value) return
  const parsed = parseInitialMuInput()
  if (parsed === null) return false
  await approvePlayer(approvingItem.value, parsed)
  showApproveDialog.value = false
  approvingItem.value = null
  initialMuInput.value = ''
  return true
}

// --- Settings state ---
interface Settings {
  alpha: number; beta: number; gamma: number; defense_weight: number
  composite_ts_weight: number; composite_perf_weight: number; composite_attendance_weight: number
  turnover_penalty: number; turnover_sigma_factor: number; break_bonus_per_goal: number; winner_floor_factor: number
  external_impact_multiplier: number
  external_opp_mu_min: number; external_opp_mu_max: number; external_opp_sigma: number
  openskill_mu: number; openskill_sigma: number; openskill_beta: number
  openskill_tau: number; openskill_kappa: number; openskill_margin: number
  openskill_limit_sigma: boolean; openskill_balance: boolean
  chemistry_win_weight: number; chemistry_combo_weight: number
  weight_cap: number; chemistry_decay_constant: number
}

const settings = ref<Settings | null>(null)
const loadingSettings = ref(false)
const savingSettings = ref(false)
const settingsForm = ref({
  alpha: '', beta: '', gamma: '', defense_weight: '',
  composite_ts_weight: '', composite_perf_weight: '', composite_attendance_weight: '',
  perf_confidence_decay: '',
  turnover_penalty: '', turnover_sigma_factor: '', break_bonus_per_goal: '', winner_floor_factor: '',
  external_impact_multiplier: '', external_opp_mu_min: '', external_opp_mu_max: '', external_opp_sigma: '',
  openskill_mu: '', openskill_sigma: '', openskill_beta: '',
  openskill_tau: '', openskill_kappa: '', openskill_margin: '',
  openskill_limit_sigma: 'false', openskill_balance: 'false',
  chemistry_win_weight: '', chemistry_combo_weight: '',
  weight_cap: '', chemistry_decay_constant: '',
})

function toBool(v: string): boolean {
  return String(v).trim().toLowerCase() === 'true'
}

function inRange(val: string) {
  const n = Number(val)
  return !isNaN(n) && n >= 0 && n <= 2
}

async function loadSettings() {
  if (auth.isSuperAdmin) return  // 超管无属队队伍，跳过
  if (!isOwner && !auth.isAdmin) return
  loadingSettings.value = true
  try {
    const res = await api.get('/team/settings')
    settings.value = res.data
    settingsForm.value = {
      alpha: String(res.data.alpha),
      beta: String(res.data.beta),
      gamma: String(res.data.gamma),
      defense_weight: String(res.data.defense_weight ?? '0.1'),
      composite_ts_weight: String(res.data.composite_ts_weight),
      composite_perf_weight: String(res.data.composite_perf_weight),
      composite_attendance_weight: String(res.data.composite_attendance_weight ?? '0.0'),
      perf_confidence_decay: String(res.data.perf_confidence_decay ?? '8.0'),
      turnover_penalty: String(res.data.turnover_penalty ?? '0.2'),
      turnover_sigma_factor: String(res.data.turnover_sigma_factor ?? '0.3'),
      break_bonus_per_goal: String(res.data.break_bonus_per_goal ?? '0.1'),
      winner_floor_factor: String(res.data.winner_floor_factor ?? '0.1'),
      external_impact_multiplier: String(res.data.external_impact_multiplier ?? '1.0'),
      external_opp_mu_min: String(res.data.external_opp_mu_min ?? '15.0'),
      external_opp_mu_max: String(res.data.external_opp_mu_max ?? '50.0'),
      external_opp_sigma: String(res.data.external_opp_sigma ?? '6.0'),
      openskill_mu: String(res.data.openskill_mu ?? '25.0'),
      openskill_sigma: String(res.data.openskill_sigma ?? '8.333'),
      openskill_beta: String(res.data.openskill_beta ?? '4.167'),
      openskill_tau: String(res.data.openskill_tau ?? '0.083333'),
      openskill_kappa: String(res.data.openskill_kappa ?? '0.0001'),
      openskill_margin: String(res.data.openskill_margin ?? '0.0'),
      openskill_limit_sigma: String(Boolean(res.data.openskill_limit_sigma)),
      openskill_balance: String(Boolean(res.data.openskill_balance)),
      chemistry_win_weight: String(res.data.chemistry_win_weight ?? '0.7'),
      chemistry_combo_weight: String(res.data.chemistry_combo_weight ?? '0.3'),
      weight_cap: String(res.data.weight_cap ?? '2.0'),
      chemistry_decay_constant: String(res.data.chemistry_decay_constant ?? '8.0'),
    }
  } finally {
    loadingSettings.value = false
  }
}

async function saveSettings() {
  savingSettings.value = true
  try {
    await api.put('/team/settings', {
      alpha: Number(settingsForm.value.alpha),
      beta: Number(settingsForm.value.beta),
      gamma: Number(settingsForm.value.gamma),
      defense_weight: Number(settingsForm.value.defense_weight),
      composite_ts_weight: Number(settingsForm.value.composite_ts_weight),
      composite_perf_weight: Number(settingsForm.value.composite_perf_weight),
      composite_attendance_weight: Number(settingsForm.value.composite_attendance_weight),
      perf_confidence_decay: Number(settingsForm.value.perf_confidence_decay),
      turnover_penalty: Number(settingsForm.value.turnover_penalty),
      turnover_sigma_factor: Number(settingsForm.value.turnover_sigma_factor),
      break_bonus_per_goal: Number(settingsForm.value.break_bonus_per_goal),
      winner_floor_factor: Number(settingsForm.value.winner_floor_factor),
      external_impact_multiplier: Number(settingsForm.value.external_impact_multiplier),
      external_opp_mu_min: Number(settingsForm.value.external_opp_mu_min),
      external_opp_mu_max: Number(settingsForm.value.external_opp_mu_max),
      external_opp_sigma: Number(settingsForm.value.external_opp_sigma),
      openskill_mu: Number(settingsForm.value.openskill_mu),
      openskill_sigma: Number(settingsForm.value.openskill_sigma),
      openskill_beta: Number(settingsForm.value.openskill_beta),
      openskill_tau: Number(settingsForm.value.openskill_tau),
      openskill_kappa: Number(settingsForm.value.openskill_kappa),
      openskill_margin: Number(settingsForm.value.openskill_margin),
      openskill_limit_sigma: toBool(settingsForm.value.openskill_limit_sigma),
      openskill_balance: toBool(settingsForm.value.openskill_balance),
      chemistry_win_weight: Number(settingsForm.value.chemistry_win_weight),
      chemistry_combo_weight: Number(settingsForm.value.chemistry_combo_weight),
      weight_cap: Number(settingsForm.value.weight_cap),
      chemistry_decay_constant: Number(settingsForm.value.chemistry_decay_constant),
    })
    showToast('系数已保存')
    await loadSettings()
  } catch (err: any) {
    showToast(err?.response?.data?.detail ?? '保存失败')
  } finally {
    savingSettings.value = false
  }
}

const {
  pendingTeams,
  loadingTeams,
  finishedTeams,
  refreshingTeams,
  loadPendingTeams,
  approveTeam,
  rejectTeam,
  allTeams,
  loadingAllTeams,
  settingsTeamObject,
  showTeamSettingsPopup,
  editingTeam,
  loadingTeamSettings,
  savingTeamSettings,
  resettingTeamSettings,
  reratingTeam,
  rerateProgress,
  rerateMessage,
  broadcastScope,
  broadcastTeamIds,
  broadcastContent,
  publishingBroadcast,
  editSettingsForm,
  loadAllTeams,
  publishBroadcastNotice,
  openTeamSettings,
  saveTeamSettings,
  resetTeamSettings,
  rerateEditingTeam,
  invalidSettingMessages,
} = useAdminTeamOps()

const {
  auditLogs,
  auditPage,
  auditTotalPages,
  loadingAuditLogs,
  auditFilterTeamId,
  auditFilterAction,
  auditFilterDate,
  showAuditDatePicker,
  auditDateParts,
  auditTeamOptions,
  auditActionOptions,
  getAuditActionLabel,
  loadAuditTeamList,
  loadAuditLogs,
  onAuditDateConfirm,
  clearAuditDate,
} = useAdminAuditLogs()

function formatAuditDetail(detail: Record<string, unknown> | null): string {
  if (!detail) return ''
  const parts: string[] = []
  if (detail['score']) parts.push(`比分 ${detail['score']}`)
  if (detail['match_type']) parts.push(String(detail['match_type']))
  if (detail['status']) parts.push(String(detail['status']))
  // notes已经在标题行高亮显示，这里不再重复
  const rest = Object.entries(detail).filter(([k]) => !['score', 'match_type', 'status', 'notes', 'before', 'after'].includes(k))
  for (const [k, v] of rest) parts.push(`${k}:${v}`)
  if (detail['before'] || detail['after']) parts.push('[有字段变更]')
  return parts.join(' · ')
}

// ── 赛季管理 ────────────────────────────────────────────────────────────────

interface SeasonRaw {
  id: number
  year: number
  is_current: boolean
  member_count: number
  created_at: string
}

interface SeasonMember {
  id: number
  username: string
  display_name: string | null
  status: string
}

const seasons = ref<SeasonRaw[]>([])
const loadingSeasons = ref(false)
const showCreateSeasonWizard = ref(false)
const wizardStep = ref(1)
const wizardYear = ref(new Date().getFullYear() + 1)
const wizardSyncRatings = ref(true)
const wizardMembers = ref<SeasonMember[]>([])
const wizardSelectedMemberIds = ref<number[]>([])
const wizardSubmitting = ref(false)

// 年份滚动选择列 2024-2035
const yearPickerColumns = computed(() => {
  const cols = []
  for (let y = 2024; y <= 2040; y++) cols.push({ text: `${y} 年`, value: String(y) })
  return [cols]
})

async function loadSeasons() {
  loadingSeasons.value = true
  try {
    const params: Record<string, any> = {}
    if (auth.isSuperAdmin && auth.viewingTeamId) params.team_id = auth.viewingTeamId
    const res = await api.get('/team/seasons', { params })
    seasons.value = res.data
  } catch {
    showToast('加载赛季失败')
  } finally {
    loadingSeasons.value = false
  }
}

async function openCreateSeasonWizard() {
  // 加载当前活跃成员列表
  try {
    const params: Record<string, any> = { status: 'active', page_size: 200 }
    if (auth.isSuperAdmin && auth.viewingTeamId) params.team_id = auth.viewingTeamId
    const res = await api.get('/players', { params })
    wizardMembers.value = res.data
    wizardSelectedMemberIds.value = res.data.map((p: SeasonMember) => p.id)
  } catch {
    showToast('加载成员失败')
    return
  }
  // 默认年份为已有赛季最大年份 + 1
  const maxYear = seasons.value.length > 0 ? Math.max(...seasons.value.map(s => s.year)) : new Date().getFullYear()
  wizardYear.value = maxYear + 1
  wizardSyncRatings.value = true
  wizardStep.value = 1
  showCreateSeasonWizard.value = true
}

async function submitCreateSeason() {
  wizardSubmitting.value = true
  try {
    const params: Record<string, any> = {}
    if (auth.isSuperAdmin && auth.viewingTeamId) params.team_id = auth.viewingTeamId
    await api.post('/team/seasons', {
      year: wizardYear.value,
      sync_ratings: wizardSyncRatings.value,
      member_ids: wizardSelectedMemberIds.value,
    }, { params })
    showToast('赛季创建成功')
    showCreateSeasonWizard.value = false
    await loadSeasons()
    await auth.loadTeamSeasons()
  } catch (e: any) {
    showToast(e?.response?.data?.detail || '创建失败')
  } finally {
    wizardSubmitting.value = false
  }
}

onMounted(() => {
  loadSettings()
  if (auth.isAdmin) loadAllTeams()
  if (auth.isSuperAdmin) {
    loadPendingTeams()
    loadAuditTeamList()
  }
})
</script>

<style scoped>
.admin-page {
  padding-bottom: 60px;
}

/* ── Settings popup ────────────────────────────────────────── */
.popup-inner {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* Two-column grid on screens wider than 640 px */
.popup-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0;
  padding: 8px 0 4px;
}
@media (min-width: 640px) {
  .popup-grid {
    grid-template-columns: 1fr 1fr;
    padding: 8px 0 4px;
    gap: 0 0;
  }
}

/* Override Vant inset cell-group padding so param-row uses full card width */
:deep(.van-cell-group--inset) .param-row {
  padding-left: 12px;
  padding-right: 12px;
}
.popup-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 16px 28px;
}

/* ── Param group card (replaces van-cell-group) ─────────────── */
.param-group {
  background: #fff;
  border: 1px solid #ebedf0;
  border-radius: 8px;
  margin-bottom: 8px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
.param-group__title {
  font-size: 11px;
  font-weight: 700;
  color: #1989fa;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 6px 12px 5px;
  background: #f0f6ff;
  border-bottom: 1px solid #dce8fb;
}
.param-group__note {
  font-size: 11px;
  color: #969799;
  line-height: 1.5;
  padding: 6px 12px;
  background: #fafafa;
  border-bottom: 1px solid #f5f5f5;
}
.param-group--deprecated {
  opacity: 0.65;
}
.param-group--deprecated .param-group__title {
  background: #fff7e6;
  border-bottom-color: #ffe7b8;
  color: #fa8c16;
}

/* ── Custom param row ────────────────────────────────────────── */
.param-row {
  padding: 7px 12px;
  border-bottom: 1px solid #f5f5f5;
}
.param-row:last-child {
  border-bottom: none;
}
/* Three-column grid: [name] [?] [input]
   name gets remaining space; ? and input are fixed width.
   align-items:start keeps them top-aligned even when name wraps. */
.param-name-line {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 20px 72px;
  align-items: start;
  gap: 4px;
}
.param-key {
  font-size: 12px;
  font-weight: 500;
  color: #323233;
  word-break: break-word;
  line-height: 1.5;
  padding-top: 3px; /* vertically center with 28px input */
}
.param-value-input {
  width: 72px;
  height: 28px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 0 6px;
  font-size: 13px;
  color: #323233;
  text-align: right;
  outline: none;
  background: #fff;
  box-sizing: border-box;
}
.param-value-input:focus {
  border-color: #1989fa;
  box-shadow: 0 0 0 2px rgba(25, 137, 250, 0.15);
}

/* ── ？ help button ──────────────────────────────────────────── */
.help-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  margin-top: 4px; /* align with input top */
  border-radius: 50%;
  background: #e8eaed;
  color: #5f6368;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  user-select: none;
  line-height: 1;
}
.help-btn:hover {
  background: #1989fa;
  color: #fff;
}

/* ── Expanded description card ──────────────────────────────── */
.coeff-desc {
  font-size: 12px;
  color: #444;
  line-height: 1.6;
  white-space: pre-line;
  background: #f0f6ff;
  border-radius: 6px;
  padding: 8px 10px;
  margin-top: 6px;
  border-left: 3px solid #1989fa;
}

/* ── Legacy classes (old disabled admin tab) ─────────────────── */
.coeff-label { display: flex; flex-direction: column; gap: 2px; }
.coeff-name { font-size: 13px; color: #323233; font-weight: 500; }
.coeff-hint { font-size: 11px; color: #969799; line-height: 1.4; white-space: normal; }

/* ── Audit log ─────────────────────────────────────────────── */
.audit-action {
  font-size: 13px;
  font-weight: 500;
  color: #323233;
}
.audit-action--match { color: #1677ff; }
.audit-action--player { color: #07c160; }
.audit-action--settings, .audit-action--team { color: #ff976a; }
</style>
