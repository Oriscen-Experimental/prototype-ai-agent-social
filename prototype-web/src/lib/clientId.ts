let cached: string | null = null

const STORAGE_KEY = 'agent_social_client_id'

function randomId(): string {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  } catch {
    // ignore
  }
  return `${Date.now()}_${Math.random().toString(16).slice(2)}`
}

export function getClientId(): string {
  if (cached) return cached

  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw && raw.trim()) {
      cached = raw.trim()
      return cached
    }
  } catch {
    // ignore
  }

  cached = randomId()
  try {
    localStorage.setItem(STORAGE_KEY, cached)
  } catch {
    // ignore
  }
  return cached
}

