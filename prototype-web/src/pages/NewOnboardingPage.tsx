import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useOnboarding } from '../lib/useOnboarding.ts'
import { useAuth } from '../lib/AuthContext.tsx'
import { saveUserProfile } from '../lib/agentApi.ts'
import type { RunningProfile } from '../types.ts'

const GENDER_OPTIONS = ['Male', 'Female', 'Non-binary', 'Prefer not to say']
const CITY_OPTIONS = ['San Francisco'] as const

const EXPERIENCE_LEVELS = [
  { value: 'beginner', label: 'Beginner', desc: 'New to running or < 6 months' },
  { value: 'intermediate', label: 'Intermediate', desc: 'Regular runner, 6 months – 2 years' },
  { value: 'advanced', label: 'Advanced', desc: 'Experienced, 2+ years' },
  { value: 'competitive', label: 'Competitive', desc: 'Racing & chasing PRs' },
] as const

const PACE_OPTIONS = [
  { value: 'easy', label: 'Easy (7:00+/km)' },
  { value: 'moderate', label: 'Moderate (5:30–7:00/km)' },
  { value: 'fast', label: 'Fast (4:30–5:30/km)' },
  { value: 'racing', label: 'Racing (< 4:30/km)' },
  { value: 'any', label: 'Any pace' },
] as const

const DISTANCE_OPTIONS = [
  { value: '< 5km', label: '< 5 km' },
  { value: '5-10km', label: '5–10 km' },
  { value: '10-21km', label: '10–21 km' },
  { value: '21km+', label: '21 km+' },
  { value: 'varies', label: 'Varies' },
] as const

const AVAILABILITY_SLOTS = [
  { key: 'weekdayMorning', label: 'Weekday Morning', time: '6 am – 9 am' },
  { key: 'weekdayLunch', label: 'Weekday Lunch', time: '11 am – 2 pm' },
  { key: 'weekdayEvening', label: 'Weekday Evening', time: '5 pm – 9 pm' },
  { key: 'weekendMorning', label: 'Weekend Morning', time: '6 am – 12 pm' },
  { key: 'weekendAfternoon', label: 'Weekend Afternoon', time: '12 pm – 6 pm' },
] as const

const FREQUENCY_OPTIONS = [
  { value: '1-2', label: '1–2 / week' },
  { value: '3-4', label: '3–4 / week' },
  { value: '5+', label: '5+ / week' },
  { value: 'flexible', label: 'Flexible' },
] as const

const RUN_TYPE_OPTIONS = [
  { value: 'road', label: 'Road' },
  { value: 'trail', label: 'Trail' },
  { value: 'track', label: 'Track' },
  { value: 'treadmill', label: 'Treadmill' },
] as const

