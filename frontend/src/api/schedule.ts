import api from '@/api'

export interface ScheduleEvent {
  id: number
  title: string
  event_type: 'game' | 'training' | 'internal' | 'other'
  status: 'draft' | 'published'
  start_date: string
  end_date: string
  description?: string
  notes?: string
  linked_match_id?: number
  attendance_count?: number
  total_players?: number
  yes_count?: number
  sdl_count?: number
  leave_count?: number
  no_count?: number
  not_submitted_count?: number
}

export interface ScheduleReminderResponse {
  message: string
  reminded: number
  events?: number
}

export interface AttendanceSummary {
  yes: PlayerBrief[]
  leave: PlayerBrief[]
  sdl: PlayerBrief[]
  not_submitted: PlayerBrief[]
  no?: PlayerBrief[] // legacy compatibility only
}

export interface PlayerBrief {
  player_id: number
  player_name: string
  display_name?: string
}

export interface LinePlayerInfo {
  player_id: number
  player_name: string
  display_name?: string
  conservative_rating: number
  gender?: string | null
  jersey_number?: number | null
  attendance_status?: string
}


export interface ScheduleLineRead {
  id: number
  line_name: string
  line_type: string
  round_number: number
  order_index: number
  players: LinePlayerInfo[]
}

export interface ScheduleLineDivisionRead {
  id: number
  event_id: number
  division_method: string
  total_rounds: number
  lines: ScheduleLineRead[]
}

export interface ScheduleLineTemplate {
  id: number
  event_type: 'game' | 'training' | 'internal' | 'other'
  template_name: string
  line_count: number
  updated_at: string
}

export interface DivisionForMatch {
  event_id: number
  event_type: string
  total_rounds: number
  rounds: Record<string, { id: number; line_name: string; line_type: string; player_ids: number[] }[]>
}

export interface SmartLinePlayer {
  player_id: number
  player_name: string
  display_name?: string | null
  gender?: string | null
  role: 'handler' | 'cutter'
  ability_score: number
  chemistry_score: number
  offense_score: number
  scoring_score: number
  recent_form_score: number
  total_score: number
  reason: string
}

export interface SmartLineChemistryPair {
  player_a_id: number
  player_b_id: number
  player_a_name: string
  player_b_name: string
  chemistry_score: number
  combo_count: number
  co_matches: number
  summary: string
}

export interface SmartLineGroup {
  line_name: string
  line_type: string
  total_score: number
  chemistry_average: number
  player_ids: number[]
  players: SmartLinePlayer[]
  chemistry_pairs: SmartLineChemistryPair[]
}

export interface SmartLineAnalyzeResponse {
  event_id?: number | null
  applied_to_match: boolean
  lines: SmartLineGroup[]
  o_line: SmartLineGroup
  d_lines: SmartLineGroup[]
  rationale: Record<string, unknown>
}

// ─── Events ───────────────────────────────────────────────────────────────────

