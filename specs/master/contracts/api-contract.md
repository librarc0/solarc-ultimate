# API 接口合同: EaglesPower REST API v1

**版本**: 0.9.7
**基础路径**: `/api/v1`
**认证**: Bearer JWT Token（除公开接口外均需）
**统一响应格式**:
```json
{ "code": 0, "data": {}, "message": "" }
```
- `code = 0`：成功
- `code != 0`：失败（详见各接口错误码）

---

## 系统接口

### GET /health
**描述**: 健康检查，Docker 健康检查专用
**认证**: 无需
**响应**: `200 OK`
```json
{ "code": 0, "data": { "status": "ok", "version": "0.9.7" }, "message": "" }
```

---

## 认证接口 (`/api/v1/auth`)

### POST /auth/register
**描述**: 注册新账号（第一个用户成为 owner，其余为 pending）
**认证**: 无需
**请求体**:
```json
{
  "username": "string(6-20, 字母数字)",
  "password": "string(>=8位)",
  "display_name": "string(可选, <=50)",
  "team_name": "string(可选, 首个用户创建队伍时必填)"
}
```
**成功响应** `201 Created`:
```json
{
  "code": 0,
  "data": {
    "id": 1,
    "username": "player01",
    "status": "pending",
    "role": "member",
    "message": "注册申请已提交，请等待管理员审批"
  },
  "message": ""
}
```
**错误码**:
- `409`：用户名已存在
- `422`：输入校验失败（用户名格式/密码长度）

### POST /auth/login
**描述**: 账号密码登录
**认证**: 无需
**请求体**:
```json
{ "username": "string", "password": "string" }
```
**成功响应** `200 OK`:
```json
{
  "code": 0,
  "data": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 604800,
    "player": { "id": 1, "username": "player01", "role": "owner", "display_name": "Eagle" }
  },
  "message": ""
}
```
**错误码**:
- `401`：账号或密码错误
- `403`：账号待审批 / 已拒绝

### GET /auth/me
**描述**: 获取当前登录用户信息
**认证**: 需要
**成功响应** `200`:
```json
{
  "code": 0,
  "data": {
    "id": 1, "username": "player01", "display_name": "Eagle",
    "role": "owner", "status": "active",
    "mu": 25.0, "sigma": 8.333, "conservative_rating": 0.0,
    "total_matches": 0, "total_wins": 0, "total_goals": 0
  },
  "message": ""
}
```

---

## 队员接口 (`/api/v1/players`)

### GET /players
**描述**: 获取队员列表（需登录）
**认证**: 需要
**查询参数**: `status` (pending/active/rejected, 可选), `page`(默认1), `page_size`(默认20,最大100)
**成功响应** `200`:
```json
{
  "code": 0,
  "data": {
    "items": [
      { "id": 1, "username": "player01", "display_name": "Eagle", "role": "owner",
        "status": "active", "conservative_rating": 12.5, "total_matches": 10 }
    ],
    "total": 1, "page": 1, "page_size": 20
  },
  "message": ""
}
```

### GET /players/{player_id}
**描述**: 获取指定队员详情
**认证**: 需要
**规则**: 管理员可查看完整数据（含 μ/σ 历史）；普通成员只能查看公开字段
**成功响应** `200`

### PUT /players/{player_id}
**描述**: 更新队员信息（admin 可更新 status/role，队员只能更新自己的 display_name）
**认证**: 需要（admin 或本人）
**请求体**:
```json
{
  "display_name": "string(可选)",
  "status": "active|rejected(admin only)",
  "role": "admin|member(owner only)"
}
```

### POST /players
**描述**: 管理员直接创建并激活账号
**认证**: 需要（admin）
**请求体**:
```json
{ "username": "string", "password": "string", "display_name": "string(可选)", "status": "active" }
```

---

## 比赛接口 (`/api/v1/matches`)

### POST /matches
**描述**: 创建比赛记录
**认证**: 需要（登录队员均可，admin 直接 approved，非 admin 需等待审批）
**请求体**:
```json
{
  "match_type": "internal|external",
  "game_type": "ultimate|goal",
  "match_date": "2026-03-11T15:00:00",
  "team_a_players": [1, 2, 3],
  "team_b_players": [4, 5, 6],
  "team_a_score": 13,
  "team_b_score": 11,
  "opponent_strength": null,
  "players": [
    { "player_id": 1, "team_side": "A", "goals": 3, "assists": 2, "plus_minus": 1 }
  ],
  "events": [
    { "event_type": "goal", "team_side": "A", "player_id": 1, "assist_player_id": 2,
      "is_break": false, "elapsed_seconds": 120 }
  ],
  "notes": "可选备注"
}
```
**成功响应** `201 Created`:
```json
{
  "code": 0,
  "data": {
    "id": 42,
    "status": "approved",
    "data_level": 3,
    "rating_updated": true
  },
  "message": "比赛已提交，评分已更新"
}
```

