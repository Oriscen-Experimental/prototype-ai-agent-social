import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CalendarInviteModal } from '../components/CalendarInviteModal'
import { GroupCard } from '../components/GroupCard'
import { GroupModal } from '../components/GroupModal'
import { OptionGroup } from '../components/OptionGroup'
import { ProfileCard } from '../components/ProfileCard'
import { ProfileModal } from '../components/ProfileModal'
import { Toast } from '../components/Toast'
import { getCase } from '../mock/cases'
import { appendMessage, ensureThread, makeSystemMessage, makeThreadId } from '../lib/threads'
import type { CaseId, ChatMessage, Group, Profile } from '../types'

function sortProfiles(profiles: Profile[]) {
  return [...profiles].sort((a, b) => {
    if (a.presence !== b.presence) return a.presence === 'online' ? -1 : 1
    return b.score - a.score
  })
}

function seedFor(caseId: CaseId, profile: Profile): ChatMessage[] {
  if (profile.kind === 'ai') {
    return [{ id: `${Date.now()}_seed`, role: 'other', text: `你好，我是 ${profile.name}。你想聊点什么？`, at: Date.now() }]
  }
  if (caseId === 'drink') {
    return [
      {
        id: `${Date.now()}_seed`,
        role: 'other',
        text: '嗨～我看到你想找人喝一杯。你更偏清吧还是小酒馆？',
        at: Date.now(),
      },
    ]
  }
  if (caseId === 'tennis') {
    return [
      {
        id: `${Date.now()}_seed`,
        role: 'other',
        text: '嗨～看到你想找人练网球。你一般想在哪个区/哪个球场？更想练基本功还是打对抗？',
        at: Date.now(),
      },
    ]
  }
  return [
    {
      id: `${Date.now()}_seed`,
      role: 'other',
      text: '我在。你可以从“我现在最难受的是…”开始说，也可以只说一句“我很难受”。',
      at: Date.now(),
    },
  ]
}

