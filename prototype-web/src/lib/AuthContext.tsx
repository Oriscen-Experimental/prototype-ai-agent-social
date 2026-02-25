import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

const AUTH_STORAGE_KEY = 'proto.auth.user'

export type User = {
  uid: string
  email?: string | null
  displayName?: string | null
  photoURL?: string | null
}

type AuthState = {
  user: User | null
  loading: boolean
  signInWithGoogle: (credential: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  // Restore user from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(AUTH_STORAGE_KEY)
      if (stored) {
        setUser(JSON.parse(stored))
      }
    } catch {
      // Ignore parse errors
    }
    setLoading(false)
  }, [])

  const signInWithGoogle = async (credential: string) => {
    const apiBase = import.meta.env.VITE_API_BASE_URL || ''
    const res = await fetch(`${apiBase}/api/v1/auth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idToken: credential }),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Authentication failed' }))
      throw new Error(err.detail || 'Authentication failed')
    }

    const userData: User = await res.json()
    setUser(userData)
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(userData))
  }

  const logout = () => {
    setUser(null)
    localStorage.removeItem(AUTH_STORAGE_KEY)
  }

  return (
    <AuthContext value={{ user, loading, signInWithGoogle, logout }}>
      {children}
    </AuthContext>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
