export interface PlayerPublic {
  id: number
  team_id: number | null
  username: string
  display_name: string | null
  email?: string | null
  role: string
  status: string
  gender?: string | null
  jersey_number?: number | null
  is_superadmin?: boolean
  show_in_rankings?: boolean
  mu: number
  sigma: number
  conservative_rating: number
  avatar_url?: string | null
  total_matches: number
  total_wins: number
  total_goals: number
  total_assists: number
  total_defenses: number
  total_plus_minus: number
  total_turnovers?: number
}

export interface TeamInfo {
  id: number
  name: string
  logo_url?: string | null
  member_count: number
  my_status: string
}

export interface MatchStatItem {
  match_id: number
  match_date: string
  goals: number
  assists: number
  defenses: number
  plus_minus: number
  is_winner: boolean
}

export interface PostItem {
  id: number
  author_id: number
  author_name: string
  content: string
  parent_id: number | null
  created_at: string
  replies: PostItem[]
}

export interface RankingItem {
  rank: number
  player_id: number
  display_name: string | null
  gender?: string | null
  jersey_number?: number | null
  rank_change?: number | null
  conservative_rating: number
  mu?: number
  sigma?: number
  total_matches: number
  total_wins: number
  total_goals: number
  total_assists: number
  total_defenses: number
  total_plus_minus: number
  total_turnovers: number
  is_new?: boolean
  composite_score: number
  attendance_rate?: number
  progress_speed: number
}

export interface RankingResponse {
  items: RankingItem[]
  page: number
  page_size: number
}

export interface MyRanksResponse {
  total: number
  ranks: {
    composite?: number | null
    conservative?: number | null
    progress?: number | null
    goals?: number | null
    assists?: number | null
    plus_minus?: number | null
    turnovers?: number | null
  }
}

export interface SeasonOut {
  id: number
  name: string
  year: number
  is_active: boolean
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

export interface ExternalTeamDetail extends ExternalTeamListItem {
  forfeits: number
  prev_rank: number
  tournament_records: TournamentRecordOut[]
}

export interface MatchListItem {
  id: number
  match_type: string
  match_date: string
  team_a_score: number
  team_b_score: number
  status: string
  data_level: number
  notes: string | null
  created_by_name: string | null
  duration_seconds?: number | null
  lock_status: string
  spirit_scored: boolean
  spirit_total_score: number | null
}

export interface MatchParticipant {
  player_id: number
  player_name: string
  team_side: string
  goals: number | null
  assists: number | null
  defenses: number | null
  turnovers: number | null
  plus_minus: number | null
  is_mvp: boolean
}

export interface MatchDetail {
  id: number
  match_type: string
  match_date: string
  team_a_score: number
  team_b_score: number
  status: string
  data_level: number
  notes: string | null
  created_by_name: string
  participants: MatchParticipant[]
  spirit_score?: { total_score: number } | null
}

export interface MatchEventItem {
  id: number
  event_type: string
  team_side: string | null
  player_id: number | null
  assist_player_id: number | null
  is_break: boolean | null
  elapsed_seconds: number | null
}

export interface ScheduleEventListItem {
  id: number
  title: string
  event_type: string
  start_date: string
  end_date: string
  status: string
  linked_match_id: number | null
  attendance_count: number
  total_players: number
  yes_count: number
  sdl_count: number
  leave_count: number
  no_count: number
  not_submitted_count: number
}

export interface ScheduleEventRead {
  id: number
  team_id: number
  title: string
  event_type: string
  start_date: string
  end_date: string
  description: string | null
  status: string
  created_by: number
  linked_match_id: number | null
  created_at: string
  updated_at: string
}

export interface AttendanceRead {
  id: number
  event_id: number
  player_id: number
  player_name: string
  player_display_name: string | null
  status: 'yes' | 'leave' | 'sdl'
  submitted_at: string
  updated_at: string
}
