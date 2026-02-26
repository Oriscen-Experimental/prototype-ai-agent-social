import { useEffect, useState } from 'react'
import { Modal } from './Modal.tsx'
import { respondToInvitation } from '../lib/agentApi.ts'
import type { PendingInvitation } from '../lib/agentApi.ts'

const AUTO_CLOSE_MS = 10_000

export function InvitationPopup(props: {
  invitation: PendingInvitation
  expired: boolean
  onDone: () => void
}) {
  const { invitation, expired, onDone } = props
  const [loading, setLoading] = useState(false)
  const [failedExpired, setFailedExpired] = useState(false)

  const isExpired = expired || failedExpired

  // Auto-close 10s after becoming expired
  useEffect(() => {
    if (!isExpired) return
    const t = setTimeout(onDone, AUTO_CLOSE_MS)
    return () => clearTimeout(t)
  }, [isExpired, onDone])

  const respond = async (response: 'accept' | 'decline') => {
    if (isExpired) {
      // Already showing expired state — just ignore
      return
    }
    setLoading(true)
    try {
      const res = await respondToInvitation(invitation.invitationId, response)
      if (res.expired) {
        setFailedExpired(true)
        return
      }
    } catch {
      // Network or unexpected error — treat as expired
      setFailedExpired(true)
      return
    }
    onDone()
  }

  // --- Expired state ---
  if (isExpired) {
    return (
      <Modal title="Invitation Expired" onClose={onDone} footer={
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button className="btn" type="button" onClick={onDone}>Dismiss</button>
        </div>
      }>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ color: '#f59e0b', fontWeight: 600 }}>
            This invitation has expired and can no longer be accepted.
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div>
              <span className="muted" style={{ fontSize: 13 }}>Activity: </span>
              <span style={{ fontWeight: 600 }}>{invitation.activity}</span>
            </div>
            <div>
              <span className="muted" style={{ fontSize: 13 }}>Location: </span>
              <span style={{ fontWeight: 600 }}>{invitation.location}</span>
            </div>
          </div>
        </div>
      </Modal>
    )
  }

  // --- Active state ---
  return (
    <Modal
      title="You've been invited!"
      onClose={() => respond('decline')}
      footer={
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button
            className="btn btnGhost"
            type="button"
            disabled={loading}
            onClick={() => respond('decline')}
          >
            Decline
          </button>
          <button
            className="btn"
            type="button"
            disabled={loading}
            onClick={() => respond('accept')}
          >
            {loading ? 'Sending...' : 'Accept'}
          </button>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div>
          <div className="muted" style={{ fontSize: 13 }}>Activity</div>
          <div style={{ fontWeight: 600 }}>{invitation.activity}</div>
        </div>
        <div>
          <div className="muted" style={{ fontSize: 13 }}>Location</div>
          <div style={{ fontWeight: 600 }}>{invitation.location}</div>
        </div>
        {invitation.desiredTime && (
          <div>
            <div className="muted" style={{ fontSize: 13 }}>Time</div>
            <div style={{ fontWeight: 600 }}>{invitation.desiredTime}</div>
          </div>
        )}
      </div>
    </Modal>
  )
}
