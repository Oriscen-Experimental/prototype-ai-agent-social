import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { CardDeckView } from '../components/CardDeck'
import { GroupCard } from '../components/GroupCard'
import { GroupModal } from '../components/GroupModal'
import { ProfileCard } from '../components/ProfileCard'
import { ProfileModal } from '../components/ProfileModal'
import { Toast } from '../components/Toast'
import { orchestrate } from '../lib/agentApi'
import type { CardDeck, OrchestrateResponse } from '../lib/agentApi'
import type { Group, Profile } from '../types'

type ThreadMsg = { id: string; role: 'me' | 'ai'; text: string }

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message
  if (typeof err === 'string') return err
  try {
    return JSON.stringify(err)
  } catch {
    return 'Request failed'
  }
}

function loadLocalThread(sessionId: string): ThreadMsg[] {
  try {
    const raw = localStorage.getItem(`agent_thread_${sessionId}`)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((m) => m && typeof m.id === 'string' && (m.role === 'me' || m.role === 'ai') && typeof m.text === 'string')
  } catch {
    return []
  }
}

function saveLocalThread(sessionId: string, msgs: ThreadMsg[]) {
  try {
    localStorage.setItem(`agent_thread_${sessionId}`, JSON.stringify(msgs.slice(-60)))
  } catch {
    // ignore
  }
}

export function AgentPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const sidParam = params.get('sid') || ''
  const qParam = params.get('q') || ''

  const [sessionId, setSessionId] = useState<string>(sidParam)
  const [deck, setDeck] = useState<CardDeck | null>(null)
  const [people, setPeople] = useState<Profile[] | null>(null)
  const [things, setThings] = useState<Group[] | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [messages, setMessages] = useState<ThreadMsg[]>(() => (sidParam ? loadLocalThread(sidParam) : []))
  const [draft, setDraft] = useState('')

  const [activeProfile, setActiveProfile] = useState<Profile | null>(null)
  const [activeGroup, setActiveGroup] = useState<Group | null>(null)

  const syncUrl = (nextSid: string, clearQ: boolean) => {
    const next = new URLSearchParams(params)
    next.set('sid', nextSid)
    if (clearQ) next.delete('q')
    setParams(next, { replace: true })
  }

  const applyResponse = (res: OrchestrateResponse, appendAssistant: boolean) => {
    setSessionId(res.sessionId)
    syncUrl(res.sessionId, true)

    setDeck(res.deck ?? null)
    const nextPeople = res.results?.people ?? null
    const nextThings = res.results?.things ?? null
    setPeople(nextPeople)
    setThings(nextThings)

    if (appendAssistant) {
      setMessages((prev) => {
        const next = [...prev, { id: `${Date.now()}_ai`, role: 'ai' as const, text: res.assistantMessage }]
        saveLocalThread(res.sessionId, next)
        return next
      })
    }
  }

  const sendMessage = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return
    setBusy(true)
    setDraft('')
    setMessages((prev) => {
      const next = [...prev, { id: `${Date.now()}_me`, role: 'me' as const, text: trimmed }]
      if (sessionId) saveLocalThread(sessionId, next)
      return next
    })
    try {
      const res = await orchestrate({ sessionId: sessionId || undefined, message: trimmed })
      applyResponse(res, true)
    } catch (e: unknown) {
      setToast(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const submitCard = async (cardId: string, data: Record<string, unknown>) => {
    if (!sessionId) {
      setToast('Missing sessionId (refresh and try again).')
      return
    }
    setBusy(true)
    try {
      const res = await orchestrate({ sessionId, submit: { cardId, data } })
      applyResponse(res, true)
    } catch (e: unknown) {
      setToast(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const reset = async () => {
    if (!sessionId) return
    setBusy(true)
    try {
      const res = await orchestrate({ sessionId, reset: true })
      setMessages([])
      saveLocalThread(sessionId, [])
      setDeck(null)
      setPeople(null)
      setThings(null)
      applyResponse(res, true)
    } catch (e: unknown) {
      setToast(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (!qParam) return
    if (messages.length > 0) return
    void sendMessage(qParam)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!sessionId) return
    saveLocalThread(sessionId, messages)
  }, [sessionId, messages])

  const title = useMemo(() => {
    if (people?.length) return 'Matches'
    if (things?.length) return 'Activities'
    return 'Assistant'
  }, [people?.length, things?.length])

  return (
    <div className="page">
      <div className="row spaceBetween">
        <div>
          <div className="muted">
            <Link to="/app" className="link">
              ← Back
            </Link>
          </div>
          <div className="h1">{title}</div>
          <div className="muted">{sessionId ? `Session: ${sessionId.slice(0, 8)}…` : 'New session'}</div>
        </div>
        <div className="row">
          <button className="btn btnGhost" type="button" onClick={() => navigate('/app')} disabled={busy}>
            New search
          </button>
          <button className="btn btnGhost" type="button" onClick={reset} disabled={busy || !sessionId}>
            Reset session
          </button>
        </div>
      </div>

      <div className="card">
        <div className="assistantThread">
          {messages.length === 0 ? (
            <div className="muted">Tell me what you want to do—free-form is supported now.</div>
          ) : (
            messages.map((m) => (
              <div key={m.id} className={m.role === 'me' ? 'msgRow msgRowMe' : 'msgRow msgRowAi'}>
                <div className={m.role === 'me' ? 'msgBubble msgMe' : 'msgBubble msgAi'}>{m.text}</div>
              </div>
            ))
          )}

          <div className="composerRow">
            <input
              className="input"
              value={draft}
              disabled={busy}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Type your message…"
              onKeyDown={(e) => {
                if (e.key === 'Enter') void sendMessage(draft)
              }}
            />
            <button className="btn" type="button" disabled={busy} onClick={() => void sendMessage(draft)}>
              Send
            </button>
          </div>
          <div className="muted">Backend orchestrator + mock find-people/find-things.</div>
        </div>
      </div>

      {deck ? (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="sectionTitle">Fill in details</div>
          <CardDeckView deck={deck} onSubmitCard={submitCard} />
        </div>
      ) : null}

      {people?.length ? (
        <>
          <div className="sectionTitle">People</div>
          <div className="gridCards">
            {people.map((p) => (
              <ProfileCard key={p.id} profile={p} onClick={() => setActiveProfile(p)} />
            ))}
          </div>
        </>
      ) : null}

      {things?.length ? (
        <>
          <div className="sectionTitle">Things</div>
          <div className="gridCards">
            {things.map((g) => (
              <GroupCard key={g.id} group={g} onClick={() => setActiveGroup(g)} />
            ))}
          </div>
        </>
      ) : null}

      {activeProfile ? <ProfileModal profile={activeProfile} onClose={() => setActiveProfile(null)} onChat={() => setToast('Chat is still mock-only in this flow.')} /> : null}

      {activeGroup ? (
        <GroupModal
          group={activeGroup}
          requiredSpots={1}
          joined={false}
          onClose={() => setActiveGroup(null)}
          onNavigate={() => setToast('Opening maps / navigation (mock).')}
          onJoin={() => setToast('Join/RSVP is not implemented in this flow (mock).')}
        />
      ) : null}

      {toast ? <Toast message={toast} onClose={() => setToast(null)} /> : null}
    </div>
  )
}
