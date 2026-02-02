import { useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useOnboarding } from '../lib/useOnboarding'
import type { OnboardingData } from '../types'
import { track } from '../lib/telemetry'
import { OptionGroup } from '../components/OptionGroup'
import { SORTING_QUESTIONS, type SortingAnswers, type SortingQuizResult } from '../lib/sortingQuiz'
import { Toast } from '../components/Toast'
import { OnboardingCompletionModal } from '../components/OnboardingCompletionModal'
import { streamSortingLabels } from '../lib/agentApi'

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
  const [toast, setToast] = useState<string | null>(null)

  const [goals, setGoals] = useState<string[]>(['Meet people'])
  const [vibe, setVibe] = useState('Casual')

  const [name, setName] = useState('')
  const [gender, setGender] = useState('Prefer not to say')
  const [age, setAge] = useState('')
  const [city, setCity] = useState('San Francisco')
  const [address, setAddress] = useState('')

  const [interests, setInterests] = useState<string[]>(['Movies', 'Music'])

  const [sortingAnswers, setSortingAnswers] = useState<Partial<SortingAnswers>>({})
  const [showCompletionModal, setShowCompletionModal] = useState(false)

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

  // Partial result that gets populated via streaming
  const [sortingResult, setSortingResult] = useState<Partial<SortingQuizResult>>({})
  const [isGenerating, setIsGenerating] = useState(false)
  const lastStreamKeyRef = useRef<string>('')

  const applySortingAnswer = (key: keyof SortingAnswers, value: SortingAnswers[keyof SortingAnswers]) => {
    const nextAnswers = { ...sortingAnswers, [key]: value } as Partial<SortingAnswers>
    setSortingAnswers(nextAnswers)

    const keys: Array<keyof SortingAnswers> = ['restaurant', 'travel', 'birthday', 'weather', 'noResponse', 'awkwardWave']
    const allComplete = keys.every((k) => nextAnswers[k] !== undefined)
    if (!allComplete) {
      setSortingResult({})
      return
    }

    // Quiz complete - show modal immediately and start streaming
    const streamKey = JSON.stringify(nextAnswers)
    if (streamKey === lastStreamKeyRef.current) return
    lastStreamKeyRef.current = streamKey

    setShowCompletionModal(true)
    setIsGenerating(true)
    setSortingResult({})

    streamSortingLabels(
      { name: name.trim() || null, answers: nextAnswers as SortingAnswers },
      (event) => {
        if (event.type === 'scores') {
          setSortingResult((prev) => ({
            ...prev,
            noveltyScore: event.noveltyScore,
            securityScore: event.securityScore,
            archetype: event.archetype,
          }))
        } else if (event.type === 'warning') {
          setSortingResult((prev) => ({ ...prev, warningLabel: event.warningLabel }))
        } else if (event.type === 'nutrition') {
          setSortingResult((prev) => ({ ...prev, nutritionFacts: event.nutritionFacts }))
        } else if (event.type === 'manual') {
          setSortingResult((prev) => ({ ...prev, userManual: event.userManual }))
        } else if (event.type === 'done') {
          setIsGenerating(false)
        }
      }
    ).catch((err) => {
      console.error('[OnboardingPage] streaming failed:', err)
      setIsGenerating(false)
      setToast('Failed to generate results. Please try again.')
    })
  }

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
    setShowCompletionModal(true)
  }

  const handleProceed = () => {
    // Only proceed if we have all the data
    if (!sortingResult.archetype || !sortingResult.warningLabel || !sortingResult.nutritionFacts || !sortingResult.userManual) {
      return
    }

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
        noveltyScore: sortingResult.noveltyScore ?? 0,
        securityScore: sortingResult.securityScore ?? 0,
        archetype: sortingResult.archetype,
        warningLabel: sortingResult.warningLabel,
        nutritionFacts: sortingResult.nutritionFacts,
        userManual: sortingResult.userManual,
      },
    }
    track({ type: 'onboarding_finish', sessionId: null, payload: data as unknown as Record<string, unknown> })
    complete(data)
    navigate('/app')
  }

  // Check if all data is ready for proceed button
  const canProceed = !isGenerating &&
    sortingResult.archetype &&
    sortingResult.warningLabel &&
    sortingResult.nutritionFacts &&
    sortingResult.userManual

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
              Pick whatever feels most natural—there are no "correct" answers.
            </div>

            {SORTING_QUESTIONS.map((q) => (
              <OptionGroup
                key={q.key}
                title={q.title}
                options={q.options.map((o) => ({ value: String(o.value), label: o.label }))}
                value={(sortingAnswers[q.key] as string | undefined) ?? null}
                onChange={(next) => {
                  track({ type: 'sorting_answer', sessionId: null, payload: { key: q.key, value: next } })
                  applySortingAnswer(q.key, next as SortingAnswers[typeof q.key])
                }}
              />
            ))}

            {!isSortingComplete ? (
              <div className="hint">Answer all 6 questions to see your results.</div>
            ) : null}
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
      {showCompletionModal ? (
        <OnboardingCompletionModal
          archetype={sortingResult.archetype}
          warningLabel={sortingResult.warningLabel}
          nutritionFacts={sortingResult.nutritionFacts}
          userManual={sortingResult.userManual}
          onProceed={handleProceed}
          canProceed={!!canProceed}
        />
      ) : null}
      {toast ? <Toast message={toast} onClose={() => setToast(null)} /> : null}
    </div>
  )
}
