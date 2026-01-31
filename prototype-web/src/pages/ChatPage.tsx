import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Toast } from '../components/Toast'
import { findProfile } from '../mock/cases'
import { appendMessage, ensureThread, makeMeMessage, makeOtherMessage, parseThreadId, readThreads } from '../lib/threads'
import { subscribe } from '../lib/storage'
import { roleplayChat } from '../lib/agentApi'
import type { ChatThread, Profile } from '../types'
import { track } from '../lib/telemetry'

function formatTime(ts: number) {
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function fallbackReply(profile: Profile) {
  // Fallback response when AI service fails
  const name = profile.name
  return `Hey! Sorry, ${name} is having trouble connecting right now. Let's try again?`
}

export function ChatPage() {
  const navigate = useNavigate()
  const { threadId = '' } = useParams()
  const parsed = useMemo(() => parseThreadId(threadId), [threadId])
  const [toast, setToast] = useState<string | null>(null)

  const [draft, setDraft] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const threadCache = useRef<{ key: string; value: ChatThread | null }>({ key: '', value: null })
  const thread = useSyncExternalStore(
    subscribe,
    () => {
      const raw = readThreads()[threadId] ?? null
      const key = JSON.stringify(raw)
      if (key === threadCache.current.key) {
        return threadCache.current.value
      }
      threadCache.current = { key, value: raw }
      return raw
    },
    () => null,
  )

  const profile = useMemo(() => {
    if (!parsed) return null
    if (parsed.caseId === 'agent') {
      return thread?.profile ?? null
    }
    return findProfile(parsed.caseId, parsed.profileId)
  }, [parsed, thread])

  useEffect(() => {
    if (!parsed) return
    if (!profile) return
    if (parsed.caseId === 'agent') return // thread already created in AgentPage
    ensureThread({ caseId: parsed.caseId, profile })
  }, [parsed, profile, threadId])

  useEffect(() => {
    if (!parsed || !profile) return
    track({
      type: 'chat_open',
      sessionId: null,
      payload: { threadId, profileId: profile.id, profileName: profile.name, caseId: parsed.caseId },
    })
    return () => {
      track({
        type: 'chat_close',
        sessionId: null,
        payload: { threadId, profileId: profile.id, profileName: profile.name, caseId: parsed.caseId },
      })
    }
  }, [threadId, parsed, profile])

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

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || isLoading) return
    try {
      track({
        type: 'chat_message_send',
        sessionId: null,
        payload: { threadId, profileId: profile.id, profileName: profile.name, caseId: parsed.caseId, text: trimmed },
      })
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
        appendMessage(threadId, makeOtherMessage(fallbackReply(profile)))
      }
    } catch {
      setToast("Chat isn't available right now, but you can go back and keep exploring.")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="page chatPage">
      <div className="chatHeader">
        <button className="chatBackBtn" type="button" onClick={() => navigate(-1)}>
          ←
        </button>
        <div className="chatHeaderTitle">{thread?.title ?? profile.name} (mock)</div>
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

        <div className="chatComposer">
          <textarea
            className="input chatInput"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Type a message…"
            disabled={isLoading}
            rows={1}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.ctrlKey && !e.metaKey && !isLoading) {
                e.preventDefault()
                send(draft)
              }
            }}
          />
          <button className="btn" type="button" onClick={() => send(draft)} disabled={isLoading}>
            {isLoading ? '...' : 'Send'}
          </button>
        </div>
      </div>

      {toast ? <Toast message={toast} onClose={() => setToast(null)} /> : null}
    </div>
  )
}
