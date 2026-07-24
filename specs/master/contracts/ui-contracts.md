# UI 合同: EaglesPower 前端页面规范

**版本**: 0.9.7
**框架**: Vue 3 + Vant 4
**最小支持宽度**: 375px（iPhone SE）

---

## 导航结构

### 底部 TabBar（5 个 tab，登录后显示）

| Tab | 图标 | 路由 | 说明 |
|-----|------|------|------|
| 队伍 | team | `/team` | 队伍信息 + 留言板 |
| 排行榜 | ranking | `/rankings` | 多维度排行榜 |
| **+** | add（中心大按钮） | `/match/new` | 新建比赛（弹出选择器）|
| 比赛 | list | `/matches` | 比赛历史列表 |
| 我的 | user | `/profile` | 个人玩家卡片 |

---

## 页面合同

### 1. LoginView（`/login`）

**布局**: 全屏居中表单，品牌 Logo + 标语
**组件**:
- `van-form` + `van-field`：账号（username）、密码（password，type=password）
- `van-button`：登录按钮（全宽，type=primary）
- 链接：跳转注册页

**行为**:
- 提交后显示 `van-loading`
- 成功 → 存储 JWT → 跳转 `/rankings`
- 失败 → `van-toast` 显示错误信息

---

### 2. RegisterView（`/register`）

**布局**: 表单页
**组件**:
- `van-field`：用户名、密码、确认密码、昵称（可选）
- 队伍名称字段（仅系统无队伍时显示）
- `van-button`：提交注册

**行为**:
- 提交成功 → `van-dialog` 显示"注册申请已提交，请等待管理员审批" → 跳转 `/login`

---

### 3. RankingsView（`/rankings`，需登录）

**布局**: 顶部 `van-tabs`（6 个 tab）+ 列表
**Tab 列表**:
```
战力榜 | 稳定榜 | 得分榜 | 助攻榜 | 防守榜 | 默契度榜
```
**组件**:
- `van-tabs` + `van-tab`：6 个排行维度
- `van-list`（虚拟滚动）：排名列表，每行：`排名 · 头像 · 姓名 · 数值 · 趋势箭头`
- 点击行 → 跳转对应玩家卡片页

**响应式**: 375px 下每行紧凑布局，数值右对齐

---

### 4. ProfileView（`/profile`，需登录）

**布局**: 玩家卡片（Player Card）风格，深色主题
**区块**:
1. **卡片头部**: 头像（Vant Avatar）+ 姓名 + 保守评分（大字）+ 排名位置
2. **μ / σ 数值行**: 两列并排展示
3. **雷达图**: ECharts 雷达图，五维（进攻/助攻/防守/稳定性/胜率），作为卡片核心视觉
4. **趋势折线图**: 最近 10 场 conservative_rating，ECharts 折线图
5. **比赛记录列表**: 最近 20 场，`van-cell-group`，每行：日期 / 胜负 / 个人统计 / μ 变化

**访问他人**: URL `/profile/:id`；管理员看完整数据，普通成员看公开字段

---

### 5. MatchInputView — 比赛录入主流程（需登录）

**流程**: 分步骤（`van-steps` 顶部进度条）

#### Step 1: 类型选择
- `van-radio-group`：内战 / 外战 / 快速录入
- `van-radio-group`：比赛类型（Ultimate / Goal）

#### Step 2: 阵容设置
**内战**:
- 从队员列表（`van-checkbox-group`）分配 A 队 / B 队
- 每队至少 3 人方可继续

**外战**:
- 本队参赛队员（`van-checkbox-group`）
- 对手强度选择（`van-slider` 1–10，或 `van-stepper`）

#### Step 3: 比赛实况（主屏幕）
**常驻 UI**:
- 顶部：计时器（大数字，`HH:MM:SS`）
- 中部：比分板（A 队 VS B 队，大字）
- 底部两栏：`A队得分` / `B队得分` 按钮（大圆角按钮，高 56px+）
- 浮动按钮：防守盘（D）、半场、结束

**得分录入底部抽屉** (`van-action-sheet`):
1. 选择得分者（`van-radio-group`，按队员姓名）
2. 选择助攻者（`van-radio-group`，可跳过"无助攻"选项）
3. （Ultimate 模式）标记是否 break 球
4. 确认按钮

**比赛时间轴** (`/match/live/:id`):
- 纵向时间轴
- 左侧 A 队事件 / 右侧 B 队事件
- 每条记录：时间 · 得分者 · 助攻者 · break 标记

#### Step 4: 比赛总结 + 提交
- 最终比分
- 得分榜 / 助攻榜 / 防守榜
- "提交"按钮 + "继续编辑"按钮
- Admin 直接触发评分计算；非 Admin → 显示"已提交待审批"

---

### 6. TeamView（`/team`，需登录）

**布局**: 两个区块
1. **队伍信息**: 队伍名称 + 成员总数 + 已完成比赛数
2. **留言板**: `van-list` 显示帖子，底部 `van-field` + 发送按钮

---

### 7. MatchListView（`/matches`，需登录）

**布局**: `van-tabs`（待审批 / 已完成 / 草稿）+ `van-list`
**每行**: 日期 / 类型 / 比分 / 状态

---

### 8. 管理员入口（`/admin`，需 admin 权限）

**功能区块**:
- 待审批成员列表（批准/拒绝）
- 待审批比赛列表（审批/查看详情）
- 比赛管理（编辑/删除）
- 算法系数设置（仅 owner）

---

## 全局 UI 规范

| 规范 | 值 |
|------|-----|
| 主色 | `#4b8bff`（蓝色） |
| 背景色（深色卡片模式） | `#0d1117` |
| 字体 | 系统默认（-apple-system, sans-serif）|
| 最小触控目标 | 44px × 44px |
| 安全区域 | `env(safe-area-inset-*)` 处理 iPhone 刘海/圆角 |
| 加载状态 | 全局 `van-loading` overlay |
| 错误提示 | `van-toast` / `van-notify` |
| 确认操作 | `van-dialog` |

