import { createContext, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useAuth } from './AuthContext.tsx'
import { getPendingInvitations } from './agentApi.ts'
import type { PendingInvitation } from './agentApi.ts'
import { InvitationPopup } from '../components/InvitationPopup.tsx'

const POLL_INTERVAL = 5000

type InvitationState = {
  pending: PendingInvitation[]
}

const InvitationContext = createContext<InvitationState>({ pending: [] })

export function InvitationProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [pending, setPending] = useState<PendingInvitation[]>([])
  const [current, setCurrent] = useState<PendingInvitation | null>(null)
  const [isCurrentExpired, setIsCurrentExpired] = useState(false)
  const dismissedRef = useRef<Set<string>>(new Set())
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const isActive = !!user && !user.needsOnboarding

  useEffect(() => {
    if (!isActive || !user?.uid) {
      setPending([])
      setCurrent(null)
      return
    }

    const poll = async () => {
      try {
        const invitations = await getPendingInvitations(user.uid)
        const fresh = invitations.filter(i => !dismissedRef.current.has(i.invitationId))
        setPending(fresh)

        // Detect expiry: current invitation no longer in backend results
        setCurrent(prev => {
          if (!prev) return fresh[0] ?? null
          const stillPending = fresh.some(i => i.invitationId === prev.invitationId)
          if (!stillPending) {
            setIsCurrentExpired(true)
          }
          return prev
        })
      } catch {
        // Silently ignore polling errors
      }
    }

    void poll()
    pollRef.current = setInterval(poll, POLL_INTERVAL)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [isActive, user?.uid])

  const dismiss = (invitationId: string) => {
    dismissedRef.current.add(invitationId)
    setPending(prev => prev.filter(i => i.invitationId !== invitationId))
    setCurrent(null)
    setIsCurrentExpired(false)
  }

  // Pick next invitation if no current
  useEffect(() => {
    if (!current && pending.length > 0) {
      setCurrent(pending[0])
      setIsCurrentExpired(false)
    }
  }, [current, pending])

  return (
    <InvitationContext value={{ pending }}>
      {children}
      {current && (
        <InvitationPopup
          key={current.invitationId}
          invitation={current}
          expired={isCurrentExpired}
          onDone={() => dismiss(current.invitationId)}
        />
      )}
    </InvitationContext>
  )
}

export function useInvitations() {
  return useContext(InvitationContext)
}