export const scheduleApi = {
  getEvents: (params: { start_date?: string; end_date?: string; event_type?: string }) =>
    api.get<ScheduleEvent[]>('/schedule-events', { params }).then(r => r.data),

  getEvent: (id: number) =>
    api.get<ScheduleEvent>(`/schedule-events/${id}`).then(r => r.data),

  createEvent: (body: Partial<ScheduleEvent>) =>
    api.post<ScheduleEvent>('/schedule-events', body).then(r => r.data),

  updateEvent: (id: number, body: Partial<ScheduleEvent>) =>
    api.put<ScheduleEvent>(`/schedule-events/${id}`, body).then(r => r.data),

  deleteEvent: (id: number) =>
    api.delete(`/schedule-events/${id}`),

  publishEvent: (id: number) =>
    api.post(`/schedule-events/${id}/publish`),

  unpublishEvent: (id: number) =>
    api.post(`/schedule-events/${id}/unpublish`),

  remindEvent: (id: number) =>
    api.post<ScheduleReminderResponse>(`/schedule-events/${id}/remind`).then(r => r.data),

  remindPendingEvents: () =>
    api.post<ScheduleReminderResponse>('/schedule-events/remind/pending').then(r => r.data),

  getLinkableEvents: (matchType?: 'external' | 'internal') =>
    api.get<ScheduleEvent[]>('/schedule-events/for-match/linkable', {
      params: matchType ? { match_type: matchType } : undefined,
    }).then(r => r.data),

  // ─── Attendance ─────────────────────────────────────────────────────────────

  getMyAttendance: (eventId: number) =>
    api.get<{ status: string }>(`/schedule-attendance/${eventId}/me`).then(r => r.data),

  submitMyAttendance: (eventId: number, status: string) =>
    api.put(`/schedule-attendance/${eventId}/me`, { status }),

  getAttendanceSummary: (eventId: number) =>
    api.get<AttendanceSummary>(`/schedule-attendance/${eventId}/summary`).then(r => r.data),

  // ─── Lines ───────────────────────────────────────────────────────────────────

  getDivision: (eventId: number) =>
    api.get<ScheduleLineDivisionRead>(`/schedule-lines/${eventId}/division`).then(r => r.data),

  createOrResetDivision: (eventId: number, body: { division_method: string; total_rounds: number }) =>
    api.post<ScheduleLineDivisionRead>(`/schedule-lines/${eventId}/division`, body).then(r => r.data),

  updateDivision: (eventId: number, body: { total_rounds: number }) =>
    api.put<ScheduleLineDivisionRead>(`/schedule-lines/${eventId}/division`, body).then(r => r.data),

  deleteRound: (eventId: number, roundNumber: number) =>
    api.delete<ScheduleLineDivisionRead>(`/schedule-lines/${eventId}/division/rounds/${roundNumber}`).then(r => r.data),

  createLine: (eventId: number, body: { line_name: string; line_type: string; round_number: number; order_index: number }) =>
    api.post<ScheduleLineRead>(`/schedule-lines/${eventId}/division/lines`, body).then(r => r.data),

  updateLine: (eventId: number, lineId: number, body: { line_name?: string; order_index?: number }) =>
    api.put<ScheduleLineRead>(`/schedule-lines/${eventId}/division/lines/${lineId}`, body).then(r => r.data),

  deleteLine: (eventId: number, lineId: number) =>
    api.delete(`/schedule-lines/${eventId}/division/lines/${lineId}`),

  addPlayerToLine: (eventId: number, lineId: number, playerId: number) =>
    api.post<ScheduleLineRead>(`/schedule-lines/${eventId}/division/lines/${lineId}/players`, { player_id: playerId }).then(r => r.data),

  removePlayerFromLine: (eventId: number, lineId: number, playerId: number) =>
    api.delete(`/schedule-lines/${eventId}/division/lines/${lineId}/players/${playerId}`),

  autoAssign: (eventId: number, body: { method: string; num_lines: number; round_number: number; player_ids?: number[] }) =>
    api.post<ScheduleLineDivisionRead>(`/schedule-lines/${eventId}/division/auto-assign`, body).then(r => r.data),

  listDivisionTemplates: (eventType: 'game' | 'training') =>
    api.get<ScheduleLineTemplate[]>('/schedule-lines/templates', { params: { event_type: eventType } }).then(r => r.data),

  saveDivisionTemplate: (eventId: number, templateName: string) =>
    api.post<ScheduleLineTemplate>(`/schedule-lines/${eventId}/division/templates`, { template_name: templateName }).then(r => r.data),

  applyDivisionTemplate: (eventId: number, templateId: number) =>
    api.post<ScheduleLineDivisionRead>(`/schedule-lines/${eventId}/division/templates/${templateId}/apply`).then(r => r.data),

  getDivisionForMatch: (eventId: number) =>
    api.get<DivisionForMatch>(`/schedule-lines/${eventId}/division/for-match`).then(r => r.data),

  analyzeSmartExternalLines: (
    body: {
      player_ids: number[]
      schedule_event_id?: number
      apply_to_match?: boolean
      max_line_size?: number
      d_line_count?: 1 | 2
      recent_matches?: number
      handler_ratio?: number
      cutter_ratio?: number
    },
  ) => api.post<SmartLineAnalyzeResponse>('/schedule-lines/smart-external-lines', body).then(r => r.data),

  smartExternalLines: (
    eventId: number,
    body: { player_ids: number[]; apply_to_match?: boolean; recent_matches?: number; handler_ratio?: number; cutter_ratio?: number },
  ) => api.post<SmartLineAnalyzeResponse>(`/schedule-lines/${eventId}/division/smart-external-lines`, body).then(r => r.data),

  analyzeAssignedLines: (body: {
    lines: Array<{ line_name: string; line_type: string; player_ids: number[] }>
    recent_matches?: number
    handler_ratio?: number
    cutter_ratio?: number
  }) => api.post<SmartLineAnalyzeResponse>('/schedule-lines/analyze-assigned-lines', body).then(r => r.data),
}

export interface ChemistryPairItem {
  player_a_id: number
  player_b_id: number
  chemistry_score: number
  co_matches: number
}

export async function fetchChemistryPairs(playerIds: number[]): Promise<ChemistryPairItem[]> {
  if (playerIds.filter(id => id > 0).length < 2) return []
  const res = await api.post<ChemistryPairItem[]>('/players/chemistry-pairs', {
    player_ids: playerIds.filter(id => id > 0), // 过滤掉负数 guest id
  })
  return res.data
}

export default scheduleApi
