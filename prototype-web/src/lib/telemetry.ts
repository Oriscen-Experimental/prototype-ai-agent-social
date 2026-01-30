import { getClientId } from './clientId'

type TelemetryEvent = {
  type: string
  at_ms: number
  sessionId?: string | null
  page?: string | null
  payload?: Record<string, unknown> | null
}

const STORAGE_KEY = 'agent_social_telemetry_queue_v1'

let queue: TelemetryEvent[] = loadQueue()
let flushTimer: number | null = null
let flushing = false
let listenersInstalled = false

function nowMs() {
  return Date.now()
}

function pagePath(): string {
  try {
    return `${location.pathname}${location.search}${location.hash}`
  } catch {
    return ''
  }
}

function apiBase(): string {
  // Keep logic aligned with agentApi.ts without creating a dependency cycle.
  const raw = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''
  const s = raw.trim()
  return s.endsWith('/') ? s.slice(0, -1) : s
}

function loadQueue(): TelemetryEvent[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((e) => e && typeof e === 'object' && typeof e.type === 'string' && typeof e.at_ms === 'number') as TelemetryEvent[]
  } catch {
    return []
  }
}

function persistQueue() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(queue.slice(-2000)))
  } catch {
    // ignore
  }
}

function scheduleFlush() {
  if (flushTimer != null) return
  flushTimer = window.setTimeout(() => {
    flushTimer = null
    void flush()
  }, 750)
}

export function track(event: Omit<TelemetryEvent, 'at_ms' | 'page'> & { at_ms?: number; page?: string }) {
  if (!listenersInstalled && typeof window !== 'undefined') {
    listenersInstalled = true
    window.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') void flush()
    })
    window.addEventListener('pagehide', () => {
      void flush()
    })
  }

  queue.push({
    type: event.type,
    at_ms: event.at_ms ?? nowMs(),
    sessionId: event.sessionId ?? null,
    page: event.page ?? pagePath(),
    payload: event.payload ?? null,
  })
  persistQueue()
  scheduleFlush()
}

export async function flush() {
  if (flushing) return
  if (!queue.length) return
  flushing = true
  try {
    const batch = queue.slice(0, 50)
    const url = `${apiBase()}/api/v1/events`
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Client-Id': getClientId() },
      body: JSON.stringify({ events: batch }),
    })
    if (!res.ok) return
    queue = queue.slice(batch.length)
    persistQueue()
  } catch {
    // ignore
  } finally {
    flushing = false
    if (queue.length) scheduleFlush()
  }
}
