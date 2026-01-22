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
    if (profile.id === 'ai-warm') return `我在。听起来你现在有点难。你愿意说说“最刺痛的点”是哪一句/哪件事吗？`
    if (profile.id === 'ai-coach')
      return `我先帮你拆一下：1) 你想要的结果是什么？2) 现在最大的阻碍是什么？3) 你能做的最小一步是什么？`
    return `我们来换个视角：把这件事当成一个故事的第一幕。主角是谁？他/她此刻最需要的是什么？`
  }
  if (t.includes('时间') || t.includes('什么时候')) return '我这周都还行～你想周几？'
  if (t.includes('喝') || t.includes('酒')) return '可以啊，我更偏清吧/精酿。你呢？'
  return '收到～你可以多说一点点，我在听。'
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
          <div className="h1">这个聊天不存在（mock）</div>
          <Link className="link" to="/app">
            返回搜索
          </Link>
        </div>
      </div>
    )
  }

  const caseTitle = getCaseById(parsed.caseId).title

  const send = (text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return
    appendMessage(threadId, makeMeMessage(trimmed))
    setDraft('')
    window.setTimeout(() => {
      appendMessage(threadId, makeOtherMessage(mockReply(profile, trimmed)))
    }, 500)
  }

  return (
    <div className="page chatPage">
      <div className="row spaceBetween">
        <div>
          <div className="muted">
            <button className="linkLike" type="button" onClick={() => navigate(-1)}>
              ← 返回
            </button>
          </div>
          <div className="h1">{thread?.title ?? profile.name}</div>
          <div className="muted">
            {caseTitle} · {profile.kind === 'ai' ? 'AI' : '真人'} · {profile.presence === 'online' ? '在线' : '离线'}
          </div>
        </div>
        {profile.kind === 'human' ? (
          <button className="btn btnGhost" type="button" onClick={() => setInviteOpen(true)}>
            发日历约（mock）
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
              placeholder="输入一句话…（mock）"
              onKeyDown={(e) => {
                if (e.key === 'Enter') send(draft)
              }}
            />
            <button className="btn" type="button" onClick={() => send(draft)}>
              发送
            </button>
          </div>
          <div className="muted">提示：这是原型，没有真实后端。</div>
        </div>
      </div>

      {inviteOpen ? (
        <CalendarInviteModal
          title={`给 ${profile.name} 发日历邀请`}
          onClose={() => setInviteOpen(false)}
          onSend={(payload) => {
            setInviteOpen(false)
            appendMessage(threadId, makeSystemMessage(`已发送日历邀请（mock）：${payload.when} · ${payload.note}`))
            setToast('日历邀请已发送（mock）')
          }}
        />
      ) : null}

      {toast ? <Toast message={toast} onClose={() => setToast(null)} /> : null}
    </div>
  )
}