### GET /matches
**描述**: 获取比赛列表
**认证**: 需要
**查询参数**: `status`, `match_type`, `player_id`, `page`, `page_size`

### GET /matches/{match_id}
**描述**: 获取单场比赛详情（含所有参与者统计）
**认证**: 需要

### PUT /matches/{match_id}
**描述**: 管理员审批或修改比赛（触发评分重算）
**认证**: 需要（admin）
**请求体**: POST /matches 请求体中的任意字段（可选），或 `{"status": "approved|rejected"}`

### DELETE /matches/{match_id}
**描述**: 删除 draft 状态的比赛（仅录入者或 admin）
**认证**: 需要

---

## 排行榜接口 (`/api/v1/rankings`)

### GET /rankings
**描述**: 获取排行榜（需登录）
**认证**: 需要
**查询参数**:
- `tab`: `conservative`(战力) / `stable`(稳定) / `goals`(得分) / `assists`(助攻) / `defense`(防守) / `chemistry`(默契度)，默认 `conservative`
- `page`, `page_size`

**成功响应** `200`:
```json
{
  "code": 0,
  "data": {
    "tab": "conservative",
    "items": [
      { "rank": 1, "player_id": 3, "display_name": "Eagle", "conservative_rating": 18.2,
        "mu": 27.5, "sigma": 3.1, "total_matches": 25, "win_rate": 0.72 }
    ],
    "total": 15, "page": 1, "page_size": 20
  },
  "message": ""
}
```

### GET /rankings/me
**描述**: 获取当前用户完整个人面板（含雷达图数据 + 历史曲线）
**认证**: 需要
**成功响应** `200`:
```json
{
  "code": 0,
  "data": {
    "player": { "id": 1, "display_name": "Eagle", "rank": 3, "total_players": 15,
                "conservative_rating": 18.2, "mu": 27.5, "sigma": 3.1 },
    "radar": {
      "attack": 85, "assist": 60, "defense": 72, "stability": 88, "win_rate": 72
    },
    "history": [
      { "match_id": 10, "date": "2026-03-01", "conservative_rating": 16.5, "delta_mu": 1.2 }
    ],
    "recent_matches": [
      { "match_id": 10, "date": "2026-03-01", "match_type": "internal", "result": "win",
        "goals": 2, "assists": 1, "plus_minus": 1, "mu_change": 1.2 }
    ]
  },
  "message": ""
}
```

### GET /rankings/players/{player_id}
**描述**: 查看指定队员面板
**认证**: 需要
**规则**: 管理员返回完整数据；普通成员返回公开字段（隐藏 μ/σ 历史详情）

---

## 队伍设置接口 (`/api/v1/team`)

### GET /team/settings
**描述**: 获取当前队伍算法系数
**认证**: 需要（admin）

### PUT /team/settings
**描述**: 更新算法系数
**认证**: 需要（owner only）
**请求体**:
```json
{
  "alpha": 0.3, "beta": 0.6, "gamma": 0.4,
  "composite_ts_weight": 0.85, "composite_perf_weight": 0.15
}
```

---

## 留言板接口 (`/api/v1/team/posts`)

### GET /team/posts
**描述**: 获取留言板帖子列表（时间倒序）
**认证**: 需要
**查询参数**: `page`, `page_size`

### POST /team/posts
**描述**: 发布新帖子
**认证**: 需要（active 成员）
**请求体**: `{ "content": "string(1-500)" }`

### DELETE /team/posts/{post_id}
**描述**: 删除帖子（发帖人或 admin）
**认证**: 需要

---

## 错误码规范

| HTTP 状态码 | code | 说明 |
|------------|------|------|
| 200 | 0 | 成功 |
| 201 | 0 | 创建成功 |
| 400 | 1001 | 请求参数错误 |
| 401 | 1002 | 未认证 / Token 无效 / 已过期 |
| 403 | 1003 | 无权限 |
| 403 | 1004 | 账号待审批 |
| 403 | 1005 | 账号已拒绝 |
| 404 | 1006 | 资源不存在 |
| 409 | 1007 | 资源冲突（用户名重复等）|
| 422 | 1008 | 输入校验失败（Pydantic 详情）|
| 500 | 9001 | 服务器内部错误 |

