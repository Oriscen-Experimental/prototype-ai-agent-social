import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { MissingInfoStepper } from '../components/MissingInfoStepper'
import { CompactGroupCard, CompactProfileCard } from '../components/CompactResultCard'
import { GroupModal } from '../components/GroupModal'
import { ProfileModal } from '../components/ProfileModal'
import { Toast } from '../components/Toast'
import { DebugDrawer } from '../components/DebugDrawer'
import { orchestrate } from '../lib/agentApi'
import type { CardDeck, OrchestrateResponse } from '../lib/agentApi'
import type { Group, Profile } from '../types'

type UIBlock =
  | { type: 'text'; text: string }
  | { type: 'choices'; choices: { id?: string; label: string; value?: string }[] }
  | { type: 'results'; results: { people?: Profile[]; things?: Group[] } }

type ThreadItem = { id: string; role: 'me' | 'ai'; blocks: UIBlock[] }

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message
  if (typeof err === 'string') return err
  try {
    return JSON.stringify(err)
  } catch {
    return 'Request failed'
  }
}

function loadLocalThread(sessionId: string): ThreadItem[] {
  try {
    const raw = localStorage.getItem(`agent_thread_${sessionId}`)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []

    // v2: ThreadItem[]
    const asV2 = parsed.filter(
      (m) => m && typeof m.id === 'string' && (m.role === 'me' || m.role === 'ai') && Array.isArray(m.blocks),
    ) as ThreadItem[]
    if (asV2.length) {
      // avoid persisting large deck blocks inside the chat history
      return asV2.map((m) => ({ ...m, blocks: (m.blocks ?? []).filter((b) => (b as { type?: string })?.type !== 'deck') }))
    }

    // v1 migration: ThreadMsg[] -> ThreadItem[]
    const asV1 = parsed.filter(
      (m) => m && typeof m.id === 'string' && (m.role === 'me' || m.role === 'ai') && typeof m.text === 'string',
    ) as { id: string; role: 'me' | 'ai'; text: string }[]
    if (!asV1.length) return []
    return asV1.map((m) => ({ id: m.id, role: m.role, blocks: [{ type: 'text' as const, text: m.text }] }))
  } catch {
    return []
  }
}

function saveLocalThread(sessionId: string, msgs: ThreadItem[]) {
  try {
    localStorage.setItem(`agent_thread_${sessionId}`, JSON.stringify(msgs.slice(-60)))
  } catch {
    // ignore
  }
}

function loadLocalDeck(sessionId: string): CardDeck | null {
  try {
    const raw = localStorage.getItem(`agent_deck_${sessionId}`)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    return parsed as CardDeck
  } catch {
    return null
  }
}

function saveLocalDeck(sessionId: string, deck: CardDeck | null) {
  try {
    if (!deck) localStorage.removeItem(`agent_deck_${sessionId}`)
    else localStorage.setItem(`agent_deck_${sessionId}`, JSON.stringify(deck))
  } catch {
    // ignore
  }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return Boolean(v) && typeof v === 'object' && !Array.isArray(v)
}

function blocksFromResponse(res: OrchestrateResponse): { messageBlocks: UIBlock[]; deck: CardDeck | null } {
  const out: UIBlock[] = []
  let deck: CardDeck | null = res.deck ?? null

  const rawBlocks = Array.isArray(res.uiBlocks) ? res.uiBlocks : []
  for (const b of rawBlocks) {
    if (!isRecord(b)) continue
    if (b.type === 'text' && typeof b.text === 'string' && b.text.trim()) {
      out.push({ type: 'text', text: b.text })
      continue
    }
    if (b.type === 'choices' && Array.isArray(b.choices)) {
      const choices = (b.choices as unknown[]).flatMap((c) => {
        if (!isRecord(c)) return []
        if (typeof c.label !== 'string' || !c.label.trim()) return []
        return [{ id: typeof c.id === 'string' ? c.id : undefined, label: c.label, value: typeof c.value === 'string' ? c.value : undefined }]
      })
      if (choices.length) out.push({ type: 'choices', choices })
      continue
    }
    if (b.type === 'deck' && isRecord(b.deck)) {
      // keep deck out of chat history; store as pinned deck instead
      deck = b.deck as unknown as CardDeck
      continue
    }
    if (b.type === 'results' && isRecord(b.results)) {
      out.push({ type: 'results', results: b.results as unknown as { people?: Profile[]; things?: Group[] } })
      continue
    }
  }

  const hasText = out.some((x) => x.type === 'text')
  if (!hasText && res.assistantMessage?.trim()) out.unshift({ type: 'text', text: res.assistantMessage })

  const hasResults = out.some((x) => x.type === 'results')
  if (!hasResults && res.results) out.push({ type: 'results', results: res.results })

  if (!out.length) out.push({ type: 'text', text: res.assistantMessage || '' })
  return { messageBlocks: out, deck }
}