export function NewOnboardingPage() {
  const navigate = useNavigate()
  const { isCompleted, complete, reset } = useOnboarding()
  const { user, logout, markOnboardingComplete } = useAuth()

  // Saving state
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Basic info
  const [name, setName] = useState(user?.displayName ?? '')
  const [gender, setGender] = useState('Prefer not to say')
  const [age, setAge] = useState('')
  const [city, setCity] = useState('San Francisco')

  // Interest
  const [runningSelected, setRunningSelected] = useState(false)

  // Running level
  const [experience, setExperience] = useState<RunningProfile['level']['experience'] | ''>('')
  const [paceRange, setPaceRange] = useState<RunningProfile['level']['paceRange'] | ''>('')
  const [typicalDistance, setTypicalDistance] = useState<RunningProfile['level']['typicalDistance'] | ''>('')

  // Availability
  const [availability, setAvailability] = useState<Record<string, boolean>>({})

  // Preferences
  const [weeklyFrequency, setWeeklyFrequency] = useState<string>('')
  const [runTypes, setRunTypes] = useState<string[]>([])

  // Female only
  const [femaleOnly, setFemaleOnly] = useState(false)

  if (isCompleted) {
    return <Navigate to="/app" replace />
  }

  const canFinish = name.trim().length > 0 && runningSelected && experience !== ''

  const toggleAvailability = (key: string) => {
    setAvailability(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const toggleRunType = (type: string) => {
    setRunTypes(prev =>
      prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type],
    )
  }

  const onFinish = async () => {
    const runningProfile: RunningProfile = {
      level: {
        experience: experience as RunningProfile['level']['experience'],
        ...(paceRange ? { paceRange: paceRange as RunningProfile['level']['paceRange'] } : {}),
        ...(typicalDistance ? { typicalDistance: typicalDistance as RunningProfile['level']['typicalDistance'] } : {}),
      },
    }

    // Availability – only include if at least one slot is selected
    const selectedSlots = Object.entries(availability).filter(([, v]) => v)
    if (selectedSlots.length > 0) {
      runningProfile.availability = Object.fromEntries(selectedSlots) as RunningProfile['availability']
    }

    // Preferences
    if (weeklyFrequency || runTypes.length > 0) {
      runningProfile.preferences = {
        ...(weeklyFrequency ? { weeklyFrequency: weeklyFrequency as NonNullable<RunningProfile['preferences']>['weeklyFrequency'] } : {}),
        ...(runTypes.length > 0 ? { runTypes: runTypes as NonNullable<RunningProfile['preferences']>['runTypes'] } : {}),
      }
    }

    // Female only
    if (gender === 'Female' && femaleOnly) {
      runningProfile.femaleOnly = true
    }

    const onboardingData = {
      name: name.trim(),
      gender,
      age: age.trim(),
      city,
      address: '',
      interests: ['Running'],
      runningProfile,
    }

    // Save to backend
    if (user?.uid) {
      setSaving(true)
      setError(null)
      try {
        await saveUserProfile(user.uid, {
          name: name.trim(),
          gender,
          age: age.trim(),
          city,
          interests: ['Running'],
          runningProfile,
        })
        // Update auth context
        markOnboardingComplete()
      } catch (e) {
        console.error('Failed to save profile to backend:', e)
        setError('Failed to save profile. Please try again.')
        setSaving(false)
        return  // Don't proceed if save failed
      }
      setSaving(false)
    }

    // Also save to localStorage as cache
    complete(onboardingData)
    navigate('/app')
  }

  return (
    <div className="centerWrap">
      <div className="panel onboardingPanel">
        <div className="panelHeader">
          <div className="row spaceBetween" style={{ alignItems: 'flex-start' }}>
            <div>
              <div className="h1">Tell us about yourself</div>
              <div className="muted" style={{ marginTop: 6 }}>
                This helps us personalize your experience.
              </div>
            </div>
            <button
              className="btn btnGhost"
              type="button"
              onClick={() => { reset(); logout(); navigate('/login') }}
            >
              Logout
            </button>
          </div>
        </div>

        <div className="form">
          {/* ── Name ── */}
          <label className="label">
            Name *
            <input
              className="input"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="What should we call you?"
            />
          </label>

          {/* ── Gender & Age ── */}
          <div className="grid2">
            <label className="label">
              Gender
              <select
                className="select"
                value={gender}
                onChange={e => {
                  setGender(e.target.value)
                  if (e.target.value !== 'Female') setFemaleOnly(false)
                }}
              >
                {GENDER_OPTIONS.map(g => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            </label>
            <label className="label">
              Age
              <input
                className="input"
                type="number"
                value={age}
                onChange={e => setAge(e.target.value)}
                placeholder="Optional"
                min={13}
                max={120}
              />
            </label>
          </div>

          {/* ── City ── */}
          <label className="label">
            City *
            <select
              className="select"
              value={city}
              onChange={e => setCity(e.target.value)}
            >
              {CITY_OPTIONS.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </label>

          {/* ── Activity Interest ── */}
          <div>
            <div className="sectionTitle" style={{ marginTop: 4 }}>
              Activity Interest *
            </div>
            <div className="chipRow" style={{ marginTop: 8 }}>
              <button
                type="button"
                className={runningSelected ? 'chip chipActive' : 'chip'}
                onClick={() => setRunningSelected(prev => !prev)}
              >
                🏃 Running
              </button>
            </div>
            <div className="muted comingSoon" style={{ marginTop: 8 }}>
              More activities coming soon…
            </div>
          </div>

          {/* ── Running Details (conditional) ── */}
          {runningSelected && (
            <div className="runningDetails">
              {/* Running Level */}
              <div>
                <div className="sectionTitle">Running Level *</div>
                <div className="muted" style={{ marginBottom: 8 }}>
                  Select your experience level
                </div>
                <div className="chipRow">
                  {EXPERIENCE_LEVELS.map(lvl => (
                    <button
                      key={lvl.value}
                      type="button"
                      className={experience === lvl.value ? 'chip chipActive chipWithDesc' : 'chip chipWithDesc'}
                      onClick={() => setExperience(lvl.value)}
                    >
                      <span className="chipLabel">{lvl.label}</span>
                      <span className="chipDesc">{lvl.desc}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Pace Range */}
              <div>
                <div className="sectionTitle">Pace Range</div>
                <div className="chipRow">
                  {PACE_OPTIONS.map(p => (
                    <button
                      key={p.value}
                      type="button"
                      className={paceRange === p.value ? 'chip chipActive' : 'chip'}
                      onClick={() => setPaceRange(prev => prev === p.value ? '' : p.value)}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Typical Distance */}
              <div>
                <div className="sectionTitle">Typical Distance</div>
                <div className="chipRow">
                  {DISTANCE_OPTIONS.map(d => (
                    <button
                      key={d.value}
                      type="button"
                      className={typicalDistance === d.value ? 'chip chipActive' : 'chip'}
                      onClick={() => setTypicalDistance(prev => prev === d.value ? '' : d.value)}
                    >
                      {d.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="sectionDivider" />

              {/* Availability */}
              <div>
                <div className="sectionTitle">When are you usually free?</div>
                <div className="muted" style={{ marginBottom: 8 }}>
                  Optional — helps us find the best times for you
                </div>
                <div className="chipRow">
                  {AVAILABILITY_SLOTS.map(slot => (
                    <button
                      key={slot.key}
                      type="button"
                      className={availability[slot.key] ? 'chip chipActive chipWithDesc' : 'chip chipWithDesc'}
                      onClick={() => toggleAvailability(slot.key)}
                    >
                      <span className="chipLabel">{slot.label}</span>
                      <span className="chipDesc">{slot.time}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="sectionDivider" />

              {/* Running Preferences */}
              <div>
                <div className="sectionTitle">Running Preferences</div>
                <div className="muted" style={{ marginBottom: 8 }}>
                  Optional
                </div>

                <div style={{ marginBottom: 12 }}>
                  <div className="label" style={{ marginBottom: 6 }}>How often do you run?</div>
                  <div className="chipRow">
                    {FREQUENCY_OPTIONS.map(f => (
                      <button
                        key={f.value}
                        type="button"
                        className={weeklyFrequency === f.value ? 'chip chipActive' : 'chip'}
                        onClick={() => setWeeklyFrequency(prev => prev === f.value ? '' : f.value)}
                      >
                        {f.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="label" style={{ marginBottom: 6 }}>What type of running?</div>
                  <div className="chipRow">
                    {RUN_TYPE_OPTIONS.map(rt => (
                      <button
                        key={rt.value}
                        type="button"
                        className={runTypes.includes(rt.value) ? 'chip chipActive' : 'chip'}
                        onClick={() => toggleRunType(rt.value)}
                      >
                        {rt.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Female Only */}
              {gender === 'Female' && (
                <>
                  <div className="sectionDivider" />
                  <label className="checkboxLabel">
                    <input
                      type="checkbox"
                      checked={femaleOnly}
                      onChange={e => setFemaleOnly(e.target.checked)}
                    />
                    Female only — I prefer to run with other women
                  </label>
                </>
              )}
            </div>
          )}
        </div>

        <div className="row spaceBetween" style={{ marginTop: 16 }}>
          <div className="hint">* Required</div>
          <button
            className="btn"
            onClick={onFinish}
            type="button"
            disabled={!canFinish || saving}
          >
            {saving ? 'Saving...' : 'Get Started'}
          </button>
        </div>
        {error && <div className="error" style={{ color: '#e74c3c', marginTop: 8, textAlign: 'right' }}>{error}</div>}
      </div>
    </div>
  )
}
