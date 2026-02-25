import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

type ChatOption = { id: string; label: string }

type Message = {
  id: string
  role: 'ai' | 'user'
  text: string
  options?: ChatOption[]
}

const SCRIPTED: Record<string, { reply: string; options?: ChatOption[] }> = {
  'first-reply': {
    reply: "I hear you. That's more common than you think — a lot of people feel the same way. Let me understand better. Which of these sounds most like you?",
    options: [
      { id: 'hard-to-fit-in', label: "I want to find people to hang out with... but it's hard to fit in" },
      { id: 'dont-know-where', label: "I want to meet new friends, but I don't know where to start" },
      { id: 'conversations-fizzle', label: "I feel like people don't really like me... conversations always fizzle out" },
    ],
  },
  'hard-to-fit-in': {
    reply: "That makes total sense. Fitting in can feel overwhelming, but you don't have to change who you are. Our system can match you with people who share your interests and vibe — so you're already starting from common ground. Want me to help you find compatible people nearby?",
  },
  'dont-know-where': {
    reply: "Starting is always the hardest part! What if I set you up with a casual, low-pressure experience? We can match you with someone for a relaxed hangout — coffee, a walk, or whatever feels comfortable. No pressure, just a friendly conversation.",
  },
  'conversations-fizzle': {
    reply: "I appreciate you sharing that — it takes courage. Sometimes conversations fizzle not because of you, but because of compatibility. Our matching considers personality and communication style, not just interests. We can also help you practice with conversation guides and social exercises. Want to try?",
  },
}

export function DemoChatPage() {
  const navigate = useNavigate()
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'greeting',
      role: 'ai',
      text: "Hey! I noticed you want to connect with people but feel it's hard. Tell me more about what's going on?",
    },
  ])
  const [draft, setDraft] = useState('')
  const [phase, setPhase] = useState<'free-text' | 'options-shown' | 'done'>('free-text')
  const [typing, setTyping] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, typing])

  const addAiMessage = (scriptKey: string) => {
    setTyping(true)
    setTimeout(() => {
      const resp = SCRIPTED[scriptKey]
      if (!resp) return
      setMessages(prev => [
        ...prev,
        {
          id: `ai-${Date.now()}`,
          role: 'ai',
          text: resp.reply,
          options: resp.options,
        },
      ])
      setTyping(false)
      if (resp.options) {
        setPhase('options-shown')
      } else {
        setPhase('done')
      }
    }, 800)
  }

  const sendFreeText = () => {
    if (!draft.trim() || phase !== 'free-text') return
    setMessages(prev => [
      ...prev,
      { id: `user-${Date.now()}`, role: 'user', text: draft.trim() },
    ])
    setDraft('')
    addAiMessage('first-reply')
  }

  const selectOption = (opt: ChatOption) => {
    if (phase !== 'options-shown') return
    setMessages(prev => [
      ...prev,
      { id: `user-${Date.now()}`, role: 'user', text: opt.label },
    ])
    addAiMessage(opt.id)
  }

  return (
    <div className="page">
      <div style={{ marginBottom: 12 }}>
        <button className="linkLike" type="button" onClick={() => navigate('/app')}>
          &larr; Back
        </button>
      </div>

      <div className="h1" style={{ marginBottom: 4 }}>AI Assistant</div>
      <div className="muted" style={{ marginBottom: 16 }}>
        Demo conversation &mdash; all responses are pre-scripted
      </div>

      <div className="chatLayout">
        <div className="chatMessages card">
          {messages.map(m => (
            <div key={m.id} className={m.role === 'user' ? 'msg msgMe' : 'msg'}>
              <div className="msgBubble">
                {m.text}
                {m.options && (
                  <div className="demoChatOptions">
                    {m.options.map(opt => (
                      <button
                        key={opt.id}
                        className="demoChatOption"
                        type="button"
                        onClick={() => selectOption(opt)}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {typing && (
            <div className="msg">
              <div className="msgBubble">
                <span className="typingDots">
                  <span className="typingDot" />
                  <span className="typingDot" />
                  <span className="typingDot" />
                </span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="chatComposer card">
          {phase === 'done' ? (
            <div className="row spaceBetween" style={{ flex: 1 }}>
              <div className="muted">Demo complete.</div>
              <button className="btn" type="button" onClick={() => navigate('/app')}>
                Back to Home
              </button>
            </div>
          ) : (
            <>
              <input
                className="input"
                style={{ flex: 1 }}
                value={draft}
                onChange={e => setDraft(e.target.value)}
                placeholder={
                  phase === 'free-text'
                    ? 'Type anything... (this is a demo)'
                    : 'Choose an option above...'
                }
                disabled={phase !== 'free-text' || typing}
                onKeyDown={e => { if (e.key === 'Enter') sendFreeText() }}
              />
              <button
                className="btn"
                type="button"
                onClick={sendFreeText}
                disabled={phase !== 'free-text' || typing || !draft.trim()}
              >
                Send
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
