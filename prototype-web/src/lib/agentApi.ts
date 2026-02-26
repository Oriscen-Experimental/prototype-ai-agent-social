import type { Group, Profile } from '../types'
import { getClientId } from './clientId'
import type { SortingAnswers, SortingQuizResult } from './sortingQuiz'

// ========== Orchestrate API Types ==========

export type FormQuestionOption = {
  label: string
  value: unknown
  followUp?: FormQuestion[] | null  // Nested questions if this option is selected
}

export type FormQuestion = {
  param: string
  question: string
  options: FormQuestionOption[]
}

export type MessageContent = {
  text: string
}

export type ResultsContent = {
  results: { people?: Profile[]; things?: Group[] }
  summary?: string | null
}

export type FormContent = {
  toolName: string
  toolArgs: Record<string, unknown>
  questions: FormQuestion[]
}

// ========== UI Block Types ==========

export type BookingStatusBlock = {
  type: 'booking_status'
  bookingTaskId: string
  bookingStatus: string
  acceptedCount: number
  targetCount: number
}

export type BookingResultBlock = {
  type: 'booking_result'
  activity: string
  location: string
  profiles: Profile[]
  bookedTime?: string | null
  bookedLocation?: string | null
  selectedSlot?: string | null
}

export type CancelStatusBlock = {
  type: 'cancel_status'
  cancelFlowId: string
  cancelStatus: string
}

export type UIBlock =
  | { type: 'text'; text: string }
  | { type: 'profiles'; profiles: Profile[]; layout?: 'compact' | 'full' }
  | { type: 'groups'; groups: Group[]; layout?: 'compact' | 'full' }
  | { type: 'form'; form: FormContent }
  | BookingStatusBlock
  | BookingResultBlock
  | CancelStatusBlock

export type OrchestrateResponse = {
  sessionId: string
  // New: UI blocks array (primary)
  blocks?: UIBlock[] | null
  // Legacy fields (for backward compatibility)
  type?: 'message' | 'results' | 'form' | null
  content?: MessageContent | ResultsContent | FormContent | null
  trace?: Record<string, unknown> | null
}

/**
 * Normalize response to always have blocks array.
 * Converts legacy type+content format to blocks if needed.
 */
export function normalizeResponse(res: OrchestrateResponse): { sessionId: string; blocks: UIBlock[]; trace?: Record<string, unknown> | null } {
  // If blocks already present, use them
  if (res.blocks && res.blocks.length > 0) {
    return { sessionId: res.sessionId, blocks: res.blocks, trace: res.trace }
  }

  // Convert legacy format to blocks
  const blocks: UIBlock[] = []

  if (res.type === 'message' && res.content) {
    const content = res.content as MessageContent
    if (content.text?.trim()) {
      blocks.push({ type: 'text', text: content.text })
    }
  } else if (res.type === 'results' && res.content) {
    const content = res.content as ResultsContent
    if (content.summary?.trim()) {
      blocks.push({ type: 'text', text: content.summary })
    }
    if (content.results?.people?.length) {
      blocks.push({ type: 'profiles', profiles: content.results.people, layout: 'compact' })
    }
    if (content.results?.things?.length) {
      blocks.push({ type: 'groups', groups: content.results.things, layout: 'compact' })
    }
  } else if (res.type === 'form' && res.content) {
    const content = res.content as FormContent
    blocks.push({ type: 'form', form: content })
  }

  return { sessionId: res.sessionId, blocks, trace: res.trace }
}

export type FormSubmission = {
  toolName: string
  toolArgs: Record<string, unknown>
  answers: Record<string, unknown>
}

export type PlannerModel = 'light' | 'medium' | 'heavy'

export type UserContext = {
  name: string
  city?: string
  interests: string[]
  goals?: string[]
  vibe?: string
  archetype?: string
}

export type OrchestrateRequest =
  | { sessionId?: string | null; message: string; plannerModel?: PlannerModel; userContext?: UserContext; reset?: boolean }
  | { sessionId: string; formSubmission: FormSubmission; plannerModel?: PlannerModel; userContext?: UserContext; reset?: boolean }
  | { sessionId: string; reset: true; plannerModel?: PlannerModel; userContext?: UserContext }

