import { expect, test } from '@playwright/test'

const LIVE_API_BASE = process.env.E2E_BACKEND_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'

function mockAuth(page: import('@playwright/test').Page) {
  return page.addInitScript(() => {
    localStorage.setItem('access_token', 'e2e-token')
    localStorage.setItem('user_role', 'member')
    localStorage.setItem('team_id', '1')
  })
}

function mockCurrentUser(page: import('@playwright/test').Page) {
  return page.route('**/api/v1/players/me**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 101,
        team_id: 1,
        username: 'e2e-member',
        display_name: 'E2E Member',
        role: 'member',
        status: 'active',
        is_superadmin: false,
      }),
    })
  })
}

async function ensureAuthState(page: import('@playwright/test').Page) {
  await page.addInitScript(() => {
    localStorage.setItem('access_token', 'e2e-token')
    localStorage.setItem('user_role', 'member')
    localStorage.setItem('team_id', '1')
  })
}

test.describe('Live Draft Concurrency', () => {
  test('second user sees lock conflict and is redirected to match list', async ({ page }) => {
    await mockAuth(page)
    await mockCurrentUser(page)

    await page.route('**/api/v1/players?**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 101,
            username: 'e2e-member',
            display_name: 'E2E Member',
          },
        ]),
      })
    })

    await page.route('**/api/v1/matches?**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      })
    })

    await page.route('**/api/v1/matches/drafts/1001**', async (route) => {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: {
            code: 'DRAFT_LOCKED',
            message: '正在有人录入该比赛',
            locked_by: '队友A',
          },
        }),
      })
    })

    await page.goto('/matches/live?draft_id=1001')

    await expect(page).toHaveURL(/\/matches\/list/)
    await expect(page.getByText('正在有人录入该比赛（队友A）')).toBeVisible()
  })

  test('first user can enter live page when draft is available', async ({ page }) => {
    await mockAuth(page)
    await mockCurrentUser(page)

    await page.route('**/api/v1/matches/drafts/1002**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1002,
          match_type: 'internal',
          match_date: '2026-03-20T12:00:00Z',
          team_a_ids: [101],
          team_b_ids: [102],
          team_a_score: 0,
          team_b_score: 0,
          status: 'draft',
          data_level: 3,
          notes: '并发测试草稿',
          duration_seconds: 0,
          last_event_seq: 0,
          expires_at: '2026-03-22T12:00:00Z',
          snapshot: { is_halftime: false },
          events: [],
        }),
      })
    })

    await page.route('**/api/v1/players?**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 101,
            username: 'e2e-member',
            display_name: 'E2E Member',
          },
          {
            id: 102,
            username: 'teammate',
            display_name: 'Teammate',
          },
        ]),
      })
    })

    await page.goto('/matches/live?draft_id=1002')

    await expect(page).toHaveURL(/\/matches\/live\?draft_id=1002/)
    await expect(page.getByText('比赛实况')).toBeVisible()
  })

  test('user can retry and enter after lock conflict is cleared', async ({ page }) => {
    await mockAuth(page)
    await mockCurrentUser(page)

    let draftRequestCount = 0

    await page.route('**/api/v1/matches/drafts/1003**', async (route) => {
      draftRequestCount += 1
      if (draftRequestCount === 1) {
        await route.fulfill({
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({
            detail: {
              code: 'DRAFT_LOCKED',
              message: '正在有人录入该比赛',
              locked_by: '队友B',
            },
          }),
        })
        return
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1003,
          match_type: 'internal',
          match_date: '2026-03-20T12:00:00Z',
          team_a_ids: [101],
          team_b_ids: [102],
          team_a_score: 0,
          team_b_score: 0,
          status: 'draft',
          data_level: 3,
          notes: '重试进入草稿',
          duration_seconds: 0,
          last_event_seq: 0,
          expires_at: '2026-03-22T12:00:00Z',
          snapshot: { is_halftime: false },
          events: [],
        }),
      })
    })

    await page.route('**/api/v1/players?**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 101,
            username: 'e2e-member',
            display_name: 'E2E Member',
          },
          {
            id: 102,
            username: 'teammate2',
            display_name: 'Teammate 2',
          },
        ]),
      })
    })

    await page.route('**/api/v1/matches?**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 1003,
            match_type: 'internal',
            match_date: '2026-03-20T12:00:00Z',
            team_a_score: 0,
            team_b_score: 0,
            status: 'draft',
            data_level: 3,
            duration_seconds: 0,
            countdown_seconds: 3600,
            created_by_name: '队友B',
          },
        ]),
      })
    })

    await page.goto('/matches/live?draft_id=1003')
    await expect(page).toHaveURL(/\/matches\/list/)
    await expect(page.getByText('正在有人录入该比赛（队友B）')).toBeVisible()

    await page.goto('/matches/live?draft_id=1003')
    await expect(page).toHaveURL(/\/matches\/live\?draft_id=1003/)
    await expect(page.getByRole('button', { name: '保存待录入' })).toBeVisible()
  })

  test('same account can reopen draft in another tab without lock conflict', async ({ browser }) => {
    const context = await browser.newContext()

    await context.route('**/api/v1/players/me**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 101,
          team_id: 1,
          username: 'e2e-member',
          display_name: 'E2E Member',
          role: 'member',
          status: 'active',
          is_superadmin: false,
        }),
      })
    })

    await context.route('**/api/v1/players?**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 101, username: 'e2e-member', display_name: 'E2E Member' },
          { id: 102, username: 'teammate3', display_name: 'Teammate 3' },
        ]),
      })
    })

    await context.route('**/api/v1/matches/drafts/1004**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1004,
          match_type: 'internal',
          match_date: '2026-03-20T12:00:00Z',
          team_a_ids: [101],
          team_b_ids: [102],
          team_a_score: 0,
          team_b_score: 0,
          status: 'draft',
          data_level: 3,
          notes: '同账号多标签测试',
          duration_seconds: 0,
          last_event_seq: 0,
          expires_at: '2026-03-22T12:00:00Z',
          snapshot: { is_halftime: false },
          events: [],
        }),
      })
    })

    const page1 = await context.newPage()
    const page2 = await context.newPage()

    try {
      await ensureAuthState(page1)
      await page1.goto('/matches/live?draft_id=1004')
      await expect(page1).toHaveURL(/\/matches\/live\?draft_id=1004/)
      await expect(page1.getByRole('button', { name: '保存待录入' })).toBeVisible()

      await ensureAuthState(page2)
      await page2.goto('/matches/live?draft_id=1004')
      await expect(page2).toHaveURL(/\/matches\/live\?draft_id=1004/)
      await expect(page2.getByRole('button', { name: '保存待录入' })).toBeVisible()
      await expect(page2.getByText('正在有人录入该比赛')).toHaveCount(0)
    } finally {
      await context.close()
    }
  })

  test('second user can enter after owner releases lock via back button', async ({ browser }) => {
    const context = await browser.newContext()

    await context.route('**/api/v1/matches/predict**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) })
    })

    // Single handler dispatches both GET draft data and POST release
    await context.route('**/api/v1/matches/drafts/1005**', async (route) => {
      const url = route.request().url()
      if (url.includes('/release')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) })
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1005,
          match_type: 'internal',
          match_date: '2026-03-20T12:00:00Z',
          team_a_ids: [101],
          team_b_ids: [102],
          team_a_score: 0,
          team_b_score: 0,
          status: 'draft',
          data_level: 3,
          notes: '锁释放重入测试',
          duration_seconds: 0,
          last_event_seq: 0,
          expires_at: '2026-03-22T12:00:00Z',
          snapshot: { is_halftime: false },
          events: [],
        }),
      })
    })

    await context.route('**/api/v1/players/me**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 101,
          team_id: 1,
          username: 'e2e-owner',
          display_name: 'E2E Owner',
          role: 'member',
          status: 'active',
          is_superadmin: false,
        }),
      })
    })

    await context.route('**/api/v1/players?**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 101, username: 'e2e-owner', display_name: 'E2E Owner' },
          { id: 102, username: 'e2e-player2', display_name: 'Player 2' },
        ]),
      })
    })

    const page1 = await context.newPage()
    const page2 = await context.newPage()

    try {
      // Owner enters live page — ?draft_id path loads directly, no setup dialog
      await ensureAuthState(page1)
      await page1.goto('/matches/live?draft_id=1005')
      await expect(page1.getByRole('button', { name: '保存待录入' })).toBeVisible()

      // Owner clicks nav-bar back → handleBack fires POST /release
      const releasePromise = page1.waitForRequest(/\/matches\/drafts\/1005\/release/)
      await page1.locator('.van-nav-bar__left').click()
      await releasePromise

      // Second user enters same draft — lock released, should not be blocked
      await ensureAuthState(page2)
      await page2.goto('/matches/live?draft_id=1005')
      await expect(page2).toHaveURL(/\/matches\/live\?draft_id=1005/)
      await expect(page2.getByRole('button', { name: '保存待录入' })).toBeVisible()
      await expect(page2.getByText('正在有人录入该比赛')).toHaveCount(0)
    } finally {
      await context.close()
    }
  })
})

