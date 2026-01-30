import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { CalendarInviteModal } from '../components/CalendarInviteModal'
import { Toast } from '../components/Toast'
import { findProfile, getCaseById } from '../mock/cases'
import { appendMessage, ensureThread, makeMeMessage, makeOtherMessage, makeSystemMessage, parseThreadId, readThreads } from '../lib/threads'
import { subscribe } from '../lib/storage'
import { roleplayChat } from '../lib/agentApi'
import type { Profile } from '../types'

function formatTime(ts: number) {
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function fallbackReply(profile: Profile, _text: string) {
  // Fallback response when AI service fails
  const name = profile.name
  return `Hey! Sorry, ${name} is having trouble connecting right now. Let's try again?`
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
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
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

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || isLoading) return
    try {
      appendMessage(threadId, makeMeMessage(trimmed))
      setDraft('')
      setIsLoading(true)

      // Build chat history for AI
      const currentThread = readThreads()[threadId]
      const chatHistory = (currentThread?.messages ?? [])
        .filter((m) => m.role === 'me' || m.role === 'other')
        .map((m) => ({
          role: m.role === 'me' ? 'user' as const : 'assistant' as const,
          content: m.text,
        }))

      try {
        const reply = await roleplayChat({ profile, messages: chatHistory })
        appendMessage(threadId, makeOtherMessage(reply))
      } catch (err) {
        console.error('[ChatPage] roleplayChat failed:', err)
        // Fallback to local reply on error
        appendMessage(threadId, makeOtherMessage(fallbackReply(profile, trimmed)))
      }
    } catch {
      setToast("Chat isn't available right now, but you can go back and keep exploring.")
    } finally {
      setIsLoading(false)
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
          <div className="h1">{thread?.title ?? profile.name} (mock)</div>
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
          {isLoading && (
            <div className="msg msgOther">
              <div className="msgBubble">typing...</div>
            </div>
          )}
          <div ref={messagesEndRef} />
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
              placeholder="Type a message…"
              disabled={isLoading}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !isLoading) send(draft)
              }}
            />
            <button className="btn" type="button" onClick={() => send(draft)} disabled={isLoading}>
              {isLoading ? '...' : 'Send'}
            </button>
          </div>
          <div className="muted">AI is roleplaying as this character (mock)</div>
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
