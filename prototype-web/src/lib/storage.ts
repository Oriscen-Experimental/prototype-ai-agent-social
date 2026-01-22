const INTERNAL_EVENT = 'proto-storage'

const memory: Record<string, string> = {}

function safeLocalStorage(): Storage | null {
  try {
    return localStorage
  } catch {
    return null
  }
}

function getRaw(key: string): string | null {
  const ls = safeLocalStorage()
  if (ls) {
    try {
      return ls.getItem(key)
    } catch {
      // ignore
    }
  }
  return memory[key] ?? null
}

function setRaw(key: string, value: string) {
  const ls = safeLocalStorage()
  if (ls) {
    try {
      ls.setItem(key, value)
      return
    } catch {
      // ignore
    }
  }
  memory[key] = value
}

function removeRaw(key: string) {
  const ls = safeLocalStorage()
  if (ls) {
    try {
      ls.removeItem(key)
      return
    } catch {
      // ignore
    }
  }
  delete memory[key]
}

function emitChange() {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new Event(INTERNAL_EVENT))
}

export function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = getRaw(key)
    if (!raw) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

export function writeJson<T>(key: string, value: T) {
  try {
    setRaw(key, JSON.stringify(value))
  } finally {
    emitChange()
  }
}

export function removeKey(key: string) {
  try {
    removeRaw(key)
  } finally {
    emitChange()
  }
}

export function subscribe(callback: () => void) {
  if (typeof window === 'undefined') return () => {}
  const onStorage = (e: StorageEvent) => {
    // Some browsers may block localStorage; treat any storage event as a hint.
    if (!e.storageArea || e.storageArea === safeLocalStorage()) callback()
  }
  const onInternal = () => callback()
  window.addEventListener('storage', onStorage)
  window.addEventListener(INTERNAL_EVENT, onInternal)
  return () => {
    window.removeEventListener('storage', onStorage)
    window.removeEventListener(INTERNAL_EVENT, onInternal)
  }
}
