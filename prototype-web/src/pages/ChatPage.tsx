import { useEffect, useMemo, useState, useSyncExternalStore } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { CalendarInviteModal } from '../components/CalendarInviteModal'
import { Toast } from '../components/Toast'
import { findProfile, getCaseById } from '../mock/cases'
import { appendMessage, ensureThread, makeMeMessage, makeOtherMessage, makeSystemMessage, parseThreadId, readThreads } from '../lib/threads'
import { subscribe } from '../lib/storage'
import type { Profile } from '../types'

function formatTime(ts: number) {
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function mockReply(profile: Profile, text: string) {
  const t = text.trim()
  if (profile.kind === 'ai') {
    if (profile.id === 'ai-warm') return `I'm here. It sounds like things feel heavy right now. What was the most painful moment or thought?`
    if (profile.id === 'ai-coach')
      return `Let's break it down: 1) What outcome do you want? 2) What's the biggest blocker? 3) What's the smallest next step you can take?`
    return `Let's try a different angle: treat this as the first scene of a story. Who's the main character—and what do they need most right now?`
  }
  if (t.toLowerCase().includes('time') || t.toLowerCase().includes('when')) return "This week works for me. What day are you thinking?"
  if (t.toLowerCase().includes('drink') || t.toLowerCase().includes('bar')) return "I'm down. Do you prefer a cocktail bar or a brewery?"
  if (t.toLowerCase().includes('tennis')) return "Nice—do you want to rally/drill or play points?"
  return "Got it. If you're up for it, tell me a little more—I'm listening."
}

export function ChatPage() {
  const navigate = useNavigate()
  const { threadId = '' } = useParams()
  const parsed = useMemo(() => parseThreadId(threadId), [threadId])
  const [toast, setToast] = useState<string | null>(null)
  const [inviteOpen, setInviteOpen] = useState(false)

  const profile = useMemo(() => {
    if (!parsed) return null
    return findProfile(parsed.caseId, parsed.profileId)
  }, [parsed])

  const [draft, setDraft] = useState('')
  const thread = useSyncExternalStore(
    subscribe,
    () => readThreads()[threadId] ?? null,
    () => null,
  )

  useEffect(() => {
    if (!parsed) return
    if (!profile) return
    ensureThread({ caseId: parsed.caseId, profile })
  }, [parsed, profile, threadId])

  if (!parsed || !profile) {
    return (
      <div className="page">
        <div className="card">
          <div className="h1">This chat doesn't exist (mock)</div>
          <Link className="link" to="/app">
            Back to search
          </Link>
        </div>
      </div>
    )
  }

  const caseTitle = getCaseById(parsed.caseId).title

  const send = (text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return
    try {
      appendMessage(threadId, makeMeMessage(trimmed))
      setDraft('')
      window.setTimeout(() => {
        try {
          appendMessage(threadId, makeOtherMessage(mockReply(profile, trimmed)))
        } catch {
          // ignore
        }
      }, 500)
    } catch {
      setToast("Chat isn't available right now (mock), but you can go back and keep exploring.")
    }
  }

  return (
    <div className="page chatPage">
      <div className="row spaceBetween">
        <div>
          <div className="muted">
            <button className="linkLike" type="button" onClick={() => navigate(-1)}>
              ← Back
            </button>
          </div>
          <div className="h1">{thread?.title ?? profile.name}</div>
          <div className="muted">
            {caseTitle} · {profile.kind === 'ai' ? 'AI' : 'Human'} · {profile.presence === 'online' ? 'Online' : 'Offline'}
          </div>
        </div>
        {profile.kind === 'human' ? (
          <button className="btn btnGhost" type="button" onClick={() => setInviteOpen(true)}>
            Calendar invite (mock)
          </button>
        ) : null}
      </div>

      <div className="chatLayout">
        <div className="chatMessages card">
          {thread?.messages.map((m) => (
            <div key={m.id} className={m.role === 'me' ? 'msg msgMe' : m.role === 'system' ? 'msg msgSys' : 'msg msgOther'}>
              <div className="msgBubble">{m.text}</div>
              <div className="msgMeta">{formatTime(m.at)}</div>
            </div>
          ))}
        </div>

        <div className="chatComposer card">
          <div className="tagRow">
            {profile.topics.slice(0, 5).map((t) => (
              <button key={t} type="button" className="tag tagBtn" onClick={() => setDraft((d) => (d ? `${d} ${t}` : t))}>
                {t}
              </button>
            ))}
          </div>
          <div className="row">
            <input
              className="input"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Type a message… (mock)"
              onKeyDown={(e) => {
                if (e.key === 'Enter') send(draft)
              }}
            />
            <button className="btn" type="button" onClick={() => send(draft)}>
              Send
            </button>
          </div>
          <div className="muted">Note: this is a prototype—no real backend.</div>
        </div>
      </div>

      {inviteOpen ? (
        <CalendarInviteModal
          title={`Send a calendar invite to ${profile.name}`}
          onClose={() => setInviteOpen(false)}
          onSend={(payload) => {
            setInviteOpen(false)
            appendMessage(threadId, makeSystemMessage(`Calendar invite sent (mock): ${payload.when} · ${payload.note}`))
            setToast('Calendar invite sent (mock)')
          }}
        />
      ) : null}

      {toast ? <Toast message={toast} onClose={() => setToast(null)} /> : null}
    </div>
  )
}
