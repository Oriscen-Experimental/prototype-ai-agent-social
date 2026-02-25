import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { FormQuestionStepper } from '../components/FormQuestionStepper'
import { CompactGroupCard, CompactProfileCard } from '../components/CompactResultCard'
import { GroupModal } from '../components/GroupModal'
import { ProfileModal } from '../components/ProfileModal'
import { Toast } from '../components/Toast'
import { DebugDrawer } from '../components/DebugDrawer'
import { usePlannerModel } from '../lib/usePlannerModel'
import { useOnboarding } from '../lib/useOnboarding'
import { orchestrate, normalizeResponse, getBookingStatus, setBookingSpeed, getBookingNotifications } from '../lib/agentApi'
import type { OrchestrateResponse, FormContent, FormSubmission, UIBlock, UserContext, BookingStatusResponse } from '../lib/agentApi'
import type { Group, Profile } from '../types'
import { ensureThread, makeThreadId } from '../lib/threads'
import { track } from '../lib/telemetry'

// Thread item stores blocks for rendering
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

    const asV2 = parsed.filter(
      (m) => m && typeof m.id === 'string' && (m.role === 'me' || m.role === 'ai') && Array.isArray(m.blocks),
    ) as ThreadItem[]
    if (asV2.length) {
      // Convert old 'results' blocks to new 'profiles'/'groups' blocks
      return asV2.map((m) => ({
        ...m,
        blocks: (m.blocks ?? [])
          .filter((b) => (b as { type?: string })?.type !== 'deck')
          .flatMap((b) => {
            // Handle legacy 'results' block type
            const bAny = b as unknown as { type?: string; results?: { people?: Profile[]; things?: Group[] } }
            if (bAny.type === 'results' && bAny.results) {
              const converted: UIBlock[] = []
              if (bAny.results.people?.length) {
                converted.push({ type: 'profiles', profiles: bAny.results.people, layout: 'compact' })
              }
              if (bAny.results.things?.length) {
                converted.push({ type: 'groups', groups: bAny.results.things, layout: 'compact' })
              }
              return converted
            }
            return [b as UIBlock]
          }),
      }))
    }

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

function loadLocalForm(sessionId: string): FormContent | null {
  try {
    const raw = localStorage.getItem(`agent_form_${sessionId}`)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    return parsed as FormContent
  } catch {
    return null
  }
}

function saveLocalForm(sessionId: string, form: FormContent | null) {
  try {
    if (!form) localStorage.removeItem(`agent_form_${sessionId}`)
    else localStorage.setItem(`agent_form_${sessionId}`, JSON.stringify(form))
  } catch {
    // ignore
  }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return Boolean(v) && typeof v === 'object' && !Array.isArray(v)
}

function isPlannerTrace(v: unknown): v is { plannerInput: unknown; plannerOutput: unknown } {
  if (!isRecord(v)) return false
  return v.plannerInput != null && v.plannerOutput != null
}

function blocksFromResponse(res: OrchestrateResponse): { messageBlocks: UIBlock[]; formData: FormContent | null } {
  const { blocks } = normalizeResponse(res)

  // Separate form blocks from display blocks
  const messageBlocks: UIBlock[] = []
  let formData: FormContent | null = null

  for (const b of blocks) {
    if (b.type === 'form') {
      formData = b.form
    } else {
      messageBlocks.push(b)
    }
  }

  return { messageBlocks, formData }
}