export function CaseFlowPage(props: { caseId: string | undefined }) {
  const navigate = useNavigate()
  const c = getCase(props.caseId)

  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [submitted, setSubmitted] = useState(false)

  const [activeProfile, setActiveProfile] = useState<Profile | null>(null)
  const [inviteFor, setInviteFor] = useState<Profile | null>(null)
  const [activeGroup, setActiveGroup] = useState<Group | null>(null)
  const [joinedGroupIds, setJoinedGroupIds] = useState<Record<string, boolean>>({})
  const [groupList, setGroupList] = useState<Group[]>(() => (c?.resultType === 'groups' ? c.groups : []))
  const [toast, setToast] = useState<string | null>(null)

  const canSubmit = useMemo(() => {
    if (!c) return false
    const qs = c.questions ?? []
    return qs.every((q) => !q.required || Boolean(answers[q.key]))
  }, [c, answers])

  useEffect(() => {
    if (!c?.questions?.length) return
    if (submitted) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Enter') return
      if (!canSubmit) return
      setSubmitted(true)
      setToast('已根据你的选择完成匹配（mock）')
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [c?.questions?.length, canSubmit, submitted])

  if (!c) {
    return (
      <div className="page">
        <div className="card">
          <div className="h1">找不到这个体验</div>
          <Link to="/app" className="link">
            返回搜索
          </Link>
        </div>
      </div>
    )
  }

  const profiles = c.resultType === 'profiles' ? sortProfiles(c.profiles) : []
  const groups = c.resultType === 'groups' ? groupList : []

  const onGoChat = (profile: Profile) => {
    const caseId = c.id
    try {
      ensureThread({ caseId, profile, seed: seedFor(caseId, profile) })
      navigate(`/app/chat/${makeThreadId(caseId, profile.id)}`)
    } catch {
      setToast('聊天 mock 当前不可用，但你可以返回继续体验')
    }
  }

  const onSendInvite = (profile: Profile, payload: { when: string; note: string }) => {
    try {
      const thread = ensureThread({ caseId: c.id, profile, seed: seedFor(c.id, profile) })
      appendMessage(thread.threadId, makeSystemMessage(`已发送日历邀请（mock）：${payload.when} · ${payload.note}`))
      navigate(`/app/chat/${thread.threadId}`)
    } catch {
      setToast('日历邀请 mock 当前不可用，但你可以返回继续体验')
    }
  }

  const updateGroup = (groupId: string, patch: Partial<Group>) => {
    if (c.resultType !== 'groups') return
    setGroupList((prev) => prev.map((g) => (g.id === groupId ? { ...g, ...patch } : g)))
    setActiveGroup((g) => (g?.id === groupId ? { ...g, ...patch } : g))
  }

  return (
    <div className="page">
      <div className="row spaceBetween">
        <div>
          <div className="muted">
            <Link to="/app" className="link">
              ← 返回
            </Link>
          </div>
          <div className="h1">{c.exampleQuery}</div>
        </div>
        <div className="rightHint">{submitted ? '已匹配（mock）' : '配置需求（mock）'}</div>
      </div>

      <div className="card">
        <div className="assistant">
          <div className="assistantAvatar">AI</div>
          <div className="assistantBubble">
            <div className="assistantText">{c.assistantIntro}</div>
            {c.questions?.length ? (
              <div className="stack">
                {c.questions.map((q) => (
                  <OptionGroup
                    key={q.key}
                    title={q.question}
                    options={q.options}
                    value={answers[q.key] ?? null}
                    onChange={(next) => setAnswers((prev) => ({ ...prev, [q.key]: next }))}
                  />
                ))}
                <div className="row">
                  <button
                    className="btn"
                    type="button"
                    disabled={!canSubmit || submitted}
                    onClick={() => {
                      if (!canSubmit || submitted) return
                      setSubmitted(true)
                      setToast('已根据你的选择完成匹配（mock）')
                    }}
                  >
                    回车/开始匹配
                  </button>
                  <div className="muted">（不会让你手打回复，全部点选）</div>
                </div>
              </div>
            ) : (
              <div className="muted">（本体验不需要补问，直接展示候选）</div>
            )}
          </div>
        </div>
      </div>

      <div className="row spaceBetween">
        <div className="sectionTitle">匹配结果（在线优先）</div>
        {c.resultType === 'profiles' ? (
          <div className="muted">{profiles.filter((p) => p.presence === 'online').length} 在线</div>
        ) : (
          <div className="muted">{groups.length} 个局</div>
        )}
      </div>

      {c.questions?.length && !submitted ? (
        <div className="card">
          <div className="muted">
            完成上面的点选后，点击“开始匹配”即可看到{c.resultType === 'profiles' ? '候选用户' : '候选局'}。
          </div>
        </div>
      ) : c.resultType === 'profiles' ? (
        <div className="gridCards">
          {profiles.map((p) => (
            <ProfileCard key={p.id} profile={p} onClick={() => setActiveProfile(p)} />
          ))}
        </div>
      ) : (
        <div className="gridCards">
          {groups.map((g) => (
            <GroupCard key={g.id} group={g} onClick={() => setActiveGroup(g)} />
          ))}
        </div>
      )}

      {activeProfile ? (
        <ProfileModal
          profile={activeProfile}
          onClose={() => setActiveProfile(null)}
          onChat={() => onGoChat(activeProfile)}
          onInvite={activeProfile.kind === 'human' ? () => setInviteFor(activeProfile) : undefined}
        />
      ) : null}

      {activeGroup ? (
        <GroupModal
          group={activeGroup}
          joined={Boolean(joinedGroupIds[activeGroup.id])}
          onClose={() => setActiveGroup(null)}
          onNavigate={() => setToast('导航/打开地图（mock）')}
          onJoin={() => {
            if (joinedGroupIds[activeGroup.id]) return
            if (activeGroup.availability.status === 'full') {
              setToast('该局已满（mock）')
              return
            }
            const partySizeRaw = answers.partySize ?? '1'
            const requested =
              partySizeRaw === '4+'
                ? 4
                : Number.isFinite(Number(partySizeRaw))
                  ? Math.max(1, Number(partySizeRaw))
                  : 1
            const spots = Math.max(0, activeGroup.capacity - activeGroup.memberCount)
            const delta = Math.max(1, Math.min(spots, requested))
            setJoinedGroupIds((prev) => ({ ...prev, [activeGroup.id]: true }))
            if (activeGroup.memberCount < activeGroup.capacity) {
              updateGroup(activeGroup.id, { memberCount: Math.min(activeGroup.capacity, activeGroup.memberCount + delta) })
            }
            setToast(`报名成功（mock）：占位 ${delta} 人`)
          }}
        />
      ) : null}

      {inviteFor ? (
        <CalendarInviteModal
          title={`给 ${inviteFor.name} 发日历邀请`}
          onClose={() => setInviteFor(null)}
          onSend={(payload) => {
            setInviteFor(null)
            onSendInvite(inviteFor, payload)
          }}
        />
      ) : null}

      {toast ? <Toast message={toast} onClose={() => setToast(null)} /> : null}
    </div>
  )
}
