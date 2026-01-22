const INTERNAL_EVENT = 'proto-storage'

export function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

export function writeJson<T>(key: string, value: T) {
  localStorage.setItem(key, JSON.stringify(value))
  window.dispatchEvent(new Event(INTERNAL_EVENT))
}

export function removeKey(key: string) {
  localStorage.removeItem(key)
  window.dispatchEvent(new Event(INTERNAL_EVENT))
}

export function subscribe(callback: () => void) {
  const onStorage = (e: StorageEvent) => {
    if (e.storageArea === localStorage) callback()
  }
  const onInternal = () => callback()
  window.addEventListener('storage', onStorage)
  window.addEventListener(INTERNAL_EVENT, onInternal)
  return () => {
    window.removeEventListener('storage', onStorage)
    window.removeEventListener(INTERNAL_EVENT, onInternal)
  }
}