export function AgentPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const sidParam = params.get('sid') || ''
  const qParam = params.get('q') || ''
  const { model: plannerModel } = usePlannerModel()
  const { data: onboardingData } = useOnboarding()

  // Build user context from onboarding data
  const userContext: UserContext | undefined = useMemo(() => {
    if (!onboardingData) return undefined
    return {
      name: onboardingData.name,
      city: onboardingData.city,
      interests: onboardingData.interests,
      goals: onboardingData.goals,
      vibe: onboardingData.vibe,
      archetype: onboardingData.sortingQuiz?.archetype,
    }
  }, [onboardingData])

  const [sessionId, setSessionId] = useState<string>(sidParam)
  const [toast, setToast] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [thread, setThread] = useState<ThreadItem[]>(() => (sidParam ? loadLocalThread(sidParam) : []))
  const [activeForm, setActiveForm] = useState<FormContent | null>(() => (sidParam ? loadLocalForm(sidParam) : null))
  const [draft, setDraft] = useState('')

  const [activeProfile, setActiveProfile] = useState<Profile | null>(null)
  const [activeGroup, setActiveGroup] = useState<Group | null>(null)
  const [debugOpen, setDebugOpen] = useState(false)
  const [lastTrace, setLastTrace] = useState<unknown>(null)

  // Booking state
  const [activeBookingTaskId, setActiveBookingTaskId] = useState<string | null>(null)
  const [bookingStatus, setBookingStatus] = useState<BookingStatusResponse | null>(null)
  const [demoSpeed, setDemoSpeed] = useState<number>(360)
  const bookingPollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const notificationPollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Polling for booking status
  useEffect(() => {
    if (!activeBookingTaskId) return
    const poll = async () => {
      try {
        const status = await getBookingStatus(activeBookingTaskId)
        setBookingStatus(status)
        if (status.status === 'completed' || status.status === 'failed') {
          // Stop polling
          if (bookingPollRef.current) clearInterval(bookingPollRef.current)
          bookingPollRef.current = null
        }
      } catch {
        // ignore polling errors
      }
    }
    void poll() // immediate first check
    bookingPollRef.current = setInterval(poll, 3000)
    return () => {
      if (bookingPollRef.current) clearInterval(bookingPollRef.current)
    }
  }, [activeBookingTaskId])

  // Polling for booking notifications (completion/failure messages)
  useEffect(() => {
    if (!sessionId || !activeBookingTaskId) return
    const poll = async () => {
      try {
        const { notifications } = await getBookingNotifications(sessionId)
        for (const n of notifications) {
          const blocks: UIBlock[] = [{ type: 'text', text: n.message }]
          if (n.profiles?.length) {
            blocks.push({ type: 'profiles', profiles: n.profiles, layout: 'compact' })
          }
          setThread((prev) => {
            const next = [...prev, { id: `${Date.now()}_booking`, role: 'ai' as const, blocks }]
            saveLocalThread(sessionId, next)
            return next
          })
          if (n.type === 'booking_completed' || n.type === 'booking_failed') {
            setActiveBookingTaskId(null)
            setBookingStatus(null)
          }
        }
      } catch {
        // ignore
      }
    }
    notificationPollRef.current = setInterval(poll, 3000)
    return () => {
      if (notificationPollRef.current) clearInterval(notificationPollRef.current)
    }
  }, [sessionId, activeBookingTaskId])

  const handleSpeedChange = useCallback(async (speed: number) => {
    setDemoSpeed(speed)
    if (activeBookingTaskId) {
      try {
        await setBookingSpeed(activeBookingTaskId, speed)
      } catch {
        // ignore
      }
    }
  }, [activeBookingTaskId])

  const onGoChat = (profile: Profile) => {
    try {
      ensureThread({ caseId: 'agent', profile })
      navigate(`/app/chat/${makeThreadId('agent', profile.id)}`)
    } catch {
      setToast("Chat isn't available right now.")
    }
  }

  const syncUrl = (nextSid: string, clearQ: boolean) => {
    const next = new URLSearchParams(params)
    next.set('sid', nextSid)
    if (clearQ) next.delete('q')
    setParams(next, { replace: true })
  }

  const applyResponse = (res: OrchestrateResponse, appendAssistant: boolean) => {
    setSessionId(res.sessionId)
    syncUrl(res.sessionId, true)
    if (isPlannerTrace(res.trace)) setLastTrace(res.trace)

    const { messageBlocks, formData } = blocksFromResponse(res)
    setActiveForm(formData)
    saveLocalForm(res.sessionId, formData)

    // Check for booking_status blocks and start polling
    for (const b of messageBlocks) {
      if (b.type === 'booking_status' && 'bookingTaskId' in b && b.bookingTaskId) {
        setActiveBookingTaskId(b.bookingTaskId)
        // Set initial speed
        void setBookingSpeed(b.bookingTaskId, demoSpeed).catch(() => {})
        break
      }
    }

    if (appendAssistant && messageBlocks.length > 0) {
      setThread((prev) => {
        const next = [...prev, { id: `${Date.now()}_ai`, role: 'ai' as const, blocks: messageBlocks }]
        saveLocalThread(res.sessionId, next)
        return next
      })
    }
  }

  const sendMessage = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return
    track({ type: 'agent_message_send', sessionId: sessionId || null, payload: { text: trimmed, plannerModel } })
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
      const res = await orchestrate({ sessionId: sessionId || undefined, message: trimmed, plannerModel, userContext })
      applyResponse(res, true)
    } catch (e: unknown) {
      setToast(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const submitForm = async (submission: FormSubmission) => {
    if (!sessionId) {
      setToast('Missing sessionId (refresh and try again).')
      return
    }
    track({
      type: 'agent_form_submit',
      sessionId,
      payload: { toolName: submission.toolName, toolArgs: submission.toolArgs, answers: submission.answers, plannerModel },
    })
    setBusy(true)
    try {
      const res = await orchestrate({ sessionId, formSubmission: submission, plannerModel, userContext })
      applyResponse(res, true)
    } catch (e: unknown) {
      setToast(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const reset = async () => {
    if (!sessionId) return
    track({ type: 'agent_reset', sessionId, payload: { plannerModel } })
    setBusy(true)
    try {
      const res = await orchestrate({ sessionId, reset: true, plannerModel, userContext })
      setThread([])
      saveLocalThread(sessionId, [])
      setActiveForm(null)
      saveLocalForm(sessionId, null)
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
    saveLocalForm(sessionId, activeForm)
  }, [sessionId, thread, activeForm])

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
                    if (b.type === 'text') {
                      return <div key={bIdx} style={{ whiteSpace: 'pre-wrap' }}>{b.text}</div>
                    }
                    if (b.type === 'profiles' && b.profiles?.length) {
                      return (
                        <div key={bIdx} style={{ marginTop: 10 }}>
                          <div className="muted" style={{ marginBottom: 8 }}>
                            People · {b.profiles.length}
                          </div>
                          <div className="compactRow">
                            {b.profiles.map((p) => (
                              <CompactProfileCard
                                key={p.id}
                                profile={p}
                                onClick={() => {
                                  track({
                                    type: 'agent_profile_open',
                                    sessionId: sessionId || null,
                                    payload: { profileId: p.id, profileName: p.name, city: p.city },
                                  })
                                  setActiveProfile(p)
                                }}
                              />
                            ))}
                          </div>
                        </div>
                      )
                    }
                    if (b.type === 'groups' && b.groups?.length) {
                      return (
                        <div key={bIdx} style={{ marginTop: 10 }}>
                          <div className="muted" style={{ marginBottom: 8 }}>
                            Things · {b.groups.length}
                          </div>
                          <div className="compactRow">
                            {b.groups.map((g) => (
                              <CompactGroupCard
                                key={g.id}
                                group={g}
                                onClick={() => {
                                  track({
                                    type: 'agent_group_open',
                                    sessionId: sessionId || null,
                                    payload: { groupId: g.id, groupTitle: g.title, city: g.city, location: g.location },
                                  })
                                  setActiveGroup(g)
                                }}
                              />
                            ))}
                          </div>
                        </div>
                      )
                    }
                    if (b.type === 'booking_status' && 'bookingTaskId' in b) {
                      return (
                        <div key={bIdx} style={{ marginTop: 10, padding: '8px 12px', background: 'rgba(100,200,100,0.1)', borderRadius: 8 }}>
                          <div style={{ fontSize: 13, fontWeight: 600 }}>Booking in progress...</div>
                          <div className="muted" style={{ fontSize: 12 }}>Task ID: {b.bookingTaskId?.slice(0, 8)}</div>
                        </div>
                      )
                    }
                    // form blocks are handled separately via activeForm state
                    return null
                  })}
                </div>
              </div>
            ))
          )}

          {activeForm ? (
            <div className="msgRow msgRowAi">
              <div className="msgBubble msgAi">
                <div className="muted" style={{ marginBottom: 8 }}>
                  Additional information needed
                </div>
                <FormQuestionStepper form={activeForm} onSubmit={submitForm} />
              </div>
            </div>
          ) : null}

          {/* Booking status panel */}
          {bookingStatus && activeBookingTaskId ? (
            <div style={{ margin: '12px 0', padding: '12px 16px', background: 'rgba(59,130,246,0.08)', borderRadius: 10, border: '1px solid rgba(59,130,246,0.2)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>
                  {bookingStatus.status === 'running' ? 'Booking in progress...' :
                   bookingStatus.status === 'completed' ? 'Booking complete!' :
                   bookingStatus.status === 'failed' ? 'Booking ended' : bookingStatus.status}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span className="muted" style={{ fontSize: 11 }}>Speed:</span>
                  {[1, 60, 360, 3600].map((s) => (
                    <button
                      key={s}
                      type="button"
                      className={`btn ${demoSpeed === s ? '' : 'btnGhost'}`}
                      style={{ padding: '2px 8px', fontSize: 11, minWidth: 0 }}
                      onClick={() => void handleSpeedChange(s)}
                    >
                      {s}x
                    </button>
                  ))}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 16, fontSize: 13 }}>
                <div>Accepted: <strong>{bookingStatus.acceptedCount}</strong> / {bookingStatus.targetCount}</div>
                <div>Batch: <strong>{bookingStatus.currentBatch + 1}</strong></div>
                <div>Invited: <strong>{bookingStatus.totalInvitations}</strong></div>
              </div>
              {/* Progress bar */}
              <div style={{ marginTop: 8, height: 4, background: 'rgba(0,0,0,0.1)', borderRadius: 2 }}>
                <div style={{
                  height: '100%',
                  borderRadius: 2,
                  background: bookingStatus.status === 'completed' ? '#22c55e' : '#3b82f6',
                  width: `${Math.min(100, (bookingStatus.acceptedCount / bookingStatus.targetCount) * 100)}%`,
                  transition: 'width 0.3s',
                }} />
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
          <div className="muted">Gemini orchestrator + real user matching.</div>
        </div>
      </div>

      {activeProfile ? (
        <ProfileModal
          profile={activeProfile}
          onClose={() => {
            track({
              type: 'agent_profile_close',
              sessionId: sessionId || null,
              payload: { profileId: activeProfile.id, profileName: activeProfile.name },
            })
            setActiveProfile(null)
          }}
          onChat={() => {
            track({
              type: 'agent_profile_chat',
              sessionId: sessionId || null,
              payload: { profileId: activeProfile.id, profileName: activeProfile.name },
            })
            onGoChat(activeProfile)
          }}
        />
      ) : null}

      {activeGroup ? (
        <GroupModal
          group={activeGroup}
          requiredSpots={1}
          joined={false}
          onClose={() => {
            track({
              type: 'agent_group_close',
              sessionId: sessionId || null,
              payload: { groupId: activeGroup.id, groupTitle: activeGroup.title },
            })
            setActiveGroup(null)
          }}
          onNavigate={() => {
            track({
              type: 'agent_group_navigate',
              sessionId: sessionId || null,
              payload: { groupId: activeGroup.id, groupTitle: activeGroup.title },
            })
            setToast('Opening maps / navigation (mock).')
          }}
          onJoin={() => {
            track({
              type: 'agent_group_join',
              sessionId: sessionId || null,
              payload: { groupId: activeGroup.id, groupTitle: activeGroup.title },
            })
            setToast('Join/RSVP is not implemented in this flow (mock).')
          }}
        />
      ) : null}

      {toast ? <Toast message={toast} onClose={() => setToast(null)} /> : null}
      <DebugDrawer open={debugOpen} trace={lastTrace} onClose={() => setDebugOpen(false)} />
    </div>
  )
}