export function AgentPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const sidParam = params.get('sid') || ''
  const qParam = params.get('q') || ''

  const [sessionId, setSessionId] = useState<string>(sidParam)
  const [toast, setToast] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [thread, setThread] = useState<ThreadItem[]>(() => (sidParam ? loadLocalThread(sidParam) : []))
  const [activeDeck, setActiveDeck] = useState<CardDeck | null>(() => (sidParam ? loadLocalDeck(sidParam) : null))
  const [draft, setDraft] = useState('')

  const [activeProfile, setActiveProfile] = useState<Profile | null>(null)
  const [activeGroup, setActiveGroup] = useState<Group | null>(null)
  const [debugOpen, setDebugOpen] = useState(false)
  const [lastTrace, setLastTrace] = useState<unknown>(null)

  const syncUrl = (nextSid: string, clearQ: boolean) => {
    const next = new URLSearchParams(params)
    next.set('sid', nextSid)
    if (clearQ) next.delete('q')
    setParams(next, { replace: true })
  }

  const applyResponse = (res: OrchestrateResponse, appendAssistant: boolean) => {
    setSessionId(res.sessionId)
    syncUrl(res.sessionId, true)
    setLastTrace(res.trace ?? null)

    if (appendAssistant) {
      const { messageBlocks, deck } = blocksFromResponse(res)
      setActiveDeck(deck)
      setThread((prev) => {
        const next = [...prev, { id: `${Date.now()}_ai`, role: 'ai' as const, blocks: messageBlocks }]
        saveLocalThread(res.sessionId, next)
        saveLocalDeck(res.sessionId, deck)
        return next
      })
    } else {
      // still keep pinned deck fresh even if we didn't append a message
      const { deck } = blocksFromResponse(res)
      setActiveDeck(deck)
      saveLocalDeck(res.sessionId, deck)
    }
  }

  const sendMessage = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return
    setBusy(true)
    setDraft('')
    setThread((prev) => {
      const next = [
        ...prev,
        { id: `${Date.now()}_me`, role: 'me' as const, blocks: [{ type: 'text' as const, text: trimmed }] },
      ]
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
      setThread([])
      saveLocalThread(sessionId, [])
      setActiveDeck(null)
      saveLocalDeck(sessionId, null)
      applyResponse(res, true)
    } catch (e: unknown) {
      setToast(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (!qParam) return
    if (thread.length > 0) return
    void sendMessage(qParam)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!sessionId) return
    saveLocalThread(sessionId, thread)
    saveLocalDeck(sessionId, activeDeck)
  }, [sessionId, thread, activeDeck])

  const title = useMemo(() => {
    return 'Assistant'
  }, [])

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
          <button className="btn btnGhost" type="button" onClick={() => setDebugOpen(true)} disabled={busy}>
            Debug
          </button>
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
          {thread.length === 0 ? (
            <div className="muted">Tell me what you want to do—free-form is supported now.</div>
          ) : (
            thread.map((m) => (
              <div key={m.id} className={m.role === 'me' ? 'msgRow msgRowMe' : 'msgRow msgRowAi'}>
                <div className={m.role === 'me' ? 'msgBubble msgMe' : 'msgBubble msgAi'}>
                  {m.blocks.map((b, bIdx) => {
                    if (b.type === 'text') return <div key={bIdx} style={{ whiteSpace: 'pre-wrap' }}>{b.text}</div>
                    if (b.type === 'choices') {
                          return (
                            <div key={bIdx} className="row" style={{ flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
                              {b.choices.map((c, cIdx) => (
                                <button
                                  key={c.id ?? String(cIdx)}
                                  type="button"
                                  className="tag tagBtn"
                                  disabled={busy}
                                  onClick={() => void sendMessage(c.value ?? c.label)}
                                >
                                  {c.label}
                                </button>
                              ))}
                            </div>
                          )
                    }
                    if (b.type === 'results') {
                      const people = b.results.people ?? []
                      const things = b.results.things ?? []
                      return (
                        <div key={bIdx} style={{ marginTop: 10 }}>
                          {people.length ? (
                            <>
                              <div className="muted" style={{ marginBottom: 8 }}>
                                People · {people.length}
                              </div>
                              <div className="compactRow">
                                {people.map((p) => (
                                  <CompactProfileCard key={p.id} profile={p} onClick={() => setActiveProfile(p)} />
                                ))}
                              </div>
                            </>
                          ) : null}
                          {things.length ? (
                            <>
                              <div className="muted" style={{ marginBottom: 8 }}>
                                Things · {things.length}
                              </div>
                              <div className="compactRow">
                                {things.map((g) => (
                                  <CompactGroupCard key={g.id} group={g} onClick={() => setActiveGroup(g)} />
                                ))}
                              </div>
                            </>
                          ) : null}
                        </div>
                      )
                    }
                    return null
                  })}
                </div>
              </div>
            ))
          )}

          {activeDeck ? (
            <div className="msgRow msgRowAi">
              <div className="msgBubble msgAi">
                <div className="muted" style={{ marginBottom: 8 }}>
                  补全信息
                </div>
                <MissingInfoStepper deck={activeDeck} onSubmit={submitCard} />
              </div>
            </div>
          ) : null}

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
          <div className="muted">Gemini orchestrator + AI-generated results.</div>
        </div>
      </div>

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
      <DebugDrawer open={debugOpen} trace={lastTrace} onClose={() => setDebugOpen(false)} />
    </div>
  )
}
