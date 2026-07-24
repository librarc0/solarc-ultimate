/**
 * 公开排行榜 API（无需认证）
 * 基础 URL: /api/v1/public
 */
import axios from 'axios'

const baseURL = (import.meta.env.VITE_API_BASE_URL ?? '/api/v1') + '/public'

const publicApi = axios.create({ baseURL, timeout: 10000 })

// ── 赛季接口 ──────────────────────────────

export interface SeasonOut {
  id: number
  name: string
  year: number
  start_date: string | null
  end_date: string | null
  description: string | null
  is_active: boolean
  created_at: string
}

export async function fetchSeasons(): Promise<SeasonOut[]> {
  const res = await publicApi.get('/seasons')
  return res.data
}

// ── 队伍接口 ──────────────────────────────

export interface TournamentRecordOut {
  id: number
  tournament_name: string
  level: string
  month: string
  wins: number
  losses: number
  draws: number
  forfeits: number
  total_games: number
  win_rate: number
  points_scored: number
  points_conceded: number
  pool: string
  final_rank: number
  computed_score: number
}

export interface ExternalTeamListItem {
  id: number
  season_id: number | null
  name: string
  rank: number
  rank_change: number
  total_score: number
  avg_score: number
  tournament_count: number
  wins: number
  losses: number
  draws: number
  total_games: number
  win_rate: number
  points_scored: number
  points_conceded: number
  net_points: number
  province: string | null
  city: string | null
  last_updated: string
}

export interface ExternalTeamDetail extends ExternalTeamListItem {
  forfeits: number
  prev_rank: number
  tournament_records: TournamentRecordOut[]
}

export interface ExternalTeamForMatch {
  name: string
  total_score: number
  rank: number
}

export interface TeamRankingListResponse {
  total: number
  page: number
  page_size: number
  season_id: number | null
  items: ExternalTeamListItem[]
}

export async function fetchTeamRankings(params?: {
  season_id?: number
  search?: string
  sort_by?: string
  order?: string
  province_filter?: string
  page?: number
  page_size?: number
}): Promise<TeamRankingListResponse> {
  const res = await publicApi.get('/team-rankings', { params })
  return res.data
}

export async function fetchTeamDetail(teamName: string, seasonId?: number): Promise<ExternalTeamDetail> {
  const res = await publicApi.get(`/team-rankings/${encodeURIComponent(teamName)}`, {
    params: seasonId ? { season_id: seasonId } : {},
  })
  return res.data
}

export async function fetchTeamsForMatch(search?: string, seasonId?: number): Promise<ExternalTeamForMatch[]> {
  const params: Record<string, unknown> = {}
  if (search) params.search = search
  if (seasonId) params.season_id = seasonId
  const res = await publicApi.get('/team-rankings/for-match', { params })
  return res.data
}

/** 支持跨赛季对比：seasonIds[i] 对应 teamNames[i] */
export async function fetchTeamsCompare(
  teamNames: string[],
  seasonIds?: (number | null)[],
): Promise<ExternalTeamDetail[]> {
  const params: Record<string, string> = {
    teams: teamNames.join(','),
  }
  if (seasonIds && seasonIds.some((s) => s != null)) {
    params.season_ids = seasonIds.map((s) => String(s ?? '')).join(',')
  }
  const res = await publicApi.get('/team-rankings/compare', { params })
  return res.data
}

export async function fetchTeamStrength(teamName: string, seasonId?: number): Promise<{
  name: string
  total_score: number
  strength: number
  rank: number
}> {
  const res = await publicApi.get(
    `/team-rankings-strength/${encodeURIComponent(teamName)}`,
    { params: seasonId ? { season_id: seasonId } : {} },
  )
  return res.data
}

export interface TeamStrengthV2 {
  name: string
  total_score: number
  strength: number
  rank: number
  season_id: number | null
  calibrated_mu: number
  calibrated_sigma: number
  team_id: number
}

export async function fetchTeamStrengthV2(
  teamName: string,
  teamId: number,
  seasonId?: number,
): Promise<TeamStrengthV2> {
  const params: Record<string, unknown> = { team_id: teamId }
  if (seasonId) params.season_id = seasonId
  const res = await publicApi.get(
    `/team-rankings-strength-v2/${encodeURIComponent(teamName)}`,
    { params },
  )
  return res.data
}

/** 批量获取全榜最高/最低分，用于外战强度线性映射 */
export async function fetchScoreRange(seasonId?: number): Promise<{ min: number; max: number }> {
  const params: Record<string, unknown> = { page: 1, page_size: 1, sort_by: 'total_score', order: 'desc' }
  if (seasonId) params.season_id = seasonId
  const res = await publicApi.get('/team-rankings', { params })
  const data: TeamRankingListResponse = res.data
  if (!data.total) return { min: 0, max: 0 }
  const max = data.items[0]?.total_score ?? 0

  const resMin = await publicApi.get('/team-rankings', {
    params: { ...params, page: data.total, order: 'asc' },
  })
  const min = (resMin.data as TeamRankingListResponse).items[0]?.total_score ?? 0
  return { min, max }
}
