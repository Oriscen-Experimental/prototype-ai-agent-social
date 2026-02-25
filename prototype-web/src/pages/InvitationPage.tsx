import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getInvitation, respondToInvitation } from '../lib/agentApi'
import type { InvitationDetails } from '../lib/agentApi'

export function InvitationPage() {
  const { invitationId } = useParams<{ invitationId: string }>()
  const [invitation, setInvitation] = useState<InvitationDetails | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [responding, setResponding] = useState(false)
  const [responded, setResponded] = useState(false)

  useEffect(() => {
    if (!invitationId) return
    const load = async () => {
      try {
        const data = await getInvitation(invitationId)
        setInvitation(data)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load invitation')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [invitationId])

  const handleRespond = async (response: 'accept' | 'decline') => {
    if (!invitationId) return
    setResponding(true)
    try {
      await respondToInvitation(invitationId, response)
      setResponded(true)
      setInvitation((prev) => prev ? { ...prev, status: response === 'accept' ? 'accepted' : 'declined' } : prev)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to respond')
    } finally {
      setResponding(false)
    }
  }

  if (loading) {
    return (
      <div className="centerWrap">
        <div className="panel" style={{ padding: 40, textAlign: 'center' }}>
          <div className="h1">Loading invitation...</div>
        </div>
      </div>
    )
  }

  if (error || !invitation) {
    return (
      <div className="centerWrap">
        <div className="panel" style={{ padding: 40, textAlign: 'center' }}>
          <div className="h1">Invitation Not Found</div>
          <div className="muted" style={{ marginTop: 8 }}>{error || 'This invitation does not exist.'}</div>
          <Link to="/app" className="btn" style={{ marginTop: 20, display: 'inline-block' }}>
            Go to App
          </Link>
        </div>
      </div>
    )
  }

  const isPending = invitation.status === 'pending'
  const isAccepted = invitation.status === 'accepted'
  const isDeclined = invitation.status === 'declined'

  return (
    <div className="centerWrap">
      <div className="panel" style={{ padding: 32, maxWidth: 480 }}>
        <div className="h1" style={{ marginBottom: 4 }}>You're Invited!</div>
        <div className="muted" style={{ marginBottom: 24 }}>Someone wants to do an activity with you</div>

        <div style={{ background: 'rgba(59,130,246,0.06)', borderRadius: 12, padding: '20px 24px', marginBottom: 24 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div>
              <div className="muted" style={{ fontSize: 12, marginBottom: 2 }}>Activity</div>
              <div style={{ fontSize: 18, fontWeight: 600 }}>{invitation.activity}</div>
            </div>
            <div>
              <div className="muted" style={{ fontSize: 12, marginBottom: 2 }}>Location</div>
              <div style={{ fontSize: 15 }}>{invitation.location}</div>
            </div>
            {invitation.desiredTime ? (
              <div>
                <div className="muted" style={{ fontSize: 12, marginBottom: 2 }}>When</div>
                <div style={{ fontSize: 15 }}>{invitation.desiredTime}</div>
              </div>
            ) : null}
            <div>
              <div className="muted" style={{ fontSize: 12, marginBottom: 2 }}>Status</div>
              <div style={{
                fontSize: 14,
                fontWeight: 600,
                color: isAccepted ? '#22c55e' : isDeclined ? '#ef4444' : '#3b82f6',
              }}>
                {isAccepted ? 'Accepted' : isDeclined ? 'Declined' : isPending ? 'Pending your response' : invitation.status}
              </div>
            </div>
          </div>
        </div>

        {isPending && !responded ? (
          <div style={{ display: 'flex', gap: 12 }}>
            <button
              className="btn"
              type="button"
              style={{ flex: 1, background: '#22c55e', borderColor: '#22c55e' }}
              onClick={() => void handleRespond('accept')}
              disabled={responding}
            >
              {responding ? 'Responding...' : 'Accept'}
            </button>
            <button
              className="btn btnGhost"
              type="button"
              style={{ flex: 1 }}
              onClick={() => void handleRespond('decline')}
              disabled={responding}
            >
              Decline
            </button>
          </div>
        ) : (
          <div style={{ textAlign: 'center' }}>
            <div className="muted" style={{ marginBottom: 12 }}>
              {isAccepted ? 'You accepted this invitation!' :
               isDeclined ? 'You declined this invitation.' :
               'This invitation is no longer pending.'}
            </div>
            <Link to="/app" className="btn btnGhost" style={{ display: 'inline-block' }}>
              Go to App
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
