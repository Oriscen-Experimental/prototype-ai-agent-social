import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useOnboarding } from '../lib/useOnboarding'
import type { OnboardingData } from '../types'
import { track } from '../lib/telemetry'
import { OptionGroup } from '../components/OptionGroup'
import { SocialWarningLabel } from '../components/SocialWarningLabel'
import { computeSortingQuizResult, SORTING_QUESTIONS, type SortingAnswers } from '../lib/sortingQuiz'

const GOALS = ['Meet people', 'Make friends', 'Dating', 'Study / workout buddy', 'Someone to talk to', 'Just browsing']
const INTERESTS = [
  'Craft beer / cocktails',
  'Coffee',
  'Movies',
  'Music',
  'Board games',
  'Fitness',
  'Travel',
  'Photography',
  'Reading',
  'Food',
  'AI / Tech',
]

const TOTAL_STEPS = 4

export function OnboardingPage() {
  const navigate = useNavigate()
  const { complete } = useOnboarding()

  const [step, setStep] = useState(0)

  const [goals, setGoals] = useState<string[]>(['Meet people'])
  const [vibe, setVibe] = useState('Casual')

  const [name, setName] = useState('')
  const [gender, setGender] = useState('Prefer not to say')
  const [age, setAge] = useState('')
  const [city, setCity] = useState('San Francisco')
  const [address, setAddress] = useState('')

  const [interests, setInterests] = useState<string[]>(['Movies', 'Music'])

  const [sortingAnswers, setSortingAnswers] = useState<Partial<SortingAnswers>>({})

  const isSortingComplete = useMemo(() => {
    const keys: Array<keyof SortingAnswers> = [
      'restaurant',
      'travel',
      'birthday',
      'weather',
      'noResponse',
      'awkwardWave',
    ]
    return keys.every((k) => sortingAnswers[k] !== undefined)
  }, [sortingAnswers])

  const sortingResult = useMemo(() => {
    if (!isSortingComplete) return null
    return computeSortingQuizResult(sortingAnswers as SortingAnswers)
  }, [isSortingComplete, sortingAnswers])

  const canNext = useMemo(() => {
    if (step === 0) return goals.length > 0 && vibe.length > 0
    if (step === 1) return name.trim().length > 0 && city.trim().length > 0
    if (step === 2) return interests.length > 0
    if (step === 3) return isSortingComplete
    return false
  }, [step, goals, vibe, name, city, interests, isSortingComplete])

  const next = () => {
    track({ type: 'onboarding_next', sessionId: null, payload: { step } })
    setStep((s) => Math.min(TOTAL_STEPS - 1, s + 1))
  }
  const back = () => {
    track({ type: 'onboarding_back', sessionId: null, payload: { step } })
    setStep((s) => Math.max(0, s - 1))
  }

  const onFinish = () => {
    if (!sortingResult) return
    const data: OnboardingData = {
      name: name.trim(),
      gender,
      age: age.trim(),
      city: city.trim(),
      address: address.trim(),
      interests,
      goals,
      vibe,
      sortingQuiz: {
        noveltyScore: sortingResult.noveltyScore,
        securityScore: sortingResult.securityScore,
        archetype: sortingResult.archetype,
        warningLabel: sortingResult.warningLabel,
      },
    }
    track({ type: 'onboarding_finish', sessionId: null, payload: data as unknown as Record<string, unknown> })
    complete(data)
    navigate('/app')
  }

  return (
    <div className="centerWrap">
      <div className="panel">
        <div className="panelHeader">
          <div className="h1">Quick onboarding</div>
          <div className="muted">This is a mock prototype—just enough to show the basic journey.</div>
        </div>

        <div className="stepper">
          {Array.from({ length: TOTAL_STEPS }).map((_, idx) => (
            <div key={idx} style={{ display: 'contents' }}>
              <div className={step === idx ? 'step stepActive' : 'step'}>{idx + 1}</div>
              {idx < TOTAL_STEPS - 1 ? <div className="stepLine" /> : null}
            </div>
          ))}
        </div>

        {step === 0 ? (
          <div className="stack">
            <div className="sectionTitle">What are you here for? (multi-select)</div>
            <div className="optionRow">
              {GOALS.map((g) => {
                const active = goals.includes(g)
                return (
                  <button
                    key={g}
                    type="button"
                    className={active ? 'chip chipActive' : 'chip'}
                    onClick={() => {
                      track({ type: 'onboarding_goal_toggle', sessionId: null, payload: { goal: g, next: active ? 'remove' : 'add' } })
                      setGoals((prev) => (prev.includes(g) ? prev.filter((x) => x !== g) : [...prev, g]))
                    }}
                  >
                    {g}
                  </button>
                )
              })}
            </div>

            <div className="sectionTitle">What vibe do you want?</div>
            <div className="optionRow">
              {['Casual', 'Serious', 'Direct'].map((v) => (
                <button
                  key={v}
                  type="button"
                  className={vibe === v ? 'chip chipActive' : 'chip'}
                  onClick={() => {
                    track({ type: 'onboarding_vibe_set', sessionId: null, payload: { vibe: v } })
                    setVibe(v)
                  }}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {step === 1 ? (
          <div className="form">
            <label className="label">
              Name *
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g., Alex" />
            </label>
            <div className="grid2">
              <label className="label">
                Gender
                <select className="select" value={gender} onChange={(e) => setGender(e.target.value)}>
                  <option value="Prefer not to say">Prefer not to say</option>
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                  <option value="Other">Other</option>
                </select>
              </label>
              <label className="label">
                Age
                <input className="input" value={age} onChange={(e) => setAge(e.target.value)} placeholder="Optional" />
              </label>
            </div>
            <label className="label">
              City *
              <input className="input" value={city} onChange={(e) => setCity(e.target.value)} placeholder="e.g., San Francisco" />
            </label>
            <label className="label">
              Neighborhood / address (optional)
              <input className="input" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="e.g., Mission District" />
            </label>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="stack">
            <div className="sectionTitle">What are you into? (multi-select)</div>
            <div className="optionRow">
              {INTERESTS.map((i) => {
                const active = interests.includes(i)
                return (
                  <button
                    key={i}
                    type="button"
                    className={active ? 'chip chipActive' : 'chip'}
                    onClick={() =>
                      setInterests((prev) => (prev.includes(i) ? prev.filter((x) => x !== i) : [...prev, i]))
                    }
                  >
                    {i}
                  </button>
                )
              })}
            </div>
            <div className="hint">Used only for the prototype UI; nothing is actually uploaded.</div>
          </div>
        ) : null}

        {step === 3 ? (
          <div className="stack">
            <div className="sectionTitle">Section 1: Sorting (6 Questions)</div>
            <div className="muted" style={{ marginTop: -6 }}>
              Pick whatever feels most natural—there are no “correct” answers.
            </div>

            {SORTING_QUESTIONS.map((q) => (
              <OptionGroup
                key={q.key}
                title={q.title}
                options={q.options.map((o) => ({ value: String(o.value), label: o.label }))}
                value={(sortingAnswers[q.key] as string | undefined) ?? null}
                onChange={(next) => {
                  track({ type: 'sorting_answer', sessionId: null, payload: { key: q.key, value: next } })
                  setSortingAnswers((prev) => ({ ...prev, [q.key]: next as SortingAnswers[typeof q.key] }))
                }}
              />
            ))}

            {sortingResult ? (
              <>
                <div className="row spaceBetween" style={{ marginTop: 4 }}>
                  <div className="muted">
                    Novelty: <b>{sortingResult.noveltyScore}</b> / 3 · Security: <b>{sortingResult.securityScore}</b> / 3
                  </div>
                  <div className="muted">
                    Archetype: <b>{sortingResult.archetype}</b>
                  </div>
                </div>
                <SocialWarningLabel label={sortingResult.warningLabel} archetype={sortingResult.archetype} />
              </>
            ) : (
              <div className="hint">Answer all 6 questions to unlock your Social Warning Label.</div>
            )}
          </div>
        ) : null}

        <div className="row spaceBetween">
          <div className="muted">Step {step + 1} / {TOTAL_STEPS}</div>
          <div className="row">
            {step > 0 ? (
              <button className="btn btnGhost" onClick={back} type="button">
                Back
              </button>
            ) : null}
            {step < TOTAL_STEPS - 1 ? (
              <button className="btn" onClick={next} type="button" disabled={!canNext}>
                Next
              </button>
            ) : (
              <button className="btn" onClick={onFinish} type="button" disabled={!canNext}>
                Enter prototype
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