function apiBase(): string {
  const raw = import.meta.env.VITE_API_BASE_URL as string | undefined
  const s = (raw ?? '').trim()
  return s.endsWith('/') ? s.slice(0, -1) : s
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const url = `${apiBase()}${path}`
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Client-Id': getClientId() },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Request failed: ${res.status} ${res.statusText}${text ? ` - ${text}` : ''}`)
  }
  return (await res.json()) as T
}

async function getJson<T>(path: string): Promise<T> {
  const url = `${apiBase()}${path}`
  const res = await fetch(url, {
    headers: { 'X-Client-Id': getClientId() },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Request failed: ${res.status} ${res.statusText}${text ? ` - ${text}` : ''}`)
  }
  return (await res.json()) as T
}

export async function orchestrate(body: OrchestrateRequest): Promise<OrchestrateResponse> {
  return await postJson<OrchestrateResponse>('/api/v1/orchestrate', body)
}

// ========== Booking API ==========

export type BookingStatusResponse = {
  taskId: string
  status: string
  activity: string
  location: string
  desiredTime: string | null
  acceptedCount: number
  targetCount: number
  currentBatch: number
  totalCandidates: number
  totalInvitations: number
  speedMultiplier: number
  invitations: {
    id: string
    userId: string
    nickname: string
    status: string
    batchIndex: number
    isMock: boolean
  }[]
  acceptedUsers: {
    id: string
    nickname: string
    location: string
    occupation: string
    interests: string[]
    matchScore: number
  }[]
}

export type BookingNotification = {
  type: string
  message: string
  profiles?: Profile[]
  bookingTaskId?: string
  timestamp: number
  finalSlots?: string[]
  bookedTime?: string | null
  bookedLocation?: string | null
  bookedIsoStart?: string | null
  bookedIsoEnd?: string | null
  activity?: string
  location?: string
  // Cancel flow fields
  cancelFlowId?: string
  responses?: { userId: string; vote: string; profile: Profile }[]
  allAccepted?: boolean
  remainingCount?: number
  departedCount?: number
  filled?: number
  totalNeeded?: number
}

// ========== Cancel Flow API ==========

export type RescheduleResponseEntry = {
  userId: string
  vote: 'accept' | 'decline' | 'pending' | 'expired'
  profile: Profile
}

export type CancelStatusResponse = {
  cancelFlowId: string
  taskId: string
  status: string
  intention: string | null
  cancellingUserId: string
  activity: string
  location: string
  bookedTime: string | null
  bookedLocation: string | null
  targetCount: number
  remainingParticipants: Profile[]
  departedParticipants: Profile[]
  rescheduleResponses: RescheduleResponseEntry[]
  newSlots: string[]
  backfillApproved: boolean
  backfillInvited: number
  backfillAccepted: number
  backfillAcceptedUsers: Profile[]
  replacementTaskId: string | null
}

export async function getCancelStatus(cancelFlowId: string): Promise<CancelStatusResponse> {
  return await getJson<CancelStatusResponse>(`/api/v1/cancel/status/${cancelFlowId}`)
}

export async function getBookingStatus(taskId: string): Promise<BookingStatusResponse> {
  return await getJson<BookingStatusResponse>(`/api/v1/booking/status/${taskId}`)
}

export async function setBookingSpeed(taskId: string, multiplier: number): Promise<void> {
  await postJson('/api/v1/booking/speed', { taskId, multiplier })
}

export async function getBookingNotifications(sessionId: string): Promise<{ notifications: BookingNotification[] }> {
  return await getJson<{ notifications: BookingNotification[] }>(`/api/v1/booking/notifications/${sessionId}`)
}

export type InvitationDetails = {
  invitationId: string
  status: string
  activity: string
  location: string
  desiredTime: string | null
  invitedBy: string | null
  sentAt: number
}

export async function getInvitation(invitationId: string): Promise<InvitationDetails> {
  return await getJson<InvitationDetails>(`/api/v1/invitation/${invitationId}`)
}

export async function respondToInvitation(
  invitationId: string,
  response: 'accept' | 'decline',
): Promise<{ ok: boolean; expired?: boolean; status?: string }> {
  return await postJson(`/api/v1/invitation/${invitationId}/respond`, { response })
}

export type PendingInvitation = {
  invitationId: string
  taskId: string
  activity: string
  location: string
  desiredTime: string | null
  sentAt: number
}

export async function getPendingInvitations(userId: string): Promise<PendingInvitation[]> {
  const url = `${apiBase()}/api/v1/invitations/pending`
  const res = await fetch(url, {
    headers: { 'X-Client-Id': getClientId(), 'X-User-Id': userId },
  })
  if (!res.ok) return []
  const data = (await res.json()) as { invitations: PendingInvitation[] }
  return data.invitations
}

// ========== Roleplay Chat API ==========

export type RoleplayChatMessage = {
  role: 'user' | 'assistant'
  content: string
}

export type RoleplayChatRequest = {
  profile: Profile
  messages: RoleplayChatMessage[]
}

export type RoleplayChatResponse = {
  reply: string
}

export async function roleplayChat(body: RoleplayChatRequest): Promise<string> {
  const res = await postJson<RoleplayChatResponse>('/api/v1/chat', body)
  return res.reply
}

// ========== Sorting Labels API ==========

export type SortingLabelsRequest = {
  name?: string | null
  answers: SortingAnswers
}

export async function generateSortingLabels(body: SortingLabelsRequest): Promise<SortingQuizResult> {
  return await postJson<SortingQuizResult>('/api/v1/sorting/labels', body)
}

// ========== Streaming Sorting Labels API ==========

import type { WarningLabel, NutritionFacts, UserManual, SocialArchetype } from './sortingQuiz'

export type SortingLabelEvent =
  | { type: 'scores'; noveltyScore: number; securityScore: number; archetype: SocialArchetype }
  | { type: 'warning'; warningLabel: WarningLabel }
  | { type: 'nutrition'; nutritionFacts: NutritionFacts }
  | { type: 'manual'; userManual: UserManual }
  | { type: 'done' }

export async function streamSortingLabels(
  body: SortingLabelsRequest,
  onEvent: (event: SortingLabelEvent) => void
): Promise<void> {
  const url = `${apiBase()}/api/v1/sorting/labels/stream`
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Client-Id': getClientId() },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Request failed: ${res.status} ${res.statusText}${text ? ` - ${text}` : ''}`)
  }

  const reader = res.body?.getReader()
  if (!reader) {
    throw new Error('No response body')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // Process complete lines
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? '' // Keep incomplete line in buffer

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue

      try {
        const event = JSON.parse(trimmed) as SortingLabelEvent
        onEvent(event)
      } catch {
        console.warn('[streamSortingLabels] failed to parse line:', trimmed)
      }
    }
  }

  // Process any remaining buffer
  if (buffer.trim()) {
    try {
      const event = JSON.parse(buffer.trim()) as SortingLabelEvent
      onEvent(event)
    } catch {
      console.warn('[streamSortingLabels] failed to parse final buffer:', buffer)
    }
  }
}

// ========== Profile API ==========

export type SaveProfileRequest = {
  name: string
  gender?: string | null
  age?: string | null
  city?: string | null
  interests?: string[]
  runningProfile?: {
    level: {
      experience: string
      paceRange?: string
      typicalDistance?: string
    }
    availability?: Record<string, boolean>
    preferences?: {
      weeklyFrequency?: string
      runTypes?: string[]
    }
    femaleOnly?: boolean
  } | null
}

export type SaveProfileResponse = {
  success: boolean
  message?: string | null
}

export async function saveUserProfile(
  userId: string,
  body: SaveProfileRequest
): Promise<SaveProfileResponse> {
  const url = `${apiBase()}/api/v1/profile`
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Client-Id': getClientId(),
      'X-User-Id': userId,
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Request failed: ${res.status} ${res.statusText}${text ? ` - ${text}` : ''}`)
  }
  return (await res.json()) as SaveProfileResponse
}
