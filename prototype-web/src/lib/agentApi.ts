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

export type OrchestrateResponse = {
  sessionId: string
  type: 'message' | 'results' | 'form'
  content: MessageContent | ResultsContent | FormContent
  trace?: Record<string, unknown> | null
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