async function apiRegister(request: import('@playwright/test').APIRequestContext, username: string) {
  const res = await request.post(`${LIVE_API_BASE}/auth/register`, {
    data: {
      username,
      email: `${username}@e2e.test`,
      password: 'pw123456',
    },
  })
  expect(res.ok()).toBeTruthy()
}

async function apiLogin(request: import('@playwright/test').APIRequestContext, username: string) {
  const form = new URLSearchParams()
  form.set('username', username)
  form.set('password', 'pw123456')
  const res = await request.post(`${LIVE_API_BASE}/auth/login`, {
    data: form.toString(),
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  expect(res.ok()).toBeTruthy()
  const payload = await res.json()
  return payload.access_token as string
}

test('live backend concurrency lock works for two real users @live', async ({ browser, request }) => {
  const enabled = process.env.E2E_LIVE_BACKEND === '1'
  test.skip(!enabled, 'Set E2E_LIVE_BACKEND=1 to run live backend E2E test')

  const owner = `e2e_owner_${Date.now()}`
  const member = `e2e_member_${Date.now()}`

  await apiRegister(request, owner)
  await apiRegister(request, member)

  const ownerToken = await apiLogin(request, owner)
  const memberToken = await apiLogin(request, member)

  const createTeamResp = await request.post(`${LIVE_API_BASE}/team/create`, {
    data: { team_name: `E2E Team ${Date.now()}` },
    headers: { Authorization: `Bearer ${ownerToken}` },
  })
  expect(createTeamResp.ok()).toBeTruthy()
  const teamId = (await createTeamResp.json()).team_id as number

  const applyResp = await request.post(`${LIVE_API_BASE}/team/apply`, {
    data: { team_id: teamId },
    headers: { Authorization: `Bearer ${memberToken}` },
  })
  expect(applyResp.ok()).toBeTruthy()

  const pendingResp = await request.get(`${LIVE_API_BASE}/players?status=pending`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
  })
  expect(pendingResp.ok()).toBeTruthy()
  const pending = (await pendingResp.json()) as Array<{ id: number; username: string }>
  const pendingMember = pending.find((p) => p.username === member)
  expect(pendingMember).toBeTruthy()

  const approveResp = await request.patch(`${LIVE_API_BASE}/players/${pendingMember!.id}/status`, {
    data: { status: 'active' },
    headers: { Authorization: `Bearer ${ownerToken}` },
  })
  expect(approveResp.ok()).toBeTruthy()

  const ownerMeResp = await request.get(`${LIVE_API_BASE}/players/me`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
  })
  expect(ownerMeResp.ok()).toBeTruthy()
  const ownerId = (await ownerMeResp.json()).id as number

  const draftResp = await request.post(`${LIVE_API_BASE}/matches/drafts`, {
    data: {
      match_date: new Date().toISOString().slice(0, 10),
      match_type: 'internal',
      team_a_ids: [ownerId],
      team_b_ids: [pendingMember!.id],
      data_level: 3,
      notes: 'live backend e2e draft',
    },
    headers: { Authorization: `Bearer ${ownerToken}` },
  })
  expect(draftResp.ok()).toBeTruthy()
  const draftId = (await draftResp.json()).id as number

  const ownerContext = await browser.newContext()
  const memberContext = await browser.newContext()

  await ownerContext.addInitScript((token) => {
    localStorage.setItem('access_token', token)
    localStorage.setItem('user_role', 'owner')
  }, ownerToken)
  await memberContext.addInitScript((token) => {
    localStorage.setItem('access_token', token)
    localStorage.setItem('user_role', 'member')
  }, memberToken)

  const ownerPage = await ownerContext.newPage()
  const memberPage = await memberContext.newPage()

  try {
    // Phase 1: Owner enters live page, member is blocked
    await ownerPage.goto(`/matches/live?draft_id=${draftId}`)
    await expect(ownerPage.getByText('比赛实况')).toBeVisible()

    await memberPage.goto(`/matches/live?draft_id=${draftId}`)
    await expect(memberPage).toHaveURL(/\/matches\/list/)
    await expect(memberPage.getByText('正在有人录入该比赛')).toBeVisible()

    // Phase 2: Owner releases lock via nav back button
    const releasePromise = ownerPage.waitForRequest(/\/matches\/drafts\/\d+\/release/)
    await ownerPage.locator('.van-nav-bar__left').click()
    await releasePromise

    // Phase 3: Member re-enters — lock released, should succeed
    await memberPage.goto(`/matches/live?draft_id=${draftId}`)
    await expect(memberPage).toHaveURL(new RegExp(`/matches/live\\?draft_id=${draftId}`))
    await expect(memberPage.getByRole('button', { name: '保存待录入' })).toBeVisible()
  } finally {
    await ownerContext.close()
    await memberContext.close()
  }
})
