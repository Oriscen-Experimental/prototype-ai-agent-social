import type { Group, Profile } from '../types'

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

export type UIBlock =
  | { type: 'text'; text: string }
  | { type: 'profiles'; profiles: Profile[]; layout?: 'compact' | 'full' }
  | { type: 'groups'; groups: Group[]; layout?: 'compact' | 'full' }
  | { type: 'form'; form: FormContent }

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

export type OrchestrateRequest =
  | { sessionId?: string | null; message: string; plannerModel?: PlannerModel; reset?: boolean }
  | { sessionId: string; formSubmission: FormSubmission; plannerModel?: PlannerModel; reset?: boolean }
  | { sessionId: string; reset: true; plannerModel?: PlannerModel }

function apiBase(): string {
  const raw = import.meta.env.VITE_API_BASE_URL as string | undefined
  const s = (raw ?? '').trim()
  return s.endsWith('/') ? s.slice(0, -1) : s
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const url = `${apiBase()}${path}`
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
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
