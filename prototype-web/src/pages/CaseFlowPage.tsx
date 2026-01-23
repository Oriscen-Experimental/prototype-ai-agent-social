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

function partySizeFrom(raw: string | undefined) {
  if (!raw) return 1
  if (raw === '4+') return 4
  const n = Number(raw)
  if (!Number.isFinite(n)) return 1
  return Math.max(1, Math.floor(n))
}

function sortGroups(groups: Group[]) {
  const score = (g: Group) => {
    if (g.availability.status === 'open') return 0
    if (g.availability.status === 'scheduled') return 1
    return 2
  }
  return [...groups].sort((a, b) => score(a) - score(b))
}

function seedFor(caseId: CaseId, profile: Profile): ChatMessage[] {
  if (profile.kind === 'ai') {
    return [{ id: `${Date.now()}_seed`, role: 'other', text: `Hi—I'm ${profile.name}. What do you want to talk about?`, at: Date.now() }]
  }
  if (caseId === 'drink') {
    return [
      {
        id: `${Date.now()}_seed`,
        role: 'other',
        text: "Hey! I saw you're looking to grab a drink. Do you prefer a cocktail bar or a brewery?",
        at: Date.now(),
      },
    ]
  }
  if (caseId === 'tennis') {
    return [
      {
        id: `${Date.now()}_seed`,
        role: 'other',
        text: "Hey! I saw you're looking for a tennis partner. Where do you usually play—and do you want to rally/drill or play points?",
        at: Date.now(),
      },
    ]
  }
  return [
    {
      id: `${Date.now()}_seed`,
      role: 'other',
      text: "I'm here. You can start with “the hardest part right now is…” or just say “I'm not doing great.”",
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
      setToast('Matches updated based on your choices (mock).')
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [c?.questions?.length, canSubmit, submitted])

  if (!c) {
    return (
      <div className="page">
        <div className="card">
          <div className="h1">Demo not found</div>
          <Link to="/app" className="link">
            Back to search
          </Link>
        </div>
      </div>
    )
  }

  const profiles = c.resultType === 'profiles' ? sortProfiles(c.profiles) : []
  const requestedPartySize = partySizeFrom(answers.partySize)
  const groupsAll = c.resultType === 'groups' ? groupList : []
  const groupsFiltered =
    c.resultType === 'groups' && submitted
      ? sortGroups(
          groupsAll.filter((g) => {
            if (g.availability.status === 'full') return false
            const spots = g.capacity - g.memberCount
            return spots >= requestedPartySize
          }),
        )
      : sortGroups(groupsAll)

  const onGoChat = (profile: Profile) => {
    const caseId = c.id
    try {
      ensureThread({ caseId, profile, seed: seedFor(caseId, profile) })
      navigate(`/app/chat/${makeThreadId(caseId, profile.id)}`)
    } catch {
      setToast("Chat isn't available right now (mock), but you can go back and keep exploring.")
    }
  }

  const onSendInvite = (profile: Profile, payload: { when: string; note: string }) => {
    try {
      const thread = ensureThread({ caseId: c.id, profile, seed: seedFor(c.id, profile) })
      appendMessage(thread.threadId, makeSystemMessage(`Calendar invite sent (mock): ${payload.when} · ${payload.note}`))
      navigate(`/app/chat/${thread.threadId}`)
    } catch {
      setToast("Calendar invites aren't available right now (mock), but you can go back and keep exploring.")
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
              ← Back
            </Link>
          </div>
          <div className="h1">{c.exampleQuery}</div>
        </div>
        <div className="rightHint">{submitted ? 'Matched (mock)' : 'Set preferences (mock)'}</div>
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
                      setToast('Matches updated based on your choices (mock).')
                    }}
                  >
                    Enter / Match
                  </button>
                  <div className="muted">(No typing needed—just click options.)</div>
                </div>
              </div>
            ) : (
              <div className="muted">(No follow-ups needed for this demo.)</div>
            )}
          </div>
        </div>
      </div>

      <div className="row spaceBetween">
        <div className="sectionTitle">{c.resultType === 'profiles' ? 'Matches (online first)' : 'Recommended games'}</div>
        {c.resultType === 'profiles' ? (
          <div className="muted">{profiles.filter((p) => p.presence === 'online').length} online</div>
        ) : (
          <div className="muted">{(submitted ? groupsFiltered : groupsAll).length} games</div>
        )}
      </div>

      {c.questions?.length && !submitted ? (
        <div className="card">
          <div className="muted">
            After you pick the options above, click “Match” to see {c.resultType === 'profiles' ? 'people' : 'games'}.
          </div>
        </div>
      ) : c.resultType === 'profiles' ? (
        <div className="gridCards">
          {profiles.map((p) => (
            <ProfileCard key={p.id} profile={p} onClick={() => setActiveProfile(p)} />
          ))}
        </div>
      ) : (
        <>
          {submitted && groupsFiltered.length === 0 ? (
            <div className="card">
              <div className="muted">
                No games can fit your party of <b>{requestedPartySize}</b> right now (mock). Try adjusting party size or timing.
              </div>
            </div>
          ) : (
            <div className="gridCards">
              {(submitted ? groupsFiltered : groupsAll).map((g) => (
                <GroupCard key={g.id} group={g} onClick={() => setActiveGroup(g)} />
              ))}
            </div>
          )}
        </>
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
          requiredSpots={c.resultType === 'groups' ? requestedPartySize : 1}
          joined={Boolean(joinedGroupIds[activeGroup.id])}
          onClose={() => setActiveGroup(null)}
          onNavigate={() => setToast('Opening maps / navigation (mock).')}
          onJoin={() => {
            if (joinedGroupIds[activeGroup.id]) return
            if (activeGroup.availability.status === 'full') {
              setToast('This game is full (mock).')
              return
            }
            const spots = Math.max(0, activeGroup.capacity - activeGroup.memberCount)
            if (spots < requestedPartySize) {
              setToast(`Not enough spots (need ${requestedPartySize}, have ${spots}) (mock).`)
              return
            }
            const delta = requestedPartySize
            setJoinedGroupIds((prev) => ({ ...prev, [activeGroup.id]: true }))
            if (activeGroup.memberCount < activeGroup.capacity) {
              updateGroup(activeGroup.id, { memberCount: Math.min(activeGroup.capacity, activeGroup.memberCount + delta) })
            }
            setToast(`Joined (mock): held ${delta} spot(s).`)
          }}
        />
      ) : null}

      {inviteFor ? (
        <CalendarInviteModal
          title={`Send a calendar invite to ${inviteFor.name}`}
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
