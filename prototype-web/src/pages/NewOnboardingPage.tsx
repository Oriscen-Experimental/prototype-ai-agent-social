import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useOnboarding } from '../lib/useOnboarding.ts'
import { useAuth } from '../lib/AuthContext.tsx'

const HOBBY_OPTIONS = [
  'Running', 'Hiking', 'Cooking', 'Reading', 'Gaming', 'Photography',
  'Music', 'Movies', 'Travel', 'Fitness', 'Yoga', 'Dancing', 'Painting',
  'Coffee', 'Board Games', 'Swimming', 'Cycling', 'Tennis', 'Basketball',
  'Volunteering', 'Writing', 'Podcasts', 'Gardening', 'Meditation',
]

const GENDER_OPTIONS = ['Male', 'Female', 'Non-binary', 'Prefer not to say']

export function NewOnboardingPage() {
  const navigate = useNavigate()
  const { isCompleted, complete } = useOnboarding()
  const { user } = useAuth()

  const [name, setName] = useState(user?.displayName ?? '')
  const [gender, setGender] = useState('Prefer not to say')
  const [age, setAge] = useState('')
  const [selectedHobbies, setSelectedHobbies] = useState<string[]>([])
  const [otherHobbies, setOtherHobbies] = useState('')

  if (isCompleted) {
    return <Navigate to="/app" replace />
  }

  const canFinish = name.trim().length > 0 && selectedHobbies.length > 0

  const toggleHobby = (hobby: string) => {
    setSelectedHobbies(prev =>
      prev.includes(hobby) ? prev.filter(h => h !== hobby) : [...prev, hobby]
    )
  }

  const onFinish = () => {
    const customHobbies = otherHobbies
      .split(',')
      .map(s => s.trim())
      .filter(Boolean)

    complete({
      name: name.trim(),
      gender,
      age: age.trim(),
      city: '',
      address: '',
      interests: [...selectedHobbies, ...customHobbies],
    })
    navigate('/app')
  }

  return (
    <div className="centerWrap">
      <div className="panel onboardingPanel">
        <div className="panelHeader">
          <div className="h1">Tell us about yourself</div>
          <div className="muted" style={{ marginTop: 6 }}>
            This helps us personalize your experience.
          </div>
        </div>

        <div className="form">
          <label className="label">
            Name *
            <input
              className="input"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="What should we call you?"
            />
          </label>

          <div className="grid2">
            <label className="label">
              Gender
              <select
                className="select"
                value={gender}
                onChange={e => setGender(e.target.value)}
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

          <div>
            <div className="sectionTitle" style={{ marginTop: 4 }}>
              Hobbies &amp; Interests *
            </div>
            <div className="muted" style={{ marginBottom: 10 }}>
              Select all that apply
            </div>
            <div className="chipRow hobbyGrid">
              {HOBBY_OPTIONS.map(h => (
                <button
                  key={h}
                  type="button"
                  className={selectedHobbies.includes(h) ? 'chip chipActive' : 'chip'}
                  onClick={() => toggleHobby(h)}
                >
                  {h}
                </button>
              ))}
            </div>
          </div>

          <label className="label">
            Other interests
            <input
              className="input"
              value={otherHobbies}
              onChange={e => setOtherHobbies(e.target.value)}
              placeholder="e.g., Surfing, Rock climbing (comma-separated)"
            />
          </label>
        </div>

        <div className="row spaceBetween" style={{ marginTop: 16 }}>
          <div className="hint">* Required</div>
          <button
            className="btn"
            onClick={onFinish}
            type="button"
            disabled={!canFinish}
          >
            Get Started
          </button>
        </div>
      </div>
    </div>
  )
}
