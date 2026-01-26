import type { Group, Profile } from '../types'

export type OrchestrateIntent =
  | 'unknown'
  | 'find_people'
  | 'find_things'
  | 'analyze_people'
  | 'analyze_things'
  | 'refine_people'
  | 'refine_things'
export type OrchestrateAction = 'chat' | 'form' | 'results'

export type CardStatus = 'completed' | 'active' | 'upcoming'

export type FormOption = { value: string; label: string }

export type FormFieldType = 'text' | 'number' | 'select' | 'multi_select' | 'range'

export type FormField = {
  key: string
  label: string
  type: FormFieldType
  required?: boolean
  placeholder?: string | null
  options?: FormOption[] | null
  min?: number | null
  max?: number | null
  value?: unknown
}

export type Card = {
  id: string
  title: string
  status: CardStatus
  fields: FormField[]
  required?: boolean
}

export type CardDeck = {
  layout: 'stacked'
  activeCardId?: string | null
  cards: Card[]
}

export type OrchestrateRequest =
  | { sessionId?: string | null; message: string; reset?: boolean }
  | { sessionId: string; submit: { cardId: string; data: Record<string, unknown> }; reset?: boolean }
  | { sessionId: string; reset: true }

export type OrchestrateResponse = {
  requestId: string
  sessionId: string
  intent: OrchestrateIntent
  action: OrchestrateAction
  assistantMessage: string
  missingFields: string[]
  deck?: CardDeck | null
  results?: { people?: Profile[]; things?: Group[] } | null
  uiBlocks?: unknown[] | null
  trace?: Record<string, unknown> | null
}

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
